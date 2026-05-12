import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.db import Application, Job, JobHash, ParseLog
from backend.models.schemas import (
    JobDetail,
    JobListItem,
    JobPasteRequest,
    JobPasteResponse,
)
from backend.services.parser import (
    clean_jd_text,
    compute_hash,
    extract_jd_with_claude,
    validate_jd_text,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _job_id_from_extracted(title: str, company: str, location: str | None) -> str:
    """Compute the canonical job id: sha256 of normalised title+company+location."""
    key = (
        (title or "").lower().strip()
        + (company or "").lower().strip()
        + (location or "").lower().strip()
    )
    return compute_hash(key.encode())


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/paste", response_model=JobPasteResponse, status_code=201)
async def paste_job(
    body: JobPasteRequest,
    db: AsyncSession = Depends(get_db),
) -> JobPasteResponse:
    """Accept a raw job description, extract structured fields via Ollama, and persist.

    Flow:
    1. Validate length (200–50 000 chars).
    2. Clean text (ftfy + whitespace normalisation).
    3. Check job_hashes for an exact-text duplicate — 409 if found.
    4. Call Ollama to extract structured JD fields.
    5. Compute job_id from normalised title+company+location.
    6. Check jobs table for a semantic duplicate — 409 if found (also records hash).
    7. Check applications table for already-applied flag.
    8. Persist job, job_hash, parse_log.
    9. Return 201 with full structured response.
    """
    # ── Step 1: length validation ─────────────────────────────────────────────
    ok, error_code = validate_jd_text(body.text)
    if not ok:
        messages = {
            "too_short": "Job description is too short (minimum 200 characters).",
            "too_long": "Job description is too long (maximum 50 000 characters).",
        }
        raise HTTPException(
            status_code=422,
            detail={"error": error_code, "message": messages.get(error_code, error_code)},
        )

    # ── Step 2: clean text ────────────────────────────────────────────────────
    clean_text = clean_jd_text(body.text)

    # ── Step 3: exact-text duplicate check (before Ollama call) ──────────────
    text_hash = compute_hash(clean_text.encode())
    existing_hash_row = await db.get(JobHash, text_hash)
    if existing_hash_row:
        logger.info("Exact duplicate JD paste detected (hash=%s)", text_hash[:12])
        raise HTTPException(
            status_code=409,
            detail={"error": "duplicate", "job_id": existing_hash_row.job_id},
        )

    # ── Step 4: Ollama JD extraction ──────────────────────────────────────────
    t0 = time.monotonic()
    try:
        extracted = await extract_jd_with_claude(clean_text)
    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.error("JD extraction failed: %s", exc)
        # Record the failed attempt in parse_log (no job_id yet)
        db.add(ParseLog(
            job_id=None,
            raw_length_chars=len(body.text),
            clean_length_chars=len(clean_text),
            extraction_ok=False,
            extraction_duration_ms=duration_ms,
            was_duplicate=False,
        ))
        await db.commit()
        raise HTTPException(
            status_code=500,
            detail={"error": "extraction_failed", "message": str(exc)},
        )
    duration_ms = int((time.monotonic() - t0) * 1000)

    # ── Step 5: compute job_id from normalised identity fields ────────────────
    title = (extracted.get("title") or "").strip()
    company = (extracted.get("company") or "").strip()
    location = extracted.get("location")
    job_id = _job_id_from_extracted(title, company, location)

    # ── Step 6: semantic duplicate check ─────────────────────────────────────
    existing_job = await db.get(Job, job_id)
    if existing_job:
        logger.info("Semantic duplicate detected for job_id=%s (%s @ %s)", job_id[:12], title, company)
        # Record the new text hash so future identical pastes are caught earlier
        db.add(JobHash(hash=text_hash, job_id=job_id))
        db.add(ParseLog(
            job_id=job_id,
            raw_length_chars=len(body.text),
            clean_length_chars=len(clean_text),
            extraction_ok=True,
            extraction_duration_ms=duration_ms,
            was_duplicate=True,
        ))
        await db.commit()
        raise HTTPException(
            status_code=409,
            detail={"error": "duplicate", "job_id": job_id},
        )

    # ── Step 7: already-applied check ─────────────────────────────────────────
    app_result = await db.execute(
        select(Application).where(
            Application.job_id == job_id,
            Application.profile_id == body.profile_id,
        )
    )
    already_applied = app_result.scalar_one_or_none() is not None

    # ── Step 8: persist job + hash + parse_log ────────────────────────────────
    skills_required = extracted.get("skills_required") or []
    skills_preferred = extracted.get("skills_preferred") or []
    ats_keywords = extracted.get("ats_keywords") or []

    job = Job(
        id=job_id,
        raw_text=body.text,
        title=title,
        company=company,
        location=location,
        remote_type=extracted.get("remote_type"),
        salary_min=extracted.get("salary_min"),
        salary_max=extracted.get("salary_max"),
        salary_currency=extracted.get("salary_currency"),
        description_clean=clean_text,
        skills_required=json.dumps(skills_required),
        skills_preferred=json.dumps(skills_preferred),
        ats_keywords=json.dumps(ats_keywords),
        seniority=extracted.get("seniority"),
        posted_date=extracted.get("posted_date"),
        extraction_ok=True,
        extraction_error=None,
    )
    db.add(job)
    db.add(JobHash(hash=text_hash, job_id=job_id))
    db.add(ParseLog(
        job_id=job_id,
        raw_length_chars=len(body.text),
        clean_length_chars=len(clean_text),
        extraction_ok=True,
        extraction_duration_ms=duration_ms,
        was_duplicate=False,
    ))
    await db.commit()

    logger.info(
        "Job saved: %s @ %s (job_id=%s, %dms)",
        title, company, job_id[:12], duration_ms,
    )

    # ── Step 9: return structured response ────────────────────────────────────
    return JobPasteResponse(
        job_id=job_id,
        title=title,
        company=company,
        location=location,
        remote_type=extracted.get("remote_type"),
        seniority=extracted.get("seniority"),
        salary_min=extracted.get("salary_min"),
        salary_max=extracted.get("salary_max"),
        salary_currency=extracted.get("salary_currency"),
        skills_required=skills_required,
        skills_preferred=skills_preferred,
        ats_keywords=ats_keywords,
        description_summary=extracted.get("description_summary") or "",
        already_applied=already_applied,
        duplicate_of=None,
    )


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> JobDetail:
    """Return full detail for a single job by its id."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Job not found"},
        )
    return JobDetail.model_validate(job)


@router.get("", response_model=list[JobListItem])
async def list_jobs(
    db: AsyncSession = Depends(get_db),
) -> list[JobListItem]:
    """Return the 50 most recently fetched jobs, newest first."""
    result = await db.execute(
        select(Job).order_by(Job.fetched_at.desc()).limit(50)
    )
    return result.scalars().all()
