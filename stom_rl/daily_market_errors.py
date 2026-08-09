"""Typed errors for the daily market research pipeline."""


class DailyMarketContractError(ValueError):
    """A typed input or research-contract violation."""


class DailyMarketArtifactError(DailyMarketContractError):
    """An untrusted, malformed, or unbounded artifact."""


class DailyMarketScoreError(DailyMarketContractError):
    """A causal score dataset contract violation."""


class DailyMarketStateError(DailyMarketContractError):
    """A causal state dataset contract violation."""


class DailyMarketDataError(DailyMarketContractError):
    """A read-only market data boundary violation."""


class DailyMarketTransitionError(DailyMarketContractError):
    """A portfolio transition request violation."""


class DailyMarketInvariantError(RuntimeError):
    """An internal lineage or accounting invariant failure."""


__all__ = [
    "DailyMarketArtifactError",
    "DailyMarketContractError",
    "DailyMarketDataError",
    "DailyMarketInvariantError",
    "DailyMarketScoreError",
    "DailyMarketStateError",
    "DailyMarketTransitionError",
]
