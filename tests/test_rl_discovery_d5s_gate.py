from dataclasses import replace

import pytest

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d5s_gate import (
    D5SBaseline,
    D5SCheckpointOutcome,
    D5SGateError,
    evaluate_d5s_stability_gate,
    select_global_checkpoint,
)

CHECKPOINTS = (50_000, 100_000, 150_000, 200_000, 300_000, 400_000)


def _metrics(accuracy: float, reward_ratio: float) -> D3Metrics:
    return D3Metrics(accuracy, reward_ratio, reward_ratio, 1.0, 0.8, 0.4, 0)


def _passing_matrix() -> tuple[D5SCheckpointOutcome, ...]:
    rows: list[D5SCheckpointOutcome] = []
    native_reward = {50_000: 0.82, 100_000: 0.86, 150_000: 0.89, 200_000: 0.91, 300_000: 0.90, 400_000: 0.88}
    for arm in ("NATIVE", "SHUFFLED"):
        for seed in range(3):
            for steps in CHECKPOINTS:
                reward = native_reward[steps] + seed * 0.01 if arm == "NATIVE" else 0.10 + seed * 0.01
                accuracy = 0.73 + seed * 0.01 if arm == "NATIVE" else 0.20
                rows.append(D5SCheckpointOutcome(arm, seed, steps, _metrics(accuracy, reward)))
    return tuple(rows)


def test_d5s_gate_selects_one_global_checkpoint_and_confirms_stability() -> None:
    outcomes = _passing_matrix()
    baselines = tuple(D5SBaseline(seed, 0.71, 0.87) for seed in range(3))

    gate = evaluate_d5s_stability_gate(outcomes, baselines)

    assert gate.verdict == "D5S_STABILITY_CONFIRMED"
    assert gate.selected_steps == 200_000
    assert gate.preserved_native_seed_fraction == 1.0
    assert gate.reward_ratio_degradation_at_400k == pytest.approx(0.03)


def test_d5s_selection_uses_accuracy_then_earliest_for_reward_ties() -> None:
    outcomes = _passing_matrix()
    tied = tuple(
        replace(row, native_23bp=_metrics(0.74 if row.total_steps == 150_000 else 0.73, 0.91))
        if row.reward_arm == "NATIVE" and row.total_steps in {150_000, 200_000}
        else row
        for row in outcomes
    )

    assert select_global_checkpoint(tied) == 150_000


def test_d5s_gate_fails_closed_when_one_checkpoint_is_missing() -> None:
    outcomes = _passing_matrix()[:-1]
    baselines = tuple(D5SBaseline(seed, 0.71, 0.87) for seed in range(3))

    with pytest.raises(D5SGateError):
        evaluate_d5s_stability_gate(outcomes, baselines)


def test_d5s_gate_preserves_no_go_when_selected_model_misses_baseline() -> None:
    outcomes = tuple(
        replace(row, native_23bp=_metrics(0.60, 0.70)) if row.reward_arm == "NATIVE" else row
        for row in _passing_matrix()
    )
    baselines = tuple(D5SBaseline(seed, 0.71, 0.87) for seed in range(3))

    gate = evaluate_d5s_stability_gate(outcomes, baselines)

    assert gate.verdict == "D5S_STABILITY_NOT_CONFIRMED"
