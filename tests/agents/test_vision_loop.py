import pytest

from backend.agents.vision_loop.perceive import (
    build_perceive_prompt,
    encode_screenshot,
    parse_action_response,
)


def test_build_perceive_prompt_contains_task():
    prompt = build_perceive_prompt("fill form", ["name"], "John, Python dev")
    assert "fill form" in prompt
    assert "1280x800" in prompt


def test_encode_screenshot_structure():
    result = encode_screenshot(b"fake_png_bytes")
    assert result["type"] == "image"
    assert result["source"]["type"] == "base64"
    assert result["source"]["media_type"] == "image/png"


def test_parse_action_response_valid():
    raw = '{"action": "click", "x": 100, "y": 200, "value": "", "field_name": "submit", "reasoning": "Submit button visible", "confidence": 0.95, "done": false}'
    action = parse_action_response(raw)
    assert action["action"] == "click"
    assert action["confidence"] == 0.95


def test_parse_action_response_missing_keys():
    raw = '{"action": "click"}'
    with pytest.raises(ValueError, match="Missing required keys"):
        parse_action_response(raw)


def test_parse_action_response_invalid_action():
    raw = '{"action": "hover", "reasoning": "r", "confidence": 0.9, "done": false}'
    with pytest.raises(ValueError, match="Unknown action"):
        parse_action_response(raw)
