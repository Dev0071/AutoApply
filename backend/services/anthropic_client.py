"""Single place that constructs the Anthropic client.

Identity-linked API keys are rejected with a 400 unless the request names the
workspace it acts in, so the header is applied here rather than at each of the
call sites.
"""
from __future__ import annotations

import anthropic

from backend.config import settings


def build_anthropic_client(api_key: str | None = None) -> anthropic.AsyncAnthropic:
    headers: dict[str, str] = {}
    workspace_id = (settings.anthropic_workspace_id or "").strip()
    if workspace_id:
        headers["anthropic-workspace-id"] = workspace_id

    return anthropic.AsyncAnthropic(
        api_key=api_key or settings.anthropic_api_key,
        default_headers=headers or None,
    )
