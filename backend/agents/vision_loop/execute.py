from playwright.async_api import Page


async def execute_action(page: Page, action: dict) -> None:
    act = action["action"]
    x = action.get("x")
    y = action.get("y")
    value = action.get("value", "")

    if act == "click":
        await page.mouse.click(x, y)
    elif act == "type":
        await page.mouse.click(x, y)
        await page.keyboard.type(value)
    elif act == "select":
        await page.mouse.click(x, y)
    elif act == "scroll":
        await page.mouse.wheel(0, 300)
    elif act in ("done", "error"):
        pass
