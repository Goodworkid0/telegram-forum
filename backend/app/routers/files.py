"""Public file board — lists approved files users dropped into the bot, and
delivers a requested file to the user via the bot (no re-hosting)."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import limiter
from app.auth import get_current_active_user
from app.models import User, SharedFile, SharedFileStatus, FileCategory
from app.schemas import SharedFileResponse, FileCategoryResponse
from app.routers.forum_helpers import user_to_minimal
from app.telegram import send_file

router = APIRouter(prefix="/api/files", tags=["Files"])


def serialize_file(f: SharedFile, *, include_admin: bool = False) -> SharedFileResponse:
    return SharedFileResponse(
        id=f.id,
        kind=f.kind,
        file_name=f.file_name,
        mime_type=f.mime_type,
        file_size=f.file_size,
        caption=f.caption,
        uploader=user_to_minimal(f.uploader) if f.uploader else None,
        category_id=f.category_id,
        category_name=f.category.name if f.category else None,
        suggested_category_id=(f.suggested_category_id if include_admin else None),
        suggested_category_name=(f.suggested_category.name if include_admin and f.suggested_category else None),
        download_count=f.download_count or 0,
        created_at=f.created_at,
        status=(f.status.value if include_admin and f.status else None),
        reject_reason=(f.reject_reason if include_admin else None),
    )


@router.get("/categories", response_model=list[FileCategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Active categories for the board filter (ordered)."""
    result = await db.execute(
        select(FileCategory).where(FileCategory.is_active == True)
        .order_by(FileCategory.sort_order, FileCategory.name)
    )
    return [FileCategoryResponse.model_validate(c) for c in result.scalars().all()]


@router.get("")
async def list_files(
    q: str = Query(None, max_length=100),
    category_id: int = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List approved files on the board (newest first), optionally filtered by
    category. category_id=0 selects the uncategorized files."""
    base = select(SharedFile).where(SharedFile.status == SharedFileStatus.APPROVED)
    if q:
        base = base.where(SharedFile.file_name.ilike(f"%{q}%"))
    if category_id is not None:
        base = base.where(SharedFile.category_id == (category_id or None))

    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    result = await db.execute(
        base.options(selectinload(SharedFile.uploader), selectinload(SharedFile.category))
        .order_by(desc(SharedFile.created_at))
        .offset((page - 1) * per_page).limit(per_page)
    )
    items = [serialize_file(f) for f in result.scalars().all()]
    return {"items": items, "total": total or 0, "page": page, "per_page": per_page}


@router.post("/{file_id}/download")
@limiter.limit("20/minute")
async def request_file(
    request: Request,
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Deliver the file to the requesting user via the bot (DM)."""
    f = await db.get(SharedFile, file_id)
    if not f or f.status != SharedFileStatus.APPROVED:
        raise HTTPException(404, "File not found")

    ok, err = await send_file(
        current_user.telegram_id, f.file_id, kind=f.kind,
        caption=f.file_name or None,
    )
    if not ok:
        if err == "not_started":
            raise HTTPException(
                409,
                "Open the bot and tap Start first, then request the file again.",
            )
        raise HTTPException(502, "Could not deliver the file. Please try again.")

    # Best-effort counter; a failed increment must not fail the delivery.
    f.download_count = (f.download_count or 0) + 1
    await db.commit()
    return {"ok": True, "message": "The file has been sent to you on Telegram."}
