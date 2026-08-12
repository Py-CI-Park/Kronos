"""Preregistered validation-only gate for four-action DQN/CQL screening."""

from __future__ import annotations

from statistics import median
from typing import ClassVar, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .daily_market_allocation_evaluation_contract import AllocationPolicyMetrics
from .daily_market_allocation_rl_contract import (
    ALLOCATION_MODEL_SEEDS,
    AllocationAlgorithm,
)
from .daily_market_rl_contract import DailyMarketRlContractError

ALLOCATION_GATE_CHECK_IDS: Final = (
    "CQL_VALIDATION_MEDIAN_BEATS_NO_TRADE",
    "CQL_VALIDATION_FOUR_OF_FIVE_POSITIVE",
    "CQL_VALIDATION_STRESS_MEDIAN_POSITIVE",
    "CQL_VALIDATION_ACTION_DIVERSITY",
    "CQL_VALIDATION_BEATS_DQN_MEDIAN",
    "CQL_VALIDATION_MDD_WITHIN_20_PERCENT",
)


class AllocationSeedOutcome(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    algorithm: AllocationAlgorithm
    seed: int = Field(ge=0)
    validation_base: AllocationPolicyMetrics
    validation_stress: AllocationPolicyMetrics


class AllocationGateCheck(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    passed: bool
    observed: str


class AllocationValidationGate(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
    )

    schema_version: Literal["kronos_daily_market_allocation_gate.v1"]
    verdict: Literal["VALIDATION_CANDIDATE", "NO_GO_VALIDATION_SCREEN"]
    checks: tuple[AllocationGateCheck, ...]
    failed_checks: tuple[str, ...]
    dqn_base_median_return_percent: float
    cql_base_median_return_percent: float
    cql_stress_median_return_percent: float
    historical_test_read: Literal[False]
    fresh_oos_read: Literal[False]
    promotion_allowed: Literal[False]

    @model_validator(mode="after")
    def _gate_verdict_is_canonical(self) -> Self:
        check_ids = tuple(check.check_id for check in self.checks)
        if check_ids != ALLOCATION_GATE_CHECK_IDS:
            raise ValueError("allocation gate check set or order is invalid")
        failed = tuple(check.check_id for check in self.checks if not check.passed)
        if self.failed_checks != failed:
            raise ValueError("allocation gate failed checks are inconsistent")
        expected = "VALIDATION_CANDIDATE" if not failed else "NO_GO_VALIDATION_SCREEN"
        if self.verdict != expected:
            raise ValueError("allocation gate verdict is inconsistent")
        return self


def _validate(
    rows: tuple[AllocationSeedOutcome, ...],
    algorithm: AllocationAlgorithm,
) -> None:
    if len(rows) != len(ALLOCATION_MODEL_SEEDS):
        raise DailyMarketRlContractError(
            "ALLOCATION_GATE_REQUIRES_FIVE_SEEDS",
            algorithm.value,
        )
    if tuple(sorted(row.seed for row in rows)) != ALLOCATION_MODEL_SEEDS:
        raise DailyMarketRlContractError(
            "ALLOCATION_GATE_SEEDS_MISMATCH",
            algorithm.value,
        )
    if any(row.algorithm is not algorithm for row in rows):
        raise DailyMarketRlContractError(
            "ALLOCATION_GATE_ALGORITHM_MISMATCH",
            algorithm.value,
        )
    if any(
        row.validation_base.split != "VALIDATION"
        or row.validation_stress.split != "VALIDATION"
        for row in rows
    ):
        raise DailyMarketRlContractError("ALLOCATION_GATE_FORBIDS_NON_VALIDATION")


def evaluate_allocation_validation_gate(
    dqn: tuple[AllocationSeedOutcome, ...],
    cql: tuple[AllocationSeedOutcome, ...],
) -> AllocationValidationGate:
    """Evaluate six fixed screening checks without opening historical TEST."""
    _validate(dqn, AllocationAlgorithm.DQN)
    _validate(cql, AllocationAlgorithm.CQL)
    dqn_median = median(row.validation_base.net_return_percent for row in dqn)
    cql_returns = tuple(row.validation_base.net_return_percent for row in cql)
    stress_returns = tuple(row.validation_stress.net_return_percent for row in cql)
    cql_median = median(cql_returns)
    stress_median = median(stress_returns)
    positive_seeds = sum(value > 0 for value in cql_returns)
    diverse_seeds = sum(row.validation_base.distinct_action_count >= 3 for row in cql)
    worst_drawdown = min(row.validation_base.max_drawdown_percent for row in cql)
    checks = (
        AllocationGateCheck(
            check_id="CQL_VALIDATION_MEDIAN_BEATS_NO_TRADE",
            passed=cql_median > 0,
            observed=f"median={cql_median:.6f}",
        ),
        AllocationGateCheck(
            check_id="CQL_VALIDATION_FOUR_OF_FIVE_POSITIVE",
            passed=positive_seeds >= 4,
            observed=f"positive_seeds={positive_seeds}/5",
        ),
        AllocationGateCheck(
            check_id="CQL_VALIDATION_STRESS_MEDIAN_POSITIVE",
            passed=stress_median > 0,
            observed=f"median={stress_median:.6f}",
        ),
        AllocationGateCheck(
            check_id="CQL_VALIDATION_ACTION_DIVERSITY",
            passed=diverse_seeds >= 4,
            observed=f"diverse_seeds={diverse_seeds}/5",
        ),
        AllocationGateCheck(
            check_id="CQL_VALIDATION_BEATS_DQN_MEDIAN",
            passed=cql_median > dqn_median,
            observed=f"cql={cql_median:.6f},dqn={dqn_median:.6f}",
        ),
        AllocationGateCheck(
            check_id="CQL_VALIDATION_MDD_WITHIN_20_PERCENT",
            passed=worst_drawdown >= -20,
            observed=f"worst={worst_drawdown:.6f}",
        ),
    )
    failed = tuple(check.check_id for check in checks if not check.passed)
    return AllocationValidationGate(
        schema_version="kronos_daily_market_allocation_gate.v1",
        verdict="VALIDATION_CANDIDATE" if not failed else "NO_GO_VALIDATION_SCREEN",
        checks=checks,
        failed_checks=failed,
        dqn_base_median_return_percent=dqn_median,
        cql_base_median_return_percent=cql_median,
        cql_stress_median_return_percent=stress_median,
        historical_test_read=False,
        fresh_oos_read=False,
        promotion_allowed=False,
    )


__all__ = [
    "AllocationGateCheck",
    "ALLOCATION_GATE_CHECK_IDS",
    "AllocationSeedOutcome",
    "AllocationValidationGate",
    "evaluate_allocation_validation_gate",
]
