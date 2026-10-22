"""Forum Tab & Section CRUD, Forum Stats, Image Upload, Search"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel as PydanticBaseModel
import os
import uuid
import asyncio

from app.dependencies import limiter

from app.database import get_db
from app.auth import (
    get_current_user,
    get_current_active_user,
)
from app.models import (
    User, UserRole, UserBadge,
    ForumSection, ForumBoard, ForumTab, Thread, Post,
    ThreadStatus, ThreadView, PostLike, ReputationEntry,
)
from app.schemas import (
    ForumSectionResponse,
    ForumTabResponse, ForumTabWithSectionsResponse,
    UserMinimal, SuccessResponse, ThreadMinimal, PostResponse,
)
from app.routers.forum_helpers import (
    ROLE_ORDER, user_to_minimal,
)
from app.images import process_upload, validated_image_extension, InvalidImageError
from app.search import IS_POSTGRES, fts_match, fts_rank

router = APIRouter(prefix="/api/forum", tags=["Forum"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "images")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


def _write_file(filepath: str, data: bytes) -> None:
    """Blocking file write — call via asyncio.to_thread from async handlers."""
    with open(filepath, "wb") as f:
        f.write(data)


# ============================================================================
# FORUM STATS
# ============================================================================

class LatestUserInfo(PydanticBaseModel):
    id: int
    username: str
    # Needed by displayName(): members who hide their @handle are shown by
    # display name — without it they'd all render as the literal "User".
    first_name: Optional[str] = None
    avatar_url: Optional[str] = None
    show_telegram: bool = True
    joined_at: datetime

class ForumStatsResponse(PydanticBaseModel):
    total_threads: int
    total_posts: int
    total_users: int
    online_24h: int
    latest_user: Optional[LatestUserInfo] = None

@router.get("/stats", response_model=ForumStatsResponse)
async def get_forum_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get forum-wide statistics"""
    last_24h = datetime.utcnow() - timedelta(hours=24)

    total_threads = await db.scalar(select(func.count()).select_from(Thread)) or 0
    total_posts = await db.scalar(select(func.count()).select_from(Post)) or 0
    total_users = await db.scalar(select(func.count()).select_from(User)) or 0
    online_24h = await db.scalar(
        select(func.count()).select_from(User).where(User.last_seen_at >= last_24h)
    ) or 0

    # Get latest registered user
    latest_user_result = await db.execute(
        select(User).order_by(desc(User.created_at)).limit(1)
    )
    latest_user = latest_user_result.scalar_one_or_none()

    latest_user_info = None
    if latest_user:
        latest_user_info = LatestUserInfo(
            id=latest_user.id,
            username=latest_user.username or f"user_{latest_user.id}",
            first_name=latest_user.first_name,
            avatar_url=latest_user.avatar_url,
            show_telegram=latest_user.show_telegram if latest_user.show_telegram is not None else True,
            joined_at=latest_user.created_at
        )

    return ForumStatsResponse(
        total_threads=total_threads,
        total_posts=total_posts,
        total_users=total_users,
        online_24h=online_24h,
        latest_user=latest_user_info
    )


# ============================================================================
# IMAGE UPLOAD
# ============================================================================

@router.post("/upload-image")
@limiter.limit("10/minute")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Upload an image for use in posts/threads"""
    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    # Validate by content (magic bytes), not the client-supplied type/filename.
    if validated_image_extension(contents) is None:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: JPEG, PNG, GIF, WebP")

    raw_filename = f"{current_user.id}_{uuid.uuid4().hex[:12]}.webp"

    # Process image off the event loop (Pillow encode is CPU-bound and blocking).
    try:
        processed_bytes, filename = await asyncio.to_thread(process_upload, contents, raw_filename)
    except InvalidImageError:
        raise HTTPException(status_code=400, detail="Invalid or corrupt image")
    filepath = os.path.join(UPLOAD_DIR, filename)

    await asyncio.to_thread(_write_file, filepath, processed_bytes)

    return {"url": f"/api/uploads/images/{filename}"}


# ============================================================================
# SEARCH & DISCOVERY
# ============================================================================

# Search endpoint moved to end of file


def _thread_to_feed_item(t: Thread) -> dict:
    """Serialize a Thread as a 'thread' activity-feed item."""
    return {
        "type": "thread",
        "id": t.id,
        "title": t.title,
        "slug": t.slug,
        "title_color": t.title_color,
        "title_glow": bool(t.title_glow),
        "reply_count": t.reply_count or 0,
        "view_count": t.view_count or 0,
        "like_count": t.like_count or 0,
        "is_pinned": t.is_pinned,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "last_post_at": t.last_post_at.isoformat() if t.last_post_at else None,
        "author": user_to_minimal(t.author) if t.author else None,
        "last_post_by": user_to_minimal(t.last_post_by) if t.last_post_by else None,
        "board_name": t.board.name if t.board else None,
        "board_slug": t.board.slug if t.board else None,
    }


@router.get("/activity-count")
async def get_activity_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    now = datetime.utcnow()
    since = now - timedelta(hours=24)

    thread_count_result = await db.execute(
        select(func.count(Thread.id)).where(
            Thread.status != ThreadStatus.DELETED,
            Thread.created_at >= since,
        )
    )
    thread_count = thread_count_result.scalar() or 0

    post_count_result = await db.execute(
        select(func.count(Post.id)).where(
            Post.is_deleted == False,
            Post.created_at >= since,
        )
    )
    post_count = post_count_result.scalar() or 0

    return {"total": thread_count + post_count, "threads": thread_count, "posts": post_count, "since_hours": 24}


@router.get("/activity-feed")
@limiter.limit("60/minute")
async def get_activity_feed(
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Unified activity feed: recently active threads, new member joins, and
    reputation (+rep / -rep) events, merged and ordered newest-first.

    Each source is queried independently and ordered by its own timestamp, then
    the streams are merged in Python. To paginate correctly across the merged
    stream we over-fetch ``offset + limit`` rows from every source so the global
    top ``offset + limit`` items are guaranteed to be present before slicing.
    """
    offset = (page - 1) * limit
    fetch_n = offset + limit

    # --- recently active threads ---
    thread_rows = (await db.execute(
        select(Thread)
        .where(Thread.status != ThreadStatus.DELETED)
        .options(
            selectinload(Thread.author),
            selectinload(Thread.board),
            selectinload(Thread.last_post_by),
        )
        .order_by(desc(Thread.last_post_at))
        .limit(fetch_n)
    )).scalars().all()

    # --- new member joins (skip banned/inactive accounts) ---
    join_rows = (await db.execute(
        select(User)
        .where(User.is_banned == False, User.is_active == True)
        .order_by(desc(User.created_at))
        .limit(fetch_n)
    )).scalars().all()

    # --- reputation events ---
    rep_rows = (await db.execute(
        select(ReputationEntry)
        .options(
            selectinload(ReputationEntry.from_user),
            selectinload(ReputationEntry.to_user),
        )
        .order_by(desc(ReputationEntry.created_at))
        .limit(fetch_n)
    )).scalars().all()

    # Merge into a single (timestamp, payload) list. datetime.min is the fallback
    # so rows with a NULL timestamp sort to the very bottom rather than crash.
    merged: list[tuple[datetime, dict]] = []

    for t in thread_rows:
        ts = t.last_post_at or t.created_at
        merged.append((ts or datetime.min, _thread_to_feed_item(t)))

    for u in join_rows:
        ts = u.created_at
        merged.append((ts or datetime.min, {
            "type": "join",
            "id": u.id,
            "created_at": ts.isoformat() if ts else None,
            "user": user_to_minimal(u),
        }))

    for r in rep_rows:
        ts = r.created_at
        merged.append((ts or datetime.min, {
            "type": "rep",
            "id": r.id,
            "is_positive": bool(r.is_positive),
            "comment": r.comment,
            "created_at": ts.isoformat() if ts else None,
            "from_user": user_to_minimal(r.from_user) if r.from_user else None,
            "to_user": user_to_minimal(r.to_user) if r.to_user else None,
        }))

    merged.sort(key=lambda x: x[0], reverse=True)
    page_items = [item for _, item in merged[offset:offset + limit]]

    # Totals per source for pagination / display.
    total_threads = await db.scalar(
        select(func.count()).select_from(Thread).where(Thread.status != ThreadStatus.DELETED)
    ) or 0
    total_joins = await db.scalar(
        select(func.count()).select_from(User).where(User.is_banned == False, User.is_active == True)
    ) or 0
    total_rep = await db.scalar(
        select(func.count()).select_from(ReputationEntry)
    ) or 0

    return {
        "items": page_items,
        "total": total_threads + total_joins + total_rep,
        "page": page,
        "per_page": limit,
    }


# ============================================================================
# FORUM TABS
# ============================================================================

@router.get("/tabs", response_model=List[ForumTabWithSectionsResponse])
async def list_tabs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all visible forum tabs with their sections and boards"""
    query = select(ForumTab).where(ForumTab.is_visible == True)
    query = query.options(
        selectinload(ForumTab.sections)
            .selectinload(ForumSection.boards)
            .selectinload(ForumBoard.last_thread)
            .selectinload(Thread.author),
        selectinload(ForumTab.sections)
            .selectinload(ForumSection.boards)
            .selectinload(ForumBoard.last_thread)
            .selectinload(Thread.last_post_by),
    ).order_by(ForumTab.sort_order)

    result = await db.execute(query)
    tabs = result.scalars().all()

    # Tab-level access control. Admins see every tab; otherwise a tab is hidden
    # unless the user meets its min_role AND (for badge-gated tabs) holds the
    # required badge.
    is_admin = current_user.role == UserRole.ADMIN
    user_badge_ids: set[int] = set()
    if not is_admin and any(t.required_badge_id for t in tabs):
        rows = await db.execute(
            select(UserBadge.badge_id).where(UserBadge.user_id == current_user.id)
        )
        user_badge_ids = {r[0] for r in rows}

    def _tab_visible(tab) -> bool:
        if is_admin:
            return True
        if ROLE_ORDER.get(current_user.role, 0) < ROLE_ORDER.get(tab.min_role, 0):
            return False
        if tab.required_badge_id and tab.required_badge_id not in user_badge_ids:
            return False
        return True

    tabs = [t for t in tabs if _tab_visible(t)]

    # Filter sections by visibility and min_role requirement
    for tab in tabs:
        tab.sections = [
            s for s in tab.sections
            if s.is_visible and ROLE_ORDER.get(current_user.role, 0) >= ROLE_ORDER.get(s.min_role, 0)
        ]

    return tabs


# ============================================================================
# FORUM SECTIONS
# ============================================================================

# ============================================================================
# SEARCH
# ============================================================================

class ForumSearchResultItem(PydanticBaseModel):
    """A unified search hit (thread or post) for the search results list."""
    type: str                       # "thread" | "post"
    thread_id: int
    thread_title: Optional[str] = None
    thread_slug: Optional[str] = None
    post_id: Optional[int] = None   # None for thread hits
    snippet: Optional[str] = None
    board_name: Optional[str] = None
    author: Optional[UserMinimal] = None
    created_at: Optional[datetime] = None


class ForumSearchResponse(PydanticBaseModel):
    # Unified, flat results list consumed by the search UIs (ForumHome / Board).
    results: List[ForumSearchResultItem] = []
    total: int = 0
    # Structured breakdown (kept for callers that want it).
    threads: List[ThreadMinimal] = []
    posts: List[PostResponse] = []
    users: List[UserMinimal] = []
    total_threads: int = 0
    total_posts: int = 0
    total_users: int = 0


@router.get("/search", response_model=ForumSearchResponse)
@limiter.limit("30/minute")
async def search_forum(
    request: Request,
    q: str = Query(..., min_length=2, max_length=200),
    type: str = Query("all", pattern="^(threads|posts|users|all)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Search threads, posts, and users by content"""
    offset = (page - 1) * per_page
    pattern = f"%{q}%"
    result = ForumSearchResponse()

    search_threads = type in ("threads", "all")
    search_posts = type in ("posts", "all")
    search_users = type in ("users", "all")

    if search_threads:
        if IS_POSTGRES:
            thread_where = fts_match("threads", q)
            thread_order = [desc(fts_rank("threads", q)), desc(Thread.bumped_at)]
        else:
            thread_where = (Thread.title.ilike(pattern) | Thread.content.ilike(pattern))
            thread_order = [desc(Thread.bumped_at)]

        thread_q = (
            select(Thread)
            .where(thread_where, Thread.status != ThreadStatus.DELETED)
            .options(selectinload(Thread.author), selectinload(Thread.last_post_by), selectinload(Thread.board))
            .order_by(*thread_order)
            .offset(offset)
            .limit(per_page)
        )
        thread_count_q = select(func.count()).select_from(Thread).where(
            thread_where, Thread.status != ThreadStatus.DELETED,
        )

        thread_res = await db.execute(thread_q)
        threads = thread_res.scalars().all()
        result.total_threads = await db.scalar(thread_count_q) or 0

        if threads:
            thread_ids = [t.id for t in threads]
            views_res = await db.execute(
                select(ThreadView.thread_id, ThreadView.last_read_post_id)
                .where(
                    ThreadView.thread_id.in_(thread_ids),
                    ThreadView.user_id == current_user.id,
                )
            )
            views_map = {row.thread_id: row.last_read_post_id for row in views_res}
        else:
            views_map = {}

        result.threads = []
        for t in threads:
            has_unread = True
            if t.id in views_map:
                if views_map[t.id] and t.last_post_id:
                    has_unread = t.last_post_id > views_map[t.id]
                elif not t.last_post_id:
                    has_unread = False
            result.threads.append(ThreadMinimal(
                id=t.id,
                title=t.title,
                slug=t.slug,
                status=t.status,
                is_pinned=t.is_pinned,
                is_announcement=t.is_announcement,
                title_color=t.title_color,
                title_glow=t.title_glow or False,
                reply_count=t.reply_count or 0,
                view_count=t.view_count or 0,
                like_count=t.like_count or 0,
                created_at=t.created_at,
                last_post_at=t.last_post_at,
                author=user_to_minimal(t.author) if t.author else None,
                last_post_by=user_to_minimal(t.last_post_by) if t.last_post_by else None,
                has_unread=has_unread,
            ))
            result.results.append(ForumSearchResultItem(
                type="thread",
                thread_id=t.id,
                thread_title=t.title,
                thread_slug=t.slug,
                post_id=None,
                snippet=(t.content or "")[:200],
                board_name=t.board.name if t.board else None,
                author=user_to_minimal(t.author) if t.author else None,
                created_at=t.created_at,
            ))

    if search_posts:
        if IS_POSTGRES:
            post_where = fts_match("posts", q)
            post_order = [desc(fts_rank("posts", q)), desc(Post.created_at)]
        else:
            post_where = Post.content.ilike(pattern)
            post_order = [desc(Post.created_at)]

        post_q = (
            select(Post)
            .where(post_where, Post.is_deleted == False)
            .options(
                selectinload(Post.author),
                selectinload(Post.thread).selectinload(Thread.board),
                selectinload(Post.parent).selectinload(Post.author),
            )
            .order_by(*post_order)
            .offset(offset)
            .limit(per_page)
        )
        post_count_q = select(func.count()).select_from(Post).where(
            post_where, Post.is_deleted == False,
        )

        post_res = await db.execute(post_q)
        posts = post_res.scalars().all()
        result.total_posts = await db.scalar(post_count_q) or 0

        liked_posts: set = set()
        if posts:
            post_ids = [p.id for p in posts]
            likes_res = await db.execute(
                select(PostLike.post_id).where(
                    PostLike.post_id.in_(post_ids),
                    PostLike.user_id == current_user.id,
                )
            )
            liked_posts = {row.post_id for row in likes_res}

        result.posts = []
        for p in posts:
            parent_author = None
            parent_preview = None
            if p.parent and p.parent.author:
                parent_author = user_to_minimal(p.parent.author)
                parent_preview = (p.parent.content or "")[:120]
            result.posts.append(PostResponse(
                id=p.id,
                thread_id=p.thread_id,
                thread_slug=p.thread.slug if p.thread else None,
                content=p.content,
                parent_id=p.parent_id,
                is_edited=p.is_edited,
                edited_at=p.edited_at,
                edit_count=p.edit_count or 0,
                like_count=p.like_count or 0,
                is_best_answer=p.is_best_answer,
                is_deleted=p.is_deleted,
                delete_reason=p.delete_reason,
                created_at=p.created_at,
                author=user_to_minimal(p.author) if p.author else None,
                parent_author=parent_author,
                parent_preview=parent_preview,
                is_liked=p.id in liked_posts,
            ))
            result.results.append(ForumSearchResultItem(
                type="post",
                thread_id=p.thread_id,
                thread_title=p.thread.title if p.thread else None,
                thread_slug=p.thread.slug if p.thread else None,
                post_id=p.id,
                snippet=(p.content or "")[:200],
                board_name=p.thread.board.name if p.thread and p.thread.board else None,
                author=user_to_minimal(p.author) if p.author else None,
                created_at=p.created_at,
            ))

    if search_users:
        user_q = (
            select(User)
            .where(
                (User.username.ilike(pattern) | User.first_name.ilike(pattern)),
                User.is_active == True,
            )
            .order_by(desc(User.post_count))
            .offset(offset)
            .limit(per_page)
        )
        user_count_q = select(func.count()).select_from(User).where(
            (User.username.ilike(pattern) | User.first_name.ilike(pattern)),
            User.is_active == True,
        )

        user_res = await db.execute(user_q)
        users = user_res.scalars().all()
        result.total_users = await db.scalar(user_count_q) or 0

        result.users = [user_to_minimal(u) for u in users]

    # `total` backs the "N results" label in the search UIs (threads + posts).
    result.total = result.total_threads + result.total_posts
    return result
