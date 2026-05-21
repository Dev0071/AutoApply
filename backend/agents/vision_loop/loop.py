from dataclasses import dataclass, field
from datetime import datetime

import anthropic
import structlog
from playwright.async_api import Page

from backend.agents.vision_loop.execute import execute_action
from backend.agents.vision_loop.perceive import (
    build_perceive_prompt,
    encode_screenshot,
    parse_action_response,
)
from backend.config import settings
from backend.services.storage import StorageService

log = structlog.get_logger()


class AgentError(Exception):
    pass


@dataclass
class StepLog:
    step_number: int
    timestamp: str
    action: dict
    screenshot_url: str
    success: bool
    field_name: str = ""

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "timestamp": self.timestamp,
            "action": self.action.get("action"),
            "x": self.action.get("x"),
            "y": self.action.get("y"),
            "value": self.action.get("value"),
            "field_name": self.field_name,
            "reasoning": self.action.get("reasoning"),
            "confidence": self.action.get("confidence"),
            "screenshot_url": self.screenshot_url,
            "success": self.success,
        }


def summarize_profile(profile: dict) -> str:
    return (
        f"Name: {profile.get('name')}, "
        f"Skills: {', '.join(profile.get('skills', []))}, "
        f"Location: {profile.get('location')}"
    )


class VisionActionLoop:
    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic,
        storage: StorageService,
        max_steps: int = settings.vision_loop_max_steps,
        wait_ms: int = settings.vision_loop_wait_ms,
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
        filled: list[str] = []

        for step_num in range(self.max_steps):
            png = await page.screenshot(type="png", full_page=False)

            prompt = build_perceive_prompt(task, filled, summarize_profile(profile))
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

            screenshot_url = await self.storage.upload_screenshot(png, run_id=run_id, step=step_num)

            step = StepLog(
                step_number=step_num,
                timestamp=datetime.utcnow().isoformat(),
                action=action,
                screenshot_url=screenshot_url,
                success=True,
                field_name=action.get("field_name", ""),
            )
            self._steps.append(step)

            log.info("vision_step", step=step_num, action=action.get("action"), field=step.field_name)

            if action["done"]:
                break
            if action["action"] == "error":
                raise AgentError(action["reasoning"])

            await execute_action(page, action)
            filled.append(action.get("field_name", ""))
            await page.wait_for_timeout(self.wait_ms)

        return self._steps
