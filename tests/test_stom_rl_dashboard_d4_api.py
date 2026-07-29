from __future__ import annotations

import json

from stom_rl.rl_discovery.storage import artifact_manifest_sha256
from webui import rl_dashboard


def test_d4_primary_is_discoverable_and_tamper_blocked(tmp_path, monkeypatch) -> None:
    # Given: a custody-consistent D4 Primary artifact with a confirmed DQN arm.
    run = tmp_path / "type2-d4-primary"
    run.mkdir()
    summary = {
        "schema_version": "kronos.rl-discovery.d4.result.v1",
        "status": "COMPLETE",
        "verdict": "D4_ALGORITHM_OBJECTIVE_CONFIRMED",
        "profile": "PRIMARY",
        "fresh_oos": "NOT_RUN_NO_READ",
        "prereg_sha256": "e" * 64,
        "episode_snapshot_sha256": "f" * 64,
        "gate": {
            "best_rl_arm": "C_DQN_DISCRETE",
            "confirmed_rl_arms": ["C_DQN_DISCRETE"],
            "supervised_ceiling_confirmed": True,
        },
        "models": [],
    }
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    receipt = {
        "status": "COMPLETE",
        "profile": "PRIMARY",
        "verdict": summary["verdict"],
        "prereg_sha256": summary["prereg_sha256"],
        "episode_snapshot_sha256": summary["episode_snapshot_sha256"],
        "fresh_oos": "NOT_RUN_NO_READ",
        "artifact_manifest_sha256": artifact_manifest_sha256(run),
    }
    (run / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    # When: the official dashboard lists and loads D4.
    record = next(item for item in rl_dashboard.list_rl_runs() if item["name"] == run.name)
    detail = rl_dashboard.load_rl_run(run.name)

    # Then: D4 evidence is exposed, but post-receipt mutation fails closed.
    assert record["artifact_type"] == "rl_discovery_d4"
    assert record["summary"]["verdict"] == "D4_ALGORITHM_OBJECTIVE_CONFIRMED"
    assert detail["detail"]["gate"]["best_rl_arm"] == "C_DQN_DISCRETE"
    summary["models"] = [{"tampered": True}]
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    blocked = rl_dashboard.load_rl_run(run.name)
    assert blocked["summary"]["status"] == "BLOCK"
    assert blocked["detail"] == {}
