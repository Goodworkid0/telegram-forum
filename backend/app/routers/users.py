"""Users API Router"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, desc
from sqlalchemy.orm import selectinload
from typing import List
from datetime import datetime
import os
import asyncio

from app.database import get_db
from app.ledger import record_balance_change, commit_and_broadcast
from app.auth import get_current_active_user, block_if_impersonating
from app.dependencies import limiter
from app.telegram import create_notification
from app.models import (
    User, UserRole, UserFollow, UserBadge, Badge,
    Thread, Post, Notification, AppSettings, DailyRewardConfig,
    LeaderboardPeriod, LeaderboardScore,
)
from app.schemas import (
    UserResponse, UserPublicProfile, UserMinimal,
    UserBadgeResponse, SuccessResponse,
    XPResponse, DailyRewardResponse,
    LeaderboardEntry, LeaderboardResponse,
)
from app.images import process_upload, validated_image_extension, InvalidImageError
from app.money import to_money
from app.sanitize import sanitize_content
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

router = APIRouter(prefix="/api/users", tags=["Users"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "avatars")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# user_to_minimal, calculate_level (= _calc_level) and xp_for_level live in
# forum_helpers — the single source of truth for the leveling curve.
from app.routers.forum_helpers import (
    user_to_minimal,
    _calc_level as calculate_level,
    xp_for_level, public_name,
)


# ============================================================================
# CURRENT USER ENDPOINTS
# ============================================================================

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get current user's profile"""
    # Get primary badge
    primary_badge_result = await db.execute(
        select(UserBadge)
        .where(UserBadge.user_id == current_user.id, UserBadge.is_primary == True)
        .options(selectinload(UserBadge.badge))
    )
    primary_badge_entry = primary_badge_result.scalar_one_or_none()
    primary_badge = primary_badge_entry.badge if primary_badge_entry else None
    
    return UserResponse(
        id=current_user.id,
        telegram_id=current_user.telegram_id,
        username=current_user.username,
        first_name=current_user.first_name,
        avatar_url=current_user.avatar_url,
        role=current_user.role,
        is_active=current_user.is_active,
        is_banned=current_user.is_banned or False,
        ban_reason=current_user.ban_reason,
        balance=current_user.balance or 0.0,
        pending_balance=current_user.pending_balance or 0.0,
        post_count=current_user.post_count or 0,
        thread_count=current_user.thread_count or 0,
        like_count=current_user.like_count or 0,
        rep_positive=current_user.rep_positive or 0,
        rep_negative=current_user.rep_negative or 0,
        signature=current_user.signature,
        custom_title=current_user.custom_title,
        profile_banner_url=current_user.profile_banner_url,
        profile_bio=current_user.profile_bio,
        notification_preferences=current_user.notification_preferences,
        show_telegram=current_user.show_telegram if current_user.show_telegram is not None else True,
        created_at=current_user.created_at,
        last_seen_at=current_user.last_seen_at,
        primary_badge=primary_badge,
        xp=current_user.xp or 0,
        level=current_user.level or 1,
        login_streak=current_user.login_streak or 0,
        is_premium=current_user.is_premium or False,
        premium_until=current_user.premium_until,
        # MUST be included: it defaults to False in the schema, so omitting it makes
        # the frontend think setup is incomplete and re-triggers the onboarding modal
        # every time the user object is refreshed from this endpoint.
        is_setup_complete=current_user.is_setup_complete or False,
    )


# Price of a display-name change (the first one is free at onboarding).
DISPLAY_NAME_CHANGE_PRICE = to_money(20)

DOPPELGANGER_BADGE_NAME = "Doppelganger"


async def _award_doppelganger(db: AsyncSession, user: User) -> None:
    """Grant (or stack) the Doppelganger badge — one per paid name change."""
    badge = (await db.execute(
        select(Badge).where(Badge.name == DOPPELGANGER_BADGE_NAME)
    )).scalar_one_or_none()
    if not badge:
        badge = Badge(
            name=DOPPELGANGER_BADGE_NAME,
            description="Earned each time you change your display name. Who are you really?",
            icon="venetian-mask",
            icon_style="glow",
            color="#b44dff",
            multi_purchase=True,
            is_purchasable=False,
            is_active=True,
        )
        db.add(badge)
        try:
            # SAVEPOINT so a concurrent first-time create (different user) only
            # rolls back this insert, not the caller's already-flushed payment.
            async with db.begin_nested():
                await db.flush()
        except IntegrityError:
            badge = (await db.execute(
                select(Badge).where(Badge.name == DOPPELGANGER_BADGE_NAME)
            )).scalar_one()

    # Same-user concurrency is serialized by the user-row lock in the caller,
    # so a plain get-then-increment is safe here.
    ub = (await db.execute(
        select(UserBadge).where(UserBadge.user_id == user.id, UserBadge.badge_id == badge.id)
    )).scalar_one_or_none()
    if ub:
        ub.quantity = (ub.quantity or 1) + 1
    else:
        db.add(UserBadge(user_id=user.id, badge_id=badge.id, acquired_type="purchase", quantity=1))


class DisplayNameChangeRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=64)


@router.post("/me/display-name", response_model=UserResponse)
async def change_display_name(
    payload: DisplayNameChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _imp: User = Depends(block_if_impersonating),
):
    """Paid display-name change ($20). The initial display name is set free at
    onboarding; any later change costs DISPLAY_NAME_CHANGE_PRICE."""
    new_name = (sanitize_content(payload.first_name) or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Display name cannot be empty")

    from app.pricing import get_price
    DISPLAY_NAME_CHANGE_PRICE = await get_price(db, "name_change_price")

    # Lock the user row to prevent double-spend on concurrent requests.
    result = await db.execute(select(User).where(User.id == current_user.id).with_for_update())
    user = result.scalar_one()

    if to_money(user.balance) < DISPLAY_NAME_CHANGE_PRICE:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. A name change costs ${DISPLAY_NAME_CHANGE_PRICE}.",
        )

    record_balance_change(
        db, user, delta=-DISPLAY_NAME_CHANGE_PRICE, entry_type="display_name_change",
        description=f"Display name change to {new_name}",
    )
    user.first_name = new_name
    await db.flush()  # persist payment + name before the badge get-or-create savepoint
    await _award_doppelganger(db, user)
    await commit_and_broadcast(db)
    await db.refresh(user)

    return await get_current_user_profile(db, user)


@router.post("/me/avatar", response_model=UserResponse)
@limiter.limit("10/minute")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload avatar image"""
    # Validate file size (max 2MB)
    contents = await file.read()
    if len(contents) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 2MB)")

    # Validate by content (magic bytes), not the client-supplied type/filename.
    if validated_image_extension(contents) is None:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: JPEG, PNG, GIF, WebP")

    # Process image off the event loop (Pillow encode is CPU-bound and blocking).
    try:
        processed_bytes, processed_filename = await asyncio.to_thread(process_upload, contents, file.filename or "avatar.jpg")
    except InvalidImageError:
        raise HTTPException(status_code=400, detail="Invalid or corrupt image")
    filepath = os.path.join(UPLOAD_DIR, processed_filename)
    
    # Delete old avatar if exists
    if current_user.avatar_url and current_user.avatar_url.startswith("/api/uploads/avatars/"):
        old_filename = current_user.avatar_url.split("/")[-1]
        old_filepath = os.path.join(UPLOAD_DIR, old_filename)
        if os.path.exists(old_filepath):
            os.remove(old_filepath)
    
    # Save new avatar
    with open(filepath, "wb") as f:
        f.write(processed_bytes)
    
    current_user.avatar_url = f"/api/uploads/avatars/{processed_filename}"
    await db.commit()
    await db.refresh(current_user)
    
    return await get_current_user_profile(db, current_user)


@router.post("/me/banner", response_model=UserResponse)
@limiter.limit("10/minute")
async def upload_banner(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    # Validate by content (magic bytes), not the client-supplied type/filename.
    if validated_image_extension(contents) is None:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: JPEG, PNG, GIF, WebP")

    # Process image off the event loop (Pillow encode is CPU-bound and blocking).
    try:
        processed_bytes, processed_filename = await asyncio.to_thread(process_upload, contents, file.filename or "banner.jpg")
    except InvalidImageError:
        raise HTTPException(status_code=400, detail="Invalid or corrupt image")
    banner_dir = os.path.join(os.path.dirname(UPLOAD_DIR), "banners")
    os.makedirs(banner_dir, exist_ok=True)
    filepath = os.path.join(banner_dir, processed_filename)
    if current_user.profile_banner_url and "/banners/" in current_user.profile_banner_url:
        old_filename = current_user.profile_banner_url.split("/")[-1]
        old_filepath = os.path.join(banner_dir, old_filename)
        if os.path.exists(old_filepath):
            os.remove(old_filepath)
    with open(filepath, "wb") as f:
        f.write(processed_bytes)
    current_user.profile_banner_url = f"/api/uploads/banners/{processed_filename}"
    await db.commit()
    await db.refresh(current_user)
    return await get_current_user_profile(db, current_user)


@router.get("/leaderboard", response_model=LeaderboardResponse)
@limiter.limit("30/minute")
async def get_leaderboard(
    request: Request,
    type: str = Query("score", pattern="^(score|posts|rep)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    now = datetime.utcnow()
    
    # Find active period
    period = await db.scalar(
        select(LeaderboardPeriod).where(
            LeaderboardPeriod.is_active == True,
            LeaderboardPeriod.ends_at > now,
        ).order_by(LeaderboardPeriod.starts_at.desc()).limit(1)
    )
    
    if not period:
        return LeaderboardResponse(entries=[], current_user_rank=None, current_user_value=None,
                                   period_ends_at=None, period_starts_at=None)

    offset = (page - 1) * per_page
    
    if type == "score":
        query = (
            select(LeaderboardScore, User.username, User.first_name, User.avatar_url, User.show_telegram, User.role, User.profile_theme)
            .join(User, LeaderboardScore.user_id == User.id)
            .where(LeaderboardScore.period_id == period.id, User.is_banned == False)
            .order_by(LeaderboardScore.score.desc())
            .offset(offset).limit(per_page)
        )
    elif type == "posts":
        query = (
            select(LeaderboardScore, User.username, User.first_name, User.avatar_url, User.show_telegram, User.role, User.profile_theme)
            .join(User, LeaderboardScore.user_id == User.id)
            .where(LeaderboardScore.period_id == period.id, User.is_banned == False)
            .order_by(LeaderboardScore.post_count.desc())
            .offset(offset).limit(per_page)
        )
    else:
        query = (
            select(LeaderboardScore, User.username, User.first_name, User.avatar_url, User.show_telegram, User.role, User.profile_theme)
            .join(User, LeaderboardScore.user_id == User.id)
            .where(LeaderboardScore.period_id == period.id, User.is_banned == False)
            .order_by(LeaderboardScore.rep_received.desc())
            .offset(offset).limit(per_page)
        )
    
    result = await db.execute(query)
    rows = result.all()
    
    entries = []
    for i, row in enumerate(rows):
        score, uname, fname, avatar, show_tg, urole, ptheme = row
        entries.append(LeaderboardEntry(
            rank=offset + i + 1,
            user_id=score.user_id,
            username=uname,
            first_name=fname,
            avatar_url=avatar,
            show_telegram=show_tg if show_tg is not None else True,
            role=urole,
            profile_theme=ptheme,
            value=score.score if type == "score" else (score.post_count if type == "posts" else score.rep_received),
            post_count=score.post_count,
            thread_count=score.thread_count,
            likes_received=score.likes_received,
            likes_given=score.likes_given,
            rep_received=score.rep_received,
        ))
    
    # Current user's rank
    current_user_rank = None
    current_user_value = None
    if page == 1:
        user_score = await db.scalar(
            select(LeaderboardScore).where(
                LeaderboardScore.user_id == current_user.id,
                LeaderboardScore.period_id == period.id,
            )
        )
        if user_score:
            val = user_score.score if type == "score" else (user_score.post_count if type == "posts" else user_score.rep_received)
            col = LeaderboardScore.score if type == "score" else (LeaderboardScore.post_count if type == "posts" else LeaderboardScore.rep_received)
            rank_count = await db.scalar(
                select(func.count()).select_from(LeaderboardScore).where(
                    LeaderboardScore.period_id == period.id,
                    col > val,
                )
            )
            current_user_rank = (rank_count or 0) + 1
            current_user_value = val
    
    return LeaderboardResponse(
        entries=entries,
        current_user_rank=current_user_rank,
        current_user_value=current_user_value,
        period_ends_at=period.ends_at,
        period_starts_at=period.starts_at,
    )


# ============================================================================
# PUBLIC USER ENDPOINTS
# ============================================================================

@router.get("/{user_id}", response_model=UserPublicProfile)
async def get_user_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a user's public profile"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get badges
    badges_result = await db.execute(
        select(UserBadge)
        .where(UserBadge.user_id == user_id, UserBadge.is_hidden == False)
        .options(selectinload(UserBadge.badge))
        .order_by(UserBadge.is_primary.desc(), UserBadge.acquired_at)
    )
    badges = [
        UserBadgeResponse(
            id=ub.id,
            badge=ub.badge,
            is_primary=ub.is_primary,
            acquired_at=ub.acquired_at,
            acquired_type=ub.acquired_type,
            quantity=ub.quantity or 1,
        )
        for ub in badges_result.scalars()
    ]
    
    # Check if current user is following
    is_following = False
    if current_user.id != user_id:
        follow_result = await db.execute(
            select(UserFollow).where(
                UserFollow.follower_id == current_user.id,
                UserFollow.following_id == user_id,
            )
        )
        is_following = follow_result.scalar_one_or_none() is not None
    
    # Get follower/following counts
    follower_count = await db.execute(
        select(func.count(UserFollow.id)).where(UserFollow.following_id == user_id)
    )
    following_count = await db.execute(
        select(func.count(UserFollow.id)).where(UserFollow.follower_id == user_id)
    )
    
    # Privacy: only expose the raw @handle to the owner or staff when the user
    # has hidden it; everyone else gets None and sees the display name.
    _viewer_is_staff = current_user.role in (UserRole.MODERATOR, UserRole.ADMIN)
    _show_handle = user.show_telegram is not False or current_user.id == user.id or _viewer_is_staff

    return UserPublicProfile(
        id=user.id,
        username=user.username if _show_handle else None,
        first_name=user.first_name,
        avatar_url=user.avatar_url,
        role=user.role,
        post_count=user.post_count or 0,
        thread_count=user.thread_count or 0,
        like_count=user.like_count or 0,
        rep_positive=user.rep_positive or 0,
        rep_negative=user.rep_negative or 0,
        signature=user.signature,
        custom_title=user.custom_title,
        profile_banner_url=user.profile_banner_url,
        profile_bio=user.profile_bio,
        profile_theme=user.profile_theme,
        show_telegram=user.show_telegram if user.show_telegram is not None else True,
        last_seen_at=user.last_seen_at,
        created_at=user.created_at,
        badges=badges,
        is_following=is_following,
        follower_count=follower_count.scalar() or 0,
        following_count=following_count.scalar() or 0,
        xp=user.xp or 0,
        level=user.level or 1,
        login_streak=user.login_streak or 0,
        is_premium=user.is_premium or False,
        is_banned=user.is_banned or False,
        is_muted=user.is_muted or False,
    )


@router.get("", response_model=List[UserMinimal])
@limiter.limit("30/minute")
async def search_users(
    request: Request,
    q: str = Query(None, min_length=2, max_length=50),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Search users by username or name"""
    query = select(User).where(User.is_active == True, User.is_banned == False)
    
    if q:
        search_term = f"%{q}%"
        query = query.where(
            or_(
                # Don't confirm a hidden @handle via username match — users who
                # hide their handle are findable only by display name.
                and_(User.show_telegram != False, User.username.ilike(search_term)),
                User.first_name.ilike(search_term),
            )
        )
    
    query = query.order_by(desc(User.post_count)).offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return [user_to_minimal(u) for u in users]


# ============================================================================
# FOLLOW SYSTEM
# ============================================================================

@router.post("/{user_id}/follow", response_model=SuccessResponse)
async def follow_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Follow a user"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
    
    # Check if user exists
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already following
    existing = await db.execute(
        select(UserFollow).where(
            UserFollow.follower_id == current_user.id,
            UserFollow.following_id == user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already following")
    
    follow = UserFollow(follower_id=current_user.id, following_id=user_id)
    db.add(follow)
    
    # Notify user (in-app + Telegram mirror + SSE)
    await create_notification(
        db, user_id=user_id, type="new_follower",
        title="New follower",
        body=f"{public_name(current_user)} started following you",
        link=f"/profile/{current_user.id}",
        related_user_id=current_user.id,
    )
    
    await db.commit()
    
    return SuccessResponse(message="User followed")


@router.delete("/{user_id}/follow", response_model=SuccessResponse)
async def unfollow_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Unfollow a user"""
    result = await db.execute(
        select(UserFollow).where(
            UserFollow.follower_id == current_user.id,
            UserFollow.following_id == user_id,
        )
    )
    follow = result.scalar_one_or_none()
    
    if not follow:
        raise HTTPException(status_code=400, detail="Not following")
    
    await db.delete(follow)
    await db.commit()

    return SuccessResponse(message="User unfollowed")


@router.get("/{user_id}/followers", response_model=List[UserMinimal])
async def get_user_followers(
    user_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Users who follow this user (newest first)."""
    result = await db.execute(
        select(UserFollow)
        .where(UserFollow.following_id == user_id)
        .options(selectinload(UserFollow.follower))
        .order_by(desc(UserFollow.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    follows = result.scalars().all()
    return [user_to_minimal(f.follower) for f in follows if f.follower]


@router.get("/{user_id}/following", response_model=List[UserMinimal])
async def get_user_following(
    user_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Users this user follows (newest first)."""
    result = await db.execute(
        select(UserFollow)
        .where(UserFollow.follower_id == user_id)
        .options(selectinload(UserFollow.following))
        .order_by(desc(UserFollow.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    follows = result.scalars().all()
    return [user_to_minimal(f.following) for f in follows if f.following]


# ============================================================================
# USER CONTENT
# ============================================================================

@router.get("/{user_id}/threads")
async def get_user_threads(
    user_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get threads created by a user"""
    from app.models import ThreadStatus
    
    query = (
        select(Thread)
        .where(
            Thread.author_id == user_id,
            Thread.status != ThreadStatus.DELETED,
        )
        .options(selectinload(Thread.board))
        .order_by(Thread.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    
    result = await db.execute(query)
    threads = result.scalars().all()
    
    return [
        {
            "id": t.id,
            "title": t.title,
            "slug": t.slug,
            "title_color": t.title_color,
            "title_glow": bool(t.title_glow),
            "auto_bump_until": t.auto_bump_until.isoformat() if t.auto_bump_until else None,
            "board_name": t.board.name if t.board else None,
            "board_slug": t.board.slug if t.board else None,
            "reply_count": t.reply_count or 0,
            "view_count": t.view_count or 0,
            "created_at": t.created_at,
        }
        for t in threads
    ]


@router.get("/{user_id}/posts")
async def get_user_posts(
    user_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get posts by a user"""
    query = (
        select(Post)
        .where(
            Post.author_id == user_id,
            Post.is_deleted == False,
        )
        .options(selectinload(Post.thread))
        .order_by(Post.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    
    result = await db.execute(query)
    posts = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "content": p.content[:200] + "..." if len(p.content) > 200 else p.content,
            "thread_id": p.thread_id,
            "thread_title": p.thread.title if p.thread else None,
            "like_count": p.like_count or 0,
            "created_at": p.created_at,
        }
        for p in posts
    ]


# ============================================================================
# XP / LEVELING / LEADERBOARD
# (calculate_level / xp_for_level imported from forum_helpers above)
# ============================================================================


@router.get("/me/xp", response_model=XPResponse)
async def get_my_xp(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from datetime import date
    xp = current_user.xp or 0
    level = current_user.level or 1
    current_level_xp = xp_for_level(level)
    next_level_xp = xp_for_level(level + 1)
    today = date.today()
    streak = current_user.login_streak or 0
    already_claimed = current_user.last_daily_claim_date == today

    result = await db.execute(
        select(DailyRewardConfig)
        .where(DailyRewardConfig.day <= streak, DailyRewardConfig.is_active == True)
        .order_by(DailyRewardConfig.day.desc())
        .limit(1)
    )
    config = result.scalar_one_or_none()
    if not config:
        result = await db.execute(
            select(DailyRewardConfig)
            .where(DailyRewardConfig.is_active == True)
            .order_by(DailyRewardConfig.day)
            .limit(1)
        )
        config = result.scalar_one_or_none()

    badge_name = None
    if config and config.badge_id:
        badge_result = await db.execute(select(Badge).where(Badge.id == config.badge_id))
        badge = badge_result.scalar_one_or_none()
        if badge:
            badge_name = badge.name

    return XPResponse(
        xp=xp,
        level=level,
        xp_to_next_level=next_level_xp,
        xp_for_current_level=current_level_xp,
        login_streak=streak,
        streak_bonus_claimed=current_user.streak_bonus_claimed or False,
        last_daily_claim_date=current_user.last_daily_claim_date,
        daily_xp_preview=config.xp_amount if config else 10,
        daily_balance_preview=config.balance_amount if config else 0.10,
        daily_badge_preview=config.badge_id if config else None,
        daily_badge_name_preview=badge_name,
        daily_can_claim=not already_claimed,
    )


@router.post("/me/daily-reward", response_model=DailyRewardResponse)
async def claim_daily_reward(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from datetime import date
    today = date.today()

    # Lock the user row and re-read the claim date under the lock so two concurrent
    # requests can't both pass the "not yet claimed today" check and double-award.
    locked = await db.execute(
        select(User).where(User.id == current_user.id).with_for_update()
    )
    current_user = locked.scalar_one()

    if current_user.last_daily_claim_date == today:
        return DailyRewardResponse(
            claimed=False,
            streak=current_user.login_streak or 0,
            xp_awarded=0,
            balance_awarded=0.0,
        )

    streak = current_user.login_streak or 0

    result = await db.execute(
        select(DailyRewardConfig)
        .where(DailyRewardConfig.day <= streak, DailyRewardConfig.is_active == True)
        .order_by(DailyRewardConfig.day.desc())
        .limit(1)
    )
    config = result.scalar_one_or_none()

    if not config:
        result = await db.execute(
            select(DailyRewardConfig)
            .where(DailyRewardConfig.is_active == True)
            .order_by(DailyRewardConfig.day)
            .limit(1)
        )
        config = result.scalar_one_or_none()

    badge = None
    if not config:
        xp_awarded = 10
        balance_awarded = 0.10
        badge_id = None
        badge_name = None
    else:
        xp_awarded = config.xp_amount
        balance_awarded = config.balance_amount
        badge_id = config.badge_id
        badge_name = None
        if badge_id:
            # Lock the badge row so concurrent grants can't oversell limited supply.
            badge_result = await db.execute(
                select(Badge).where(Badge.id == badge_id).with_for_update()
            )
            badge = badge_result.scalar_one_or_none()
            if badge:
                badge_name = badge.name

    current_user.xp = (current_user.xp or 0) + xp_awarded
    record_balance_change(
        db, current_user, delta=balance_awarded, entry_type="daily_reward",
        description="Daily reward claim",
    )
    current_user.last_daily_claim_date = today
    # Mark today's streak bonus as claimed so streak_bonus_claimed reflects the
    # claim state (it was previously only ever reset to False on login and never
    # set True here, making the flag meaningless to clients).
    current_user.streak_bonus_claimed = True

    new_level = calculate_level(current_user.xp)
    leveled_up = new_level > (current_user.level or 1)
    current_user.level = new_level

    # Grant the day's badge if one is configured and the user doesn't already own
    # it. Done in the same transaction as the claim so it's atomic. (Previously the
    # badge was surfaced in the response but never actually granted.)
    badge_awarded = False
    if badge:
        existing_badge = await db.execute(
            select(UserBadge).where(
                UserBadge.user_id == current_user.id,
                UserBadge.badge_id == badge.id,
            )
        )
        if existing_badge.scalar_one_or_none() is None:
            db.add(UserBadge(
                user_id=current_user.id, badge_id=badge.id, acquired_type="daily_reward",
            ))
            if badge.is_limited:
                badge.current_supply = (badge.current_supply or 0) + 1
            badge_awarded = True
        else:
            # Already owned — don't tell the client they just earned it.
            badge_id = None
            badge_name = None

    await commit_and_broadcast(db)
    await db.refresh(current_user)

    if leveled_up:
        await create_notification(
            db, user_id=current_user.id, type="level_up",
            title=f"Level {new_level}!", body=f"You reached level {new_level}! Keep going!",
            link=f"/profile/{current_user.id}",
        )
        await db.commit()

    if badge_awarded:
        await create_notification(
            db, user_id=current_user.id, type="badge",
            title=f"Badge earned: {badge.name}!",
            body=badge.description or f"You earned the '{badge.name}' badge!",
            link=f"/profile/{current_user.id}",
        )
        await db.commit()

    return DailyRewardResponse(
        claimed=True,
        streak=current_user.login_streak or 0,
        xp_awarded=xp_awarded,
        balance_awarded=balance_awarded,
        badge_id=badge_id,
        badge_name=badge_name,
    )


@router.get("/me/referrals")
async def get_referral_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get current user's referral stats: earnings, direct/indirect counts, code, link"""
    from app.database import get_referral_settings

    referral_settings = await get_referral_settings(db)

    # Count direct referrals
    direct_result = await db.execute(
        select(func.count()).select_from(User).where(User.referred_by_id == current_user.id)
    )
    direct_count = direct_result.scalar() or 0

    # Get direct referrals for counting indirect
    direct_ids_result = await db.execute(
        select(User.id).where(User.referred_by_id == current_user.id)
    )
    direct_ids = [row[0] for row in direct_ids_result.all()]

    indirect_count = 0
    if direct_ids:
        indirect_result = await db.execute(
            select(func.count()).select_from(User).where(User.referred_by_id.in_(direct_ids))
        )
        indirect_count = indirect_result.scalar() or 0

    # Get recent referral commissions (last 20)
    recent_commissions_result = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.type == "referral_bonus",
        )
        .order_by(Notification.created_at.desc())
        .limit(20)
    )
    recent = [
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in recent_commissions_result.scalars().all()
    ]

    settings_result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    settings = settings_result.scalar_one_or_none()
    bot_username = (settings.bot_username if settings and settings.bot_username else "ForumMarketBot")
    if hasattr(current_user, 'username') and current_user.username:
        # Get bot username from settings
        settings_result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
        settings = settings_result.scalar_one_or_none()
        if settings and settings.bot_username:
            bot_username = settings.bot_username

    ref_code = current_user.referral_code

    return {
        "referral_code": ref_code,
        "referral_link": f"https://t.me/{bot_username}?start={ref_code}" if ref_code else None,
        "referral_earnings": current_user.referral_earnings or 0.0,
        "direct_referrals": direct_count,
        "indirect_referrals": indirect_count,
        "level1_percent": referral_settings.get("level1_percent", 3.0),
        "level2_percent": referral_settings.get("level2_percent", 5.0),
        "recent_commissions": recent,
    }
