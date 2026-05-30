from __future__ import annotations

import json
import re

import anthropic
import httpx
import structlog
from bs4 import BeautifulSoup

from backend.agents.schemas import JDResult

log = structlog.get_logger()

_ATS_PATTERNS: list[tuple[str, str]] = [
    (r"greenhouse\.io", "greenhouse"),
    (r"lever\.co", "lever"),
    (r"myworkdayjobs\.com", "workday"),
    (r"ashbyhq\.com", "ashby"),
    (r"jobvite\.com", "jobvite"),
    (r"icims\.com", "icims"),
]

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
    for pattern, name in _ATS_PATTERNS:
        if re.search(pattern, url):
            return name
    return "unknown"


def _strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers Claude sometimes adds despite instructions."""
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)


class JDMiner:
    def __init__(self, anthropic_client: anthropic.AsyncAnthropic, timeout: int = 15):
        self._client = anthropic_client
        self._timeout = timeout

    async def fetch(self, url: str) -> JDResult:
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

        return JDResult(
            url=url,
            title=extracted.get("title"),
            company=extracted.get("company"),
            raw_jd_text=raw_text,
            keywords=extracted.get("keywords", []),
            ats_type=ats_type,
        )

    async def _fetch_text(self, url: str) -> str:
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
        text = self._clean_html(response.text)
        if len(text.strip()) < 200:
            raise ValueError(
                f"Job page returned too little text ({len(text.strip())} chars). "
                "The page likely requires JavaScript — try a direct ATS link "
                "(e.g. boards.greenhouse.io/… or jobs.lever.co/…) rather than a company careers page."
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
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=[{
                "type": "text",
                "text": _EXTRACT_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": f"Job description:\n{truncated}",
            }],
        )
        raw = _strip_code_fences(response.content[0].text)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.warning("jd_extraction_non_json", raw_preview=raw[:200])
            # Claude returned a conversational reply instead of JSON — page content was
            # probably too thin. Return empty structure; fit scorer will score 0.
            return {"title": None, "company": None, "keywords": []}
