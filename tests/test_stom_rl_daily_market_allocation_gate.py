from __future__ import annotations

from stom_rl.daily_market_allocation_evaluation_contract import AllocationPolicyMetrics
from stom_rl.daily_market_allocation_gate import (
    AllocationSeedOutcome,
    evaluate_allocation_validation_gate,
)
from stom_rl.daily_market_allocation_rl_contract import AllocationAlgorithm


def _metrics(
    policy: str,
    net_return_percent: float,
    *,
    distinct_actions: int = 3,
    max_drawdown_percent: float = -5.0,
) -> AllocationPolicyMetrics:
    return AllocationPolicyMetrics(
        policy=policy,
        policy_kind="RL",
        split="VALIDATION",
        round_trip_cost_percent=0.230,
        date_count=20,
        initial_nav_krw=60_000_000.0,
        final_nav_krw=60_000_000.0 * (1.0 + net_return_percent / 100.0),
        total_net_pnl_krw=600_000.0 * net_return_percent,
        net_return_percent=net_return_percent,
        max_drawdown_percent=max_drawdown_percent,
        action_cash_count=5 if distinct_actions >= 1 else 0,
        action_top3_count=5 if distinct_actions >= 2 else 0,
        action_top5_count=5 if distinct_actions >= 3 else 0,
        action_top10_count=5 if distinct_actions >= 4 else 0,
        distinct_action_count=distinct_actions,
        filled_slots=100,
        total_cost_krw=100_000.0,
        turnover=2.0,
        mean_reward=0.001,
        cumulative_reward=0.02,
    )


def _outcomes(
    algorithm: AllocationAlgorithm,
    base_returns: tuple[float, ...],
    stress_returns: tuple[float, ...],
    *,
    distinct_actions: int = 3,
) -> tuple[AllocationSeedOutcome, ...]:
    return tuple(
        AllocationSeedOutcome(
            algorithm=algorithm,
            seed=seed,
            validation_base=_metrics(
                f"{algorithm.value}-{seed}",
                base_returns[seed],
                distinct_actions=distinct_actions,
            ),
            validation_stress=_metrics(
                f"{algorithm.value}-{seed}",
                stress_returns[seed],
                distinct_actions=distinct_actions,
            ),
        )
        for seed in range(5)
    )


def test_validation_candidate_requires_all_six_preregistered_checks() -> None:
    # Given: five DQN seeds and five CQL seeds satisfying the validation screen.
    dqn = _outcomes(AllocationAlgorithm.DQN, (0.2, 0.3, 0.4, 0.5, 0.6), (0.1,) * 5)
    cql = _outcomes(AllocationAlgorithm.CQL, (1.0, 1.1, 1.2, 1.3, 1.4), (0.2,) * 5)

    # When: the preregistered validation-only gate is evaluated.
    result = evaluate_allocation_validation_gate(dqn, cql)

    # Then: candidate status still forbids TEST access and promotion.
    assert result.verdict == "VALIDATION_CANDIDATE"
    assert all(check.passed for check in result.checks)
    assert tuple(check.check_id for check in result.checks) == (
        "CQL_VALIDATION_MEDIAN_BEATS_NO_TRADE",
        "CQL_VALIDATION_FOUR_OF_FIVE_POSITIVE",
        "CQL_VALIDATION_STRESS_MEDIAN_POSITIVE",
        "CQL_VALIDATION_ACTION_DIVERSITY",
        "CQL_VALIDATION_BEATS_DQN_MEDIAN",
        "CQL_VALIDATION_MDD_WITHIN_20_PERCENT",
    )
    assert result.historical_test_read is False
    assert result.promotion_allowed is False


def test_validation_screen_reports_economic_and_action_failures() -> None:
    # Given: CQL loses money and collapses to one action.
    dqn = _outcomes(AllocationAlgorithm.DQN, (0.1,) * 5, (0.05,) * 5)
    cql = _outcomes(
        AllocationAlgorithm.CQL,
        (-1.0,) * 5,
        (-2.0,) * 5,
        distinct_actions=1,
    )

    # When: the same fixed screen is evaluated.
    result = evaluate_allocation_validation_gate(dqn, cql)

    # Then: it fails closed with exact failed checks.
    assert result.verdict == "NO_GO_VALIDATION_SCREEN"
    assert "CQL_VALIDATION_MEDIAN_BEATS_NO_TRADE" in result.failed_checks
    assert "CQL_VALIDATION_STRESS_MEDIAN_POSITIVE" in result.failed_checks
    assert "CQL_VALIDATION_ACTION_DIVERSITY" in result.failed_checks
    assert "CQL_VALIDATION_BEATS_DQN_MEDIAN" in result.failed_checks
