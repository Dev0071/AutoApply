from __future__ import annotations

from playwright.async_api import Page


async def verify_action(page: Page, field_name: str, expected_value: str) -> bool:
    """
    Post-action DOM verification only — NEVER used for targeting.
    Tries multiple locator strategies; returns False (non-blocking) if all fail.
    """
    strategies = [
        page.get_by_label(field_name, exact=False),
        page.get_by_placeholder(field_name, exact=False),
        page.get_by_role("textbox", name=field_name),
    ]
    for locator in strategies:
        try:
            actual = await locator.first.input_value(timeout=500)
            return actual.strip() == expected_value.strip()
        except Exception:
            continue
    return False
