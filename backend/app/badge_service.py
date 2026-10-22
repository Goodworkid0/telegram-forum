"""Canonical badge create/update/delete logic.

Used by both badge CRUD surfaces (`/api/badges` in routers/badges.py and
`/api/admin/badges` in routers/admin/catalog.py) so they can't drift. Folds in
the safer behavior each copy previously had on its own: name-uniqueness +
IntegrityError handling on create/update, and soft-delete (deactivate) when a
badge is already owned instead of a hard delete that would orphan UserBadge rows.
"""
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Badge, UserBadge

# The badge whose ownership represents Premium. Acquiring it (via the $80 Shop
# purchase OR a direct badge purchase) grants the is_premium perks, so the flag
# and the badge can't drift apart. Single source for the name.
PREMIUM_BADGE_NAME = "Premium"


def _validate_economics(is_purchasable, price, reward_balance) -> None:
    """A purchasable badge must not pay back as much as (or more than) it costs.

    Otherwise a multi_purchase badge with reward_balance >= price is an unbounded
    money printer (buy -> credited >= price -> repeat), and even a one-time badge
    would be guaranteed free money for every user. Enforced on the merged state
    so an update can't sneak the badge into that configuration either.
    """
    if is_purchasable and (reward_balance or 0) > 0 and (reward_balance or 0) >= (price or 0):
        raise HTTPException(
            status_code=400,
            detail="A purchasable badge's reward_balance must be less than its price",
        )


async def create_badge(db: AsyncSession, data) -> Badge:
    existing = await db.scalar(select(Badge).where(Badge.name == data.name))
    if existing:
        raise HTTPException(status_code=400, detail=f"Badge with name '{data.name}' already exists")
    _validate_economics(data.is_purchasable, data.price, data.reward_balance)
    badge = Badge(**data.model_dump())
    db.add(badge)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Badge with this name already exists")
    await db.refresh(badge)
    return badge


async def update_badge(db: AsyncSession, badge_id: int, data) -> Badge:
    badge = await db.scalar(select(Badge).where(Badge.id == badge_id))
    if not badge:
        raise HTTPException(status_code=404, detail="Badge not found")
    if data.name and data.name != badge.name:
        existing = await db.scalar(select(Badge).where(Badge.name == data.name))
        if existing:
            raise HTTPException(status_code=400, detail=f"Badge with name '{data.name}' already exists")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(badge, key, val)
    # Validate the merged state so an update can't introduce a money-printer config.
    _validate_economics(badge.is_purchasable, badge.price, badge.reward_balance)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Badge with this name already exists")
    await db.refresh(badge)
    return badge


async def delete_badge(db: AsyncSession, badge_id: int) -> str:
    """Delete a badge, or deactivate it if already owned (avoids orphaning
    UserBadge rows). Returns a human-readable result message."""
    badge = await db.scalar(select(Badge).where(Badge.id == badge_id))
    if not badge:
        raise HTTPException(status_code=404, detail="Badge not found")
    owners = await db.scalar(select(func.count(UserBadge.id)).where(UserBadge.badge_id == badge_id))
    if owners and owners > 0:
        badge.is_active = False
        await db.commit()
        return "Badge deactivated (has owners)"
    await db.delete(badge)
    await db.commit()
    return "Badge deleted"
