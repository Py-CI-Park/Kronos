from __future__ import annotations

import json

from stom_rl.rl_discovery.d4_approval import primary_custody_signature
from stom_rl.rl_discovery.d4_contract import D4AlgorithmArmId, D4RewardArmId
from stom_rl.rl_discovery.storage import artifact_manifest_sha256
from webui import rl_dashboard


def _models() -> list[dict[str, object]]:
    metric = {"accuracy": 1.0, "reward_ratio": 1.0, "dominant_action_rate": .2, "invalid_action_count": 0}
    return [
        {"algorithm_arm": algorithm.value, "reward_arm": reward.value, "seed": seed,
         "fit": metric, "native": metric, "cost_23bp": metric}
        for algorithm in D4AlgorithmArmId for reward in D4RewardArmId for seed in (0, 1, 2)
    ]


def test_d4_primary_is_discoverable_only_with_authenticated_exact_matrix(tmp_path, monkeypatch) -> None:
    run = tmp_path / "type2-d4-primary"
    run.mkdir()
    key = bytes(range(32))
    monkeypatch.setenv("KRONOS_D4_APPROVAL_KEY_HEX", key.hex())
    summary = {
        "schema_version": "kronos.rl-discovery.d4.result.v1", "status": "COMPLETE",
        "verdict": "D4_ALGORITHM_OBJECTIVE_CONFIRMED", "profile": "PRIMARY",
        "fresh_oos": "NOT_RUN_NO_READ", "prereg_sha256": "e" * 64,
        "episode_snapshot_sha256": "f" * 64, "approved_smoke": "approved-smoke",
        "promotion_allowed": False, "profitability_claim_allowed": False,
        "gate": {"best_rl_arm": "C_DQN_DISCRETE", "confirmed_rl_arms": ["C_DQN_DISCRETE"], "supervised_ceiling_confirmed": True},
        "models": _models(),
    }
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    digest = artifact_manifest_sha256(run)
    receipt = {
        "status": "COMPLETE", "profile": "PRIMARY", "verdict": summary["verdict"],
        "prereg_sha256": summary["prereg_sha256"], "episode_snapshot_sha256": summary["episode_snapshot_sha256"],
        "fresh_oos": "NOT_RUN_NO_READ", "artifact_manifest_sha256": digest,
        "primary_custody_hmac_sha256": primary_custody_signature(
            key, run_name=run.name, prereg_sha="e" * 64, episode_sha="f" * 64,
            manifest_sha=digest, approved_smoke="approved-smoke",
        ),
    }
    (run / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    record = next(item for item in rl_dashboard.list_rl_runs() if item["name"] == run.name)
    detail = rl_dashboard.load_rl_run(run.name)
    assert record["summary"]["verdict"] == "D4_ALGORITHM_OBJECTIVE_CONFIRMED"
    assert detail["detail"]["gate"]["best_rl_arm"] == "C_DQN_DISCRETE"

    summary["models"] = []
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    blocked = rl_dashboard.load_rl_run(run.name)
    assert blocked["summary"]["status"] == "BLOCK"
    assert blocked["detail"] == {}


def test_d4_non_object_json_and_missing_verification_key_fail_closed(tmp_path, monkeypatch) -> None:
    run = tmp_path / "type2-d4-primary-invalid"
    run.mkdir()
    (run / "summary.json").write_text("[]", encoding="utf-8")
    (run / "terminal_receipt.json").write_text("[]", encoding="utf-8")
    monkeypatch.delenv("KRONOS_D4_APPROVAL_KEY_HEX", raising=False)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])
    detail = rl_dashboard.load_rl_run(run.name)
    assert detail["summary"] == {}
    assert detail.get("detail", {}) == {}
