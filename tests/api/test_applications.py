from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.api.schemas import JobAnalyzeResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_anthropic_mock(jd_text: str, cover_letter: str, bullets: list[str]) -> MagicMock:
    """Mock client serving JD extraction, then the single merged tailoring call."""
    jd_extraction = json.dumps({
        "title": "Senior Engineer",
        "company": "Acme",
        "keywords": ["python", "fastapi"],
    })
    tailoring = json.dumps({"cover_letter": cover_letter, "bullets": bullets})

    jd_block = MagicMock(); jd_block.text = jd_extraction
    t_block = MagicMock(); t_block.text = tailoring

    jd_msg = MagicMock(); jd_msg.content = [jd_block]
    t_msg = MagicMock(); t_msg.content = [t_block]

    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=[jd_msg, t_msg])
    return client


_PROFILE_BODY = {
    "user_id": "user-123",
    "name": "John Gacheru",
    "email": "john@example.com",
    "phone": "+1-555-0001",
    "location": "Nairobi",
    "skills": ["python", "fastapi"],
    "experience": {"backend": ["Built REST APIs"]},
    "fit_threshold": 70,
}

# Body text must clear the JD miner's 200-char minimum-content guard.
_JOB_HTML = (
    "<html><body>"
    "<h1>Senior Engineer at Acme</h1>"
    "<p>We need Python and FastAPI developers to build and operate resilient "
    "high-throughput backend services. You will design REST APIs, evolve our "
    "PostgreSQL schemas, ship containerized deployments, and collaborate with "
    "product engineering on roadmap delivery across the entire stack.</p>"
    "</body></html>"
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /jobs/analyze — stateless, works without DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_job_passes_threshold():
    mock_response = MagicMock()
    mock_response.text = _JOB_HTML
    mock_response.raise_for_status = MagicMock()

    anthropic_mock = _make_anthropic_mock(
        _JOB_HTML,
        cover_letter="Dear Hiring Manager...",
        bullets=["Built FastAPI services", "Led Python migration"],
    )

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from backend.api.dependencies import get_anthropic, get_cache
        app.dependency_overrides[get_anthropic] = lambda: anthropic_mock
        app.dependency_overrides[get_cache] = lambda: None  # no Redis in tests

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/jobs/analyze", json={
                "url": "https://boards.greenhouse.io/acme/jobs/1",
                "profile": {**_PROFILE_BODY, "fit_threshold": 1},  # low threshold → always passes
            })

    app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Senior Engineer"
    assert data["company"] == "Acme"
    assert data["passes_threshold"] is True
    assert data["cover_letter"] == "Dear Hiring Manager..."
    assert len(data["bullets"]) == 2
    assert data["ats_type"] == "greenhouse"


@pytest.mark.asyncio
async def test_analyze_job_fails_threshold_skips_tailoring():
    mock_response = MagicMock()
    mock_response.text = _JOB_HTML
    mock_response.raise_for_status = MagicMock()

    # Only JD extraction call — no tailoring calls expected
    jd_block = MagicMock()
    jd_block.text = json.dumps({"title": "Engineer", "company": "Acme", "keywords": ["rust"]})
    jd_msg = MagicMock(); jd_msg.content = [jd_block]
    anthropic_mock = MagicMock()
    anthropic_mock.messages.create = AsyncMock(return_value=jd_msg)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from backend.api.dependencies import get_anthropic, get_cache
        app.dependency_overrides[get_anthropic] = lambda: anthropic_mock
        app.dependency_overrides[get_cache] = lambda: None  # no Redis in tests

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/jobs/analyze", json={
                "url": "https://example.com/job",
                "profile": {**_PROFILE_BODY, "fit_threshold": 99},  # high threshold → always fails
            })

    app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()
    assert data["passes_threshold"] is False
    assert data["cover_letter"] == ""
    assert data["bullets"] == []
    # Tailoring was NOT called
    assert anthropic_mock.messages.create.await_count == 1


@pytest.mark.asyncio
async def test_analyze_job_returns_422_on_fetch_failure():
    import httpx

    anthropic_mock = MagicMock()

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from backend.api.dependencies import get_anthropic, get_cache
        app.dependency_overrides[get_anthropic] = lambda: anthropic_mock
        app.dependency_overrides[get_cache] = lambda: None  # no Redis in tests

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/jobs/analyze", json={
                "url": "https://example.com/job",
                "profile": _PROFILE_BODY,
            })

    app.dependency_overrides.clear()
    assert r.status_code == 422
