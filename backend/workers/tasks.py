from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict

import structlog
from celery import Celery

from backend.config import settings

log = structlog.get_logger()

celery_app = Celery("autoapply", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"backend.workers.tasks.*": {"queue": "applications"}}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_application(self, run_id: str, job_url: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    from backend.agents.exceptions import FitThresholdError

    try:
        return asyncio.run(_execute(run_id, job_url))
    except FitThresholdError as exc:
        # Not retryable — expected outcome when fit score is too low.
        log.info("fit_threshold_not_met", run_id=run_id, error=str(exc))
        return {"status": "failed", "reason": "fit_threshold_not_met"}
    except Exception as exc:
        log.error("task_failed", run_id=run_id, retries=self.request.retries, error=str(exc))
        if self.request.retries >= self.max_retries:
            asyncio.run(_mark_failed(run_id, str(exc)))
        raise self.retry(exc=exc)


async def _execute(run_id: str, job_url: str) -> Dict[str, Any]:
    import anthropic
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from backend.agents.exceptions import FitThresholdError
    from backend.agents.orchestrator import Orchestrator
    from backend.db.models import ApplicationRun, ApplicationStatus, JobRecord, UserProfile
    from backend.services.browser import BrowserService
    from backend.services.storage import StorageService

    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(ApplicationRun).where(ApplicationRun.id == uuid.UUID(run_id))
            )
            run = result.scalar_one()

            # Load associated profile (first match for user)
            profile_result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == run.user_id).limit(1)
            )
            profile_record = profile_result.scalar_one_or_none()
            profile_dict = _profile_to_dict(profile_record) if profile_record else {}

            run.status = ApplicationStatus.running
            await db.commit()

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        storage = StorageService()
        browser = BrowserService()
        orchestrator = Orchestrator(client, storage, browser)

        try:
            result_data = await orchestrator.run(job_url, profile_dict, run_id)
        except FitThresholdError:
            async with SessionLocal() as db:
                result = await db.execute(
                    select(ApplicationRun).where(ApplicationRun.id == uuid.UUID(run_id))
                )
                run = result.scalar_one()
                run.status = ApplicationStatus.failed
                run.steps = [{"error": "fit_threshold_not_met", "timestamp": datetime.utcnow().isoformat()}]
                await db.commit()
            raise

        # Write results back to DB
        async with SessionLocal() as db:
            result = await db.execute(
                select(ApplicationRun).where(ApplicationRun.id == uuid.UUID(run_id))
            )
            run = result.scalar_one()
            run.status = ApplicationStatus.review
            run.cover_letter = result_data.get("cover_letter", "")
            run.bullets = result_data.get("bullets", [])
            run.steps = result_data.get("steps", [])

            job_result = await db.execute(
                select(JobRecord).where(JobRecord.id == run.job_record_id)
            )
            job = job_result.scalar_one_or_none()
            if job:
                jd = result_data.get("jd", {})
                job.fit_score = result_data.get("fit_score")
                job.title = jd.get("title")
                job.company = jd.get("company")
                job.raw_jd_text = jd.get("raw_jd_text")
                job.keywords = jd.get("keywords", [])
                job.ats_type = jd.get("ats_type")

            await db.commit()

        log.info(
            "application_complete",
            run_id=run_id,
            fit_score=result_data.get("fit_score"),
            steps=len(result_data.get("steps", [])),
        )
        return result_data

    finally:
        await engine.dispose()


async def _mark_failed(run_id: str, error: str) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from backend.db.models import ApplicationRun, ApplicationStatus

    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(ApplicationRun).where(ApplicationRun.id == uuid.UUID(run_id))
            )
            run = result.scalar_one_or_none()
            if run:
                run.status = ApplicationStatus.failed
                existing = list(run.steps or [])
                existing.append({"error": error, "timestamp": datetime.utcnow().isoformat()})
                run.steps = existing
                await db.commit()
    finally:
        await engine.dispose()


def _profile_to_dict(profile: Any) -> Dict[str, Any]:
    return {
        "user_id": profile.user_id,
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "linkedin_url": profile.linkedin_url,
        "github_url": profile.github_url,
        "skills": profile.skills or [],
        "experience": profile.experience or {},
        "fit_threshold": profile.fit_threshold,
    }
