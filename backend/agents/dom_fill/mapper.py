"""Map serialized form fields to candidate answers in a single cheap call.

The whole form is mapped at once — one Haiku-class call instead of one
vision call per field. Sensitive (EEO/demographic) questions are never
answered: the model is instructed to skip them, and a deterministic keyword
net catches anything the model misses.
"""
from __future__ import annotations

import json
import re

import anthropic
import structlog

from backend.agents.schemas import JDResult, TailoringResult
from backend.agents.usage import UsageTracker
from backend.config import settings

log = structlog.get_logger()

# Deterministic belt-and-braces guard: any label matching these is skipped
# regardless of what the mapping model returned.
_SENSITIVE_PATTERNS = re.compile(
    r"race|ethnic|gender|veteran|disabilit|sexual orientation|lgbtq|"
    r"date of birth|religion|national origin|criminal|marital",
    re.IGNORECASE,
)

MAPPING_SYSTEM = (
    "You map a job application form's fields to a candidate's answers.\n"
    "You receive the form's fields (each with a numeric ref) and the candidate's "
    "profile, tailored cover letter, and role context.\n\n"
    "Rules:\n"
    "- Answer ONLY from the provided candidate data. Never invent facts.\n"
    "- For select fields, value must be one of the listed options, verbatim.\n"
    "- For a cover letter textarea, use the provided cover letter text.\n"
    "- Set skip=true with skip_reason='sensitive' for ANY demographic/EEO "
    "question (race, ethnicity, gender, veteran status, disability, sexual "
    "orientation, age, religion, and similar). These require the candidate's "
    "own answer.\n"
    "- Set skip=true with skip_reason='needs_user_input' for file uploads, "
    "questions you lack data for, or legal attestations.\n"
    "- confidence reflects how certain you are the value is correct for that field."
)

_MAPPING_SCHEMA = {
    "type": "object",
    "properties": {
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ref": {"type": "integer"},
                    "value": {"type": "string"},
                    "confidence": {"type": "number"},
                    "skip": {"type": "boolean"},
                    "skip_reason": {"type": "string"},
                },
                "required": ["ref", "value", "confidence", "skip", "skip_reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["mappings"],
    "additionalProperties": False,
}


def is_sensitive_label(label: str) -> bool:
    return bool(_SENSITIVE_PATTERNS.search(label or ""))


def build_mapping_prompt(
    fields: list[dict],
    profile: dict,
    tailoring: TailoringResult | None,
    jd: JDResult | dict | None,
    extra_questions: list[dict] | None = None,
) -> str:
    compact_fields = [
        {
            "ref": f["ref"],
            "type": f"{f['tag']}:{f['input_type']}" if f["input_type"] else f["tag"],
            "label": f["label"],
            "required": f["required"],
            "options": f["options"],
        }
        for f in fields
    ]
    parts = [
        f"Form fields:\n{json.dumps(compact_fields, indent=1)}",
        f"Candidate profile:\n{json.dumps(profile, default=str, indent=1)}",
    ]
    if tailoring and tailoring.cover_letter:
        parts.append(f"Tailored cover letter:\n{tailoring.cover_letter}")
    if jd is not None:
        title = jd.title if isinstance(jd, JDResult) else jd.get("title")
        company = jd.company if isinstance(jd, JDResult) else jd.get("company")
        parts.append(f"Role: {title} at {company}")
    if extra_questions:
        parts.append(
            "Authoritative question schema from the ATS API:\n"
            + json.dumps(extra_questions, indent=1)
        )
    return "\n\n".join(parts)


async def map_fields(
    client: anthropic.AsyncAnthropic,
    fields: list[dict],
    profile: dict,
    tailoring: TailoringResult | None = None,
    jd: JDResult | dict | None = None,
    extra_questions: list[dict] | None = None,
    tracker: UsageTracker | None = None,
    model: str | None = None,
) -> list[dict]:
    model = model or settings.mapping_model
    prompt = build_mapping_prompt(fields, profile, tailoring, jd, extra_questions)

    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=MAPPING_SYSTEM,
        output_config={
            "format": {"type": "json_schema", "schema": _MAPPING_SCHEMA}
        },
        messages=[{"role": "user", "content": prompt}],
    )
    if tracker is not None:
        tracker.add(model, response, stage="dom_mapping")

    raw = response.content[0].text
    mappings = json.loads(raw)["mappings"]

    # Deterministic sensitive-label guard on top of the model's own skips
    labels_by_ref = {f["ref"]: f["label"] for f in fields}
    for m in mappings:
        if not m["skip"] and is_sensitive_label(labels_by_ref.get(m["ref"], "")):
            m["skip"] = True
            m["skip_reason"] = "sensitive"
            log.warning("mapper_sensitive_override", ref=m["ref"])

    return mappings
