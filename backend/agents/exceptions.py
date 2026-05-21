from __future__ import annotations


class AgentError(Exception):
    pass


class MaxStepsExceededError(AgentError):
    pass


class BrowserError(AgentError):
    pass


class FitThresholdError(Exception):
    pass
