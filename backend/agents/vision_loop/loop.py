from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import anthropic
import structlog
from playwright.async_api import Page

from backend.agents.exceptions import AgentError, MaxStepsExceededError
from backend.agents.vision_loop.execute import execute_action
from backend.agents.vision_loop.perceive import (
    build_perceive_prompt,
    encode_screenshot,
    parse_action_response,
)

if TYPE_CHECKING:
    from backend.services.storage import StorageService

log = structlog.get_logger()


@dataclass
class StepLog:
    step_number: int
    timestamp: str
    action: dict
    screenshot_url: str
    success: bool

    def to_dict(self) -> dict:
        return {
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
        }


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
    ):
        self.client = anthropic_client
        self.storage = storage
        self.max_steps = max_steps
        self.wait_ms = wait_ms
        self._steps: list[StepLog] = []

    async def run(
        self,
        page: Page,
        task: str,
        profile: dict,
        run_id: str,
    ) -> list[StepLog]:
        self._steps = []  # reset for each run
        filled: list[str] = []

        for step_num in range(self.max_steps):
            # 1. Screenshot (functional)
            png = await page.screenshot(type="png", full_page=False)

            # 2. Perceive — image first, then text prompt
            prompt = build_perceive_prompt(task, filled, _summarize_profile(profile))
            response = await self.client.messages.create(
                model="claude-opus-4-5",
                max_tokens=512,
                messages=[{
                    "role": "user",
                    "content": [
                        encode_screenshot(png),
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            action = parse_action_response(response.content[0].text)

            # 3. Upload screenshot to S3
            screenshot_url = await self.storage.upload_screenshot(
                png, run_id=run_id, step=step_num
            )

            # 4. Log step before acting (so partial runs are auditable)
            step = StepLog(
                step_number=step_num,
                timestamp=datetime.utcnow().isoformat(),
                action=action,
                screenshot_url=screenshot_url,
                success=True,
            )
            self._steps.append(step)

            log.info(
                "vision_step",
                run_id=run_id,
                step=step_num,
                action=action.get("action"),
                field=action.get("field_name", ""),
                confidence=action.get("confidence"),
            )

            # 5. Terminal conditions
            if action["done"]:
                log.info("vision_loop_complete", run_id=run_id, steps=step_num + 1)
                break

            if action["action"] == "error":
                raise AgentError(action["reasoning"])

            # 6. Execute action (functional dispatch)
            await execute_action(page, action)
            if field := action.get("field_name"):
                filled.append(field)

            # 7. Wait for React/Angular re-render — non-optional
            await page.wait_for_timeout(self.wait_ms)

        else:
            raise MaxStepsExceededError(
                f"Vision loop exceeded {self.max_steps} steps without completing. Run: {run_id}"
            )

        return self._steps
