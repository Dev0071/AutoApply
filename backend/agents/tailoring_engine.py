from __future__ import annotations

import json
import re

import anthropic
import structlog

from backend.agents.schemas import JDResult, TailoringResult

log = structlog.get_logger()

_COVER_LETTER_SYSTEM = (
    "You are an expert career coach who writes tailored, concise cover letters. "
    "Mirror the job description's language naturally. "
    "Do not invent experience not in the candidate profile. "
    "Output plain text only — no markdown, no headers."
)

_COVER_LETTER_USER = (
    "Write a 3-paragraph cover letter for this role.\n\n"
    "Candidate profile:\n{profile_text}\n\n"
    "Role:\n"
    "Title: {title}\n"
    "Company: {company}\n"
    "Key requirements: {keywords}"
)

_BULLETS_SYSTEM = (
    "You are an expert resume writer. "
    "Rewrite experience bullets to mirror the job description's language. "
    "Output ONLY a JSON array of strings — no preamble, no markdown fences."
)

_BULLETS_USER = (
    "Rewrite these resume bullets to match this job's language.\n\n"
    "JD keywords: {keywords}\n\n"
    "Original bullets:\n{bullets}"
)


class TailoringError(Exception):
    pass


def _strip_code_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)


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
    def __init__(self, anthropic_client: anthropic.AsyncAnthropic):
        self.client = anthropic_client

    async def generate_cover_letter(
        self, profile: dict, jd: dict | JDResult
    ) -> TailoringResult:
        profile_text = _format_profile(profile)
        prompt = _COVER_LETTER_USER.format(
            profile_text=profile_text,
            title=_jd_field(jd, "title"),
            company=_jd_field(jd, "company"),
            keywords=_jd_keywords(jd),
        )

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": _COVER_LETTER_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Candidate profile:\n{profile_text}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )

        log.info("cover_letter_generated", company=_jd_field(jd, "company"))
        return TailoringResult(cover_letter=response.content[0].text, bullets=[])

    async def rewrite_bullets(
        self, profile: dict, jd: dict | JDResult
    ) -> TailoringResult:
        original_bullets = _extract_bullets(profile)
        prompt = _BULLETS_USER.format(
            keywords=_jd_keywords(jd),
            bullets=original_bullets or "(no bullets provided)",
        )

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": _BULLETS_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Original bullets:\n{original_bullets}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )

        raw = _strip_code_fences(response.content[0].text)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TailoringError(
                f"Failed to parse rewritten bullets: {exc} | Raw: {raw}"
            ) from exc

        if not isinstance(parsed, list):
            raise TailoringError(
                f"Expected a JSON array of bullets, got: {type(parsed).__name__}"
            )

        log.info("bullets_rewritten", count=len(parsed), company=_jd_field(jd, "company"))
        return TailoringResult(cover_letter="", bullets=parsed)
