"""Giveaways router"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
import random
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.dependencies import limiter
from app.auth import get_current_active_user, get_current_admin
from app.sanitize import sanitize_content
from app.models import Giveaway, GiveawayEntry, User, CryptoDeposit

router = APIRouter(prefix="/api/giveaways", tags=["giveaways"])


class GiveawayCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    prize: Optional[str] = Field(None, max_length=200)
    enabled: bool = True
    deposit_required: bool = False
    auto_pick_winner: bool = False
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class GiveawayUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    prize: Optional[str] = Field(None, max_length=200)
    enabled: Optional[bool] = None
    deposit_required: Optional[bool] = None
    auto_pick_winner: Optional[bool] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class EnterPayload(BaseModel):
    # Optional message/metadata could be added later; keep minimal.
    pass


def _serialize_giveaway(g: Giveaway) -> dict:
    return {
        "id": g.id,
        "title": g.title,
        "description": g.description,
        "prize": g.prize,
        "enabled": bool(g.enabled),
        "deposit_required": bool(getattr(g, "deposit_required", False)),
        "auto_pick_winner": bool(getattr(g, "auto_pick_winner", False)),
        "starts_at": g.starts_at.isoformat() if g.starts_at else None,
        "ends_at": g.ends_at.isoformat() if g.ends_at else None,
        "created_at": g.created_at.isoformat() if getattr(g, "created_at", None) else None,
        "updated_at": g.updated_at.isoformat() if getattr(g, "updated_at", None) else None,
        "winner": {
            "display_name": _display_name(g.winner_user) if getattr(g, "winner_user", None) else None,
            "picked_at": g.winner_picked_at.isoformat() if g.winner_picked_at else None,
        } if getattr(g, "winner_user_id", None) else None,
    }


def _display_name(u: User) -> str:
    # Prefer display name; only fall back to the @handle when it isn't hidden.
    if u.first_name and u.first_name.strip():
        return u.first_name.strip()
    if u.show_telegram is False:
        return "User"
    return (u.username or "User").strip() or "User"


def _serialize_participant(e: GiveawayEntry) -> dict:
    u = e.user
    return {
        "display_name": _display_name(u) if u else "User",
        "entered_at": e.created_at.isoformat() if e.created_at else None,
    }


def _is_current(g: Giveaway) -> bool:
    now = datetime.utcnow()
    if not g.enabled:
        return False
    if g.starts_at and g.starts_at > now:
        return False
    if g.ends_at and g.ends_at < now:
        return False
    return True


@router.get("/for-user")
async def list_current_giveaways_for_user(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Auth: list current giveaways with an already_entered flag for current user."""
    result = await db.execute(
        select(Giveaway)
        .options(selectinload(Giveaway.winner_user))
        .order_by(desc(Giveaway.created_at))
    )
    items = [g for g in result.scalars().all() if _is_current(g)]

    if not items:
        return []

    giveaway_ids = [g.id for g in items]

    entered_res = await db.execute(
        select(GiveawayEntry.giveaway_id)
        .where(GiveawayEntry.user_id == current_user.id)
        .where(GiveawayEntry.giveaway_id.in_(giveaway_ids))
    )
    entered_ids = set(entered_res.scalars().all())

    all_entries_res = await db.execute(
        select(GiveawayEntry)
        .where(GiveawayEntry.giveaway_id.in_(giveaway_ids))
        .options(selectinload(GiveawayEntry.user))
        .order_by(desc(GiveawayEntry.created_at))
    )
    all_entries = all_entries_res.scalars().all()
    entries_by_giveaway = {}
    for e in all_entries:
        entries_by_giveaway.setdefault(e.giveaway_id, []).append(e)

    out = []
    for g in items:
        entries = entries_by_giveaway.get(g.id, [])
        payload = _serialize_giveaway(g)
        payload["participant_count"] = len(entries)
        payload["participants"] = [_serialize_participant(e) for e in entries]
        payload["already_entered"] = g.id in entered_ids
        out.append(payload)
    return out


@router.post("/{giveaway_id}/enter")
@limiter.limit("10/minute")
async def enter_giveaway(
    request: Request,
    giveaway_id: int,
    _payload: EnterPayload,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    g = await db.get(Giveaway, giveaway_id)
    if not g or not _is_current(g):
        raise HTTPException(404, "Giveaway not found")

    if getattr(g, "deposit_required", False):
        has_deposit = await db.scalar(
            select(func.count(CryptoDeposit.id)).where(
                CryptoDeposit.user_id == current_user.id,
                CryptoDeposit.is_credited == True,
            )
        )
        if not (has_deposit or 0):
            raise HTTPException(403, "Deposit required")

    existing = await db.execute(
        select(GiveawayEntry).where(
            GiveawayEntry.giveaway_id == giveaway_id,
            GiveawayEntry.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        return {"ok": True, "already_entered": True}

    entry = GiveawayEntry(giveaway_id=giveaway_id, user_id=current_user.id)
    db.add(entry)
    await db.commit()
    return {"ok": True, "already_entered": False}


# ---- Admin ----

@router.get("/admin")
async def admin_list_giveaways(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Giveaway)
        .options(selectinload(Giveaway.winner_user))
        .order_by(desc(Giveaway.created_at))
    )
    items = result.scalars().all()
    out = []
    for g in items:
        count = await db.scalar(select(func.count(GiveawayEntry.id)).where(GiveawayEntry.giveaway_id == g.id))
        payload = _serialize_giveaway(g)
        payload["participant_count"] = int(count or 0)
        out.append(payload)
    return out


@router.get("/admin/{giveaway_id}/entries")
async def admin_list_entries(
    giveaway_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    g = await db.get(Giveaway, giveaway_id)
    if not g:
        raise HTTPException(404, "Giveaway not found")
    res = await db.execute(
        select(GiveawayEntry)
        .where(GiveawayEntry.giveaway_id == giveaway_id)
        .options(selectinload(GiveawayEntry.user))
        .order_by(desc(GiveawayEntry.created_at))
    )
    entries = res.scalars().all()
    return [
        {
            "id": e.id,
            "user_id": e.user.id if e.user else None,
            "display_name": _display_name(e.user) if e.user else "User",
            "username": e.user.username if e.user else None,
            "entered_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


@router.post("/admin/{giveaway_id}/pick-winner")
async def admin_pick_winner(
    giveaway_id: int,
    force: bool = Query(False),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    # Lock the giveaway row so two concurrent pick requests can't both pass the
    # "winner already picked" guard and overwrite each other.
    g_res = await db.execute(
        select(Giveaway)
        .where(Giveaway.id == giveaway_id)
        .options(selectinload(Giveaway.winner_user))
        .with_for_update()
    )
    g = g_res.scalar_one_or_none()
    if not g:
        raise HTTPException(404, "Giveaway not found")

    if g.winner_user_id and not force:
        raise HTTPException(400, "Winner already picked")

    # Pick from existing entries (eligibility already enforced on entry; re-check deposit requirement).
    entries_res = await db.execute(
        select(GiveawayEntry)
        .where(GiveawayEntry.giveaway_id == giveaway_id)
        .options(selectinload(GiveawayEntry.user))
    )
    entries = [e for e in entries_res.scalars().all() if e.user is not None]
    if not entries:
        raise HTTPException(400, "No entries")

    if getattr(g, "deposit_required", False):
        eligible = []
        for e in entries:
            has_deposit = await db.scalar(
                select(func.count(CryptoDeposit.id)).where(
                    CryptoDeposit.user_id == e.user_id,
                    CryptoDeposit.is_credited == True,
                )
            )
            if (has_deposit or 0) > 0:
                eligible.append(e)
        entries = eligible
        if not entries:
            raise HTTPException(400, "No eligible entries")

    winner_entry = random.choice(entries)
    g.winner_user_id = winner_entry.user_id
    g.winner_picked_at = datetime.utcnow()
    await db.commit()
    await db.refresh(g, ["winner_user"])
    payload = _serialize_giveaway(g)
    payload["participant_count"] = await db.scalar(select(func.count(GiveawayEntry.id)).where(GiveawayEntry.giveaway_id == g.id)) or 0
    return payload


@router.post("/admin")
async def admin_create_giveaway(
    payload: GiveawayCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    g = Giveaway(
        title=sanitize_content(payload.title.strip()),
        description=sanitize_content((payload.description or "").strip()) or None,
        prize=sanitize_content((payload.prize or "").strip()) or None,
        enabled=payload.enabled,
        deposit_required=payload.deposit_required,
        auto_pick_winner=payload.auto_pick_winner,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
    )
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return _serialize_giveaway(g)


@router.put("/admin/{giveaway_id}")
async def admin_update_giveaway(
    giveaway_id: int,
    payload: GiveawayUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    g = await db.get(Giveaway, giveaway_id)
    if not g:
        raise HTTPException(404, "Giveaway not found")

    if payload.title is not None:
        g.title = sanitize_content(payload.title.strip())
    if payload.description is not None:
        g.description = sanitize_content(payload.description.strip()) or None
    if payload.prize is not None:
        g.prize = sanitize_content(payload.prize.strip()) or None
    if payload.enabled is not None:
        g.enabled = payload.enabled
    if payload.deposit_required is not None:
        g.deposit_required = payload.deposit_required
    if payload.auto_pick_winner is not None:
        g.auto_pick_winner = payload.auto_pick_winner
    if payload.starts_at is not None:
        g.starts_at = payload.starts_at
    if payload.ends_at is not None:
        g.ends_at = payload.ends_at

    g.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(g)
    return _serialize_giveaway(g)


@router.delete("/admin/{giveaway_id}")
async def admin_delete_giveaway(
    giveaway_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    g = await db.get(Giveaway, giveaway_id)
    if not g:
        raise HTTPException(404, "Giveaway not found")

    # Delete entries first (simple, minimal)
    await db.execute(
        GiveawayEntry.__table__.delete().where(GiveawayEntry.giveaway_id == giveaway_id)
    )
    await db.delete(g)
    await db.commit()
    return {"ok": True}
