from contextlib import asynccontextmanager

import structlog
from browserbase import Browserbase
from playwright.async_api import async_playwright

from backend.config import settings

log = structlog.get_logger()

BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
]

VIEWPORT = {"width": 1280, "height": 800}


class BrowserService:
    def __init__(self):
        self._bb = Browserbase(api_key=settings.browserbase_api_key)

    @asynccontextmanager
    async def new_page(self):
        session = self._bb.sessions.create()
        log.info("browser_session_created", session_id=session.id)
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(session.connect_url)
            context = await browser.new_context(
                viewport=VIEWPORT,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                locale="en-US",
            )
            page = await context.new_page()
            try:
                yield page
            finally:
                await browser.close()
                log.info("browser_session_closed", session_id=session.id)
