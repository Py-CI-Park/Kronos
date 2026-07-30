from __future__ import annotations

import json

import pytest

from stom_rl.rl_discovery import d5_runner
from stom_rl.rl_discovery.d4_contract import D4RewardArmId
from stom_rl.rl_discovery.d5_approval import approve_d5_smoke, create_d5_smoke_approval
from stom_rl.rl_discovery.d5_execution import D5RunProfile
from stom_rl.rl_discovery.d5_runner import run_d5
from stom_rl.rl_discovery.storage import artifact_manifest_sha256


def test_d5_early_failure_writes_terminal_no_go_receipt(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        run_d5(tmp_path, profile=D5RunProfile.SMOKE, run_id="early-failure")

    receipt = json.loads(
        (tmp_path / "webui/rl_runs/rl_discovery/early-failure/terminal_receipt.json").read_text()
    )
    assert receipt["status"] == "FAILED"
    assert receipt["verdict"] == "NO_GO"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"


def test_d5_interrupt_terminalizes_the_run(tmp_path, monkeypatch) -> None:
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt("operator stop")

    monkeypatch.setattr(d5_runner, "execute_d5", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run_d5(tmp_path, profile=D5RunProfile.SMOKE, run_id="interrupted")

    receipt = json.loads(
        (tmp_path / "webui/rl_runs/rl_discovery/interrupted/terminal_receipt.json").read_text()
    )
    assert receipt["status"] == "FAILED"
    assert receipt["fresh_oos"] == "NOT_RUN_NO_READ"


def test_d5_smoke_requires_detached_exact_two_unit_approval(tmp_path) -> None:
    run_root = tmp_path / "runs"
    smoke = run_root / "smoke"
    smoke.mkdir(parents=True)
    prereg_sha, episode_sha = "a" * 64, "b" * 64
    models: list[dict[str, str | int]] = []
    for reward in D4RewardArmId:
        identity = {"algorithm_arm": "C_DQN_DISCRETE", "reward_arm": reward.value, "seed": 0}
        models.append(identity)
        outcome = smoke / "outcomes" / reward.value / "seed-0.json"
        model = smoke / "models" / f"C_DQN_DISCRETE__{reward.value}" / "seed-0" / "model.zip"
        outcome.parent.mkdir(parents=True, exist_ok=True)
        model.parent.mkdir(parents=True, exist_ok=True)
        outcome.write_text(json.dumps(identity), encoding="utf-8")
        model.write_bytes(b"model")
    summary = {
        "schema_version": "kronos.rl-discovery.d5.result.v1",
        "profile": "SMOKE",
        "status": "COMPLETE",
        "verdict": "SMOKE_COMPLETE",
        "prereg_sha256": prereg_sha,
        "episode_snapshot_sha256": episode_sha,
        "models": models,
    }
    (smoke / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    digest = artifact_manifest_sha256(
        smoke,
        excluded_relative_paths=frozenset({"terminal_receipt.json", "operator_approval.json"}),
    )
    receipt = {
        "profile": "SMOKE",
        "status": "COMPLETE",
        "verdict": "SMOKE_COMPLETE",
        "prereg_sha256": prereg_sha,
        "episode_snapshot_sha256": episode_sha,
        "artifact_manifest_sha256": digest,
        "fresh_oos": "NOT_RUN_NO_READ",
    }
    (smoke / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    key = bytes(range(32))

    with pytest.raises(PermissionError, match="detached operator approval"):
        approve_d5_smoke(
            smoke,
            run_root=run_root,
            prereg_sha=prereg_sha,
            episode_sha=episode_sha,
            approval_key=key,
        )
    create_d5_smoke_approval(smoke, run_root=run_root, approval_key=key)
    assert approve_d5_smoke(
        smoke,
        run_root=run_root,
        prereg_sha=prereg_sha,
        episode_sha=episode_sha,
        approval_key=key,
    ) == "smoke"
