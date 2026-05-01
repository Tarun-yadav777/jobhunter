import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models.schemas import HealthResponse, SettingsPatch, SettingsResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Return app health, DB connectivity, and version."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)
        db_status = "error"

    return HealthResponse(
        status="ok",
        db=db_status,
        version=settings.app_version,
    )


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db)) -> SettingsResponse:
    """Return current app settings (active profile, version)."""
    rows = await db.execute(text("SELECT key, value FROM settings"))
    data = {row.key: row.value for row in rows}

    active_raw = data.get("active_profile_id", "")
    active_id = int(active_raw) if active_raw and active_raw.isdigit() else None

    return SettingsResponse(
        active_profile_id=active_id,
        app_version=data.get("app_version", settings.app_version),
    )


@router.patch("/settings", response_model=SettingsResponse)
async def patch_settings(
    body: SettingsPatch,
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """Update active_profile_id in settings table."""
    await db.execute(
        text("UPDATE settings SET value = :val WHERE key = 'active_profile_id'"),
        {"val": str(body.active_profile_id)},
    )
    await db.commit()

    return SettingsResponse(
        active_profile_id=body.active_profile_id,
        app_version=settings.app_version,
    )
