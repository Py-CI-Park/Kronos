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
        "d5r_2_capacity": {
            "reward_arms": ["NATIVE", "SHUFFLED"],
            "seeds": [0, 1, 2],
            "continuation_source_steps": 200000,
            "checkpoint_total_steps": [400000, 800000],
            "additional_steps_per_lineage": [200000, 600000],
            "algorithm": {
                "id": "C_DQN_DISCRETE",
                "family": "DQN",
                "net_arch": [256, 128],
                "gamma": 1.0,
                "learning_rate": 0.001,
                "train_freq": 4,
                "gradient_steps": 1,
            },
            "costs": {
                "training_round_trip_bp": 23,
                "primary_evaluation_round_trip_bp": 23,
                "diagnostic_zero_cost_bp": 0,
            },
            "smoke": {"reward_arms": ["NATIVE", "SHUFFLED"], "seeds": [0], "additional_steps": 2048},
            "execution_condition": "D5R-1 capacity_required_when is true",
            "gate": {
                "minimum_800k_native_median_accuracy_lift_vs_200k": 0.03,
                "minimum_800k_native_median_reward_ratio_lift_vs_200k": 0.02,
                "minimum_800k_native_reward_delta_vs_shuffled": 0.2,
                "minimum_native_improving_seed_fraction": 0.6666666666666666,
                "zero_invalid_actions": True,
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
    amendment = {
        "schema_version": "kronos.rl-discovery.d5r.amendment.v1",
        "status": "APPROVED_BEFORE_D5R2_CODE",
        "experiment_id": "TYPE2-D5R-CAPACITY-OBJECTIVE",
        "parent_prereg_commit": "bb0d97a",
        "reason": "D5 archives omit replay buffers, so the study uses deterministic replay from zero.",
        "supersedes": {
            "continuation_source_steps": 200000,
            "additional_steps_per_lineage": [200000, 600000],
        },
        "replacement_execution": {
            "method": "DETERMINISTIC_REPLAY_FROM_ZERO_WITH_IN_PROCESS_CHECKPOINTS",
            "d5_200k_role": "CUSTODY_BOUND_COMPARISON_BASELINE_ONLY",
            "reward_arms": ["NATIVE", "SHUFFLED"],
            "seeds": [0, 1, 2],
            "checkpoint_total_steps": [400000, 800000],
            "training_steps_per_lineage": 800000,
            "lineage_count": 6,
            "total_new_rl_steps": 4800000,
            "replay_buffer_continuity": "PRESERVED_WITHIN_EACH_0_TO_800K_LINEAGE",
            "fixed_execution_parameters": {
                "batch_size": 64,
                "buffer_size": 200000,
                "learning_starts": 128,
                "gamma": 1.0,
                "learning_rate": 0.001,
                "train_freq": 4,
                "gradient_steps": 1,
                "net_arch": [256, 128],
                "device": "cpu",
                "deterministic_algorithms": True,
                "reset_num_timesteps_between_checkpoints": False,
            },
        },
        "unchanged": {
            "gate": "UNCHANGED",
            "training_round_trip_bp": 23,
            "primary_evaluation_round_trip_bp": 23,
            "diagnostic_zero_cost_bp": 0,
            "native_and_shuffled_controls": True,
            "reused_validation": "NOT_RUN_NO_READ",
            "fresh_oos": "NOT_RUN_NO_READ",
            "profitability_claim_allowed": False,
            "promotion_allowed": False,
            "live_broker_order_allowed": False,
        },
    }
    (inputs / "amendment.json").write_text(json.dumps(amendment), encoding="utf-8")
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
            "native_accuracy_lift": -0.2120418848167539,
            "native_reward_ratio_lift": -0.3727793884825973,
            "native_reward_delta_vs_shuffled": 0.4,
            "improving_seed_fraction": 0.0,
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


def _resign_primary(run: Path, key: bytes) -> None:
    import hashlib

    receipt = json.loads((run / "terminal_receipt.json").read_text(encoding="utf-8"))
    digest = artifact_manifest_sha256(run)
    receipt["artifact_manifest_sha256"] = digest
    receipt["primary_custody_hmac_sha256"] = primary_custody_signature(
        key,
        run_name=run.name,
        prereg_sha=hashlib.sha256((run / "inputs/prereg.json").read_bytes()).hexdigest(),
        episode_sha="c" * 64,
        manifest_sha=digest,
        approved_smoke=receipt["approved_smoke"] if "approved_smoke" in receipt else "type2-d5r-smoke",
    )
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


def test_d5r_primary_blocks_authenticated_malformed_amendment(tmp_path: Path, monkeypatch) -> None:
    run = tmp_path / "type2-d5r-primary-malformed-amendment"
    run.mkdir()
    key = bytes(range(32))
    _write_primary(run, key)
    amendment_path = run / "inputs/amendment.json"
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    amendment["replacement_execution"]["fixed_execution_parameters"]["device"] = "cuda"
    amendment_path.write_text(json.dumps(amendment), encoding="utf-8")
    _resign_primary(run, key)
    monkeypatch.setenv("KRONOS_D5R_APPROVAL_KEY_HEX", key.hex())
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    blocked = rl_dashboard.load_rl_run(run.name)

    assert blocked["summary"]["status"] == "BLOCK"
    assert blocked["detail"] == {}


def test_d5r_primary_blocks_authenticated_inconsistent_gate(tmp_path: Path, monkeypatch) -> None:
    run = tmp_path / "type2-d5r-primary-inconsistent-gate"
    run.mkdir()
    key = bytes(range(32))
    _write_primary(run, key)
    summary_path = run / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["gate"]["native_reward_delta_vs_shuffled"] = 0.5
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    _resign_primary(run, key)
    monkeypatch.setenv("KRONOS_D5R_APPROVAL_KEY_HEX", key.hex())
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    blocked = rl_dashboard.load_rl_run(run.name)

    assert blocked["summary"]["status"] == "BLOCK"
    assert blocked["detail"] == {}
