import anthropic
import structlog

from backend.agents.exceptions import FitThresholdError
from backend.agents.fit_scorer import score_fit
from backend.agents.jd_miner import JDMiner
from backend.agents.schemas import JDResult, TailoringResult
from backend.agents.tailoring_engine import TailoringEngine
from backend.agents.vision_loop.loop import VisionActionLoop
from backend.config import settings
from backend.services.browser import BrowserService
from backend.services.storage import StorageService

log = structlog.get_logger()


class Orchestrator:
    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic,
        storage: StorageService,
        browser: BrowserService,
    ):
        self.jd_miner = JDMiner(anthropic_client)
        self.tailoring = TailoringEngine(anthropic_client)
        self.vision_loop = VisionActionLoop(
            anthropic_client, storage,
            max_steps=settings.vision_loop_max_steps,
            wait_ms=settings.vision_loop_wait_ms,
        )
        self.browser = browser

    async def run(self, job_url: str, profile: dict, run_id: str) -> dict:
        jd: JDResult = await self.jd_miner.fetch(job_url)

        fit_score = score_fit(profile, jd.model_dump())
        threshold = profile.get("fit_threshold", settings.fit_threshold_default)
        if fit_score < threshold:
            raise FitThresholdError(
                f"Fit score {fit_score} below threshold {threshold}",
                score=fit_score,
                threshold=threshold,
            )

        log.info("fit_passed", score=fit_score, threshold=threshold, job=jd.title)

        cover_result: TailoringResult = await self.tailoring.generate_cover_letter(profile, jd)
        bullets_result: TailoringResult = await self.tailoring.rewrite_bullets(profile, jd)

        async with self.browser.new_page() as page:
            steps = await self.vision_loop.run(page, task=job_url, profile=profile, run_id=run_id)

        return {
            "fit_score": fit_score,
            "cover_letter": cover_result.cover_letter,
            "bullets": bullets_result.bullets,
            "steps": [s.to_dict() for s in steps],
            "jd": jd.model_dump(),
        }
