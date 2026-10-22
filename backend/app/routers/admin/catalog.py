"""Admin: badge catalog endpoints (split from admin.py).

The dead /banners duplicates that used to live here were removed — the live
banner admin routes are in app/routers/banners.py under /api/banners/admin/*.
Badge CRUD delegates to app.badge_service (shared with /api/badges admin routes).
"""
from app.routers.admin.common import *  # noqa: F401,F403
from app import badge_service

router = APIRouter()


@router.get("/badges", response_model=List[BadgeResponse])
async def list_badges(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all badges"""
    result = await db.execute(select(Badge).order_by(Badge.sort_order))
    return result.scalars().all()


@router.post("/badges", response_model=BadgeResponse)
async def create_badge(
    data: BadgeCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new badge"""
    return await badge_service.create_badge(db, data)


@router.delete("/badges/{badge_id}", response_model=SuccessResponse)
async def delete_badge(
    badge_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a badge (deactivates instead if already owned)"""
    return SuccessResponse(message=await badge_service.delete_badge(db, badge_id))
