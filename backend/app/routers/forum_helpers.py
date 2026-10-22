"""Shared helpers for forum router modules."""
import re
import math
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.exc import IntegrityError

from app.models import (
    User, UserRole,
    LeaderboardPeriod, LeaderboardScore,
)
from app.schemas import UserMinimal


# ============================================================================
# SLUG GENERATION
# ============================================================================

def slugify(text: str) -> str:
    """Generate URL-friendly slug from text"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text[:100]


# ============================================================================
# CONSTANTS
# ============================================================================

ROLE_ORDER = {UserRole.TRIAL: 0, UserRole.USER: 1, UserRole.MODERATOR: 2, UserRole.ADMIN: 3}

# XP constants
XP_THREAD = 15
XP_POST = 5
XP_LIKE_RECEIVED = 2
XP_LIKE_GIVEN = 1

# Scoring constants
SCORE_POST = 2
SCORE_THREAD = 5
SCORE_LIKE_RECEIVED = 1
SCORE_LIKE_GIVEN = 1
SCORE_REP_RECEIVED = 3


# ============================================================================
# LEVEL / XP
# ============================================================================

def _calc_level(xp: int) -> int:
    return max(1, int(math.sqrt(xp / 100)) + 1)


def xp_for_level(level: int) -> int:
    """Total XP required to reach `level` (inverse of _calc_level)."""
    return (level - 1) ** 2 * 100


def bump_level(user: User) -> None:
    """Recompute a user's level from their XP (never lowers it). Use after
    directly crediting xp outside _award_xp (badge/achievement/leaderboard
    rewards) so the level formula lives in exactly one place."""
    user.level = max(user.level or 1, _calc_level(user.xp or 0))


async def _award_xp(db: AsyncSession, user: User, amount: int):
    user.xp = (user.xp or 0) + amount
    new_level = _calc_level(user.xp)
    if new_level > (user.level or 1):
        user.level = new_level
        from app.telegram import create_notification as tg_notify
        await tg_notify(
            db,
            user_id=user.id,
            type="level_up",
            title=f"Level {new_level}!",
            body=f"You reached level {new_level}! Keep posting!",
            link=f"/profile/{user.id}",
        )


async def _remove_xp(db: AsyncSession, user: User, amount: int):
    """Reverse XP granted for an action that was undone (unlike, thread delete,
    rep removal). Clamps at 0 and deliberately does NOT lower the user's level —
    a level-up, once notified, stands — but removing the XP means a like/unlike
    or give/remove-rep cycle nets to zero and can't be used to farm XP, levels,
    or leaderboard rewards."""
    user.xp = max(0, (user.xp or 0) - amount)


# ============================================================================
# USER SERIALIZATION
# ============================================================================

async def assert_board_readable(db: AsyncSession, board, user: User) -> None:
    """Raise 403 if `user` can't read `board` (role gate or staff-hidden).

    Shared read-gate for satellite endpoints (likes, watch, poll vote) that act
    on a thread by id — they previously skipped the min_role/is_visible check
    that the thread/board listings enforce, leaking restricted-board content.
    """
    from fastapi import HTTPException
    if board is None:
        raise HTTPException(status_code=404, detail="Not found")
    is_staff = user.role in (UserRole.MODERATOR, UserRole.ADMIN)
    if not is_staff:
        if board.is_visible is False:
            raise HTTPException(status_code=404, detail="Not found")
        if ROLE_ORDER.get(user.role, 0) < ROLE_ORDER.get(board.min_role, 0):
            raise HTTPException(status_code=403, detail="Access restricted")


def public_name(user: Optional[User]) -> str:
    """The name safe to embed in server-generated text (notifications, system
    messages, flat *_username response fields). Respects show_telegram: users
    who hide their @handle are named by display name everywhere."""
    if not user:
        return "User"
    if user.show_telegram is False:
        return user.first_name or "User"
    return user.username or user.first_name or "User"


def user_to_minimal(user: User) -> UserMinimal:
    """Convert User to UserMinimal schema.

    Privacy: when the user hides their Telegram handle, `username` is omitted
    from the payload entirely (not just hidden client-side) so the raw @handle
    can't be recovered from the API. `first_name` + `show_telegram` are still
    sent so the client renders the display name via displayName()."""
    return UserMinimal(
        id=user.id,
        username=user.username if user.show_telegram is not False else None,
        first_name=user.first_name,
        avatar_url=user.avatar_url,
        role=user.role,
        custom_title=user.custom_title,
        rep_positive=user.rep_positive or 0,
        rep_negative=user.rep_negative or 0,
        post_count=user.post_count or 0,
        thread_count=user.thread_count or 0,
        like_count=user.like_count or 0,
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
        signature=user.signature,
        primary_badge=None,
        profile_theme=user.profile_theme,
        show_telegram=user.show_telegram if user.show_telegram is not None else True,
        xp=user.xp or 0,
        level=user.level or 1,
        is_premium=user.is_premium or False,
        premium_until=user.premium_until,
    )


# ============================================================================
# LEADERBOARD SCORING
# ============================================================================

async def _add_leaderboard_score(db: AsyncSession, user_id: int, action: str):
    """Add points to the active leaderboard period for a user action."""
    now = datetime.utcnow()
    period = await db.scalar(
        select(LeaderboardPeriod).where(
            LeaderboardPeriod.is_active == True,
            LeaderboardPeriod.ends_at > now,
        ).order_by(LeaderboardPeriod.starts_at.desc()).limit(1)
    )
    if not period:
        return

    # Lock the existing row so concurrent actions by the same user don't lose
    # updates on the denormalized counters.
    score = await db.scalar(
        select(LeaderboardScore).where(
            LeaderboardScore.user_id == user_id,
            LeaderboardScore.period_id == period.id,
        ).with_for_update()
    )
    if not score:
        score = LeaderboardScore(user_id=user_id, period_id=period.id)
        db.add(score)
        try:
            # SAVEPOINT so a concurrent insert of the same (user, period) row
            # only rolls back this insert, not the caller's whole transaction.
            async with db.begin_nested():
                await db.flush()
        except IntegrityError:
            # Lost the create race — fetch the row the other request created.
            score = await db.scalar(
                select(LeaderboardScore).where(
                    LeaderboardScore.user_id == user_id,
                    LeaderboardScore.period_id == period.id,
                ).with_for_update()
            )
            if not score:
                return

    if action == 'post':
        score.post_count += 1
        score.score += SCORE_POST
    elif action == 'thread':
        score.thread_count += 1
        score.score += SCORE_THREAD
    elif action == 'like_received':
        score.likes_received += 1
        score.score += SCORE_LIKE_RECEIVED
    elif action == 'like_given':
        score.likes_given += 1
        score.score += SCORE_LIKE_GIVEN
    elif action == 'rep_received':
        score.rep_received += 1
        score.score += SCORE_REP_RECEIVED


async def _remove_leaderboard_score(db: AsyncSession, user_id: int, action: str):
    """Reverse points added by _add_leaderboard_score when the underlying action
    is undone (unlike, thread delete, rep removal). Subtracts from the active
    period and clamps counters/score at 0. Without this, repeatedly doing and
    undoing a scored action farms leaderboard rank and its balance rewards."""
    now = datetime.utcnow()
    period = await db.scalar(
        select(LeaderboardPeriod).where(
            LeaderboardPeriod.is_active == True,
            LeaderboardPeriod.ends_at > now,
        ).order_by(LeaderboardPeriod.starts_at.desc()).limit(1)
    )
    if not period:
        return

    score = await db.scalar(
        select(LeaderboardScore).where(
            LeaderboardScore.user_id == user_id,
            LeaderboardScore.period_id == period.id,
        ).with_for_update()
    )
    if not score:
        return

    if action == 'post':
        score.post_count = max(0, score.post_count - 1)
        score.score = max(0, score.score - SCORE_POST)
    elif action == 'thread':
        score.thread_count = max(0, score.thread_count - 1)
        score.score = max(0, score.score - SCORE_THREAD)
    elif action == 'like_received':
        score.likes_received = max(0, score.likes_received - 1)
        score.score = max(0, score.score - SCORE_LIKE_RECEIVED)
    elif action == 'like_given':
        score.likes_given = max(0, score.likes_given - 1)
        score.score = max(0, score.score - SCORE_LIKE_GIVEN)
    elif action == 'rep_received':
        score.rep_received = max(0, score.rep_received - 1)
        score.score = max(0, score.score - SCORE_REP_RECEIVED)


# ============================================================================
# NOTIFICATIONS — use app.telegram.create_notification (canonical implementation)
# ============================================================================
