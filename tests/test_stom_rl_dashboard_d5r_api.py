from __future__ import annotations

import json
from pathlib import Path

from stom_rl.rl_discovery.d5_approval import primary_custody_signature
from stom_rl.rl_discovery.storage import artifact_manifest_sha256
from webui import rl_dashboard


def _metric(value: float) -> dict[str, float | int]:
    return {
        "accuracy": value,
        "reward_ratio": value,
        "dominant_action_rate": 0.25,
        "invalid_action_count": 0,
        "oracle_reward": 1.0,
        "total_reward": value,
        "trade_rate": 0.5,
    }


def _write_primary(run: Path, key: bytes) -> None:
    prereg = {
        "schema_version": "kronos.rl-discovery.d5r.prereg.v1",
        "status": "APPROVED_EXECUTABLE",
        "experiment_id": "TYPE2-D5R-CAPACITY-OBJECTIVE",
        "parent_release": "fork-v1.15.0-kronos-rl-d5-full-train-cost",
        "source_run": {
            "run_name": "type2-d5-primary-20260729-001",
            "artifact_manifest_sha256": "a" * 64,
            "summary_sha256": "b" * 64,
            "episode_snapshot_sha256": "c" * 64,
            "episode_count": 573,
            "partition": "TRAIN_ONLY",
        },
        "d5r_1_diagnostic": {
            "source_arms": ["NATIVE", "SHUFFLED"],
            "seeds": [0, 1, 2, 3, 4],
            "cost_bp": 23,
            "near_optimal_tolerance_bp": [5, 10, 25],
            "regret_definition": "registered",
            "capacity_required_when": {
                "median_native_near_optimal_25bp_below": 0.85,
                "or_median_native_regret_bp_above": 25.0,
            },
        },
        "claims_boundary": {
            "research_only": True,
            "profitability_claim_allowed": False,
            "promotion_allowed": False,
            "live_broker_order_allowed": False,
            "reused_validation": "NOT_RUN_NO_READ",
            "fresh_oos": "NOT_RUN_NO_READ",
        },
    }
    inputs = run / "inputs"
    inputs.mkdir(parents=True)
    prereg_bytes = json.dumps(prereg, sort_keys=True).encode()
    (inputs / "prereg.json").write_bytes(prereg_bytes)
    (inputs / "amendment.json").write_text("{}", encoding="utf-8")
    rows: list[dict[str, object]] = []
    for reward in ("NATIVE", "SHUFFLED"):
        for seed in range(3):
            for steps in (400_000, 800_000):
                row = {
                    "reward_arm": reward,
                    "seed": seed,
                    "total_steps": steps,
                    "fit_23bp": _metric(0.6),
                    "native_23bp": _metric(0.5 if reward == "NATIVE" else 0.1),
                    "native_0bp": _metric(0.55 if reward == "NATIVE" else 0.15),
                }
                rows.append(row)
                model = run / "models" / reward / f"seed-{seed}" / f"steps-{steps}" / "model.zip"
                outcome = run / "outcomes" / reward / f"seed-{seed}" / f"steps-{steps}.json"
                model.parent.mkdir(parents=True, exist_ok=True)
                outcome.parent.mkdir(parents=True, exist_ok=True)
                model.write_bytes(b"model")
                outcome.write_text(json.dumps(row), encoding="utf-8")
    summary = {
        "schema_version": "kronos.rl-discovery.d5r.capacity.v1",
        "profile": "PRIMARY",
        "status": "COMPLETE",
        "verdict": "D5R_CAPACITY_NOT_CONFIRMED",
        "gate": {
            "verdict": "D5R_CAPACITY_NOT_CONFIRMED",
            "native_accuracy_lift": 0.01,
            "native_reward_ratio_lift": 0.01,
            "native_reward_delta_vs_shuffled": 0.4,
            "improving_seed_fraction": 1 / 3,
            "invalid_action_count": 0,
        },
        "models": rows,
        "source_run": prereg["source_run"]["run_name"],
        "approved_smoke": "type2-d5r-smoke",
        "d5_verdict_unchanged": "D5_FULL_TRAIN_COST_NOT_CONFIRMED",
        "reused_validation": "NOT_RUN_NO_READ",
        "fresh_oos": "NOT_RUN_NO_READ",
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "live_broker_order_allowed": False,
    }
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    digest = artifact_manifest_sha256(run)
    import hashlib

    prereg_sha = hashlib.sha256(prereg_bytes).hexdigest()
    receipt = {
        "schema_version": "kronos.rl-discovery.d5r.receipt.v1",
        "profile": "PRIMARY",
        "status": "COMPLETE",
        "verdict": summary["verdict"],
        "artifact_manifest_sha256": digest,
        "fresh_oos": "NOT_RUN_NO_READ",
        "live_broker_order_allowed": False,
        "primary_custody_hmac_sha256": primary_custody_signature(
            key,
            run_name=run.name,
            prereg_sha=prereg_sha,
            episode_sha="c" * 64,
            manifest_sha=digest,
            approved_smoke="type2-d5r-smoke",
        ),
    }
    (run / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")


def test_d5r_primary_requires_authenticated_exact_capacity_matrix(tmp_path: Path, monkeypatch) -> None:
    run = tmp_path / "type2-d5r-primary"
    run.mkdir()
    key = bytes(range(32))
    _write_primary(run, key)
    monkeypatch.setenv("KRONOS_D5R_APPROVAL_KEY_HEX", key.hex())
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    record = next(item for item in rl_dashboard.list_rl_runs() if item["name"] == run.name)
    detail = rl_dashboard.load_rl_run(run.name)

    assert record["artifact_type"] == "rl_discovery_d5r"
    assert record["summary"]["verdict"] == "D5R_CAPACITY_NOT_CONFIRMED"
    assert detail["detail"]["gate"]["native_reward_delta_vs_shuffled"] == 0.4
    assert detail["summary"]["primary_round_trip_cost_bp"] == 23
    assert detail["summary"]["live_broker_order_allowed"] is False

    (run / "models/NATIVE/seed-0/steps-400000/model.zip").unlink()
    blocked = rl_dashboard.load_rl_run(run.name)
    assert blocked["summary"]["status"] == "BLOCK"
    assert blocked["detail"] == {}
