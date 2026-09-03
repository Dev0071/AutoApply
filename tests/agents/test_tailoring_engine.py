import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agents.tailoring_engine import TailoringEngine, TailoringError
from backend.agents.schemas import TailoringResult
from backend.agents.usage import UsageTracker

_PROFILE = {
    "name": "John Gacheru",
    "skills": ["python", "fastapi", "postgresql"],
    "experience": {
        "backend_eng": [
            "Built REST APIs serving 10M requests/day",
            "Led migration to async architecture",
        ]
    },
}

_JD = {
    "title": "Senior Backend Engineer",
    "company": "Acme Corp",
    "keywords": ["python", "fastapi", "postgresql"],
}

_TAILORING_JSON = json.dumps({
    "cover_letter": "Dear Hiring Manager,\n\nI am excited...",
    "bullets": [
        "Architected FastAPI services handling 10M+ daily requests",
        "Led async migration reducing p99 latency by 40%",
    ],
})


def _make_client(response_text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = response_text
    message = MagicMock()
    message.content = [content_block]
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=message)
    return client


@pytest.mark.asyncio
async def test_generate_tailoring_returns_both_outputs():
    engine = TailoringEngine(_make_client(_TAILORING_JSON))
    result = await engine.generate_tailoring(_PROFILE, _JD)

    assert isinstance(result, TailoringResult)
    assert result.cover_letter.startswith("Dear Hiring Manager")
    assert len(result.bullets) == 2


@pytest.mark.asyncio
async def test_generate_tailoring_is_a_single_call():
    """Cover letter + bullets in one request — profile and JD sent once."""
    client = _make_client(_TAILORING_JSON)
    engine = TailoringEngine(client)
    await engine.generate_tailoring(_PROFILE, _JD)

    assert client.messages.create.await_count == 1


@pytest.mark.asyncio
async def test_generate_tailoring_passes_profile_and_jd():
    client = _make_client(_TAILORING_JSON)
    engine = TailoringEngine(client)
    await engine.generate_tailoring(_PROFILE, _JD)

    prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "John Gacheru" in prompt
    assert "Acme Corp" in prompt
    assert "Built REST APIs serving 10M requests/day" in prompt


@pytest.mark.asyncio
async def test_generate_tailoring_uses_structured_output():
    client = _make_client(_TAILORING_JSON)
    engine = TailoringEngine(client)
    await engine.generate_tailoring(_PROFILE, _JD)

    output_config = client.messages.create.call_args.kwargs["output_config"]
    assert output_config["format"]["type"] == "json_schema"
    schema_props = output_config["format"]["schema"]["properties"]
    assert set(schema_props) == {"cover_letter", "bullets"}


@pytest.mark.asyncio
async def test_generate_tailoring_records_usage():
    tracker = UsageTracker()
    engine = TailoringEngine(_make_client(_TAILORING_JSON), tracker=tracker)
    await engine.generate_tailoring(_PROFILE, _JD)

    assert len(tracker.entries) == 1
    assert tracker.entries[0]["stage"] == "tailoring"


@pytest.mark.asyncio
async def test_generate_tailoring_missing_profile_fields():
    engine = TailoringEngine(_make_client(_TAILORING_JSON))
    result = await engine.generate_tailoring({}, _JD)
    assert isinstance(result, TailoringResult)


@pytest.mark.asyncio
async def test_generate_tailoring_raises_on_bad_json():
    engine = TailoringEngine(_make_client("Sorry, I cannot do that."))
    with pytest.raises(TailoringError, match="Failed to parse tailoring response"):
        await engine.generate_tailoring(_PROFILE, _JD)


@pytest.mark.asyncio
async def test_generate_tailoring_raises_on_missing_fields():
    engine = TailoringEngine(_make_client('{"cover_letter": "hi"}'))
    with pytest.raises(TailoringError, match="missing fields"):
        await engine.generate_tailoring(_PROFILE, _JD)
