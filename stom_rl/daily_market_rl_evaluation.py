"""Costed controls and policy replay for actual-market offline RL."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import fmean
from typing import ClassVar, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_rl_dataset import MarketDay, TrainScoreScale
from .daily_market_rl_trajectory import build_model_observation, select_non_overlapping_days
from .daily_market_transition import execute_binary_transition
from .daily_market_transition_contract import (
    ActionName,
    BinaryAction,
    MarketTransitionConfig,
    SplitName,
    build_market_state,
)

PolicyKind = Literal["CONTROL", "RULE", "RL"]


class MarketDecisionPolicy(Protocol):
    """Minimal policy surface shared by rules, controls, and learned Q policies."""

    @property
    def name(self) -> str: ...

    @property
    def policy_kind(self) -> PolicyKind: ...

    def action(self, observation: tuple[float, ...], day: MarketDay) -> BinaryAction: ...


@dataclass(frozen=True, slots=True)
class ConstantMarketPolicy:
    """Deterministic no-trade or always-invest control."""

    name: str
    selected_action: BinaryAction
    policy_kind: Literal["CONTROL"] = "CONTROL"

    def action(self, observation: tuple[float, ...], day: MarketDay) -> BinaryAction:
        _ = observation, day
        return self.selected_action


@dataclass(frozen=True, slots=True)
class CostAwareMomentumPolicy:
    """Non-RL rule using only reconstructed causal five-day returns."""

    name: str
    train_mean: float
    train_scaling_denominator: float
    threshold_fraction: float
    policy_kind: Literal["RULE"] = "RULE"

    def action(self, observation: tuple[float, ...], day: MarketDay) -> BinaryAction:
        _ = observation
        five_day_returns = tuple(
            self.train_mean
            + day.state_day.feature_vector[(slot * 16) + 2] * self.train_scaling_denominator
            for slot in range(10)
        )
        return (
            BinaryAction.INVEST_TOP10_EQUAL_SLOT
            if fmean(five_day_returns) > self.threshold_fraction
            else BinaryAction.CASH
        )


class MarketTrajectoryStep(BaseModel):
    """One observable action and costed accounting result."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    decision_date: str
    action: ActionName
    final_nav_krw: float = Field(gt=0)
    deployed_at_entry_krw: float = Field(ge=0)
    total_cost_krw: float = Field(ge=0)
    reward_log_nav: float
    drawdown_percent: float = Field(ge=-100, le=0)
    filled_slots: int = Field(ge=0, le=10)


class MarketPolicyMetrics(BaseModel):
    """Bounded scalar summary suitable for the dashboard evidence catalog."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    policy: str
    policy_kind: PolicyKind
    split: SplitName
    round_trip_cost_percent: float = Field(ge=0)
    date_count: int = Field(gt=0)
    initial_nav_krw: float = Field(gt=0)
    final_nav_krw: float = Field(gt=0)
    total_net_pnl_krw: float
    net_return_percent: float
    max_drawdown_percent: float = Field(ge=-100, le=0)
    invest_action_count: int = Field(ge=0)
    invest_action_rate: float = Field(ge=0, le=1)
    filled_slots: int = Field(ge=0)
    total_cost_krw: float = Field(ge=0)
    turnover: float = Field(ge=0)
    mean_reward: float
    cumulative_reward: float


class MarketPolicyTrajectory(BaseModel):
    """Full auditable replay plus its compact metrics."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    metrics: MarketPolicyMetrics
    steps: tuple[MarketTrajectoryStep, ...]
    research_scope: Literal["LOCAL_RETROSPECTIVE_RESEARCH"]
    promotion_allowed: Literal[False]
    fresh_oos_read: Literal[False]


def simulate_policy(
    days: tuple[MarketDay, ...],
    scale: TrainScoreScale,
    policy: MarketDecisionPolicy,
    *,
    split: SplitName,
    cost_config: MarketTransitionConfig,
) -> MarketPolicyTrajectory:
    """Replay one fixed policy without overlapping unresolved positions."""
    selected = select_non_overlapping_days(days, split=split)
    if not selected:
        raise DailyMarketRlContractError("POLICY_EVALUATION_DAYS_MISSING", split)
    initial_nav = cost_config.initial_capital_krw
    nav = initial_nav
    peak = nav
    exposure = Decimal("0")
    drawdown = Decimal("0")
    steps: list[MarketTrajectoryStep] = []
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
        result = execute_binary_transition(
            state,
            day.candidates,
            policy.action(observation, day),
            previous_nav_krw=nav,
            previous_peak_nav_krw=peak,
            config=cost_config,
        )
        steps.append(
            MarketTrajectoryStep(
                decision_date=day.decision_date.isoformat(),
                action=result.executed_action,
                final_nav_krw=float(result.final_nav_krw),
                deployed_at_entry_krw=float(result.deployed_at_entry_krw),
                total_cost_krw=float(result.total_cost_krw),
                reward_log_nav=float(result.reward_log_nav),
                drawdown_percent=float(result.drawdown_fraction * 100),
                filled_slots=result.filled_slots,
            )
        )
        nav = result.final_nav_krw
        peak = result.peak_nav_krw
        exposure = result.deployed_at_entry_krw / result.previous_nav_krw
        drawdown = result.drawdown_fraction
    invest_count = sum(step.action == "INVEST_TOP10_EQUAL_SLOT" for step in steps)
    total_deployed = sum(step.deployed_at_entry_krw for step in steps)
    total_cost = sum(step.total_cost_krw for step in steps)
    rewards = tuple(step.reward_log_nav for step in steps)
    final_nav = steps[-1].final_nav_krw
    metrics = MarketPolicyMetrics(
        policy=policy.name,
        policy_kind=policy.policy_kind,
        split=split,
        round_trip_cost_percent=float(cost_config.round_trip_cost_percent),
        date_count=len(steps),
        initial_nav_krw=float(initial_nav),
        final_nav_krw=final_nav,
        total_net_pnl_krw=final_nav - float(initial_nav),
        net_return_percent=((final_nav / float(initial_nav)) - 1.0) * 100.0,
        max_drawdown_percent=min(step.drawdown_percent for step in steps),
        invest_action_count=invest_count,
        invest_action_rate=invest_count / len(steps),
        filled_slots=sum(step.filled_slots for step in steps),
        total_cost_krw=total_cost,
        turnover=total_deployed / float(initial_nav),
        mean_reward=fmean(rewards),
        cumulative_reward=sum(rewards),
    )
    return MarketPolicyTrajectory(
        metrics=metrics,
        steps=tuple(steps),
        research_scope="LOCAL_RETROSPECTIVE_RESEARCH",
        promotion_allowed=False,
        fresh_oos_read=False,
    )


__all__ = [
    "ConstantMarketPolicy",
    "CostAwareMomentumPolicy",
    "MarketDecisionPolicy",
    "MarketPolicyMetrics",
    "MarketPolicyTrajectory",
    "MarketTrajectoryStep",
    "PolicyKind",
    "simulate_policy",
]
