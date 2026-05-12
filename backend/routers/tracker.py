import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.db import Application, DocumentSnapshot
from backend.models.schemas import ApplicationListItem, TrackerResponse
from backend.services.docx_generator import generate_ats_resume_docx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tracker", tags=["tracker"])


@router.get("", response_model=TrackerResponse)
async def list_applications(
    profile_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> TrackerResponse:
    """Return a paginated list of applications, optionally filtered by profile and search term.

    Search matches against company and role fields (case-insensitive).
    Results are ordered newest-first.
    """
    query = select(Application)

    if profile_id is not None:
        query = query.where(Application.profile_id == profile_id)

    if search:
        term = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(Application.company).like(term),
                func.lower(Application.role).like(term),
            )
        )

    # Total count for pagination
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    # Paginated results, newest first
    query = query.order_by(Application.applied_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    apps = result.scalars().all()

    return TrackerResponse(
        total=total,
        applications=[ApplicationListItem.model_validate(a) for a in apps],
    )


@router.get("/{application_id}/resume")
async def get_resume_snapshot(
    application_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the resume JSON snapshot for an approved application."""
    app = await db.get(Application, application_id)
    if not app:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Application not found"},
        )

    snap = await db.get(DocumentSnapshot, app.resume_snapshot_id)
    if not snap or not snap.content_json:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Resume snapshot not found"},
        )

    return json.loads(snap.content_json)


@router.get("/{application_id}/cover-letter")
async def get_cover_letter_snapshot(
    application_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the cover letter text snapshot for an approved application."""
    app = await db.get(Application, application_id)
    if not app:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Application not found"},
        )

    snap = await db.get(DocumentSnapshot, app.cl_snapshot_id)
    if not snap or not snap.content_text:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Cover letter snapshot not found"},
        )

    return {"text": snap.content_text}


@router.get("/{application_id}/resume/download")
async def download_resume_docx(
    application_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Generate and stream an ATS-safe .docx resume for an approved application.

    The .docx is generated on demand from the stored resume JSON snapshot.
    No file is saved to disk.
    """
    app = await db.get(Application, application_id)
    if not app:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Application not found"},
        )

    snap = await db.get(DocumentSnapshot, app.resume_snapshot_id)
    if not snap or not snap.content_json:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Resume snapshot not found"},
        )

    resume_json = json.loads(snap.content_json)
    docx_bytes = generate_ats_resume_docx(resume_json)

    # Build a clean filename from company and role
    safe_company = "".join(c for c in app.company if c.isalnum() or c in " -_").strip().replace(" ", "_")
    safe_role = "".join(c for c in app.role if c.isalnum() or c in " -_").strip().replace(" ", "_")
    filename = f"Resume_{safe_role}_{safe_company}.docx"

    logger.info(
        "Streaming resume download: application_id=%d filename=%s size=%d bytes",
        application_id, filename, len(docx_bytes),
    )

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
