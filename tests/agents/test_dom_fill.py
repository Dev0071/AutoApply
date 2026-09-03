from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.dom_fill.executor import fill_fields
from backend.agents.dom_fill.greenhouse import fetch_question_schema, parse_greenhouse_url
from backend.agents.dom_fill.mapper import (
    build_mapping_prompt,
    is_sensitive_label,
    map_fields,
)
from backend.agents.schemas import TailoringResult


# ---------------------------------------------------------------------------
# mapper — sensitive label guard (pure)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", [
    "Race/Ethnicity",
    "Gender identity",
    "Are you a protected veteran?",
    "Disability status",
    "Sexual Orientation",
    "Date of Birth",
])
def test_sensitive_labels_detected(label):
    assert is_sensitive_label(label) is True


@pytest.mark.parametrize("label", ["First Name", "Email Address", "LinkedIn URL", ""])
def test_normal_labels_not_sensitive(label):
    assert is_sensitive_label(label) is False


# ---------------------------------------------------------------------------
# mapper — prompt building (pure)
# ---------------------------------------------------------------------------

_FIELDS = [
    {"ref": 0, "tag": "input", "input_type": "text", "label": "First Name",
     "required": True, "value": "", "options": [], "visible": True},
    {"ref": 1, "tag": "select", "input_type": "select-one", "label": "Country",
     "required": False, "value": "", "options": ["Kenya", "USA"], "visible": True},
]

_PROFILE = {"name": "John Gacheru", "email": "john@example.com", "skills": ["python"]}


def test_build_mapping_prompt_includes_fields_and_profile():
    prompt = build_mapping_prompt(_FIELDS, _PROFILE, None, None)
    assert "First Name" in prompt
    assert "John Gacheru" in prompt
    assert "Kenya" in prompt


def test_build_mapping_prompt_includes_cover_letter_and_schema():
    tailoring = TailoringResult(cover_letter="Dear team...", bullets=[])
    questions = [{"label": "Why us?", "required": True, "type": "textarea"}]
    prompt = build_mapping_prompt(_FIELDS, _PROFILE, tailoring, None, questions)
    assert "Dear team..." in prompt
    assert "Why us?" in prompt


# ---------------------------------------------------------------------------
# mapper — Claude call
# ---------------------------------------------------------------------------

def _make_client(mappings: list[dict]) -> MagicMock:
    block = MagicMock()
    block.text = json.dumps({"mappings": mappings})
    msg = MagicMock()
    msg.content = [block]
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=msg)
    return client


@pytest.mark.asyncio
async def test_map_fields_returns_mappings():
    client = _make_client([
        {"ref": 0, "value": "John", "confidence": 0.98, "skip": False, "skip_reason": ""},
    ])
    mappings = await map_fields(client, _FIELDS, _PROFILE)
    assert mappings[0]["value"] == "John"
    assert client.messages.create.call_args.kwargs["output_config"]["format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_map_fields_overrides_sensitive_label_the_model_missed():
    fields = [{"ref": 0, "tag": "select", "input_type": "select-one",
               "label": "Gender identity", "required": False, "value": "",
               "options": ["Male", "Female"], "visible": True}]
    # Model wrongly tried to answer a demographic question
    client = _make_client([
        {"ref": 0, "value": "Male", "confidence": 0.9, "skip": False, "skip_reason": ""},
    ])
    mappings = await map_fields(client, fields, _PROFILE)
    assert mappings[0]["skip"] is True
    assert mappings[0]["skip_reason"] == "sensitive"


# ---------------------------------------------------------------------------
# executor — mocked page
# ---------------------------------------------------------------------------

def _make_exec_page() -> tuple[MagicMock, MagicMock]:
    locator = MagicMock()
    locator.fill = AsyncMock()
    locator.input_value = AsyncMock(return_value="John")
    locator.select_option = AsyncMock()
    locator.check = AsyncMock()
    locator.is_checked = AsyncMock(return_value=True)

    nth = MagicMock(return_value=locator)
    page = MagicMock()
    page.locator = MagicMock(return_value=MagicMock(nth=nth))
    page.wait_for_timeout = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"\x89PNG")
    return page, locator


def _make_storage() -> MagicMock:
    storage = MagicMock()
    storage.upload_screenshot = AsyncMock(return_value="s3://bucket/runs/r/step_000.jpg")
    return storage


@pytest.mark.asyncio
async def test_fill_fields_fills_and_verifies():
    page, locator = _make_exec_page()
    fields = [_FIELDS[0]]
    mappings = [{"ref": 0, "value": "John", "confidence": 0.98, "skip": False, "skip_reason": ""}]

    steps, attempted, failed = await fill_fields(page, fields, mappings, _make_storage(), "r")

    locator.fill.assert_awaited_once_with("John")
    assert attempted == 1
    assert failed == 0
    assert steps[0]["success"] is True
    assert steps[0]["tier"] == "dom"
    assert steps[0]["screenshot_url"].startswith("s3://")


@pytest.mark.asyncio
async def test_fill_fields_counts_verification_failure():
    page, locator = _make_exec_page()
    locator.input_value = AsyncMock(return_value="wrong value")
    mappings = [{"ref": 0, "value": "John", "confidence": 0.98, "skip": False, "skip_reason": ""}]

    steps, attempted, failed = await fill_fields(page, [_FIELDS[0]], mappings, _make_storage(), "r")

    assert failed == 1
    assert steps[0]["success"] is False


@pytest.mark.asyncio
async def test_fill_fields_skips_sensitive_and_flags_user_input():
    page, locator = _make_exec_page()
    fields = [{"ref": 0, "tag": "select", "input_type": "select-one",
               "label": "Race/Ethnicity", "required": False, "value": "",
               "options": [], "visible": True}]
    mappings = [{"ref": 0, "value": "", "confidence": 0.0, "skip": True, "skip_reason": "sensitive"}]

    steps, attempted, failed = await fill_fields(page, fields, mappings, _make_storage(), "r")

    locator.fill.assert_not_awaited()
    locator.select_option.assert_not_awaited()
    assert attempted == 0
    assert steps[0]["action"] == "skipped"
    assert steps[0]["needs_user_input"] is True


@pytest.mark.asyncio
async def test_fill_fields_skips_low_confidence():
    page, locator = _make_exec_page()
    mappings = [{"ref": 0, "value": "guess", "confidence": 0.2, "skip": False, "skip_reason": ""}]

    steps, attempted, _ = await fill_fields(page, [_FIELDS[0]], mappings, _make_storage(), "r")

    locator.fill.assert_not_awaited()
    assert attempted == 0
    assert steps[0]["reasoning"] == "low_confidence"


@pytest.mark.asyncio
async def test_fill_fields_select_uses_option_label():
    page, locator = _make_exec_page()
    mappings = [{"ref": 1, "value": "Kenya", "confidence": 0.97, "skip": False, "skip_reason": ""}]

    steps, attempted, failed = await fill_fields(page, [_FIELDS[1]], mappings, _make_storage(), "r")

    locator.select_option.assert_awaited_once_with(label="Kenya")
    assert failed == 0
    assert steps[0]["action"] == "select"


@pytest.mark.asyncio
async def test_fill_fields_element_error_counts_as_failure():
    page, locator = _make_exec_page()
    locator.fill = AsyncMock(side_effect=Exception("detached element"))
    mappings = [{"ref": 0, "value": "John", "confidence": 0.98, "skip": False, "skip_reason": ""}]

    steps, attempted, failed = await fill_fields(page, [_FIELDS[0]], mappings, _make_storage(), "r")

    assert attempted == 1
    assert failed == 1
    assert steps[0]["success"] is False


# ---------------------------------------------------------------------------
# greenhouse — Tier 1 schema prefetch
# ---------------------------------------------------------------------------

def test_parse_greenhouse_url_boards():
    assert parse_greenhouse_url("https://boards.greenhouse.io/acme/jobs/12345") == ("acme", "12345")


def test_parse_greenhouse_url_job_boards():
    assert parse_greenhouse_url("https://job-boards.greenhouse.io/acme/jobs/999") == ("acme", "999")


def test_parse_greenhouse_url_non_greenhouse():
    assert parse_greenhouse_url("https://jobs.lever.co/acme/abc") is None


@pytest.mark.asyncio
async def test_fetch_question_schema_maps_questions():
    payload = {"questions": [
        {"label": "First Name", "required": True, "fields": [{"type": "input_text"}]},
        {"label": "Resume", "required": True, "fields": [{"type": "input_file"}]},
    ]}
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=payload)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        questions = await fetch_question_schema("https://boards.greenhouse.io/acme/jobs/1")

    assert questions == [
        {"label": "First Name", "required": True, "type": "input_text"},
        {"label": "Resume", "required": True, "type": "input_file"},
    ]


@pytest.mark.asyncio
async def test_fetch_question_schema_best_effort_on_failure():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=Exception("network down"))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        assert await fetch_question_schema("https://boards.greenhouse.io/acme/jobs/1") is None


@pytest.mark.asyncio
async def test_fetch_question_schema_none_for_non_greenhouse():
    assert await fetch_question_schema("https://jobs.lever.co/acme/abc") is None
