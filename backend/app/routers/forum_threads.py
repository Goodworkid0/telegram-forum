"""Forum Thread CRUD, listing, pin/feature/lock, likes, watch, views"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime, timedelta
import re

from app.dependencies import limiter

from app.database import get_db
from app.auth import block_if_impersonating
from app.auth import (
    get_current_user,
    get_current_active_user,
    get_current_unmuted_user,
    get_current_verified_user,
    get_current_moderator,
    check_can_post,
    check_can_create_thread,
)
from app.models import (
    User, UserRole, UserBadge,
    ForumSection, ForumBoard, Thread, Post,
    ThreadStatus, ThreadView, ThreadWatch, ThreadLike,
    Poll, PollOption, PollVote, ModAction,
)
from app.schemas import (
    ForumBoardResponse,
    ThreadCreate, ThreadUpdate, ThreadModUpdate, ThreadResponse, ThreadMinimal, ThreadListResponse,
    PollCreate, PollResponse,
    UserMinimal, LikeResponse, SuccessResponse,
)
from app.sanitize import sanitize_content
from app.ledger import record_balance_change, commit_and_broadcast
from app.money import to_money
from app.routers.forum_helpers import (
    slugify, ROLE_ORDER,
    XP_THREAD, XP_POST,
    _award_xp, _add_leaderboard_score,
    _remove_xp, _remove_leaderboard_score,
    user_to_minimal, public_name,
    assert_board_readable,
)
from app.telegram import create_notification

router = APIRouter(prefix="/api/forum", tags=["Forum"])


# ============================================================================
# THREADS - LIST
# ============================================================================

@router.get("/boards/{slug}/threads", response_model=ThreadListResponse)
async def list_board_threads(
    slug: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List threads in a board"""
    # Get board
    result = await db.execute(
        select(ForumBoard).where(ForumBoard.slug == slug, ForumBoard.is_visible == True)
    )
    board = result.scalar_one_or_none()

    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    if ROLE_ORDER.get(current_user.role, 0) < ROLE_ORDER.get(board.min_role, 0):
        raise HTTPException(status_code=403, detail="Access restricted")

    # Base query
    query = (
        select(Thread)
        .where(
            Thread.board_id == board.id,
            Thread.status != ThreadStatus.DELETED,
        )
        .options(
            selectinload(Thread.author),
            selectinload(Thread.last_post_by),
        )
        .order_by(
            desc(Thread.is_pinned),
            desc(Thread.bumped_at),
        )
    )

    # Count total
    count_query = select(func.count(Thread.id)).where(
        Thread.board_id == board.id,
        Thread.status != ThreadStatus.DELETED,
    )
    total = (await db.execute(count_query)).scalar()

    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    threads = result.scalars().all()

    # Get read status for current user
    if threads:
        thread_ids = [t.id for t in threads]
        views_result = await db.execute(
            select(ThreadView.thread_id, ThreadView.last_read_post_id)
            .where(
                ThreadView.thread_id.in_(thread_ids),
                ThreadView.user_id == current_user.id,
            )
        )
        views_map = {row.thread_id: row.last_read_post_id for row in views_result}
    else:
        views_map = {}

    # Build response
    thread_list = []
    for thread in threads:
        has_unread = True
        if thread.id in views_map:
            if views_map[thread.id] and thread.last_post_id:
                has_unread = thread.last_post_id > views_map[thread.id]
            elif not thread.last_post_id:
                has_unread = False

        thread_list.append(ThreadMinimal(
            id=thread.id,
            title=thread.title,
            slug=thread.slug,
            status=thread.status,
            is_pinned=thread.is_pinned,
            is_announcement=thread.is_announcement,
            title_color=thread.title_color,
            title_glow=thread.title_glow or False,
            reply_count=thread.reply_count or 0,
            view_count=thread.view_count or 0,
            like_count=thread.like_count or 0,
            created_at=thread.created_at,
            last_post_at=thread.last_post_at,
            author=user_to_minimal(thread.author),
            last_post_by=user_to_minimal(thread.last_post_by) if thread.last_post_by else None,
            has_unread=has_unread,
        ))

    return ThreadListResponse(
        threads=thread_list,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


# ============================================================================
# THREADS - CREATE
# ============================================================================

@router.post("/boards/{slug}/threads", response_model=ThreadResponse)
@limiter.limit("10/minute")
async def create_thread(
    request: Request,
    slug: str,
    data: ThreadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_unmuted_user),
):
    """Create a new thread in a board"""
    # Admin-configurable daily thread cap (staff exempt).
    if current_user.role not in (UserRole.MODERATOR, UserRole.ADMIN):
        from app.models import AppSettings
        settings = await db.scalar(select(AppSettings).where(AppSettings.id == 1))
        max_per_day = settings.max_threads_per_day if settings and settings.max_threads_per_day else 10
        recent = await db.scalar(
            select(func.count()).select_from(Thread).where(
                Thread.author_id == current_user.id,
                Thread.created_at > datetime.utcnow() - timedelta(days=1),
            )
        )
        if (recent or 0) >= max_per_day:
            raise HTTPException(status_code=429, detail=f"Thread limit reached ({max_per_day}/day). Try again tomorrow.")

    # Get board
    result = await db.execute(
        select(ForumBoard).where(ForumBoard.slug == slug, ForumBoard.is_visible == True)
    )
    board = result.scalar_one_or_none()

    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    # Check permissions
    check_can_create_thread(current_user, board)

    # Create thread
    thread = Thread(
        board_id=board.id,
        author_id=current_user.id,
        title=sanitize_content(data.title),
        slug=slugify(data.title),
        content=sanitize_content(data.content),
        status=ThreadStatus.OPEN,
        tags=",".join(t.strip() for t in data.tags if t.strip()) if data.tags else None,
        last_post_at=datetime.utcnow(),
        last_post_by_id=current_user.id,
        bumped_at=datetime.utcnow(),
    )
    db.add(thread)

    # Update board stats. A new thread is the board's most recent activity but is
    # not a reply, so clear last_post_id (which only ever points to a reply Post)
    # to keep it consistent with last_post_at.
    board.thread_count = (board.thread_count or 0) + 1
    board.last_post_at = datetime.utcnow()
    board.last_post_id = None

    # Update user stats. The opening post counts toward the author's post
    # counter (it's still a post they authored), but NOT toward the thread's
    # reply_count — reply_count only tracks replies, so the board list shows the
    # right reply total and "last reply by" stays hidden until someone replies.
    current_user.thread_count = (current_user.thread_count or 0) + 1
    current_user.post_count = (current_user.post_count or 0) + 1
    current_user.last_post_at = datetime.utcnow()

    # Award XP
    await _award_xp(db, current_user, XP_THREAD)
    await _add_leaderboard_score(db, current_user.id, 'thread')

    await db.flush()

    # Create poll if provided
    if data.poll:
        poll = Poll(
            thread_id=thread.id,
            author_id=current_user.id,
            question=sanitize_content(data.poll.question),
            is_multiple_choice=data.poll.is_multiple_choice,
            max_choices=data.poll.max_choices,
            is_anonymous=data.poll.is_anonymous,
            show_results_before_vote=data.poll.show_results_before_vote,
            allow_vote_change=data.poll.allow_vote_change,
            ends_at=data.poll.ends_at,
        )
        db.add(poll)
        await db.flush()

        # Create poll options
        for i, option in enumerate(data.poll.options):
            poll_option = PollOption(
                poll_id=poll.id,
                text=sanitize_content(option.text),
                sort_order=i,
            )
            db.add(poll_option)

    # Update board last thread
    board.last_thread_id = thread.id
    await db.commit()
    await db.refresh(thread)

    # Load relationships
    result = await db.execute(
        select(Thread)
        .where(Thread.id == thread.id)
        .options(
            selectinload(Thread.author),
            selectinload(Thread.board),
            selectinload(Thread.poll).selectinload(Poll.options),
        )
    )
    thread = result.scalar_one()

    # Build poll response if poll exists
    poll_response = None
    if thread.poll:
        poll = thread.poll
        poll_response = PollResponse(
            id=poll.id,
            question=poll.question,
            is_multiple_choice=poll.is_multiple_choice,
            max_choices=poll.max_choices,
            is_anonymous=poll.is_anonymous,
            show_results_before_vote=poll.show_results_before_vote,
            allow_vote_change=poll.allow_vote_change,
            ends_at=poll.ends_at,
            is_closed=poll.is_closed,
            total_votes=0,
            created_at=poll.created_at,
            options=[
                {
                    "id": opt.id,
                    "text": opt.text,
                    "vote_count": 0,
                    "percentage": 0.0,
                }
                for opt in poll.options
            ],
            has_voted=False,
            voted_options=[],
        )

    return ThreadResponse(
        id=thread.id,
        board_id=thread.board_id,
        title=thread.title,
        title_color=thread.title_color,
        title_glow=thread.title_glow or False,
        last_manual_bump_at=thread.last_manual_bump_at,
        auto_bump_until=thread.auto_bump_until,
        bump_available_at=_bump_available(thread),
        slug=thread.slug,
        content=thread.content,
        status=thread.status,
        is_pinned=thread.is_pinned,
        is_announcement=thread.is_announcement,
        is_featured=thread.is_featured,
        view_count=thread.view_count or 0,
        reply_count=thread.reply_count or 0,
        like_count=thread.like_count or 0,
        is_edited=thread.is_edited,
        edited_at=thread.edited_at,
        edit_count=thread.edit_count or 0,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        last_post_at=thread.last_post_at,
        author=user_to_minimal(thread.author),
        board=thread.board,
        poll=poll_response,
        is_liked=False,
    )


# ============================================================================
# THREADS - GET
# ============================================================================

@router.get("/threads/by-slug/{slug}", response_model=ThreadResponse)
async def get_thread_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a thread by slug"""
    result = await db.execute(
        select(Thread)
        .where(Thread.slug == slug, Thread.status != ThreadStatus.DELETED)
        .options(
            selectinload(Thread.author),
            selectinload(Thread.board).selectinload(ForumBoard.section),
            selectinload(Thread.poll).selectinload(Poll.options),
        )
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    if ROLE_ORDER.get(current_user.role, 0) < ROLE_ORDER.get(thread.board.min_role, 0):
        raise HTTPException(status_code=403, detail="Access restricted")

    # Atomic increment so concurrent views don't lose updates. We deliberately do
    # NOT assign thread.view_count here — an ORM assignment would flush an absolute
    # value on commit and clobber the atomic increment. The response therefore shows
    # the pre-view count (the viewer's own view isn't reflected back), which is fine.
    await db.execute(
        update(Thread).where(Thread.id == thread.id).values(view_count=Thread.view_count + 1)
    )

    view_result = await db.execute(
        select(ThreadView).where(
            ThreadView.thread_id == thread.id,
            ThreadView.user_id == current_user.id,
        )
    )
    view = view_result.scalar_one_or_none()

    if view:
        view.last_viewed_at = datetime.utcnow()
        if thread.last_post_id:
            view.last_read_post_id = thread.last_post_id
    else:
        view = ThreadView(
            thread_id=thread.id,
            user_id=current_user.id,
            last_read_post_id=thread.last_post_id,
            last_viewed_at=datetime.utcnow(),
        )
        db.add(view)

    await db.commit()

    like_result = await db.execute(
        select(ThreadLike).where(
            ThreadLike.thread_id == thread.id,
            ThreadLike.user_id == current_user.id,
        )
    )
    is_liked = like_result.scalar_one_or_none() is not None

    watch_result = await db.execute(
        select(ThreadWatch).where(
            ThreadWatch.thread_id == thread.id,
            ThreadWatch.user_id == current_user.id,
        )
    )
    is_watched = watch_result.scalar_one_or_none() is not None

    poll_response = None
    if thread.poll:
        poll = thread.poll
        total_votes = poll.total_votes or 0
        votes_result = await db.execute(
            select(PollVote.option_id).where(
                PollVote.poll_id == poll.id,
                PollVote.user_id == current_user.id,
            )
        )
        voted_option_ids = [row.option_id for row in votes_result]
        poll_response = PollResponse(
            id=poll.id,
            question=poll.question,
            is_multiple_choice=poll.is_multiple_choice,
            max_choices=poll.max_choices,
            is_anonymous=poll.is_anonymous,
            show_results_before_vote=poll.show_results_before_vote,
            allow_vote_change=poll.allow_vote_change,
            ends_at=poll.ends_at,
            is_closed=poll.is_closed,
            total_votes=total_votes,
            created_at=poll.created_at,
            has_voted=len(voted_option_ids) > 0,
            voted_options=voted_option_ids,
            options=[
                {
                    "id": opt.id,
                    "text": opt.text,
                    "vote_count": opt.vote_count or 0,
                    "percentage": (opt.vote_count or 0) / total_votes * 100 if total_votes > 0 else 0,
                    "sort_order": opt.sort_order,
                }
                for opt in (poll.options or [])
            ],
        )

    # Avoid lazy-load of nested board relationships during serialization
    if thread.board:
        board = thread.board
        board.last_thread = None
        board_dict = ForumBoardResponse(
            id=board.id,
            section_id=board.section_id,
            name=board.name,
            slug=board.slug,
            description=board.description,
            icon=board.icon,
            sort_order=board.sort_order or 0,
            is_visible=board.is_visible,
            is_locked=board.is_locked,
            min_role=board.min_role.value if board.min_role else "TRIAL",
            can_trial_view=board.can_trial_view,
            can_trial_post=board.can_trial_post,
            min_role_to_post=board.min_role_to_post,
            min_role_to_create_thread=board.min_role_to_create_thread,
            thread_count=board.thread_count or 0,
            post_count=board.post_count or 0,
            last_post_at=board.last_post_at,
        )
    else:
        board_dict = None

    # Load author badges via separate query
    author_badges = []
    badge_result = await db.execute(
        select(UserBadge).where(UserBadge.user_id == thread.author_id, UserBadge.is_hidden == False)
        .options(selectinload(UserBadge.badge))
    )
    for ub in badge_result.scalars().all():
        if ub.badge:
            author_badges.append({
                "badge_id": ub.badge.id, "badge_name": ub.badge.name,
                "badge_color": ub.badge.color, "badge_icon": ub.badge.icon,
                "badge_icon_style": ub.badge.icon_style or "default",
                "is_primary": ub.is_primary,
            })

    return ThreadResponse(
        id=thread.id,
        board_id=thread.board_id,
        title=thread.title,
        title_color=thread.title_color,
        title_glow=thread.title_glow or False,
        last_manual_bump_at=thread.last_manual_bump_at,
        auto_bump_until=thread.auto_bump_until,
        bump_available_at=_bump_available(thread),
        slug=thread.slug,
        content=thread.content,
        status=thread.status,
        is_pinned=thread.is_pinned,
        is_announcement=thread.is_announcement,
        is_featured=thread.is_featured,
        tags=thread.tags.split(",") if thread.tags else None,
        view_count=thread.view_count,
        reply_count=thread.reply_count,
        like_count=thread.like_count,
        is_edited=thread.is_edited,
        edited_at=thread.edited_at,
        edit_count=thread.edit_count or 0,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        last_post_at=thread.last_post_at,
        author=user_to_minimal(thread.author),
        author_badges=author_badges,
        board=board_dict,
        poll=poll_response,
        section_name=thread.board.section.name if thread.board and thread.board.section else None,
        section_slug=thread.board.section.slug if thread.board and thread.board.section else None,
        is_liked=is_liked,
        is_watched=is_watched,
    )


@router.get("/threads/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a thread by ID"""
    result = await db.execute(
        select(Thread)
        .where(Thread.id == thread_id, Thread.status != ThreadStatus.DELETED)
        .options(
            selectinload(Thread.author),
            selectinload(Thread.board).selectinload(ForumBoard.section),
            selectinload(Thread.poll).selectinload(Poll.options),
        )
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Check board visibility
    if ROLE_ORDER.get(current_user.role, 0) < ROLE_ORDER.get(thread.board.min_role, 0):
        raise HTTPException(status_code=403, detail="Access restricted")

    # Increment view count atomically (see get_thread_by_slug — no ORM assignment,
    # so the atomic UPDATE isn't clobbered by an absolute value on flush).
    await db.execute(
        update(Thread).where(Thread.id == thread.id).values(view_count=Thread.view_count + 1)
    )

    # Update/create thread view for current user
    view_result = await db.execute(
        select(ThreadView).where(
            ThreadView.thread_id == thread_id,
            ThreadView.user_id == current_user.id,
        )
    )
    view = view_result.scalar_one_or_none()

    if view:
        view.last_viewed_at = datetime.utcnow()
        if thread.last_post_id:
            view.last_read_post_id = thread.last_post_id
    else:
        view = ThreadView(
            thread_id=thread_id,
            user_id=current_user.id,
            last_read_post_id=thread.last_post_id,
            last_viewed_at=datetime.utcnow(),
        )
        db.add(view)

    await db.commit()

    # Check if user liked
    like_result = await db.execute(
        select(ThreadLike).where(
            ThreadLike.thread_id == thread_id,
            ThreadLike.user_id == current_user.id,
        )
    )
    is_liked = like_result.scalar_one_or_none() is not None

    # Check if user is watching
    watch_result = await db.execute(
        select(ThreadWatch).where(
            ThreadWatch.thread_id == thread_id,
            ThreadWatch.user_id == current_user.id,
        )
    )
    is_watched = watch_result.scalar_one_or_none() is not None

    # Build poll response
    poll_response = None
    if thread.poll:
        poll = thread.poll
        total_votes = poll.total_votes or 0

        # Check if user voted
        votes_result = await db.execute(
            select(PollVote.option_id).where(
                PollVote.poll_id == poll.id,
                PollVote.user_id == current_user.id,
            )
        )
        voted_option_ids = [row.option_id for row in votes_result]

        poll_response = PollResponse(
            id=poll.id,
            question=poll.question,
            is_multiple_choice=poll.is_multiple_choice,
            max_choices=poll.max_choices,
            is_anonymous=poll.is_anonymous,
            show_results_before_vote=poll.show_results_before_vote,
            allow_vote_change=poll.allow_vote_change,
            ends_at=poll.ends_at,
            is_closed=poll.is_closed,
            total_votes=total_votes,
            created_at=poll.created_at,
            options=[
                {
                    "id": opt.id,
                    "text": opt.text,
                    "vote_count": opt.vote_count or 0,
                    "percentage": (opt.vote_count or 0) / total_votes * 100 if total_votes > 0 else 0,
                }
                for opt in poll.options
            ],
            has_voted=len(voted_option_ids) > 0,
            voted_options=voted_option_ids,
        )

    # Avoid lazy-load of nested board relationships during serialization
    if thread.board:
        board_obj = thread.board
        board_obj.last_thread = None
        board_data = ForumBoardResponse(
            id=board_obj.id,
            section_id=board_obj.section_id,
            name=board_obj.name,
            slug=board_obj.slug,
            description=board_obj.description,
            icon=board_obj.icon,
            sort_order=board_obj.sort_order or 0,
            is_visible=board_obj.is_visible,
            is_locked=board_obj.is_locked,
            min_role=board_obj.min_role.value if board_obj.min_role else "TRIAL",
            can_trial_view=board_obj.can_trial_view,
            can_trial_post=board_obj.can_trial_post,
            min_role_to_post=board_obj.min_role_to_post,
            min_role_to_create_thread=board_obj.min_role_to_create_thread,
            thread_count=board_obj.thread_count or 0,
            post_count=board_obj.post_count or 0,
            last_post_at=board_obj.last_post_at,
        )
    else:
        board_data = None

    # Load author badges via separate query
    author_badges = []
    badge_result = await db.execute(
        select(UserBadge).where(UserBadge.user_id == thread.author_id, UserBadge.is_hidden == False)
        .options(selectinload(UserBadge.badge))
    )
    for ub in badge_result.scalars().all():
        if ub.badge:
            author_badges.append({
                "badge_id": ub.badge.id, "badge_name": ub.badge.name,
                "badge_color": ub.badge.color, "badge_icon": ub.badge.icon,
                "badge_icon_style": ub.badge.icon_style or "default",
                "is_primary": ub.is_primary,
            })

    return ThreadResponse(
        id=thread.id,
        board_id=thread.board_id,
        title=thread.title,
        title_color=thread.title_color,
        title_glow=thread.title_glow or False,
        last_manual_bump_at=thread.last_manual_bump_at,
        auto_bump_until=thread.auto_bump_until,
        bump_available_at=_bump_available(thread),
        slug=thread.slug,
        content=thread.content,
        status=thread.status,
        is_pinned=thread.is_pinned,
        is_announcement=thread.is_announcement,
        is_featured=thread.is_featured,
        view_count=thread.view_count or 0,
        reply_count=thread.reply_count or 0,
        like_count=thread.like_count or 0,
        is_edited=thread.is_edited,
        edited_at=thread.edited_at,
        edit_count=thread.edit_count or 0,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        last_post_at=thread.last_post_at,
        author=user_to_minimal(thread.author),
        author_badges=author_badges,
        board=board_data,
        poll=poll_response,
        section_name=thread.board.section.name if thread.board and thread.board.section else None,
        section_slug=thread.board.section.slug if thread.board and thread.board.section else None,
        is_liked=is_liked,
        is_watched=is_watched,
    )


# ============================================================================
# THREADS - UPDATE / DELETE
# ============================================================================

async def _serialize_thread_by_id(db: AsyncSession, thread_id: int, current_user: User) -> ThreadResponse:
    """Build a ThreadResponse WITHOUT mutating view state.

    Used by edit/mod endpoints so that editing a thread does not inflate its
    view_count or rewrite the editor's read marker (which calling get_thread did).
    """
    # NOTE: no `status != DELETED` filter here — this serializer is used by the
    # edit/mod endpoints (already authorized), and a mod that just set the thread
    # to DELETED still needs a valid response back (otherwise the request 404s
    # even though the action succeeded, and the client errors out).
    result = await db.execute(
        select(Thread)
        .where(Thread.id == thread_id)
        .options(
            selectinload(Thread.author),
            selectinload(Thread.board).selectinload(ForumBoard.section),
            selectinload(Thread.poll).selectinload(Poll.options),
        )
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    like_result = await db.execute(
        select(ThreadLike).where(
            ThreadLike.thread_id == thread_id,
            ThreadLike.user_id == current_user.id,
        )
    )
    is_liked = like_result.scalar_one_or_none() is not None

    watch_result = await db.execute(
        select(ThreadWatch).where(
            ThreadWatch.thread_id == thread_id,
            ThreadWatch.user_id == current_user.id,
        )
    )
    is_watched = watch_result.scalar_one_or_none() is not None

    poll_response = None
    if thread.poll:
        poll = thread.poll
        total_votes = poll.total_votes or 0
        votes_result = await db.execute(
            select(PollVote.option_id).where(
                PollVote.poll_id == poll.id,
                PollVote.user_id == current_user.id,
            )
        )
        voted_option_ids = [row.option_id for row in votes_result]
        poll_response = PollResponse(
            id=poll.id,
            question=poll.question,
            is_multiple_choice=poll.is_multiple_choice,
            max_choices=poll.max_choices,
            is_anonymous=poll.is_anonymous,
            show_results_before_vote=poll.show_results_before_vote,
            allow_vote_change=poll.allow_vote_change,
            ends_at=poll.ends_at,
            is_closed=poll.is_closed,
            total_votes=total_votes,
            created_at=poll.created_at,
            options=[
                {
                    "id": opt.id,
                    "text": opt.text,
                    "vote_count": opt.vote_count or 0,
                    "percentage": (opt.vote_count or 0) / total_votes * 100 if total_votes > 0 else 0,
                }
                for opt in (poll.options or [])
            ],
            has_voted=len(voted_option_ids) > 0,
            voted_options=voted_option_ids,
        )

    board_data = None
    if thread.board:
        board_obj = thread.board
        board_obj.last_thread = None
        board_data = ForumBoardResponse(
            id=board_obj.id,
            section_id=board_obj.section_id,
            name=board_obj.name,
            slug=board_obj.slug,
            description=board_obj.description,
            icon=board_obj.icon,
            sort_order=board_obj.sort_order or 0,
            is_visible=board_obj.is_visible,
            is_locked=board_obj.is_locked,
            min_role=board_obj.min_role.value if board_obj.min_role else "TRIAL",
            can_trial_view=board_obj.can_trial_view,
            can_trial_post=board_obj.can_trial_post,
            min_role_to_post=board_obj.min_role_to_post,
            min_role_to_create_thread=board_obj.min_role_to_create_thread,
            thread_count=board_obj.thread_count or 0,
            post_count=board_obj.post_count or 0,
            last_post_at=board_obj.last_post_at,
        )

    author_badges = []
    badge_result = await db.execute(
        select(UserBadge).where(UserBadge.user_id == thread.author_id, UserBadge.is_hidden == False)
        .options(selectinload(UserBadge.badge))
    )
    for ub in badge_result.scalars().all():
        if ub.badge:
            author_badges.append({
                "badge_id": ub.badge.id, "badge_name": ub.badge.name,
                "badge_color": ub.badge.color, "badge_icon": ub.badge.icon,
                "badge_icon_style": ub.badge.icon_style or "default",
                "is_primary": ub.is_primary,
            })

    return ThreadResponse(
        id=thread.id,
        board_id=thread.board_id,
        title=thread.title,
        title_color=thread.title_color,
        title_glow=thread.title_glow or False,
        last_manual_bump_at=thread.last_manual_bump_at,
        auto_bump_until=thread.auto_bump_until,
        bump_available_at=_bump_available(thread),
        slug=thread.slug,
        content=thread.content,
        status=thread.status,
        is_pinned=thread.is_pinned,
        is_announcement=thread.is_announcement,
        is_featured=thread.is_featured,
        tags=thread.tags.split(",") if thread.tags else None,
        view_count=thread.view_count or 0,
        reply_count=thread.reply_count or 0,
        like_count=thread.like_count or 0,
        is_edited=thread.is_edited,
        edited_at=thread.edited_at,
        edit_count=thread.edit_count or 0,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        last_post_at=thread.last_post_at,
        author=user_to_minimal(thread.author),
        author_badges=author_badges,
        board=board_data,
        poll=poll_response,
        section_name=thread.board.section.name if thread.board and thread.board.section else None,
        section_slug=thread.board.section.slug if thread.board and thread.board.section else None,
        is_liked=is_liked,
        is_watched=is_watched,
    )


@router.put("/threads/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: int,
    data: ThreadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_unmuted_user),
):
    """Update a thread (author or moderator only)"""
    result = await db.execute(
        select(Thread)
        .where(Thread.id == thread_id, Thread.status != ThreadStatus.DELETED)
        .options(selectinload(Thread.author), selectinload(Thread.board))
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Check permissions
    if thread.author_id != current_user.id and current_user.role not in (UserRole.MODERATOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Not authorized to edit this thread")

    # Check if thread is locked
    if thread.status == ThreadStatus.LOCKED and current_user.role not in (UserRole.MODERATOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Thread is locked")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key in ('title', 'content'):
            value = sanitize_content(value)
        setattr(thread, key, value)

    thread.is_edited = True
    thread.edited_at = datetime.utcnow()
    thread.edit_count = (thread.edit_count or 0) + 1

    await db.commit()
    await db.refresh(thread)

    # Serialize without mutating view state (editing must not inflate view_count).
    return await _serialize_thread_by_id(db, thread_id, current_user)


@router.patch("/threads/{thread_id}/mod", response_model=ThreadResponse)
async def mod_update_thread(
    thread_id: int,
    data: ThreadModUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator),
):
    """Moderator actions on thread (pin, lock, etc.)"""
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(thread, key, value)

    await db.commit()
    await db.refresh(thread)

    # Log mod action
    action_details = []
    if data.is_pinned is not None:
        action_details.append(f"pinned={'true' if data.is_pinned else 'false'}")
    if data.status is not None:
        action_details.append(f"status={data.status}")
    if data.is_featured is not None:
        action_details.append(f"featured={'true' if data.is_featured else 'false'}")
    if data.is_announcement is not None:
        action_details.append(f"announcement={'true' if data.is_announcement else 'false'}")

    if action_details:
        mod_action = ModAction(
            moderator_id=current_user.id,
            target_user_id=thread.author_id,
            action_type="thread_mod",
            reason=f"Thread #{thread_id}: " + ", ".join(action_details),
        )
        db.add(mod_action)
        await db.commit()

    # Serialize without mutating view state.
    return await _serialize_thread_by_id(db, thread_id, current_user)


# ============================================================================
# THREAD UPGRADES — author lock, free/paid bump, stand-out title
# ============================================================================

BUMP_COOLDOWN = timedelta(hours=48)
AUTO_BUMP_INTERVAL = timedelta(hours=48)
AUTO_BUMP_DURATION = timedelta(days=30)
TITLE_STYLE_PRICE = to_money(20)
AUTO_BUMP_PRICE = to_money(60)
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")


def _bump_thread(thread: Thread) -> None:
    """Resurface a thread: move it to the top of its board list (bumped_at) and
    mark it recently active in the activity feed (last_post_at), without a reply."""
    now = datetime.utcnow()
    thread.bumped_at = now
    thread.last_post_at = now
    if not thread.last_post_by_id:
        thread.last_post_by_id = thread.author_id


def _bump_available(thread: Thread):
    """When this thread may next be manually bumped via the button (None = now)."""
    if thread.last_manual_bump_at and (datetime.utcnow() - thread.last_manual_bump_at) < BUMP_COOLDOWN:
        return thread.last_manual_bump_at + BUMP_COOLDOWN
    return None


async def _own_thread_or_403(db: AsyncSession, thread_id: int, current_user: User, *, lock: bool = False) -> Thread:
    q = select(Thread).where(Thread.id == thread_id, Thread.status != ThreadStatus.DELETED)
    if lock:
        q = q.with_for_update()
    thread = await db.scalar(q)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    is_mod = current_user.role in (UserRole.MODERATOR, UserRole.ADMIN)
    if thread.author_id != current_user.id and not is_mod:
        raise HTTPException(status_code=403, detail="You can only manage your own threads")
    return thread


@router.post("/threads/{thread_id}/lock", response_model=ThreadResponse)
async def toggle_thread_lock(
    thread_id: int,
    locked: bool = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """Author (USER+) locks/unlocks their OWN thread (no replies while locked)."""
    thread = await _own_thread_or_403(db, thread_id, current_user)
    if thread.status not in (ThreadStatus.OPEN, ThreadStatus.LOCKED):
        raise HTTPException(status_code=400, detail="This thread can't be locked")
    thread.status = ThreadStatus.LOCKED if locked else ThreadStatus.OPEN
    await db.commit()
    return await _serialize_thread_by_id(db, thread_id, current_user)


@router.post("/threads/{thread_id}/bump", response_model=ThreadResponse)
async def bump_thread(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """Free manual bump of your OWN thread — once per 48h. (Replies also bump, no cooldown.)"""
    thread = await _own_thread_or_403(db, thread_id, current_user, lock=True)
    if thread.status != ThreadStatus.OPEN:
        raise HTTPException(status_code=400, detail="Only open threads can be bumped")
    now = datetime.utcnow()
    if thread.last_manual_bump_at and (now - thread.last_manual_bump_at) < BUMP_COOLDOWN:
        nxt = thread.last_manual_bump_at + BUMP_COOLDOWN
        raise HTTPException(status_code=429, detail=f"You can bump this thread again after {nxt.isoformat()}Z")
    _bump_thread(thread)
    thread.last_manual_bump_at = now
    await db.commit()
    return await _serialize_thread_by_id(db, thread_id, current_user)


@router.post("/threads/{thread_id}/title-style", response_model=ThreadResponse)
async def purchase_title_style(
    thread_id: int,
    color: Optional[str] = Query(None, description="Hex color, e.g. #00c8e6; empty clears it"),
    glow: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
    _imp: User = Depends(block_if_impersonating),
):
    """Buy a stand-out (colored / glowing) title for your thread — $20."""
    from app.pricing import get_price
    TITLE_STYLE_PRICE = await get_price(db, "thread_title_price")
    thread = await _own_thread_or_403(db, thread_id, current_user, lock=True)
    color = (color or "").strip() or None
    if color and not _HEX_RE.match(color):
        raise HTTPException(status_code=400, detail="Color must be a hex value like #00c8e6")

    user = await db.scalar(select(User).where(User.id == current_user.id).with_for_update())
    if to_money(user.balance) < TITLE_STYLE_PRICE:
        raise HTTPException(status_code=400, detail=f"Insufficient balance. Title styling costs ${TITLE_STYLE_PRICE}.")
    record_balance_change(
        db, user, delta=-TITLE_STYLE_PRICE, entry_type="thread_title_style",
        ref_type="thread", ref_id=thread.id, description=f"Stand-out title for thread #{thread.id}",
    )
    thread.title_color = color
    thread.title_glow = bool(glow)
    await commit_and_broadcast(db)
    return await _serialize_thread_by_id(db, thread_id, current_user)


@router.post("/threads/{thread_id}/auto-bump", response_model=ThreadResponse)
async def purchase_auto_bump(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
    _imp: User = Depends(block_if_impersonating),
):
    """Buy auto-bump: the thread is auto-bumped to the top every 48h for 30 days — $60."""
    from app.pricing import get_price
    AUTO_BUMP_PRICE = await get_price(db, "thread_autobump_price")
    thread = await _own_thread_or_403(db, thread_id, current_user, lock=True)
    user = await db.scalar(select(User).where(User.id == current_user.id).with_for_update())
    if to_money(user.balance) < AUTO_BUMP_PRICE:
        raise HTTPException(status_code=400, detail=f"Insufficient balance. Auto-bump costs ${AUTO_BUMP_PRICE}.")
    record_balance_change(
        db, user, delta=-AUTO_BUMP_PRICE, entry_type="thread_auto_bump",
        ref_type="thread", ref_id=thread.id, description=f"30-day auto-bump for thread #{thread.id}",
    )
    now = datetime.utcnow()
    # Stack: extend from the current expiry if still active, else start now.
    base = thread.auto_bump_until if (thread.auto_bump_until and thread.auto_bump_until > now) else now
    thread.auto_bump_until = base + AUTO_BUMP_DURATION
    # Bump immediately and arm the 48h interval.
    _bump_thread(thread)
    thread.last_auto_bump_at = now
    await commit_and_broadcast(db)
    return await _serialize_thread_by_id(db, thread_id, current_user)


# ============================================================================
# THREAD LIKES
# ============================================================================

@router.post("/threads/{thread_id}/like", response_model=LikeResponse)
async def like_thread(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """Like a thread"""
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id, Thread.status != ThreadStatus.DELETED)
        .with_for_update()
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    await assert_board_readable(db, await db.get(ForumBoard, thread.board_id), current_user)

    # Check if already liked
    existing = await db.execute(
        select(ThreadLike).where(
            ThreadLike.thread_id == thread_id,
            ThreadLike.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already liked")

    # Can't like own thread
    if thread.author_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot like your own thread")

    like = ThreadLike(thread_id=thread_id, user_id=current_user.id)
    db.add(like)

    thread.like_count = (thread.like_count or 0) + 1

    # Update author's like count
    author = await db.execute(
        select(User).where(User.id == thread.author_id).with_for_update()
    )
    author = author.scalar_one()
    author.like_count = (author.like_count or 0) + 1

    current_user.like_given_count = (current_user.like_given_count or 0) + 1

    await db.commit()
    await _add_leaderboard_score(db, thread.author_id, 'like_received')
    await _add_leaderboard_score(db, current_user.id, 'like_given')

    # Notify author
    await create_notification(
        db,
        user_id=thread.author_id,
        type="thread_like",
        title="Your thread was liked",
        body=f"{public_name(current_user)} liked your thread",
        link=f"/thread/{thread.slug}",
        related_user_id=current_user.id,
        related_thread_id=thread_id,
    )
    await db.commit()

    return LikeResponse(liked=True, like_count=thread.like_count)


@router.delete("/threads/{thread_id}/like", response_model=LikeResponse)
async def unlike_thread(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Unlike a thread"""
    result = await db.execute(
        select(ThreadLike).where(
            ThreadLike.thread_id == thread_id,
            ThreadLike.user_id == current_user.id,
        )
    )
    like = result.scalar_one_or_none()

    if not like:
        raise HTTPException(status_code=400, detail="Not liked")

    await db.delete(like)

    # Update thread count
    thread = await db.execute(select(Thread).where(Thread.id == thread_id))
    thread = thread.scalar_one()
    thread.like_count = max(0, (thread.like_count or 0) - 1)

    # Update author's like count (lock to mirror the like path)
    author = await db.execute(
        select(User).where(User.id == thread.author_id).with_for_update()
    )
    author = author.scalar_one()
    author.like_count = max(0, (author.like_count or 0) - 1)

    current_user.like_given_count = max(0, (current_user.like_given_count or 0) - 1)

    await db.commit()

    # Reverse leaderboard points so thread like/unlike cycling can't farm rank.
    await _remove_leaderboard_score(db, thread.author_id, 'like_received')
    await _remove_leaderboard_score(db, current_user.id, 'like_given')
    await db.commit()

    return LikeResponse(liked=False, like_count=thread.like_count)


# ============================================================================
# THREAD LIKE ATTRIBUTION
# ============================================================================

@router.get("/threads/{thread_id}/likes")
async def get_thread_likers(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get users who liked a thread"""
    _t = await db.scalar(select(Thread).where(Thread.id == thread_id))
    if not _t:
        raise HTTPException(status_code=404, detail="Thread not found")
    await assert_board_readable(db, await db.get(ForumBoard, _t.board_id), current_user)
    result = await db.execute(
        select(ThreadLike)
        .where(ThreadLike.thread_id == thread_id)
        .options(selectinload(ThreadLike.user))
        .order_by(ThreadLike.created_at.desc())
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


# ============================================================================
# THREAD WATCH (Subscribe for notifications)
# ============================================================================

@router.post("/threads/{thread_id}/watch", response_model=SuccessResponse)
async def watch_thread(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Watch a thread for new reply notifications"""
    thread = await db.scalar(select(Thread).where(Thread.id == thread_id, Thread.status != ThreadStatus.DELETED))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    await assert_board_readable(db, await db.get(ForumBoard, thread.board_id), current_user)

    existing = await db.scalar(
        select(ThreadWatch).where(ThreadWatch.thread_id == thread_id, ThreadWatch.user_id == current_user.id)
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already watching")

    db.add(ThreadWatch(thread_id=thread_id, user_id=current_user.id))
    await db.commit()
    return SuccessResponse(message="Watching thread")


@router.delete("/threads/{thread_id}/watch", response_model=SuccessResponse)
async def unwatch_thread(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Stop watching a thread"""
    watch = await db.scalar(
        select(ThreadWatch).where(ThreadWatch.thread_id == thread_id, ThreadWatch.user_id == current_user.id)
    )
    if not watch:
        raise HTTPException(status_code=400, detail="Not watching")

    await db.delete(watch)
    await db.commit()
    return SuccessResponse(message="Stopped watching thread")
