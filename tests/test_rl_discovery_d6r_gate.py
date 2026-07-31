from dataclasses import replace

import pytest

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d6r_gate import (
    D6RGateError,
    D6RGateThresholds,
    D6RUnitOutcome,
    evaluate_d6r_gate,
)


THRESHOLDS = D6RGateThresholds(0.2, 0.0, 0.0, 0.1, 0.8, 2 / 3, 0.65, 0.15, 0.25, True)


def _metrics(
    *,
    accuracy: float,
    reward_ratio: float,
    total_reward: float,
    trade_rate: float,
) -> D3Metrics:
    return D3Metrics(accuracy, reward_ratio, total_reward, 1.0, trade_rate, 0.4, 0)


def _matrix(*, primary_trade_rate: float = 0.4) -> tuple[D6RUnitOutcome, ...]:
    rows: list[D6RUnitOutcome] = []
    for profile in ("COST_ONLY", "TURNOVER_10BP"):
        for arm in ("NATIVE", "SHUFFLED"):
            for seed in range(3):
                for fold_id in range(5):
                    native = arm == "NATIVE"
                    primary = profile == "TURNOVER_10BP"
                    metrics = _metrics(
                        accuracy=0.4 if native else 0.15,
                        reward_ratio=0.5 if native else -0.1,
                        total_reward=0.5 if native else -0.1,
                        trade_rate=(primary_trade_rate if primary else 0.8) if native else 0.5,
                    )
                    rows.append(
                        D6RUnitOutcome(
                            profile,
                            arm,
                            seed,
                            fold_id,
                            metrics,
                            replace(metrics, reward_ratio=metrics.reward_ratio + 0.05),
                            0.1,
                        )
                    )
    return tuple(rows)


def test_d6r_gate_accepts_only_a_stable_low_churn_primary_profile() -> None:
    # Given
    outcomes = _matrix()

    # When
    gate = evaluate_d6r_gate(outcomes, thresholds=THRESHOLDS)

    # Then
    assert gate.verdict == "D6R_TRAIN_FALSIFICATION_CANDIDATE"
    assert gate.positive_fold_fraction == 1.0
    assert gate.positive_seed_fraction == 1.0
    assert gate.trade_rate_reduction_vs_cost_only == pytest.approx(0.4)
    assert gate.passed_gate_count == gate.total_gate_count == 10


def test_d6r_gate_rejects_churn_even_when_rewards_are_positive() -> None:
    # Given
    outcomes = _matrix(primary_trade_rate=0.9)

    # When
    gate = evaluate_d6r_gate(outcomes, thresholds=THRESHOLDS)

    # Then
    assert gate.verdict == "D6R_TRAIN_FALSIFICATION_NOT_CONFIRMED"
    assert gate.native_median_reward_ratio == 0.5
    assert gate.native_median_trade_rate == 0.9
    assert gate.passed_gate_count == 8


def test_d6r_gate_rejects_an_incomplete_or_duplicate_matrix() -> None:
    # Given
    outcomes = _matrix()

    # When / Then
    with pytest.raises(D6RGateError):
        evaluate_d6r_gate(outcomes[:-1], thresholds=THRESHOLDS)
    with pytest.raises(D6RGateError):
        evaluate_d6r_gate((*outcomes[:-1], outcomes[0]), thresholds=THRESHOLDS)
