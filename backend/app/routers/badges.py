"""Badge System API Router"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
import os
import uuid

from app.database import get_db
from app.auth import get_current_active_user, get_current_admin, block_if_impersonating
from app.dependencies import limiter
from app.models import User, Badge, UserBadge, UserRole
from app.ledger import record_balance_change, commit_and_broadcast
from app.money import to_money, ZERO
from app.schemas import (
    BadgeCreate, BadgeUpdate, BadgeResponse,
    UserBadgeResponse, SuccessResponse,
)
from app.telegram import create_notification
from app.routers.forum_helpers import bump_level
from app import badge_service

router = APIRouter(prefix="/api/badges", tags=["Badges"])

ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "badges")
os.makedirs(ICONS_DIR, exist_ok=True)
# SVG removed: it can carry <script> and become stored XSS when served same-origin.
ALLOWED_ICON_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_ICON_SIZE = 512 * 1024  # 512 KB


# ============================================================================
# PUBLIC ENDPOINTS
# ============================================================================

@router.get("", response_model=List[BadgeResponse])
async def list_badges(
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all badges"""
    query = select(Badge).order_by(Badge.sort_order, Badge.name)
    
    if not include_inactive or current_user.role.value not in ("moderator", "admin"):
        query = query.where(Badge.is_active == True)
    
    result = await db.execute(query)
    badges = result.scalars().all()
    
    return badges


@router.get("/shop", response_model=List[BadgeResponse])
async def list_purchasable_badges(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List purchasable badges"""
    query = (
        select(Badge)
        .where(
            Badge.is_active == True,
            Badge.is_purchasable == True,
        )
        .order_by(Badge.price, Badge.name)
    )
    
    result = await db.execute(query)
    badges = result.scalars().all()
    
    # Filter out badges user already has (unless multi_purchase)
    user_badge_ids = await db.execute(
        select(UserBadge.badge_id).where(UserBadge.user_id == current_user.id)
    )
    owned_ids = {row.badge_id for row in user_badge_ids}
    
    return [b for b in badges if b.id not in owned_ids or b.multi_purchase]


@router.get("/my", response_model=List[UserBadgeResponse])
async def list_my_badges(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(UserBadge)
        .where(UserBadge.user_id == current_user.id)
        .options(selectinload(UserBadge.badge))
        .order_by(UserBadge.acquired_at.desc())
    )
    user_badges = result.scalars().all()
    return [
        UserBadgeResponse(
            id=ub.id,
            badge=ub.badge,
            is_primary=ub.is_primary,
            acquired_at=ub.acquired_at,
            acquired_type=ub.acquired_type,
            quantity=ub.quantity or 1,
        )
        for ub in user_badges
    ]


@router.post("/{badge_id}/purchase", response_model=UserBadgeResponse)
@limiter.limit("10/minute")
async def purchase_badge(
    request: Request,
    badge_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _imp: User = Depends(block_if_impersonating),
):
    """Purchase a badge"""
    # Lock the badge row so the limited-supply check and increment below are
    # serialized — otherwise two concurrent buyers can both pass the
    # `current_supply >= max_supply` check and oversell a limited badge.
    result = await db.execute(
        select(Badge).where(Badge.id == badge_id, Badge.is_active == True).with_for_update()
    )
    badge = result.scalar_one_or_none()

    if not badge:
        raise HTTPException(status_code=404, detail="Badge not found")
    
    if not badge.is_purchasable:
        raise HTTPException(status_code=400, detail="Badge is not purchasable")
    
    # Check if user already has this badge
    existing_result = await db.execute(
        select(UserBadge).where(
            UserBadge.user_id == current_user.id,
            UserBadge.badge_id == badge_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    
    if existing and not badge.multi_purchase:
        raise HTTPException(status_code=400, detail="You already own this badge")
    
    if existing and badge.multi_purchase:
        if badge.is_limited:
            if badge.max_supply and badge.current_supply >= badge.max_supply:
                raise HTTPException(status_code=400, detail="Badge sold out")
    
    # Check limited edition availability for new purchases
    if not existing and badge.is_limited:
        if badge.max_supply and badge.current_supply >= badge.max_supply:
            raise HTTPException(status_code=400, detail="Badge sold out")
    
    # Lock user row to prevent race conditions
    user_result = await db.execute(
        select(User).where(User.id == current_user.id).with_for_update()
    )
    user = user_result.scalar_one()
    
    price = max(ZERO, to_money(badge.price))
    if to_money(user.balance) < price:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # Deduct balance (floored at 0 — a negative configured price must never credit)
    record_balance_change(
        db, user, delta=-price, entry_type="badge_purchase",
        ref_type="badge", ref_id=badge.id, description=f"Purchased badge: {badge.name}",
    )

    # Update badge supply
    badge.current_supply = (badge.current_supply or 0) + 1
    
    # Create or increment user badge
    if existing and badge.multi_purchase:
        existing.quantity = (existing.quantity or 1) + 1
        user_badge = existing
    else:
        user_badge = UserBadge(
            user_id=current_user.id,
            badge_id=badge_id,
            acquired_type="purchase",
        )
        db.add(user_badge)
    
    # Grant purchase rewards
    reward_parts = []
    
    if (badge.reward_xp or 0) > 0:
        user.xp = (user.xp or 0) + badge.reward_xp
        reward_parts.append(f"+{badge.reward_xp} XP")
        bump_level(user)
    
    if (badge.reward_balance or 0) > 0:
        record_balance_change(
            db, user, delta=badge.reward_balance, entry_type="badge_reward",
            ref_type="badge", ref_id=badge.id, description=f"Badge reward: {badge.name}",
        )
        reward_parts.append(f"+${badge.reward_balance:.2f}")
    
    if badge.reward_role:
        try:
            new_role = UserRole(badge.reward_role.upper())
            # A self-service purchase must never grant staff privileges. Even if a
            # badge is (mis)configured with reward_role=MODERATOR/ADMIN, buying it
            # only ever upgrades a TRIAL account to USER. Staff roles are granted
            # exclusively through the admin role endpoint.
            if new_role not in (UserRole.TRIAL, UserRole.MODERATOR, UserRole.ADMIN):
                user.role = new_role
                reward_parts.append(f"Role upgraded to {new_role.value}")
        except ValueError:
            pass

    # Owning the Premium badge IS premium — keep the flag in sync no matter which
    # purchase path granted the badge, so cosmetic perks always come with it.
    if badge.name == badge_service.PREMIUM_BADGE_NAME and not user.is_premium:
        user.is_premium = True
        user.premium_until = None
        reward_parts.append("Premium unlocked")

    # Create notification before commit so it's included in the transaction
    reward_text = " | ".join(reward_parts) if reward_parts else ""
    await create_notification(
        db,
        user_id=current_user.id,
        type="badge",
        title=f"Badge purchased: {badge.name}!",
        body=(badge.description or f"You purchased the '{badge.name}' badge!") + (f"\n{reward_text}" if reward_text else ""),
        link=f"/profile/{current_user.id}",
    )

    await commit_and_broadcast(db)
    await db.refresh(user_badge)
    
    return UserBadgeResponse(
        id=user_badge.id,
        badge=badge,
        is_primary=user_badge.is_primary,
        acquired_at=user_badge.acquired_at,
        acquired_type=user_badge.acquired_type,
        quantity=user_badge.quantity or 1,
    )


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.post("/upload-icon")
@limiter.limit("20/minute")
async def upload_badge_icon(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_admin),
):
    """Upload a badge icon (admin only)"""
    if file.content_type not in ALLOWED_ICON_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: PNG, JPEG, WebP, GIF")

    contents = await file.read()
    if len(contents) > MAX_ICON_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 512KB)")

    # Verify the real file type from magic bytes — the client Content-Type and
    # filename are attacker-controlled and must not decide what we store/serve.
    from app.images import validated_image_extension
    ext = validated_image_extension(contents)
    if not ext:
        raise HTTPException(status_code=400, detail="File is not a valid PNG, JPEG, WebP, or GIF image")

    filename = f"badge_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(ICONS_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    return {"url": f"/api/uploads/badges/{filename}"}


@router.post("", response_model=BadgeResponse)
async def create_badge(
    data: BadgeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Create a new badge (admin only)"""
    return await badge_service.create_badge(db, data)


@router.put("/{badge_id}", response_model=BadgeResponse)
async def update_badge(
    badge_id: int,
    data: BadgeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Update a badge (admin only)"""
    return await badge_service.update_badge(db, badge_id, data)


@router.post("/{badge_id}/award/{user_id}", response_model=UserBadgeResponse)
async def award_badge(
    badge_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Award a badge to a user (admin only)"""
    # Get badge (locked so concurrent awards/purchases don't oversell supply)
    badge = await db.execute(select(Badge).where(Badge.id == badge_id).with_for_update())
    badge = badge.scalar_one_or_none()
    
    if not badge:
        raise HTTPException(status_code=404, detail="Badge not found")
    
    # Get user
    user = await db.execute(select(User).where(User.id == user_id))
    user = user.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user already has this badge
    existing = await db.execute(
        select(UserBadge).where(
            UserBadge.user_id == user_id,
            UserBadge.badge_id == badge_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already has this badge")
    
    # Create user badge
    user_badge = UserBadge(
        user_id=user_id,
        badge_id=badge_id,
        acquired_type="admin",
    )
    db.add(user_badge)
    
    # Update supply if limited
    if badge.is_limited:
        badge.current_supply = (badge.current_supply or 0) + 1
    
    await db.commit()
    await db.refresh(user_badge)
    
    return UserBadgeResponse(
        id=user_badge.id,
        badge=badge,
        is_primary=user_badge.is_primary,
        acquired_at=user_badge.acquired_at,
        acquired_type=user_badge.acquired_type,
        quantity=user_badge.quantity or 1,
    )


