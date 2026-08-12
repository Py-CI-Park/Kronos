"""Historical validation replay telemetry for the four-action CQL screen."""

from __future__ import annotations

import math
from datetime import datetime, time, timedelta, timezone
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .daily_market_allocation_contract import AllocationActionName
from .daily_market_allocation_experiment_contract import (
    LabeledAllocationTrajectory,
)
from .daily_market_allocation_rl_contract import AllocationAlgorithm
from .daily_market_rl_contract import DailyMarketRlContractError


class AllocationTelemetryMetricMetadata(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    reward_kind: Literal["raw_reward"] = "raw_reward"
    reward_unit: Literal["fraction"] = "fraction"
    equity_kind: Literal["krw_nav"] = "krw_nav"
    equity_unit: Literal["krw"] = "krw"
    action_recorded: Literal[True] = True


class AllocationValidationReplayEvent(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    global_step: int = Field(ge=1)
    phase: Literal["VALIDATION_REPLAY"] = "VALIDATION_REPLAY"
    reward: float
    equity: float = Field(gt=0)
    loss: None = None
    exploration: None = None
    action_name: AllocationActionName
    timestamp: datetime
    decision_timestamp: datetime
    reward_observed_at: datetime
    algorithm: Literal["CQL"] = "CQL"
    seed: int = Field(ge=0)
    scenario: Literal["BASE_0_230_PERCENT"] = "BASE_0_230_PERCENT"
    telemetry_scope: Literal["HISTORICAL_VALIDATION_MEDIAN_SEED_REPLAY"] = (
        "HISTORICAL_VALIDATION_MEDIAN_SEED_REPLAY"
    )
    telemetry_live_stream: Literal[False] = False
    historical_test_read: Literal[False] = False
    fresh_oos_read: Literal[False] = False
    promotion_allowed: Literal[False] = False
    info: AllocationTelemetryMetricMetadata = Field(
        default_factory=AllocationTelemetryMetricMetadata
    )

    @model_validator(mode="after")
    def _timestamps_are_kst_and_causal(self) -> Self:
        kst_offset = timedelta(hours=9)
        values = (self.timestamp, self.decision_timestamp, self.reward_observed_at)
        if any(value.utcoffset() != kst_offset for value in values):
            raise ValueError("allocation telemetry timestamps must be KST-aware")
        if (
            self.timestamp != self.reward_observed_at
            or self.decision_timestamp >= self.reward_observed_at
        ):
            raise ValueError("allocation telemetry timestamps are not causal")
        return self


def _median_cql_trajectory(
    trajectories: tuple[LabeledAllocationTrajectory, ...],
    median_return_percent: float,
) -> LabeledAllocationTrajectory:
    candidates = tuple(
        row
        for row in trajectories
        if row.algorithm is AllocationAlgorithm.CQL
        and row.scenario == "BASE_0_230_PERCENT"
        and math.isclose(
            row.trajectory.metrics.net_return_percent,
            median_return_percent,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
    )
    if not candidates:
        raise DailyMarketRlContractError(
            "ALLOCATION_MEDIAN_CQL_TRAJECTORY_MISSING",
            f"median={median_return_percent:.12f}",
        )
    return min(candidates, key=lambda row: row.seed)


def build_validation_replay_events(
    trajectories: tuple[LabeledAllocationTrajectory, ...],
    *,
    median_return_percent: float,
) -> tuple[AllocationValidationReplayEvent, ...]:
    """Expose the exact median CQL VALIDATION path without implying live training."""
    selected = _median_cql_trajectory(trajectories, median_return_percent)
    kst = timezone(timedelta(hours=9))
    return tuple(
        AllocationValidationReplayEvent(
            global_step=index,
            reward=step.reward_log_nav,
            equity=step.final_nav_krw,
            action_name=step.action,
            timestamp=datetime.combine(step.exit_date, time(9), tzinfo=kst),
            decision_timestamp=datetime.combine(
                step.decision_date, time(15, 30), tzinfo=kst
            ),
            reward_observed_at=datetime.combine(step.exit_date, time(9), tzinfo=kst),
            seed=selected.seed,
        )
        for index, step in enumerate(selected.trajectory.steps, start=1)
    )


__all__ = [
    "AllocationTelemetryMetricMetadata",
    "AllocationValidationReplayEvent",
    "build_validation_replay_events",
]
