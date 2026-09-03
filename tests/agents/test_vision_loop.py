from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.exceptions import AgentError, MaxStepsExceededError, StuckLoopError
from backend.agents.vision_loop.execute import execute_action
from backend.agents.vision_loop.perceive import (
    PERCEIVE_SYSTEM,
    build_perceive_prompt,
    encode_screenshot,
    parse_action_response,
    parse_batch_response,
)
from backend.agents.vision_loop.verify import verify_action


# ---------------------------------------------------------------------------
# perceive.py — pure functions
# ---------------------------------------------------------------------------

def test_perceive_system_states_viewport():
    assert "1280x800" in PERCEIVE_SYSTEM


def test_build_perceive_prompt_contains_task():
    prompt = build_perceive_prompt("fill form", ["name"], "John, Python dev")
    assert "fill form" in prompt


def test_build_perceive_prompt_includes_filled_fields():
    prompt = build_perceive_prompt("fill form", ["email", "phone"], "Jane")
    assert "email" in prompt
    assert "phone" in prompt


def test_encode_screenshot_structure():
    result = encode_screenshot(b"fake_png_bytes")
    assert result["type"] == "image"
    assert result["source"]["type"] == "base64"
    assert result["source"]["media_type"] == "image/png"
    assert isinstance(result["source"]["data"], str)


def test_encode_screenshot_roundtrip():
    import base64
    data = b"\x89PNG\r\n\x1a\n"
    result = encode_screenshot(data)
    decoded = base64.b64decode(result["source"]["data"])
    assert decoded == data


def test_parse_action_response_valid():
    raw = json.dumps({
        "action": "click", "x": 100, "y": 200, "value": "",
        "field_name": "submit", "reasoning": "Submit button visible",
        "confidence": 0.95, "done": False,
    })
    action = parse_action_response(raw)
    assert action["action"] == "click"
    assert action["confidence"] == 0.95


def test_parse_action_response_missing_keys():
    with pytest.raises(ValueError, match="Missing required keys"):
        parse_action_response('{"action": "click"}')


def test_parse_action_response_invalid_action():
    raw = json.dumps({"action": "hover", "reasoning": "r", "confidence": 0.9, "done": False})
    with pytest.raises(ValueError, match="Unknown action"):
        parse_action_response(raw)


def test_parse_batch_response_valid():
    raw = json.dumps({
        "actions": [
            {"action": "type", "x": 1, "y": 2, "value": "a", "field_name": "f", "confidence": 0.9},
            {"action": "click", "x": 3, "y": 4, "value": "", "field_name": "g", "confidence": 0.8},
        ],
        "reasoning": "fill visible fields",
        "done": False,
    })
    batch = parse_batch_response(raw)
    assert len(batch["actions"]) == 2
    assert batch["done"] is False


def test_parse_batch_response_done_with_empty_actions():
    raw = json.dumps({"actions": [], "reasoning": "complete", "done": True})
    batch = parse_batch_response(raw)
    assert batch["done"] is True
    assert batch["actions"] == []


def test_parse_batch_response_missing_envelope_keys():
    with pytest.raises(ValueError, match="Missing required keys"):
        parse_batch_response('{"actions": []}')


def test_parse_batch_response_unknown_action():
    raw = json.dumps({
        "actions": [{"action": "hover", "confidence": 0.9}],
        "reasoning": "r", "done": False,
    })
    with pytest.raises(ValueError, match="Unknown action"):
        parse_batch_response(raw)


def test_parse_batch_response_action_missing_confidence():
    raw = json.dumps({
        "actions": [{"action": "click", "x": 1, "y": 2}],
        "reasoning": "r", "done": False,
    })
    with pytest.raises(ValueError, match="missing confidence"):
        parse_batch_response(raw)


def test_parse_batch_response_actions_not_list():
    raw = json.dumps({"actions": "click", "reasoning": "r", "done": False})
    with pytest.raises(ValueError, match="must be a list"):
        parse_batch_response(raw)


def test_parse_batch_response_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        parse_batch_response("not json")


# ---------------------------------------------------------------------------
# execute.py
# ---------------------------------------------------------------------------

def _make_page() -> MagicMock:
    page = MagicMock()
    page.mouse = MagicMock()
    page.mouse.click = AsyncMock()
    page.mouse.wheel = AsyncMock()
    page.keyboard = MagicMock()
    page.keyboard.type = AsyncMock()
    page.keyboard.press = AsyncMock()
    return page


@pytest.mark.asyncio
async def test_execute_click_calls_mouse_click():
    page = _make_page()
    await execute_action(page, {"action": "click", "x": 100, "y": 200, "value": ""})
    page.mouse.click.assert_awaited_once_with(100, 200)


@pytest.mark.asyncio
async def test_execute_type_triple_clicks_then_types():
    page = _make_page()
    await execute_action(page, {"action": "type", "x": 640, "y": 300, "value": "hello"})
    page.mouse.click.assert_awaited_once_with(640, 300, click_count=3)
    page.keyboard.type.assert_awaited_once_with("hello")


@pytest.mark.asyncio
async def test_execute_scroll_uses_value_as_delta():
    page = _make_page()
    await execute_action(page, {"action": "scroll", "x": 0, "y": 0, "value": "600"})
    page.mouse.wheel.assert_awaited_once_with(0, 600)


@pytest.mark.asyncio
async def test_execute_unknown_action_raises():
    page = _make_page()
    with pytest.raises(AgentError, match="Unknown action"):
        await execute_action(page, {"action": "hover", "x": 0, "y": 0, "value": ""})


# ---------------------------------------------------------------------------
# verify.py
# ---------------------------------------------------------------------------

def _make_locator(value: str) -> MagicMock:
    loc = MagicMock()
    loc.first = MagicMock()
    loc.first.input_value = AsyncMock(return_value=value)
    return loc


def _make_missing_locator() -> MagicMock:
    loc = MagicMock()
    loc.first = MagicMock()
    loc.first.input_value = AsyncMock(side_effect=Exception("no such element"))
    return loc


def _verify_page(locator: MagicMock) -> MagicMock:
    page = MagicMock()
    page.get_by_label = MagicMock(return_value=locator)
    page.get_by_placeholder = MagicMock(return_value=locator)
    page.locator = MagicMock(return_value=locator)
    return page


@pytest.mark.asyncio
async def test_verify_returns_true_on_match():
    assert await verify_action(_verify_page(_make_locator("John")), "first_name", "John") is True


@pytest.mark.asyncio
async def test_verify_returns_false_on_mismatch():
    assert await verify_action(_verify_page(_make_locator("Jane")), "first_name", "John") is False


@pytest.mark.asyncio
async def test_verify_returns_none_when_field_not_found():
    """Not locatable is not the same as wrong — None keeps the loop from
    escalating to the expensive model over an unverifiable field."""
    page = _verify_page(_make_missing_locator())
    assert await verify_action(page, "nonexistent", "value") is None


@pytest.mark.asyncio
async def test_verify_matches_snake_case_field_against_spaced_label():
    """Claude says 'first_name'; the DOM label reads 'First Name *'."""
    page = MagicMock()
    matching = _make_locator("John")
    missing = _make_missing_locator()
    page.get_by_label = MagicMock(side_effect=lambda key, **kw: matching if key == "First Name" else missing)
    page.get_by_placeholder = MagicMock(return_value=missing)
    page.locator = MagicMock(return_value=missing)

    assert await verify_action(page, "first_name", "John") is True


@pytest.mark.asyncio
async def test_verify_returns_none_for_empty_field_name():
    assert await verify_action(MagicMock(), "", "value") is None


# ---------------------------------------------------------------------------
# loop.py — unit tests with mocked page and Anthropic client
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _verify_passes(monkeypatch):
    """DOM verification is best-effort and can't run against a MagicMock page —
    default it to success; tests that exercise escalation override it."""
    monkeypatch.setattr(
        "backend.agents.vision_loop.loop.verify_action",
        AsyncMock(return_value=True),
    )


def _usage(input_tokens: int = 1500, output_tokens: int = 200) -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )


def _batch(actions: list[dict], reasoning: str = "batch reasoning", done: bool = False) -> dict:
    return {"actions": actions, "reasoning": reasoning, "done": done}


def _type_action(field: str, value: str, x: int = 640, y: int = 200, confidence: float = 0.95) -> dict:
    return {"action": "type", "x": x, "y": y, "value": value,
            "field_name": field, "confidence": confidence}


def _make_claude_client(batches: list[dict]) -> MagicMock:
    """Mock Anthropic client that yields batched perceive responses in sequence."""
    responses = []
    for batch in batches:
        block = MagicMock()
        block.text = json.dumps(batch)
        msg = MagicMock()
        msg.content = [block]
        msg.usage = _usage()
        responses.append(msg)
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=responses)
    return client


def _make_storage() -> MagicMock:
    storage = MagicMock()
    storage.upload_screenshot = AsyncMock(return_value="s3://bucket/runs/test/step_000.jpg")
    return storage


def _make_loop_page(unique_screens: bool = True) -> MagicMock:
    page = _make_page()
    if unique_screens:
        counter = iter(range(10_000))
        page.screenshot = AsyncMock(
            side_effect=lambda **kw: b"\x89PNG" + str(next(counter)).encode()
        )
    else:
        page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n")
    page.wait_for_timeout = AsyncMock()
    return page


_PROFILE = {
    "name": "John Gacheru",
    "skills": ["python", "fastapi"],
    "location": "Nairobi",
}


@pytest.mark.asyncio
async def test_loop_executes_batch_then_done():
    from backend.agents.vision_loop.loop import VisionActionLoop

    batches = [
        _batch([_type_action("first_name", "John"), _type_action("last_name", "Gacheru", y=260)]),
        _batch([], reasoning="all fields filled", done=True),
    ]
    loop = VisionActionLoop(_make_claude_client(batches), _make_storage())
    steps = await loop.run(_make_loop_page(), task="fill form", profile=_PROFILE, run_id="run-001")

    # 2 action steps + 1 terminal done step
    assert len(steps) == 3
    assert steps[-1].action["done"] is True
    assert [s.action["action"] for s in steps[:2]] == ["type", "type"]
    assert loop.abort_reason is None


@pytest.mark.asyncio
async def test_loop_one_perceive_call_per_batch():
    from backend.agents.vision_loop.loop import VisionActionLoop

    batches = [
        _batch([_type_action(f"field_{i}", "v", y=200 + i * 40) for i in range(5)]),
        _batch([], done=True),
    ]
    client = _make_claude_client(batches)
    loop = VisionActionLoop(client, _make_storage())
    steps = await loop.run(_make_loop_page(), task="t", profile=_PROFILE, run_id="r")

    # 5 fields filled with only 2 API calls — the whole point of batching
    assert client.messages.create.await_count == 2
    assert len(steps) == 6


@pytest.mark.asyncio
async def test_loop_raises_on_error_action():
    from backend.agents.vision_loop.loop import VisionActionLoop

    batches = [_batch(
        [{"action": "error", "confidence": 0.1}],
        reasoning="Cannot find form",
    )]
    loop = VisionActionLoop(_make_claude_client(batches), _make_storage())

    with pytest.raises(AgentError, match="Cannot find form"):
        await loop.run(_make_loop_page(), task="t", profile=_PROFILE, run_id="r")


@pytest.mark.asyncio
async def test_loop_raises_on_max_steps_exceeded():
    from backend.agents.vision_loop.loop import VisionActionLoop

    # Different action each round so stuck detection doesn't fire first
    batches = [_batch([_type_action("f", "v", x=i + 1)]) for i in range(5)]
    loop = VisionActionLoop(_make_claude_client(batches), _make_storage(), max_steps=5)

    with pytest.raises(MaxStepsExceededError):
        await loop.run(_make_loop_page(), task="t", profile=_PROFILE, run_id="r")


@pytest.mark.asyncio
async def test_loop_stuck_on_identical_screens():
    from backend.agents.vision_loop.loop import VisionActionLoop

    batches = [_batch([_type_action("f", "v", x=i + 1)]) for i in range(10)]
    client = _make_claude_client(batches)
    page = _make_loop_page(unique_screens=False)  # screen never changes
    loop = VisionActionLoop(client, _make_storage())

    with pytest.raises(StuckLoopError, match="Screen unchanged"):
        await loop.run(page, task="t", profile=_PROFILE, run_id="r")

    # The unchanged-screen check runs BEFORE perceive — the detecting round is free
    assert client.messages.create.await_count == 2


@pytest.mark.asyncio
async def test_loop_stuck_on_identical_batches():
    from backend.agents.vision_loop.loop import VisionActionLoop

    same = _batch([_type_action("f", "v")])
    loop = VisionActionLoop(_make_claude_client([same] * 5), _make_storage())

    with pytest.raises(StuckLoopError, match="Identical action batch"):
        await loop.run(_make_loop_page(), task="t", profile=_PROFILE, run_id="r")


@pytest.mark.asyncio
async def test_loop_stuck_on_sustained_low_confidence():
    from backend.agents.vision_loop.loop import VisionActionLoop

    batches = [
        _batch([_type_action("f", "v", x=1, confidence=0.1)]),
        _batch([_type_action("g", "w", x=2, confidence=0.2)]),
    ]
    loop = VisionActionLoop(_make_claude_client(batches), _make_storage())

    with pytest.raises(StuckLoopError, match="Confidence below"):
        await loop.run(_make_loop_page(), task="t", profile=_PROFILE, run_id="r")


@pytest.mark.asyncio
async def test_loop_aborts_on_token_budget():
    from backend.agents.vision_loop.loop import VisionActionLoop

    batches = [
        _batch([_type_action("f", "v")]),
        _batch([], done=True),  # never reached
    ]
    loop = VisionActionLoop(
        _make_claude_client(batches), _make_storage(), token_budget=100
    )
    steps = await loop.run(_make_loop_page(), task="t", profile=_PROFILE, run_id="r")

    assert loop.abort_reason == "token_budget_exceeded"
    assert len(steps) == 1  # partial steps preserved for review


@pytest.mark.asyncio
async def test_loop_records_usage_and_cost():
    from backend.agents.vision_loop.loop import VisionActionLoop

    batches = [_batch([_type_action("f", "v")]), _batch([], done=True)]
    loop = VisionActionLoop(_make_claude_client(batches), _make_storage())
    steps = await loop.run(_make_loop_page(), task="t", profile=_PROFILE, run_id="r")

    assert len(loop.tracker.entries) == 2
    assert loop.tracker.total_cost_usd > 0
    assert steps[0].usage is not None
    assert steps[0].usage["input_tokens"] == 1500
    assert steps[0].to_dict()["usage"]["cost_usd"] > 0


@pytest.mark.asyncio
async def test_loop_escalates_model_on_verification_failure():
    from backend.agents.vision_loop.loop import VisionActionLoop

    batches = [
        _batch([_type_action("f", "v", x=1)]),
        _batch([_type_action("g", "w", x=2)]),
        _batch([], done=True),
    ]
    client = _make_claude_client(batches)
    loop = VisionActionLoop(
        client, _make_storage(), model="cheap-model", fallback_model="expensive-model"
    )

    with patch(
        "backend.agents.vision_loop.loop.verify_action", AsyncMock(return_value=False)
    ):
        await loop.run(_make_loop_page(), task="t", profile=_PROFILE, run_id="r")

    models = [c.kwargs["model"] for c in client.messages.create.call_args_list]
    assert models[0] == "cheap-model"
    assert models[1] == "expensive-model"  # escalated after failed verification


@pytest.mark.asyncio
async def test_loop_resets_steps_between_runs():
    from backend.agents.vision_loop.loop import VisionActionLoop

    done = _batch([], done=True)
    loop = VisionActionLoop(_make_claude_client([done, done]), _make_storage())
    page = _make_loop_page()

    steps1 = await loop.run(page, task="t", profile=_PROFILE, run_id="run-1")
    steps2 = await loop.run(page, task="t", profile=_PROFILE, run_id="run-2")

    assert len(steps1) == 1
    assert len(steps2) == 1  # not 2 — steps reset between runs


@pytest.mark.asyncio
async def test_loop_step_log_serialization():
    from backend.agents.vision_loop.loop import VisionActionLoop

    batches = [
        _batch([_type_action("email", "jane@example.com")], reasoning="Email field visible"),
        _batch([], done=True),
    ]
    loop = VisionActionLoop(_make_claude_client(batches), _make_storage())
    steps = await loop.run(_make_loop_page(), task="t", profile=_PROFILE, run_id="r")

    d = steps[0].to_dict()
    assert d["step_number"] == 0
    assert d["action"] == "type"
    assert d["value"] == "jane@example.com"
    assert d["field_name"] == "email"
    assert d["reasoning"] == "Email field visible"
    assert d["screenshot_url"].startswith("s3://")
    assert d["success"] is True
    assert "timestamp" in d
