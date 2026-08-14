"""Deterministic replay engine for a contaminated 60-score-day window."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from .daily_market_allocation_contract import AllocationAction
from .daily_market_allocation_transition import execute_allocation_transition
from .daily_market_existing_db_sim_contract import (
    ExistingDbSimulationMetrics,
    ExistingDbSimulationStep,
    SimulationPolicyKind,
    SimulationScenario,
)
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_rl_dataset import MarketDay, TrainScoreScale
from .daily_market_rl_trajectory import build_model_observation
from .daily_market_transition_contract import MarketTransitionConfig, build_market_state


class ExistingDbDecisionPolicy(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def policy_kind(self) -> SimulationPolicyKind: ...

    @property
    def seed(self) -> int | None: ...

    def action(
        self, observation: tuple[float, ...], day: MarketDay
    ) -> AllocationAction: ...


class ActionDelegate(Protocol):
    def action(
        self, observation: tuple[float, ...], day: MarketDay
    ) -> AllocationAction: ...


@dataclass(frozen=True, slots=True)
class ConstantSimulationPolicy:
    name: str
    policy_kind: SimulationPolicyKind
    selected_action: AllocationAction
    seed: int | None = None

    def action(
        self, observation: tuple[float, ...], day: MarketDay
    ) -> AllocationAction:
        _ = observation, day
        return self.selected_action


@dataclass(frozen=True, slots=True)
class RandomSimulationPolicy:
    name: str
    seed: int
    policy_kind: SimulationPolicyKind = "RANDOM"

    def action(
        self, observation: tuple[float, ...], day: MarketDay
    ) -> AllocationAction:
        _ = observation
        payload = f"UNIFORM_RANDOM_FOUR_ACTIONS_V1:{self.seed}:{day.decision_date}"
        value = int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big")
        return AllocationAction(value % 4)


@dataclass(frozen=True, slots=True)
class DateActionSimulationPolicy:
    name: str
    seed: int
    actions: dict[date, AllocationAction]
    policy_kind: SimulationPolicyKind = "SHUFFLE"

    def action(
        self, observation: tuple[float, ...], day: MarketDay
    ) -> AllocationAction:
        _ = observation
        try:
            return self.actions[day.decision_date]
        except KeyError as error:
            raise DailyMarketRlContractError(
                "HISTORICAL_SIMULATION_ACTION_DATE_MISSING",
                day.decision_date.isoformat(),
            ) from error


@dataclass(frozen=True, slots=True)
class NamedModelPolicy:
    name: str
    seed: int
    delegate: ActionDelegate
    policy_kind: SimulationPolicyKind = "RL"

    def action(
        self, observation: tuple[float, ...], day: MarketDay
    ) -> AllocationAction:
        return self.delegate.action(observation, day)


def select_non_overlapping_window_days(
    days: tuple[MarketDay, ...],
) -> tuple[MarketDay, ...]:
    """Keep chronological decisions only after the prior position has exited."""
    selected: list[MarketDay] = []
    previous_exit: date | None = None
    for day in sorted(days, key=lambda value: value.decision_date):
        if previous_exit is None or previous_exit <= day.decision_date:
            selected.append(day)
            previous_exit = day.exit_date
    if not selected:
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_DAYS_MISSING")
    return tuple(selected)


def simulate_existing_db_policy(
    days: tuple[MarketDay, ...],
    scale: TrainScoreScale,
    policy: ExistingDbDecisionPolicy,
    *,
    scenario: SimulationScenario,
    config: MarketTransitionConfig,
) -> tuple[ExistingDbSimulationMetrics, tuple[ExistingDbSimulationStep, ...]]:
    """Replay one policy on the already-consumed window with full accounting."""
    selected = select_non_overlapping_window_days(days)
    initial_nav = config.initial_capital_krw
    nav = initial_nav
    peak = nav
    exposure = Decimal("0")
    drawdown = Decimal("0")
    steps: list[ExistingDbSimulationStep] = []
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
            config=config,
        )
        accounting = result.accounting
        steps.append(
            ExistingDbSimulationStep(
                policy=policy.name,
                policy_kind=policy.policy_kind,
                seed=policy.seed,
                scenario=scenario,
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
    frozen = tuple(steps)
    counts = tuple(
        sum(step.action == action.name for step in frozen)
        for action in AllocationAction
    )
    if len(counts) != 4 or sum(counts) != len(frozen):
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_ACTION_COUNT_INVALID")
    final_nav = frozen[-1].final_nav_krw
    cost_bps = int(config.round_trip_cost_percent * Decimal("100"))
    if cost_bps not in (23, 46):
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_COST_INVALID")
    metrics = ExistingDbSimulationMetrics(
        policy=policy.name,
        policy_kind=policy.policy_kind,
        seed=policy.seed,
        scenario=scenario,
        round_trip_cost_bps=cost_bps,
        decision_count=len(frozen),
        initial_nav_krw=float(initial_nav),
        final_nav_krw=final_nav,
        net_return_percent=((final_nav / float(initial_nav)) - 1.0) * 100.0,
        max_drawdown_percent=min(step.drawdown_percent for step in frozen),
        total_cost_krw=sum(step.total_cost_krw for step in frozen),
        turnover=sum(step.deployed_at_entry_krw for step in frozen)
        / float(initial_nav),
        action_counts=(counts[0], counts[1], counts[2], counts[3]),
        distinct_action_count=sum(value > 0 for value in counts),
        cumulative_reward=sum(step.reward_log_nav for step in frozen),
    )
    expected_reward = math.log(metrics.final_nav_krw / metrics.initial_nav_krw)
    if not math.isclose(
        metrics.cumulative_reward, expected_reward, rel_tol=0.0, abs_tol=1e-12
    ):
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_REWARD_MISMATCH")
    return metrics, frozen


def paired_shuffle_policy(
    policy_name: str,
    seed: int,
    steps: tuple[ExistingDbSimulationStep, ...],
) -> DateActionSimulationPolicy:
    """Permute a CQL action vector deterministically while preserving its histogram."""
    dates = tuple(step.decision_date for step in steps)
    actions = tuple(AllocationAction[step.action] for step in steps)
    order = tuple(
        sorted(
            range(len(actions)),
            key=lambda index: hashlib.sha256(
                f"PAIRED_ACTION_SHUFFLE_V1:{seed}:{index}".encode()
            ).digest(),
        )
    )
    return DateActionSimulationPolicy(
        name=policy_name,
        seed=seed,
        actions={day: actions[order[index]] for index, day in enumerate(dates)},
    )


__all__ = [
    "ConstantSimulationPolicy",
    "DateActionSimulationPolicy",
    "ExistingDbDecisionPolicy",
    "NamedModelPolicy",
    "RandomSimulationPolicy",
    "paired_shuffle_policy",
    "select_non_overlapping_window_days",
    "simulate_existing_db_policy",
]
