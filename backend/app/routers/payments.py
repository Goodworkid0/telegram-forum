"""Payments Router (NowPayments)"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
import json
import hmac
import hashlib
import httpx
from datetime import datetime

from app.database import get_db
from app.auth import get_current_active_user, block_if_impersonating
from app.models import User, CryptoDeposit, AppSettings
from app.ledger import record_balance_change, commit_and_broadcast
from app.money import to_money, apply_percent
from app.telegram import create_notification
from app.routers.forum_helpers import public_name
from app.schemas import CreateCryptoDeposit, CryptoDepositResponse, CryptoDepositStatus, CryptoDepositItem, CoinInfo
from app.nowpayments import (
    fetch_available_coins, fetch_min_usd, coin_display, resolve_enabled, DEFAULT_COINS,
)

from app.dependencies import limiter

router = APIRouter()

NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY", "")
NOWPAYMENTS_IPN_SECRET = os.getenv("NOWPAYMENTS_IPN_SECRET", "")
NOWPAYMENTS_BASE_URL = os.getenv("NOWPAYMENTS_BASE_URL", "https://api.nowpayments.io/v1")
NOWPAYMENTS_IPN_URL = os.getenv("NOWPAYMENTS_IPN_URL", "")

async def _get_settings(db: AsyncSession):
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    return result.scalar_one_or_none()


async def _resolve_enabled_coins(db: AsyncSession) -> list[str]:
    """The deposit coins currently offered: admin-curated set ∩ account-available."""
    available = await fetch_available_coins()
    settings = await _get_settings(db)
    curated_csv = settings.enabled_deposit_coins if settings else None
    return resolve_enabled(curated_csv, available)


def _verify_signature(raw_body: bytes, signature: str) -> bool:
    if not NOWPAYMENTS_IPN_SECRET or not signature:
        return False
    expected = hmac.new(
        NOWPAYMENTS_IPN_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _distribute_referral_commissions(db: AsyncSession, depositor: User, amount: float):
    """Pay multi-level referral commissions on a deposit.
    Level 1 (direct referrer): referral_level1_percent (default 3%)
    Level 2 (referrer's referrer): referral_level2_percent (default 5%)
    """
    if amount <= 0:
        return

    referral_settings = await _get_referral_settings(db)
    if not referral_settings.get("enabled", True):
        return

    level1_pct = float(referral_settings.get("level1_percent", 3.0))
    level2_pct = float(referral_settings.get("level2_percent", 5.0))

    from datetime import timedelta as _td
    now = datetime.utcnow()
    min_age = now - _td(days=7)

    # Level 1: direct referrer
    if depositor.referred_by_id:
        l1_result = await db.execute(
            select(User).where(User.id == depositor.referred_by_id).with_for_update()
        )
        l1 = l1_result.scalar_one_or_none()
        if l1 and l1.created_at and l1.created_at <= min_age:
            l1_commission = apply_percent(amount, level1_pct)
            if l1_commission > 0:
                record_balance_change(
                    db, l1, delta=l1_commission, entry_type="referral_commission",
                    ref_type="user", ref_id=depositor.id,
                    description=f"L1 referral commission from @{public_name(depositor)}",
                )
                l1.referral_earnings = to_money(l1.referral_earnings) + l1_commission
                await create_notification(
                    db, user_id=l1.id, type="referral_bonus",
                    title=f"Referral commission: +${l1_commission:.2f}",
                    body=f"Your referral made a deposit of ${amount:.2f}. You earned {level1_pct}%.",
                    link="/profile", telegram_id=l1.telegram_id,
                )

                # Level 2: referrer's referrer
                if l1.referred_by_id:
                    l2_result = await db.execute(
                        select(User).where(User.id == l1.referred_by_id).with_for_update()
                    )
                    l2 = l2_result.scalar_one_or_none()
                    if l2 and l2.created_at and l2.created_at <= min_age:
                        l2_commission = apply_percent(amount, level2_pct)
                        if l2_commission > 0:
                            record_balance_change(
                                db, l2, delta=l2_commission, entry_type="referral_commission",
                                ref_type="user", ref_id=depositor.id,
                                description=f"L2 referral commission from @{public_name(depositor)}",
                            )
                            l2.referral_earnings = to_money(l2.referral_earnings) + l2_commission
                            await create_notification(
                                db, user_id=l2.id, type="referral_bonus",
                                title=f"Referral commission: +${l2_commission:.2f}",
                                body=f"Your referral's referral made a deposit of ${amount:.2f}. You earned {level2_pct}%.",
                                link="/profile", telegram_id=l2.telegram_id,
                            )


async def _get_referral_settings(db: AsyncSession) -> dict:
    """Get referral settings from AppSettings."""
    from app.models import AppSettings
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    settings = result.scalar_one_or_none()
    if not settings:
        return {"enabled": True, "level1_percent": 3.0, "level2_percent": 5.0}
    return {
        "enabled": settings.referral_enabled if settings.referral_enabled is not None else True,
        "level1_percent": settings.referral_level1_percent if settings.referral_level1_percent is not None else 3.0,
        "level2_percent": settings.referral_level2_percent if settings.referral_level2_percent is not None else 5.0,
    }


@router.get("/nowpayments/currencies", response_model=list[CoinInfo])
async def list_deposit_currencies(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Deposit coins offered to users: the admin-curated set, enriched with
    display metadata and each coin's USD minimum (best-effort)."""
    enabled = await _resolve_enabled_coins(db)
    out = []
    for code in enabled:
        info = coin_display(code)
        info["min_usd"] = await fetch_min_usd(code)
        out.append(info)
    return out


@router.post("/nowpayments/create", response_model=CryptoDepositResponse)
async def create_nowpayments_deposit(
    payload: CreateCryptoDeposit,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    if not NOWPAYMENTS_API_KEY:
        raise HTTPException(status_code=500, detail="NOWPAYMENTS_API_KEY not set")
    if not NOWPAYMENTS_IPN_URL:
        raise HTTPException(status_code=500, detail="NOWPAYMENTS_IPN_URL not set")

    pay_currency = payload.pay_currency.strip().lower()
    enabled = await _resolve_enabled_coins(db)
    if pay_currency not in enabled:
        raise HTTPException(status_code=400, detail="Unsupported currency")

    settings = await _get_settings(db)
    global_min = float(settings.min_deposit_amount) if settings and settings.min_deposit_amount else 10.0
    coin_min = await fetch_min_usd(pay_currency)
    effective_min = max(global_min, coin_min or 0.0)
    if payload.amount < effective_min:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum deposit for {pay_currency.upper()} is ${effective_min:.2f}",
        )

    deposit = CryptoDeposit(
        user_id=current_user.id,
        price_amount=payload.amount,
        price_currency="usd",
        price_amount_usd=payload.amount,
        payment_status="created"
    )
    db.add(deposit)
    # Flush (not commit) to obtain the autoincrement id, then stamp order_id
    # BEFORE persisting so the row is never committed without one. Otherwise a
    # failed provider call below would leave an order_id-less row that breaks the
    # admin deposits list.
    await db.flush()
    order_id = f"dep_{deposit.id}"
    deposit.order_id = order_id
    await db.commit()
    await db.refresh(deposit)

    req_payload = {
        "price_amount": payload.amount,
        "price_currency": "usd",
        "pay_currency": pay_currency,
        "ipn_callback_url": NOWPAYMENTS_IPN_URL,
        "order_id": order_id,
        "order_description": "Wallet deposit"
    }
    headers = {
        "x-api-key": NOWPAYMENTS_API_KEY,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{NOWPAYMENTS_BASE_URL}/payment", json=req_payload, headers=headers)

    if resp.status_code not in (200, 201):
        deposit.payment_status = "error"
        await db.commit()
        error_detail = "NowPayments create failed"
        try:
            err_data = resp.json()
            error_detail = err_data.get("message") or err_data.get("description") or str(err_data)
            import logging
            logging.getLogger(__name__).error(f"NowPayments error ({resp.status_code}): {err_data}")
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=error_detail)

    data = resp.json()
    deposit.payment_id = data.get("payment_id")
    deposit.pay_address = data.get("pay_address")
    deposit.pay_amount = data.get("pay_amount")
    deposit.pay_currency = data.get("pay_currency")
    deposit.payment_status = data.get("payment_status") or deposit.payment_status

    await db.commit()
    await db.refresh(deposit)

    return CryptoDepositResponse(
        deposit_id=deposit.id,
        payment_id=deposit.payment_id,
        pay_address=deposit.pay_address,
        pay_amount=deposit.pay_amount,
        pay_currency=deposit.pay_currency,
        payment_status=deposit.payment_status,
        price_amount_usd=deposit.price_amount_usd
    )


@router.post("/nowpayments/webhook")
@limiter.exempt
async def nowpayments_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    # Exempt from rate limiting: IPNs arrive in bursts from NOWPayments' small
    # IP pool and are HMAC-verified below — throttling them drops real payments.
    raw = await request.body()
    signature = request.headers.get("x-nowpayments-sig", "")
    if not _verify_signature(raw, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    payment_id = str(payload.get("payment_id") or "")
    order_id = payload.get("order_id")

    query = None
    if payment_id:
        query = select(CryptoDeposit).where(CryptoDeposit.payment_id == payment_id).with_for_update()
    elif order_id:
        query = select(CryptoDeposit).where(CryptoDeposit.order_id == order_id).with_for_update()
    else:
        raise HTTPException(status_code=400, detail="Missing payment identifiers")

    result = await db.execute(query)
    deposit = result.scalar_one_or_none()
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    deposit.payment_status = payload.get("payment_status") or deposit.payment_status
    deposit.pay_address = payload.get("pay_address") or deposit.pay_address
    deposit.pay_amount = payload.get("pay_amount") or deposit.pay_amount
    deposit.pay_currency = payload.get("pay_currency") or deposit.pay_currency
    deposit.tx_hash = payload.get("payin_hash") or deposit.tx_hash
    deposit.confirmations = payload.get("confirmations") or deposit.confirmations

    if deposit.payment_status in {"confirmed", "finished"} and not deposit.is_credited:
        # Credit based on what was ACTUALLY paid, never the user-requested USD.
        # NowPayments can mark a payment confirmed/finished for less crypto than was
        # invoiced (underpayment); crediting the requested amount would let a user
        # order $10,000, send $10 of crypto, and be credited $10,000. Scale the USD
        # credit by (actually_paid / pay_amount), capped at the requested amount.
        import logging
        audit = logging.getLogger("audit")

        def _to_float(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0.0

        actually_paid = _to_float(payload.get("actually_paid"))
        expected_pay = _to_float(payload.get("pay_amount")) or _to_float(deposit.pay_amount)

        if actually_paid <= 0 or expected_pay <= 0:
            # Settled crypto amount is unknown — refuse to credit and flag for review
            # rather than trusting the user-supplied invoice amount.
            deposit.payment_status = "needs_review"
            audit.warning(
                "deposit.credit.unverifiable deposit_id=%s payment_id=%s actually_paid=%s pay_amount=%s",
                deposit.id, deposit.payment_id, actually_paid, expected_pay,
            )
            await db.commit()
            return {"status": "ok"}

        paid_ratio = actually_paid / expected_pay
        requested_usd = to_money(deposit.price_amount_usd)
        # Cap at the invoiced amount — overpayment doesn't credit extra (handled
        # manually). Underpayment credits proportionally to what actually arrived.
        base_amount = to_money(float(requested_usd) * min(paid_ratio, 1.0))

        if base_amount <= 0:
            deposit.payment_status = "needs_review"
            audit.warning(
                "deposit.credit.zero_after_scaling deposit_id=%s requested=%s ratio=%s",
                deposit.id, requested_usd, paid_ratio,
            )
            await db.commit()
            return {"status": "ok"}

        if paid_ratio < 0.99:
            audit.warning(
                "deposit.credit.underpaid deposit_id=%s requested=%s credited=%s ratio=%s",
                deposit.id, requested_usd, base_amount, paid_ratio,
            )

        # Lock user row to prevent race conditions on balance update
        result = await db.execute(
            select(User).where(User.id == deposit.user_id).with_for_update()
        )
        user = result.scalar_one_or_none()
        if user:
            record_balance_change(
                db, user, delta=base_amount, entry_type="deposit",
                ref_type="crypto_deposit", ref_id=deposit.id,
                description=f"Crypto deposit ({deposit.pay_currency or 'crypto'})",
            )
            deposit.is_credited = True
            deposit.completed_at = datetime.utcnow()
            
            await create_notification(
                db, user_id=user.id, type="deposit_credited",
                title=f"Deposit of ${base_amount:.2f} credited",
                body=f"Your {deposit.pay_currency.upper() if deposit.pay_currency else 'crypto'} deposit has been confirmed.",
                link="/wallet", telegram_id=user.telegram_id,
            )

            # Multi-level referral commissions
            await _distribute_referral_commissions(db, user, base_amount)

    await commit_and_broadcast(db)
    return {"status": "ok"}


@router.get("/nowpayments/deposits/{deposit_id}", response_model=CryptoDepositStatus)
async def get_nowpayments_deposit_status(
    deposit_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CryptoDeposit).where(
            CryptoDeposit.id == deposit_id,
            CryptoDeposit.user_id == current_user.id
        )
    )
    deposit = result.scalar_one_or_none()
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    return CryptoDepositStatus(
        deposit_id=deposit.id,
        payment_status=deposit.payment_status,
        confirmations=deposit.confirmations or 0,
        pay_address=deposit.pay_address,
        pay_amount=deposit.pay_amount,
        pay_currency=deposit.pay_currency,
        price_amount_usd=deposit.price_amount_usd or 0.0,
        is_credited=deposit.is_credited,
        tx_hash=deposit.tx_hash
    )


@router.get("/nowpayments/deposits", response_model=list[CryptoDepositItem])
async def list_nowpayments_deposits(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CryptoDeposit)
        .where(CryptoDeposit.user_id == current_user.id)
        .order_by(CryptoDeposit.created_at.desc())
    )
    deposits = result.scalars().all()
    return [
        CryptoDepositItem(
            deposit_id=dep.id,
            payment_status=dep.payment_status,
            confirmations=dep.confirmations or 0,
            pay_amount=dep.pay_amount,
            pay_currency=dep.pay_currency,
            price_amount_usd=dep.price_amount_usd or 0.0,
            is_credited=dep.is_credited,
            tx_hash=dep.tx_hash,
            created_at=dep.created_at
        )
        for dep in deposits
    ]


# ============ Payout Webhook ============

@router.post("/premium/purchase")
async def purchase_premium(
    current_user: User = Depends(block_if_impersonating),
    db: AsyncSession = Depends(get_db),
):
    """Buy lifetime Premium.

    Grants the is_premium flag (unlocks avatar/name customization + rich
    markdown signatures), upgrades a trial account to full member (board
    access), and grants the 'Premium' badge. Permanent (no expiry).
    """
    from app.models import UserRole, UserBadge, Badge
    from app.pricing import get_price
    PREMIUM_PRICE = await get_price(db, "premium_price")

    # Lock the user row so two concurrent purchases can't both charge/grant.
    result = await db.execute(
        select(User).where(User.id == current_user.id).with_for_update()
    )
    user = result.scalar_one()

    if user.is_premium:
        raise HTTPException(status_code=400, detail="You already have Premium")

    if to_money(user.balance) < PREMIUM_PRICE:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Need ${PREMIUM_PRICE}, have ${user.balance:.2f}"
        )

    record_balance_change(
        db, user, delta=-PREMIUM_PRICE, entry_type="premium_purchase",
        description="Premium purchase",
    )

    user.is_premium = True
    user.premium_until = None  # permanent

    perks = ["profile customization", "rich signatures"]
    if user.role == UserRole.TRIAL:
        user.role = UserRole.USER
        perks.append("full board access")

    # Grant the Premium badge (idempotent) if one is configured.
    from app.badge_service import PREMIUM_BADGE_NAME
    badge = await db.scalar(select(Badge).where(Badge.name == PREMIUM_BADGE_NAME))
    if badge:
        owns = await db.scalar(
            select(UserBadge).where(
                UserBadge.user_id == user.id, UserBadge.badge_id == badge.id
            )
        )
        if not owns:
            db.add(UserBadge(user_id=user.id, badge_id=badge.id, acquired_type="purchase"))
            badge.current_supply = (badge.current_supply or 0) + 1
            perks.append("Premium badge")

    await create_notification(
        db,
        user_id=user.id,
        type="premium_purchase",
        title="Welcome to Premium!",
        body="You're now a Premium member: " + ", ".join(perks) + ".",
        link=f"/profile/{user.id}",
    )

    await commit_and_broadcast(db)

    return {"message": "Premium activated", "is_premium": True, "balance": float(user.balance)}
