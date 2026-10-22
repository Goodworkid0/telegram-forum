"""Forum Board — public read endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.auth import (
    get_current_user,
    get_current_active_user,
)
from app.models import (
    User, UserRole,
    ForumSection, ForumBoard, Thread, Post,
    ThreadStatus,
)
from app.schemas import (
    ForumBoardResponse,
    SuccessResponse,
)
from app.routers.forum_helpers import ROLE_ORDER

router = APIRouter(prefix="/api/forum", tags=["Forum"])


@router.get("/boards/{slug}", response_model=ForumBoardResponse)
async def get_board(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a forum board by slug"""
    query = select(ForumBoard).where(
        ForumBoard.slug == slug,
        ForumBoard.is_visible == True,
    )

    result = await db.execute(query)
    board = result.scalar_one_or_none()

    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    if ROLE_ORDER.get(current_user.role, 0) < ROLE_ORDER.get(board.min_role, 0):
        raise HTTPException(status_code=403, detail="Access restricted")

    # Compute live counts (denormalized fields may be stale)
    thread_count = await db.scalar(
        select(func.count(Thread.id)).where(
            Thread.board_id == board.id,
            Thread.status != ThreadStatus.DELETED,
        )
    )
    post_count = await db.scalar(
        select(func.count(Post.id)).where(
            Post.thread_id == Thread.id,
            Thread.board_id == board.id,
            Thread.status != ThreadStatus.DELETED,
            Post.is_deleted == False,
        )
    )
    board.thread_count = thread_count or 0
    board.post_count = post_count or 0
    board.last_thread = None  # avoid lazy-load in response serialization

    return board



