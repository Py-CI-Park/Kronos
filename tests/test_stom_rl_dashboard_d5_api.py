from __future__ import annotations

import json

from stom_rl.rl_discovery.d4_contract import D4RewardArmId
from stom_rl.rl_discovery.d5_approval import primary_custody_signature
from stom_rl.rl_discovery.storage import JsonValue, artifact_manifest_sha256
from webui import rl_dashboard


def _models() -> list[dict[str, JsonValue]]:
    metric = {
        "accuracy": 0.95,
        "reward_ratio": 0.95,
        "dominant_action_rate": 0.2,
        "invalid_action_count": 0,
    }
    return [
        {
            "algorithm_arm": "C_DQN_DISCRETE",
            "reward_arm": reward.value,
            "seed": seed,
            "fit_23bp": metric,
            "native_23bp": metric,
            "native_0bp": metric,
        }
        for reward in D4RewardArmId
        for seed in range(5)
    ]


def test_d5_primary_is_discoverable_only_with_authenticated_exact_matrix(
    tmp_path,
    monkeypatch,
) -> None:
    run = tmp_path / "type2-d5-primary"
    run.mkdir()
    key = bytes(range(32))
    monkeypatch.setenv("KRONOS_D5_APPROVAL_KEY_HEX", key.hex())
    summary = {
        "schema_version": "kronos.rl-discovery.d5.result.v1",
        "research_lane": "rl_discovery",
        "experiment_id": "TYPE2-D5-FULL-TRAIN-COST",
        "status": "COMPLETE",
        "verdict": "D5_FULL_TRAIN_COST_NOT_CONFIRMED",
        "profile": "PRIMARY",
        "fresh_oos": "NOT_RUN_NO_READ",
        "reused_validation": "NOT_RUN_NO_READ",
        "prereg_sha256": "e" * 64,
        "episode_snapshot_sha256": "f" * 64,
        "approved_smoke": "approved-smoke",
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "primary_round_trip_cost_bp": 23,
        "diagnostic_round_trip_cost_bp": 0,
        "gate": {
            "verdict": "D5_FULL_TRAIN_COST_NOT_CONFIRMED",
            "native_passing_seed_fraction": 0.4,
            "shuffled_passing_seed_fraction": 0.6,
            "native_delta_vs_shuffled": 0.8,
            "promotion_allowed": False,
            "profitability_claim_allowed": False,
            "reused_validation": "NOT_RUN_NO_READ",
            "fresh_oos": "NOT_RUN_NO_READ",
        },
        "models": _models(),
    }
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    digest = artifact_manifest_sha256(run)
    receipt = {
        "status": "COMPLETE",
        "profile": "PRIMARY",
        "verdict": summary["verdict"],
        "prereg_sha256": summary["prereg_sha256"],
        "episode_snapshot_sha256": summary["episode_snapshot_sha256"],
        "fresh_oos": "NOT_RUN_NO_READ",
        "artifact_manifest_sha256": digest,
        "primary_custody_hmac_sha256": primary_custody_signature(
            key,
            run_name=run.name,
            prereg_sha="e" * 64,
            episode_sha="f" * 64,
            manifest_sha=digest,
            approved_smoke="approved-smoke",
        ),
    }
    (run / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    record = next(item for item in rl_dashboard.list_rl_runs() if item["name"] == run.name)
    detail = rl_dashboard.load_rl_run(run.name)

    assert record["artifact_type"] == "rl_discovery_d5"
    assert record["summary"]["verdict"] == "D5_FULL_TRAIN_COST_NOT_CONFIRMED"
    assert detail["detail"]["gate"]["native_passing_seed_fraction"] == 0.4

    summary["models"] = summary["models"][:-1]
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    blocked = rl_dashboard.load_rl_run(run.name)
    assert blocked["summary"]["status"] == "BLOCK"
    assert blocked["detail"] == {}
