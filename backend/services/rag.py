import logging

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db import CvChunk
from backend.services.embedder import embed_text

logger = logging.getLogger(__name__)


async def retrieve_relevant_chunks(
    job_description: str,
    profile_id: int,
    session: AsyncSession,
    top_k: int = 8,
) -> tuple[list[str], list[int]]:
    """Return the top-k most relevant CV chunks for a job description.

    Algorithm (section 7):
    1. Embed the full job description with all-MiniLM-L6-v2 (normalised).
    2. Fetch every cv_chunk row for this profile.
    3. Compute dot product between JD embedding and each chunk embedding.
       Because both vectors are L2-normalised, dot product == cosine similarity.
    4. Sort descending, return top_k (texts, ids).

    Returns:
        (chunk_texts, chunk_ids) — parallel lists of length <= top_k.
    """
    if not job_description.strip():
        logger.warning("retrieve_relevant_chunks: empty job description")
        return [], []

    # Step 1: embed JD
    jd_embedding: np.ndarray = embed_text(job_description)

    # Step 2: fetch all chunks for this profile
    result = await session.execute(
        select(CvChunk).where(CvChunk.profile_id == profile_id)
    )
    chunks = result.scalars().all()

    if not chunks:
        logger.warning(
            "retrieve_relevant_chunks: no cv_chunks for profile %d", profile_id
        )
        return [], []

    # Step 3: cosine similarity via dot product
    scored: list[tuple[float, int, str]] = []
    for chunk in chunks:
        chunk_emb = np.frombuffer(chunk.embedding, dtype=np.float32)
        score = float(np.dot(jd_embedding, chunk_emb))
        scored.append((score, chunk.id, chunk.chunk_text))

    # Step 4: sort descending, take top_k
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    chunk_texts = [text for _, _, text in top]
    chunk_ids = [cid for _, cid, _ in top]

    logger.info(
        "RAG: retrieved %d/%d chunks for profile %d (top score=%.3f)",
        len(top), len(chunks), profile_id, scored[0][0] if scored else 0.0,
    )
    return chunk_texts, chunk_ids
