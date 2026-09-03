"""Verify Anthropic credentials before a UAT run.

Makes one 1-token call and reports exactly what's wrong, so a misconfigured
key is caught here rather than after a Celery task has already fetched a JD.

    make check-anthropic
"""
from __future__ import annotations

import asyncio
import sys

import anthropic

from backend.config import settings
from backend.services.anthropic_client import build_anthropic_client


async def main() -> int:
    key = settings.anthropic_api_key or ""
    workspace = (settings.anthropic_workspace_id or "").strip()

    print(f"  key:       {key[:14]}…{key[-4:]}" if len(key) > 20 else f"  key:       {key!r}")
    print(f"  workspace: {workspace or '(not set)'}")

    if key.endswith("...") or not key:
        print("\nFAIL: ANTHROPIC_API_KEY is still the placeholder. Set a real key in .env.")
        return 1

    client = build_anthropic_client()
    try:
        response = await client.messages.with_raw_response.create(
            model=settings.extraction_model,
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
        resolved = response.headers.get("anthropic-workspace-id")
        print(f"\nOK: credentials work. Request ran in workspace {resolved or '(default)'}.")
        if resolved and not workspace:
            print(f"    Tip: set ANTHROPIC_WORKSPACE_ID={resolved} to pin it explicitly.")
        return 0
    except anthropic.BadRequestError as exc:
        message = str(exc)
        print(f"\nFAIL (400): {message[:300]}")
        if "workspace-id is required" in message:
            print(
                "\n  Your key is identity-linked and spans multiple workspaces, so every\n"
                "  request must name the workspace it acts in.\n"
                "  Fix A: set ANTHROPIC_WORKSPACE_ID in .env — find the wrkspc_… id at\n"
                "          https://platform.claude.com/settings/workspaces\n"
                "  Fix B: create an API key scoped to a single workspace; such a key\n"
                "          needs no header at all."
            )
        elif "must be a valid workspace" in message:
            print(
                "\n  The header is being sent, but the id is wrong. Copy the exact\n"
                "  wrkspc_… value from https://platform.claude.com/settings/workspaces"
            )
        return 1
    except anthropic.AuthenticationError as exc:
        print(f"\nFAIL (401): the API key is invalid or revoked. {str(exc)[:200]}")
        return 1
    except anthropic.PermissionDeniedError as exc:
        print(f"\nFAIL (403): the key lacks access to that workspace. {str(exc)[:200]}")
        return 1
    finally:
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
