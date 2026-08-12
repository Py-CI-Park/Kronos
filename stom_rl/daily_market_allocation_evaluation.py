"""Validation-only replay and metrics for four-action allocation policies."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import fmean
from typing import Literal, Protocol

from .daily_market_allocation_contract import AllocationAction
from .daily_market_allocation_evaluation_contract import (
    AllocationPolicyKind,
    AllocationPolicyMetrics,
    AllocationPolicyTrajectory,
    AllocationTrajectoryStep,
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


def summarize_allocation_steps(
    *,
    policy: str,
    policy_kind: AllocationPolicyKind,
    split: SplitName,
    round_trip_cost_percent: float,
    initial_nav_krw: float,
    steps: tuple[AllocationTrajectoryStep, ...],
) -> AllocationPolicyMetrics:
    """Recompute metrics while verifying sequential reward and drawdown accounting."""
    if not steps:
        raise DailyMarketRlContractError("ALLOCATION_EVALUATION_STEPS_MISSING")
    previous_nav = initial_nav_krw
    peak_nav = initial_nav_krw
    previous_decision: date | None = None
    previous_exit: date | None = None
    for step in steps:
        if not (
            step.decision_date < step.entry_date < step.exit_date
            and (previous_decision is None or previous_decision < step.decision_date)
            and (previous_exit is None or previous_exit <= step.decision_date)
        ):
            raise DailyMarketRlContractError("ALLOCATION_STEP_TIME_ORDER_INVALID")
        expected_reward = math.log(step.final_nav_krw / previous_nav)
        peak_nav = max(peak_nav, step.final_nav_krw)
        expected_drawdown = ((step.final_nav_krw / peak_nav) - 1.0) * 100.0
        if not math.isclose(
            step.reward_log_nav, expected_reward, rel_tol=0.0, abs_tol=1e-12
        ) or not math.isclose(
            step.drawdown_percent,
            expected_drawdown,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise DailyMarketRlContractError("ALLOCATION_STEP_ACCOUNTING_MISMATCH")
        previous_nav = step.final_nav_krw
        previous_decision = step.decision_date
        previous_exit = step.exit_date
    counts = _action_counts(steps)
    final_nav = steps[-1].final_nav_krw
    rewards = tuple(row.reward_log_nav for row in steps)
    return AllocationPolicyMetrics(
        policy=policy,
        policy_kind=policy_kind,
        split=split,
        round_trip_cost_percent=round_trip_cost_percent,
        date_count=len(steps),
        initial_nav_krw=initial_nav_krw,
        final_nav_krw=final_nav,
        total_net_pnl_krw=final_nav - initial_nav_krw,
        net_return_percent=((final_nav / initial_nav_krw) - 1.0) * 100.0,
        max_drawdown_percent=min(row.drawdown_percent for row in steps),
        action_cash_count=counts[0],
        action_top3_count=counts[1],
        action_top5_count=counts[2],
        action_top10_count=counts[3],
        distinct_action_count=sum(value > 0 for value in counts),
        filled_slots=sum(row.filled_slots for row in steps),
        total_cost_krw=sum(row.total_cost_krw for row in steps),
        turnover=sum(row.deployed_at_entry_krw for row in steps) / initial_nav_krw,
        mean_reward=fmean(rewards),
        cumulative_reward=sum(rewards),
    )


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
                decision_date=day.decision_date,
                entry_date=day.entry_date,
                exit_date=day.exit_date,
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
    metrics = summarize_allocation_steps(
        policy=policy.name,
        policy_kind=policy.policy_kind,
        split=split,
        round_trip_cost_percent=float(cost_config.round_trip_cost_percent),
        initial_nav_krw=float(initial_nav),
        steps=frozen_steps,
    )
    return AllocationPolicyTrajectory(
        metrics=metrics,
        steps=frozen_steps,
        research_scope="LOCAL_RETROSPECTIVE_RESEARCH",
        historical_test_read=False,
        fresh_oos_read=False,
        promotion_allowed=False,
    )
