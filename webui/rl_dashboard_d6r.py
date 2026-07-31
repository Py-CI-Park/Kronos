"""Fail-closed D6R TRAIN_ONLY falsification evidence verification."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import math
from pathlib import Path

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d6r_contract import D6RGate, load_d6r_prereg_bytes
from stom_rl.rl_discovery.d6r_gate import (
    D6RGateThresholds,
    D6RUnitOutcome,
    evaluate_d6r_gate,
)
from stom_rl.rl_discovery.storage import JsonValue

if __package__:
    from .rl_dashboard_d6r_schema import (
        D6RCustody,
        D6REvaluation,
        D6RGateEvidence,
        D6RMetric,
        D6ROutcome,
        D6RReceipt,
    )
else:  # pragma: no cover - supports direct script-style imports
    from webui.rl_dashboard_d6r_schema import (
        D6RCustody,
        D6REvaluation,
        D6RGateEvidence,
        D6RMetric,
        D6ROutcome,
        D6RReceipt,
    )


def valid_d6r_primary(
    run_dir: Path,
    payload: dict[str, JsonValue],
    receipt: dict[str, JsonValue],
    digest: str,
    relative_paths: frozenset[str],
    captured: Mapping[str, bytes],
) -> bool:
    rows_value = payload.get("evaluations")
    if not isinstance(rows_value, list):
        return False
    try:
        prereg = load_d6r_prereg_bytes(captured["inputs/prereg.json"])
        rows = tuple(D6REvaluation.model_validate(row) for row in rows_value)
        gate = D6RGateEvidence.model_validate(payload.get("gate"))
        parsed_receipt = D6RReceipt.model_validate(receipt)
    except (KeyError, TypeError, ValueError):
        return False
    prereg_sha = hashlib.sha256(captured["inputs/prereg.json"]).hexdigest()
    if (
        payload.get("verdict") != gate.verdict
        or parsed_receipt.verdict != gate.verdict
        or payload.get("prereg_sha256") != prereg_sha
        or parsed_receipt.prereg_sha256 != prereg_sha
        or payload.get("source_episode_sha256") != prereg.source.episode_snapshot_sha256
        or parsed_receipt.source_episode_sha256 != prereg.source.episode_snapshot_sha256
        or payload.get("source_episode_count") != 573
        or payload.get("unit_count") != 60
        or payload.get("invalid_action_count") != 0
        or payload.get("training_partition") != "TRAIN_ONLY"
        or payload.get("normalizer") != "EXISTING_FULL_TRAIN_ONLY_NORMALIZER_NO_REFIT"
        or payload.get("reused_validation") != "NO_READ_ALREADY_CONSUMED_DIAGNOSTIC_ONLY"
        or payload.get("fresh_oos") != "NOT_RUN_NO_READ"
        or payload.get("d7") != "LOCKED"
        or payload.get("candidate_is_not_confirmation") is not True
        or any(payload.get(key) is not False for key in (
            "promotion_allowed",
            "profitability_claim_allowed",
            "paper_forward_allowed",
            "live_broker_order_allowed",
        ))
        or not _valid_matrix(relative_paths, captured, rows)
        or not _gate_matches(gate, rows, prereg.gate)
    ):
        return False
    return _matches_custody(run_dir, digest, gate.verdict)


def _valid_matrix(
    paths: frozenset[str],
    captured: Mapping[str, bytes],
    rows: tuple[D6REvaluation, ...],
) -> bool:
    expected_keys = {
        (profile, arm, seed, fold_id)
        for profile in ("COST_ONLY", "TURNOVER_10BP")
        for arm in ("NATIVE", "SHUFFLED")
        for seed in range(3)
        for fold_id in range(5)
    }
    indexed = {(row.profile, row.reward_arm, row.seed, row.fold_id): row for row in rows}
    expected_outcomes = frozenset(_outcome_path(*key) for key in expected_keys)
    expected_models = frozenset(_model_path(*key) for key in expected_keys)
    observed_outcomes = frozenset(path for path in paths if path.startswith("outcomes/"))
    observed_models = frozenset(path for path in paths if path.startswith("models/"))
    if len(rows) != 60 or set(indexed) != expected_keys:
        return False
    if observed_outcomes != expected_outcomes or observed_models != expected_models:
        return False
    for key, row in indexed.items():
        try:
            outcome = D6ROutcome.model_validate_json(captured[_outcome_path(*key)])
        except (KeyError, ValueError):
            return False
        if D6REvaluation.model_validate(outcome.model_dump(exclude={"events"})) != row:
            return False
    return True


def _outcome_path(profile: str, arm: str, seed: int, fold_id: int) -> str:
    return f"outcomes/{profile}/{arm}/fold-{fold_id}/seed-{seed}.json"


def _model_path(profile: str, arm: str, seed: int, fold_id: int) -> str:
    return f"models/{profile}/{arm}/fold-{fold_id}/seed-{seed}/model.zip"


def _gate_matches(gate: D6RGateEvidence, rows: tuple[D6REvaluation, ...], contract: D6RGate) -> bool:
    expected = evaluate_d6r_gate(
        tuple(
            D6RUnitOutcome(
                row.profile,
                row.reward_arm,
                row.seed,
                row.fold_id,
                _metrics(row.evaluation_23bp),
                _metrics(row.evaluation_0bp),
                row.maximum_drawdown_23bp,
            )
            for row in rows
        ),
        thresholds=D6RGateThresholds(
            contract.minimum_native_median_accuracy,
            contract.minimum_native_median_reward_ratio,
            contract.minimum_native_median_total_reward,
            contract.minimum_native_reward_delta_vs_shuffled,
            contract.minimum_positive_fold_fraction,
            contract.minimum_positive_seed_fraction,
            contract.maximum_native_median_trade_rate,
            contract.minimum_trade_rate_reduction_vs_cost_only,
            contract.maximum_native_median_reward_drawdown,
            contract.zero_invalid_actions,
        ),
    )
    if (
        gate.verdict != expected.verdict
        or gate.invalid_action_count != expected.invalid_action_count
        or gate.passed_gate_count != expected.passed_gate_count
        or gate.total_gate_count != expected.total_gate_count
    ):
        return False
    observed_values = (
        gate.native_median_accuracy,
        gate.native_median_reward_ratio,
        gate.native_median_total_reward,
        gate.native_reward_delta_vs_shuffled,
        gate.positive_fold_fraction,
        gate.positive_seed_fraction,
        gate.native_median_trade_rate,
        gate.trade_rate_reduction_vs_cost_only,
        gate.native_median_reward_drawdown,
    )
    expected_values = (
        expected.native_median_accuracy,
        expected.native_median_reward_ratio,
        expected.native_median_total_reward,
        expected.native_reward_delta_vs_shuffled,
        expected.positive_fold_fraction,
        expected.positive_seed_fraction,
        expected.native_median_trade_rate,
        expected.trade_rate_reduction_vs_cost_only,
        expected.native_median_reward_drawdown,
    )
    return all(
        math.isclose(actual, target, rel_tol=0, abs_tol=1e-12)
        for actual, target in zip(observed_values, expected_values, strict=True)
    )


def _metrics(value: D6RMetric) -> D3Metrics:
    return D3Metrics(
        value.accuracy,
        value.reward_ratio,
        value.total_reward,
        value.oracle_reward,
        value.trade_rate,
        value.dominant_action_rate,
        value.invalid_action_count,
    )


def _matches_custody(run_dir: Path, digest: str, verdict: str) -> bool:
    path = Path(__file__).resolve().parents[1] / "docs/evidence" / f"{run_dir.name}.custody.json"
    try:
        custody = D6RCustody.model_validate_json(path.read_bytes())
        summary_sha = hashlib.sha256((run_dir / "summary.json").read_bytes()).hexdigest()
        receipt_sha = hashlib.sha256((run_dir / "terminal_receipt.json").read_bytes()).hexdigest()
    except (OSError, ValueError):
        return False
    return (
        custody.run_name == run_dir.name
        and custody.artifact_manifest_sha256 == digest
        and custody.summary_sha256 == summary_sha
        and custody.terminal_receipt_sha256 == receipt_sha
        and custody.verdict == verdict
    )
