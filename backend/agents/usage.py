"""Token usage extraction and cost estimation for Claude API calls.

Every agent component records its calls into a per-run UsageTracker so the
cost of an ApplicationRun is measurable, persistable, and displayable.
"""
from __future__ import annotations

from typing import Any

# USD per million tokens: (input, output). Cache read is 0.1x input,
# cache write is 1.25x input.
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# Unknown models are priced at Opus tier so estimates err high, never low.
_DEFAULT_PRICING = (5.00, 25.00)

_CACHE_READ_MULTIPLIER = 0.1
_CACHE_WRITE_MULTIPLIER = 1.25


def _as_int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def extract_usage(response: Any) -> dict[str, int]:
    """Pull token counts off a Messages API response. Tolerates mocks and
    responses missing cache fields — absent values count as zero."""
    usage = getattr(response, "usage", None)
    return {
        "input_tokens": _as_int(getattr(usage, "input_tokens", 0)),
        "output_tokens": _as_int(getattr(usage, "output_tokens", 0)),
        "cache_read_input_tokens": _as_int(getattr(usage, "cache_read_input_tokens", 0)),
        "cache_creation_input_tokens": _as_int(getattr(usage, "cache_creation_input_tokens", 0)),
    }


def estimate_cost_usd(model: str, usage: dict[str, int]) -> float:
    input_price, output_price = PRICING_USD_PER_MTOK.get(model, _DEFAULT_PRICING)
    cost = (
        usage.get("input_tokens", 0) * input_price
        + usage.get("output_tokens", 0) * output_price
        + usage.get("cache_read_input_tokens", 0) * input_price * _CACHE_READ_MULTIPLIER
        + usage.get("cache_creation_input_tokens", 0) * input_price * _CACHE_WRITE_MULTIPLIER
    ) / 1_000_000
    return round(cost, 6)


class UsageTracker:
    """Accumulates per-call usage across all agents in a single run."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def reset(self) -> None:
        self.entries.clear()

    def add(self, model: str, response: Any, stage: str = "") -> dict:
        usage = extract_usage(response)
        entry = {
            "model": model,
            "stage": stage,
            **usage,
            "cost_usd": estimate_cost_usd(model, usage),
        }
        self.entries.append(entry)
        return entry

    @property
    def total_tokens(self) -> int:
        return sum(
            e["input_tokens"]
            + e["output_tokens"]
            + e["cache_read_input_tokens"]
            + e["cache_creation_input_tokens"]
            for e in self.entries
        )

    @property
    def total_cost_usd(self) -> float:
        return round(sum(e["cost_usd"] for e in self.entries), 6)

    def to_dict(self) -> dict:
        return {
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "calls": self.entries,
        }
