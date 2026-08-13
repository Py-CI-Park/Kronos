"""Typed trajectories and metrics for the four-action allocation screen."""

from __future__ import annotations

from datetime import date
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .daily_market_allocation_contract import AllocationActionName
from .daily_market_transition_contract import SplitName

AllocationPolicyKind = Literal["CONTROL", "RL"]


class AllocationTrajectoryStep(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    decision_date: date
    entry_date: date
    exit_date: date
    action: AllocationActionName
    final_nav_krw: float = Field(gt=0)
    deployed_at_entry_krw: float = Field(ge=0)
    total_cost_krw: float = Field(ge=0)
    reward_log_nav: float
    drawdown_percent: float = Field(ge=-100, le=0)
    filled_slots: int = Field(ge=0, le=10)

    @model_validator(mode="after")
    def _action_accounting_is_possible(self) -> Self:
        slot_limit = {
            "CASH": 0,
            "INVEST_TOP3_EQUAL_SLOT": 3,
            "INVEST_TOP5_EQUAL_SLOT": 5,
            "INVEST_TOP10_EQUAL_SLOT": 10,
        }[self.action]
        if (
            self.filled_slots > slot_limit
            or self.deployed_at_entry_krw > self.filled_slots * 5_000_000
        ):
            raise ValueError("allocation action exceeds registered slot exposure")
        if self.action == "CASH":
            valid = (
                self.filled_slots == 0
                and self.deployed_at_entry_krw == 0
                and self.total_cost_krw == 0
            )
        else:
            valid = (
                self.filled_slots >= 1
                and self.deployed_at_entry_krw > 0
                and self.total_cost_krw > 0
            )
        if not valid:
            raise ValueError("allocation fill, deployment, and cost disagree")
        return self


class AllocationPolicyMetrics(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    policy: str
    policy_kind: AllocationPolicyKind
    split: SplitName
    round_trip_cost_percent: float = Field(ge=0)
    date_count: int = Field(gt=0)
    initial_nav_krw: float = Field(gt=0)
    final_nav_krw: float = Field(gt=0)
    total_net_pnl_krw: float
    net_return_percent: float
    max_drawdown_percent: float = Field(ge=-100, le=0)
    action_cash_count: int = Field(ge=0)
    action_top3_count: int = Field(ge=0)
    action_top5_count: int = Field(ge=0)
    action_top10_count: int = Field(ge=0)
    distinct_action_count: int = Field(ge=1, le=4)
    filled_slots: int = Field(ge=0)
    total_cost_krw: float = Field(ge=0)
    turnover: float = Field(ge=0)
    mean_reward: float
    cumulative_reward: float


class AllocationPolicyTrajectory(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    metrics: AllocationPolicyMetrics
    steps: tuple[AllocationTrajectoryStep, ...]
    research_scope: Literal["LOCAL_RETROSPECTIVE_RESEARCH"]
    historical_test_read: Literal[False]
    fresh_oos_read: Literal[False]
    promotion_allowed: Literal[False]


__all__ = [
    "AllocationPolicyKind",
    "AllocationPolicyMetrics",
    "AllocationPolicyTrajectory",
    "AllocationTrajectoryStep",
]
