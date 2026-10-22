"""Reports & Moderation API Router"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.dependencies import limiter
from app.auth import get_current_active_user, get_current_moderator
from app.sanitize import sanitize_content
from app.routers.forum_helpers import _award_xp
from app.moderation import apply_ban, apply_mute, clear_mute
from app.telegram import create_notification
from app.models import (
    User, UserRole, Report, ReportStatus, ReportType,
    ModAction, Thread, Post, Notification, ThreadStatus,
)
from app.schemas import (
    ReportCreate, ReportResponse, ReportListResponse,
    ModActionResponse, SuccessResponse,
)

router = APIRouter(prefix="/api", tags=["Reports & Moderation"])


# ============================================================================
# USER REPORT ENDPOINTS
# ============================================================================

@router.post("/reports", response_model=ReportResponse)
@limiter.limit("10/minute")
async def create_report(
    request: Request,
    data: ReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Report content (thread, post, or user)"""
    # Validate report type and target
    if data.report_type == ReportType.THREAD:
        result = await db.execute(select(Thread).where(Thread.id == data.thread_id))
        target = result.scalar_one_or_none()
        if not target:
            raise HTTPException(status_code=404, detail="Thread not found")
        reported_user_id = target.author_id
    elif data.report_type == ReportType.POST:
        result = await db.execute(select(Post).where(Post.id == data.post_id))
        target = result.scalar_one_or_none()
        if not target:
            raise HTTPException(status_code=404, detail="Post not found")
        reported_user_id = target.author_id
    elif data.report_type == ReportType.USER:
        result = await db.execute(select(User).where(User.id == data.reported_user_id))
        target = result.scalar_one_or_none()
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        reported_user_id = data.reported_user_id
    else:
        raise HTTPException(status_code=400, detail="Invalid report type")
    
    # Can't report yourself
    if reported_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot report yourself")
    
    # Check for duplicate pending reports
    existing = await db.execute(
        select(Report).where(
            Report.reporter_id == current_user.id,
            Report.report_type == data.report_type,
            Report.status == ReportStatus.PENDING,
            or_(
                and_(data.thread_id is not None, Report.thread_id == data.thread_id),
                and_(data.post_id is not None, Report.post_id == data.post_id),
                and_(data.reported_user_id is not None, Report.reported_user_id == data.reported_user_id),
            ),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You already have a pending report for this content")
    
    report = Report(
        reporter_id=current_user.id,
        report_type=data.report_type,
        thread_id=data.thread_id,
        post_id=data.post_id,
        reported_user_id=reported_user_id,
        reason=sanitize_content(data.reason),
        description=sanitize_content(data.description),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    await _award_xp(db, current_user, 2)
    await db.commit()

    return ReportResponse(
        id=report.id,
        reporter_id=report.reporter_id,
        report_type=report.report_type,
        thread_id=report.thread_id,
        post_id=report.post_id,
        reported_user_id=report.reported_user_id,
        reason=report.reason,
        description=report.description,
        status=report.status,
        created_at=report.created_at,
    )


# ============================================================================
# MODERATOR ENDPOINTS
# ============================================================================

def _thread_summary(t: Optional[Thread]) -> Optional[dict]:
    """ReportResponse.thread is a plain dict (not an ORM object)."""
    if not t:
        return None
    return {"id": t.id, "title": t.title, "slug": t.slug}


def _post_summary(p: Optional[Post]) -> Optional[dict]:
    """ReportResponse.post is a plain dict (not an ORM object)."""
    if not p:
        return None
    preview = (p.content or "")[:120]
    return {"id": p.id, "thread_id": p.thread_id, "content_preview": preview}

@router.get("/mod/reports", response_model=ReportListResponse)
async def get_reports(
    status: Optional[ReportStatus] = Query(None),
    report_type: Optional[ReportType] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator),
):
    """Get all reports (moderators only)"""
    query = select(Report)
    count_query = select(func.count(Report.id))
    
    if status:
        query = query.where(Report.status == status)
        count_query = count_query.where(Report.status == status)
    
    if report_type:
        query = query.where(Report.report_type == report_type)
        count_query = count_query.where(Report.report_type == report_type)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Get reports with relationships
    query = (
        query
        .options(
            selectinload(Report.reporter),
            selectinload(Report.reported_user),
            selectinload(Report.thread),
            selectinload(Report.post),
            selectinload(Report.resolved_by_user),
        )
        .order_by(Report.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    
    result = await db.execute(query)
    reports = result.scalars().all()
    
    return ReportListResponse(
        items=[
            ReportResponse(
                id=r.id,
                reporter_id=r.reporter_id,
                reporter=r.reporter,
                report_type=r.report_type,
                thread_id=r.thread_id,
                thread=_thread_summary(r.thread),
                post_id=r.post_id,
                post=_post_summary(r.post),
                reported_user_id=r.reported_user_id,
                reported_user=r.reported_user,
                reason=r.reason,
                description=r.description,
                status=r.status,
                resolved_by=r.resolved_by,
                resolved_by_user=r.resolved_by_user,
                mod_notes=r.mod_notes,
                created_at=r.created_at,
                resolved_at=r.resolved_at,
            )
            for r in reports
        ],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.put("/mod/reports/{report_id}/resolve", response_model=ReportResponse)
async def resolve_report(
    report_id: int,
    action: str = Query(..., description="Action taken: dismissed, warned, content_removed, user_banned"),
    mod_notes: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator),
):
    """Resolve a report"""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if report.status != ReportStatus.PENDING:
        raise HTTPException(status_code=400, detail="Report already resolved")
    
    # Map action to status
    if action == "dismissed":
        report.status = ReportStatus.DISMISSED
    else:
        report.status = ReportStatus.RESOLVED
    
    report.resolved_by = current_user.id
    report.resolved_at = datetime.utcnow()
    report.mod_notes = mod_notes
    
    # Create mod action log
    mod_action = ModAction(
        moderator_id=current_user.id,
        target_user_id=report.reported_user_id,
        action_type=action,
        reason=f"Report #{report_id}: {report.reason}",
        notes=mod_notes,
        thread_id=report.thread_id,
        post_id=report.post_id,
    )
    db.add(mod_action)
    
    # Notify reporter. Link to the reported thread when there is one — there is
    # no user-facing "my reports" page. create_notification also mirrors to
    # Telegram and pushes SSE.
    await create_notification(
        db, user_id=report.reporter_id, type="report_resolved",
        title="Report resolved",
        body="Your report has been reviewed by a moderator",
        link=f"/thread/{report.thread_id}" if report.thread_id else None,
    )
    
    # Execute the resolution action
    if action == "user_banned" and report.reported_user_id:
        target_user = await db.get(User, report.reported_user_id)
        if target_user:
            # Staff-protection rules live in apply_ban (shared with the admin
            # ban path).
            apply_ban(target=target_user, actor=current_user,
                      reason=f"Report resolution: {report.reason}")
    elif action == "content_removed":
        if report.report_type == ReportType.THREAD and report.thread_id:
            thread = await db.get(Thread, report.thread_id)
            if thread:
                thread.status = ThreadStatus.DELETED
        elif report.report_type == ReportType.POST and report.post_id:
            post = await db.get(Post, report.post_id)
            if post:
                post.is_deleted = True
                post.deleted_by_id = current_user.id
                post.deleted_at = datetime.utcnow()
    elif action == "warned" and report.reported_user_id:
        await create_notification(
            db, user_id=report.reported_user_id, type="warning",
            title="Warning received",
            body=f"You received a warning regarding a report. Reason: {report.reason}",
        )
    
    await db.commit()
    await db.refresh(report)

    return ReportResponse(
        id=report.id,
        reporter_id=report.reporter_id,
        report_type=report.report_type,
        thread_id=report.thread_id,
        post_id=report.post_id,
        reported_user_id=report.reported_user_id,
        reason=report.reason,
        description=report.description,
        status=report.status,
        resolved_by=report.resolved_by,
        mod_notes=report.mod_notes,
        created_at=report.created_at,
        resolved_at=report.resolved_at,
    )


# ============================================================================
# MOD ACTIONS
# ============================================================================

@router.get("/mod/actions")
async def get_mod_actions(
    user_id: Optional[int] = Query(None, description="Filter by target user"),
    moderator_id: Optional[int] = Query(None, description="Filter by moderator"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator),
):
    """Get moderation action log"""
    filters = []
    if user_id:
        filters.append(ModAction.target_user_id == user_id)
    if moderator_id:
        filters.append(ModAction.moderator_id == moderator_id)

    total = await db.scalar(
        select(func.count()).select_from(ModAction).where(*filters)
    )

    query = (
        select(ModAction)
        .options(
            selectinload(ModAction.moderator),
            selectinload(ModAction.target_user),
        )
        .where(*filters)
        .order_by(ModAction.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    result = await db.execute(query)
    actions = result.scalars().all()

    items = [
        ModActionResponse(
            id=a.id,
            moderator_id=a.moderator_id,
            moderator=a.moderator,
            target_user_id=a.target_user_id,
            target_user=a.target_user,
            action_type=a.action_type,
            reason=a.reason,
            notes=a.notes,
            thread_id=a.thread_id,
            post_id=a.post_id,
            expires_at=a.expires_at,
            created_at=a.created_at,
        )
        for a in actions
    ]
    return {"items": items, "total": total or 0, "page": page, "per_page": per_page}


@router.post("/mod/warn/{user_id}", response_model=SuccessResponse)
async def warn_user(
    user_id: int,
    reason: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator),
):
    """Warn a user"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role in [UserRole.MODERATOR, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Cannot warn moderators or admins")
    
    # Log action
    mod_action = ModAction(
        moderator_id=current_user.id,
        target_user_id=user_id,
        action_type="warning",
        reason=reason,
    )
    db.add(mod_action)
    
    # Notify user
    await create_notification(
        db, user_id=user_id, type="warning",
        title="Warning received",
        body=f"You have received a warning: {reason}",
    )
    
    await db.commit()
    
    return SuccessResponse(message="User warned")


@router.post("/mod/mute/{user_id}", response_model=SuccessResponse)
async def mute_user(
    user_id: int,
    reason: str = Query(...),
    duration_minutes: Optional[int] = Query(None, description="Mute duration in minutes (None = permanent)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator),
):
    """Mute a user (blocks posting, replies and live chat; reading and DMs still work)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    apply_mute(target=user, actor=current_user, reason=reason, duration_minutes=duration_minutes)

    # Log action
    mod_action = ModAction(
        moderator_id=current_user.id,
        target_user_id=user_id,
        action_type="mute",
        reason=reason,
        details=f"duration_minutes={duration_minutes}" if duration_minutes else "permanent",
    )
    db.add(mod_action)

    # Notify user
    await create_notification(
        db, user_id=user_id, type="muted",
        title="You have been muted",
        body=f"You have been muted: {reason}",
    )

    await db.commit()

    return SuccessResponse(message=f"User muted {'permanently' if not duration_minutes else f'for {duration_minutes} minutes'}")


@router.post("/mod/unmute/{user_id}", response_model=SuccessResponse)
async def unmute_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_moderator),
):
    """Unmute a user"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_muted:
        raise HTTPException(status_code=400, detail="User is not muted")

    clear_mute(user)

    # Log action
    mod_action = ModAction(
        moderator_id=current_user.id,
        target_user_id=user_id,
        action_type="unmute",
        reason="User unmuted",
    )
    db.add(mod_action)

    await db.commit()

    return SuccessResponse(message="User unmuted")


