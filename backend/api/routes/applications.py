from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db
from backend.api.schemas import (
    ApplicationListItem,
    ApplicationStatusResponse,
    ApplicationTriggerRequest,
    ApplicationTriggerResponse,
)
from backend.db.models import ApplicationRun, ApplicationStatus, JobRecord

log = structlog.get_logger()
router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("/trigger", response_model=ApplicationTriggerResponse, status_code=201)
async def trigger_application(
    body: ApplicationTriggerRequest,
    db: AsyncSession = Depends(get_db),
) -> ApplicationTriggerResponse:
    """
    Creates an ApplicationRun record and queues the Celery task.
    Returns run_id immediately — poll GET /applications/{run_id} for status.
    """
    job = JobRecord(
        id=uuid.uuid4(),
        user_id=body.user_id,
        url=body.job_url,
    )
    db.add(job)

    run = ApplicationRun(
        id=uuid.uuid4(),
        job_record_id=job.id,
        user_id=body.user_id,
        status=ApplicationStatus.queued,
        steps=[],
    )
    db.add(run)
    await db.commit()

    run_id = str(run.id)

    try:
        from backend.workers.tasks import run_application
        run_application.delay(run_id, body.job_url, {})
        log.info("application_queued", run_id=run_id, url=body.job_url)
    except Exception as exc:
        log.warning("celery_unavailable", error=str(exc))
        # Update status to reflect queue failure so caller knows
        run.status = ApplicationStatus.failed
        await db.commit()
        return ApplicationTriggerResponse(
            run_id=run_id,
            status=ApplicationStatus.failed.value,
            message="Application created but task queue unavailable. Start Redis/Celery to process.",
        )

    return ApplicationTriggerResponse(
        run_id=run_id,
        status=ApplicationStatus.queued.value,
        message="Application queued. Poll GET /applications/{run_id} for status.",
    )


@router.get("", response_model=list[ApplicationListItem])
async def list_applications(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationListItem]:
    result = await db.execute(
        select(ApplicationRun, JobRecord)
        .join(JobRecord, ApplicationRun.job_record_id == JobRecord.id)
        .where(ApplicationRun.user_id == user_id)
        .order_by(ApplicationRun.created_at.desc())
    )
    rows = result.all()
    return [
        ApplicationListItem(
            id=str(run.id),
            status=run.status.value,
            job_url=job.url,
            job_title=job.title,
            company=job.company,
            fit_score=job.fit_score,
            created_at=run.created_at.isoformat(),
        )
        for run, job in rows
    ]


@router.get("/{run_id}", response_model=ApplicationStatusResponse)
async def get_application(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApplicationStatusResponse:
    result = await db.execute(
        select(ApplicationRun).where(ApplicationRun.id == uuid.UUID(run_id))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Application run not found")

    return ApplicationStatusResponse(
        id=str(run.id),
        status=run.status.value,
        job_record_id=str(run.job_record_id) if run.job_record_id else None,
        steps=run.steps or [],
        cover_letter=run.cover_letter,
        bullets=run.bullets or [],
        created_at=run.created_at.isoformat(),
        submitted_at=run.submitted_at.isoformat() if run.submitted_at else None,
    )


@router.post("/{run_id}/submit", response_model=ApplicationStatusResponse)
async def submit_application(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApplicationStatusResponse:
    """
    Review gate — moves status from `review` → `submitted`.
    Will not submit if status is not `review` (enforces human approval).
    """
    result = await db.execute(
        select(ApplicationRun).where(ApplicationRun.id == uuid.UUID(run_id))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Application run not found")

    if run.status != ApplicationStatus.review:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot submit: status is '{run.status.value}', expected 'review'.",
        )

    run.status = ApplicationStatus.submitted
    run.submitted_at = datetime.utcnow()
    await db.commit()
    await db.refresh(run)

    log.info("application_submitted", run_id=run_id, user_id=run.user_id)

    return ApplicationStatusResponse(
        id=str(run.id),
        status=run.status.value,
        job_record_id=str(run.job_record_id) if run.job_record_id else None,
        steps=run.steps or [],
        cover_letter=run.cover_letter,
        bullets=run.bullets or [],
        created_at=run.created_at.isoformat(),
        submitted_at=run.submitted_at.isoformat() if run.submitted_at else None,
    )
