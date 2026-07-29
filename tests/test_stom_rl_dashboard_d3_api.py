from __future__ import annotations

import json

from stom_rl.rl_discovery.storage import artifact_manifest_sha256
from webui import rl_dashboard
from webui import rl_dashboard_runs


def test_d3_summary_and_receipt_are_discoverable_and_tamper_blocked(tmp_path, monkeypatch) -> None:
    # Given: a custody-consistent D3 Primary artifact.
    run = tmp_path / "type2-d3-primary"
    run.mkdir()
    summary = {
        "schema_version": "kronos.rl-discovery.d3.result.v1",
        "status": "COMPLETE",
        "verdict": "D3_REPRESENTATION_ACTION_NOT_CONFIRMED",
        "profile": "PRIMARY",
        "fresh_oos": "NOT_RUN_NO_READ",
        "prereg_sha256": "c" * 64,
        "episode_snapshot_sha256": "d" * 64,
        "gate": {"best_policy_arm": "D_TOP5_CONTEXT_4X", "confirmed_policy_arms": []},
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

    # When: the official read-only dashboard lists and loads the D3 run.
    record = next(item for item in rl_dashboard.list_rl_runs() if item["name"] == run.name)
    original_reader = rl_dashboard_runs._find_discovery_evidence

    def mutate_after_verified_snapshot(run_dir, artifact_type):
        compact, verified_detail = original_reader(run_dir, artifact_type)
        summary["models"] = [{"tampered": True}]
        (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return compact, verified_detail

    monkeypatch.setattr(rl_dashboard_runs, "_find_discovery_evidence", mutate_after_verified_snapshot)
    detail = rl_dashboard.load_rl_run(run.name)

    # Then: D3 is live evidence, while post-receipt mutation fails closed.
    assert record["artifact_type"] == "rl_discovery_d3"
    assert record["summary"]["verdict"] == "D3_REPRESENTATION_ACTION_NOT_CONFIRMED"
    assert detail["detail"]["gate"]["best_policy_arm"] == "D_TOP5_CONTEXT_4X"
    assert detail["detail"]["models"] == []
    monkeypatch.setattr(rl_dashboard_runs, "_find_discovery_evidence", original_reader)
    blocked = rl_dashboard.load_rl_run(run.name)
    assert blocked["summary"]["status"] == "BLOCK"
    assert blocked["detail"] == {}
