"""Semantic ledger and replay validation for daily-market allocation bundles."""

from __future__ import annotations

from pydantic import ValidationError

from stom_rl.daily_market_allocation_evaluation import summarize_allocation_steps
from stom_rl.daily_market_allocation_experiment_contract import (
    AllocationExperimentReceipt,
    LabeledAllocationTrajectory,
)
from stom_rl.daily_market_allocation_rl_contract import AllocationAlgorithm
from stom_rl.daily_market_allocation_telemetry import (
    AllocationValidationReplayEvent,
    build_validation_replay_events,
)
from stom_rl.daily_market_rl_contract import DailyMarketRlContractError


def allocation_streams_are_canonical(
    receipt: AllocationExperimentReceipt,
    ledger_payload: bytes,
    telemetry_payload: bytes,
) -> bool:
    try:
        ledger_lines = ledger_payload.decode("utf-8").splitlines()
        telemetry_lines = telemetry_payload.decode("utf-8").splitlines()
        if any(not line.strip() for line in (*ledger_lines, *telemetry_lines)):
            return False
        trajectories = tuple(
            LabeledAllocationTrajectory.model_validate_json(line)
            for line in ledger_lines
        )
        events = tuple(
            AllocationValidationReplayEvent.model_validate_json(line)
            for line in telemetry_lines
        )
    except (UnicodeDecodeError, ValidationError):
        return False
    expected_keys = tuple(
        (algorithm, seed, scenario)
        for algorithm in AllocationAlgorithm
        for seed in range(5)
        for scenario in ("BASE_0_230_PERCENT", "STRESS_0_460_PERCENT")
    )
    if (
        tuple((row.algorithm, row.seed, row.scenario) for row in trajectories)
        != expected_keys
    ):
        return False
    models = {(row.algorithm, row.seed): row for row in receipt.model_runs}
    try:
        for row in trajectories:
            model = models[(row.algorithm, row.seed)]
            expected_metrics = (
                model.validation_base
                if row.scenario == "BASE_0_230_PERCENT"
                else model.validation_stress
            )
            observed_metrics = summarize_allocation_steps(
                policy=row.trajectory.metrics.policy,
                policy_kind=row.trajectory.metrics.policy_kind,
                split=row.trajectory.metrics.split,
                round_trip_cost_percent=(
                    row.trajectory.metrics.round_trip_cost_percent
                ),
                initial_nav_krw=receipt.initial_capital_krw,
                steps=row.trajectory.steps,
            )
            if observed_metrics != expected_metrics:
                return False
        expected_events = build_validation_replay_events(
            trajectories,
            median_return_percent=(
                receipt.validation_gate.cql_base_median_return_percent
            ),
        )
    except (DailyMarketRlContractError, KeyError):
        return False
    return events == expected_events and bool(events)


__all__ = ["allocation_streams_are_canonical"]
