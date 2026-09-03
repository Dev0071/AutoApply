import anthropic
import structlog
from playwright.async_api import Page

from backend.agents.dom_fill.executor import fill_fields
from backend.agents.dom_fill.greenhouse import fetch_question_schema
from backend.agents.dom_fill.mapper import map_fields
from backend.agents.dom_fill.serialize import serialize_form
from backend.agents.exceptions import DomFillError, FitThresholdError
from backend.agents.fit_scorer import score_fit
from backend.agents.jd_miner import JDMiner
from backend.agents.schemas import JDResult, TailoringResult
from backend.agents.tailoring_engine import TailoringEngine
from backend.agents.usage import UsageTracker
from backend.agents.vision_loop.loop import VisionActionLoop
from backend.config import settings
from backend.services.browser import BrowserService
from backend.services.storage import StorageService

log = structlog.get_logger()

# If more than half of the attempted DOM fills fail verification, the page is
# not DOM-friendly — fall back to the vision loop.
_DOM_FAILURE_RATIO = 0.5
_MIN_SERIALIZABLE_FIELDS = 3


class Orchestrator:
    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic,
        storage: StorageService,
        browser: BrowserService,
        cache=None,
    ):
        self.client = anthropic_client
        self.storage = storage
        self.tracker = UsageTracker()
        self.jd_miner = JDMiner(anthropic_client, cache=cache, tracker=self.tracker)
        self.tailoring = TailoringEngine(anthropic_client, tracker=self.tracker)
        self.vision_loop = VisionActionLoop(
            anthropic_client, storage,
            max_steps=settings.vision_loop_max_steps,
            wait_ms=settings.vision_loop_wait_ms,
            tracker=self.tracker,
        )
        self.browser = browser

    async def run(self, job_url: str, profile: dict, run_id: str) -> dict:
        self.tracker.reset()

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

        tailoring: TailoringResult = await self.tailoring.generate_tailoring(profile, jd)

        async with self.browser.new_page() as page:
            await page.goto(job_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(settings.vision_loop_wait_ms)
            steps, tier = await self._fill(page, job_url, profile, jd, tailoring, run_id)

        result = {
            "fit_score": fit_score,
            "cover_letter": tailoring.cover_letter,
            "bullets": tailoring.bullets,
            "steps": steps,
            "jd": jd.model_dump(),
            "tier": tier,
            "token_usage": self.tracker.to_dict(),
            "total_cost_usd": self.tracker.total_cost_usd,
        }
        if self.vision_loop.abort_reason:
            result["abort_reason"] = self.vision_loop.abort_reason

        log.info(
            "run_cost",
            run_id=run_id,
            tier=tier,
            total_cost_usd=self.tracker.total_cost_usd,
            total_tokens=self.tracker.total_tokens,
        )
        return result

    async def _fill(
        self,
        page: Page,
        job_url: str,
        profile: dict,
        jd: JDResult,
        tailoring: TailoringResult,
        run_id: str,
    ) -> tuple[list[dict], str]:
        """Tiered navigation: DOM-serialized fill first, vision loop fallback."""
        if settings.hybrid_fill_enabled and profile.get("hybrid_fill", True):
            try:
                return await self._dom_fill(page, job_url, profile, jd, tailoring, run_id), "dom"
            except DomFillError as exc:
                log.warning("dom_fill_fallback_to_vision", run_id=run_id, reason=str(exc))

        vision_steps = await self.vision_loop.run(
            page, task=job_url, profile=profile, run_id=run_id
        )
        return [s.to_dict() for s in vision_steps], "vision"

    async def _dom_fill(
        self,
        page: Page,
        job_url: str,
        profile: dict,
        jd: JDResult,
        tailoring: TailoringResult,
        run_id: str,
    ) -> list[dict]:
        try:
            fields = await serialize_form(page)
        except Exception as exc:
            raise DomFillError(f"Form serialization failed: {exc}") from exc

        if len(fields) < _MIN_SERIALIZABLE_FIELDS:
            raise DomFillError(
                f"Only {len(fields)} fillable fields found — page likely not DOM-readable"
            )

        # Tier 1: authoritative question schema for Greenhouse postings
        questions = None
        if jd.ats_type == "greenhouse":
            questions = await fetch_question_schema(job_url)

        mappings = await map_fields(
            self.client, fields, profile,
            tailoring=tailoring, jd=jd,
            extra_questions=questions,
            tracker=self.tracker,
        )

        steps, attempted, failed = await fill_fields(
            page, fields, mappings, self.storage, run_id
        )

        if attempted == 0:
            raise DomFillError("Mapper produced no fillable answers")
        if (failed / attempted) > _DOM_FAILURE_RATIO:
            raise DomFillError(
                f"{failed}/{attempted} fields failed verification — falling back to vision"
            )
        return steps
