"""Preregistered contracts for actual-market offline DQN and CQL research."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum, unique
from typing import Final
from typing_extensions import override

from .daily_market_errors import DailyMarketContractError
from .daily_market_transition_contract import MarketTransitionConfig

MODEL_INPUT_DIMENSION: Final = 172
ACTION_COUNT: Final = 2
MODEL_SEEDS: Final = (0, 1, 2, 3, 4)
BEHAVIOR_SEEDS: Final = tuple(range(1_000, 1_032))


@dataclass(frozen=True, slots=True)
class DailyMarketRlContractError(DailyMarketContractError):
    """A typed actual-market RL preregistration violation."""

    code: str
    detail: str = ""

    @override
    def __str__(self) -> str:
        return self.code if not self.detail else f"{self.code}:{self.detail}"


@unique
class MarketAlgorithm(StrEnum):
    """Closed set of algorithms and falsification controls."""

    DQN = "DQN"
    CQL = "CQL"
    CQL_REWARD_SHUFFLED = "CQL_REWARD_SHUFFLED"
    CQL_ACTION_SHUFFLED = "CQL_ACTION_SHUFFLED"


_CQL_ALPHA_BY_ALGORITHM: Final = {
    MarketAlgorithm.DQN: 0.0,
    MarketAlgorithm.CQL: 1.0,
    MarketAlgorithm.CQL_REWARD_SHUFFLED: 1.0,
    MarketAlgorithm.CQL_ACTION_SHUFFLED: 1.0,
}


@dataclass(frozen=True, slots=True)
class MarketTrainingConfig:
    """Immutable optimizer contract fixed before historical TEST evaluation."""

    algorithm: MarketAlgorithm
    seed: int
    input_dimension: int
    action_count: int
    hidden_dimensions: tuple[int, int]
    learning_rate: float
    discount: float
    cql_alpha: float
    reward_scale: float
    batch_size: int
    gradient_steps: int
    target_update_interval: int
    behavior_trajectory_count: int

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise DailyMarketRlContractError("INVALID_MODEL_SEED", str(self.seed))
        if self.input_dimension != MODEL_INPUT_DIMENSION or self.action_count != ACTION_COUNT:
            raise DailyMarketRlContractError("INVALID_MODEL_SHAPE")
        if self.gradient_steps < 1 or self.batch_size < 1:
            raise DailyMarketRlContractError("INVALID_OPTIMIZATION_BUDGET")

    @classmethod
    def registered(
        cls,
        *,
        algorithm: MarketAlgorithm,
        seed: int,
    ) -> MarketTrainingConfig:
        """Build the exact configuration committed in the preregistration."""
        return cls(
            algorithm=algorithm,
            seed=seed,
            input_dimension=MODEL_INPUT_DIMENSION,
            action_count=ACTION_COUNT,
            hidden_dimensions=(128, 64),
            learning_rate=0.0003,
            discount=0.95,
            cql_alpha=_CQL_ALPHA_BY_ALGORITHM[algorithm],
            reward_scale=100.0,
            batch_size=256,
            gradient_steps=600,
            target_update_interval=25,
            behavior_trajectory_count=len(BEHAVIOR_SEEDS),
        )


def base_cost_config() -> MarketTransitionConfig:
    """Return the percent-first 0.230% Kiwoom cost contract."""
    return MarketTransitionConfig()


def stress_cost_config() -> MarketTransitionConfig:
    """Return the same contract with 0.115% slippage on each side."""
    return replace(
        MarketTransitionConfig(),
        buy_slippage_percent=Decimal("0.115"),
        sell_slippage_percent=Decimal("0.115"),
    )


__all__ = [
    "ACTION_COUNT",
    "BEHAVIOR_SEEDS",
    "MODEL_INPUT_DIMENSION",
    "MODEL_SEEDS",
    "DailyMarketRlContractError",
    "MarketAlgorithm",
    "MarketTrainingConfig",
    "base_cost_config",
    "stress_cost_config",
]
