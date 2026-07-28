from __future__ import annotations

from pathlib import Path

import pytest

from stom_rl.rl_discovery.d1_contract import D1ArmId
from stom_rl.rl_discovery.d1_gates import D1Outcome
from stom_rl.rl_discovery.d1_lifecycle import D1Lifecycle, D1LifecycleError
from stom_rl.rl_discovery.gates import RunProfile
from stom_rl.rl_discovery.storage import atomic_write_json, contained_path


def _outcome() -> D1Outcome:
    return D1Outcome(
        arm=D1ArmId.BINARY_NATIVE,
        seed=0,
        training_timesteps=128,
        economic_reward_ratio=1.0,
        initial_decision_accuracy=1.0,
        invalid_action_count=0,
        block_count=0,
        no_fill_count=0,
        dominant_initial_action_rate=0.75,
    )


def _write_unit_files(run_dir: Path, outcome: D1Outcome) -> None:
    atomic_write_json(
        contained_path(run_dir, "outcomes", outcome.arm.value, "seed-0.json"),
        {
            "arm": outcome.arm.value,
            "seed": outcome.seed,
            "training_timesteps": outcome.training_timesteps,
            "economic_reward_ratio": outcome.economic_reward_ratio,
            "initial_decision_accuracy": outcome.initial_decision_accuracy,
            "invalid_action_count": 0,
            "block_count": 0,
            "no_fill_count": 0,
            "dominant_initial_action_rate": outcome.dominant_initial_action_rate,
        },
    )
    atomic_write_json(
        contained_path(run_dir, "events", outcome.arm.value, "seed-0.json"),
        [],
    )
    model_dir = contained_path(run_dir, "models", outcome.arm.value, "seed-0")
    model_dir.mkdir(parents=True)
    _ = (model_dir / "model.zip").write_bytes(b"model")
    _ = (model_dir / "normalizer.pkl").write_bytes(b"normalizer")


def _open(run_root: Path, *, resume: bool) -> D1Lifecycle:
    return D1Lifecycle.open(
        run_root,
        run_id="d1-resume-test",
        experiment_id="TYPE2-D1-REWARD-ACTION",
        profile=RunProfile.SMOKE,
        prereg_sha256="a" * 64,
        fixture_sha256="b" * 64,
        expected_runs=("A_BINARY_NATIVE:0",),
        resume=resume,
    )


def test_d1_lifecycle_resumes_only_digest_verified_units(tmp_path: Path) -> None:
    lifecycle = _open(tmp_path, resume=False)
    outcome = _outcome()
    _write_unit_files(lifecycle.run_dir, outcome)
    lifecycle.record(outcome)

    resumed = _open(tmp_path, resume=True)

    assert resumed.completed_keys == frozenset({"A_BINARY_NATIVE:0"})
    assert resumed.outcomes == (outcome,)


def test_d1_lifecycle_rejects_changed_completed_artifact(tmp_path: Path) -> None:
    lifecycle = _open(tmp_path, resume=False)
    outcome = _outcome()
    _write_unit_files(lifecycle.run_dir, outcome)
    lifecycle.record(outcome)
    _ = (
        lifecycle.run_dir / "models" / outcome.arm.value / "seed-0" / "model.zip"
    ).write_bytes(b"tampered")

    with pytest.raises(D1LifecycleError, match="artifact changed"):
        _open(tmp_path, resume=True)


def test_d1_lifecycle_rejects_resume_after_terminal_receipt(tmp_path: Path) -> None:
    lifecycle = _open(tmp_path, resume=False)
    _ = (lifecycle.run_dir / "terminal_receipt.json").write_text("{}", encoding="utf-8")

    with pytest.raises(D1LifecycleError, match="immutable"):
        _open(tmp_path, resume=True)
