from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

import anthropic
import httpx
import structlog
from bs4 import BeautifulSoup

from backend.agents.exceptions import JDFetchError
from backend.agents.schemas import JDResult
from backend.agents.usage import UsageTracker
from backend.config import settings

log = structlog.get_logger()

_BLOCKED_DOMAINS: list[tuple[str, str]] = [
    (r"indeed\.com",        "Indeed"),
    (r"linkedin\.com",      "LinkedIn"),
    (r"glassdoor\.com",     "Glassdoor"),
    (r"ziprecruiter\.com",  "ZipRecruiter"),
    (r"monster\.com",       "Monster"),
    (r"simplyhired\.com",   "SimplyHired"),
    (r"careerbuilder\.com", "CareerBuilder"),
    (r"dice\.com",          "Dice"),
]

_ATS_HINT = (
    "Paste the direct ATS link from the job posting instead — for example: "
    "boards.greenhouse.io/…, jobs.lever.co/…, jobs.ashbyhq.com/…, or myworkdayjobs.com/…"
)

_ATS_PATTERNS: list[tuple[str, str]] = [
    (r"greenhouse\.io", "greenhouse"),
    (r"lever\.co", "lever"),
    (r"myworkdayjobs\.com", "workday"),
    (r"ashbyhq\.com", "ashby"),
    (r"jobvite\.com", "jobvite"),
    (r"icims\.com", "icims"),
]

# Search / board-index URLs. These are the single most common thing a user
# pastes by mistake: they look like ATS links and even live on ATS domains,
# but they list many jobs rather than describing one, so there is no JD to
# mine and no form to fill.
# Matched against the URL PATH only, never the query string: a valid posting
# URL may carry tracking params like ?q=... or ?keywords=..., and rejecting a
# real job is a worse failure than accepting a search page.
_LISTING_PATTERNS: list[str] = [
    r"/jobs/search/?$",       # my.greenhouse.io/jobs/search
    r"/job-search/?$",
    r"/jobs/?$",              # bare /jobs index
    r"/search/?$",
    r"/careers/?$",           # bare careers index
    r"/openings/?$",
    r"/positions/?$",
]

_LISTING_HINT = (
    "That link is a job search or listing page, not a single job posting. "
    "Open the job you want from that list and paste the URL of that job's own "
    "page — it will look like boards.greenhouse.io/<company>/jobs/<id>, "
    "jobs.lever.co/<company>/<id>, jobs.ashbyhq.com/<company>/<id>, or a "
    "myworkdayjobs.com job URL."
)


def is_listing_url(url: str) -> bool:
    """True when the URL points at a list of jobs rather than one posting.

    Only the path is examined — a real posting can carry any query string,
    and wrongly rejecting a valid job is worse than letting a search page
    through to the thin-content check.
    """
    path = urlsplit(url).path or "/"
    return any(re.search(p, path, re.IGNORECASE) for p in _LISTING_PATTERNS)

_EXTRACT_SYSTEM = (
    "Extract structured information from job descriptions.\n\n"
    "Reply with ONLY a JSON object — no preamble, no markdown fences:\n"
    '{\n'
    '  "title": "<job title or null>",\n'
    '  "company": "<company name or null>",\n'
    '  "keywords": ["<skill or technology>", ...]\n'
    "}\n\n"
    "Include technical skills, tools, languages, and frameworks in keywords.\n"
    "Limit keywords to 30 items max."
)


def detect_ats_type(url: str) -> str:
    # A listing page on an ATS domain is not an ATS posting — classifying it
    # as one would send the orchestrator off to prefetch a question schema
    # for a job id that doesn't exist.
    if is_listing_url(url):
        return "unknown"
    for pattern, name in _ATS_PATTERNS:
        if re.search(pattern, url):
            return name
    return "unknown"


def _strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers Claude sometimes adds despite instructions."""
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)


_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": ["string", "null"]},
        "company": {"type": ["string", "null"]},
        "keywords": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "company", "keywords"],
    "additionalProperties": False,
}


class JDMiner:
    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic,
        timeout: int = 15,
        cache=None,
        tracker: UsageTracker | None = None,
        browser=None,
    ):
        self._client = anthropic_client
        self._timeout = timeout
        self._cache = cache
        self.tracker = tracker if tracker is not None else UsageTracker()
        # Optional BrowserService. Plain HTTP handles Greenhouse postings fine
        # (9-18k chars); the browser is the fallback for SPA boards like Ashby
        # and for sites that 403 a bare HTTP client.
        self._browser = browser

    async def fetch(self, url: str) -> JDResult:
        # Popular postings are applied to by many users — mine each URL once.
        if self._cache is not None:
            try:
                cached = await self._cache.get(f"jd:{url}")
            except Exception as exc:
                log.warning("jd_cache_read_failed", error=str(exc))
                cached = None
            if cached:
                log.info("jd_cache_hit", url=url)
                return JDResult.model_validate_json(cached)

        raw_text = await self._fetch_text(url)
        extracted = await self._extract_structured(raw_text)
        ats_type = detect_ats_type(url)

        log.info(
            "jd_fetched",
            url=url,
            title=extracted.get("title"),
            company=extracted.get("company"),
            keyword_count=len(extracted.get("keywords", [])),
            ats_type=ats_type,
        )

        result = JDResult(
            url=url,
            title=extracted.get("title"),
            company=extracted.get("company"),
            raw_jd_text=raw_text,
            keywords=extracted.get("keywords", []),
            ats_type=ats_type,
        )

        if self._cache is not None:
            try:
                await self._cache.set(
                    f"jd:{url}",
                    result.model_dump_json(),
                    ttl=settings.jd_cache_ttl_seconds,
                )
            except Exception as exc:
                log.warning("jd_cache_write_failed", error=str(exc))

        return result

    async def _fetch_text(self, url: str) -> str:
        """Cheap HTTP first, real browser only if that isn't enough.

        Measured: Greenhouse postings return 9-18k chars over plain HTTP, so
        the common path costs no browser session. Ashby (SPA) and sites that
        403 a bare client need a rendered page.
        """
        # Cheapest checks first — neither costs a request or a token.
        if is_listing_url(url):
            raise JDFetchError(_LISTING_HINT)

        for pattern, name in _BLOCKED_DOMAINS:
            if re.search(pattern, url, re.IGNORECASE):
                raise JDFetchError(
                    f"{name} blocks automated requests. {_ATS_HINT}"
                )

        try:
            return await self._fetch_text_http(url)
        except JDFetchError as exc:
            if self._browser is None:
                raise
            log.info("jd_http_insufficient_using_browser", url=url, reason=str(exc)[:80])
            try:
                return await self._fetch_text_browser(url)
            except JDFetchError:
                raise
            except Exception as browser_exc:
                log.warning("jd_browser_render_failed", url=url, error=str(browser_exc))
                raise exc from browser_exc

    async def _fetch_text_browser(self, url: str) -> str:
        """Render the page in a real browser and extract its text."""
        async with self._browser.new_page() as page:
            await page.goto(url, wait_until="domcontentloaded")
            # SPA boards paint their content after hydration
            await page.wait_for_timeout(settings.jd_render_wait_ms)
            html = await page.content()

        text = self._clean_html(html)
        if len(text.strip()) < 200:
            raise JDFetchError(
                f"Job page returned too little text ({len(text.strip())} chars) even "
                f"after rendering in a browser. It may require a login, or the URL "
                f"may not be a job posting. {_ATS_HINT}"
            )
        log.info("jd_fetched_via_browser", url=url, chars=len(text))
        return text

    async def _fetch_text_http(self, url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 403:
                raise JDFetchError(
                    f"Job page blocked the request (403 Forbidden). "
                    f"This site likely requires a real browser or blocks bots. {_ATS_HINT}"
                ) from exc
            raise JDFetchError(
                f"Job page returned HTTP {code}. Check the URL and try again."
            ) from exc
        except httpx.RequestError as exc:
            raise JDFetchError(
                f"Could not reach the job page: {exc}. Check the URL and your network."
            ) from exc

        text = self._clean_html(response.text)
        if len(text.strip()) < 200:
            raise JDFetchError(
                f"Job page returned too little text ({len(text.strip())} chars). "
                f"The page likely requires JavaScript. {_ATS_HINT}"
            )
        return text

    def _clean_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)

    async def _extract_structured(self, jd_text: str) -> dict:
        truncated = jd_text[:8000]

        response = await self._client.messages.create(
            model=settings.extraction_model,
            max_tokens=512,
            system=_EXTRACT_SYSTEM,
            output_config={
                "format": {"type": "json_schema", "schema": _EXTRACT_SCHEMA}
            },
            messages=[{
                "role": "user",
                "content": f"Job description:\n{truncated}",
            }],
        )
        self.tracker.add(settings.extraction_model, response, stage="jd_extraction")
        raw = _strip_code_fences(response.content[0].text)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.warning("jd_extraction_non_json", raw_preview=raw[:200])
            # Claude returned a conversational reply instead of JSON — page content was
            # probably too thin. Return empty structure; fit scorer will score 0.
            return {"title": None, "company": None, "keywords": []}
