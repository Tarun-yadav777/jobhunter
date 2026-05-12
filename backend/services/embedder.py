import json
import logging
import time

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import CvChunk, EmbeddingRun

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ── Load model once at module level ───────────────────────────────────────────
# Takes ~2s on first import; cached for all subsequent calls.
_model: SentenceTransformer = SentenceTransformer(EMBEDDING_MODEL)
logger.info("Embedding model '%s' loaded", EMBEDDING_MODEL)


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_cv(cv_parsed_json: str) -> list[dict[str, str]]:
    """Split parsed CV JSON into semantic chunks for embedding.

    Returns a list of {"type": str, "text": str} dicts.
    Chunk types: summary | experience | skills | education
    Target: 10-30 chunks per CV per CLAUDE.md section 7.
    """
    try:
        cv = json.loads(cv_parsed_json)
    except (json.JSONDecodeError, TypeError):
        logger.warning("chunk_cv: invalid JSON, returning empty chunk list")
        return []

    if not cv or cv == {}:
        return []

    chunks: list[dict[str, str]] = []

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = (cv.get("summary") or "").strip()
    if summary:
        chunks.append({"type": "summary", "text": f"Professional Summary:\n{summary}"})

    # ── One chunk per experience entry ────────────────────────────────────────
    for exp in cv.get("experiences") or []:
        title = exp.get("title", "")
        company = exp.get("company", "")
        start = exp.get("start_date", "")
        end = exp.get("end_date", "")
        description = (exp.get("description") or "").strip()
        skills_used = exp.get("skills_used") or []

        lines: list[str] = []
        if title or company:
            lines.append(f"{title} at {company} ({start} – {end})")
        if description:
            lines.append(description)
        if skills_used:
            lines.append(f"Skills used: {', '.join(skills_used)}")

        text = "\n".join(lines).strip()
        if text:
            chunks.append({"type": "experience", "text": text})

    # ── Skills section (all in one chunk) ─────────────────────────────────────
    skills = cv.get("skills") or {}
    skill_lines: list[str] = []
    technical = skills.get("technical") or []
    tools = skills.get("tools") or []
    soft = skills.get("soft") or []
    if technical:
        skill_lines.append(f"Technical skills: {', '.join(technical)}")
    if tools:
        skill_lines.append(f"Tools & platforms: {', '.join(tools)}")
    if soft:
        skill_lines.append(f"Soft skills: {', '.join(soft)}")
    if skill_lines:
        chunks.append({"type": "skills", "text": "\n".join(skill_lines)})

    # ── Education + certifications + languages (one chunk) ────────────────────
    edu_lines: list[str] = []
    for edu in cv.get("education") or []:
        degree = edu.get("degree", "")
        institution = edu.get("institution", "")
        year = edu.get("year") or ""
        parts = [p for p in [degree, institution, year] if p]
        if parts:
            edu_lines.append(", ".join(parts))

    certifications = cv.get("certifications") or []
    if certifications:
        edu_lines.append(f"Certifications: {', '.join(certifications)}")

    languages = cv.get("languages") or []
    if languages:
        edu_lines.append(f"Languages: {', '.join(languages)}")

    if edu_lines:
        chunks.append({"type": "education", "text": "\n".join(edu_lines)})

    logger.info("chunk_cv produced %d chunks", len(chunks))
    return chunks


# ── Embedding ─────────────────────────────────────────────────────────────────

async def embed_chunks(
    profile_id: int,
    chunks: list[dict[str, str]],
    session: AsyncSession,
) -> int:
    """Embed all chunks and persist to cv_chunks table.

    Deletes any existing chunks for profile_id first, then inserts fresh ones.
    Writes an EmbeddingRun record. Returns the number of chunks created.

    Embedding is CPU-bound; it runs directly (caller is already off the main
    event loop in a daemon thread).
    """
    if not chunks:
        logger.warning("embed_chunks: no chunks to embed for profile %d", profile_id)
        return 0

    # Delete old chunks for this profile before inserting new ones
    await session.execute(delete(CvChunk).where(CvChunk.profile_id == profile_id))

    t0 = time.monotonic()

    texts = [c["text"] for c in chunks]
    # normalize_embeddings=True → dot product equals cosine similarity (RAG section 7)
    embeddings = _model.encode(texts, normalize_embeddings=True)

    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        session.add(CvChunk(
            profile_id=profile_id,
            chunk_index=idx,
            chunk_type=chunk["type"],
            chunk_text=chunk["text"],
            embedding=embedding.astype(np.float32).tobytes(),
        ))

    duration_ms = int((time.monotonic() - t0) * 1000)

    session.add(EmbeddingRun(
        profile_id=profile_id,
        chunks_created=len(chunks),
        model_used=EMBEDDING_MODEL,
        duration_ms=duration_ms,
    ))

    await session.commit()
    logger.info(
        "Embedded %d chunks for profile %d in %dms",
        len(chunks), profile_id, duration_ms,
    )
    return len(chunks)
