from __future__ import annotations

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
    """Browserbase in production; local headless Chromium when
    BROWSER_MODE=local so dev/test iterations never consume paid sessions."""

    def __init__(self, mode: str | None = None):
        self._mode = mode or settings.browser_mode
        self._bb = (
            Browserbase(api_key=settings.browserbase_api_key)
            if self._mode == "browserbase"
            else None
        )

    @asynccontextmanager
    async def new_page(self):
        if self._mode == "local":
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True, args=BROWSER_ARGS)
                context = await browser.new_context(viewport=VIEWPORT, locale="en-US")
                page = await context.new_page()
                log.info("browser_session_created", mode="local")
                try:
                    yield page
                finally:
                    await browser.close()
                    log.info("browser_session_closed", mode="local")
            return

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
