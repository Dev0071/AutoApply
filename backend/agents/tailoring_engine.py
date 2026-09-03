from __future__ import annotations

import json

import anthropic
import structlog

from backend.agents.schemas import JDResult, TailoringResult
from backend.agents.usage import UsageTracker
from backend.config import settings

log = structlog.get_logger()

_TAILORING_SYSTEM = (
    "You are an expert career coach and resume writer.\n"
    "Given a candidate profile and a role, produce BOTH:\n"
    "1. cover_letter — a tailored, concise 3-paragraph cover letter in plain text "
    "(no markdown, no headers) that mirrors the job description's language naturally.\n"
    "2. bullets — the candidate's experience bullets rewritten to mirror the job's "
    "language.\n"
    "Never invent experience not in the candidate profile."
)

_TAILORING_USER = (
    "Candidate profile:\n{profile_text}\n\n"
    "Role:\n"
    "Title: {title}\n"
    "Company: {company}\n"
    "Key requirements: {keywords}\n\n"
    "Original bullets:\n{bullets}"
)

_TAILORING_SCHEMA = {
    "type": "object",
    "properties": {
        "cover_letter": {"type": "string"},
        "bullets": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["cover_letter", "bullets"],
    "additionalProperties": False,
}


class TailoringError(Exception):
    pass


def _format_profile(profile: dict) -> str:
    lines = [
        f"Name: {profile.get('name', 'N/A')}",
        f"Skills: {', '.join(profile.get('skills', []))}",
        f"Location: {profile.get('location', 'N/A')}",
    ]
    experience = profile.get("experience", {})
    if experience:
        lines.append("Experience:")
        for bullets in experience.values():
            entries = bullets if isinstance(bullets, list) else [bullets]
            for b in entries:
                lines.append(f"  - {b}")
    return "\n".join(lines)


def _extract_bullets(profile: dict) -> str:
    experience = profile.get("experience", {})
    lines = []
    for bullets in experience.values():
        entries = bullets if isinstance(bullets, list) else [bullets]
        lines.extend(f"- {b}" for b in entries)
    return "\n".join(lines)


def _jd_keywords(jd: dict | JDResult) -> str:
    keywords = jd.keywords if isinstance(jd, JDResult) else jd.get("keywords", [])
    return ", ".join(keywords)


def _jd_field(jd: dict | JDResult, field: str) -> str:
    if isinstance(jd, JDResult):
        return getattr(jd, field, "") or ""
    return jd.get(field, "") or ""


class TailoringEngine:
    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic,
        tracker: UsageTracker | None = None,
    ):
        self.client = anthropic_client
        self.tracker = tracker if tracker is not None else UsageTracker()

    async def generate_tailoring(
        self, profile: dict, jd: dict | JDResult
    ) -> TailoringResult:
        """One call produces both the cover letter and the rewritten bullets —
        the profile and JD context are sent once instead of twice."""
        prompt = _TAILORING_USER.format(
            profile_text=_format_profile(profile),
            title=_jd_field(jd, "title"),
            company=_jd_field(jd, "company"),
            keywords=_jd_keywords(jd),
            bullets=_extract_bullets(profile) or "(no bullets provided)",
        )

        response = await self.client.messages.create(
            model=settings.tailoring_model,
            max_tokens=2048,
            system=_TAILORING_SYSTEM,
            output_config={
                "format": {"type": "json_schema", "schema": _TAILORING_SCHEMA}
            },
            messages=[{"role": "user", "content": prompt}],
        )
        self.tracker.add(settings.tailoring_model, response, stage="tailoring")

        raw = next((b.text for b in response.content if getattr(b, "type", "text") == "text"), None)
        if raw is None:
            raw = response.content[0].text
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TailoringError(
                f"Failed to parse tailoring response: {exc} | Raw: {raw[:200]}"
            ) from exc

        if not isinstance(parsed.get("cover_letter"), str) or not isinstance(
            parsed.get("bullets"), list
        ):
            raise TailoringError(f"Tailoring response missing fields: {list(parsed)}")

        log.info(
            "tailoring_generated",
            company=_jd_field(jd, "company"),
            bullet_count=len(parsed["bullets"]),
        )
        return TailoringResult(
            cover_letter=parsed["cover_letter"], bullets=parsed["bullets"]
        )
