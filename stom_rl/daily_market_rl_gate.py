"""Preregistered economic gate for actual-market CQL historical TEST."""

from __future__ import annotations

import random
from statistics import median
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from .daily_market_rl_contract import (
    MODEL_SEEDS,
    DailyMarketRlContractError,
    MarketAlgorithm,
)
from .daily_market_rl_evaluation import MarketPolicyMetrics


class SeedOutcome(BaseModel):
    """Historical TEST policy results for one algorithm seed."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    algorithm: MarketAlgorithm
    seed: int = Field(ge=0)
    historical_test_base: MarketPolicyMetrics
    historical_test_stress: MarketPolicyMetrics


class SeedBootstrapInterval(BaseModel):
    """Fixed-seed 95% bootstrap interval over five seed returns."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    estimate: float
    low: float
    high: float
    resamples: Literal[5000]
    bootstrap_seed: Literal[20260809]


class EconomicGateCheck(BaseModel):
    """One immutable preregistered pass/fail claim."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    passed: bool
    observed: str


class EconomicGateResult(BaseModel):
    """Complete historical economic verdict without promotion authority."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: Literal["kronos_daily_market_economic_gate.v1"]
    verdict: Literal[
        "PASS_HISTORICAL_RESEARCH_ONLY",
        "NO_GO_HISTORICAL_ECONOMIC_GATE",
    ]
    checks: tuple[EconomicGateCheck, ...]
    failed_checks: tuple[str, ...]
    best_control_return_percent: float
    cql_base_median_return_percent: float
    cql_stress_median_return_percent: float
    reward_shuffled_median_return_percent: float
    action_shuffled_median_return_percent: float
    cql_seed_bootstrap_95: SeedBootstrapInterval
    promotion_blockers: tuple[str, ...]
    promotion_allowed: Literal[False]
    fresh_oos_read: Literal[False]


def _validate_outcomes(
    rows: tuple[SeedOutcome, ...],
    algorithm: MarketAlgorithm,
) -> None:
    if len(rows) != len(MODEL_SEEDS):
        raise DailyMarketRlContractError("GATE_REQUIRES_FIVE_SEEDS", algorithm.value)
    if tuple(sorted(row.seed for row in rows)) != MODEL_SEEDS:
        raise DailyMarketRlContractError("GATE_MODEL_SEEDS_MISMATCH", algorithm.value)
    if any(row.algorithm is not algorithm for row in rows):
        raise DailyMarketRlContractError("GATE_ALGORITHM_MISMATCH", algorithm.value)
    if any(
        row.historical_test_base.split != "TEST"
        or row.historical_test_stress.split != "TEST"
        for row in rows
    ):
        raise DailyMarketRlContractError("GATE_REQUIRES_HISTORICAL_TEST")


def _bootstrap(values: tuple[float, ...]) -> SeedBootstrapInterval:
    generator = random.Random(20260809)
    estimates = sorted(
        median(generator.choice(values) for _ in values)
        for _ in range(5_000)
    )
    return SeedBootstrapInterval(
        estimate=median(values),
        low=estimates[int((len(estimates) - 1) * 0.025)],
        high=estimates[int((len(estimates) - 1) * 0.975)],
        resamples=5000,
        bootstrap_seed=20260809,
    )


def evaluate_economic_gate(
    native_cql: tuple[SeedOutcome, ...],
    reward_shuffled_cql: tuple[SeedOutcome, ...],
    action_shuffled_cql: tuple[SeedOutcome, ...],
    controls: tuple[MarketPolicyMetrics, ...],
) -> EconomicGateResult:
    """Evaluate all seven checks exactly once over historical TEST results."""
    _validate_outcomes(native_cql, MarketAlgorithm.CQL)
    _validate_outcomes(reward_shuffled_cql, MarketAlgorithm.CQL_REWARD_SHUFFLED)
    _validate_outcomes(action_shuffled_cql, MarketAlgorithm.CQL_ACTION_SHUFFLED)
    if not controls or any(row.split != "TEST" for row in controls):
        raise DailyMarketRlContractError("GATE_TEST_CONTROLS_MISSING")
    native_returns = tuple(row.historical_test_base.net_return_percent for row in native_cql)
    stress_returns = tuple(row.historical_test_stress.net_return_percent for row in native_cql)
    reward_shuffled_returns = tuple(
        row.historical_test_base.net_return_percent
        for row in reward_shuffled_cql
    )
    action_shuffled_returns = tuple(
        row.historical_test_base.net_return_percent
        for row in action_shuffled_cql
    )
    best_control = max(row.net_return_percent for row in controls)
    native_median = median(native_returns)
    stress_median = median(stress_returns)
    reward_shuffled_median = median(reward_shuffled_returns)
    action_shuffled_median = median(action_shuffled_returns)
    confidence = _bootstrap(native_returns)
    seed_wins = sum(value > best_control for value in native_returns)
    diverse_seeds = sum(
        0.1 <= row.historical_test_base.invest_action_rate <= 0.9
        for row in native_cql
    )
    drawdown_passed = all(
        row.historical_test_base.max_drawdown_percent >= -20.0
        for row in native_cql
    )
    checks = (
        EconomicGateCheck(
            check_id="CQL_MEDIAN_BEATS_ZERO_AND_BEST_CONTROL",
            passed=native_median > max(0.0, best_control),
            observed=f"median={native_median:.6f},best_control={best_control:.6f}",
        ),
        EconomicGateCheck(
            check_id="CQL_FOUR_OF_FIVE_BEAT_BEST_CONTROL",
            passed=seed_wins >= 4,
            observed=f"seed_wins={seed_wins}/5",
        ),
        EconomicGateCheck(
            check_id="CQL_BOOTSTRAP_LOW_POSITIVE",
            passed=confidence.low > 0.0,
            observed=f"low={confidence.low:.6f}",
        ),
        EconomicGateCheck(
            check_id="CQL_STRESS_MEDIAN_POSITIVE",
            passed=stress_median > 0.0,
            observed=f"median={stress_median:.6f}",
        ),
        EconomicGateCheck(
            check_id="CQL_MAX_DRAWDOWN_WITHIN_20_PERCENT",
            passed=drawdown_passed,
            observed=f"worst={min(row.historical_test_base.max_drawdown_percent for row in native_cql):.6f}",
        ),
        EconomicGateCheck(
            check_id="CQL_ACTION_DIVERSITY",
            passed=diverse_seeds >= 4,
            observed=f"diverse_seeds={diverse_seeds}/5",
        ),
        EconomicGateCheck(
            check_id="CQL_BEATS_SHUFFLED_CONTROLS",
            passed=(
                native_median > reward_shuffled_median
                and native_median > action_shuffled_median
            ),
            observed=(
                f"native={native_median:.6f},reward_shuffle={reward_shuffled_median:.6f},"
                f"action_shuffle={action_shuffled_median:.6f}"
            ),
        ),
    )
    failed = tuple(check.check_id for check in checks if not check.passed)
    verdict = (
        "PASS_HISTORICAL_RESEARCH_ONLY"
        if not failed
        else "NO_GO_HISTORICAL_ECONOMIC_GATE"
    )
    return EconomicGateResult(
        schema_version="kronos_daily_market_economic_gate.v1",
        verdict=verdict,
        checks=checks,
        failed_checks=failed,
        best_control_return_percent=best_control,
        cql_base_median_return_percent=native_median,
        cql_stress_median_return_percent=stress_median,
        reward_shuffled_median_return_percent=reward_shuffled_median,
        action_shuffled_median_return_percent=action_shuffled_median,
        cql_seed_bootstrap_95=confidence,
        promotion_blockers=(
            "D0_PRICE_BASIS_NOT_VERIFIED",
            "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED",
            "FRESH_OOS_NOT_RUN_NO_READ",
        ),
        promotion_allowed=False,
        fresh_oos_read=False,
    )


__all__ = [
    "EconomicGateCheck",
    "EconomicGateResult",
    "SeedBootstrapInterval",
    "SeedOutcome",
    "evaluate_economic_gate",
]
