"""
Integration test: vision loop against a real Playwright browser + static Greenhouse-clone form.
Claude responses are scripted using actual element bounding boxes so coordinates are always correct.

Run with: pytest -m integration
Skip in CI if Playwright browsers not installed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

FORM_PATH = Path(__file__).parent.parent / "static" / "greenhouse_form.html"

_PROFILE = {
    "name": "John Gacheru",
    "skills": ["python", "fastapi", "postgresql"],
    "location": "Nairobi, Kenya",
    "experience": {
        "backend_eng": ["Built REST APIs serving 10M requests/day"]
    },
}


def _make_scripted_client(actions: list[dict]) -> MagicMock:
    """Mock Anthropic client that returns pre-scripted actions in sequence."""
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
    storage.upload_screenshot = AsyncMock(return_value="s3://autoapply/runs/test/step_000.png")
    return storage


def _center(bb: dict) -> tuple[int, int]:
    return int(bb["x"] + bb["width"] / 2), int(bb["y"] + bb["height"] / 2)


def _action(act: str, x: int, y: int, value: str, field: str, done: bool = False) -> dict:
    return {
        "action": act, "x": x, "y": y, "value": value, "field_name": field,
        "reasoning": f"Filling {field}", "confidence": 0.97, "done": done,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vision_loop_fills_greenhouse_form():
    """
    Loads the static Greenhouse-clone form in a real headless Chromium browser,
    runs the VisionActionLoop with scripted Claude responses built from actual
    element bounding boxes, and asserts all fields were filled correctly.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("playwright not installed")

    from backend.agents.vision_loop.loop import VisionActionLoop

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = await context.new_page()

        await page.goto(f"file://{FORM_PATH.resolve()}")

        # Resolve actual element centers so mock coordinates are guaranteed to hit
        bb_first = await page.locator("#first_name").bounding_box()
        bb_last = await page.locator("#last_name").bounding_box()
        bb_email = await page.locator("#email").bounding_box()
        bb_phone = await page.locator("#phone").bounding_box()

        fx, fy = _center(bb_first)
        lx, ly = _center(bb_last)
        ex, ey = _center(bb_email)
        px, py = _center(bb_phone)

        scripted_actions = [
            _action("type", fx, fy, "John", "first_name"),
            _action("type", lx, ly, "Gacheru", "last_name"),
            _action("type", ex, ey, "john@example.com", "email"),
            _action("type", px, py, "+1-555-123-4567", "phone"),
            _action("done", 0, 0, "", "", done=True),
        ]

        client = _make_scripted_client(scripted_actions)
        storage = _make_storage()

        loop = VisionActionLoop(client, storage, wait_ms=0)  # no wait in tests
        steps = await loop.run(page, task="fill greenhouse form", profile=_PROFILE, run_id="test-001")

        # Loop control assertions
        assert len(steps) == 5
        assert steps[-1].action["done"] is True
        assert steps[-1].action["action"] == "done"

        # All steps logged with screenshot URLs
        for step in steps:
            assert step.screenshot_url.startswith("s3://")
            assert step.success is True

        # Actual DOM state verification
        assert await page.input_value("#first_name") == "John"
        assert await page.input_value("#last_name") == "Gacheru"
        assert await page.input_value("#email") == "john@example.com"
        assert await page.input_value("#phone") == "+1-555-123-4567"

        await browser.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vision_loop_stops_on_error_action():
    """Error action from Claude raises AgentError and halts the loop."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("playwright not installed")

    from backend.agents.exceptions import AgentError
    from backend.agents.vision_loop.loop import VisionActionLoop

    scripted_actions = [
        {"action": "error", "x": 0, "y": 0, "value": "", "field_name": "",
         "reasoning": "Cannot locate application form on page", "confidence": 0.1, "done": False},
    ]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        await page.goto(f"file://{FORM_PATH.resolve()}")

        loop = VisionActionLoop(_make_scripted_client(scripted_actions), _make_storage(), wait_ms=0)

        with pytest.raises(AgentError, match="Cannot locate application form"):
            await loop.run(page, task="fill form", profile=_PROFILE, run_id="test-002")

        await browser.close()
