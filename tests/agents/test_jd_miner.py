from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.exceptions import JDFetchError
from backend.agents.jd_miner import JDMiner, detect_ats_type, is_listing_url
from backend.agents.schemas import JDResult
from backend.agents.usage import UsageTracker


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
# is_listing_url — search/index pages vs real postings
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    # The exact URL from the field report
    "https://my.greenhouse.io/jobs/search?query=QA%20automation&location=United%20States"
    "&lat=39.71614&lon=-96.999246&location_type=country&country_short_name=US"
    "&date_posted=past_five_days&salary=more_than_60k",
    "https://my.greenhouse.io/jobs/search",
    "https://acme.com/jobs",
    "https://acme.com/jobs/",
    "https://acme.com/careers",
    "https://acme.com/search?query=engineer",
    "https://acme.com/openings",
    "https://acme.com/positions/",
])
def test_listing_urls_detected(url):
    assert is_listing_url(url) is True


@pytest.mark.parametrize("url", [
    # Real postings must never be rejected — a false positive here blocks a
    # legitimate application, which is worse than the bug this guards against.
    "https://boards.greenhouse.io/acme/jobs/12345",
    "https://job-boards.greenhouse.io/acme/jobs/999",
    "https://jobs.lever.co/acme/abc-123",
    "https://jobs.ashbyhq.com/acme/1a2b3c",
    "https://acme.wd1.myworkdayjobs.com/careers/job/San-Francisco/Engineer_R-123",
    "https://acme.com/careers/senior-engineer",
    # Tracking/search params on a real posting must not trigger the guard
    "https://boards.greenhouse.io/acme/jobs/12345?q=qa+automation",
    "https://boards.greenhouse.io/acme/jobs/12345?keywords=python&utm_source=search",
    "https://jobs.lever.co/acme/abc-123?query=engineer",
])
def test_real_postings_not_flagged_as_listings(url):
    assert is_listing_url(url) is False


def test_listing_url_on_ats_domain_is_not_an_ats_type():
    """A search page on an ATS domain must not route to Tier 1 schema
    prefetch — there is no job id to look up."""
    url = "https://my.greenhouse.io/jobs/search?query=QA"
    assert detect_ats_type(url) == "unknown"


# ---------------------------------------------------------------------------
# JDMiner.fetch — happy path
# ---------------------------------------------------------------------------

_CLAUDE_EXTRACTION = json.dumps({
    "title": "Senior Python Engineer",
    "company": "Acme Corp",
    "keywords": ["python", "fastapi", "postgresql", "docker"],
})

# Body text must clear the 200-char minimum that guards against JS-only pages.
_JOB_HTML = """
<html><body>
  <nav>Nav junk</nav>
  <h1>Senior Python Engineer at Acme Corp</h1>
  <p>We need Python and FastAPI developers with PostgreSQL and Docker experience
  to build and operate high-throughput backend services. You will design REST
  APIs, own database schema evolution, ship containerized deployments, and
  collaborate with product engineering on roadmap delivery across the stack.</p>
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


def _patch_http(mock_cls, html: str = _JOB_HTML):
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=mock_response)
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_http


@pytest.mark.asyncio
async def test_fetch_returns_jd_result():
    with patch("httpx.AsyncClient") as mock_cls:
        _patch_http(mock_cls)
        miner = JDMiner(anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION))
        result = await miner.fetch("https://boards.greenhouse.io/acme/jobs/1")

    assert isinstance(result, JDResult)
    assert result.title == "Senior Python Engineer"
    assert result.company == "Acme Corp"
    assert "python" in result.keywords
    assert result.ats_type == "greenhouse"


@pytest.mark.asyncio
async def test_fetch_strips_nav_footer_from_text():
    with patch("httpx.AsyncClient") as mock_cls:
        _patch_http(mock_cls)
        miner = JDMiner(anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION))
        result = await miner.fetch("https://boards.greenhouse.io/acme/jobs/1")

    assert "Nav junk" not in result.raw_jd_text
    assert "Footer junk" not in result.raw_jd_text


@pytest.mark.asyncio
async def test_fetch_uses_cheap_extraction_model_with_structured_output():
    client = _make_anthropic_mock(_CLAUDE_EXTRACTION)
    with patch("httpx.AsyncClient") as mock_cls:
        _patch_http(mock_cls)
        miner = JDMiner(anthropic_client=client)
        await miner.fetch("https://boards.greenhouse.io/acme/jobs/1")

    kwargs = client.messages.create.call_args.kwargs
    from backend.config import settings
    assert kwargs["model"] == settings.extraction_model
    assert kwargs["output_config"]["format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_fetch_records_usage():
    tracker = UsageTracker()
    with patch("httpx.AsyncClient") as mock_cls:
        _patch_http(mock_cls)
        miner = JDMiner(
            anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION), tracker=tracker
        )
        await miner.fetch("https://boards.greenhouse.io/acme/jobs/1")

    assert len(tracker.entries) == 1
    assert tracker.entries[0]["stage"] == "jd_extraction"


@pytest.mark.asyncio
async def test_fetch_handles_claude_json_in_code_block():
    """Claude sometimes wraps JSON in ```json ... ``` despite instructions."""
    wrapped = f"```json\n{_CLAUDE_EXTRACTION}\n```"
    with patch("httpx.AsyncClient") as mock_cls:
        _patch_http(mock_cls)
        miner = JDMiner(anthropic_client=_make_anthropic_mock(wrapped))
        result = await miner.fetch("https://example.com/job")

    assert result.title == "Senior Python Engineer"


# ---------------------------------------------------------------------------
# JD caching — mine each URL once
# ---------------------------------------------------------------------------

def _make_cache(hit: str | None = None) -> MagicMock:
    cache = MagicMock()
    cache.get = AsyncMock(return_value=hit)
    cache.set = AsyncMock()
    return cache


@pytest.mark.asyncio
async def test_fetch_cache_hit_skips_http_and_claude():
    cached = JDResult(
        url="https://boards.greenhouse.io/acme/jobs/1",
        title="Cached Title",
        company="Acme",
        raw_jd_text="cached text",
        keywords=["python"],
        ats_type="greenhouse",
    ).model_dump_json()

    client = _make_anthropic_mock(_CLAUDE_EXTRACTION)
    cache = _make_cache(hit=cached)
    miner = JDMiner(anthropic_client=client, cache=cache)
    result = await miner.fetch("https://boards.greenhouse.io/acme/jobs/1")

    assert result.title == "Cached Title"
    client.messages.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_cache_miss_populates_cache():
    cache = _make_cache(hit=None)
    with patch("httpx.AsyncClient") as mock_cls:
        _patch_http(mock_cls)
        miner = JDMiner(
            anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION), cache=cache
        )
        await miner.fetch("https://boards.greenhouse.io/acme/jobs/1")

    cache.set.assert_awaited_once()
    key = cache.set.await_args.args[0]
    assert key == "jd:https://boards.greenhouse.io/acme/jobs/1"


# ---------------------------------------------------------------------------
# JDMiner.fetch — failure paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_blocked_domain_raises_before_http():
    miner = JDMiner(anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION))
    with pytest.raises(JDFetchError, match="LinkedIn"):
        await miner.fetch("https://www.linkedin.com/jobs/view/123")


@pytest.mark.asyncio
async def test_fetch_listing_url_raises_actionable_error_before_http():
    """The search page costs no request and no tokens, and the message names
    the actual fix rather than pointing at the domain the user already used."""
    client = _make_anthropic_mock(_CLAUDE_EXTRACTION)
    miner = JDMiner(anthropic_client=client)

    with pytest.raises(JDFetchError, match="search or listing page"):
        await miner.fetch("https://my.greenhouse.io/jobs/search?query=QA%20automation")

    client.messages.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_raises_jdfetch_error_on_http_error():
    import httpx

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_response = MagicMock()
        error_response = MagicMock()
        error_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=error_response
        )
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        miner = JDMiner(anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION))
        with pytest.raises(JDFetchError, match="HTTP 404"):
            await miner.fetch("https://example.com/job")


@pytest.mark.asyncio
async def test_fetch_thin_page_raises_jdfetch_error():
    with patch("httpx.AsyncClient") as mock_cls:
        _patch_http(mock_cls, html="<html><body>tiny</body></html>")
        miner = JDMiner(anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION))
        with pytest.raises(JDFetchError, match="too little text"):
            await miner.fetch("https://example.com/job")


# ---------------------------------------------------------------------------
# Browser fallback for SPA / bot-blocked posting pages
# ---------------------------------------------------------------------------

_RENDERED_HTML = (
    "<html><body><h1>Senior Python Engineer at Acme Corp</h1><p>"
    + "We need Python and FastAPI developers with PostgreSQL experience. " * 8
    + "</p></body></html>"
)


def _make_browser(html: str) -> MagicMock:
    from contextlib import asynccontextmanager

    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.content = AsyncMock(return_value=html)

    browser = MagicMock()

    @asynccontextmanager
    async def new_page():
        yield page

    browser.new_page = new_page
    browser.page = page
    return browser


@pytest.mark.asyncio
async def test_thin_http_response_falls_back_to_browser():
    """An SPA board (Ashby) returns ~56 chars over plain HTTP; rendering it
    in the browser we already own recovers the JD."""
    browser = _make_browser(_RENDERED_HTML)
    with patch("httpx.AsyncClient") as mock_cls:
        _patch_http(mock_cls, html="<html><body>loading…</body></html>")
        miner = JDMiner(
            anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION), browser=browser
        )
        result = await miner.fetch("https://jobs.ashbyhq.com/acme/1a2b3c")

    assert result.title == "Senior Python Engineer"
    browser.page.goto.assert_awaited_once()


@pytest.mark.asyncio
async def test_403_falls_back_to_browser():
    """Career sites that 403 a bare HTTP client render fine in a real browser."""
    import httpx

    browser = _make_browser(_RENDERED_HTML)
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_response = MagicMock()
        err = MagicMock(); err.status_code = 403
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=err
        )
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        miner = JDMiner(
            anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION), browser=browser
        )
        result = await miner.fetch("https://careers.leidos.com/jobs/17658008-qa-lead")

    assert result.title == "Senior Python Engineer"


@pytest.mark.asyncio
async def test_good_http_response_never_opens_a_browser():
    """Greenhouse postings work over plain HTTP — the browser session (and its
    cost) must not be spent on the common path."""
    browser = _make_browser(_RENDERED_HTML)
    with patch("httpx.AsyncClient") as mock_cls:
        _patch_http(mock_cls)
        miner = JDMiner(
            anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION), browser=browser
        )
        await miner.fetch("https://boards.greenhouse.io/acme/jobs/1")

    browser.page.goto.assert_not_awaited()


@pytest.mark.asyncio
async def test_listing_url_never_opens_a_browser():
    """A search page has no JD to render — don't spend a session discovering that."""
    browser = _make_browser(_RENDERED_HTML)
    miner = JDMiner(anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION), browser=browser)

    with pytest.raises(JDFetchError, match="search or listing page"):
        await miner.fetch("https://my.greenhouse.io/jobs/search?query=QA")

    browser.page.goto.assert_not_awaited()


@pytest.mark.asyncio
async def test_browser_render_still_thin_raises_clear_error():
    browser = _make_browser("<html><body>Please sign in</body></html>")
    with patch("httpx.AsyncClient") as mock_cls:
        _patch_http(mock_cls, html="<html><body>tiny</body></html>")
        miner = JDMiner(
            anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION), browser=browser
        )
        with pytest.raises(JDFetchError, match="even after rendering in a browser"):
            await miner.fetch("https://jobs.ashbyhq.com/acme/1a2b3c")


@pytest.mark.asyncio
async def test_browser_crash_surfaces_original_http_error():
    """If the browser itself fails, the user sees the actionable HTTP-level
    message, not an internal Playwright error."""
    browser = MagicMock()
    browser.new_page = MagicMock(side_effect=RuntimeError("browser session died"))

    with patch("httpx.AsyncClient") as mock_cls:
        _patch_http(mock_cls, html="<html><body>tiny</body></html>")
        miner = JDMiner(
            anthropic_client=_make_anthropic_mock(_CLAUDE_EXTRACTION), browser=browser
        )
        with pytest.raises(JDFetchError, match="too little text"):
            await miner.fetch("https://jobs.ashbyhq.com/acme/1a2b3c")


@pytest.mark.asyncio
async def test_fetch_invalid_claude_json_degrades_gracefully():
    """Non-JSON extraction returns an empty structure; the fit scorer then
    scores 0 and the gate rejects — no crash, no wasted downstream spend."""
    with patch("httpx.AsyncClient") as mock_cls:
        _patch_http(mock_cls)
        miner = JDMiner(anthropic_client=_make_anthropic_mock("not valid json at all"))
        result = await miner.fetch("https://example.com/job")

    assert result.title is None
    assert result.keywords == []
