from playwright.async_api import Page

VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 800


async def capture_screenshot(page: Page) -> bytes:
    return await page.screenshot(type="png", full_page=False)
