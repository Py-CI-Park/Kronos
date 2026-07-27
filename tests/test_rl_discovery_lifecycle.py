from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from stom_rl.rl_discovery.gates import ArmOutcome, evaluate_discovery_gate
from stom_rl.rl_discovery.lifecycle import (
    DiscoveryLifecycle,
    LifecycleIntegrityError,
    ResumeMismatchError,
    TerminalRunError,
)

PREREG_SHA = "a" * 64
FIXTURE_SHA = "b" * 64


def _outcome(*, arm: str = "A_PPO_ONLY", seed: int = 0) -> ArmOutcome:
    return ArmOutcome(
        arm=arm,
        seed=seed,
        training_timesteps=256,
        oracle_reward_ratio=0.75,
        exact_basket_accuracy=0.5,
        invalid_action_count=0,
        block_count=0,
        no_fill_count=0,
        dominant_action_rate=1.0,
        shuffled_reward=False,
    )


def test_lifecycle_records_each_arm_seed_as_resumable_dashboard_evidence(tmp_path: Path) -> None:
    lifecycle = DiscoveryLifecycle.start(
        tmp_path,
        run_id="type2-d0-smoke-test",
        experiment_id="TYPE2-D0",
        profile="SMOKE",
        prereg_sha256=PREREG_SHA,
        fixture_sha256=FIXTURE_SHA,
        expected_runs=("A_PPO_ONLY:0", "B_BC_THEN_PPO:0"),
    )

    lifecycle.record(_outcome())

    state = cast(
        dict[str, object],
        json.loads((lifecycle.run_dir / "lifecycle.json").read_text(encoding="utf-8")),
    )
    dashboard = cast(
        dict[str, object],
        json.loads((lifecycle.run_dir / "sb3_smoke_summary.json").read_text(encoding="utf-8")),
    )
    summary = cast(dict[str, object], dashboard["summary"])
    assert state["status"] == "RUNNING"
    assert state["completed_runs"] == ["A_PPO_ONLY:0"]
    assert summary["status"] == "RUNNING"
    assert summary["completed_run_count"] == 1
    assert summary["expected_run_count"] == 2
    assert summary["fresh_oos"] == "NOT_RUN_NO_READ"
    assert (lifecycle.run_dir / "outcomes" / "A_PPO_ONLY" / "seed-0.json").is_file()


def test_lifecycle_resume_loads_completed_outcomes_and_rejects_changed_contract(
    tmp_path: Path,
) -> None:
    lifecycle = DiscoveryLifecycle.start(
        tmp_path,
        run_id="type2-d0-primary-test",
        experiment_id="TYPE2-D0",
        profile="PRIMARY",
        prereg_sha256=PREREG_SHA,
        fixture_sha256=FIXTURE_SHA,
        expected_runs=("A_PPO_ONLY:0",),
    )
    lifecycle.record(_outcome())

    resumed = DiscoveryLifecycle.resume(
        lifecycle.run_dir,
        run_root=tmp_path,
        experiment_id="TYPE2-D0",
        profile="PRIMARY",
        prereg_sha256=PREREG_SHA,
        fixture_sha256=FIXTURE_SHA,
        expected_runs=("A_PPO_ONLY:0",),
    )

    assert resumed.completed_keys == frozenset({"A_PPO_ONLY:0"})
    assert resumed.outcomes == (_outcome(),)
    with pytest.raises(ResumeMismatchError, match="prereg_sha256"):
        _ = DiscoveryLifecycle.resume(
            lifecycle.run_dir,
            run_root=tmp_path,
            experiment_id="TYPE2-D0",
            profile="PRIMARY",
            prereg_sha256="c" * 64,
            fixture_sha256=FIXTURE_SHA,
            expected_runs=("A_PPO_ONLY:0",),
        )


def test_lifecycle_completion_writes_terminal_receipt_without_opening_fresh_oos(
    tmp_path: Path,
) -> None:
    lifecycle = DiscoveryLifecycle.start(
        tmp_path,
        run_id="type2-d0-smoke-terminal",
        experiment_id="TYPE2-D0",
        profile="SMOKE",
        prereg_sha256=PREREG_SHA,
        fixture_sha256=FIXTURE_SHA,
        expected_runs=("A_PPO_ONLY:0",),
    )
    lifecycle.record(_outcome())

    lifecycle.complete(evaluate_discovery_gate(lifecycle.outcomes, profile="SMOKE"))

    receipt = cast(
        dict[str, object],
        json.loads((lifecycle.run_dir / "terminal_receipt.json").read_text(encoding="utf-8")),
    )
    assert receipt["status"] == "SMOKE_COMPLETE"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"
    assert receipt["promotion_allowed"] is False
    assert receipt["profitability_claim_allowed"] is False


def test_lifecycle_rejects_run_id_outside_direct_run_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="direct child"):
        _ = DiscoveryLifecycle.start(
            tmp_path,
            run_id="../escape",
            experiment_id="TYPE2-D0",
            profile="SMOKE",
            prereg_sha256=PREREG_SHA,
            fixture_sha256=FIXTURE_SHA,
            expected_runs=("A_PPO_ONLY:0",),
        )


def test_lifecycle_resume_rejects_directory_outside_configured_run_root(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    outside_root = tmp_path / "outside"
    lifecycle = DiscoveryLifecycle.start(
        outside_root,
        run_id="type2-d0-primary-outside",
        experiment_id="TYPE2-D0",
        profile="PRIMARY",
        prereg_sha256=PREREG_SHA,
        fixture_sha256=FIXTURE_SHA,
        expected_runs=("A_PPO_ONLY:0",),
    )

    with pytest.raises(ValueError, match="direct child"):
        _ = DiscoveryLifecycle.resume(
            lifecycle.run_dir,
            run_root=run_root,
            experiment_id="TYPE2-D0",
            profile="PRIMARY",
            prereg_sha256=PREREG_SHA,
            fixture_sha256=FIXTURE_SHA,
            expected_runs=("A_PPO_ONLY:0",),
        )


def test_lifecycle_resume_rejects_changed_expected_arm_seed_contract(tmp_path: Path) -> None:
    lifecycle = DiscoveryLifecycle.start(
        tmp_path,
        run_id="type2-d0-primary-contract",
        experiment_id="TYPE2-D0",
        profile="PRIMARY",
        prereg_sha256=PREREG_SHA,
        fixture_sha256=FIXTURE_SHA,
        expected_runs=("A_PPO_ONLY:0",),
    )

    with pytest.raises(ResumeMismatchError, match="expected_runs"):
        _ = DiscoveryLifecycle.resume(
            lifecycle.run_dir,
            run_root=tmp_path,
            experiment_id="TYPE2-D0",
            profile="PRIMARY",
            prereg_sha256=PREREG_SHA,
            fixture_sha256=FIXTURE_SHA,
            expected_runs=("A_PPO_ONLY:0", "A_PPO_ONLY:1"),
        )


def test_lifecycle_resume_rejects_outcome_whose_identity_differs_from_path(tmp_path: Path) -> None:
    lifecycle = DiscoveryLifecycle.start(
        tmp_path,
        run_id="type2-d0-primary-tampered",
        experiment_id="TYPE2-D0",
        profile="PRIMARY",
        prereg_sha256=PREREG_SHA,
        fixture_sha256=FIXTURE_SHA,
        expected_runs=("A_PPO_ONLY:0",),
    )
    lifecycle.record(_outcome())
    outcome_path = lifecycle.run_dir / "outcomes" / "A_PPO_ONLY" / "seed-0.json"
    payload = cast(dict[str, object], json.loads(outcome_path.read_text(encoding="utf-8")))
    payload["arm"] = "B_BC_THEN_PPO"
    _ = outcome_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="identity"):
        _ = DiscoveryLifecycle.resume(
            lifecycle.run_dir,
            run_root=tmp_path,
            experiment_id="TYPE2-D0",
            profile="PRIMARY",
            prereg_sha256=PREREG_SHA,
            fixture_sha256=FIXTURE_SHA,
            expected_runs=("A_PPO_ONLY:0",),
        )


def test_lifecycle_cannot_terminalize_until_every_expected_run_is_recorded(tmp_path: Path) -> None:
    lifecycle = DiscoveryLifecycle.start(
        tmp_path,
        run_id="type2-d0-primary-incomplete",
        experiment_id="TYPE2-D0",
        profile="PRIMARY",
        prereg_sha256=PREREG_SHA,
        fixture_sha256=FIXTURE_SHA,
        expected_runs=("A_PPO_ONLY:0", "B_BC_THEN_PPO:0"),
    )
    lifecycle.record(_outcome())

    with pytest.raises(LifecycleIntegrityError, match="every expected"):
        lifecycle.complete(evaluate_discovery_gate(lifecycle.outcomes, profile="PRIMARY"))


def test_terminal_receipt_makes_resume_immutable(tmp_path: Path) -> None:
    lifecycle = DiscoveryLifecycle.start(
        tmp_path,
        run_id="type2-d0-smoke-immutable",
        experiment_id="TYPE2-D0",
        profile="SMOKE",
        prereg_sha256=PREREG_SHA,
        fixture_sha256=FIXTURE_SHA,
        expected_runs=("A_PPO_ONLY:0",),
    )
    lifecycle.record(_outcome())
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
