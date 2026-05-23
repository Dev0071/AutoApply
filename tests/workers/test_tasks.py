from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run(user_id: str = "u1", status: str = "queued") -> MagicMock:
    run = MagicMock()
    run.id = uuid.uuid4()
    run.user_id = user_id
    run.job_record_id = uuid.uuid4()
    run.status = status
    run.steps = []
    return run


def _make_profile(user_id: str = "u1") -> MagicMock:
    profile = MagicMock()
    profile.user_id = user_id
    profile.name = "John Gacheru"
    profile.email = "john@example.com"
    profile.phone = "+1-555-0001"
    profile.location = "Nairobi"
    profile.linkedin_url = None
    profile.github_url = None
    profile.skills = ["python", "fastapi"]
    profile.experience = {}
    profile.fit_threshold = 70
    return profile


def _make_job() -> MagicMock:
    job = MagicMock()
    job.fit_score = None
    job.title = None
    job.company = None
    job.raw_jd_text = None
    job.keywords = []
    job.ats_type = None
    return job


ORCHESTRATOR_RESULT = {
    "fit_score": 85.0,
    "cover_letter": "Dear Hiring Manager...",
    "bullets": ["Built APIs", "Led migration"],
    "steps": [{"step_number": 0, "action": "click", "x": 100, "y": 200}],
    "jd": {"title": "Senior Engineer", "company": "Acme", "raw_jd_text": "...", "keywords": ["python"], "ats_type": "greenhouse"},
}


# ---------------------------------------------------------------------------
# _profile_to_dict
# ---------------------------------------------------------------------------

def test_profile_to_dict_maps_all_fields():
    from backend.workers.tasks import _profile_to_dict

    profile = _make_profile()
    result = _profile_to_dict(profile)

    assert result["user_id"] == "u1"
    assert result["name"] == "John Gacheru"
    assert result["skills"] == ["python", "fastapi"]
    assert result["fit_threshold"] == 70


def test_profile_to_dict_none_skills_becomes_empty_list():
    from backend.workers.tasks import _profile_to_dict

    profile = _make_profile()
    profile.skills = None
    result = _profile_to_dict(profile)
    assert result["skills"] == []


# ---------------------------------------------------------------------------
# _mark_failed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_failed_sets_status_and_appends_step():
    from backend.workers.tasks import _mark_failed

    run_id = str(uuid.uuid4())
    run = _make_run()

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=run)))
    mock_db.commit = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    mock_session_local = MagicMock(return_value=mock_db)
    mock_engine = AsyncMock()
    mock_engine.dispose = AsyncMock()

    with patch("backend.workers.tasks.settings") as mock_settings, \
         patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine), \
         patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=mock_session_local):
        mock_settings.database_url = "postgresql+asyncpg://test"
        await _mark_failed(run_id, "something went wrong")

    from backend.db.models import ApplicationStatus
    assert run.status == ApplicationStatus.failed
    assert any("something went wrong" in str(s) for s in run.steps)


# ---------------------------------------------------------------------------
# _execute — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_writes_results_and_sets_review():
    from backend.workers.tasks import _execute

    run_id = str(uuid.uuid4())
    run = _make_run()
    profile = _make_profile()
    job = _make_job()

    def make_db() -> AsyncMock:
        db = AsyncMock()
        db.__aenter__ = AsyncMock(return_value=db)
        db.__aexit__ = AsyncMock(return_value=False)
        db.commit = AsyncMock()
        scalar_run = MagicMock(scalar_one=MagicMock(return_value=run))
        scalar_profile = MagicMock(scalar_one_or_none=MagicMock(return_value=profile))
        scalar_job = MagicMock(scalar_one_or_none=MagicMock(return_value=job))
        db.execute = AsyncMock(side_effect=[scalar_run, scalar_profile, scalar_run, scalar_job])
        return db

    mock_session_local = MagicMock(side_effect=make_db)
    mock_engine = AsyncMock()
    mock_engine.dispose = AsyncMock()

    mock_orchestrator = AsyncMock()
    mock_orchestrator.run = AsyncMock(return_value=ORCHESTRATOR_RESULT)
    mock_orch_cls = MagicMock(return_value=mock_orchestrator)

    with patch("backend.workers.tasks.settings") as mock_settings, \
         patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine), \
         patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=mock_session_local), \
         patch("anthropic.AsyncAnthropic"), \
         patch("backend.agents.orchestrator.Orchestrator", mock_orch_cls), \
         patch("backend.services.browser.BrowserService"), \
         patch("backend.services.storage.StorageService"):
        mock_settings.database_url = "postgresql+asyncpg://test"
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.vision_loop_max_steps = 30
        mock_settings.vision_loop_wait_ms = 800
        result = await _execute(run_id, "https://boards.greenhouse.io/acme/jobs/1")

    assert result["fit_score"] == 85.0
    assert result["cover_letter"] == "Dear Hiring Manager..."

    from backend.db.models import ApplicationStatus
    assert run.status == ApplicationStatus.review
    assert run.cover_letter == "Dear Hiring Manager..."
    assert run.bullets == ["Built APIs", "Led migration"]
