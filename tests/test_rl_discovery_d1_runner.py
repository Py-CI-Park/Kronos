from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from stom_rl.rl_discovery.d1_contract import D1ArmId
from stom_rl.rl_discovery.d1_evidence import write_d1_unit
from stom_rl.rl_discovery.d1_gates import D1Outcome
from stom_rl.rl_discovery.d1_lifecycle import D1Lifecycle
from stom_rl.rl_discovery.d1_approval import approved_smoke_reference
from stom_rl.rl_discovery.gates import RunProfile
from stom_rl.rl_discovery.storage import artifact_manifest_sha256


def _approved_smoke(run_root: Path, prereg_path: Path) -> tuple[Path, str, str]:
    prereg_bytes = prereg_path.read_bytes()
    fixture_bytes = (
        Path(__file__).resolve().parents[1]
        / "tests"
        / "fixtures"
        / "type1_synthetic_fixture.json"
    ).read_bytes()
    prereg_sha = hashlib.sha256(prereg_bytes).hexdigest()
    fixture_sha = hashlib.sha256(fixture_bytes).hexdigest()
    expected = tuple(f"{arm.value}:0" for arm in D1ArmId)
    lifecycle = D1Lifecycle.open(
        run_root,
        run_id="type2-d1-smoke",
        experiment_id="TYPE2-D1-REWARD-ACTION",
        profile=RunProfile.SMOKE,
        prereg_sha256=prereg_sha,
        fixture_sha256=fixture_sha,
        expected_runs=expected,
        resume=False,
    )
    smoke_dir = lifecycle.run_dir
    (smoke_dir / "inputs").mkdir()
    (smoke_dir / "inputs" / "prereg.json").write_bytes(prereg_bytes)
    (smoke_dir / "inputs" / "fixture.json").write_bytes(fixture_bytes)
    models: list[dict[str, object]] = []
    for arm in D1ArmId:
        model_dir = smoke_dir / "models" / arm.value / "seed-0"
        outcome_dir = smoke_dir / "outcomes" / arm.value
        model_dir.mkdir(parents=True)
        outcome_dir.mkdir(parents=True)
        (model_dir / "model.zip").write_bytes(b"model")
        (model_dir / "normalizer.pkl").write_bytes(b"normalizer")
        ratio = 0.0 if arm is D1ArmId.BINARY_SHUFFLED else 1.0
        accuracy = 0.25 if arm is D1ArmId.BINARY_SHUFFLED else 1.0
        dominant = 1.0 if arm is D1ArmId.BINARY_SHUFFLED else 0.75
        outcome = D1Outcome(
            arm=arm,
            seed=0,
            training_timesteps=2_048,
            economic_reward_ratio=ratio,
            initial_decision_accuracy=accuracy,
            invalid_action_count=0,
            block_count=0,
            no_fill_count=0,
            dominant_initial_action_rate=dominant,
        )
        write_d1_unit(smoke_dir, outcome=outcome, events=())
        lifecycle.record(outcome)
        models.append(
            {
                "algorithm": arm.value,
                "seed": 0,
                "training_timesteps": 2_048,
                "oracle_reward_ratio": ratio,
                "exact_basket_accuracy": accuracy,
                "dominant_action_rate": dominant,
                "invalid_action_count": 0,
                "block_count": 0,
                "no_fill_count": 0,
            }
        )
    lifecycle.mark_complete_pending_receipt()
    boundary: dict[str, object] = {
        "experiment_id": "TYPE2-D1-REWARD-ACTION",
        "profile": "SMOKE",
        "status": "SMOKE_COMPLETE",
        "verdict": "SMOKE_INCOMPLETE",
        "d1_smoke_pass": True,
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "fresh_oos": "NOT_RUN_NO_READ",
        "prereg_sha256": prereg_sha,
        "fixture_sha256": fixture_sha,
        "primary_round_trip_cost_bp": 23,
    }
    (smoke_dir / "sb3_smoke_summary.json").write_text(
        json.dumps({"summary": boundary, "models": models}),
        encoding="utf-8",
    )
    digest = artifact_manifest_sha256(
        smoke_dir,
        excluded_relative_paths=frozenset({"terminal_receipt.json"}),
    )
    (smoke_dir / "terminal_receipt.json").write_text(
        json.dumps({**boundary, "artifact_manifest_sha256": digest}),
        encoding="utf-8",
    )
    return smoke_dir, prereg_sha, fixture_sha


def _official_prereg() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "kronos_rl_discovery_type2_d1_prereg_2026-07-28.json"
    )


def test_d1_primary_requires_approved_smoke(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="approved Smoke"):
        approved_smoke_reference(
            profile=RunProfile.PRIMARY,
            approved_smoke=None,
            prereg_sha="a" * 64,
            fixture_sha="b" * 64,
            run_root=tmp_path,
        )


def test_d1_primary_accepts_matching_safe_smoke_receipt(tmp_path: Path) -> None:
    smoke_dir, prereg_sha, fixture_sha = _approved_smoke(tmp_path, _official_prereg())

    reference = approved_smoke_reference(
        profile=RunProfile.PRIMARY,
        approved_smoke=smoke_dir,
        prereg_sha=prereg_sha,
        fixture_sha=fixture_sha,
        run_root=tmp_path,
    )

    assert reference == smoke_dir.name


def test_d1_primary_rejects_smoke_outside_run_root(tmp_path: Path) -> None:
    external_root = tmp_path / "external"
    external_root.mkdir()
    smoke_dir, prereg_sha, fixture_sha = _approved_smoke(external_root, _official_prereg())
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()

    with pytest.raises(ValueError, match="direct child"):
        approved_smoke_reference(
            profile=RunProfile.PRIMARY,
            approved_smoke=smoke_dir,
            prereg_sha=prereg_sha,
            fixture_sha=fixture_sha,
            run_root=trusted_root,
        )


def test_d1_primary_rejects_tampered_smoke_bundle(tmp_path: Path) -> None:
    smoke_dir, prereg_sha, fixture_sha = _approved_smoke(tmp_path, _official_prereg())
    (smoke_dir / "models" / D1ArmId.BINARY_NATIVE.value / "seed-0" / "model.zip").write_bytes(
        b"tampered"
    )

    with pytest.raises(PermissionError, match="manifest"):
        approved_smoke_reference(
            profile=RunProfile.PRIMARY,
            approved_smoke=smoke_dir,
            prereg_sha=prereg_sha,
            fixture_sha=fixture_sha,
            run_root=tmp_path,
        )
