import asyncio
import json
import logging
import threading
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings
from backend.database import get_db
from backend.models.db import (
    GenerationLog,
    GenerationResult,
    Job,
    Profile,
    ProfilePreferences,
)
from backend.models.schemas import (
    GenerateRequest,
    GenerateStartResponse,
    GenerationStatusResponse,
)
from backend.services.generator import (
    calculate_ats_score,
    run_cover_letter,
    run_gap_analysis,
    run_resume_tailoring,
)
from backend.services.rag import retrieve_relevant_chunks

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/generate", tags=["generate"])


# ── Engine factory (same daemon-thread pattern as profile.py) ─────────────────

def _make_session_factory():
    """Create a fresh async engine + session factory for use in a daemon thread."""
    engine = create_async_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


def _run_in_thread(coro) -> None:
    """Launch an async coroutine in a daemon thread with its own event loop."""
    threading.Thread(target=lambda: asyncio.run(coro), daemon=True).start()


# ── Background generation pipeline ───────────────────────────────────────────

async def _generation_background(generation_id: int) -> None:
    """Run the full 4-step generation pipeline in a daemon thread.

    Steps:
        1. RAG          — embed JD, retrieve top-8 CV chunks
        2. Gap analysis — Ollama structured JSON
        3. Resume + Cover letter — concurrent Ollama calls via asyncio.gather
        4. ATS scoring  — pure Python
    Updates gen_status / current_step live. Sets gen_status='ready' on success
    or 'failed' on any error.
    """
    Session, engine = _make_session_factory()
    t_start = time.monotonic()

    async with Session() as session:
        gen = await session.get(GenerationResult, generation_id)
        if not gen:
            logger.error("Generation %d not found in background task", generation_id)
            await engine.dispose()
            return

        job = await session.get(Job, gen.job_id)
        profile = await session.get(Profile, gen.profile_id)

        if not job or not profile:
            gen.gen_status = "failed"
            gen.error_message = "Job or profile not found"
            gen.total_duration_ms = 0
            await session.commit()
            await engine.dispose()
            return

        # Load preferences (use defaults if none set)
        prefs_result = await session.execute(
            select(ProfilePreferences).where(ProfilePreferences.profile_id == gen.profile_id)
        )
        prefs = prefs_result.scalar_one_or_none()

        # skills_required / skills_preferred / ats_keywords stay as JSON strings —
        # generator.py calls json.loads() on them internally.
        job_dict: dict = {
            "title": job.title,
            "company": job.company,
            "location": job.location or "",
            "seniority": job.seniority or "unknown",
            "skills_required": job.skills_required,
            "skills_preferred": job.skills_preferred,
            "description_clean": job.description_clean,
            "ats_keywords": job.ats_keywords,
        }

        prefs_dict: dict = {
            "target_roles": prefs.target_roles if prefs else "[]",
            "skills_to_grow": prefs.skills_to_grow if prefs else "[]",
            "tone_preference": prefs.tone_preference if prefs else "professional",
            "extra_context": prefs.extra_context if prefs else None,
            "seniority_target": prefs.seniority_target if prefs else "senior",
            "cover_letter_length": prefs.cover_letter_length if prefs else "medium",
        }

        try:
            # ── Step 1: RAG retrieval ─────────────────────────────────────────
            gen.current_step = "rag"
            await session.commit()

            t_rag = time.monotonic()
            chunk_texts, chunk_ids = await retrieve_relevant_chunks(
                job.description_clean, gen.profile_id, session
            )
            rag_ms = int((time.monotonic() - t_rag) * 1000)
            logger.info(
                "Generation %d — RAG: %d chunks in %dms", generation_id, len(chunk_texts), rag_ms
            )

            # ── Step 2: Gap analysis ──────────────────────────────────────────
            gen.current_step = "gap_analysis"
            await session.commit()

            t_gap = time.monotonic()
            gap_result = await run_gap_analysis(chunk_texts, job_dict, prefs_dict)
            gap_ms = int((time.monotonic() - t_gap) * 1000)

            gen.gap_analysis_json = json.dumps(gap_result)
            gen.chunks_used = json.dumps(chunk_ids)
            await session.commit()
            logger.info(
                "Generation %d — gap analysis: score=%s in %dms",
                generation_id, gap_result.get("match_score"), gap_ms,
            )

            # ── Step 3+4: Resume + Cover letter (concurrent) ──────────────────
            gen.current_step = "resume"
            await session.commit()

            t_resume = time.monotonic()
            resume_result, cover_letter_result = await asyncio.gather(
                run_resume_tailoring(
                    gap_result, chunk_texts, profile.cv_parsed_json, job_dict, prefs_dict
                ),
                run_cover_letter(gap_result, chunk_texts, job_dict, prefs_dict),
            )
            resume_ms = int((time.monotonic() - t_resume) * 1000)
            logger.info("Generation %d — resume+CL: %dms", generation_id, resume_ms)

            # ── Step 5: ATS scoring (pure Python) ─────────────────────────────
            ats_keywords = json.loads(job.ats_keywords)
            ats = calculate_ats_score(resume_result, ats_keywords)

            total_ms = int((time.monotonic() - t_start) * 1000)

            gen.resume_json = json.dumps(resume_result)
            gen.cover_letter_text = cover_letter_result
            gen.ats_score = ats["score"]
            gen.ats_matched = json.dumps(ats["matched"])
            gen.ats_missing = json.dumps(ats["missing"])
            gen.total_duration_ms = total_ms
            gen.gen_status = "ready"
            gen.current_step = None
            gen.error_message = None

            session.add(GenerationLog(
                generation_id=generation_id,
                profile_id=gen.profile_id,
                job_id=gen.job_id,
                match_score=gap_result.get("match_score"),
                hard_gap_count=len(gap_result.get("hard_gaps", [])),
                chunks_retrieved=len(chunk_ids),
                rag_duration_ms=rag_ms,
                gap_analysis_ms=gap_ms,
                resume_duration_ms=resume_ms,
                cover_letter_ms=resume_ms,  # ran concurrently — same wall time
                total_duration_ms=total_ms,
            ))

            await session.commit()
            logger.info(
                "Generation %d complete in %dms (ATS %d%%)",
                generation_id, total_ms, ats["score"],
            )

        except Exception as exc:
            logger.error(
                "Generation %d failed at step '%s': %s",
                generation_id, gen.current_step, exc, exc_info=True,
            )
            try:
                gen.gen_status = "failed"
                gen.error_message = str(exc)
                gen.total_duration_ms = int((time.monotonic() - t_start) * 1000)
                await session.commit()
            except Exception as commit_exc:
                logger.error(
                    "Could not persist failure for generation %d: %s", generation_id, commit_exc
                )

    await engine.dispose()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=GenerateStartResponse, status_code=202)
async def start_generation(
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateStartResponse:
    """Start async generation for a job+profile pair.

    Validates job and profile exist, creates a generation_results placeholder row,
    fires the 4-step pipeline in a daemon thread, and returns 202 immediately.
    """
    # Validate job exists
    job = await db.get(Job, body.job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Job not found"},
        )

    # Validate profile is parsed
    profile = await db.get(Profile, body.profile_id)
    if not profile or profile.is_deleted:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Profile not found"},
        )
    if profile.cv_parsed_json in ("{}", ""):
        raise HTTPException(
            status_code=409,
            detail={"error": "not_ready", "message": "Profile CV has not been parsed yet"},
        )

    # Guard against duplicate in-flight generation for same job+profile
    running_check = await db.execute(
        select(GenerationResult.id)
        .where(
            GenerationResult.job_id == body.job_id,
            GenerationResult.profile_id == body.profile_id,
            GenerationResult.gen_status == "running",
        )
        .limit(1)
    )
    if running_check.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail={"error": "already_running", "message": "Generation already in progress for this job+profile"},
        )

    # Create placeholder row; background task updates it in-place
    gen = GenerationResult(
        job_id=body.job_id,
        profile_id=body.profile_id,
        gap_analysis_json="{}",
        resume_json="{}",
        cover_letter_text="",
        chunks_used="[]",
        ats_matched="[]",
        ats_missing="[]",
        total_duration_ms=0,
        gen_status="running",
        current_step="rag",
    )
    db.add(gen)
    await db.flush()
    generation_id = gen.id
    await db.commit()

    _run_in_thread(_generation_background(generation_id))

    logger.info(
        "Generation %d started for job=%s profile=%d",
        generation_id, body.job_id[:12], body.profile_id,
    )
    return GenerateStartResponse(generation_id=generation_id, status="running")


@router.get("/{generation_id}/status", response_model=GenerationStatusResponse)
async def get_generation_status(
    generation_id: int,
    db: AsyncSession = Depends(get_db),
) -> GenerationStatusResponse:
    """Return live status of a generation: running | ready | failed, plus active step."""
    gen = await db.get(GenerationResult, generation_id)
    if not gen:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Generation not found"},
        )
    return GenerationStatusResponse(
        generation_id=generation_id,
        status=gen.gen_status,
        step=gen.current_step,
        error=gen.error_message,
    )
