from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from stom_rl.rl_discovery.gates import ArmOutcome, evaluate_discovery_gate
from stom_rl.rl_discovery.lifecycle import (
    DiscoveryLifecycle,
    LifecycleIntegrityError,
    TerminalRunError,
)

PREREG_SHA = "a" * 64
FIXTURE_SHA = "b" * 64


def _record(lifecycle: DiscoveryLifecycle) -> None:
    outcome = ArmOutcome(
        arm="A_PPO_ONLY",
        seed=0,
        training_timesteps=256,
        oracle_reward_ratio=0.75,
        exact_basket_accuracy=0.5,
        invalid_action_count=0,
        block_count=0,
        no_fill_count=0,
        dominant_action_rate=1.0,
        shuffled_reward=False,
    )
    model_dir = lifecycle.run_dir / "models" / outcome.arm / "seed-0"
    model_dir.mkdir(parents=True)
    _ = (model_dir / "model.zip").write_bytes(b"model")
    _ = (model_dir / "normalizer.pkl").write_bytes(b"normalizer")
    lifecycle.record(outcome)


def _start(tmp_path: Path, *, run_id: str, profile: str, expected: tuple[str, ...]) -> DiscoveryLifecycle:
    return DiscoveryLifecycle.start(
        tmp_path,
        run_id=run_id,
        experiment_id="TYPE2-D0",
        profile=profile,
        prereg_sha256=PREREG_SHA,
        fixture_sha256=FIXTURE_SHA,
        expected_runs=expected,
    )


def test_lifecycle_cannot_terminalize_until_every_expected_run_is_recorded(tmp_path: Path) -> None:
    lifecycle = _start(
        tmp_path,
        run_id="type2-d0-primary-incomplete",
        profile="PRIMARY",
        expected=("A_PPO_ONLY:0", "B_BC_THEN_PPO:0"),
    )
    _record(lifecycle)

    with pytest.raises(LifecycleIntegrityError, match="every expected"):
        lifecycle.complete(evaluate_discovery_gate(lifecycle.outcomes, profile="PRIMARY"))


def test_lifecycle_rejects_terminal_gate_for_another_profile(tmp_path: Path) -> None:
    lifecycle = _start(
        tmp_path,
        run_id="type2-d0-primary-wrong-gate",
        profile="PRIMARY",
        expected=("A_PPO_ONLY:0",),
    )
    _record(lifecycle)

    with pytest.raises(LifecycleIntegrityError, match="gate_status"):
        lifecycle.complete(evaluate_discovery_gate(lifecycle.outcomes, profile="SMOKE"))


def test_lifecycle_rejects_caller_forged_verdict(tmp_path: Path) -> None:
    lifecycle = _start(
        tmp_path,
        run_id="type2-d0-smoke-forged-gate",
        profile="SMOKE",
        expected=("A_PPO_ONLY:0",),
    )
    _record(lifecycle)
    computed = evaluate_discovery_gate(lifecycle.outcomes, profile="SMOKE")

    with pytest.raises(LifecycleIntegrityError, match="recomputed"):
        lifecycle.complete(replace(computed, verdict="FORGED_GO"))


@pytest.mark.parametrize("tamper", ["modify", "delete"])
def test_terminalization_reverifies_recorded_model_bundle(tmp_path: Path, tamper: str) -> None:
    lifecycle = _start(
        tmp_path,
        run_id=f"type2-d0-smoke-tampered-{tamper}",
        profile="SMOKE",
        expected=("A_PPO_ONLY:0",),
    )
    _record(lifecycle)
    model_path = lifecycle.run_dir / "models" / "A_PPO_ONLY" / "seed-0" / "model.zip"
    if tamper == "modify":
        _ = model_path.write_bytes(b"tampered")
    else:
        model_path.unlink()

    with pytest.raises(LifecycleIntegrityError):
        lifecycle.complete(evaluate_discovery_gate(lifecycle.outcomes, profile="SMOKE"))


def test_terminal_receipt_makes_resume_immutable(tmp_path: Path) -> None:
    lifecycle = _start(
        tmp_path,
        run_id="type2-d0-smoke-immutable",
        profile="SMOKE",
        expected=("A_PPO_ONLY:0",),
    )
    _record(lifecycle)
    lifecycle.complete(evaluate_discovery_gate(lifecycle.outcomes, profile="SMOKE"))

    with pytest.raises(TerminalRunError, match="immutable"):
        _ = DiscoveryLifecycle.resume(
            lifecycle.run_dir,
            run_root=tmp_path,
            experiment_id="TYPE2-D0",
            profile="SMOKE",
            prereg_sha256=PREREG_SHA,
            fixture_sha256=FIXTURE_SHA,
            expected_runs=("A_PPO_ONLY:0",),
        )
