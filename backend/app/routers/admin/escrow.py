"""Admin: escrow endpoints (split from admin.py)."""
from app.routers.admin.common import *  # noqa: F401,F403

router = APIRouter()


class EscrowDealAdminItem(BaseModel):
    id: int
    buyer_id: int
    seller_id: int
    buyer_username: Optional[str] = None
    seller_username: Optional[str] = None
    title: str
    amount: float
    fee_amount: float = 0.0
    status: str
    hold_ends_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)



class EscrowStats(BaseModel):
    total_deals: int = 0
    active_deals: int = 0
    disputed_deals: int = 0
    completed_deals: int = 0
    total_volume: float = 0.0          # sum of amount across all deals
    completed_volume: float = 0.0      # sum of amount on COMPLETED deals
    fees_earned: float = 0.0           # realized platform revenue (COMPLETED deals)
    fees_pending: float = 0.0          # fees on funds still in escrow (not yet earned)



class EscrowAdminListResponse(BaseModel):
    items: List[EscrowDealAdminItem]
    total: int
    page: int
    per_page: int
    pages: int
    stats: EscrowStats



_ESCROW_PENDING_FEE_STATUSES = [
    EscrowStatus.FUNDED, EscrowStatus.DELIVERED, EscrowStatus.DISPUTED,
]



_ESCROW_ACTIVE_STATUSES = [
    EscrowStatus.PENDING, EscrowStatus.ACCEPTED, EscrowStatus.FUNDED,
    EscrowStatus.DELIVERED, EscrowStatus.DISPUTED,
]



@router.get("/escrow/deals", response_model=EscrowAdminListResponse)
async def list_escrow_deals(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db),
):
    """All escrow deals (admin view) plus platform earnings stats."""
    filters = []
    if status:
        try:
            filters.append(EscrowDeal.status == EscrowStatus(status))
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    count_q = select(func.count(EscrowDeal.id))
    if filters:
        count_q = count_q.where(*filters)
    total = await db.scalar(count_q) or 0
    pages = max(1, (total + per_page - 1) // per_page)

    q = (
        select(EscrowDeal)
        .options(selectinload(EscrowDeal.buyer), selectinload(EscrowDeal.seller))
        .order_by(desc(EscrowDeal.updated_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    if filters:
        q = q.where(*filters)
    deals = (await db.execute(q)).scalars().all()

    items = [
        EscrowDealAdminItem(
            id=d.id, buyer_id=d.buyer_id, seller_id=d.seller_id,
            buyer_username=d.buyer.username if d.buyer else None,
            seller_username=d.seller.username if d.seller else None,
            title=d.title, amount=d.amount, fee_amount=d.fee_amount or 0.0,
            status=d.status.value if isinstance(d.status, EscrowStatus) else str(d.status),
            hold_ends_at=d.hold_ends_at, created_at=d.created_at,
            updated_at=d.updated_at, completed_at=d.completed_at,
        )
        for d in deals
    ]

    # Platform-wide stats (computed across ALL deals, ignoring the page filter).
    stats = EscrowStats(
        total_deals=await db.scalar(select(func.count(EscrowDeal.id))) or 0,
        active_deals=await db.scalar(
            select(func.count(EscrowDeal.id)).where(EscrowDeal.status.in_(_ESCROW_ACTIVE_STATUSES))
        ) or 0,
        disputed_deals=await db.scalar(
            select(func.count(EscrowDeal.id)).where(EscrowDeal.status == EscrowStatus.DISPUTED)
        ) or 0,
        completed_deals=await db.scalar(
            select(func.count(EscrowDeal.id)).where(EscrowDeal.status == EscrowStatus.COMPLETED)
        ) or 0,
        total_volume=float(await db.scalar(select(func.coalesce(func.sum(EscrowDeal.amount), 0))) or 0),
        completed_volume=float(await db.scalar(
            select(func.coalesce(func.sum(EscrowDeal.amount), 0)).where(EscrowDeal.status == EscrowStatus.COMPLETED)
        ) or 0),
        fees_earned=float(await db.scalar(
            select(func.coalesce(func.sum(EscrowDeal.fee_amount), 0)).where(EscrowDeal.status == EscrowStatus.COMPLETED)
        ) or 0),
        fees_pending=float(await db.scalar(
            select(func.coalesce(func.sum(EscrowDeal.fee_amount), 0)).where(EscrowDeal.status.in_(_ESCROW_PENDING_FEE_STATUSES))
        ) or 0),
    )

    return EscrowAdminListResponse(
        items=items, total=total, page=page, per_page=per_page, pages=pages, stats=stats,
    )

