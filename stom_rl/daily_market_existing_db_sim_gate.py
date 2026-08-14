"""Technical-only gate for contaminated existing-DB simulation metrics."""

from __future__ import annotations

from statistics import median

from .daily_market_existing_db_sim_contract import (
    ExistingDbSimulationGate,
    ExistingDbSimulationGateCheck,
    ExistingDbSimulationMetrics,
)
from .daily_market_rl_contract import DailyMarketRlContractError


def build_existing_db_simulation_gate(
    metrics: tuple[ExistingDbSimulationMetrics, ...],
) -> ExistingDbSimulationGate:
    """Compare fixed CQL seeds with no-trade/rule/random and paired shuffle."""
    cql_base = tuple(
        row
        for row in metrics
        if row.policy_kind == "RL" and row.scenario == "BASE_23BP"
    )
    cql_stress = tuple(
        row
        for row in metrics
        if row.policy_kind == "RL" and row.scenario == "STRESS_46BP"
    )
    base_controls = tuple(
        row
        for row in metrics
        if row.policy_kind in {"CONTROL", "RULE", "RANDOM"}
        and row.scenario == "BASE_23BP"
    )
    base_shuffles = tuple(
        row
        for row in metrics
        if row.policy_kind == "SHUFFLE" and row.scenario == "BASE_23BP"
    )
    if not (
        len(cql_base) == len(cql_stress) == len(base_shuffles) == 5
        and len(base_controls) == 7
    ):
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_GATE_MATRIX_INVALID")
    cql_base_median = median(row.net_return_percent for row in cql_base)
    cql_stress_median = median(row.net_return_percent for row in cql_stress)
    best_control = max(row.net_return_percent for row in base_controls)
    shuffle_median = median(row.net_return_percent for row in base_shuffles)
    wins = sum(row.net_return_percent > best_control for row in cql_base)
    worst_mdd = min(row.max_drawdown_percent for row in cql_base)
    checks = (
        ExistingDbSimulationGateCheck(
            check_id="CQL_MEDIAN_BEATS_ZERO_AND_BEST_CONTROL",
            passed=cql_base_median > max(0.0, best_control),
            observed=f"median={cql_base_median:.6f},best_control={best_control:.6f}",
        ),
        ExistingDbSimulationGateCheck(
            check_id="CQL_FOUR_OF_FIVE_BEAT_BEST_CONTROL",
            passed=wins >= 4,
            observed=f"seed_wins={wins}/5",
        ),
        ExistingDbSimulationGateCheck(
            check_id="CQL_STRESS_MEDIAN_POSITIVE",
            passed=cql_stress_median > 0.0,
            observed=f"median={cql_stress_median:.6f}",
        ),
        ExistingDbSimulationGateCheck(
            check_id="CQL_MAX_DRAWDOWN_WITHIN_20_PERCENT",
            passed=worst_mdd >= -20.0,
            observed=f"worst={worst_mdd:.6f}",
        ),
        ExistingDbSimulationGateCheck(
            check_id="CQL_BEATS_PAIRED_ACTION_SHUFFLE",
            passed=cql_base_median > shuffle_median,
            observed=f"cql={cql_base_median:.6f},shuffle={shuffle_median:.6f}",
        ),
    )
    return ExistingDbSimulationGate(
        technical_gate_passed=all(check.passed for check in checks),
        checks=checks,
        failed_checks=tuple(check.check_id for check in checks if not check.passed),
        cql_base_median_return_percent=cql_base_median,
        cql_stress_median_return_percent=cql_stress_median,
        best_base_control_return_percent=best_control,
        paired_shuffle_base_median_return_percent=shuffle_median,
    )


__all__ = ["build_existing_db_simulation_gate"]
