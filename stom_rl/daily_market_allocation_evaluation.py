"""Validation-only replay and metrics for four-action allocation policies."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import fmean
from typing import ClassVar, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .daily_market_allocation_contract import (
    AllocationAction,
    AllocationActionName,
)
from .daily_market_allocation_transition import execute_allocation_transition
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_rl_dataset import MarketDay, TrainScoreScale
from .daily_market_rl_trajectory import (
    build_model_observation,
    select_non_overlapping_days,
)
from .daily_market_transition_contract import (
    MarketTransitionConfig,
    SplitName,
    build_market_state,
)

AllocationPolicyKind = Literal["CONTROL", "RL"]


class AllocationDecisionPolicy(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def policy_kind(self) -> AllocationPolicyKind: ...

    def action(
        self,
        observation: tuple[float, ...],
        day: MarketDay,
    ) -> AllocationAction: ...


@dataclass(frozen=True, slots=True)
class ConstantAllocationPolicy:
    name: str
    selected_action: AllocationAction
    policy_kind: Literal["CONTROL"] = "CONTROL"

    def action(
        self,
        observation: tuple[float, ...],
        day: MarketDay,
    ) -> AllocationAction:
        _ = observation, day
        return self.selected_action


class AllocationTrajectoryStep(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    decision_date: str
    action: AllocationActionName
    final_nav_krw: float = Field(gt=0)
    deployed_at_entry_krw: float = Field(ge=0)
    total_cost_krw: float = Field(ge=0)
    reward_log_nav: float
    drawdown_percent: float = Field(ge=-100, le=0)
    filled_slots: int = Field(ge=0, le=10)


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


def _action_counts(
    steps: tuple[AllocationTrajectoryStep, ...],
) -> tuple[int, int, int, int]:
    return (
        sum(row.action == "CASH" for row in steps),
        sum(row.action == "INVEST_TOP3_EQUAL_SLOT" for row in steps),
        sum(row.action == "INVEST_TOP5_EQUAL_SLOT" for row in steps),
        sum(row.action == "INVEST_TOP10_EQUAL_SLOT" for row in steps),
    )


def simulate_allocation_policy(
    days: tuple[MarketDay, ...],
    scale: TrainScoreScale,
    policy: AllocationDecisionPolicy,
    *,
    split: SplitName,
    cost_config: MarketTransitionConfig,
) -> AllocationPolicyTrajectory:
    """Replay one fixed policy on TRAIN or VALIDATION without reading TEST."""
    if split not in ("TRAIN", "VALIDATION"):
        raise DailyMarketRlContractError("ALLOCATION_SCREEN_FORBIDS_TEST", split)
    selected = select_non_overlapping_days(days, split=split)
    if not selected:
        raise DailyMarketRlContractError("ALLOCATION_EVALUATION_DAYS_MISSING", split)
    initial_nav = cost_config.initial_capital_krw
    nav = initial_nav
    peak = nav
    exposure = Decimal("0")
    drawdown = Decimal("0")
    steps: list[AllocationTrajectoryStep] = []
    for day in selected:
        observation = build_model_observation(
            day,
            scale,
            previous_exposure_ratio=exposure,
            previous_drawdown=drawdown,
        )
        state = build_market_state(
            day.score_day.scores,
            feature_vector=day.state_day.feature_vector,
            previous_exposure_ratio=exposure,
            previous_drawdown=drawdown,
        )
        result = execute_allocation_transition(
            state,
            day.candidates,
            policy.action(observation, day),
            previous_nav_krw=nav,
            previous_peak_nav_krw=peak,
            config=cost_config,
        )
        accounting = result.accounting
        steps.append(
            AllocationTrajectoryStep(
                decision_date=day.decision_date.isoformat(),
                action=result.executed_action,
                final_nav_krw=float(accounting.final_nav_krw),
                deployed_at_entry_krw=float(accounting.deployed_at_entry_krw),
                total_cost_krw=float(accounting.total_cost_krw),
                reward_log_nav=float(accounting.reward_log_nav),
                drawdown_percent=float(accounting.drawdown_fraction * 100),
                filled_slots=accounting.filled_slots,
            )
        )
        nav = accounting.final_nav_krw
        peak = accounting.peak_nav_krw
        exposure = accounting.deployed_at_entry_krw / accounting.previous_nav_krw
        drawdown = accounting.drawdown_fraction
    frozen_steps = tuple(steps)
    counts = _action_counts(frozen_steps)
    final_nav = frozen_steps[-1].final_nav_krw
    rewards = tuple(row.reward_log_nav for row in frozen_steps)
    metrics = AllocationPolicyMetrics(
        policy=policy.name,
        policy_kind=policy.policy_kind,
        split=split,
        round_trip_cost_percent=float(cost_config.round_trip_cost_percent),
        date_count=len(frozen_steps),
        initial_nav_krw=float(initial_nav),
        final_nav_krw=final_nav,
        total_net_pnl_krw=final_nav - float(initial_nav),
        net_return_percent=((final_nav / float(initial_nav)) - 1.0) * 100.0,
        max_drawdown_percent=min(row.drawdown_percent for row in frozen_steps),
        action_cash_count=counts[0],
        action_top3_count=counts[1],
        action_top5_count=counts[2],
        action_top10_count=counts[3],
        distinct_action_count=sum(value > 0 for value in counts),
        filled_slots=sum(row.filled_slots for row in frozen_steps),
        total_cost_krw=sum(row.total_cost_krw for row in frozen_steps),
        turnover=(
            sum(row.deployed_at_entry_krw for row in frozen_steps) / float(initial_nav)
        ),
        mean_reward=fmean(rewards),
        cumulative_reward=sum(rewards),
    )
    return AllocationPolicyTrajectory(
        metrics=metrics,
        steps=frozen_steps,
        research_scope="LOCAL_RETROSPECTIVE_RESEARCH",
        historical_test_read=False,
        fresh_oos_read=False,
        promotion_allowed=False,
    )


__all__ = [
    "AllocationDecisionPolicy",
    "AllocationPolicyMetrics",
    "AllocationPolicyTrajectory",
    "AllocationTrajectoryStep",
    "ConstantAllocationPolicy",
    "simulate_allocation_policy",
]
