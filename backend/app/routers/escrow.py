"""Escrow Router"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc, func
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from app.database import get_db
from app.models import EscrowDeal, EscrowMessage, EscrowInvite, EscrowStatus, User, UserRole, ModAction, AppSettings
from app.ledger import record_balance_change, commit_and_broadcast, ACCOUNT_PENDING
from app.money import apply_percent, to_money, ZERO
from app.auth import get_current_active_user, get_current_verified_user, get_current_moderator, block_if_impersonating
from app.dependencies import limiter
from app.schemas import EscrowMessageCreate, EscrowDealResponse, EscrowMessageResponse, EscrowResolveRequest
from app.telegram import create_notification
from app.sanitize import sanitize_content
from app.routers.forum_helpers import _award_xp, public_name

router = APIRouter(prefix="/api/escrow", tags=["Escrow"])


def _deal_to_response(deal, include_messages=False):
    resp = EscrowDealResponse(
        id=deal.id,
        buyer_id=deal.buyer_id,
        seller_id=deal.seller_id,
        buyer_username=public_name(deal.buyer) if deal.buyer else None,
        seller_username=public_name(deal.seller) if deal.seller else None,
        title=deal.title,
        description=deal.description,
        amount=deal.amount,
        status=deal.status.value if isinstance(deal.status, EscrowStatus) else deal.status,
        dispute_reason=deal.dispute_reason,
        dispute_by_id=deal.dispute_by_id,
        dispute_by_username=public_name(deal.dispute_by) if deal.dispute_by else None,
        resolution_note=deal.resolution_note,
        resolved_by_id=deal.resolved_by_id,
        resolved_by_username=public_name(deal.resolved_by) if deal.resolved_by else None,
        hold_days=deal.hold_days,
        hold_ends_at=deal.hold_ends_at.isoformat() if deal.hold_ends_at else None,
        fee_amount=deal.fee_amount or 0.0,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
        completed_at=deal.completed_at,
    )
    if include_messages and deal.messages:
        resp.messages = [
            EscrowMessageResponse(
                id=m.id, deal_id=m.deal_id, sender_id=m.sender_id,
                sender_username=public_name(m.sender) if m.sender else None,
                content=m.content, is_system=m.is_system, created_at=m.created_at,
            )
            for m in deal.messages
        ]
    return resp


async def _add_system_message(db: AsyncSession, deal_id: int, content: str):
    # sender_id is an FK to users.id; there is no user 0, so a literal 0 violates
    # the FK and rolls back the whole transaction on Postgres (SQLite doesn't
    # enforce FKs, which is why tests missed it). System messages have no sender.
    msg = EscrowMessage(deal_id=deal_id, sender_id=None, content=content, is_system=True)
    db.add(msg)


async def _notify(db: AsyncSession, user_id: int, title: str, body: str, deal_id: int):
    """Create a notification and commit it immediately."""
    await create_notification(db, user_id=user_id, type="escrow", title=title, body=body, link=f"/escrow/{deal_id}")
    await db.commit()


async def _get_deal_locked(db: AsyncSession, deal_id: int):
    """Load a deal under a row lock (SELECT ... FOR UPDATE).

    Every status transition / money movement must go through this so concurrent
    requests on the same deal serialize and re-check status under the lock —
    otherwise two callers can both pass a stale status check and release or fund
    a deal twice. Read-only handlers may use db.get instead.
    """
    result = await db.execute(
        select(EscrowDeal).where(EscrowDeal.id == deal_id).with_for_update()
    )
    return result.scalar_one_or_none()


@router.get("/deals")
async def list_deals(user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    q = (
        select(EscrowDeal)
        .options(selectinload(EscrowDeal.buyer), selectinload(EscrowDeal.seller))
        .where(or_(EscrowDeal.buyer_id == user.id, EscrowDeal.seller_id == user.id))
        .order_by(desc(EscrowDeal.updated_at))
    )
    result = await db.execute(q)
    deals = result.scalars().all()
    return [_deal_to_response(d) for d in deals]


@router.get("/deals/{deal_id}", response_model=EscrowDealResponse)
async def get_deal(deal_id: int, user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    q = (
        select(EscrowDeal)
        .options(
            selectinload(EscrowDeal.buyer),
            selectinload(EscrowDeal.seller),
            selectinload(EscrowDeal.dispute_by),
            selectinload(EscrowDeal.resolved_by),
            selectinload(EscrowDeal.messages).selectinload(EscrowMessage.sender),
        )
        .where(EscrowDeal.id == deal_id)
    )
    result = await db.execute(q)
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")
    is_staff = user.role in (UserRole.ADMIN, UserRole.MODERATOR)
    if deal.buyer_id != user.id and deal.seller_id != user.id and not is_staff:
        raise HTTPException(403, "Not authorized")
    return _deal_to_response(deal, include_messages=True)


# NOTE: there is no /accept endpoint — deals are created already-ACCEPTED via the
# invite flow (accept_escrow_invite below). PENDING is no longer a reachable state.


@router.post("/deals/{deal_id}/fund")
async def fund_deal(deal_id: int, user: User = Depends(get_current_verified_user), _imp: User = Depends(block_if_impersonating), db: AsyncSession = Depends(get_db)):
    deal = await _get_deal_locked(db, deal_id)
    if not deal: raise HTTPException(404, "Deal not found")
    if deal.buyer_id != user.id: raise HTTPException(403, "Only the buyer can fund")
    if deal.status != EscrowStatus.ACCEPTED: raise HTTPException(400, "Deal must be accepted first")

    buyer_result = await db.execute(select(User).where(User.id == user.id).with_for_update())
    buyer = buyer_result.scalar_one()
    if to_money(buyer.balance) < to_money(deal.amount): raise HTTPException(400, "Insufficient balance")

    settings_result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    settings = settings_result.scalar_one_or_none()
    if not settings: settings = AppSettings(id=1)

    fee = apply_percent(deal.amount, settings.escrow_fee_percent or 0)
    net = deal.amount - fee

    record_balance_change(
        db, buyer, delta=-deal.amount, entry_type="escrow_fund",
        ref_type="escrow_deal", ref_id=deal.id,
        description=f"Funded escrow: {deal.title}",
    )
    record_balance_change(
        db, buyer, delta=net, account=ACCOUNT_PENDING, entry_type="escrow_hold",
        ref_type="escrow_deal", ref_id=deal.id,
        description=f"Escrow hold: {deal.title}",
    )
    buyer.total_escrow_fees = to_money(buyer.total_escrow_fees) + fee
    deal.fee_amount = fee
    deal.status = EscrowStatus.FUNDED
    if deal.hold_days:
        deal.hold_ends_at = datetime.utcnow() + timedelta(days=deal.hold_days)

    await _add_system_message(db, deal.id, f"Buyer funded ${deal.amount:.2f}. Hold period: {deal.hold_days}d. Fee: ${fee:.2f}.")
    await commit_and_broadcast(db)
    await db.refresh(deal, ["seller"])
    await _notify(db, deal.seller_id, "Escrow Funded", f"@{public_name(user)} funded ${deal.amount:.2f} for: {deal.title}", deal.id)
    return {"status": "funded"}


@router.post("/deals/{deal_id}/deliver")
async def mark_delivered(deal_id: int, user: User = Depends(get_current_active_user), _imp: User = Depends(block_if_impersonating), db: AsyncSession = Depends(get_db)):
    deal = await _get_deal_locked(db, deal_id)
    if not deal: raise HTTPException(404, "Deal not found")
    if deal.seller_id != user.id: raise HTTPException(403, "Only the seller can mark as delivered")
    if deal.status != EscrowStatus.FUNDED: raise HTTPException(400, "Deal must be funded first")
    deal.status = EscrowStatus.DELIVERED
    await _add_system_message(db, deal.id, f"Marked as delivered by @{public_name(user)}")
    await db.commit()
    await db.refresh(deal, ["buyer"])
    await _notify(db, deal.buyer_id, "Seller Delivered", f"@{public_name(user)} marked deal as delivered: {deal.title}", deal.id)
    return {"status": "delivered"}


@router.post("/deals/{deal_id}/complete")
async def complete_deal(deal_id: int, user: User = Depends(get_current_active_user), _imp: User = Depends(block_if_impersonating), db: AsyncSession = Depends(get_db)):
    deal = await _get_deal_locked(db, deal_id)
    if not deal: raise HTTPException(404, "Deal not found")
    if deal.buyer_id != user.id: raise HTTPException(403, "Only the buyer can confirm completion")
    if deal.status != EscrowStatus.DELIVERED: raise HTTPException(400, "Deal must be marked as delivered first")

    buyer_result = await db.execute(select(User).where(User.id == deal.buyer_id).with_for_update())
    buyer = buyer_result.scalar_one()
    seller_result = await db.execute(select(User).where(User.id == deal.seller_id).with_for_update())
    seller = seller_result.scalar_one()

    net = deal.amount - deal.fee_amount
    record_balance_change(
        db, buyer, delta=-net, account=ACCOUNT_PENDING, clamp_zero=True,
        entry_type="escrow_release_hold", ref_type="escrow_deal", ref_id=deal.id,
        description=f"Escrow released: {deal.title}",
    )
    record_balance_change(
        db, seller, delta=net, entry_type="escrow_payout",
        ref_type="escrow_deal", ref_id=deal.id,
        description=f"Escrow payout: {deal.title}",
    )
    deal.status = EscrowStatus.COMPLETED
    deal.completed_at = datetime.utcnow()
    await _add_system_message(db, deal.id, f"Deal completed. ${net:.2f} released to @{public_name(seller)}")
    await _award_xp(db, buyer, 25)
    await _award_xp(db, seller, 25)
    await commit_and_broadcast(db)
    await _notify(db, deal.seller_id, "Deal Completed", f"@{public_name(user)} confirmed delivery. ${net:.2f} released to your balance.", deal.id)
    return {"status": "completed"}


@router.post("/deals/{deal_id}/dispute")
async def dispute_deal(deal_id: int, data: EscrowMessageCreate, user: User = Depends(get_current_active_user), _imp: User = Depends(block_if_impersonating), db: AsyncSession = Depends(get_db)):
    deal = await _get_deal_locked(db, deal_id)
    if not deal: raise HTTPException(404, "Deal not found")
    if deal.buyer_id != user.id and deal.seller_id != user.id: raise HTTPException(403, "Not authorized")
    if deal.status not in (EscrowStatus.FUNDED, EscrowStatus.DELIVERED): raise HTTPException(400, "Can only dispute funded or delivered deals")
    deal.status = EscrowStatus.DISPUTED
    deal.dispute_reason = sanitize_content(data.content)
    deal.dispute_by_id = user.id
    await _add_system_message(db, deal.id, f"Dispute opened by @{public_name(user)}: {sanitize_content(data.content)}")
    await db.commit()
    await db.refresh(deal, ["buyer", "seller"])
    other_id = deal.seller_id if user.id == deal.buyer_id else deal.buyer_id
    await _notify(db, other_id, "Dispute Opened", f"@{public_name(user)} opened a dispute on: {deal.title}", deal.id)
    return {"status": "disputed"}


@router.post("/deals/{deal_id}/cancel")
async def cancel_deal(deal_id: int, user: User = Depends(get_current_active_user), _imp: User = Depends(block_if_impersonating), db: AsyncSession = Depends(get_db)):
    deal = await _get_deal_locked(db, deal_id)
    if not deal: raise HTTPException(404, "Deal not found")
    if deal.buyer_id != user.id and deal.seller_id != user.id: raise HTTPException(403, "Not authorized")
    if deal.status not in (EscrowStatus.PENDING, EscrowStatus.ACCEPTED): raise HTTPException(400, "Cannot cancel a funded deal — open a dispute instead")
    deal.status = EscrowStatus.CANCELLED
    await _add_system_message(db, deal.id, f"Deal cancelled by @{public_name(user)}")
    await db.commit()
    await db.refresh(deal, ["buyer", "seller"])
    other_id = deal.seller_id if user.id == deal.buyer_id else deal.buyer_id
    await _notify(db, other_id, "Deal Cancelled", f"@{public_name(user)} cancelled the deal: {deal.title}", deal.id)
    return {"status": "cancelled"}


@router.post("/deals/{deal_id}/messages")
async def send_message(deal_id: int, data: EscrowMessageCreate, user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    deal = await db.get(EscrowDeal, deal_id)
    if not deal: raise HTTPException(404, "Deal not found")
    is_staff = user.role in (UserRole.ADMIN, UserRole.MODERATOR)
    if deal.buyer_id != user.id and deal.seller_id != user.id and not is_staff: raise HTTPException(403, "Not authorized")
    if deal.status in (EscrowStatus.COMPLETED, EscrowStatus.CANCELLED, EscrowStatus.REFUNDED): raise HTTPException(400, "Deal is closed")

    msg = EscrowMessage(deal_id=deal_id, sender_id=user.id, content=sanitize_content(data.content))
    db.add(msg)
    await db.commit()
    await db.refresh(msg, ["sender"])
    await db.refresh(deal, ["buyer", "seller"])
    other_id = deal.seller_id if user.id == deal.buyer_id else deal.buyer_id
    await create_notification(db, user_id=other_id, type="escrow_message",
        title=f"New message from @{public_name(user)}",
        body=data.content[:150] + ("..." if len(data.content) > 150 else ""),
        link=f"/escrow/{deal_id}")
    await db.commit()
    return EscrowMessageResponse(
        id=msg.id, deal_id=msg.deal_id, sender_id=msg.sender_id,
        sender_username=public_name(msg.sender) if msg.sender else None,
        content=msg.content, is_system=msg.is_system, created_at=msg.created_at,
    )


# ---- Invite codes ----
# A shareable single-use code carrying fixed deal terms. The creator picks
# their role; the redeemer becomes the counterparty and the deal is created
# directly in ACCEPTED state (both sides have consented; buyer funds next).

from pydantic import BaseModel as _BaseModel, Field as _Field
import secrets
import string as _string

INVITE_TTL_DAYS = 7
_CODE_ALPHABET = _string.ascii_uppercase + _string.digits


class EscrowInviteCreate(_BaseModel):
    role: str = _Field(..., pattern="^(buyer|seller)$")  # the CREATOR's role
    title: str = _Field(..., min_length=1, max_length=300)
    description: str | None = _Field(None, max_length=2000)
    amount: float = _Field(..., gt=0)
    hold_days: int | None = _Field(None, ge=1, le=30)


def _invite_to_response(inv: EscrowInvite, creator: User | None = None) -> dict:
    return {
        "code": inv.code,
        "creator_name": public_name(creator or inv.creator),
        "creator_role": inv.creator_role,
        "title": inv.title,
        "description": inv.description,
        "amount": float(inv.amount),
        "hold_days": inv.hold_days,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "used": inv.used_by_id is not None,
        "deal_id": inv.deal_id,
    }


@router.post("/invites")
@limiter.limit("10/hour")
async def create_escrow_invite(
    request: Request,
    data: EscrowInviteCreate,
    user: User = Depends(get_current_verified_user),
    _imp: User = Depends(block_if_impersonating),
    db: AsyncSession = Depends(get_db),
):
    """Create a shareable invite code with fixed deal terms."""
    # A creator who will be the buyer must be able to fund the deal.
    if data.role == "buyer" and to_money(user.balance) < to_money(data.amount):
        raise HTTPException(400, f"Insufficient balance. You need ${data.amount:.2f} to act as buyer.")

    # Unique short code; retry on the (unlikely) collision.
    for _ in range(5):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        exists = await db.scalar(select(EscrowInvite.id).where(EscrowInvite.code == code))
        if not exists:
            break
    else:
        raise HTTPException(500, "Could not generate invite code, try again")

    invite = EscrowInvite(
        code=code,
        creator_id=user.id,
        creator_role=data.role,
        title=sanitize_content(data.title),
        description=sanitize_content(data.description) if data.description else None,
        amount=to_money(data.amount),
        hold_days=data.hold_days,
        expires_at=datetime.utcnow() + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return _invite_to_response(invite, creator=user)


@router.get("/invites/{code}")
async def preview_escrow_invite(
    code: str,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Preview an invite before accepting it."""
    invite = await db.scalar(
        select(EscrowInvite)
        .where(EscrowInvite.code == code.strip().upper())
        .options(selectinload(EscrowInvite.creator))
    )
    if not invite or invite.used_by_id is not None or invite.expires_at < datetime.utcnow():
        raise HTTPException(404, "Invite not found or no longer valid")
    return _invite_to_response(invite)


@router.post("/invites/{code}/accept")
@limiter.limit("10/hour")
async def accept_escrow_invite(
    request: Request,
    code: str,
    user: User = Depends(get_current_verified_user),
    _imp: User = Depends(block_if_impersonating),
    db: AsyncSession = Depends(get_db),
):
    """Redeem an invite: creates the deal in ACCEPTED state (buyer funds next)."""
    # Lock the invite row so two concurrent redeems can't both pass the
    # used check and create two deals from one code.
    invite = await db.scalar(
        select(EscrowInvite)
        .where(EscrowInvite.code == code.strip().upper())
        .options(selectinload(EscrowInvite.creator))
        .with_for_update()
    )
    if not invite or invite.used_by_id is not None or invite.expires_at < datetime.utcnow():
        raise HTTPException(404, "Invite not found or no longer valid")
    if invite.creator_id == user.id:
        raise HTTPException(400, "Cannot accept your own invite")

    creator = invite.creator
    if not creator or creator.is_banned:
        raise HTTPException(400, "Invite is no longer valid")

    buyer = creator if invite.creator_role == "buyer" else user
    seller = user if invite.creator_role == "buyer" else creator

    # The buyer must be able to fund the deal now.
    if to_money(buyer.balance) < to_money(invite.amount):
        raise HTTPException(400, "Buyer has insufficient balance for this deal")

    # Both parties must be under the active-deal cap.
    settings_result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    settings = settings_result.scalar_one_or_none()
    max_deals = settings.max_active_escrow_deals if settings and settings.max_active_escrow_deals is not None else 3
    active_statuses = [EscrowStatus.PENDING, EscrowStatus.ACCEPTED, EscrowStatus.FUNDED, EscrowStatus.DELIVERED, EscrowStatus.DISPUTED]
    for party in (buyer, seller):
        active_count = await db.scalar(
            select(func.count(EscrowDeal.id)).where(
                or_(EscrowDeal.buyer_id == party.id, EscrowDeal.seller_id == party.id),
                EscrowDeal.status.in_(active_statuses),
            )
        )
        if (active_count or 0) >= max_deals:
            who = "You have" if party.id == user.id else "The other party has"
            raise HTTPException(400, f"{who} reached the maximum number of active escrow deals")

    deal = EscrowDeal(
        buyer_id=buyer.id, seller_id=seller.id,
        title=invite.title, description=invite.description,
        amount=invite.amount, hold_days=invite.hold_days,
        status=EscrowStatus.ACCEPTED,
    )
    db.add(deal)
    await db.flush()
    invite.used_by_id = user.id
    invite.deal_id = deal.id
    await _add_system_message(
        db, deal.id,
        f"Deal created via invite code by @{public_name(creator)}, accepted by @{public_name(user)}",
    )
    await db.commit()
    await db.refresh(deal, ["buyer", "seller"])
    await _notify(db, creator.id, "Invite Accepted",
                  f"@{public_name(user)} accepted your escrow invite: {invite.title}", deal.id)
    return _deal_to_response(deal)


# ---- Admin endpoints ----


@router.post("/deals/{deal_id}/resolve")
async def resolve_disputed_deal(
    deal_id: int,
    data: EscrowResolveRequest,
    user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    deal_result = await db.execute(
        select(EscrowDeal)
        .where(EscrowDeal.id == deal_id)
        .with_for_update()
    )
    deal = deal_result.scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")
    if deal.status != EscrowStatus.DISPUTED:
        raise HTTPException(400, "Deal is not disputed")
    # A moderator who is a party to the deal must not adjudicate their own
    # dispute (they could release the held funds to themselves).
    if user.id in (deal.buyer_id, deal.seller_id):
        raise HTTPException(403, "You cannot resolve a dispute you are party to")

    buyer_result = await db.execute(
        select(User).where(User.id == deal.buyer_id).with_for_update()
    )
    buyer = buyer_result.scalar_one()

    seller_result = await db.execute(
        select(User).where(User.id == deal.seller_id).with_for_update()
    )
    seller = seller_result.scalar_one()

    net = deal.amount - (deal.fee_amount or 0)

    if data.release_to == "seller":
        if to_money(buyer.pending_balance) < to_money(net):
            raise HTTPException(400, "Buyer has insufficient pending balance for this release")
        record_balance_change(
            db, buyer, delta=-net, account=ACCOUNT_PENDING, clamp_zero=True,
            entry_type="escrow_release_hold", ref_type="escrow_deal", ref_id=deal.id,
            description=f"Dispute released to seller: {deal.title}",
        )
        record_balance_change(
            db, seller, delta=net, entry_type="escrow_payout",
            ref_type="escrow_deal", ref_id=deal.id,
            description=f"Dispute payout: {deal.title}",
        )
        deal.status = EscrowStatus.COMPLETED
        system_msg = f"Dispute resolved by moderator @{public_name(user)}. Funds released to seller @{public_name(seller)}."
        await _award_xp(db, buyer, 25)
        await _award_xp(db, seller, 25)
    else:
        if to_money(buyer.pending_balance) < to_money(net):
            raise HTTPException(400, "Buyer has insufficient pending balance for refund")
        record_balance_change(
            db, buyer, delta=-net, account=ACCOUNT_PENDING, clamp_zero=True,
            entry_type="escrow_release_hold", ref_type="escrow_deal", ref_id=deal.id,
            description=f"Dispute refund hold release: {deal.title}",
        )
        # Refund the full amount (buyer is made whole on a refund). The escrow
        # fee was recorded against total_escrow_fees at funding; since the buyer
        # is fully refunded the platform did not actually earn it, so reverse the
        # stat to keep fee accounting consistent.
        record_balance_change(
            db, buyer, delta=deal.amount, entry_type="escrow_refund",
            ref_type="escrow_deal", ref_id=deal.id,
            description=f"Dispute refund: {deal.title}",
        )
        fee_amt = to_money(deal.fee_amount)
        if fee_amt:
            buyer.total_escrow_fees = max(ZERO, to_money(buyer.total_escrow_fees) - fee_amt)
        deal.status = EscrowStatus.REFUNDED
        system_msg = f"Dispute resolved by moderator @{public_name(user)}. Funds refunded to buyer @{public_name(buyer)}."

    deal.resolved_by_id = user.id
    deal.resolution_note = data.note
    deal.completed_at = datetime.utcnow()

    await _add_system_message(db, deal.id, system_msg)

    mod_action = ModAction(
        moderator_id=user.id,
        target_user_id=deal.seller_id if data.release_to == "buyer" else deal.buyer_id,
        action_type="escrow_resolve",
        reason=f"Deal #{deal_id}: Funds released to {data.release_to}. Note: {data.note or '(none)'}",
    )
    db.add(mod_action)

    await commit_and_broadcast(db)
    await db.refresh(deal, ["buyer", "seller", "dispute_by", "resolved_by"])

    outcome = data.release_to
    await _notify(db, deal.buyer_id, "Dispute Resolved",
                  f"Moderator @{public_name(user)} resolved the dispute on: {deal.title}. Outcome: {outcome}.", deal.id)
    await _notify(db, deal.seller_id, "Dispute Resolved",
                  f"Moderator @{public_name(user)} resolved the dispute on: {deal.title}. Outcome: {outcome}.", deal.id)

    return {"status": deal.status.value}
