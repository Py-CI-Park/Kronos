"""Training-only trade-penalty environment for D6R."""

from __future__ import annotations

from typing import TypeAlias, final

import numpy as np
from numpy.typing import NDArray
from typing_extensions import override

from stom_rl.rl_discovery.d3_env import D3Episode, D3Representation, HistoricalTopKEnv

StepValue: TypeAlias = str | int | float | None


class D6REnvironmentError(ValueError):
    """The registered training trade penalty is invalid."""


@final
class D6RTradePenaltyEnv(HistoricalTopKEnv):
    _additional_trade_penalty: float
    _additional_trade_penalty_bp: int

    def __init__(
        self,
        episodes: tuple[D3Episode, ...],
        *,
        representation: D3Representation,
        cost_bp: int,
        additional_trade_penalty_bp: int,
    ) -> None:
        if not 0 <= additional_trade_penalty_bp <= 100:
            raise D6REnvironmentError("D6R trade penalty must be between 0bp and 100bp")
        self._additional_trade_penalty = additional_trade_penalty_bp / 10_000
        self._additional_trade_penalty_bp = additional_trade_penalty_bp
        super().__init__(episodes, representation=representation, cost_bp=cost_bp)

    @override
    def step(
        self,
        action: int,
    ) -> tuple[NDArray[np.float32], float, bool, bool, dict[str, StepValue]]:
        observation, reward, terminated, truncated, info = super().step(action)
        penalized_reward = reward - self._additional_trade_penalty if action > 0 else reward
        typed_info: dict[str, StepValue] = {
            "decision_date": info["decision_date"],
            "symbol": info["symbol"],
            "action": info["action"],
            "gross_return": info["gross_return"],
            "cost_bp": info["cost_bp"],
            "training_trade_penalty_bp": self._additional_trade_penalty_bp,
        }
        return observation, penalized_reward, terminated, truncated, typed_info
