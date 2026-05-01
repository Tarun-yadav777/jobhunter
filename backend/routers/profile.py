import asyncio
import json
import logging
import threading

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import AsyncSessionLocal, get_db
from backend.models.db import Profile
from backend.models.schemas import ProfileCreateResponse, ProfileStatusResponse
from backend.services.parser import (
    clean_cv_text,
    compute_hash,
    extract_cv_with_claude,
    extract_text_from_pdf,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profiles", tags=["profiles"])


# ── Background task ───────────────────────────────────────────────────────────

async def _parse_cv_background(profile_id: int, raw_text: str) -> None:
    """Background task: call Ollama to parse CV, update profile row.

    Runs in a daemon thread with its own event loop, so creates a fresh
    SQLAlchemy engine to avoid sharing the server's connection pool.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from backend.config import settings as _settings

    _engine = create_async_engine(
        _settings.database_url,
        connect_args={"check_same_thread": False},
    )
    _Session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    async with _Session() as session:
        profile = await session.get(Profile, profile_id)
        if not profile:
            logger.error("Background parse: profile %d not found", profile_id)
            await _engine.dispose()
            return

        profile.parse_attempts += 1
        try:
            parsed = await extract_cv_with_claude(raw_text)
            profile.cv_parsed_json = json.dumps(parsed)
            profile.last_parse_error = None
            logger.info("CV parsed successfully for profile %d", profile_id)
        except Exception as exc:
            logger.error("CV parse failed for profile %d: %s", profile_id, exc)
            profile.last_parse_error = str(exc)

        await session.commit()
    await _engine.dispose()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=ProfileCreateResponse, status_code=201)
async def create_profile(
    name: str = Form(...),
    cv_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ProfileCreateResponse:
    """Accept a CV PDF upload, create a profile row, and queue background parsing."""
    file_bytes = await cv_file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=422,
            detail={"error": "empty_file", "message": "Uploaded file is empty"},
        )

    try:
        raw_text = extract_text_from_pdf(file_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "pdf_parse_failed", "message": str(exc)},
        )

    if not raw_text.strip():
        raise HTTPException(
            status_code=422,
            detail={"error": "pdf_no_text", "message": "Could not extract text from PDF"},
        )

    clean_text = clean_cv_text(raw_text)
    file_hash = compute_hash(file_bytes)

    profile = Profile(
        name=name,
        cv_raw_text=clean_text,
        cv_parsed_json="{}",
        cv_filename=cv_file.filename or "cv.pdf",
        cv_hash=file_hash,
        parse_attempts=0,
    )
    db.add(profile)
    await db.flush()
    profile_id = profile.id
    await db.commit()  # commit before background task so the row is visible

    # Run in a daemon thread with its own event loop — escapes anyio's request-scoped task group
    threading.Thread(
        target=lambda: asyncio.run(_parse_cv_background(profile_id, clean_text)),
        daemon=True,
    ).start()

    return ProfileCreateResponse(id=profile_id, name=name, status="parsing")


@router.get("/{profile_id}/status", response_model=ProfileStatusResponse)
async def get_profile_status(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProfileStatusResponse:
    """Return parse status for a profile: parsing | ready | failed."""
    profile = await db.get(Profile, profile_id)
    if not profile or profile.is_deleted:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Profile not found"},
        )

    if profile.last_parse_error:
        parse_status = "failed"
    elif profile.cv_parsed_json == "{}":
        parse_status = "parsing"
    else:
        parse_status = "ready"

    return ProfileStatusResponse(id=profile_id, status=parse_status)
