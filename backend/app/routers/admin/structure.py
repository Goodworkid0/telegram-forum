"""Admin: structure endpoints (split from admin.py)."""
from app.routers.admin.common import *  # noqa: F401,F403

router = APIRouter()


@router.get("/tabs", response_model=List[ForumTabResponse])
async def list_tabs(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all forum tabs"""
    result = await db.execute(
        select(ForumTab)
        .options(selectinload(ForumTab.sections).selectinload(ForumSection.boards).selectinload(ForumBoard.last_thread).options(selectinload(Thread.author), selectinload(Thread.last_post_by)))
        .order_by(ForumTab.sort_order)
    )
    return result.scalars().all()



@router.post("/tabs", response_model=ForumTabResponse)
async def create_tab(
    data: ForumTabCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new forum tab"""
    existing = await db.scalar(select(ForumTab).where(ForumTab.slug == data.slug))
    if existing:
        raise HTTPException(status_code=400, detail=f"Tab with slug '{data.slug}' already exists")
    
    tab = ForumTab(**data.model_dump())
    db.add(tab)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Tab with this name or slug already exists")
    await db.refresh(tab)
    result = await db.execute(
        select(ForumTab).where(ForumTab.id == tab.id)
        .options(selectinload(ForumTab.sections).selectinload(ForumSection.boards).selectinload(ForumBoard.last_thread).options(selectinload(Thread.author), selectinload(Thread.last_post_by)))
    )
    return result.scalar_one()



class ReorderPayload(BaseModel):
    item_ids: List[int]



@router.put("/tabs/reorder", response_model=SuccessResponse)
async def reorder_tabs(
    data: ReorderPayload,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    for i, tab_id in enumerate(data.item_ids):
        tab = await db.get(ForumTab, tab_id)
        if tab:
            tab.sort_order = i
    await db.commit()
    return SuccessResponse(message="Tabs reordered")



@router.put("/tabs/{tab_id}", response_model=ForumTabResponse)
async def update_tab(
    tab_id: int,
    data: ForumTabUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a forum tab"""
    result = await db.execute(select(ForumTab).where(ForumTab.id == tab_id))
    tab = result.scalar_one_or_none()
    if not tab:
        raise HTTPException(status_code=404, detail="Tab not found")
    
    if data.slug and data.slug != tab.slug:
        existing = await db.scalar(select(ForumTab).where(ForumTab.slug == data.slug))
        if existing:
            raise HTTPException(status_code=400, detail=f"Tab with slug '{data.slug}' already exists")
    
    for key, val in data.model_dump(exclude_unset=True).items():
        if key == 'min_role' and val:
            val = UserRole(val.upper())
        setattr(tab, key, val)
    
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Tab with this name or slug already exists")
    await db.refresh(tab)
    return tab



@router.delete("/tabs/{tab_id}", response_model=SuccessResponse)
async def delete_tab(
    tab_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a forum tab (sections will become unassigned)"""
    result = await db.execute(select(ForumTab).where(ForumTab.id == tab_id))
    tab = result.scalar_one_or_none()
    if not tab:
        raise HTTPException(status_code=404, detail="Tab not found")
    
    # Unassign sections from this tab
    await db.execute(
        text("UPDATE forum_sections SET tab_id = NULL WHERE tab_id = :tab_id"),
        {"tab_id": tab_id}
    )
    
    await db.delete(tab)
    await db.commit()
    return SuccessResponse(message="Tab deleted")



@router.get("/sections", response_model=List[ForumSectionResponse])
async def list_sections(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all forum sections"""
    result = await db.execute(
        select(ForumSection).options(selectinload(ForumSection.boards).selectinload(ForumBoard.last_thread).options(selectinload(Thread.author), selectinload(Thread.last_post_by))).order_by(ForumSection.sort_order)
    )
    return result.scalars().all()



@router.post("/sections", response_model=ForumSectionResponse)
async def create_section(
    data: ForumSectionCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new forum section"""
    # Check if slug already exists
    existing = await db.scalar(select(ForumSection).where(ForumSection.slug == data.slug))
    if existing:
        raise HTTPException(status_code=400, detail=f"Section with slug '{data.slug}' already exists")
    
    section = ForumSection(**data.model_dump())
    db.add(section)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Section with this slug already exists")
    await db.refresh(section)

    # Eager load boards for response serialization
    result = await db.execute(
        select(ForumSection).where(ForumSection.id == section.id).options(selectinload(ForumSection.boards).selectinload(ForumBoard.last_thread).options(selectinload(Thread.author), selectinload(Thread.last_post_by)))
    )
    return result.scalar_one()



@router.put("/sections/reorder", response_model=SuccessResponse)
async def reorder_sections(
    data: ReorderPayload,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    for i, section_id in enumerate(data.item_ids):
        section = await db.get(ForumSection, section_id)
        if section:
            section.sort_order = i
    await db.commit()
    return SuccessResponse(message="Sections reordered")



@router.put("/sections/{section_id}", response_model=ForumSectionResponse)
async def update_section(
    section_id: int,
    data: ForumSectionUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a forum section"""
    result = await db.execute(select(ForumSection).where(ForumSection.id == section_id))
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    # Check slug uniqueness if updating slug
    if data.slug and data.slug != section.slug:
        existing = await db.scalar(select(ForumSection).where(ForumSection.slug == data.slug))
        if existing:
            raise HTTPException(status_code=400, detail=f"Section with slug '{data.slug}' already exists")
    
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(section, key, val)
    
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Section with this slug already exists")
    await db.refresh(section)
    result = await db.execute(
        select(ForumSection).where(ForumSection.id == section.id).options(selectinload(ForumSection.boards).selectinload(ForumBoard.last_thread).options(selectinload(Thread.author), selectinload(Thread.last_post_by)))
    )
    return result.scalar_one()



@router.delete("/sections/{section_id}", response_model=SuccessResponse)
async def delete_section(
    section_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a forum section (must have no boards)"""
    result = await db.execute(select(ForumSection).where(ForumSection.id == section_id))
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    board_count = await db.scalar(select(func.count()).select_from(ForumBoard).where(ForumBoard.section_id == section_id))
    if board_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete section with boards")
    
    await db.delete(section)
    await db.commit()
    return SuccessResponse(message="Section deleted")



@router.get("/boards", response_model=List[ForumBoardResponse])
async def list_boards(
    section_id: Optional[int] = None,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all forum boards"""
    q = select(ForumBoard).options(
        selectinload(ForumBoard.last_thread)
            .selectinload(Thread.author),
        selectinload(ForumBoard.last_thread)
            .selectinload(Thread.last_post_by),
    ).order_by(ForumBoard.section_id, ForumBoard.sort_order)
    if section_id:
        q = q.where(ForumBoard.section_id == section_id)
    result = await db.execute(q)
    return result.scalars().all()



@router.post("/boards", response_model=ForumBoardResponse)
async def create_board(
    data: ForumBoardCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new forum board"""
    section = await db.get(ForumSection, data.section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    if data.parent_id:
        parent = await db.get(ForumBoard, data.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent board not found")
        if parent.section_id != data.section_id:
            raise HTTPException(status_code=400, detail="Parent board must be in the same section")
    
    existing = await db.scalar(select(ForumBoard).where(ForumBoard.slug == data.slug))
    if existing:
        raise HTTPException(status_code=400, detail=f"Board with slug '{data.slug}' already exists")
    
    board = ForumBoard(**data.model_dump())
    db.add(board)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Board with this slug already exists")
    await db.refresh(board)
    return board



@router.put("/boards/reorder", response_model=SuccessResponse)
async def reorder_boards(
    data: ReorderPayload,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    for i, board_id in enumerate(data.item_ids):
        board = await db.get(ForumBoard, board_id)
        if board:
            board.sort_order = i
    await db.commit()
    return SuccessResponse(message="Boards reordered")



@router.put("/boards/{board_id}", response_model=ForumBoardResponse)
async def update_board(
    board_id: int,
    data: ForumBoardUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a forum board"""
    result = await db.execute(
        select(ForumBoard).where(ForumBoard.id == board_id).options(selectinload(ForumBoard.last_thread).options(selectinload(Thread.author), selectinload(Thread.last_post_by)))
    )
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    if data.slug and data.slug != board.slug:
        existing = await db.scalar(select(ForumBoard).where(ForumBoard.slug == data.slug))
        if existing:
            raise HTTPException(status_code=400, detail=f"Board with slug '{data.slug}' already exists")
    
    if data.parent_id is not None and data.parent_id != board.parent_id:
        if data.parent_id == board.id:
            raise HTTPException(status_code=400, detail="A board cannot be its own parent")
        parent = await db.get(ForumBoard, data.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent board not found")
        if parent.section_id != board.section_id:
            raise HTTPException(status_code=400, detail="Parent board must be in the same section")
    
    update_data = data.model_dump(exclude_unset=True)
    
    for key, val in update_data.items():
        setattr(board, key, val)
    
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Board with this slug already exists")
    await db.refresh(board)
    return board



@router.delete("/boards/{board_id}", response_model=SuccessResponse)
async def delete_board(
    board_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a forum board (must have no threads)"""
    result = await db.execute(select(ForumBoard).where(ForumBoard.id == board_id).options(selectinload(ForumBoard.last_thread).options(selectinload(Thread.author), selectinload(Thread.last_post_by))))
    board = result.scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    thread_count = await db.scalar(select(func.count()).select_from(Thread).where(Thread.board_id == board_id))
    if thread_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete board with threads")
    
    await db.delete(board)
    await db.commit()
    return SuccessResponse(message="Board deleted")

