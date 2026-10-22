"""Banners Router"""
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from app.database import get_db
from app.dependencies import limiter
from app.models import Banner, User
from app.schemas import BannerResponse, BannerCreate, BannerUpdate
from app.auth import get_current_admin

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
BANNERS_DIR = os.path.join(UPLOAD_DIR, "banners")


@router.get("", response_model=List[BannerResponse])
async def list_banners(
    position: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Banner).where(Banner.is_active == True)
    if position:
        query = query.where(Banner.position == position)
    query = query.order_by(Banner.sort_order.asc(), Banner.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/admin/all", response_model=List[BannerResponse])
async def list_all_banners(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all banners including inactive (admin only)"""
    result = await db.execute(
        select(Banner).order_by(Banner.sort_order.asc(), Banner.created_at.desc())
    )
    return result.scalars().all()


@router.post("/admin", response_model=BannerResponse)
async def create_banner(
    banner_data: BannerCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new banner (admin only)"""
    banner = Banner(**banner_data.model_dump())
    db.add(banner)
    await db.commit()
    await db.refresh(banner)
    return banner


@router.put("/admin/{banner_id}", response_model=BannerResponse)
async def update_banner(
    banner_id: int,
    banner_data: BannerUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a banner (admin only)"""
    result = await db.execute(select(Banner).where(Banner.id == banner_id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    
    update_data = banner_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(banner, field, value)
    
    await db.commit()
    await db.refresh(banner)
    return banner


@router.delete("/admin/{banner_id}")
async def delete_banner(
    banner_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a banner (admin only)"""
    result = await db.execute(select(Banner).where(Banner.id == banner_id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    
    # Delete associated image file if exists
    if banner.image_url and banner.image_url.startswith("/api/banners/images/"):
        filename = banner.image_url.split("/")[-1]
        filepath = os.path.join(BANNERS_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    
    await db.delete(banner)
    await db.commit()
    return {"message": "Banner deleted"}


@router.post("/admin/{banner_id}/upload")
@limiter.limit("20/minute")
async def upload_banner_image(
    request: Request,
    banner_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Upload a GIF/image for a banner (admin only)"""
    result = await db.execute(select(Banner).where(Banner.id == banner_id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    
    MAX_SIZE = 5 * 1024 * 1024  # 5MB for GIFs
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 5MB)")

    # Verify the real image type from magic bytes (not the client filename) so a
    # script-bearing SVG/HTML polyglot can't be stored and served same-origin.
    from app.images import validated_image_extension
    ext = validated_image_extension(content)
    if not ext:
        raise HTTPException(status_code=400, detail="Only valid GIF/PNG/JPG/WebP images allowed")

    # Create banners directory
    os.makedirs(BANNERS_DIR, exist_ok=True)
    
    filename = f"banner_{banner_id}.{ext}"
    filepath = os.path.join(BANNERS_DIR, filename)
    
    # Remove old banner images with different extension
    for old_ext in ("gif", "png", "jpg", "jpeg", "webp"):
        old_path = os.path.join(BANNERS_DIR, f"banner_{banner_id}.{old_ext}")
        if os.path.exists(old_path) and old_path != filepath:
            os.remove(old_path)
    
    with open(filepath, "wb") as f:
        f.write(content)
    
    banner.image_url = f"/api/banners/images/{filename}"
    await db.commit()
    await db.refresh(banner)
    
    return {"message": "Banner image uploaded", "image_url": banner.image_url}


@router.get("/images/{filename}")
async def serve_banner_image(filename: str):
    """Serve banner image/GIF file"""
    safe_name = os.path.basename(filename)
    filepath = os.path.join(BANNERS_DIR, safe_name)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(filepath)
