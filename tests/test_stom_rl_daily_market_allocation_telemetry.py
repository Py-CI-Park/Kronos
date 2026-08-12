from __future__ import annotations

import json
from datetime import date
from typing import Literal

import pytest
from pydantic import ValidationError

from stom_rl.daily_market_allocation_evaluation import (
    summarize_allocation_steps,
)
from stom_rl.daily_market_allocation_evaluation_contract import (
    AllocationPolicyMetrics,
    AllocationPolicyTrajectory,
    AllocationTrajectoryStep,
)
from stom_rl.daily_market_allocation_experiment_contract import (
    LabeledAllocationTrajectory,
)
from stom_rl.daily_market_allocation_rl_contract import AllocationAlgorithm
from stom_rl.daily_market_allocation_telemetry import (
    AllocationValidationReplayEvent,
    build_validation_replay_events,
)
from stom_rl.daily_market_rl_contract import DailyMarketRlContractError


def _trajectory(
    seed: int,
    net_return_percent: float,
    *,
    scenario: Literal[
        "BASE_0_230_PERCENT", "STRESS_0_460_PERCENT"
    ] = "BASE_0_230_PERCENT",
) -> LabeledAllocationTrajectory:
    steps = (
        AllocationTrajectoryStep(
            decision_date=date(2026, 1, 2),
            entry_date=date(2026, 1, 5),
            exit_date=date(2026, 1, 6),
            action="CASH",
            final_nav_krw=60_000_000.0,
            deployed_at_entry_krw=0.0,
            total_cost_krw=0.0,
            reward_log_nav=0.0,
            drawdown_percent=0.0,
            filled_slots=0,
        ),
        AllocationTrajectoryStep(
            decision_date=date(2026, 1, 5),
            entry_date=date(2026, 1, 6),
            exit_date=date(2026, 1, 7),
            action="INVEST_TOP5_EQUAL_SLOT",
            final_nav_krw=60_600_000.0,
            deployed_at_entry_krw=25_000_000.0,
            total_cost_krw=57_500.0,
            reward_log_nav=0.009950330853168092,
            drawdown_percent=0.0,
            filled_slots=5,
        ),
    )
    metrics = AllocationPolicyMetrics(
        policy=f"CQL-{seed}",
        policy_kind="RL",
        split="VALIDATION",
        round_trip_cost_percent=0.230,
        date_count=2,
        initial_nav_krw=60_000_000.0,
        final_nav_krw=60_600_000.0,
        total_net_pnl_krw=600_000.0,
        net_return_percent=net_return_percent,
        max_drawdown_percent=0.0,
        action_cash_count=1,
        action_top3_count=0,
        action_top5_count=1,
        action_top10_count=0,
        distinct_action_count=2,
        filled_slots=5,
        total_cost_krw=57_500.0,
        turnover=25_000_000.0 / 60_000_000.0,
        mean_reward=sum(step.reward_log_nav for step in steps) / len(steps),
        cumulative_reward=sum(step.reward_log_nav for step in steps),
    )
    return LabeledAllocationTrajectory(
        algorithm=AllocationAlgorithm.CQL,
        seed=seed,
        scenario=scenario,
        trajectory=AllocationPolicyTrajectory(
            metrics=metrics,
            steps=steps,
            research_scope="LOCAL_RETROSPECTIVE_RESEARCH",
            historical_test_read=False,
            fresh_oos_read=False,
            promotion_allowed=False,
        ),
    )


def test_validation_replay_uses_cql_median_seed_with_declared_metric_semantics() -> (
    None
):
    # Given: base trajectories surround the preregistered CQL median return.
    trajectories = (
        _trajectory(0, 1.0),
        _trajectory(1, 2.0),
        _trajectory(2, 3.0),
        _trajectory(1, 1.5, scenario="STRESS_0_460_PERCENT"),
    )

    # When: dashboard telemetry is derived from the exact median base trajectory.
    events = build_validation_replay_events(
        trajectories,
        median_return_percent=2.0,
    )

    # Then: every point says this is historical validation replay, not live training.
    assert len(events) == 2
    assert tuple(event.global_step for event in events) == (1, 2)
    assert all(event.algorithm == "CQL" and event.seed == 1 for event in events)
    assert all(event.phase == "VALIDATION_REPLAY" for event in events)
    assert all(event.telemetry_live_stream is False for event in events)
    assert events[1].action_name == "INVEST_TOP5_EQUAL_SLOT"
    assert events[1].equity == 60_600_000.0
    assert events[1].info.reward_kind == "raw_reward"
    assert events[1].info.reward_unit == "fraction"
    assert events[1].info.equity_kind == "krw_nav"
    assert events[1].info.equity_unit == "krw"
    assert events[1].info.action_recorded is True
    assert events[1].decision_timestamp.isoformat() == "2026-01-05T15:30:00+09:00"
    assert events[1].reward_observed_at.isoformat() == "2026-01-07T09:00:00+09:00"
    assert events[1].timestamp == events[1].reward_observed_at
    assert json.loads(events[1].model_dump_json())["loss"] is None


def test_validation_replay_fails_closed_when_median_trajectory_is_missing() -> None:
    with pytest.raises(
        DailyMarketRlContractError,
        match="ALLOCATION_MEDIAN_CQL_TRAJECTORY_MISSING",
    ):
        _ = build_validation_replay_events(
            (_trajectory(0, 1.0),),
            median_return_percent=2.0,
        )


def test_validation_replay_rejects_naive_or_noncausal_timestamps() -> None:
    event = build_validation_replay_events(
        (_trajectory(0, 1.0),),
        median_return_percent=1.0,
    )[0]
    naive = event.model_dump(mode="json")
    naive["decision_timestamp"] = "2026-01-02T15:30:00"
    with pytest.raises(ValidationError, match="KST-aware"):
        _ = AllocationValidationReplayEvent.model_validate(naive)
    noncausal = event.model_dump(mode="json")
    noncausal["decision_timestamp"] = noncausal["reward_observed_at"]
    with pytest.raises(ValidationError, match="not causal"):
        _ = AllocationValidationReplayEvent.model_validate(noncausal)


def test_trajectory_step_rejects_non_dates() -> None:
    with pytest.raises(ValidationError):
        _ = AllocationTrajectoryStep.model_validate(
            {
                "decision_date": "a",
                "entry_date": "b",
                "exit_date": "c",
                "action": "CASH",
                "final_nav_krw": 60_000_000,
                "deployed_at_entry_krw": 0,
                "total_cost_krw": 0,
                "reward_log_nav": 0,
                "drawdown_percent": 0,
                "filled_slots": 0,
            }
        )


@pytest.mark.parametrize(
    ("action", "filled_slots", "deployed", "cost"),
    (
        ("CASH", 0, 0.0, 1.0),
        ("INVEST_TOP3_EQUAL_SLOT", 0, 0.0, 1.0),
        ("INVEST_TOP3_EQUAL_SLOT", 4, 20_000_000.0, 1.0),
        ("INVEST_TOP5_EQUAL_SLOT", 1, 0.0, 1.0),
        ("INVEST_TOP10_EQUAL_SLOT", 1, 5_000_000.0, 0.0),
    ),
)
def test_trajectory_step_rejects_impossible_action_accounting(
    action: str,
    filled_slots: int,
    deployed: float,
    cost: float,
) -> None:
    with pytest.raises(ValidationError, match="allocation"):
        _ = AllocationTrajectoryStep.model_validate(
            {
                "decision_date": "2026-01-02",
                "entry_date": "2026-01-05",
                "exit_date": "2026-01-06",
                "action": action,
                "final_nav_krw": 60_000_000,
                "deployed_at_entry_krw": deployed,
                "total_cost_krw": cost,
                "reward_log_nav": 0,
                "drawdown_percent": 0,
                "filled_slots": filled_slots,
            }
        )


def test_trajectory_summary_rejects_overlapping_positions() -> None:
    first = AllocationTrajectoryStep(
        decision_date=date(2026, 1, 2),
        entry_date=date(2026, 1, 5),
        exit_date=date(2026, 1, 7),
        action="CASH",
        final_nav_krw=60_000_000,
        deployed_at_entry_krw=0,
        total_cost_krw=0,
        reward_log_nav=0,
        drawdown_percent=0,
        filled_slots=0,
    )
    second = first.model_copy(
        update={
            "decision_date": date(2026, 1, 6),
            "entry_date": date(2026, 1, 7),
            "exit_date": date(2026, 1, 8),
        }
    )

    with pytest.raises(
        DailyMarketRlContractError,
        match="ALLOCATION_STEP_TIME_ORDER_INVALID",
    ):
        _ = summarize_allocation_steps(
            policy="CASH",
            policy_kind="CONTROL",
            split="VALIDATION",
            round_trip_cost_percent=0.23,
            initial_nav_krw=60_000_000,
            steps=(first, second),
        )
