"""
Integration tests against a real Playwright browser + static Greenhouse-clone form.

Covers both navigation tiers:
- Tier 2 (DOM fill): serialize → map (scripted) → deterministic fill → verify
- Tier 3 (vision loop): batched screenshot → perceive (scripted) → act → verify

Claude responses are scripted so no tokens are spent; coordinates/refs come
from the live page so they are always correct. Doubles as the cost/steps
baseline eval — each test asserts the API-call budget for the run.

Run with: pytest -m integration
Skip in CI if Playwright browsers not installed.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
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


def _make_scripted_client(payloads: list[dict]) -> MagicMock:
    """Mock Anthropic client returning pre-scripted JSON payloads in sequence,
    each carrying realistic token usage so cost aggregation is exercised."""
    responses = []
    for payload in payloads:
        block = MagicMock()
        block.text = json.dumps(payload)
        msg = MagicMock()
        msg.content = [block]
        msg.usage = SimpleNamespace(
            input_tokens=800,
            output_tokens=150,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )
        responses.append(msg)
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=responses)
    return client


def _make_storage() -> MagicMock:
    storage = MagicMock()
    storage.upload_screenshot = AsyncMock(return_value="s3://autoapply/runs/test/step_000.jpg")
    return storage


def _center(bb: dict) -> tuple[int, int]:
    return int(bb["x"] + bb["width"] / 2), int(bb["y"] + bb["height"] / 2)


def _type(x: int, y: int, value: str, field: str) -> dict:
    return {"action": "type", "x": x, "y": y, "value": value,
            "field_name": field, "confidence": 0.97}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_vision_loop_fills_greenhouse_form_in_two_calls():
    """The batched vision loop fills a 4-field form with exactly 2 perceive
    calls (one batch, one done-check) — the baseline the cost work targets."""
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

        fx, fy = _center(await page.locator("#first_name").bounding_box())
        lx, ly = _center(await page.locator("#last_name").bounding_box())
        ex, ey = _center(await page.locator("#email").bounding_box())
        px, py = _center(await page.locator("#phone").bounding_box())

        scripted = [
            {
                "actions": [
                    _type(fx, fy, "John", "first_name"),
                    _type(lx, ly, "Gacheru", "last_name"),
                    _type(ex, ey, "john@example.com", "email"),
                    _type(px, py, "+1-555-123-4567", "phone"),
                ],
                "reasoning": "Filling all visible fields",
                "done": False,
            },
            {"actions": [], "reasoning": "All fields filled", "done": True},
        ]

        client = _make_scripted_client(scripted)
        loop = VisionActionLoop(client, _make_storage(), wait_ms=0, inter_action_wait_ms=0)
        steps = await loop.run(page, task="fill greenhouse form", profile=_PROFILE, run_id="test-001")

        # Eval baseline: 4 fields, 2 API calls, 5 audit steps (4 actions + done)
        assert client.messages.create.await_count == 2
        assert len(steps) == 5
        assert steps[-1].action["done"] is True

        for step in steps:
            assert step.screenshot_url.startswith("s3://")

        # Typed fields verified against the real DOM by the loop itself
        assert all(s.success for s in steps)

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

    scripted = [{
        "actions": [{"action": "error", "confidence": 0.1}],
        "reasoning": "Cannot locate application form on page",
        "done": False,
    }]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        await page.goto(f"file://{FORM_PATH.resolve()}")

        loop = VisionActionLoop(
            _make_scripted_client(scripted), _make_storage(), wait_ms=0, inter_action_wait_ms=0
        )

        with pytest.raises(AgentError, match="Cannot locate application form"):
            await loop.run(page, task="fill form", profile=_PROFILE, run_id="test-002")

        await browser.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_orchestrator_end_to_end_local_browser():
    """Full pipeline against a real browser in local mode: JD mine → fit gate →
    tailoring → DOM tier fill → cost aggregation. Every Claude call is scripted,
    so this spends no tokens and no Browserbase minutes."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright not installed")

    from backend.agents.orchestrator import Orchestrator
    from backend.services.browser import BrowserService

    form_url = f"file://{FORM_PATH.resolve()}"

    jd_payload = {
        "title": "Software Engineer",
        "company": "Acme Corp",
        "keywords": ["python", "fastapi", "postgresql"],
    }
    tailoring_payload = {
        "cover_letter": "Dear Acme Corp team, ...",
        "bullets": ["Built REST APIs serving 10M requests/day"],
    }
    # refs follow DOM order of `input, select, textarea` on the fixture form
    mapping_payload = {"mappings": [
        {"ref": 0, "value": "John", "confidence": 0.99, "skip": False, "skip_reason": ""},
        {"ref": 1, "value": "Gacheru", "confidence": 0.99, "skip": False, "skip_reason": ""},
        {"ref": 2, "value": "john@example.com", "confidence": 0.99, "skip": False, "skip_reason": ""},
        {"ref": 3, "value": "+1-555-123-4567", "confidence": 0.99, "skip": False, "skip_reason": ""},
        {"ref": 4, "value": "Nairobi, Kenya", "confidence": 0.95, "skip": False, "skip_reason": ""},
    ]}

    client = _make_scripted_client([jd_payload, tailoring_payload, mapping_payload])
    orch = Orchestrator(client, _make_storage(), BrowserService(mode="local"))
    # The fixture is a local file, so serve the JD text directly rather than
    # exercising the HTTP fetch path (covered in test_jd_miner.py).
    orch.jd_miner._fetch_text = AsyncMock(
        return_value="Software Engineer at Acme Corp. Python FastAPI PostgreSQL. " * 10
    )

    result = await orch.run(form_url, {**_PROFILE, "fit_threshold": 50}, "e2e-001")

    assert result["tier"] == "dom"
    assert result["fit_score"] >= 50
    assert result["cover_letter"].startswith("Dear Acme Corp")
    assert result["bullets"] == ["Built REST APIs serving 10M requests/day"]
    assert all(s["success"] for s in result["steps"])

    # Cost is measured across all three stages of the run
    stages = {c["stage"] for c in result["token_usage"]["calls"]}
    assert stages == {"jd_extraction", "tailoring", "dom_mapping"}
    assert result["total_cost_usd"] > 0
    # The whole application costs well under a cent on the DOM tier
    assert result["total_cost_usd"] < 0.01


@pytest.mark.integration
@pytest.mark.asyncio
async def test_screenshot_compression_shrinks_a_real_screenshot():
    """Audit screenshots are stored as WebP at full resolution. Measured
    against a real rendered form, not a synthetic image — flat synthetic
    fills compress unrealistically well as PNG and would hide the win."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("playwright not installed")

    from backend.services.storage import compress_screenshot

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        await page.goto(f"file://{FORM_PATH.resolve()}")
        png = await page.screenshot(type="png", full_page=False)
        await browser.close()

    body, ext = compress_screenshot(png)
    assert ext == "webp"
    assert len(body) < len(png) / 2  # measured ~2.8x on this fixture

    from PIL import Image
    import io
    assert Image.open(io.BytesIO(body)).size == (1280, 800)  # no downscaling


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dom_fill_fills_greenhouse_form_in_one_call():
    """Tier 2: serialize the real form, map with a single (scripted) call,
    fill deterministically, and verify by DOM readback — no vision tokens."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("playwright not installed")

    from backend.agents.dom_fill.executor import fill_fields
    from backend.agents.dom_fill.mapper import map_fields
    from backend.agents.dom_fill.serialize import serialize_form

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        await page.goto(f"file://{FORM_PATH.resolve()}")

        fields = await serialize_form(page)
        labels = {f["label"]: f["ref"] for f in fields}
        assert "First Name *" in " ".join(labels) or any("First" in l for l in labels)
        assert len(fields) >= 5

        def ref_for(fragment: str) -> int:
            return next(f["ref"] for f in fields if fragment.lower() in f["label"].lower())

        scripted_mappings = {"mappings": [
            {"ref": ref_for("First"), "value": "John", "confidence": 0.99, "skip": False, "skip_reason": ""},
            {"ref": ref_for("Last"), "value": "Gacheru", "confidence": 0.99, "skip": False, "skip_reason": ""},
            {"ref": ref_for("Email"), "value": "john@example.com", "confidence": 0.99, "skip": False, "skip_reason": ""},
            {"ref": ref_for("Phone"), "value": "+1-555-123-4567", "confidence": 0.99, "skip": False, "skip_reason": ""},
        ]}
        client = _make_scripted_client([scripted_mappings])

        mappings = await map_fields(client, fields, _PROFILE)
        steps, attempted, failed = await fill_fields(
            page, fields, mappings, _make_storage(), "test-003", inter_wait_ms=0
        )

        # Eval baseline: whole form, exactly ONE model call, zero failures
        assert client.messages.create.await_count == 1
        assert attempted == 4
        assert failed == 0
        assert all(s["success"] for s in steps)
        assert all(s["tier"] == "dom" for s in steps)

        assert await page.input_value("#first_name") == "John"
        assert await page.input_value("#last_name") == "Gacheru"
        assert await page.input_value("#email") == "john@example.com"
        assert await page.input_value("#phone") == "+1-555-123-4567"

        await browser.close()
