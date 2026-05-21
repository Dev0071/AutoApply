import anthropic
import structlog
from playwright.async_api import Page

from backend.agents.fit_scorer import score_fit
from backend.agents.jd_miner import JDMiner
from backend.agents.tailoring_engine import TailoringEngine
from backend.agents.vision_loop.loop import VisionActionLoop
from backend.config import settings
from backend.services.browser import BrowserService
from backend.services.storage import StorageService

log = structlog.get_logger()


class FitThresholdError(Exception):
    pass


class Orchestrator:
    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic,
        storage: StorageService,
        browser: BrowserService,
    ):
        self.jd_miner = JDMiner()
        self.tailoring = TailoringEngine(anthropic_client)
        self.vision_loop = VisionActionLoop(anthropic_client, storage)
        self.browser = browser

    async def run(self, job_url: str, profile: dict, run_id: str) -> dict:
        jd = await self.jd_miner.fetch(job_url)

        fit_score = score_fit(profile, jd)
        threshold = profile.get("fit_threshold", settings.fit_threshold_default)
        if fit_score < threshold:
            raise FitThresholdError(
                f"Fit score {fit_score} below threshold {threshold}"
            )

        log.info("fit_passed", score=fit_score, threshold=threshold)

        cover_letter = await self.tailoring.generate_cover_letter(profile, jd)
        bullets = await self.tailoring.rewrite_bullets(profile, jd)

        async with self.browser.new_page() as page:
            steps = await self.vision_loop.run(page, task=job_url, profile=profile, run_id=run_id)

        return {
            "fit_score": fit_score,
            "cover_letter": cover_letter,
            "bullets": bullets,
            "steps": [s.to_dict() for s in steps],
            "jd": jd,
        }
