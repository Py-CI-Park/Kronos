from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from stom_rl.rl_discovery.d1_contract import D1ArmId
from stom_rl.rl_discovery.d1_approval import approved_smoke_reference
from stom_rl.rl_discovery.gates import RunProfile
from stom_rl.rl_discovery.storage import artifact_manifest_sha256


def _approved_smoke(run_root: Path, prereg_path: Path) -> tuple[Path, str]:
    smoke_dir = run_root / "type2-d1-smoke"
    (smoke_dir / "inputs").mkdir(parents=True)
    prereg_bytes = prereg_path.read_bytes()
    (smoke_dir / "inputs" / "prereg.json").write_bytes(prereg_bytes)
    models: list[dict[str, object]] = []
    for arm in D1ArmId:
        model_dir = smoke_dir / "models" / arm.value / "seed-0"
        outcome_dir = smoke_dir / "outcomes" / arm.value
        model_dir.mkdir(parents=True)
        outcome_dir.mkdir(parents=True)
        (model_dir / "model.zip").write_bytes(b"model")
        (model_dir / "normalizer.pkl").write_bytes(b"normalizer")
        (outcome_dir / "seed-0.json").write_text("{}", encoding="utf-8")
        models.append({"algorithm": arm.value, "seed": 0})
    prereg_sha = hashlib.sha256(prereg_bytes).hexdigest()
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
        "fixture_sha256": "b" * 64,
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
    return smoke_dir, prereg_sha


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
    smoke_dir, prereg_sha = _approved_smoke(tmp_path, _official_prereg())

    reference = approved_smoke_reference(
        profile=RunProfile.PRIMARY,
        approved_smoke=smoke_dir,
        prereg_sha=prereg_sha,
        fixture_sha="b" * 64,
        run_root=tmp_path,
    )

    assert reference == smoke_dir.name


def test_d1_primary_rejects_smoke_outside_run_root(tmp_path: Path) -> None:
    external_root = tmp_path / "external"
    external_root.mkdir()
    smoke_dir, prereg_sha = _approved_smoke(external_root, _official_prereg())
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()

    with pytest.raises(ValueError, match="direct child"):
        approved_smoke_reference(
            profile=RunProfile.PRIMARY,
            approved_smoke=smoke_dir,
            prereg_sha=prereg_sha,
            fixture_sha="b" * 64,
            run_root=trusted_root,
        )


def test_d1_primary_rejects_tampered_smoke_bundle(tmp_path: Path) -> None:
    smoke_dir, prereg_sha = _approved_smoke(tmp_path, _official_prereg())
    (smoke_dir / "models" / D1ArmId.BINARY_NATIVE.value / "seed-0" / "model.zip").write_bytes(
        b"tampered"
    )

    with pytest.raises(PermissionError, match="manifest"):
        approved_smoke_reference(
            profile=RunProfile.PRIMARY,
            approved_smoke=smoke_dir,
            prereg_sha=prereg_sha,
            fixture_sha="b" * 64,
            run_root=tmp_path,
        )
