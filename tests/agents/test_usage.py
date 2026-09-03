from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.agents.usage import (
    UsageTracker,
    estimate_cost_usd,
    extract_usage,
)


def _response(input_tokens=1000, output_tokens=100, cache_read=0, cache_write=0):
    return SimpleNamespace(usage=SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_write,
    ))


def test_extract_usage_reads_all_fields():
    usage = extract_usage(_response(1500, 200, 300, 400))
    assert usage == {
        "input_tokens": 1500,
        "output_tokens": 200,
        "cache_read_input_tokens": 300,
        "cache_creation_input_tokens": 400,
    }


def test_extract_usage_tolerates_mock_responses():
    """MagicMock attributes aren't ints — they must count as zero, not explode."""
    usage = extract_usage(MagicMock())
    assert usage["input_tokens"] == 0
    assert usage["output_tokens"] == 0


def test_extract_usage_tolerates_missing_usage():
    usage = extract_usage(SimpleNamespace())
    assert usage["input_tokens"] == 0


def test_estimate_cost_sonnet_5():
    # 1M input at $2 + 100K output at $10 = $2 + $1 = $3
    usage = {"input_tokens": 1_000_000, "output_tokens": 100_000}
    assert estimate_cost_usd("claude-sonnet-5", usage) == 3.0


def test_estimate_cost_cache_multipliers():
    # cache read at 0.1x input price, cache write at 1.25x
    usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 1_000_000,
        "cache_creation_input_tokens": 1_000_000,
    }
    assert estimate_cost_usd("claude-sonnet-5", usage) == 0.2 + 2.5


def test_estimate_cost_unknown_model_priced_at_opus_tier():
    usage = {"input_tokens": 1_000_000, "output_tokens": 0}
    assert estimate_cost_usd("some-future-model", usage) == 5.0


def test_tracker_accumulates_and_totals():
    tracker = UsageTracker()
    tracker.add("claude-haiku-4-5", _response(1000, 100), stage="extraction")
    tracker.add("claude-sonnet-5", _response(2000, 500), stage="vision")

    assert len(tracker.entries) == 2
    assert tracker.total_tokens == 3600
    assert tracker.total_cost_usd > 0
    d = tracker.to_dict()
    assert d["total_cost_usd"] == tracker.total_cost_usd
    assert len(d["calls"]) == 2


def test_tracker_reset():
    tracker = UsageTracker()
    tracker.add("claude-sonnet-5", _response(), stage="vision")
    tracker.reset()
    assert tracker.entries == []
    assert tracker.total_cost_usd == 0
