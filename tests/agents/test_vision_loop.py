from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from backend.agents.exceptions import AgentError, MaxStepsExceededError
from backend.agents.vision_loop.execute import execute_action
from backend.agents.vision_loop.perceive import (
    build_perceive_prompt,
    encode_screenshot,
    parse_action_response,
)
from backend.agents.vision_loop.verify import verify_action


# ---------------------------------------------------------------------------
# perceive.py — pure functions
# ---------------------------------------------------------------------------

def test_build_perceive_prompt_contains_task():
    prompt = build_perceive_prompt("fill form", ["name"], "John, Python dev")
    assert "fill form" in prompt
    assert "1280x800" in prompt


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


def test_parse_action_response_all_actions():
    for act in ("click", "type", "select", "scroll", "done", "error"):
        raw = json.dumps({"action": act, "reasoning": "r", "confidence": 0.9, "done": False})
        result = parse_action_response(raw)
        assert result["action"] == act


def test_parse_action_response_missing_keys():
    with pytest.raises(ValueError, match="Missing required keys"):
        parse_action_response('{"action": "click"}')


def test_parse_action_response_invalid_action():
    raw = json.dumps({"action": "hover", "reasoning": "r", "confidence": 0.9, "done": False})
    with pytest.raises(ValueError, match="Unknown action"):
        parse_action_response(raw)


def test_parse_action_response_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        parse_action_response("not json")


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
async def test_execute_select_clicks_coordinates():
    page = _make_page()
    await execute_action(page, {"action": "select", "x": 400, "y": 250, "value": "Full-time"})
    page.mouse.click.assert_awaited_once_with(400, 250)


@pytest.mark.asyncio
async def test_execute_scroll_uses_default_delta():
    page = _make_page()
    await execute_action(page, {"action": "scroll", "x": 640, "y": 400, "value": ""})
    page.mouse.wheel.assert_awaited_once_with(640, 300)


@pytest.mark.asyncio
async def test_execute_scroll_uses_value_as_delta():
    page = _make_page()
    await execute_action(page, {"action": "scroll", "x": 0, "y": 0, "value": "600"})
    page.mouse.wheel.assert_awaited_once_with(0, 600)


@pytest.mark.asyncio
async def test_execute_done_is_noop():
    page = _make_page()
    await execute_action(page, {"action": "done", "x": 0, "y": 0, "value": ""})
    page.mouse.click.assert_not_awaited()
    page.keyboard.type.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_error_is_noop():
    page = _make_page()
    await execute_action(page, {"action": "error", "x": 0, "y": 0, "value": ""})
    page.mouse.click.assert_not_awaited()


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


@pytest.mark.asyncio
async def test_verify_returns_true_on_match():
    page = MagicMock()
    page.get_by_label = MagicMock(return_value=_make_locator("John"))
    result = await verify_action(page, "first_name", "John")
    assert result is True


@pytest.mark.asyncio
async def test_verify_returns_false_on_mismatch():
    page = MagicMock()
    page.get_by_label = MagicMock(return_value=_make_locator("Jane"))
    result = await verify_action(page, "first_name", "John")
    assert result is False


@pytest.mark.asyncio
async def test_verify_returns_false_when_locator_throws():
    loc = MagicMock()
    loc.first = MagicMock()
    loc.first.input_value = AsyncMock(side_effect=Exception("element not found"))
    page = MagicMock()
    page.get_by_label = MagicMock(return_value=loc)
    page.get_by_placeholder = MagicMock(return_value=loc)
    page.get_by_role = MagicMock(return_value=loc)
    result = await verify_action(page, "nonexistent", "value")
    assert result is False


# ---------------------------------------------------------------------------
# loop.py — unit tests with mocked page and Anthropic client
# ---------------------------------------------------------------------------

def _make_claude_client(actions: list[dict]) -> MagicMock:
    """Returns a mock Anthropic client that yields `actions` in sequence."""
    responses = []
    for action in actions:
        block = MagicMock()
        block.text = json.dumps(action)
        msg = MagicMock()
        msg.content = [block]
        responses.append(msg)

    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=responses)
    return client


def _make_storage() -> MagicMock:
    storage = MagicMock()
    storage.upload_screenshot = AsyncMock(return_value="s3://bucket/runs/test/step_000.png")
    return storage


def _make_loop_page() -> MagicMock:
    page = MagicMock()
    page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n")
    page.mouse = MagicMock()
    page.mouse.click = AsyncMock()
    page.mouse.wheel = AsyncMock()
    page.keyboard = MagicMock()
    page.keyboard.type = AsyncMock()
    page.keyboard.press = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    return page


_PROFILE = {
    "name": "John Gacheru",
    "skills": ["python", "fastapi"],
    "location": "Nairobi",
}


@pytest.mark.asyncio
async def test_loop_returns_steps_on_done():
    from backend.agents.vision_loop.loop import VisionActionLoop

    actions = [
        {"action": "type", "x": 640, "y": 200, "value": "John", "field_name": "first_name",
         "reasoning": "First name field", "confidence": 0.97, "done": False},
        {"action": "done", "x": 0, "y": 0, "value": "", "field_name": "",
         "reasoning": "All fields filled", "confidence": 1.0, "done": True},
    ]
    client = _make_claude_client(actions)
    storage = _make_storage()
    page = _make_loop_page()

    loop = VisionActionLoop(client, storage)
    steps = await loop.run(page, task="fill form", profile=_PROFILE, run_id="run-001")

    assert len(steps) == 2
    assert steps[-1].action["done"] is True


@pytest.mark.asyncio
async def test_loop_waits_after_each_action():
    from backend.agents.vision_loop.loop import VisionActionLoop

    actions = [
        {"action": "click", "x": 100, "y": 200, "value": "", "field_name": "btn",
         "reasoning": "r", "confidence": 0.9, "done": False},
        {"action": "done", "x": 0, "y": 0, "value": "", "field_name": "",
         "reasoning": "done", "confidence": 1.0, "done": True},
    ]
    page = _make_loop_page()
    loop = VisionActionLoop(_make_claude_client(actions), _make_storage())
    await loop.run(page, task="t", profile=_PROFILE, run_id="r")

    # wait_for_timeout called once (after the click, not after done)
    assert page.wait_for_timeout.await_count == 1
    page.wait_for_timeout.assert_awaited_with(800)


@pytest.mark.asyncio
async def test_loop_raises_on_error_action():
    from backend.agents.vision_loop.loop import VisionActionLoop

    actions = [
        {"action": "error", "x": 0, "y": 0, "value": "", "field_name": "",
         "reasoning": "Cannot find form", "confidence": 0.1, "done": False},
    ]
    page = _make_loop_page()
    loop = VisionActionLoop(_make_claude_client(actions), _make_storage())

    with pytest.raises(AgentError, match="Cannot find form"):
        await loop.run(page, task="t", profile=_PROFILE, run_id="r")


@pytest.mark.asyncio
async def test_loop_raises_on_max_steps_exceeded():
    from backend.agents.vision_loop.loop import VisionActionLoop

    never_done = {"action": "click", "x": 1, "y": 1, "value": "", "field_name": "btn",
                  "reasoning": "keep clicking", "confidence": 0.5, "done": False}
    actions = [never_done] * 5

    page = _make_loop_page()
    loop = VisionActionLoop(_make_claude_client(actions), _make_storage(), max_steps=5)

    with pytest.raises(MaxStepsExceededError):
        await loop.run(page, task="t", profile=_PROFILE, run_id="r")


@pytest.mark.asyncio
async def test_loop_resets_steps_between_runs():
    from backend.agents.vision_loop.loop import VisionActionLoop

    done_action = {"action": "done", "x": 0, "y": 0, "value": "", "field_name": "",
                   "reasoning": "done", "confidence": 1.0, "done": True}
    page = _make_loop_page()
    loop = VisionActionLoop(_make_claude_client([done_action, done_action]), _make_storage())

    steps1 = await loop.run(page, task="t", profile=_PROFILE, run_id="run-1")
    steps2 = await loop.run(page, task="t", profile=_PROFILE, run_id="run-2")

    assert len(steps1) == 1
    assert len(steps2) == 1  # not 2 — steps reset between runs


@pytest.mark.asyncio
async def test_loop_step_log_serialization():
    from backend.agents.vision_loop.loop import VisionActionLoop

    actions = [
        {"action": "type", "x": 640, "y": 200, "value": "Jane", "field_name": "email",
         "reasoning": "Email field visible", "confidence": 0.98, "done": False},
        {"action": "done", "x": 0, "y": 0, "value": "", "field_name": "",
         "reasoning": "done", "confidence": 1.0, "done": True},
    ]
    page = _make_loop_page()
    loop = VisionActionLoop(_make_claude_client(actions), _make_storage())
    steps = await loop.run(page, task="t", profile=_PROFILE, run_id="r")

    d = steps[0].to_dict()
    assert d["step_number"] == 0
    assert d["action"] == "type"
    assert d["value"] == "Jane"
    assert d["field_name"] == "email"
    assert d["confidence"] == 0.98
    assert d["screenshot_url"].startswith("s3://")
    assert d["success"] is True
    assert "timestamp" in d
