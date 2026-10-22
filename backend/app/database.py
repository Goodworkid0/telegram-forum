"""Database configuration"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import select
import os
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL only at runtime. e.g. postgresql+asyncpg://user:pass@localhost:5432/forum
# (SQLite is permitted solely for the non-production test suite — see tests/conftest.py.)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Expected a PostgreSQL DSN, e.g. "
        "postgresql+asyncpg://user:pass@localhost:5432/forum"
    )

_is_postgres = DATABASE_URL.startswith("postgresql")
if not _is_postgres:
    # Allow SQLite, but only outside production (the in-memory test database).
    from app.config import IS_PRODUCTION
    if not (DATABASE_URL.startswith("sqlite") and not IS_PRODUCTION):
        raise RuntimeError(
            f"DATABASE_URL must be a PostgreSQL DSN (got scheme "
            f"'{DATABASE_URL.split(':', 1)[0]}'). This app supports PostgreSQL only "
            f"(SQLite is allowed only for non-production tests)."
        )

engine_kwargs: dict = {
    "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
}
if _is_postgres:
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "10"))

engine = create_async_engine(DATABASE_URL, **engine_kwargs)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass



async def get_referral_settings(db):
    """Get referral settings from AppSettings (shared helper)"""
    from app.models import AppSettings
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    settings = result.scalar_one_or_none()
    if not settings:
        return {
            "level1_percent": 3.0, "level2_percent": 5.0,
        }
    return {
        "enabled": settings.referral_enabled if settings.referral_enabled is not None else True,
        "level1_percent": settings.referral_level1_percent if settings.referral_level1_percent is not None else 3.0,
        "level2_percent": settings.referral_level2_percent if settings.referral_level2_percent is not None else 5.0,
    }


async def create_tables():
    from app.config import IS_PRODUCTION
    allow_auto_create = os.getenv("ALLOW_AUTO_CREATE_TABLES", "false").lower() == "true"

    if IS_PRODUCTION and not allow_auto_create:
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
