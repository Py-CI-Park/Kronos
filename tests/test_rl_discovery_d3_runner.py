from __future__ import annotations

import json

import pytest

from stom_rl.rl_discovery import d3_runner
from stom_rl.rl_discovery.d3_contract import D3PolicyArmId, D3RewardArmId
from stom_rl.rl_discovery.d3_runner import D3RunProfile, approve_d3_smoke, run_d3
from stom_rl.rl_discovery.storage import artifact_manifest_sha256


def test_d3_direct_early_failure_writes_a_terminal_no_go_receipt(tmp_path) -> None:
    # Given/When: a direct Smoke call starts in a repository without the preregistration.
    with pytest.raises(FileNotFoundError):
        run_d3(tmp_path, profile=D3RunProfile.SMOKE, run_id="early-failure")

    # Then: the newly created run is terminalized rather than left ambiguous.
    receipt = json.loads((tmp_path / "webui/rl_runs/rl_discovery/early-failure/terminal_receipt.json").read_text())
    assert receipt["status"] == "FAILED"
    assert receipt["verdict"] == "NO_GO"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"


def test_d3_interrupt_terminalizes_the_run(tmp_path, monkeypatch) -> None:
    # Given: the execution body is interrupted after the immutable run directory exists.
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt("operator stop")

    monkeypatch.setattr(d3_runner, "execute_d3", interrupt)

    # When: the public runner receives the interrupt.
    with pytest.raises(KeyboardInterrupt):
        run_d3(tmp_path, profile=D3RunProfile.SMOKE, run_id="interrupted")

    # Then: interruption remains explicit and Fresh OOS remains sealed.
    receipt = json.loads((tmp_path / "webui/rl_runs/rl_discovery/interrupted/terminal_receipt.json").read_text())
    assert receipt["status"] == "FAILED"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"


def test_d3_smoke_approval_requires_the_exact_four_unit_matrix(tmp_path) -> None:
    # Given: a complete, custody-consistent D3 Smoke directory.
    root = tmp_path / "runs"
    smoke = root / "smoke"
    smoke.mkdir(parents=True)
    prereg_sha, episode_sha = "a" * 64, "b" * 64
    models = [
        {"policy_arm": policy.value, "reward_arm": reward.value, "seed": 0}
        for policy in tuple(D3PolicyArmId)[:2]
        for reward in D3RewardArmId
    ]
    summary = {
        "schema_version": "kronos.rl-discovery.d3.result.v1",
        "profile": "SMOKE",
        "status": "COMPLETE",
        "verdict": "SMOKE_COMPLETE",
        "prereg_sha256": prereg_sha,
        "episode_snapshot_sha256": episode_sha,
        "fresh_oos": "NOT_RUN_NO_READ",
        "models": models,
    }
    (smoke / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    receipt = {
        "profile": "SMOKE",
        "status": "COMPLETE",
        "verdict": "SMOKE_COMPLETE",
        "prereg_sha256": prereg_sha,
        "episode_snapshot_sha256": episode_sha,
        "fresh_oos": "NOT_RUN_NO_READ",
        "artifact_manifest_sha256": artifact_manifest_sha256(smoke),
    }
    (smoke / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

    # When/Then: exact Smoke is approved, but a fifth duplicate is rejected even with a recomputed manifest.
    assert approve_d3_smoke(smoke, run_root=root, prereg_sha=prereg_sha, episode_sha=episode_sha) == "smoke"
    summary["models"].append(dict(models[0]))
    (smoke / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    receipt["artifact_manifest_sha256"] = artifact_manifest_sha256(smoke, excluded_relative_paths=frozenset({"terminal_receipt.json"}))
    (smoke / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(PermissionError, match="four-unit"):
        approve_d3_smoke(smoke, run_root=root, prereg_sha=prereg_sha, episode_sha=episode_sha)
