from __future__ import annotations

from pathlib import Path

from stom_rl.rl_discovery.d2_contract import D2ArmId, load_d2_prereg_bytes
from stom_rl.rl_discovery.d2_gates import D2Outcome, evaluate_d2_gate
from stom_rl.rl_discovery.d2_training import D2Metrics


PREREG = Path(__file__).resolve().parents[1] / "docs" / "kronos_rl_discovery_type2_d2_prereg_2026-07-28.json"


def _metrics(ratio: float) -> D2Metrics:
    return D2Metrics(1.0, ratio, ratio, 1.0, 0.5, 0.5, 0)


def test_d2_gate_confirms_full_capacity_but_never_promotes() -> None:
    outcomes = tuple(
        D2Outcome(
            arm,
            count,
            seed,
            _metrics(1.0),
            _metrics(1.0 if arm is D2ArmId.NATIVE else 0.0),
            _metrics(0.5),
        )
        for count in (1, 8, 32, 128)
        for arm in D2ArmId
        for seed in (0, 1, 2)
    )
    prereg = load_d2_prereg_bytes(PREREG.read_bytes())

    result = evaluate_d2_gate(outcomes, thresholds=prereg.gate)

    assert result.verdict == "D2_HISTORICAL_CAPACITY_CONFIRMED"
    assert result.maximum_confirmed_episode_count == 128
    assert result.train_only_signal_separation
    assert not result.promotion_allowed


def test_d2_gate_requires_native_separation_for_capacity_verdict() -> None:
    outcomes = tuple(
        D2Outcome(arm, count, seed, _metrics(1.0), _metrics(1.0), _metrics(1.0))
        for count in (1, 8, 32, 128)
        for arm in D2ArmId
        for seed in (0, 1, 2)
    )
    prereg = load_d2_prereg_bytes(PREREG.read_bytes())

    result = evaluate_d2_gate(outcomes, thresholds=prereg.gate)

    assert result.maximum_confirmed_episode_count == 128
    assert not result.train_only_signal_separation
    assert result.verdict == "D2_HISTORICAL_CAPACITY_NOT_CONFIRMED"
