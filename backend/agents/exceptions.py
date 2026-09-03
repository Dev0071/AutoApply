from __future__ import annotations


class AgentError(Exception):
    pass


class MaxStepsExceededError(AgentError):
    pass


class BrowserError(AgentError):
    pass


class FitThresholdError(Exception):
    def __init__(self, message: str, score: float = 0.0, threshold: float = 70.0):
        super().__init__(message)
        self.score = score
        self.threshold = threshold


class JDFetchError(Exception):
    """Job page could not be fetched. Never retried — user must fix the URL."""
    pass


class StuckLoopError(AgentError):
    """Vision loop detected it is making no progress. Never retried — retrying
    a stuck loop burns the same tokens on the same wall."""
    pass


class DomFillError(AgentError):
    """DOM-based fill could not handle this page — fall back to the vision loop."""
    pass


class RateLimitExceededError(Exception):
    """User hit the per-platform daily application cap. Never retried."""
    def __init__(self, message: str, platform: str = "", limit: int = 0):
        super().__init__(message)
        self.platform = platform
        self.limit = limit
