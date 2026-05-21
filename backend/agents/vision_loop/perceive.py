from __future__ import annotations
import base64
import json

PERCEIVE_PROMPT_TEMPLATE = """
You are controlling a browser to complete a job application.
Look at this screenshot carefully. Viewport is 1280x800 pixels.

Current task: {task}
Fields already filled: {filled_fields}
Candidate profile: {profile_summary}

Identify the NEXT single action to take. Reply ONLY with JSON:
{{
  "action": "click" | "type" | "select" | "scroll" | "done" | "error",
  "x": <pixel x — center of element>,
  "y": <pixel y — center of element>,
  "value": "<text to type or option label to select>",
  "field_name": "<human-readable field name>",
  "reasoning": "<one sentence>",
  "confidence": 0.0-1.0,
  "done": false
}}
"""


def build_perceive_prompt(
    task: str,
    filled_fields: list[str],
    profile_summary: str,
) -> str:
    return PERCEIVE_PROMPT_TEMPLATE.format(
        task=task,
        filled_fields=filled_fields,
        profile_summary=profile_summary,
    )


def encode_screenshot(png_bytes: bytes) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.standard_b64encode(png_bytes).decode("utf-8"),
        },
    }


def parse_action_response(raw_text: str) -> dict:
    action = json.loads(raw_text)
    required = {"action", "reasoning", "confidence", "done"}
    if not required.issubset(action.keys()):
        raise ValueError(f"Missing required keys: {required - action.keys()}")
    valid_actions = {"click", "type", "select", "scroll", "done", "error"}
    if action["action"] not in valid_actions:
        raise ValueError(f"Unknown action: {action['action']}")
    return action
