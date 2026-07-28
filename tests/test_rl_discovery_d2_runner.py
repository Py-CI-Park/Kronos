from __future__ import annotations

import json

import pytest

from stom_rl.rl_discovery import d2_runner
from stom_rl.rl_discovery.d2_contract import D2ArmId
from stom_rl.rl_discovery.d2_custody import D2CustodyError, assert_plain_path, verified_text_stream
from stom_rl.rl_discovery.d2_runner import _approved_smoke, _model_arm_id, run_d2
from stom_rl.rl_discovery.gates import RunProfile
from stom_rl.rl_discovery.storage import artifact_manifest_sha256, contained_path


def test_d2_model_arm_id_is_one_safe_storage_segment(tmp_path) -> None:
    arm_id = _model_arm_id(1, D2ArmId.NATIVE)

    assert arm_id == "count-1__A_NATIVE"
    assert contained_path(tmp_path, "models", arm_id).parent == tmp_path / "models"


def test_d2_custody_rejects_symlink_input(tmp_path) -> None:
    source = tmp_path / "source.json"
    source.write_text("[]", encoding="utf-8")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(D2CustodyError, match="symlink|reparse"):
        assert_plain_path(link, anchor=tmp_path, require_file=True)


def test_d2_custody_hashes_and_consumes_the_same_held_handle(tmp_path) -> None:
    source = tmp_path / "source.json"
    source.write_text('[{"value":1}]', encoding="utf-8")
    import hashlib

    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    with verified_text_stream(source, expected_sha256=expected, anchor=tmp_path) as stream:
        assert stream.read() == '[{"value":1}]'


def test_d2_direct_early_failure_writes_terminal_receipt(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        run_d2(tmp_path, profile=RunProfile.SMOKE, run_id="early-failure")

    receipt = json.loads(
        (tmp_path / "webui" / "rl_runs" / "rl_discovery" / "early-failure" / "terminal_receipt.json").read_text()
    )
    assert receipt["status"] == "FAILED"
    assert receipt["verdict"] == "NO_GO"


def test_d2_interrupt_writes_terminal_receipt(tmp_path, monkeypatch) -> None:
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt("operator stop")

    monkeypatch.setattr(d2_runner, "_run_d2", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run_d2(tmp_path, profile=RunProfile.SMOKE, run_id="interrupted")

    receipt = json.loads(
        (tmp_path / "webui" / "rl_runs" / "rl_discovery" / "interrupted" / "terminal_receipt.json").read_text()
    )
    assert receipt["status"] == "FAILED"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"


def test_d2_smoke_approval_requires_frozen_four_unit_matrix(tmp_path) -> None:
    run_root = tmp_path / "runs"
    smoke = run_root / "smoke"
    smoke.mkdir(parents=True)
    prereg_sha = "a" * 64
    data_sha = "b" * 64
    summary = {
        "schema_version": "kronos.rl-discovery.d2.result.v1",
        "profile": "SMOKE",
        "status": "COMPLETE",
        "verdict": "SMOKE_COMPLETE",
        "prereg_sha256": prereg_sha,
        "episode_snapshot_sha256": data_sha,
        "fresh_oos": "NOT_RUN_NO_READ",
        "models": [
            {"episode_count": count, "arm": arm.value, "seed": 0}
            for count in (1, 8)
            for arm in D2ArmId
        ],
    }
    (smoke / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    receipt = {
        "profile": "SMOKE",
        "status": "COMPLETE",
        "prereg_sha256": prereg_sha,
        "episode_snapshot_sha256": data_sha,
        "artifact_manifest_sha256": artifact_manifest_sha256(smoke),
        "fresh_oos": "NOT_RUN_NO_READ",
    }
    (smoke / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

    assert _approved_smoke(smoke, run_root=run_root, prereg_sha=prereg_sha, data_sha=data_sha) == "smoke"

    summary["models"].pop()
    (smoke / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    receipt["artifact_manifest_sha256"] = artifact_manifest_sha256(
        smoke,
        excluded_relative_paths=frozenset({"terminal_receipt.json"}),
    )
    (smoke / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(PermissionError, match="four-unit"):
        _approved_smoke(smoke, run_root=run_root, prereg_sha=prereg_sha, data_sha=data_sha)
