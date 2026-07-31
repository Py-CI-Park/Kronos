from pathlib import Path

import pytest

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d6r_approval import D6RApprovalError, approve_d6r_smoke
from stom_rl.rl_discovery.storage import artifact_manifest_sha256


PREREG_SHA = "a" * 64


def _smoke_run(run_root: Path, *, invalid_actions: int) -> Path:
    run_dir = run_root / "type2-d6r-smoke-test"
    run_dir.mkdir()
    summary = {
        "schema_version": "kronos.rl-discovery.d6r.falsification.v1",
        "profile": "SMOKE",
        "status": "COMPLETE",
        "verdict": "D6R_SMOKE_COMPLETE",
        "prereg_sha256": PREREG_SHA,
        "unit_count": 4,
        "invalid_action_count": invalid_actions,
        "fresh_oos": "NOT_RUN_NO_READ",
    }
    (run_dir / "summary.json").write_bytes(canonical_json_bytes(summary))
    manifest = artifact_manifest_sha256(run_dir)
    receipt = {
        "schema_version": "kronos.rl-discovery.d6r.receipt.v1",
        "profile": "SMOKE",
        "status": "COMPLETE",
        "verdict": "D6R_SMOKE_COMPLETE",
        "artifact_manifest_sha256": manifest,
        "prereg_sha256": PREREG_SHA,
        "unit_count": 4,
        "invalid_action_count": invalid_actions,
        "fresh_oos": "NOT_RUN_NO_READ",
    }
    (run_dir / "terminal_receipt.json").write_bytes(canonical_json_bytes(receipt))
    return run_dir


def test_d6r_smoke_approval_accepts_exact_complete_evidence(tmp_path: Path) -> None:
    # Given
    smoke = _smoke_run(tmp_path, invalid_actions=0)

    # When
    approved = approve_d6r_smoke(smoke, run_root=tmp_path, prereg_sha256=PREREG_SHA)

    # Then
    assert approved == "type2-d6r-smoke-test"


def test_d6r_smoke_approval_rejects_invalid_actions(tmp_path: Path) -> None:
    # Given
    smoke = _smoke_run(tmp_path, invalid_actions=1)

    # When / Then
    with pytest.raises(D6RApprovalError):
        approve_d6r_smoke(smoke, run_root=tmp_path, prereg_sha256=PREREG_SHA)
