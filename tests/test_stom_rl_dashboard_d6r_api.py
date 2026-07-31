from __future__ import annotations

# This test intentionally verifies the private artifact classifier boundary.
# pyright: reportPrivateUsage=false

from dataclasses import asdict
import hashlib
from pathlib import Path

from pytest import MonkeyPatch

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d6r_contract import load_d6r_prereg_bytes
from stom_rl.rl_discovery.d6r_gate import (
    D6RGateThresholds,
    D6RUnitOutcome,
    evaluate_d6r_gate,
)
from stom_rl.rl_discovery.d6r_unit import D6RUnitRow
from stom_rl.rl_discovery.storage import JsonValue, artifact_manifest_sha256
from webui import rl_dashboard_d6r
from webui.rl_dashboard_d6r import valid_d6r_primary
from webui.rl_dashboard_discovery import find_discovery_evidence
from webui.rl_dashboard_runs import _detect_artifact_type

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "docs/kronos_rl_discovery_type2_d6r_prereg_2026-07-31.json"


def _metric(*, total_reward: float, trade_rate: float) -> D3Metrics:
    return D3Metrics(0.24, 0.12, total_reward, 1.0, trade_rate, 0.5, 0)


def _evidence() -> tuple[
    dict[str, JsonValue],
    dict[str, JsonValue],
    frozenset[str],
    dict[str, bytes],
]:
    prereg_bytes = PREREG.read_bytes()
    prereg = load_d6r_prereg_bytes(prereg_bytes)
    rows: list[D6RUnitRow] = []
    outcomes: list[D6RUnitOutcome] = []
    captured = {"inputs/prereg.json": prereg_bytes}
    paths: set[str] = {"inputs/prereg.json", "summary.json", "terminal_receipt.json"}
    for profile in ("COST_ONLY", "TURNOVER_10BP"):
        for arm in ("NATIVE", "SHUFFLED"):
            for seed in range(3):
                for fold_id in range(5):
                    trade_rate = 0.80 if profile == "COST_ONLY" else 0.50
                    total_reward = 0.20 if arm == "NATIVE" else 0.05
                    metric = _metric(total_reward=total_reward, trade_rate=trade_rate)
                    row = D6RUnitRow(
                        profile,
                        arm,
                        seed,
                        fold_id,
                        50_000,
                        prereg.folds[fold_id].train_end_exclusive,
                        50,
                        0 if profile == "COST_ONLY" else 10,
                        metric,
                        metric,
                        0.10,
                    )
                    rows.append(row)
                    outcomes.append(
                        D6RUnitOutcome(profile, arm, seed, fold_id, metric, metric, 0.10)
                    )
                    outcome_path = f"outcomes/{profile}/{arm}/fold-{fold_id}/seed-{seed}.json"
                    model_path = f"models/{profile}/{arm}/fold-{fold_id}/seed-{seed}/model.zip"
                    captured[outcome_path] = canonical_json_bytes(
                        {**asdict(row), "events": {"evaluation_23bp": [], "evaluation_0bp": []}}
                    )
                    paths.update({outcome_path, model_path})
    gate_config = prereg.gate
    gate = evaluate_d6r_gate(
        tuple(outcomes),
        thresholds=D6RGateThresholds(
            gate_config.minimum_native_median_accuracy,
            gate_config.minimum_native_median_reward_ratio,
            gate_config.minimum_native_median_total_reward,
            gate_config.minimum_native_reward_delta_vs_shuffled,
            gate_config.minimum_positive_fold_fraction,
            gate_config.minimum_positive_seed_fraction,
            gate_config.maximum_native_median_trade_rate,
            gate_config.minimum_trade_rate_reduction_vs_cost_only,
            gate_config.maximum_native_median_reward_drawdown,
            gate_config.zero_invalid_actions,
        ),
    )
    prereg_sha = hashlib.sha256(prereg_bytes).hexdigest()
    summary: dict[str, JsonValue] = {
        "schema_version": "kronos.rl-discovery.d6r.falsification.v1",
        "profile": "PRIMARY",
        "status": "COMPLETE",
        "verdict": gate.verdict,
        "prereg_sha256": prereg_sha,
        "source_episode_sha256": prereg.source.episode_snapshot_sha256,
        "source_episode_count": 573,
        "unit_count": 60,
        "invalid_action_count": 0,
        "gate": asdict(gate),
        "evaluations": [asdict(row) for row in rows],
        "approved_smoke": "type2-d6r-smoke-20260731-001",
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
    receipt: dict[str, JsonValue] = {
        "schema_version": "kronos.rl-discovery.d6r.receipt.v1",
        "profile": "PRIMARY",
        "status": "COMPLETE",
        "verdict": gate.verdict,
        "artifact_manifest_sha256": "a" * 64,
        "prereg_sha256": prereg_sha,
        "source_episode_sha256": prereg.source.episode_snapshot_sha256,
        "unit_count": 60,
        "invalid_action_count": 0,
        "approved_smoke": "type2-d6r-smoke-20260731-001",
        "reused_validation": "NO_READ_ALREADY_CONSUMED_DIAGNOSTIC_ONLY",
        "fresh_oos": "NOT_RUN_NO_READ",
        "d7": "LOCKED",
        "live_broker_order_allowed": False,
    }
    return summary, receipt, frozenset(paths), captured


def _allow_custody(_run_dir: Path, _digest: str, _verdict: str) -> bool:
    return True


def test_d6r_primary_recomputes_gate_and_rejects_tampering(monkeypatch: MonkeyPatch) -> None:
    summary, receipt, paths, captured = _evidence()
    monkeypatch.setattr(rl_dashboard_d6r, "_matches_custody", _allow_custody)

    assert valid_d6r_primary(Path("type2-d6r-primary"), summary, receipt, "a" * 64, paths, captured)

    gate = summary["gate"]
    assert isinstance(gate, dict)
    gate["native_median_total_reward"] = 99.0
    assert not valid_d6r_primary(Path("type2-d6r-primary"), summary, receipt, "a" * 64, paths, captured)


def test_d6r_primary_is_discoverable_after_full_snapshot_verification(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    summary, receipt, paths, captured = _evidence()
    run = tmp_path / "type2-d6r-primary-20260731-001"
    for relative_path, payload in captured.items():
        path = run / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_bytes(payload)
    for relative_path in paths:
        if relative_path.startswith("models/"):
            path = run / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            _ = path.write_bytes(b"model")
    _ = (run / "summary.json").write_bytes(canonical_json_bytes(summary))
    digest = artifact_manifest_sha256(
        run,
        excluded_relative_paths=frozenset({"terminal_receipt.json"}),
    )
    receipt["artifact_manifest_sha256"] = digest
    _ = (run / "terminal_receipt.json").write_bytes(canonical_json_bytes(receipt))
    monkeypatch.setattr(rl_dashboard_d6r, "_matches_custody", _allow_custody)

    compact, detail = find_discovery_evidence(run, "rl_discovery_d6r")

    assert _detect_artifact_type(run) == "rl_discovery_d6r"
    assert compact["verdict"] == summary["verdict"]
    assert compact["type1_outcome"] == summary["verdict"]
    assert compact["fresh_oos"] == "NOT_RUN_NO_READ"
    assert detail["d7"] == "LOCKED"
