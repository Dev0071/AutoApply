from __future__ import annotations
import base64
import json

PERCEIVE_SYSTEM = (
    "You are controlling a browser to complete a job application. "
    "Look at each screenshot carefully. Viewport is 1280x800 pixels.\n\n"
    "Identify the NEXT single action to take. Reply ONLY with JSON:\n"
    "{\n"
    '  "action": "click" | "type" | "select" | "scroll" | "done" | "error",\n'
    '  "x": <pixel x — center of element>,\n'
    '  "y": <pixel y — center of element>,\n'
    '  "value": "<text to type or option label to select>",\n'
    '  "field_name": "<human-readable field name>",\n'
    '  "reasoning": "<one sentence>",\n'
    '  "confidence": 0.0-1.0,\n'
    '  "done": false\n'
    "}"
)


def build_perceive_prompt(
    task: str,
    filled_fields: list[str],
    profile_summary: str,
) -> str:
    return (
        f"Current task: {task}\n"
        f"Fields already filled: {filled_fields}\n"
        f"Candidate profile: {profile_summary}"
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
