"""Atomic summary and terminal receipt publication for D6R."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d6r_gate import D6RGateResult
from stom_rl.rl_discovery.d6r_source import D6RSourceBundle
from stom_rl.rl_discovery.d6r_unit import D6RUnitRow
from stom_rl.rl_discovery.storage import RunDirectoryGuard, artifact_manifest_sha256


def finish_d6r(
    guard: RunDirectoryGuard,
    source: D6RSourceBundle,
    *,
    profile: str,
    rows: tuple[D6RUnitRow, ...],
    gate: D6RGateResult | None,
    approved_smoke: str | None,
) -> Path:
    verdict = "D6R_SMOKE_COMPLETE" if gate is None else gate.verdict
    invalid_actions = sum(row.evaluation_23bp.invalid_action_count for row in rows)
    summary = {
        "schema_version": "kronos.rl-discovery.d6r.falsification.v1",
        "profile": profile,
        "status": "COMPLETE",
        "verdict": verdict,
        "prereg_sha256": source.prereg_sha256,
        "source_episode_sha256": source.episode_sha256,
        "source_episode_count": len(source.episodes),
        "input_hashes": dict(source.input_hashes),
        "unit_count": len(rows),
        "invalid_action_count": invalid_actions,
        "gate": None if gate is None else asdict(gate),
        "evaluations": [asdict(row) for row in rows],
        "approved_smoke": approved_smoke,
        "training_partition": "TRAIN_ONLY",
        "normalizer": "EXISTING_FULL_TRAIN_ONLY_NORMALIZER_NO_REFIT",
        "reused_validation": "NO_READ_ALREADY_CONSUMED_DIAGNOSTIC_ONLY",
        "fresh_oos": "NOT_RUN_NO_READ",
        "d7": "LOCKED",
        "candidate_is_not_confirmation": True,
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
    }
    _ = guard.publish_bytes(canonical_json_bytes(summary), "summary.json")
    with guard.locked() as locked_dir:
        digest = artifact_manifest_sha256(
            locked_dir,
            excluded_relative_paths=frozenset({"terminal_receipt.json"}),
        )
    receipt = {
        "schema_version": "kronos.rl-discovery.d6r.receipt.v1",
        "profile": profile,
        "status": "COMPLETE",
        "verdict": verdict,
        "artifact_manifest_sha256": digest,
        "prereg_sha256": source.prereg_sha256,
        "source_episode_sha256": source.episode_sha256,
        "unit_count": len(rows),
        "invalid_action_count": invalid_actions,
        "approved_smoke": approved_smoke,
        "reused_validation": "NO_READ_ALREADY_CONSUMED_DIAGNOSTIC_ONLY",
        "fresh_oos": "NOT_RUN_NO_READ",
        "d7": "LOCKED",
        "live_broker_order_allowed": False,
    }
    _ = guard.publish_bytes(canonical_json_bytes(receipt), "terminal_receipt.json")
    return guard.verify()
