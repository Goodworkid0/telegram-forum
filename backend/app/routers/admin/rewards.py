"""Admin: rewards endpoints (split from admin.py)."""
from app.routers.admin.common import *  # noqa: F401,F403

router = APIRouter()


@router.get("/daily-rewards/config", response_model=List[DailyRewardConfigResponse])
async def list_daily_reward_configs(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(DailyRewardConfig).order_by(DailyRewardConfig.day)
    )
    configs = result.scalars().all()
    output = []
    for c in configs:
        badge_name = None
        if c.badge_id:
            badge_result = await db.execute(select(Badge).where(Badge.id == c.badge_id))
            badge = badge_result.scalar_one_or_none()
            if badge:
                badge_name = badge.name
        output.append(DailyRewardConfigResponse(
            id=c.id,
            day=c.day,
            xp_amount=c.xp_amount,
            balance_amount=c.balance_amount,
            badge_id=c.badge_id,
            badge_name=badge_name,
            is_active=c.is_active,
            created_at=c.created_at,
            updated_at=c.updated_at,
        ))
    return output



@router.post("/daily-rewards/config", response_model=DailyRewardConfigResponse)
async def create_daily_reward_config(
    data: DailyRewardConfigCreate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    existing = await db.execute(
        select(DailyRewardConfig).where(DailyRewardConfig.day == data.day)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Config for day {data.day} already exists")

    config = DailyRewardConfig(**data.model_dump())
    db.add(config)
    await db.commit()
    await db.refresh(config)

    badge_name = None
    if config.badge_id:
        badge_result = await db.execute(select(Badge).where(Badge.id == config.badge_id))
        badge = badge_result.scalar_one_or_none()
        if badge:
            badge_name = badge.name

    return DailyRewardConfigResponse(
        id=config.id,
        day=config.day,
        xp_amount=config.xp_amount,
        balance_amount=config.balance_amount,
        badge_id=config.badge_id,
        badge_name=badge_name,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )



@router.put("/daily-rewards/config/{day}", response_model=DailyRewardConfigResponse)
async def update_daily_reward_config(
    day: int,
    data: DailyRewardConfigUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(DailyRewardConfig).where(DailyRewardConfig.day == day)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail=f"Config for day {day} not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "badge_id" and value is not None:
            badge_check = await db.execute(select(Badge).where(Badge.id == value))
            if not badge_check.scalar_one_or_none():
                raise HTTPException(status_code=404, detail=f"Badge with id {value} not found")
        setattr(config, key, value)

    await db.commit()
    await db.refresh(config)

    badge_name = None
    if config.badge_id:
        badge_result = await db.execute(select(Badge).where(Badge.id == config.badge_id))
        badge = badge_result.scalar_one_or_none()
        if badge:
            badge_name = badge.name

    return DailyRewardConfigResponse(
        id=config.id,
        day=config.day,
        xp_amount=config.xp_amount,
        balance_amount=config.balance_amount,
        badge_id=config.badge_id,
        badge_name=badge_name,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )



@router.delete("/daily-rewards/config/{day}", response_model=SuccessResponse)
async def delete_daily_reward_config(
    day: int,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(DailyRewardConfig).where(DailyRewardConfig.day == day)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail=f"Config for day {day} not found")

    await db.delete(config)
    await db.commit()
    return SuccessResponse(message=f"Daily reward config for day {day} deleted")




