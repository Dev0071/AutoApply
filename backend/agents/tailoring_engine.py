import anthropic
import structlog

log = structlog.get_logger()

COVER_LETTER_PROMPT = """
Write a concise, tailored cover letter for the following job.

Job title: {title}
Company: {company}
Job description keywords: {keywords}

Candidate profile:
Name: {name}
Skills: {skills}
Experience summary: {experience}

Requirements:
- 3 short paragraphs max
- Mirror the JD's language naturally
- Do not invent experience not in the profile
- Output plain text only, no markdown
"""

BULLETS_PROMPT = """
Rewrite the following resume experience bullets to mirror this job description's language.

JD keywords: {keywords}
Original bullets:
{bullets}

Output a JSON array of rewritten bullet strings only.
"""


class TailoringEngine:
    def __init__(self, anthropic_client: anthropic.AsyncAnthropic):
        self.client = anthropic_client

    async def generate_cover_letter(self, profile: dict, jd: dict) -> str:
        prompt = COVER_LETTER_PROMPT.format(
            title=jd.get("title", ""),
            company=jd.get("company", ""),
            keywords=", ".join(jd.get("keywords", [])),
            name=profile.get("name", ""),
            skills=", ".join(profile.get("skills", [])),
            experience=profile.get("experience", ""),
        )
        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        log.info("cover_letter_generated", company=jd.get("company"))
        return response.content[0].text

    async def rewrite_bullets(self, profile: dict, jd: dict) -> list[str]:
        import json

        original = "\n".join(
            f"- {b}" for exp in profile.get("experience", {}).values()
            for b in (exp if isinstance(exp, list) else [exp])
        )
        prompt = BULLETS_PROMPT.format(
            keywords=", ".join(jd.get("keywords", [])),
            bullets=original,
        )
        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        log.info("bullets_rewritten", company=jd.get("company"))
        return json.loads(response.content[0].text)
