"""Admin: content endpoints (split from admin.py)."""
from app.routers.admin.common import *  # noqa: F401,F403

router = APIRouter()


class AdminContentItem(PydanticBaseModel):
    type: str
    id: int
    title: str
    content_preview: str
    author: Optional[str] = None
    author_id: Optional[int] = None
    board_name: Optional[str] = None
    is_deleted: bool = False
    created_at: Optional[datetime] = None



class AdminContentResponse(PydanticBaseModel):
    items: List[AdminContentItem]
    total: int



@router.get("/content", response_model=AdminContentResponse)
async def admin_content_search(
    q: str = Query("", max_length=200),
    content_type: str = Query("all", pattern="^(all|threads|posts)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin content search across threads and posts.

    Uses Postgres full-text search (ranked relevance match) on the indexed
    search_vector columns when available, ILIKE otherwise. An empty query browses
    all content (newest first). Results are ordered by recency so pagination
    across the two sources stays consistent — ideal for moderation triage."""
    q_clean = (q or "").strip()
    has_q = bool(q_clean)
    if has_q:
        if IS_POSTGRES:
            thread_filter = fts_match("threads", q_clean)
            post_filter = fts_match("posts", q_clean)
        else:
            _pat = f"%{q_clean}%"
            thread_filter = Thread.title.ilike(_pat) | Thread.content.ilike(_pat)
            post_filter = Post.content.ilike(_pat)
    thread_conds = [thread_filter] if has_q else []
    post_conds = [post_filter] if has_q else []

    offset = (page - 1) * per_page
    items = []
    total = 0

    # When merging two sources we can't apply the page offset per-source, or rows
    # get dropped/duplicated across the merge boundary. Instead pull the global
    # top-(offset+per_page) from each source, merge-sort, then slice the window.
    combined = content_type == "all"
    src_offset = 0 if combined else offset
    src_limit = (offset + per_page) if combined else per_page

    if content_type in ("all", "threads"):
        from sqlalchemy.orm import selectinload
        tq = (
            select(Thread)
            .where(*thread_conds)
            .options(selectinload(Thread.author), selectinload(Thread.board))
            .order_by(desc(Thread.created_at))
            .offset(src_offset).limit(src_limit)
        )
        tcq = select(func.count()).select_from(Thread).where(*thread_conds)
        tres = await db.execute(tq)
        tcount = await db.scalar(tcq)
        total += tcount or 0
        
        for t in tres.scalars().all():
            items.append(AdminContentItem(
                type="thread", id=t.id, title=t.title,
                content_preview=(t.content or "")[:150],
                author=t.author.username if t.author else None,
                author_id=t.author_id,
                board_name=t.board.name if t.board else None,
                is_deleted=t.status == ThreadStatus.DELETED,
                created_at=t.created_at
            ))
    
    if content_type in ("all", "posts"):
        pq = (
            select(Post)
            .where(*post_conds)
            .options(selectinload(Post.author), selectinload(Post.thread).selectinload(Thread.board))
            .order_by(desc(Post.created_at))
            .offset(src_offset).limit(src_limit)
        )
        pcq = select(func.count()).select_from(Post).where(*post_conds)
        pres = await db.execute(pq)
        pcount = await db.scalar(pcq)
        total += pcount or 0
        
        for p in pres.scalars().all():
            items.append(AdminContentItem(
                type="post", id=p.id,
                title=p.thread.title if p.thread else f"Post #{p.id}",
                content_preview=(p.content or "")[:150],
                author=p.author.username if p.author else None,
                author_id=p.author_id,
                board_name=p.thread.board.name if p.thread and p.thread.board else None,
                is_deleted=p.is_deleted,
                created_at=p.created_at
            ))
    
    items.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
    if combined:
        items = items[offset:offset + per_page]
    else:
        items = items[:per_page]

    return AdminContentResponse(items=items, total=total)



@router.delete("/content/{type}/{item_id}", response_model=SuccessResponse)
async def admin_delete_content(
    type: str,
    item_id: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin delete a thread or post"""
    if type == "thread":
        thread = await db.scalar(select(Thread).where(Thread.id == item_id))
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        thread.status = ThreadStatus.DELETED
        await db.commit()
        mod_action = ModAction(
            moderator_id=current_user.id,
            target_user_id=thread.author_id,
            action_type="thread_delete",
            reason=f"Thread #{item_id} deleted by admin",
        )
        db.add(mod_action)
        await db.commit()
        return SuccessResponse(message="Thread deleted")
    elif type == "post":
        post = await db.scalar(select(Post).where(Post.id == item_id))
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        post.is_deleted = True
        await db.commit()
        mod_action = ModAction(
            moderator_id=current_user.id,
            target_user_id=post.author_id,
            action_type="post_delete",
            reason=f"Post #{item_id} deleted by admin",
        )
        db.add(mod_action)
        await db.commit()
        return SuccessResponse(message="Post deleted")
    else:
        raise HTTPException(status_code=400, detail="Invalid type. Use 'thread' or 'post'")



@router.post("/reset-database", response_model=SuccessResponse)
async def reset_database(
    confirm: bool = Query(False, description="Must be True to confirm"),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reset the entire database (DEVELOPMENT ONLY)"""
    if IS_PRODUCTION:
        raise HTTPException(status_code=403, detail="Cannot reset database in production")
    
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=True to proceed")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    return SuccessResponse(message="Database reset complete")

