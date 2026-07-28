from __future__ import annotations

import json
from pathlib import Path

import pytest

from stom_rl.rl_discovery.d1_runner import _smoke_reference
from stom_rl.rl_discovery.gates import RunProfile


def test_d1_primary_requires_approved_smoke() -> None:
    with pytest.raises(PermissionError, match="approved Smoke"):
        _smoke_reference(
            profile=RunProfile.PRIMARY,
            approved_smoke=None,
            prereg_sha="a" * 64,
            fixture_sha="b" * 64,
        )


def test_d1_primary_accepts_matching_safe_smoke_receipt(tmp_path: Path) -> None:
    smoke_dir = tmp_path / "type2-d1-smoke"
    smoke_dir.mkdir()
    receipt = {
        "experiment_id": "TYPE2-D1-REWARD-ACTION",
        "profile": "SMOKE",
        "status": "SMOKE_COMPLETE",
        "verdict": "SMOKE_INCOMPLETE",
        "d1_smoke_pass": True,
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "fresh_oos": "NOT_RUN_NO_READ",
        "prereg_sha256": "a" * 64,
        "fixture_sha256": "b" * 64,
    }
    _ = (smoke_dir / "terminal_receipt.json").write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    reference = _smoke_reference(
        profile=RunProfile.PRIMARY,
        approved_smoke=smoke_dir,
        prereg_sha="a" * 64,
        fixture_sha="b" * 64,
    )

    assert reference == smoke_dir.name


def test_d1_primary_rejects_smoke_from_different_inputs(tmp_path: Path) -> None:
    smoke_dir = tmp_path / "type2-d1-smoke"
    smoke_dir.mkdir()
    receipt = {
        "experiment_id": "TYPE2-D1-REWARD-ACTION",
        "profile": "SMOKE",
        "status": "SMOKE_COMPLETE",
        "verdict": "SMOKE_INCOMPLETE",
        "d1_smoke_pass": True,
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "fresh_oos": "NOT_RUN_NO_READ",
        "prereg_sha256": "c" * 64,
        "fixture_sha256": "b" * 64,
    }
    _ = (smoke_dir / "terminal_receipt.json").write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    with pytest.raises(PermissionError, match="input identity"):
        _smoke_reference(
            profile=RunProfile.PRIMARY,
            approved_smoke=smoke_dir,
            prereg_sha="a" * 64,
            fixture_sha="b" * 64,
        )
