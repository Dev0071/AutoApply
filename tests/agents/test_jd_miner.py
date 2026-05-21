import json

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.jd_miner import JDMiner, detect_ats_type
from backend.agents.schemas import JDResult


# ---------------------------------------------------------------------------
# detect_ats_type — pure function, no mocks needed
# ---------------------------------------------------------------------------

def test_detect_greenhouse():
    assert detect_ats_type("https://boards.greenhouse.io/acme/jobs/123") == "greenhouse"


def test_detect_lever():
    assert detect_ats_type("https://jobs.lever.co/acme/abc-123") == "lever"


def test_detect_workday():
    assert detect_ats_type("https://acme.wd1.myworkdayjobs.com/careers/job/123") == "workday"


def test_detect_ashby():
    assert detect_ats_type("https://jobs.ashbyhq.com/acme/123") == "ashby"


def test_detect_unknown():
    assert detect_ats_type("https://acme.com/careers/swe") == "unknown"


# ---------------------------------------------------------------------------
# JDMiner.fetch — happy path
# ---------------------------------------------------------------------------

_CLAUDE_EXTRACTION = json.dumps({
    "title": "Senior Python Engineer",
    "company": "Acme Corp",
    "keywords": ["python", "fastapi", "postgresql", "docker"],
})

_JOB_HTML = """
<html><body>
  <nav>Nav junk</nav>
  <h1>Senior Python Engineer at Acme Corp</h1>
  <p>We need Python and FastAPI developers with PostgreSQL and Docker experience.</p>
  <footer>Footer junk</footer>
</body></html>
"""


def _make_anthropic_mock(response_text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = response_text
    message = MagicMock()
    message.content = [content_block]
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=message)
    return client


@pytest.mark.asyncio
async def test_fetch_returns_jd_result():
    mock_response = MagicMock()
    mock_response.text = _JOB_HTML
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        miner = JDMiner(anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION))
        result = await miner.fetch("https://boards.greenhouse.io/acme/jobs/1")

    assert isinstance(result, JDResult)
    assert result.title == "Senior Python Engineer"
    assert result.company == "Acme Corp"
    assert "python" in result.keywords
    assert result.ats_type == "greenhouse"


@pytest.mark.asyncio
async def test_fetch_strips_nav_footer_from_text():
    mock_response = MagicMock()
    mock_response.text = _JOB_HTML
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        miner = JDMiner(anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION))
        result = await miner.fetch("https://boards.greenhouse.io/acme/jobs/1")

    assert "Nav junk" not in result.raw_jd_text
    assert "Footer junk" not in result.raw_jd_text


@pytest.mark.asyncio
async def test_fetch_handles_claude_json_in_code_block():
    """Claude sometimes wraps JSON in ```json ... ``` despite instructions."""
    wrapped = f"```json\n{_CLAUDE_EXTRACTION}\n```"
    mock_response = MagicMock()
    mock_response.text = _JOB_HTML
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        miner = JDMiner(anthropic_client=_make_anthropic_mock(wrapped))
        result = await miner.fetch("https://example.com/job")

    assert result.title == "Senior Python Engineer"


# ---------------------------------------------------------------------------
# JDMiner.fetch — failure paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_raises_on_http_error():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        miner = JDMiner(anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION))
        with pytest.raises(httpx.HTTPStatusError):
            await miner.fetch("https://example.com/job")


@pytest.mark.asyncio
async def test_fetch_raises_on_invalid_claude_json():
    mock_response = MagicMock()
    mock_response.text = _JOB_HTML
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        miner = JDMiner(anthropic_client=_make_anthropic_mock("not valid json at all"))
        with pytest.raises(ValueError, match="Failed to parse JD extraction"):
            await miner.fetch("https://example.com/job")
