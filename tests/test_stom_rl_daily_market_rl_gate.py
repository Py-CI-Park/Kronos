from __future__ import annotations

from stom_rl.daily_market_rl_contract import MarketAlgorithm
from stom_rl.daily_market_rl_evaluation import MarketPolicyMetrics
from stom_rl.daily_market_rl_gate import SeedOutcome, evaluate_economic_gate


def _metrics(
    policy: str,
    net_return_percent: float,
    *,
    action_rate: float = 0.5,
    drawdown_percent: float = -5.0,
) -> MarketPolicyMetrics:
    return MarketPolicyMetrics(
        policy=policy,
        policy_kind="RL" if "CQL" in policy else "CONTROL",
        split="TEST",
        round_trip_cost_percent=0.23,
        date_count=20,
        initial_nav_krw=60_000_000.0,
        final_nav_krw=60_000_000.0 * (1.0 + net_return_percent / 100.0),
        total_net_pnl_krw=600_000.0 * net_return_percent,
        net_return_percent=net_return_percent,
        max_drawdown_percent=drawdown_percent,
        invest_action_count=round(action_rate * 20),
        invest_action_rate=action_rate,
        filled_slots=round(action_rate * 200),
        total_cost_krw=100_000.0,
        turnover=action_rate * 10.0,
        mean_reward=net_return_percent / 2_000.0,
        cumulative_reward=net_return_percent / 100.0,
    )


def _outcomes(
    algorithm: MarketAlgorithm,
    returns: tuple[float, ...],
    *,
    stress_offset: float = -1.0,
    action_rate: float = 0.5,
) -> tuple[SeedOutcome, ...]:
    return tuple(
        SeedOutcome(
            algorithm=algorithm,
            seed=seed,
            historical_test_base=_metrics(algorithm.value, value, action_rate=action_rate),
            historical_test_stress=_metrics(
                algorithm.value,
                value + stress_offset,
                action_rate=action_rate,
            ),
        )
        for seed, value in enumerate(returns)
    )


def _controls() -> tuple[MarketPolicyMetrics, ...]:
    return (
        _metrics("NO_TRADE", 0.0, action_rate=0.0, drawdown_percent=0.0),
        _metrics("ALWAYS_INVEST", -2.0, action_rate=1.0),
        _metrics("COST_AWARE_MOMENTUM_RULE", -1.0, action_rate=1.0),
    )


def test_gate_passes_only_when_native_cql_clears_every_preregistered_check() -> None:
    # Given: robust positive CQL seeds and clearly inferior shuffled controls.
    native = _outcomes(MarketAlgorithm.CQL, (5.0, 6.0, 7.0, 8.0, 9.0))
    reward_shuffled = _outcomes(
        MarketAlgorithm.CQL_REWARD_SHUFFLED,
        (-3.0, -2.0, -1.0, 0.0, 1.0),
    )
    action_shuffled = _outcomes(
        MarketAlgorithm.CQL_ACTION_SHUFFLED,
        (-2.0, -1.0, 0.0, 1.0, 2.0),
    )

    # When: the immutable seven-part economic gate is evaluated.
    gate = evaluate_economic_gate(native, reward_shuffled, action_shuffled, _controls())

    # Then: historical research passes, while promotion and Fresh OOS stay locked.
    assert gate.verdict == "PASS_HISTORICAL_RESEARCH_ONLY"
    assert all(check.passed for check in gate.checks)
    assert gate.failed_checks == ()
    assert gate.promotion_allowed is False
    assert gate.fresh_oos_read is False


def test_gate_rejects_degenerate_cash_policy_and_nonpositive_stress_return() -> None:
    # Given: CQL collapses to cash and fails to beat shuffled arms after costs.
    native = _outcomes(
        MarketAlgorithm.CQL,
        (0.0, 0.0, 0.0, 0.0, 0.0),
        stress_offset=0.0,
        action_rate=0.0,
    )
    reward_shuffled = _outcomes(MarketAlgorithm.CQL_REWARD_SHUFFLED, (0.0,) * 5)
    action_shuffled = _outcomes(MarketAlgorithm.CQL_ACTION_SHUFFLED, (0.0,) * 5)

    # When: the same preregistered gate is evaluated.
    gate = evaluate_economic_gate(native, reward_shuffled, action_shuffled, _controls())

    # Then: the result is explicit NO-GO with the concrete failed check IDs.
    assert gate.verdict == "NO_GO_HISTORICAL_ECONOMIC_GATE"
    assert "CQL_MEDIAN_BEATS_ZERO_AND_BEST_CONTROL" in gate.failed_checks
    assert "CQL_STRESS_MEDIAN_POSITIVE" in gate.failed_checks
    assert "CQL_ACTION_DIVERSITY" in gate.failed_checks
    assert "CQL_BEATS_SHUFFLED_CONTROLS" in gate.failed_checks
