import asyncio
import json
import logging
import threading
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import get_db
from backend.models.db import Profile, ProfilePreferences, Setting
from backend.models.schemas import (
    ActivateProfileResponse,
    PreferencesResponse,
    PreferencesUpdate,
    ProfileCreateResponse,
    ProfileDetail,
    ProfileListItem,
    ProfilePatch,
    ProfileStatusResponse,
)
from backend.services.embedder import chunk_cv, embed_chunks
from backend.services.parser import (
    clean_cv_text,
    compute_hash,
    extract_cv_with_claude,
    extract_text_from_pdf,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profiles", tags=["profiles"])


# ── Shared engine factory for daemon threads ──────────────────────────────────

def _make_session_factory():
    """Create a fresh async engine + session factory for use in a daemon thread.

    Each background thread needs its own engine to avoid sharing the server's
    connection pool across event loops (Starlette 1.0 / anyio limitation).
    """
    engine = create_async_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


# ── Background tasks ──────────────────────────────────────────────────────────

async def _parse_and_embed_background(profile_id: int, raw_text: str) -> None:
    """Parse CV with Ollama then embed chunks — runs in a daemon thread.

    Step 1: Call Ollama to extract structured JSON from CV text.
    Step 2: Chunk the parsed JSON by semantic section.
    Step 3: Embed chunks with all-MiniLM-L6-v2 and persist to cv_chunks.
    """
    Session, engine = _make_session_factory()

    async with Session() as session:
        profile = await session.get(Profile, profile_id)
        if not profile:
            logger.error("Background task: profile %d not found", profile_id)
            await engine.dispose()
            return

        # ── Step 1: Ollama parse ──────────────────────────────────────────────
        profile.parse_attempts += 1
        try:
            parsed = await extract_cv_with_claude(raw_text)
            profile.cv_parsed_json = json.dumps(parsed)
            profile.last_parse_error = None
            logger.info("CV parsed for profile %d", profile_id)
        except Exception as exc:
            logger.error("CV parse failed for profile %d: %s", profile_id, exc)
            profile.last_parse_error = str(exc)
            await session.commit()
            await engine.dispose()
            return

        await session.commit()

        # ── Step 2 + 3: Chunk + embed ─────────────────────────────────────────
        try:
            chunks = chunk_cv(profile.cv_parsed_json)
            n = await embed_chunks(profile_id, chunks, session)
            logger.info("Embedded %d chunks for profile %d", n, profile_id)
        except Exception as exc:
            # Embedding failure is non-fatal — parse result is already saved
            logger.error("Embedding failed for profile %d: %s", profile_id, exc)

    await engine.dispose()


async def _reembed_background(profile_id: int) -> None:
    """Re-chunk and re-embed an already-parsed profile — runs in a daemon thread."""
    Session, engine = _make_session_factory()

    async with Session() as session:
        profile = await session.get(Profile, profile_id)
        if not profile or profile.is_deleted:
            logger.error("Reembed: profile %d not found", profile_id)
            await engine.dispose()
            return

        if profile.cv_parsed_json in ("{}", ""):
            logger.warning("Reembed: profile %d has no parsed JSON yet", profile_id)
            await engine.dispose()
            return

        try:
            chunks = chunk_cv(profile.cv_parsed_json)
            n = await embed_chunks(profile_id, chunks, session)
            logger.info("Reembedded %d chunks for profile %d", n, profile_id)
        except Exception as exc:
            logger.error("Reembed failed for profile %d: %s", profile_id, exc)

    await engine.dispose()


def _run_in_thread(coro) -> None:
    """Launch an async coroutine in a daemon thread with its own event loop."""
    threading.Thread(
        target=lambda: asyncio.run(coro),
        daemon=True,
    ).start()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_active_profile(profile_id: int, db: AsyncSession, *, load_prefs: bool = False) -> Profile:
    """Fetch a non-deleted profile by id, raising 404 if missing.

    Set load_prefs=True to eagerly load the preferences relationship.
    """
    stmt = select(Profile).where(Profile.id == profile_id, Profile.is_deleted == False)
    if load_prefs:
        stmt = stmt.options(selectinload(Profile.preferences))
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Profile not found"},
        )
    return profile


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=ProfileCreateResponse, status_code=201)
async def create_profile(
    name: str = Form(...),
    cv_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ProfileCreateResponse:
    """Accept a CV PDF upload, create a profile row, and queue background parsing + embedding."""
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
    await db.commit()

    _run_in_thread(_parse_and_embed_background(profile_id, clean_text))

    return ProfileCreateResponse(id=profile_id, name=name, status="parsing")


@router.get("", response_model=list[ProfileListItem])
async def list_profiles(
    db: AsyncSession = Depends(get_db),
) -> list[ProfileListItem]:
    """Return all non-deleted profiles, newest first."""
    result = await db.execute(
        select(Profile)
        .where(Profile.is_deleted == False)
        .order_by(Profile.created_at.desc())
    )
    return result.scalars().all()


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


@router.get("/{profile_id}", response_model=ProfileDetail)
async def get_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProfileDetail:
    """Return full profile detail including parsed JSON and preferences (if set)."""
    profile = await _get_active_profile(profile_id, db, load_prefs=True)
    return ProfileDetail.model_validate(profile)


@router.patch("/{profile_id}", response_model=ProfileDetail)
async def patch_profile(
    profile_id: int,
    body: ProfilePatch,
    db: AsyncSession = Depends(get_db),
) -> ProfileDetail:
    """Update a profile's name. Returns the updated profile."""
    profile = await _get_active_profile(profile_id, db, load_prefs=True)
    profile.name = body.name
    profile.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(profile, ["preferences"])
    return ProfileDetail.model_validate(profile)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a profile by setting is_deleted=True. Returns 204 No Content."""
    profile = await _get_active_profile(profile_id, db)
    profile.is_deleted = True
    profile.updated_at = datetime.utcnow()
    # If this profile was active, clear the active_profile_id setting
    if profile.is_active:
        profile.is_active = False
        await db.execute(
            sql_update(Setting)
            .where(Setting.key == "active_profile_id")
            .values(value="")
        )
    await db.commit()


@router.post("/{profile_id}/activate", response_model=ActivateProfileResponse)
async def activate_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
) -> ActivateProfileResponse:
    """Set this profile as active. Deactivates all other profiles atomically."""
    profile = await _get_active_profile(profile_id, db)

    # Deactivate every profile, then activate just this one
    await db.execute(sql_update(Profile).values(is_active=False))
    profile.is_active = True

    # Sync the settings table so GET /settings reflects the change
    await db.execute(
        sql_update(Setting)
        .where(Setting.key == "active_profile_id")
        .values(value=str(profile_id))
    )

    await db.commit()
    return ActivateProfileResponse(active_profile_id=profile_id)


@router.get("/{profile_id}/preferences", response_model=PreferencesResponse)
async def get_preferences(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
) -> PreferencesResponse:
    """Return preferences for a profile. Creates default preferences if none exist yet."""
    await _get_active_profile(profile_id, db)  # ensures profile exists

    result = await db.execute(
        select(ProfilePreferences).where(ProfilePreferences.profile_id == profile_id)
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        # Lazily create default preferences on first access
        prefs = ProfilePreferences(profile_id=profile_id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)

    return PreferencesResponse.model_validate(prefs)


@router.put("/{profile_id}/preferences", response_model=PreferencesResponse)
async def update_preferences(
    profile_id: int,
    body: PreferencesUpdate,
    db: AsyncSession = Depends(get_db),
) -> PreferencesResponse:
    """Create or replace preferences for a profile. All fields are required (full PUT semantics)."""
    await _get_active_profile(profile_id, db)  # ensures profile exists

    result = await db.execute(
        select(ProfilePreferences).where(ProfilePreferences.profile_id == profile_id)
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        prefs = ProfilePreferences(profile_id=profile_id)
        db.add(prefs)

    # Serialise list fields to JSON strings for storage; scalars map directly
    prefs.target_roles = json.dumps(body.target_roles)
    prefs.target_locations = json.dumps(body.target_locations)
    prefs.remote_preference = body.remote_preference
    prefs.salary_min_eur = body.salary_min_eur
    prefs.company_size_pref = body.company_size_pref
    prefs.industries_to_avoid = json.dumps(body.industries_to_avoid)
    prefs.skills_to_grow = json.dumps(body.skills_to_grow)
    prefs.tone_preference = body.tone_preference
    prefs.cover_letter_length = body.cover_letter_length
    prefs.seniority_target = body.seniority_target
    prefs.notice_period_weeks = body.notice_period_weeks
    prefs.open_to_contract = body.open_to_contract
    prefs.extra_context = body.extra_context
    prefs.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(prefs)
    return PreferencesResponse.model_validate(prefs)


@router.post("/{profile_id}/reembed", status_code=202)
async def reembed_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Re-chunk and re-embed an already-parsed CV. Returns 202 immediately."""
    profile = await db.get(Profile, profile_id)
    if not profile or profile.is_deleted:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Profile not found"},
        )

    if profile.cv_parsed_json in ("{}", ""):
        raise HTTPException(
            status_code=409,
            detail={"error": "not_parsed", "message": "Profile CV has not been parsed yet"},
        )

    _run_in_thread(_reembed_background(profile_id))
    return {"message": "re-embedding started"}
