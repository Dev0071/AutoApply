from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict

import anthropic
import structlog
from celery import Celery

from backend.config import settings

log = structlog.get_logger()

celery_app = Celery("autoapply", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"backend.workers.tasks.*": {"queue": "applications"}}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_application(self, run_id: str, job_url: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    from backend.agents.exceptions import (
        FitThresholdError,
        JDFetchError,
        RateLimitExceededError,
        StuckLoopError,
    )

    try:
        return asyncio.run(_execute(run_id, job_url))
    except FitThresholdError as exc:
        log.info("fit_threshold_not_met", run_id=run_id, error=str(exc))
        return {"status": "failed", "reason": "fit_threshold_not_met"}
    except JDFetchError as exc:
        log.warning("jd_fetch_failed", run_id=run_id, url=job_url, error=str(exc))
        return {"status": "failed", "reason": "jd_fetch_failed"}
    except RateLimitExceededError as exc:
        # Never retried — protecting the user's standing with the ATS platform
        log.warning("rate_limited", run_id=run_id, platform=exc.platform, error=str(exc))
        asyncio.run(_mark_failed(run_id, f"rate_limited: {exc}"))
        return {"status": "failed", "reason": "rate_limited"}
    except StuckLoopError as exc:
        # Never retried — retrying a stuck loop burns the same tokens on the same wall
        log.warning("agent_stuck", run_id=run_id, error=str(exc))
        asyncio.run(_mark_failed(run_id, f"agent_stuck: {exc}"))
        return {"status": "failed", "reason": "agent_stuck"}
    except (
        anthropic.BadRequestError,
        anthropic.AuthenticationError,
        anthropic.PermissionDeniedError,
        anthropic.NotFoundError,
    ) as exc:
        # 4xx from the API is a configuration problem (bad key, missing
        # workspace id, unknown model). Retrying re-runs the whole pipeline —
        # including the JD fetch — for a guaranteed-identical failure.
        log.error("anthropic_request_rejected", run_id=run_id, error=str(exc))
        asyncio.run(_mark_failed(run_id, f"anthropic_config_error: {exc}"))
        return {"status": "failed", "reason": "anthropic_config_error"}
    except Exception as exc:
        log.error("task_failed", run_id=run_id, retries=self.request.retries, error=str(exc))
        if self.request.retries >= self.max_retries:
            asyncio.run(_mark_failed(run_id, str(exc)))
        raise self.retry(exc=exc)


async def _execute(run_id: str, job_url: str) -> Dict[str, Any]:
    import anthropic
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from backend.agents.exceptions import (
        FitThresholdError,
        JDFetchError,
        RateLimitExceededError,
    )
    from backend.agents.jd_miner import detect_ats_type
    from backend.agents.orchestrator import Orchestrator
    from backend.db.models import ApplicationRun, ApplicationStatus, JobRecord, UserProfile
    from backend.services.anthropic_client import build_anthropic_client
    from backend.services.browser import BrowserService
    from backend.services.cache import CacheService
    from backend.services.storage import StorageService

    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    # asyncio.run() closes the loop on exit; any HTTP client still holding a
    # socket then raises "Event loop is closed" from its finalizer.
    clients_to_close: list = []

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

        cache = CacheService()
        clients_to_close.append(cache)

        # Per-platform daily cap — protects users from ATS bot detection/blocks
        platform = detect_ats_type(job_url)
        try:
            count = await cache.incr(f"ratelimit:{run.user_id}:{platform}:{datetime.utcnow():%Y%m%d}")
        except Exception as exc:
            log.warning("rate_limit_check_failed", error=str(exc))
            count = 0
        if count > settings.max_daily_applications_per_platform:
            raise RateLimitExceededError(
                f"Daily cap of {settings.max_daily_applications_per_platform} "
                f"applications on {platform} reached.",
                platform=platform,
                limit=settings.max_daily_applications_per_platform,
            )

        client = build_anthropic_client()
        clients_to_close.append(client)
        storage = StorageService()
        browser = BrowserService()
        orchestrator = Orchestrator(client, storage, browser, cache=cache)

        try:
            result_data = await orchestrator.run(job_url, profile_dict, run_id)
        except FitThresholdError as exc:
            async with SessionLocal() as db:
                result = await db.execute(
                    select(ApplicationRun).where(ApplicationRun.id == uuid.UUID(run_id))
                )
                run = result.scalar_one()
                run.status = ApplicationStatus.failed
                run.steps = [{
                    "error": "fit_threshold_not_met",
                    "fit_score": exc.score,
                    "threshold": exc.threshold,
                    "timestamp": datetime.utcnow().isoformat(),
                }]
                await db.commit()
            raise
        except JDFetchError as exc:
            async with SessionLocal() as db:
                result = await db.execute(
                    select(ApplicationRun).where(ApplicationRun.id == uuid.UUID(run_id))
                )
                run = result.scalar_one()
                run.status = ApplicationStatus.failed
                run.steps = [{
                    "error": "jd_fetch_failed",
                    "message": str(exc),
                    "timestamp": datetime.utcnow().isoformat(),
                }]
                await db.commit()
            raise

        # Cost anomaly alert — early signal that an ATS changed something
        cost = result_data.get("total_cost_usd") or 0.0
        if cost > settings.cost_alert_usd:
            log.warning(
                "cost_anomaly",
                run_id=run_id,
                cost_usd=cost,
                threshold=settings.cost_alert_usd,
                tier=result_data.get("tier"),
            )

        # Write results back to DB
        async with SessionLocal() as db:
            result = await db.execute(
                select(ApplicationRun).where(ApplicationRun.id == uuid.UUID(run_id))
            )
            run = result.scalar_one()
            run.status = ApplicationStatus.review
            run.cover_letter = result_data.get("cover_letter", "")
            run.bullets = result_data.get("bullets", [])
            steps = list(result_data.get("steps", []))
            if abort_reason := result_data.get("abort_reason"):
                steps.append({
                    "warning": abort_reason,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            run.steps = steps
            run.total_cost_usd = cost
            run.token_usage = result_data.get("token_usage")

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
        for client in clients_to_close:
            try:
                await client.close()
            except Exception as exc:  # never mask the real outcome
                log.debug("anthropic_client_close_failed", error=str(exc))
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
