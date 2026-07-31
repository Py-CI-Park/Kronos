from dataclasses import replace

import pytest

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d6_gate import (
    D6Evaluation,
    D6GateEvidenceError,
    D6GateThresholds,
    evaluate_d6_gate,
)


def _metrics(accuracy: float, reward_ratio: float, total_reward: float) -> D3Metrics:
    return D3Metrics(accuracy, reward_ratio, total_reward, 1.0, 0.7, 0.3, 0)


def _passing_matrix() -> tuple[D6Evaluation, ...]:
    return tuple(
        D6Evaluation(
            reward_arm=arm,
            seed=seed,
            metrics=_metrics(0.35 + seed * 0.01, 0.25 + seed * 0.01, 0.30 + seed * 0.01)
            if arm == "NATIVE"
            else _metrics(0.16, -0.05, -0.06),
            maximum_drawdown=0.08 if arm == "NATIVE" else 0.12,
        )
        for arm in ("NATIVE", "SHUFFLED")
        for seed in range(3)
    )


def _thresholds() -> D6GateThresholds:
    return D6GateThresholds(0.2, 0.0, 0.0, 0.1, 2 / 3, 0.25, True)


def test_d6_gate_confirms_exact_positive_native_matrix() -> None:
    # Given
    evaluations = _passing_matrix()

    # When
    gate = evaluate_d6_gate(evaluations, thresholds=_thresholds())

    # Then
    assert gate.verdict == "D6_REUSED_VALIDATION_CONFIRMED"
    assert gate.native_passing_seed_fraction == 1.0
    assert gate.native_reward_delta_vs_shuffled == pytest.approx(0.31)


def test_d6_gate_fails_closed_when_one_model_is_missing() -> None:
    # Given
    evaluations = _passing_matrix()[:-1]

    # When / Then
    with pytest.raises(D6GateEvidenceError):
        _ = evaluate_d6_gate(evaluations, thresholds=_thresholds())


def test_d6_gate_rejects_native_reward_collapse() -> None:
    # Given
    evaluations = tuple(
        replace(row, metrics=_metrics(0.22, -0.01, -0.02))
        if row.reward_arm == "NATIVE"
        else row
        for row in _passing_matrix()
    )

    # When
    gate = evaluate_d6_gate(evaluations, thresholds=_thresholds())

    # Then
    assert gate.verdict == "D6_REUSED_VALIDATION_NOT_CONFIRMED"
