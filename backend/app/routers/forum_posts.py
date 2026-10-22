"""Forum Post CRUD, likes, best answer, post delete"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, asc
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime, timedelta
import re

from app.dependencies import limiter

from app.database import get_db
from app.auth import (
    get_current_user,
    get_current_active_user,
    get_current_unmuted_user,
    get_current_verified_user,
    check_can_post,
)
from app.models import (
    User, UserRole,
    ForumBoard, Thread, Post,
    ThreadStatus, ThreadWatch, PostLike,
    ModAction, UserBadge,
)
from app.schemas import (
    PostCreate, PostUpdate, PostResponse, PostListResponse,
    UserMinimal, LikeResponse, SuccessResponse,
)
from app.sanitize import sanitize_content
from app.routers.forum_helpers import (
    ROLE_ORDER,
    XP_POST, XP_LIKE_RECEIVED, XP_LIKE_GIVEN,
    _award_xp, _add_leaderboard_score,
    _remove_xp, _remove_leaderboard_score,
    user_to_minimal, public_name,
    assert_board_readable,
)
from app.telegram import create_notification

router = APIRouter(prefix="/api/forum", tags=["Forum"])


async def _author_badges_map(db, user_ids) -> dict:
    """Return {user_id: [badge_dict, ...]} for the given author id(s) in one query.

    Posts previously omitted author_badges (so badges, incl. the Premium badge,
    showed on the thread's OP but vanished on replies). Mirrors the badge shape
    that forum_threads.py emits and that PostItem.jsx expects.
    """
    ids = [user_ids] if isinstance(user_ids, int) else list(user_ids)
    if not ids:
        return {}
    rows = await db.execute(
        select(UserBadge)
        .where(UserBadge.user_id.in_(ids), UserBadge.is_hidden == False)
        .options(selectinload(UserBadge.badge))
    )
    out: dict = {}
    for ub in rows.scalars().all():
        if ub.badge:
            out.setdefault(ub.user_id, []).append({
                "badge_id": ub.badge.id, "badge_name": ub.badge.name,
                "badge_color": ub.badge.color, "badge_icon": ub.badge.icon,
                "badge_icon_style": ub.badge.icon_style or "default",
                "is_primary": ub.is_primary,
            })
    return out


# ============================================================================
# POSTS - LIST
# ============================================================================

@router.get("/threads/{thread_id}/posts", response_model=PostListResponse)
async def list_thread_posts(
    thread_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List posts in a thread"""
    # Get thread
    result = await db.execute(
        select(Thread)
        .where(Thread.id == thread_id, Thread.status != ThreadStatus.DELETED)
        .options(selectinload(Thread.board))
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Check board visibility
    if ROLE_ORDER.get(current_user.role, 0) < ROLE_ORDER.get(thread.board.min_role, 0):
        raise HTTPException(status_code=403, detail="Access restricted")

    # Query posts
    query = (
        select(Post)
        .where(Post.thread_id == thread_id, Post.is_deleted == False)
        .options(selectinload(Post.author), selectinload(Post.parent).selectinload(Post.author))
        .order_by(asc(Post.created_at))
    )

    # Count total
    count_query = select(func.count(Post.id)).where(
        Post.thread_id == thread_id, Post.is_deleted == False
    )
    total = (await db.execute(count_query)).scalar()

    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    posts = result.scalars().all()

    # Get like status for current user
    if posts:
        post_ids = [p.id for p in posts]
        likes_result = await db.execute(
            select(PostLike.post_id).where(
                PostLike.post_id.in_(post_ids),
                PostLike.user_id == current_user.id,
            )
        )
        liked_posts = {row.post_id for row in likes_result}
    else:
        liked_posts = set()

    # Author badges for every reply author (one query) so badges — incl. the
    # Premium badge — render on replies, not just the thread's OP.
    badges_by_author = await _author_badges_map(db, {p.author_id for p in posts})

    # Build response
    post_list = []
    for post in posts:
        parent_author = None
        parent_preview = None
        if post.parent and post.parent.author:
            parent_author = user_to_minimal(post.parent.author)
            parent_preview = (post.parent.content or "")[:120]

        post_list.append(PostResponse(
            id=post.id,
            thread_id=post.thread_id,
            thread_slug=thread.slug,
            content=post.content,
            parent_id=post.parent_id,
            is_edited=post.is_edited,
            edited_at=post.edited_at,
            edit_count=post.edit_count or 0,
            like_count=post.like_count or 0,
            is_best_answer=post.is_best_answer,
            is_deleted=post.is_deleted,
            delete_reason=post.delete_reason,
            created_at=post.created_at,
            author=user_to_minimal(post.author),
            author_badges=badges_by_author.get(post.author_id, []),
            parent_author=parent_author,
            parent_preview=parent_preview,
            is_liked=post.id in liked_posts,
        ))

    return PostListResponse(
        posts=post_list,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


# ============================================================================
# POSTS - CREATE
# ============================================================================

@router.post("/threads/{thread_id}/posts", response_model=PostResponse)
@limiter.limit("30/minute")
async def create_post(
    request: Request,
    thread_id: int,
    data: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_unmuted_user),
):
    """Create a reply to a thread"""
    # Admin-configurable hourly post cap (staff exempt).
    if current_user.role not in (UserRole.MODERATOR, UserRole.ADMIN):
        from app.models import AppSettings
        settings = await db.scalar(select(AppSettings).where(AppSettings.id == 1))
        max_per_hour = settings.max_posts_per_hour if settings and settings.max_posts_per_hour else 30
        recent = await db.scalar(
            select(func.count()).select_from(Post).where(
                Post.author_id == current_user.id,
                Post.created_at > datetime.utcnow() - timedelta(hours=1),
            )
        )
        if (recent or 0) >= max_per_hour:
            raise HTTPException(status_code=429, detail=f"Post limit reached ({max_per_hour}/hour). Try again later.")

    # Get thread
    result = await db.execute(
        select(Thread)
        .where(Thread.id == thread_id, Thread.status != ThreadStatus.DELETED)
        .options(selectinload(Thread.board), selectinload(Thread.author))
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Check if thread is locked
    if thread.status == ThreadStatus.LOCKED:
        raise HTTPException(status_code=403, detail="Thread is locked")

    # Check permissions
    check_can_post(current_user, thread.board)

    # Validate parent if provided
    if data.parent_id:
        parent = await db.execute(
            select(Post).where(Post.id == data.parent_id, Post.thread_id == thread_id)
        )
        if not parent.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Invalid parent post")

    # Create post
    post = Post(
        thread_id=thread_id,
        author_id=current_user.id,
        content=sanitize_content(data.content),
        parent_id=data.parent_id,
    )
    db.add(post)
    await db.flush()

    # Update thread stats
    thread.reply_count = (thread.reply_count or 0) + 1
    thread.last_post_at = datetime.utcnow()
    thread.last_post_by_id = current_user.id
    thread.bumped_at = datetime.utcnow()
    thread.last_post_id = post.id

    # Update board stats
    thread.board.post_count = (thread.board.post_count or 0) + 1
    thread.board.last_post_at = datetime.utcnow()
    thread.board.last_post_id = post.id

    # Update user stats
    current_user.post_count = (current_user.post_count or 0) + 1
    current_user.last_post_at = datetime.utcnow()

    # Award XP
    await _award_xp(db, current_user, XP_POST)
    await _add_leaderboard_score(db, current_user.id, 'post')

    await db.commit()
    await db.refresh(post)

    # Notify thread author (if different from post author)
    already_notified = {current_user.id}
    if thread.author_id != current_user.id:
        await create_notification(
            db,
            user_id=thread.author_id,
            type="thread_reply",
            title="New reply to your thread",
            body=f"{public_name(current_user)} replied to your thread",
            link=f"/thread/{thread.slug}#post-{post.id}",
            related_user_id=current_user.id,
            related_thread_id=thread_id,
            related_post_id=post.id,
        )
        already_notified.add(thread.author_id)

    # Notify parent post author if this is a reply
    if data.parent_id:
        parent_result = await db.execute(select(Post).where(Post.id == data.parent_id))
        parent_post = parent_result.scalar_one()
        if parent_post.author_id not in already_notified:
            await create_notification(
                db,
                user_id=parent_post.author_id,
                type="post_reply",
                title="New reply to your post",
                body=f"{public_name(current_user)} replied to your post",
                link=f"/thread/{thread.slug}#post-{post.id}",
                related_user_id=current_user.id,
                related_post_id=post.id,
            )
            already_notified.add(parent_post.author_id)

    # Parse @mentions and notify mentioned users. Users who hide their Telegram
    # handle are tagged by display name (autocomplete inserts @DisplayName for
    # them), so match both fields.
    mentioned_usernames = set(re.findall(r'@(\w+)', data.content))
    if mentioned_usernames:
        mention_result = await db.execute(
            select(User).where(
                (User.username.in_(mentioned_usernames))
                | (User.first_name.in_(mentioned_usernames)),
                User.is_active == True,
            )
        )
        mentioned_users = mention_result.scalars().all()
        for mentioned_user in mentioned_users:
            if mentioned_user.id not in already_notified:
                await create_notification(
                    db,
                    user_id=mentioned_user.id,
                    type="mention",
                    title="You were mentioned",
                    body=f"{public_name(current_user)} mentioned you in a post",
                    link=f"/thread/{thread.slug}#post-{post.id}",
                    related_user_id=current_user.id,
                    related_thread_id=thread_id,
                    related_post_id=post.id,
                )
                already_notified.add(mentioned_user.id)

    # Notify thread watchers (excluding already notified users)
    if thread.status not in (ThreadStatus.LOCKED, ThreadStatus.ARCHIVED):
        post_author_name = public_name(current_user)
        watchers_result = await db.execute(
            select(ThreadWatch.user_id).where(
                ThreadWatch.thread_id == thread_id,
                ThreadWatch.user_id.not_in(already_notified),
            )
        )
        for row in watchers_result:
            await create_notification(
                db,
                user_id=row.user_id,
                type="thread_reply",
                title=f"New reply in: {thread.title[:80]}",
                body=f"{post_author_name} replied to a thread you're watching.",
                link=f"/thread/{thread.id}",
            )
        await db.commit()

    # Load author for response
    await db.refresh(post)
    result = await db.execute(
        select(Post).where(Post.id == post.id).options(selectinload(Post.author))
    )
    post = result.scalar_one()

    return PostResponse(
        id=post.id,
        thread_id=post.thread_id,
        thread_slug=thread.slug,
        content=post.content,
        parent_id=post.parent_id,
        is_edited=post.is_edited,
        edited_at=post.edited_at,
        edit_count=post.edit_count or 0,
        like_count=post.like_count or 0,
        is_best_answer=post.is_best_answer,
        is_deleted=post.is_deleted,
        delete_reason=post.delete_reason,
        created_at=post.created_at,
        author=user_to_minimal(post.author),
        author_badges=(await _author_badges_map(db, post.author_id)).get(post.author_id, []),
        is_liked=False,
    )


# ============================================================================
# POSTS - UPDATE
# ============================================================================

@router.put("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: int,
    data: PostUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_unmuted_user),
):
    """Update a post"""
    result = await db.execute(
        select(Post)
        .where(Post.id == post_id, Post.is_deleted == False)
        .options(selectinload(Post.author), selectinload(Post.thread))
    )
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    _thr = await db.scalar(select(Thread).where(Thread.id == post.thread_id))
    await assert_board_readable(db, await db.get(ForumBoard, _thr.board_id) if _thr else None, current_user)

    # No editing posts in a locked thread (mirrors update_thread), staff excepted.
    _is_staff = current_user.role in (UserRole.MODERATOR, UserRole.ADMIN)
    if _thr and _thr.status == ThreadStatus.LOCKED and not _is_staff:
        raise HTTPException(status_code=403, detail="This thread is locked")

    # Check permissions
    if post.author_id != current_user.id and current_user.role not in (UserRole.MODERATOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Not authorized to edit this post")

    post.content = sanitize_content(data.content)
    post.is_edited = True
    post.edited_at = datetime.utcnow()
    post.edit_count = (post.edit_count or 0) + 1

    await db.commit()
    await db.refresh(post)

    # Check if liked
    like_result = await db.execute(
        select(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == current_user.id)
    )
    is_liked = like_result.scalar_one_or_none() is not None

    return PostResponse(
        id=post.id,
        thread_id=post.thread_id,
        content=post.content,
        parent_id=post.parent_id,
        is_edited=post.is_edited,
        edited_at=post.edited_at,
        edit_count=post.edit_count or 0,
        like_count=post.like_count or 0,
        is_best_answer=post.is_best_answer,
        is_deleted=post.is_deleted,
        delete_reason=post.delete_reason,
        created_at=post.created_at,
        author=user_to_minimal(post.author),
        author_badges=(await _author_badges_map(db, post.author_id)).get(post.author_id, []),
        is_liked=is_liked,
    )


# ============================================================================
# POSTS - DELETE
# ============================================================================

@router.delete("/posts/{post_id}", response_model=SuccessResponse)
async def delete_post(
    post_id: int,
    reason: Optional[str] = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a post (soft delete)"""
    result = await db.execute(
        select(Post)
        .where(Post.id == post_id, Post.is_deleted == False)
        .options(selectinload(Post.thread))
    )
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check permissions
    if post.author_id != current_user.id and current_user.role not in (UserRole.MODERATOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Not authorized to delete this post")

    post.is_deleted = True
    post.deleted_by_id = current_user.id
    post.deleted_at = datetime.utcnow()
    post.delete_reason = reason

    # Update thread stats
    post.thread.reply_count = max(0, (post.thread.reply_count or 0) - 1)

    # If we just deleted the thread's most recent reply, recompute the bump so
    # ordering (board: bumped_at; activity feed: last_post_at) reflects the new
    # latest remaining reply — otherwise the thread keeps a stale bumped position.
    if post.thread.last_post_id == post.id:
        latest_result = await db.execute(
            select(Post)
            .where(
                Post.thread_id == post.thread_id,
                Post.is_deleted == False,
                Post.id != post.id,  # exclude the post being deleted (not yet flushed)
            )
            .order_by(Post.created_at.desc(), Post.id.desc())
            .limit(1)
        )
        latest_post = latest_result.scalar_one_or_none()
        if latest_post:
            post.thread.last_post_id = latest_post.id
            post.thread.last_post_by_id = latest_post.author_id
            post.thread.last_post_at = latest_post.created_at
            post.thread.bumped_at = latest_post.created_at
        else:
            # No replies left — revert to the original-post (thread) state.
            post.thread.last_post_id = None
            post.thread.last_post_by_id = post.thread.author_id
            post.thread.last_post_at = post.thread.created_at
            post.thread.bumped_at = post.thread.created_at

    # Update board stats
    board = await db.execute(select(ForumBoard).where(ForumBoard.id == post.thread.board_id))
    board = board.scalar_one()
    board.post_count = max(0, (board.post_count or 0) - 1)

    # If we just deleted the board's recorded last post, recompute it so the
    # board's "last activity" row doesn't show a stale/deleted post. Only runs
    # when the deleted post was actually the board's last_post_id.
    if board.last_post_id == post.id:
        # Newest remaining non-deleted reply across the board's (non-deleted) threads.
        latest_post = (await db.execute(
            select(Post)
            .join(Thread, Post.thread_id == Thread.id)
            .where(
                Thread.board_id == board.id,
                Thread.status != ThreadStatus.DELETED,
                Post.is_deleted == False,
                Post.id != post.id,  # exclude the post being deleted (not yet flushed)
            )
            .order_by(Post.created_at.desc(), Post.id.desc())
            .limit(1)
        )).scalar_one_or_none()
        # Newest thread creation also counts as board activity (threads bump
        # last_post_at without a reply), so compare against it.
        latest_thread_at = (await db.execute(
            select(Thread.created_at)
            .where(
                Thread.board_id == board.id,
                Thread.status != ThreadStatus.DELETED,
            )
            .order_by(Thread.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        if latest_post and (latest_thread_at is None or latest_post.created_at >= latest_thread_at):
            board.last_post_id = latest_post.id
            board.last_post_at = latest_post.created_at
        else:
            # Most recent activity is a thread creation (or the board is now empty).
            board.last_post_id = None
            board.last_post_at = latest_thread_at  # None if no threads remain

    # Reverse the reward the post earned on creation so a create→delete loop
    # can't farm XP, level, leaderboard rank, or post_count (which feed
    # reward-paying achievement badges). Mirrors the like/unlike symmetry.
    author = await db.scalar(
        select(User).where(User.id == post.author_id).with_for_update()
    )
    if author:
        author.post_count = max(0, (author.post_count or 0) - 1)
        await _remove_xp(db, author, XP_POST)

    await db.commit()

    await _remove_leaderboard_score(db, post.author_id, 'post')
    await db.commit()

    if current_user.id != post.author_id:
        mod_action = ModAction(
            moderator_id=current_user.id,
            target_user_id=post.author_id,
            action_type="post_delete",
            reason=f"Post #{post_id} deleted" + (f": {reason}" if reason else ""),
        )
        db.add(mod_action)
        await db.commit()

    return SuccessResponse(message="Post deleted")


# ============================================================================
# POST LIKES
# ============================================================================

@router.post("/posts/{post_id}/like", response_model=LikeResponse)
@limiter.limit("30/minute")
async def like_post(
    request: Request,
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """Like a post"""
    result = await db.execute(
        select(Post)
        .where(Post.id == post_id, Post.is_deleted == False)
        .with_for_update()
    )
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    _thr = await db.scalar(select(Thread).where(Thread.id == post.thread_id))
    await assert_board_readable(db, await db.get(ForumBoard, _thr.board_id) if _thr else None, current_user)

    # Check if already liked
    existing = await db.execute(
        select(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == current_user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already liked")

    # Can't like own post
    if post.author_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot like your own post")

    like = PostLike(post_id=post_id, user_id=current_user.id)
    db.add(like)

    post.like_count = (post.like_count or 0) + 1

    # Update author's like count
    author = await db.execute(
        select(User).where(User.id == post.author_id).with_for_update()
    )
    author = author.scalar_one()
    author.like_count = (author.like_count or 0) + 1

    current_user.like_given_count = (current_user.like_given_count or 0) + 1

    # Award XP: giver gets XP for engaging, receiver gets XP for quality content
    await _award_xp(db, current_user, XP_LIKE_GIVEN)
    await _award_xp(db, author, XP_LIKE_RECEIVED)

    await db.commit()

    await _add_leaderboard_score(db, post.author_id, 'like_received')
    await _add_leaderboard_score(db, current_user.id, 'like_given')

    # Get thread slug for notification link
    thread_slug_result = await db.execute(
        select(Thread.slug).where(Thread.id == post.thread_id)
    )
    thread_slug = thread_slug_result.scalar_one_or_none()

    # Notify author
    await create_notification(
        db,
        user_id=post.author_id,
        type="post_like",
        title="Your post was liked",
        body=f"{public_name(current_user)} liked your post",
        link=f"/thread/{thread_slug}#post-{post_id}",
        related_user_id=current_user.id,
        related_post_id=post_id,
    )
    await db.commit()

    return LikeResponse(liked=True, like_count=post.like_count)


@router.delete("/posts/{post_id}/like", response_model=LikeResponse)
async def unlike_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Unlike a post"""
    result = await db.execute(
        select(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == current_user.id)
    )
    like = result.scalar_one_or_none()

    if not like:
        raise HTTPException(status_code=400, detail="Not liked")

    await db.delete(like)

    # Update post count
    post = await db.execute(select(Post).where(Post.id == post_id))
    post = post.scalar_one()
    post.like_count = max(0, (post.like_count or 0) - 1)

    # Update author's like count (lock the row to mirror the like path)
    author = await db.execute(
        select(User).where(User.id == post.author_id).with_for_update()
    )
    author = author.scalar_one()
    author.like_count = max(0, (author.like_count or 0) - 1)

    current_user.like_given_count = max(0, (current_user.like_given_count or 0) - 1)

    # Reverse the XP granted on like so like/unlike cycling can't farm XP/levels.
    await _remove_xp(db, current_user, XP_LIKE_GIVEN)
    await _remove_xp(db, author, XP_LIKE_RECEIVED)

    await db.commit()

    # Reverse leaderboard points (mirrors the post-commit award in like_post).
    await _remove_leaderboard_score(db, post.author_id, 'like_received')
    await _remove_leaderboard_score(db, current_user.id, 'like_given')
    await db.commit()

    return LikeResponse(liked=False, like_count=post.like_count)


# ============================================================================
# POST LIKE ATTRIBUTION
# ============================================================================

@router.get("/posts/{post_id}/likes")
async def get_post_likers(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get users who liked a post"""
    _p = await db.scalar(select(Post).where(Post.id == post_id))
    if not _p:
        raise HTTPException(status_code=404, detail="Post not found")
    _thr = await db.scalar(select(Thread).where(Thread.id == _p.thread_id))
    await assert_board_readable(db, await db.get(ForumBoard, _thr.board_id) if _thr else None, current_user)
    result = await db.execute(
        select(PostLike)
        .where(PostLike.post_id == post_id)
        .options(selectinload(PostLike.user))
        .order_by(PostLike.created_at.desc())
        .limit(50)
    )
    likes = result.scalars().all()
    return [
        {
            "user": user_to_minimal(like.user),
            "created_at": like.created_at.isoformat() if like.created_at else None,
        }
        for like in likes if like.user
    ]
