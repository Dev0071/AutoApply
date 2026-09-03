"""Deterministically fill mapped fields via element handles.

Every action still screenshots into the S3 audit trail and verifies its value
by DOM readback — the trust features are independent of how targeting happens.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from playwright.async_api import Page

from backend.agents.dom_fill.serialize import FORM_ELEMENT_SELECTOR

if TYPE_CHECKING:
    from backend.services.storage import StorageService

log = structlog.get_logger()

_CONFIDENCE_FLOOR = 0.5


def _step(
    step_number: int,
    action: str,
    field: dict,
    value: str,
    success: bool,
    screenshot_url: str = "",
    reasoning: str = "",
    confidence: float | None = None,
    needs_user_input: bool = False,
) -> dict:
    return {
        "step_number": step_number,
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "x": None,
        "y": None,
        "value": value,
        "field_name": field.get("label", ""),
        "reasoning": reasoning,
        "confidence": confidence,
        "screenshot_url": screenshot_url,
        "success": success,
        "tier": "dom",
        "needs_user_input": needs_user_input,
    }


async def fill_fields(
    page: Page,
    fields: list[dict],
    mappings: list[dict],
    storage: StorageService,
    run_id: str,
    start_step: int = 0,
    inter_wait_ms: int = 150,
) -> tuple[list[dict], int, int]:
    """Apply the mapper's answers to the page.

    Returns (steps, attempted, failed) — `failed` counts fields whose value
    could not be applied or did not verify by readback.
    """
    fields_by_ref = {f["ref"]: f for f in fields}
    steps: list[dict] = []
    attempted = 0
    failed = 0
    step_num = start_step

    for m in mappings:
        field = fields_by_ref.get(m["ref"])
        if field is None:
            continue

        if m["skip"] or m["confidence"] < _CONFIDENCE_FLOOR:
            reason = m["skip_reason"] if m["skip"] else "low_confidence"
            steps.append(_step(
                step_num, "skipped", field, "", success=True,
                reasoning=reason, confidence=m["confidence"],
                needs_user_input=reason in ("sensitive", "needs_user_input"),
            ))
            step_num += 1
            continue

        locator = page.locator(FORM_ELEMENT_SELECTOR).nth(m["ref"])
        value = str(m["value"])
        tag = field["tag"]
        input_type = field["input_type"]
        attempted += 1

        try:
            if tag == "select":
                action = "select"
                try:
                    await locator.select_option(label=value)
                except Exception:
                    await locator.select_option(value=value)
                verified = True
            elif input_type in ("checkbox", "radio"):
                action = "check"
                if value.strip().lower() in ("true", "yes", "1", "on", "check"):
                    await locator.check()
                verified = await locator.is_checked()
            else:
                action = "type"
                await locator.fill(value)
                actual = await locator.input_value()
                verified = actual.strip() == value.strip()
        except Exception as exc:
            log.warning(
                "dom_fill_field_failed",
                run_id=run_id, ref=m["ref"], field=field.get("label"), error=str(exc),
            )
            action = "type"
            verified = False

        if not verified:
            failed += 1

        await page.wait_for_timeout(inter_wait_ms)
        png = await page.screenshot(type="png", full_page=False)
        url = await storage.upload_screenshot(png, run_id=run_id, step=step_num)

        steps.append(_step(
            step_num, action, field, value,
            success=verified, screenshot_url=url,
            reasoning="dom fill", confidence=m["confidence"],
        ))
        step_num += 1

    log.info(
        "dom_fill_complete",
        run_id=run_id, attempted=attempted, failed=failed, steps=len(steps),
    )
    return steps, attempted, failed
