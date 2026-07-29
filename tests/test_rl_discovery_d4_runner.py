from __future__ import annotations

import json

import pytest

from stom_rl.rl_discovery import d4_runner
from stom_rl.rl_discovery.d4_approval import approve_d4_smoke, create_d4_smoke_approval
from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId, D4RewardArmId
from stom_rl.rl_discovery.d4_execution import D4RunProfile
from stom_rl.rl_discovery.d4_runner import run_d4
from stom_rl.rl_discovery.storage import artifact_manifest_sha256


def test_d4_direct_early_failure_writes_a_terminal_no_go_receipt(tmp_path) -> None:
    # Given/When: D4 starts in a repository without its committed preregistration.
    with pytest.raises(FileNotFoundError):
        run_d4(tmp_path, profile=D4RunProfile.SMOKE, run_id="early-failure")

    # Then: the run is terminalized and Fresh OOS remains sealed.
    receipt = json.loads(
        (tmp_path / "webui/rl_runs/rl_discovery/early-failure/terminal_receipt.json").read_text()
    )
    assert receipt["status"] == "FAILED"
    assert receipt["verdict"] == "NO_GO"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"


def test_d4_interrupt_terminalizes_the_run(tmp_path, monkeypatch) -> None:
    # Given: execution is interrupted after immutable directory creation.
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt("operator stop")

    monkeypatch.setattr(d4_runner, "execute_d4", interrupt)

    # When: the public runner receives the interrupt.
    with pytest.raises(KeyboardInterrupt):
        run_d4(tmp_path, profile=D4RunProfile.SMOKE, run_id="interrupted")

    # Then: interruption is explicit rather than an ambiguous partial run.
    receipt = json.loads(
        (tmp_path / "webui/rl_runs/rl_discovery/interrupted/terminal_receipt.json").read_text()
    )
    assert receipt["status"] == "FAILED"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"


def test_d4_smoke_requires_a_detached_operator_approval(tmp_path) -> None:
    run_root = tmp_path / "runs"
    smoke = run_root / "smoke"
    smoke.mkdir(parents=True)
    prereg_sha, episode_sha = "a" * 64, "b" * 64
    models: list[dict[str, object]] = []
    for algorithm in D4AlgorithmArmId:
        for reward in D4RewardArmId:
            identity = {"algorithm_arm": algorithm.value, "reward_arm": reward.value, "seed": 0}
            models.append(identity)
            outcome = smoke / "outcomes" / algorithm.value / reward.value / "seed-0.json"
            model = smoke / "models" / f"{algorithm.value}__{reward.value}" / "seed-0" / "model.zip"
            outcome.parent.mkdir(parents=True, exist_ok=True)
            model.parent.mkdir(parents=True, exist_ok=True)
            outcome.write_text(json.dumps(identity), encoding="utf-8")
            model.write_bytes(b"model")
    summary = {"schema_version": "kronos.rl-discovery.d4.result.v1", "profile": "SMOKE", "status": "COMPLETE", "verdict": "SMOKE_COMPLETE", "prereg_sha256": prereg_sha, "episode_snapshot_sha256": episode_sha, "models": models}
    (smoke / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    digest = artifact_manifest_sha256(smoke, excluded_relative_paths=frozenset({"terminal_receipt.json", "operator_approval.json"}))
    receipt = {"profile": "SMOKE", "status": "COMPLETE", "verdict": "SMOKE_COMPLETE", "prereg_sha256": prereg_sha, "episode_snapshot_sha256": episode_sha, "artifact_manifest_sha256": digest, "fresh_oos": "NOT_RUN_NO_READ"}
    (smoke / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    key = bytes(range(32))

    with pytest.raises(PermissionError, match="detached operator approval"):
        approve_d4_smoke(smoke, run_root=run_root, prereg_sha=prereg_sha, episode_sha=episode_sha, approval_key=key)
    create_d4_smoke_approval(smoke, run_root=run_root, approval_key=key)
    assert approve_d4_smoke(smoke, run_root=run_root, prereg_sha=prereg_sha, episode_sha=episode_sha, approval_key=key) == "smoke"
