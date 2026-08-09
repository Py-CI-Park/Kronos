"""Preregistered contracts for four-action daily-market DQN/CQL screening."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import Final

from .daily_market_allocation_contract import AllocationAction
from .daily_market_rl_contract import (
    MODEL_INPUT_DIMENSION,
    MODEL_SEEDS,
    DailyMarketRlContractError,
)

ALLOCATION_ACTION_COUNT: Final = len(AllocationAction)
ALLOCATION_MODEL_SEEDS: Final = MODEL_SEEDS


@unique
class AllocationAlgorithm(StrEnum):
    """Closed set of preregistered multi-action screening algorithms."""

    DQN = "DQN"
    CQL = "CQL"


@dataclass(frozen=True, slots=True)
class AllocationTrainingConfig:
    """Fixed optimizer contract that never grants TEST access or promotion."""

    algorithm: AllocationAlgorithm
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

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise DailyMarketRlContractError(
                "INVALID_ALLOCATION_MODEL_SEED", str(self.seed)
            )
        if (
            self.input_dimension != MODEL_INPUT_DIMENSION
            or self.action_count != ALLOCATION_ACTION_COUNT
        ):
            raise DailyMarketRlContractError("INVALID_ALLOCATION_MODEL_SHAPE")
        if self.gradient_steps < 1 or self.batch_size < 1:
            raise DailyMarketRlContractError("INVALID_ALLOCATION_OPTIMIZATION_BUDGET")

    @classmethod
    def registered(
        cls,
        *,
        algorithm: AllocationAlgorithm,
        seed: int,
    ) -> AllocationTrainingConfig:
        return cls(
            algorithm=algorithm,
            seed=seed,
            input_dimension=MODEL_INPUT_DIMENSION,
            action_count=ALLOCATION_ACTION_COUNT,
            hidden_dimensions=(128, 64),
            learning_rate=0.0003,
            discount=0.95,
            cql_alpha=0.0 if algorithm is AllocationAlgorithm.DQN else 1.0,
            reward_scale=100.0,
            batch_size=256,
            gradient_steps=600,
            target_update_interval=25,
        )


__all__ = [
    "ALLOCATION_ACTION_COUNT",
    "ALLOCATION_MODEL_SEEDS",
    "AllocationAlgorithm",
    "AllocationTrainingConfig",
]
