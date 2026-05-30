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
