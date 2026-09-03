"""Tier 1: prefetch the authoritative question schema for Greenhouse postings.

Greenhouse's public Job Board API returns the exact application questions for
a posting — knowing the fields before opening a browser makes the fill fully
deterministic. Submission still goes through the browser form; this is
planning data only. Best-effort: any failure returns None and the pipeline
proceeds without it.
"""
from __future__ import annotations

import re

import httpx
import structlog

log = structlog.get_logger()

_GREENHOUSE_URL_RE = re.compile(
    r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_app\?for=)?([A-Za-z0-9_-]+)(?:/jobs/|&token=)(\d+)"
)

_API_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}?questions=true"


def parse_greenhouse_url(url: str) -> tuple[str, str] | None:
    match = _GREENHOUSE_URL_RE.search(url)
    if not match:
        return None
    return match.group(1), match.group(2)


async def fetch_question_schema(url: str, timeout: int = 10) -> list[dict] | None:
    parsed = parse_greenhouse_url(url)
    if parsed is None:
        return None
    board, job_id = parsed

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(_API_URL.format(board=board, job_id=job_id))
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        log.info("greenhouse_schema_unavailable", url=url, error=str(exc))
        return None

    questions = []
    for q in data.get("questions", []):
        field_type = ""
        if q.get("fields"):
            field_type = q["fields"][0].get("type", "")
        questions.append({
            "label": q.get("label", ""),
            "required": bool(q.get("required")),
            "type": field_type,
        })

    log.info("greenhouse_schema_fetched", url=url, questions=len(questions))
    return questions or None
