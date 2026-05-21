import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agents.tailoring_engine import TailoringEngine, TailoringError
from backend.agents.schemas import TailoringResult

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


def _make_client(response_text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = response_text
    message = MagicMock()
    message.content = [content_block]
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=message)
    return client


# ---------------------------------------------------------------------------
# generate_cover_letter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_cover_letter_returns_tailoring_result():
    client = _make_client("Dear Hiring Manager,\n\nI am excited...")
    engine = TailoringEngine(client)
    result = await engine.generate_cover_letter(_PROFILE, _JD)

    assert isinstance(result, TailoringResult)
    assert len(result.cover_letter) > 0
    assert result.bullets == []


@pytest.mark.asyncio
async def test_generate_cover_letter_passes_profile_and_jd_to_claude():
    client = _make_client("cover letter text")
    engine = TailoringEngine(client)
    await engine.generate_cover_letter(_PROFILE, _JD)

    call_kwargs = client.messages.create.call_args.kwargs
    content = call_kwargs["messages"][0]["content"]
    combined = " ".join(
        block["text"] for block in content if block.get("type") == "text"
    )
    assert "John Gacheru" in combined
    assert "Acme Corp" in combined


@pytest.mark.asyncio
async def test_generate_cover_letter_missing_profile_fields():
    client = _make_client("cover letter text")
    engine = TailoringEngine(client)
    # Should not raise — missing fields default gracefully
    result = await engine.generate_cover_letter({}, _JD)
    assert isinstance(result, TailoringResult)


# ---------------------------------------------------------------------------
# rewrite_bullets
# ---------------------------------------------------------------------------

_BULLETS_JSON = json.dumps([
    "Architected FastAPI services handling 10M+ daily requests",
    "Led async migration reducing p99 latency by 40%",
])


@pytest.mark.asyncio
async def test_rewrite_bullets_returns_tailoring_result():
    client = _make_client(_BULLETS_JSON)
    engine = TailoringEngine(client)
    result = await engine.rewrite_bullets(_PROFILE, _JD)

    assert isinstance(result, TailoringResult)
    assert len(result.bullets) == 2
    assert result.cover_letter == ""


@pytest.mark.asyncio
async def test_rewrite_bullets_handles_code_block_wrapping():
    """Claude sometimes wraps JSON arrays in ```json ... ```."""
    wrapped = f"```json\n{_BULLETS_JSON}\n```"
    client = _make_client(wrapped)
    engine = TailoringEngine(client)
    result = await engine.rewrite_bullets(_PROFILE, _JD)
    assert len(result.bullets) == 2


@pytest.mark.asyncio
async def test_rewrite_bullets_raises_tailoring_error_on_bad_json():
    client = _make_client("Sorry, I cannot do that.")
    engine = TailoringEngine(client)
    with pytest.raises(TailoringError, match="Failed to parse rewritten bullets"):
        await engine.rewrite_bullets(_PROFILE, _JD)


@pytest.mark.asyncio
async def test_rewrite_bullets_raises_tailoring_error_when_not_list():
    client = _make_client('{"bullet": "single item"}')
    engine = TailoringEngine(client)
    with pytest.raises(TailoringError, match="Expected a JSON array"):
        await engine.rewrite_bullets(_PROFILE, _JD)


@pytest.mark.asyncio
async def test_rewrite_bullets_empty_experience():
    client = _make_client(_BULLETS_JSON)
    engine = TailoringEngine(client)
    result = await engine.rewrite_bullets({"experience": {}}, _JD)
    assert isinstance(result, TailoringResult)
