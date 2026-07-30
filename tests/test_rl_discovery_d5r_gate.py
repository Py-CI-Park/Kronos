from __future__ import annotations

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d5r_gate import (
    D5RBaseline,
    D5RCapacityOutcome,
    evaluate_d5r_capacity_gate,
)


def _metrics(accuracy: float, reward_ratio: float) -> D3Metrics:
    return D3Metrics(accuracy, reward_ratio, reward_ratio, 1.0, 0.5, 0.5, 0)


def test_d5r_capacity_gate_confirms_exact_registered_matrix() -> None:
    baselines = tuple(D5RBaseline(seed, 0.70, 0.86) for seed in range(3))
    outcomes = tuple(
        D5RCapacityOutcome(
            arm,
            seed,
            steps,
            _metrics(
                0.72 if steps == 400_000 else (0.75 if arm == "NATIVE" else 0.20),
                0.87 if steps == 400_000 else (0.90 if arm == "NATIVE" else -0.10),
            ),
        )
        for arm in ("NATIVE", "SHUFFLED")
        for seed in range(3)
        for steps in (400_000, 800_000)
    )

    gate = evaluate_d5r_capacity_gate(outcomes, baselines)

    assert gate.verdict == "D5R_CAPACITY_CONFIRMED"
    assert gate.native_accuracy_lift >= 0.03
    assert gate.native_reward_ratio_lift >= 0.02
    assert gate.native_reward_delta_vs_shuffled >= 0.2
    assert gate.improving_seed_fraction == 1.0


def test_d5r_capacity_gate_rejects_missing_checkpoint() -> None:
    baselines = tuple(D5RBaseline(seed, 0.70, 0.86) for seed in range(3))
    outcomes = tuple(
        D5RCapacityOutcome(arm, seed, steps, _metrics(0.75, 0.90))
        for arm in ("NATIVE", "SHUFFLED")
        for seed in range(3)
        for steps in (400_000, 800_000)
    )[:-1]

    try:
        _ = evaluate_d5r_capacity_gate(outcomes, baselines)
    except ValueError:
        return
    raise AssertionError("missing D5R checkpoint must fail closed")
