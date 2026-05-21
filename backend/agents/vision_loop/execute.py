from __future__ import annotations

from playwright.async_api import Page

from backend.agents.exceptions import AgentError


async def execute_action(page: Page, action: dict) -> None:
    act: str = action["action"]
    x: int = action.get("x") or 0
    y: int = action.get("y") or 0
    value: str = str(action.get("value") or "")

    if act == "click":
        await page.mouse.click(x, y)

    elif act == "type":
        # Triple-click selects any existing text before typing the new value
        await page.mouse.click(x, y, click_count=3)
        await page.keyboard.type(value)

    elif act == "select":
        # Vision-first: click to open dropdown; Claude selects option on next step
        await page.mouse.click(x, y)

    elif act == "scroll":
        delta = int(value) if value.lstrip("-").isdigit() else 300
        await page.mouse.wheel(x, delta)

    elif act in ("done", "error"):
        pass  # terminal actions — no browser interaction

    else:
        raise AgentError(f"Unknown action type: {act!r}")
