"""Admin: settings endpoints (split from admin.py)."""
from app.routers.admin.common import *  # noqa: F401,F403

router = APIRouter()


class AppSettingsSchema(BaseModel):
    # Branding
    app_name: Optional[str] = None
    logo_url: Optional[str] = None
    show_logo: Optional[bool] = None
    bot_username: Optional[str] = None
    maintenance_mode: Optional[bool] = None

    # Links
    announcements_url: Optional[str] = None
    official_group_url: Optional[str] = None

    # Forum settings
    trial_mode_enabled: Optional[bool] = None
    min_posts_for_dm: Optional[int] = None
    min_posts_for_rep: Optional[int] = None
    max_posts_per_hour: Optional[int] = None
    max_threads_per_day: Optional[int] = None
    max_pm_per_minute: Optional[int] = None

    # Shop prices
    premium_price: Optional[float] = None
    name_change_price: Optional[float] = None
    thread_title_price: Optional[float] = None
    thread_autobump_price: Optional[float] = None

    # Payments — curated deposit coins (CSV of NOWPayments tickers)
    enabled_deposit_coins: Optional[str] = None

    # Fees
    withdrawal_fee_percent: Optional[float] = None
    escrow_fee_percent: Optional[float] = None
    max_active_escrow_deals: Optional[int] = None

    # Referral
    referral_enabled: Optional[bool] = None
    referral_level1_percent: Optional[float] = None
    referral_level2_percent: Optional[float] = None

    # Leaderboard
    leaderboard_rewards: Optional[str] = None

    # Support
    support_username: Optional[str] = None
    support_display_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)



@router.get("/settings", response_model=AppSettingsSchema)
async def get_settings(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get app settings"""
    result = await db.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = AppSettings()
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    
    return settings



@router.get("/payment-coins")
async def get_payment_coins(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List every coin available on the NOWPayments account, flagged with whether
    it's currently enabled for deposits. Used by the admin coin-toggle UI.

    ``fallback`` is true when the live account list couldn't be fetched (no API
    key / upstream error) and the legacy default set is shown instead.
    """
    from app.nowpayments import fetch_available_coins, coin_display, resolve_enabled, DEFAULT_COINS

    available = await fetch_available_coins()
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    settings = result.scalar_one_or_none()
    curated_csv = settings.enabled_deposit_coins if settings else None

    enabled = set(resolve_enabled(curated_csv, available))
    coins = available if available is not None else list(DEFAULT_COINS)
    return {
        "fallback": available is None,
        "coins": [
            {**coin_display(c), "enabled": c in enabled}
            for c in sorted(coins)
        ],
    }


@router.put("/settings", response_model=AppSettingsSchema)
async def update_settings(
    data: AppSettingsSchema,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update app settings"""
    result = await db.execute(select(AppSettings).limit(1))
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = AppSettings()
        db.add(settings)
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    
    await db.commit()
    await db.refresh(settings)
    return settings

