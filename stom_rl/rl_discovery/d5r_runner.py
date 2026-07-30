"""Immutable D5R diagnostic execution."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from statistics import median

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d5r_diagnostic import diagnose_d5r_unit
from stom_rl.rl_discovery.d5r_source import load_d5r_source
from stom_rl.rl_discovery.storage import (
    RunDirectoryGuard,
    artifact_manifest_sha256,
    create_run_directory,
)

def run_d5r_diagnostic(repo_root: Path, *, run_root: Path, run_id: str) -> Path:
    source = load_d5r_source(repo_root)
    unit_rows = tuple(
        {
            "reward_arm": unit.reward_arm,
            "seed": unit.seed,
            **asdict(
                diagnose_d5r_unit(
                    source.episodes,
                    unit.events,
                    cost_bp=source.prereg.d5r_1_diagnostic.cost_bp,
                )
            ),
        }
        for unit in source.units
    )
    native_rows = tuple(row for row in unit_rows if row["reward_arm"] == "NATIVE")
    median_near_25bp = median(float(row["near_optimal_25bp"]) for row in native_rows)
    median_regret_bp = median(float(row["median_regret_bp"]) for row in native_rows)
    rule = source.prereg.d5r_1_diagnostic.capacity_required_when
    capacity_required = (
        median_near_25bp < rule.median_native_near_optimal_25bp_below
        or median_regret_bp > rule.or_median_native_regret_bp_above
    )
    verdict = "D5R_CAPACITY_REQUIRED" if capacity_required else "D5R_NEAR_OPTIMAL_GAP_EXPLAINED"
    run_dir = create_run_directory(run_root, run_id)
    guard = RunDirectoryGuard.capture(run_root, run_dir)
    _ = guard.publish_bytes(source.prereg_bytes, "inputs", "prereg.json")
    summary = {
        "schema_version": "kronos.rl-discovery.d5r.diagnostic.v1",
        "research_lane": "rl_discovery",
        "experiment_id": source.prereg.experiment_id,
        "profile": "DIAGNOSTIC",
        "status": "COMPLETE",
        "verdict": verdict,
        "capacity_required": capacity_required,
        "source_run": source.prereg.source_run.run_name,
        "source_unit_count": len(source.units),
        "episode_count": len(source.episodes),
        "median_native_near_optimal_25bp": median_near_25bp,
        "median_native_regret_bp": median_regret_bp,
        "units": unit_rows,
        "d5_verdict_unchanged": "D5_FULL_TRAIN_COST_NOT_CONFIRMED",
        "no_trade_reward": 0.0,
        "oracle_reward_ratio": 1.0,
        "reused_validation": "NOT_RUN_NO_READ",
        "fresh_oos": "NOT_RUN_NO_READ",
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "live_broker_order_allowed": False,
    }
    _ = guard.publish_bytes(canonical_json_bytes(summary), "summary.json")
    with guard.locked() as locked_dir:
        digest = artifact_manifest_sha256(
            locked_dir,
            excluded_relative_paths=frozenset({"terminal_receipt.json"}),
        )
    receipt = {
        "schema_version": "kronos.rl-discovery.d5r.receipt.v1",
        "profile": "DIAGNOSTIC",
        "status": "COMPLETE",
        "verdict": verdict,
        "artifact_manifest_sha256": digest,
        "prereg_sha256": source.prereg_sha256,
        "fresh_oos": "NOT_RUN_NO_READ",
        "live_broker_order_allowed": False,
    }
    _ = guard.publish_bytes(canonical_json_bytes(receipt), "terminal_receipt.json")
    return guard.verify()
