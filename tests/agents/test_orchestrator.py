from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.exceptions import FitThresholdError
from backend.agents.schemas import JDResult, TailoringResult

_PROFILE = {
    "name": "John Gacheru",
    "skills": ["python", "fastapi"],
    "fit_threshold": 50,
}

_JD = JDResult(
    url="https://boards.greenhouse.io/acme/jobs/1",
    title="Senior Engineer",
    company="Acme",
    raw_jd_text="x" * 300,
    keywords=["python", "fastapi"],
    ats_type="greenhouse",
)

_TAILORING = TailoringResult(cover_letter="Dear team...", bullets=["Did things"])

_FIELDS = [
    {"ref": i, "tag": "input", "input_type": "text", "label": f"Field {i}",
     "required": False, "value": "", "options": [], "visible": True}
    for i in range(4)
]


def _make_orchestrator():
    from backend.agents.orchestrator import Orchestrator

    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    browser = MagicMock()

    @asynccontextmanager
    async def new_page():
        yield page

    browser.new_page = new_page

    orch = Orchestrator(MagicMock(), MagicMock(), browser)
    orch.jd_miner.fetch = AsyncMock(return_value=_JD)
    orch.tailoring.generate_tailoring = AsyncMock(return_value=_TAILORING)
    orch.vision_loop.run = AsyncMock(return_value=[])
    orch.vision_loop.abort_reason = None
    return orch, page


@pytest.mark.asyncio
async def test_fit_gate_blocks_before_tailoring_and_browser():
    orch, page = _make_orchestrator()
    low_fit_profile = {**_PROFILE, "skills": ["cobol"], "fit_threshold": 70}

    with pytest.raises(FitThresholdError):
        await orch.run("https://boards.greenhouse.io/acme/jobs/1", low_fit_profile, "r1")

    orch.tailoring.generate_tailoring.assert_not_awaited()
    page.goto.assert_not_awaited()


@pytest.mark.asyncio
async def test_dom_tier_success():
    orch, page = _make_orchestrator()
    dom_steps = [{"step_number": 0, "action": "type", "success": True, "tier": "dom"}]

    with patch("backend.agents.orchestrator.serialize_form", AsyncMock(return_value=_FIELDS)), \
         patch("backend.agents.orchestrator.fetch_question_schema", AsyncMock(return_value=None)), \
         patch("backend.agents.orchestrator.map_fields", AsyncMock(return_value=[{"ref": 0}])), \
         patch("backend.agents.orchestrator.fill_fields", AsyncMock(return_value=(dom_steps, 4, 0))):
        result = await orch.run("https://boards.greenhouse.io/acme/jobs/1", _PROFILE, "r2")

    page.goto.assert_awaited_once()
    assert result["tier"] == "dom"
    assert result["steps"] == dom_steps
    assert result["cover_letter"] == "Dear team..."
    assert "total_cost_usd" in result
    assert "token_usage" in result
    orch.vision_loop.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_dom_failure_falls_back_to_vision():
    orch, _ = _make_orchestrator()
    dom_steps = [{"step_number": 0, "action": "type", "success": False}]

    with patch("backend.agents.orchestrator.serialize_form", AsyncMock(return_value=_FIELDS)), \
         patch("backend.agents.orchestrator.fetch_question_schema", AsyncMock(return_value=None)), \
         patch("backend.agents.orchestrator.map_fields", AsyncMock(return_value=[{"ref": 0}])), \
         patch("backend.agents.orchestrator.fill_fields", AsyncMock(return_value=(dom_steps, 4, 3))):
        result = await orch.run("https://boards.greenhouse.io/acme/jobs/1", _PROFILE, "r3")

    # 3/4 fields failed verification — vision loop takes over
    orch.vision_loop.run.assert_awaited_once()
    assert result["tier"] == "vision"


@pytest.mark.asyncio
async def test_too_few_fields_falls_back_to_vision():
    orch, _ = _make_orchestrator()

    with patch("backend.agents.orchestrator.serialize_form", AsyncMock(return_value=[])), \
         patch("backend.agents.orchestrator.map_fields", AsyncMock()) as mapper:
        result = await orch.run("https://boards.greenhouse.io/acme/jobs/1", _PROFILE, "r4")

    mapper.assert_not_awaited()  # no mapping call wasted on an unreadable page
    assert result["tier"] == "vision"


@pytest.mark.asyncio
async def test_profile_can_opt_out_of_hybrid():
    orch, _ = _make_orchestrator()
    profile = {**_PROFILE, "hybrid_fill": False}

    with patch("backend.agents.orchestrator.serialize_form", AsyncMock()) as serialize:
        result = await orch.run("https://boards.greenhouse.io/acme/jobs/1", profile, "r5")

    serialize.assert_not_awaited()
    assert result["tier"] == "vision"


@pytest.mark.asyncio
async def test_vision_budget_abort_surfaces_in_result():
    orch, _ = _make_orchestrator()
    orch.vision_loop.abort_reason = "token_budget_exceeded"
    profile = {**_PROFILE, "hybrid_fill": False}

    result = await orch.run("https://boards.greenhouse.io/acme/jobs/1", profile, "r6")

    assert result["abort_reason"] == "token_budget_exceeded"
