"""Reputation System API Router"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from datetime import datetime, timedelta

from app.database import get_db
from app.dependencies import limiter
from app.auth import get_current_active_user, get_current_verified_user
from app.models import User, UserRole, ReputationEntry, Post, Thread, AppSettings, LeaderboardPeriod, LeaderboardScore, EscrowDeal, EscrowStatus
from app.sanitize import sanitize_content
from app.routers.forum_helpers import _award_xp, user_to_minimal, public_name
from app.schemas import (
    ReputationCreate, ReputationResponse, ReputationListResponse,
    UserMinimal, SuccessResponse,
)

router = APIRouter(prefix="/api/reputation", tags=["Reputation"])


async def _add_leaderboard_score(db: AsyncSession, user_id: int):
    """Add rep points to the active leaderboard period."""
    now = datetime.utcnow()
    from sqlalchemy import select as sa_select
    period = await db.scalar(
        sa_select(LeaderboardPeriod).where(
            LeaderboardPeriod.is_active == True,
            LeaderboardPeriod.ends_at > now,
        ).order_by(LeaderboardPeriod.starts_at.desc()).limit(1)
    )
    if not period:
        return
    score = await db.scalar(
        sa_select(LeaderboardScore).where(
            LeaderboardScore.user_id == user_id,
            LeaderboardScore.period_id == period.id,
        )
    )
    if not score:
        score = LeaderboardScore(user_id=user_id, period_id=period.id)
        db.add(score)
        await db.flush()
    score.rep_received += 1
    score.score += 3


async def _remove_leaderboard_score(db: AsyncSession, user_id: int):
    """Reverse rep points added by _add_leaderboard_score when a rep entry is
    deleted, so give->delete->give can't farm leaderboard rank. Clamps at 0."""
    now = datetime.utcnow()
    from sqlalchemy import select as sa_select
    period = await db.scalar(
        sa_select(LeaderboardPeriod).where(
            LeaderboardPeriod.is_active == True,
            LeaderboardPeriod.ends_at > now,
        ).order_by(LeaderboardPeriod.starts_at.desc()).limit(1)
    )
    if not period:
        return
    score = await db.scalar(
        sa_select(LeaderboardScore).where(
            LeaderboardScore.user_id == user_id,
            LeaderboardScore.period_id == period.id,
        )
    )
    if not score:
        return
    score.rep_received = max(0, score.rep_received - 1)
    score.score = max(0, score.score - 3)


from app.telegram import create_notification


@router.post("/users/{user_id}", response_model=ReputationResponse)
@limiter.limit("10/minute")
async def give_reputation(
    request: Request,
    user_id: int,
    data: ReputationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """Give reputation (+rep or -rep) to a user"""
    # Can't rep yourself
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot give reputation to yourself")
    
    # Lock the target row for the duration of the transaction. This serializes
    # concurrent +rep requests to the same target so the cooldown check below
    # can't be raced (two requests both passing the 24h check before either
    # commits) and the rep counter increment is not lost-update prone.
    result = await db.execute(select(User).where(User.id == user_id).with_for_update())
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Counterparties of a closed escrow deal may rep each other without the
    # forum post minimum — traders aren't necessarily posters. The deal must be
    # closed with money moved (completed/refunded) and bind exactly these two users.
    deal_partner = False
    if data.deal_id:
        deal_result = await db.execute(select(EscrowDeal).where(EscrowDeal.id == data.deal_id))
        deal = deal_result.scalar_one_or_none()
        if (
            not deal
            or deal.status not in (EscrowStatus.COMPLETED, EscrowStatus.REFUNDED)
            or {current_user.id, user_id} != {deal.buyer_id, deal.seller_id}
        ):
            raise HTTPException(status_code=400, detail="Invalid escrow deal reference")
        deal_partner = True

    # Get app settings for min posts requirement
    settings_result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    settings = settings_result.scalar_one_or_none()
    min_posts = settings.min_posts_for_rep if settings else 10

    # Check if user has enough posts (waived for escrow deal partners)
    if not deal_partner and (current_user.post_count or 0) < min_posts:
        raise HTTPException(
            status_code=403,
            detail=f"You need at least {min_posts} posts to give reputation"
        )
    
    # Check if user already gave rep to this user recently (24h cooldown)
    cooldown_time = datetime.utcnow() - timedelta(hours=24)
    recent_rep = await db.execute(
        select(ReputationEntry).where(
            ReputationEntry.from_user_id == current_user.id,
            ReputationEntry.to_user_id == user_id,
            ReputationEntry.created_at > cooldown_time,
        )
    )
    if recent_rep.scalar_one_or_none():
        raise HTTPException(
            status_code=400, 
            detail="You can only give reputation to the same user once every 24 hours"
        )
    
    # Validate post/thread if provided
    if data.post_id:
        post = await db.execute(select(Post).where(Post.id == data.post_id))
        if not post.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Invalid post")
    
    if data.thread_id:
        thread = await db.execute(select(Thread).where(Thread.id == data.thread_id))
        if not thread.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Invalid thread")
    
    # Create reputation entry
    rep_entry = ReputationEntry(
        from_user_id=current_user.id,
        to_user_id=user_id,
        is_positive=data.is_positive,
        comment=sanitize_content(data.comment),
        post_id=data.post_id,
        thread_id=data.thread_id,
    )
    db.add(rep_entry)

    # Update target user's rep count
    if data.is_positive:
        target_user.rep_positive = (target_user.rep_positive or 0) + 1
    else:
        target_user.rep_negative = (target_user.rep_negative or 0) + 1

    # Flush to assign rep_entry.id without committing, so the rep entry, XP,
    # leaderboard score and notification all land in ONE atomic transaction.
    # (Previously each step committed separately and the notification — added
    # last with no following commit — was silently dropped.)
    await db.flush()

    # Award XP to giver
    await _award_xp(db, current_user, 3)

    # Leaderboard scoring for positive rep
    if data.is_positive:
        await _add_leaderboard_score(db, user_id)

    # Notify target user
    rep_type = "+rep" if data.is_positive else "-rep"
    await create_notification(
        db,
        user_id=target_user.id,
        type="reputation",
        title=f"You received {rep_type}",
        body=f"{public_name(current_user)} gave you {rep_type}" +
             (f": {data.comment}" if data.comment else ""),
        link=f"/u/{target_user.id}",
        related_user_id=current_user.id,
    )

    await db.commit()
    await db.refresh(rep_entry)

    return ReputationResponse(
        id=rep_entry.id,
        is_positive=rep_entry.is_positive,
        comment=rep_entry.comment,
        created_at=rep_entry.created_at,
        from_user=user_to_minimal(current_user),
    )


@router.get("/users/{user_id}", response_model=ReputationListResponse)
async def get_user_reputation(
    user_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get reputation history for a user"""
    # Get target user
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Query reputation entries
    query = (
        select(ReputationEntry)
        .where(ReputationEntry.to_user_id == user_id)
        .options(selectinload(ReputationEntry.from_user))
        .order_by(ReputationEntry.created_at.desc())
    )
    
    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    
    result = await db.execute(query)
    entries = result.scalars().all()
    
    return ReputationListResponse(
        entries=[
            ReputationResponse(
                id=entry.id,
                is_positive=entry.is_positive,
                comment=entry.comment,
                created_at=entry.created_at,
                from_user=user_to_minimal(entry.from_user),
            )
            for entry in entries
        ],
        total_positive=target_user.rep_positive or 0,
        total_negative=target_user.rep_negative or 0,
    )
