from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from stom_rl.rl_discovery.gates import ArmOutcome, evaluate_discovery_gate
from stom_rl.rl_discovery.lifecycle import DiscoveryLifecycle, ResumeMismatchError


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
        prereg_sha256="abc123",
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
        prereg_sha256="original",
        expected_runs=("A_PPO_ONLY:0",),
    )
    lifecycle.record(_outcome())

    resumed = DiscoveryLifecycle.resume(
        lifecycle.run_dir,
        experiment_id="TYPE2-D0",
        profile="PRIMARY",
        prereg_sha256="original",
    )

    assert resumed.completed_keys == frozenset({"A_PPO_ONLY:0"})
    assert resumed.outcomes == (_outcome(),)
    with pytest.raises(ResumeMismatchError, match="prereg_sha256"):
        _ = DiscoveryLifecycle.resume(
            lifecycle.run_dir,
            experiment_id="TYPE2-D0",
            profile="PRIMARY",
            prereg_sha256="changed",
        )


def test_lifecycle_completion_writes_terminal_receipt_without_opening_fresh_oos(
    tmp_path: Path,
) -> None:
    lifecycle = DiscoveryLifecycle.start(
        tmp_path,
        run_id="type2-d0-smoke-terminal",
        experiment_id="TYPE2-D0",
        profile="SMOKE",
        prereg_sha256="abc123",
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
            prereg_sha256="abc123",
            expected_runs=("A_PPO_ONLY:0",),
        )
