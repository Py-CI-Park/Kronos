"""Fail-closed D6R2 evidence verification for the dashboard."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import math
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d6r2_contract import load_d6r2_prereg_bytes
from stom_rl.rl_discovery.d6r2_gate import D6R2GateThresholds, D6R2UnitOutcome, evaluate_d6r2_gate
from stom_rl.rl_discovery.storage import JsonValue


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)


class _Metric(_FrozenModel):
    accuracy: float
    reward_ratio: float
    total_reward: float
    oracle_reward: float
    trade_rate: float
    dominant_action_rate: float
    invalid_action_count: int


class _Evaluation(_FrozenModel):
    algorithm: Literal["DQN_GAMMA_0_CONTEXTUAL", "DQN_GAMMA_1_SEQUENCE_CONTROL", "RIDGE_REWARD_CEILING"]
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: int
    fold_id: int
    normalizer_evaluation_row_count: int
    evaluation_23bp: _Metric
    maximum_drawdown_23bp: float


class _Gate(_FrozenModel):
    verdict: str
    passed_gate_count: int
    total_gate_count: int
    invalid_action_count: int
    normalizer_evaluation_row_count: int
    gamma0_native_median_accuracy: float
    gamma0_native_median_reward_ratio: float
    gamma0_lift_vs_gamma1: float
    gamma0_delta_vs_shuffled: float
    gamma0_positive_fold_fraction: float
    gamma0_positive_seed_fraction: float
    gamma0_native_median_trade_rate: float
    gamma0_native_median_drawdown: float
    ridge_native_median_reward_ratio: float
    ridge_delta_vs_shuffled: float
    ridge_positive_fold_fraction: float


class _Custody(_FrozenModel):
    run_name: str
    artifact_manifest_sha256: str
    summary_sha256: str
    terminal_receipt_sha256: str
    verdict: str
    unit_count: Literal[70]


def valid_d6r2_primary(
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
        prereg = load_d6r2_prereg_bytes(captured["inputs/prereg.json"])
        rows = tuple(_Evaluation.model_validate(row) for row in rows_value)
        gate = _Gate.model_validate(payload.get("gate"))
    except (KeyError, TypeError, ValueError):
        return False
    prereg_sha = hashlib.sha256(captured["inputs/prereg.json"]).hexdigest()
    if (
        payload.get("verdict") != gate.verdict
        or receipt.get("verdict") != gate.verdict
        or payload.get("prereg_sha256") != prereg_sha
        or receipt.get("prereg_sha256") != prereg_sha
        or payload.get("source_episode_sha256") != prereg.source.episode_identity_sha256
        or payload.get("source_episode_count") != 573
        or payload.get("unit_count") != 70
        or payload.get("invalid_action_count") != 0
        or payload.get("normalizer_evaluation_row_count") != 0
        or payload.get("normalizer") != "FOLD_LOCAL_TRAIN_ONLY_TYPE7_MEDIAN_IQR"
        or payload.get("fresh_oos") != "NOT_RUN_NO_READ"
        or payload.get("d7") != "LOCKED"
        or any(payload.get(key) is not False for key in ("promotion_allowed", "profitability_claim_allowed", "paper_forward_allowed", "live_broker_order_allowed"))
        or not _matrix_matches(rows, relative_paths, captured)
        or not _gate_matches(gate, rows)
    ):
        return False
    return _custody_matches(run_dir, digest, gate.verdict)


def _matrix_matches(rows: tuple[_Evaluation, ...], paths: frozenset[str], captured: Mapping[str, bytes]) -> bool:
    keys = {(row.algorithm, row.reward_arm, row.seed, row.fold_id) for row in rows}
    expected = {
        (algorithm, arm, seed, fold)
        for algorithm in ("DQN_GAMMA_0_CONTEXTUAL", "DQN_GAMMA_1_SEQUENCE_CONTROL")
        for arm in ("NATIVE", "SHUFFLED") for seed in range(3) for fold in range(5)
    } | {("RIDGE_REWARD_CEILING", arm, 0, fold) for arm in ("NATIVE", "SHUFFLED") for fold in range(5)}
    outcomes = {path for path in paths if path.startswith("outcomes/")}
    models = {path for path in paths if path.startswith("models/")}
    expected_outcomes = {_outcome_path(*key) for key in expected}
    expected_models = {_model_path(*key) for key in expected}
    return len(rows) == 70 and keys == expected and outcomes == expected_outcomes and models == expected_models and all(path in captured for path in expected_outcomes)


def _gate_matches(gate: _Gate, rows: tuple[_Evaluation, ...]) -> bool:
    expected = evaluate_d6r2_gate(
        tuple(D6R2UnitOutcome(row.algorithm, row.reward_arm, row.seed, row.fold_id, _metric(row.evaluation_23bp), row.maximum_drawdown_23bp, row.normalizer_evaluation_row_count) for row in rows),
        thresholds=D6R2GateThresholds.registered(),
    )
    if (
        gate.verdict != expected.verdict
        or gate.passed_gate_count != expected.passed_gate_count
        or gate.total_gate_count != expected.total_gate_count
        or gate.invalid_action_count != expected.invalid_action_count
        or gate.normalizer_evaluation_row_count != expected.normalizer_evaluation_row_count
    ):
        return False
    observed = (
        gate.gamma0_native_median_accuracy,
        gate.gamma0_native_median_reward_ratio,
        gate.gamma0_lift_vs_gamma1,
        gate.gamma0_delta_vs_shuffled,
        gate.gamma0_positive_fold_fraction,
        gate.gamma0_positive_seed_fraction,
        gate.gamma0_native_median_trade_rate,
        gate.gamma0_native_median_drawdown,
        gate.ridge_native_median_reward_ratio,
        gate.ridge_delta_vs_shuffled,
        gate.ridge_positive_fold_fraction,
    )
    target = (
        expected.gamma0_native_median_accuracy,
        expected.gamma0_native_median_reward_ratio,
        expected.gamma0_lift_vs_gamma1,
        expected.gamma0_delta_vs_shuffled,
        expected.gamma0_positive_fold_fraction,
        expected.gamma0_positive_seed_fraction,
        expected.gamma0_native_median_trade_rate,
        expected.gamma0_native_median_drawdown,
        expected.ridge_native_median_reward_ratio,
        expected.ridge_delta_vs_shuffled,
        expected.ridge_positive_fold_fraction,
    )
    return all(math.isclose(actual, wanted, rel_tol=0, abs_tol=1e-12) for actual, wanted in zip(observed, target, strict=True))


def _metric(value: _Metric) -> D3Metrics:
    return D3Metrics(value.accuracy, value.reward_ratio, value.total_reward, value.oracle_reward, value.trade_rate, value.dominant_action_rate, value.invalid_action_count)


def _outcome_path(algorithm: str, arm: str, seed: int, fold: int) -> str:
    return f"outcomes/{algorithm}/{arm}/fold-{fold}/seed-{seed}.json"


def _model_path(algorithm: str, arm: str, seed: int, fold: int) -> str:
    suffix = "npz" if algorithm == "RIDGE_REWARD_CEILING" else "zip"
    return f"models/{algorithm}/{arm}/fold-{fold}/seed-{seed}/model.{suffix}"


def _custody_matches(run_dir: Path, digest: str, verdict: str) -> bool:
    path = Path(__file__).resolve().parents[1] / "docs/evidence" / f"{run_dir.name}.custody.json"
    try:
        custody = _Custody.model_validate_json(path.read_bytes())
        summary_sha = hashlib.sha256((run_dir / "summary.json").read_bytes()).hexdigest()
        receipt_sha = hashlib.sha256((run_dir / "terminal_receipt.json").read_bytes()).hexdigest()
    except (OSError, ValueError):
        return False
    return custody.run_name == run_dir.name and custody.artifact_manifest_sha256 == digest and custody.summary_sha256 == summary_sha and custody.terminal_receipt_sha256 == receipt_sha and custody.verdict == verdict
