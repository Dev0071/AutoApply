from __future__ import annotations
import base64
import json

VALID_ACTIONS = {"click", "type", "select", "scroll", "done", "error"}

PERCEIVE_SYSTEM = (
    "You are controlling a browser to complete a job application. "
    "Look at each screenshot carefully. Viewport is 1280x800 pixels.\n\n"
    "Identify EVERY action you can confidently take on the visible screen, in "
    "execution order — fill all visible fields in one batch rather than one at a "
    "time. Only include actions whose target is fully visible. Reply ONLY with JSON:\n"
    "{\n"
    '  "actions": [\n'
    "    {\n"
    '      "action": "click" | "type" | "select" | "scroll",\n'
    '      "x": <pixel x — center of element>,\n'
    '      "y": <pixel y — center of element>,\n'
    '      "value": "<text to type or option label to select>",\n'
    '      "field_name": "<human-readable field name>",\n'
    '      "confidence": 0.0-1.0\n'
    "    }\n"
    "  ],\n"
    '  "reasoning": "<one sentence for the whole batch>",\n'
    '  "done": false\n'
    "}\n\n"
    'When the application is complete, reply with "done": true and an empty '
    'actions array. If you cannot proceed at all, reply with a single action '
    '"error" and explain why in reasoning.'
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
    if action["action"] not in VALID_ACTIONS:
        raise ValueError(f"Unknown action: {action['action']}")
    return action


def parse_batch_response(raw_text: str) -> dict:
    """Validate the batched perceive response: an envelope with an ordered
    list of actions, batch-level reasoning, and a done flag."""
    batch = json.loads(raw_text)
    required = {"actions", "reasoning", "done"}
    if not required.issubset(batch.keys()):
        raise ValueError(f"Missing required keys: {required - batch.keys()}")
    if not isinstance(batch["actions"], list):
        raise ValueError("'actions' must be a list")
    for action in batch["actions"]:
        if action.get("action") not in VALID_ACTIONS:
            raise ValueError(f"Unknown action: {action.get('action')!r}")
        if "confidence" not in action:
            raise ValueError(f"Action missing confidence: {action!r}")
    return batch
