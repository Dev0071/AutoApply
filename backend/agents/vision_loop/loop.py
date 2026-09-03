from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

import anthropic
import structlog
from playwright.async_api import Page

from backend.agents.exceptions import AgentError, MaxStepsExceededError, StuckLoopError
from backend.agents.usage import UsageTracker
from backend.agents.vision_loop.execute import execute_action
from backend.agents.vision_loop.perceive import (
    PERCEIVE_SYSTEM,
    build_perceive_prompt,
    encode_screenshot,
    parse_batch_response,
)
from backend.agents.vision_loop.verify import verify_action
from backend.config import settings

if TYPE_CHECKING:
    from backend.services.storage import StorageService

log = structlog.get_logger()

# Stuck detection thresholds — a dead run should cost a few perceive calls, not 30.
_MAX_IDENTICAL_SCREENS = 3
_MAX_IDENTICAL_BATCHES = 3
_MAX_LOW_CONFIDENCE_ROUNDS = 2
_LOW_CONFIDENCE_FLOOR = 0.3

# Escalate to the fallback model when more than half the typed fields in a
# batch fail DOM verification.
_ESCALATION_FAILURE_RATIO = 0.5


@dataclass
class StepLog:
    step_number: int
    timestamp: str
    action: dict
    screenshot_url: str
    success: bool
    verified: bool | None = field(default=None)
    usage: dict | None = field(default=None)

    def to_dict(self) -> dict:
        d = {
            "step_number": self.step_number,
            "timestamp": self.timestamp,
            "action": self.action.get("action"),
            "x": self.action.get("x"),
            "y": self.action.get("y"),
            "value": self.action.get("value"),
            "field_name": self.action.get("field_name", ""),
            "reasoning": self.action.get("reasoning"),
            "confidence": self.action.get("confidence"),
            "screenshot_url": self.screenshot_url,
            "success": self.success,
            "verified": self.verified,
        }
        if self.usage is not None:
            d["usage"] = self.usage
        return d


def _summarize_profile(profile: dict) -> str:
    parts = [f"Name: {profile.get('name', 'N/A')}"]
    if skills := profile.get("skills"):
        parts.append(f"Skills: {', '.join(skills)}")
    if location := profile.get("location"):
        parts.append(f"Location: {location}")
    return " | ".join(parts)


class VisionActionLoop:
    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic,
        storage: StorageService,
        max_steps: int = 30,
        wait_ms: int = 800,
        model: str | None = None,
        fallback_model: str | None = None,
        token_budget: int | None = None,
        inter_action_wait_ms: int | None = None,
        tracker: UsageTracker | None = None,
    ):
        self.client = anthropic_client
        self.storage = storage
        self.max_steps = max_steps
        self.wait_ms = wait_ms
        self.model = model or settings.vision_model
        self.fallback_model = fallback_model or settings.vision_fallback_model
        self.token_budget = token_budget or settings.vision_loop_token_budget
        self.inter_action_wait_ms = (
            inter_action_wait_ms
            if inter_action_wait_ms is not None
            else settings.vision_loop_inter_action_wait_ms
        )
        self.tracker = tracker if tracker is not None else UsageTracker()
        self._steps: list[StepLog] = []
        self.abort_reason: str | None = None

    async def run(
        self,
        page: Page,
        task: str,
        profile: dict,
        run_id: str,
    ) -> list[StepLog]:
        self._steps = []  # reset for each run
        self.abort_reason = None
        filled: list[str] = []
        step_num = 0
        tokens_spent = 0
        escalate_next = False

        prev_screen_hash: str | None = None
        identical_screens = 0
        prev_batch_sig: str | None = None
        identical_batches = 0
        low_confidence_rounds = 0

        for _round in range(self.max_steps):
            # 0. Budget guardrail — abort gracefully into review, keep partial steps
            if tokens_spent >= self.token_budget:
                self.abort_reason = "token_budget_exceeded"
                log.warning(
                    "vision_budget_exceeded",
                    run_id=run_id,
                    tokens_spent=tokens_spent,
                    budget=self.token_budget,
                )
                return self._steps

            # 1. Screenshot — what Claude will see this round
            png = await page.screenshot(type="png", full_page=False)

            # 2. Stuck screen check BEFORE the perceive call — an unchanged
            # screen shouldn't cost another API round
            screen_hash = hashlib.sha256(png).hexdigest()
            identical_screens = identical_screens + 1 if screen_hash == prev_screen_hash else 1
            prev_screen_hash = screen_hash
            if identical_screens >= _MAX_IDENTICAL_SCREENS:
                raise StuckLoopError(
                    f"Screen unchanged for {identical_screens} rounds. Run: {run_id}"
                )

            # 3. Perceive — one call returns every confident action for this screen
            model = self.fallback_model if escalate_next else self.model
            prompt = build_perceive_prompt(task, filled, _summarize_profile(profile))
            response = await self.client.messages.create(
                model=model,
                max_tokens=1024,
                system=PERCEIVE_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": [
                        encode_screenshot(png),
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            escalate_next = False
            round_usage = self.tracker.add(model, response, stage="vision")
            tokens_spent += (
                round_usage["input_tokens"]
                + round_usage["output_tokens"]
                + round_usage["cache_read_input_tokens"]
                + round_usage["cache_creation_input_tokens"]
            )
            batch = parse_batch_response(response.content[0].text)

            # 3. Upload the perceive screenshot for the audit trail
            screenshot_url = await self.storage.upload_screenshot(
                png, run_id=run_id, step=step_num
            )

            log.info(
                "vision_round",
                run_id=run_id,
                round=_round,
                model=model,
                actions=len(batch["actions"]),
                done=batch["done"],
            )

            # 4. Terminal conditions
            if batch["done"]:
                self._steps.append(StepLog(
                    step_number=step_num,
                    timestamp=datetime.utcnow().isoformat(),
                    action={"action": "done", "reasoning": batch["reasoning"], "done": True},
                    screenshot_url=screenshot_url,
                    success=True,
                    usage=round_usage,
                ))
                log.info("vision_loop_complete", run_id=run_id, steps=step_num + 1)
                return self._steps

            if batch["actions"] and batch["actions"][0]["action"] == "error":
                raise AgentError(batch["reasoning"])

            # 5. Stuck plan detection — same actions or no confidence
            batch_sig = json.dumps(batch["actions"], sort_keys=True)
            identical_batches = identical_batches + 1 if batch_sig == prev_batch_sig else 1
            prev_batch_sig = batch_sig
            if identical_batches >= _MAX_IDENTICAL_BATCHES:
                raise StuckLoopError(
                    f"Identical action batch returned {identical_batches} times. Run: {run_id}"
                )

            confidences = [a.get("confidence", 0.0) for a in batch["actions"]]
            if confidences and max(confidences) < _LOW_CONFIDENCE_FLOOR:
                low_confidence_rounds += 1
                if low_confidence_rounds >= _MAX_LOW_CONFIDENCE_ROUNDS:
                    raise StuckLoopError(
                        f"Confidence below {_LOW_CONFIDENCE_FLOOR} for "
                        f"{low_confidence_rounds} consecutive rounds. Run: {run_id}"
                    )
            else:
                low_confidence_rounds = 0

            # 6. Execute the batch, logging each action with its own screenshot
            typed = 0
            verify_failures = 0
            first_in_round = True
            for action in batch["actions"]:
                await execute_action(page, action)
                await page.wait_for_timeout(self.inter_action_wait_ms)

                # None = field not locatable, so nothing is known — only a
                # confirmed mismatch counts against the batch (and toward
                # escalating to the pricier model).
                verified: bool | None = True
                if action["action"] == "type" and action.get("field_name") and action.get("value"):
                    verified = await verify_action(
                        page, action["field_name"], str(action["value"])
                    )
                    if verified is not None:
                        typed += 1
                        if verified is False:
                            verify_failures += 1

                action_png = await page.screenshot(type="png", full_page=False)
                action_url = await self.storage.upload_screenshot(
                    action_png, run_id=run_id, step=step_num
                )
                self._steps.append(StepLog(
                    step_number=step_num,
                    timestamp=datetime.utcnow().isoformat(),
                    action={**action, "reasoning": batch["reasoning"], "done": False},
                    screenshot_url=action_url,
                    success=verified is not False,
                    verified=verified,
                    usage=round_usage if first_in_round else None,
                ))
                first_in_round = False
                step_num += 1

                if f := action.get("field_name"):
                    filled.append(f)

            # 7. Escalate one perceive call to the fallback model when this
            # screen's typed fields mostly failed verification
            if typed and (verify_failures / typed) > _ESCALATION_FAILURE_RATIO:
                escalate_next = True
                log.warning(
                    "vision_escalating_model",
                    run_id=run_id,
                    failures=verify_failures,
                    typed=typed,
                    fallback=self.fallback_model,
                )

            # 8. Wait for React/Angular re-render before the next screenshot
            await page.wait_for_timeout(self.wait_ms)

        raise MaxStepsExceededError(
            f"Vision loop exceeded {self.max_steps} rounds without completing. Run: {run_id}"
        )
