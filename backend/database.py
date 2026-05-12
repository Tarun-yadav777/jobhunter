import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """Dependency that provides a database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> bool:
    """Create all tables and load sqlite-vec extension. Returns True if vec loaded."""
    from backend.models.db import Base as ModelBase  # noqa: F401 — triggers model registration

    async with engine.begin() as conn:
        await conn.run_sync(ModelBase.metadata.create_all)

    await _migrate_generation_status()
    vec_ok = await _init_sqlite_vec()
    await _seed_settings()
    return vec_ok


async def _migrate_generation_status() -> None:
    """Add gen_status / current_step / error_message to generation_results if missing.

    SQLite does not support IF NOT EXISTS on ALTER TABLE ADD COLUMN before 3.35,
    so we attempt each column and swallow the 'duplicate column' error.
    """
    from sqlalchemy import text

    columns = [
        ("gen_status",     "TEXT NOT NULL DEFAULT 'running'"),
        ("current_step",   "TEXT"),
        ("error_message",  "TEXT"),
    ]
    async with AsyncSessionLocal() as session:
        for col_name, col_def in columns:
            try:
                await session.execute(
                    text(f"ALTER TABLE generation_results ADD COLUMN {col_name} {col_def}")
                )
                await session.commit()
                logger.info("Migrated: added generation_results.%s", col_name)
            except Exception:
                await session.rollback()  # column already exists — safe to ignore


async def _init_sqlite_vec() -> bool:
    """Attempt to load the sqlite-vec extension. Logs warning and continues on failure."""
    try:
        import sqlite_vec  # noqa: F401

        async with AsyncSessionLocal() as session:
            raw = await session.connection()
            await raw.run_sync(lambda conn: conn.enable_load_extension(True))
            await raw.run_sync(
                lambda conn: conn.execute("SELECT load_extension(?)", (sqlite_vec.loadable_path(),))
            )
            await raw.run_sync(lambda conn: conn.enable_load_extension(False))
        logger.info("sqlite-vec extension loaded successfully")
        return True
    except Exception as exc:
        logger.warning("sqlite-vec failed to load — vector operations unavailable: %s", exc)
        return False


async def _seed_settings() -> None:
    """Insert default settings rows if they do not already exist."""
    from sqlalchemy import text

    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "INSERT OR IGNORE INTO settings (key, value) VALUES "
                "('active_profile_id', ''), ('app_version', '0.1.0')"
            )
        )
        await session.commit()
