"""Fail-closed D5S stability evidence verification."""

from __future__ import annotations

import hashlib
import hmac
import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d5_approval import primary_custody_signature
from stom_rl.rl_discovery.d5s_contract import load_d5s_prereg_bytes
from stom_rl.rl_discovery.d5s_gate import (
    CHECKPOINTS,
    D5SBaseline,
    D5SCheckpointOutcome,
    D5SGateError,
    evaluate_d5s_stability_gate,
)
from stom_rl.rl_discovery.storage import JsonValue


class _Frozen(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)


class _Metric(_Frozen):
    accuracy: FiniteFloat
    reward_ratio: FiniteFloat
    total_reward: FiniteFloat
    oracle_reward: FiniteFloat
    trade_rate: FiniteFloat
    dominant_action_rate: FiniteFloat
    invalid_action_count: Literal[0]


class _Checkpoint(_Frozen):
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: int = Field(ge=0, le=2)
    total_steps: Literal[50000, 100000, 150000, 200000, 300000, 400000]
    fit_23bp: _Metric
    native_23bp: _Metric
    native_0bp: _Metric


class _TradeEvent(_Frozen):
    action: int = Field(ge=0, le=5)
    cost_bp: Literal[0, 23]
    decision_date: str = Field(min_length=1)
    expected_action: int = Field(ge=0, le=5)
    gross_return: FiniteFloat
    reward: FiniteFloat
    symbol: str | None


class _OutcomeEvents(_Frozen):
    fit_23bp: tuple[_TradeEvent, ...]
    native_23bp: tuple[_TradeEvent, ...]
    native_0bp: tuple[_TradeEvent, ...]


class _Outcome(_Checkpoint):
    events: _OutcomeEvents


class _Gate(_Frozen):
    verdict: Literal["D5S_STABILITY_CONFIRMED", "D5S_STABILITY_NOT_CONFIRMED"]
    selected_steps: Literal[50000, 100000, 150000, 200000, 300000, 400000]
    selected_native_median_accuracy: FiniteFloat
    selected_native_median_reward_ratio: FiniteFloat
    selected_native_reward_delta_vs_shuffled: FiniteFloat
    accuracy_degradation_at_400k: FiniteFloat
    reward_ratio_degradation_at_400k: FiniteFloat
    preserved_native_seed_fraction: FiniteFloat
    invalid_action_count: Literal[0]


class _Receipt(_Frozen):
    schema_version: Literal["kronos.rl-discovery.d5s.receipt.v1"]
    profile: Literal["PRIMARY"]
    status: Literal["COMPLETE"]
    verdict: Literal["D5S_STABILITY_CONFIRMED", "D5S_STABILITY_NOT_CONFIRMED"]
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    live_broker_order_allowed: Literal[False]
    primary_custody_hmac_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class _Custody(_Frozen):
    schema_version: Literal["kronos.rl-discovery.d5s.custody.v1"]
    run_name: str
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_count: Literal[36]
    outcome_count: Literal[36]
    research_branch: str
    base_release: Literal["fork-v1.16.0-kronos-rl-d5r-capacity-objective"]
    producer_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    producer_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    release_status: Literal["PR_PENDING"]


def valid_d5s_primary(
    run_dir: Path,
    payload: dict[str, JsonValue],
    receipt: dict[str, JsonValue],
    digest: str,
    relative_paths: frozenset[str],
    captured: Mapping[str, bytes],
) -> bool:
    """Accept only the authenticated preregistered 36-checkpoint D5S matrix."""

    models = payload.get("models")
    if not isinstance(models, list):
        return False
    try:
        prereg = load_d5s_prereg_bytes(captured["inputs/prereg.json"])
        rows = tuple(_Checkpoint.model_validate(row) for row in models)
        gate = _Gate.model_validate(payload.get("gate"))
        _ = _Receipt.model_validate(receipt)
    except (KeyError, TypeError, ValueError):
        return False
    expected = {
        (reward, seed, steps)
        for reward in ("NATIVE", "SHUFFLED")
        for seed in range(3)
        for steps in CHECKPOINTS
    }
    approved_smoke = payload.get("approved_smoke")
    if (
        len(rows) != 36
        or {(row.reward_arm, row.seed, row.total_steps) for row in rows} != expected
        or payload.get("verdict") != gate.verdict
        or receipt.get("verdict") != gate.verdict
        or payload.get("profile") != "PRIMARY"
        or payload.get("status") != "COMPLETE"
        or payload.get("source_run") != prereg.source_run.run_name
        or payload.get("d5_verdict_unchanged") != "D5_FULL_TRAIN_COST_NOT_CONFIRMED"
        or payload.get("d5r_verdict_unchanged") != "D5R_CAPACITY_NOT_CONFIRMED"
        or payload.get("reused_validation") != "NOT_RUN_NO_READ"
        or payload.get("fresh_oos") != "NOT_RUN_NO_READ"
        or payload.get("promotion_allowed") is not False
        or payload.get("profitability_claim_allowed") is not False
        or payload.get("live_broker_order_allowed") is not False
        or not isinstance(approved_smoke, str)
        or not _valid_artifacts(relative_paths, captured, rows)
        or not _gate_matches_rows(gate, rows)
    ):
        return False
    prereg_sha = hashlib.sha256(captured["inputs/prereg.json"]).hexdigest()
    if _matches_hmac(
        run_dir,
        receipt,
        digest,
        prereg_sha,
        prereg.source_run.episode_snapshot_sha256,
        approved_smoke,
    ):
        return True
    return _matches_custody(run_dir, digest)


def _metrics(value: _Metric) -> D3Metrics:
    return D3Metrics(
        value.accuracy,
        value.reward_ratio,
        value.total_reward,
        value.oracle_reward,
        value.trade_rate,
        value.dominant_action_rate,
        value.invalid_action_count,
    )


def _gate_matches_rows(gate: _Gate, rows: tuple[_Checkpoint, ...]) -> bool:
    outcomes = tuple(
        D5SCheckpointOutcome(row.reward_arm, row.seed, row.total_steps, _metrics(row.native_23bp))
        for row in rows
    )
    baselines = (
        D5SBaseline(0, 0.7120418848167539, 0.8727793884825973),
        D5SBaseline(1, 0.6614310645724258, 0.8503857573981751),
        D5SBaseline(2, 0.7277486910994765, 0.9037528526603933),
    )
    try:
        expected = evaluate_d5s_stability_gate(outcomes, baselines)
    except D5SGateError:
        return False
    if gate.verdict != expected.verdict or gate.selected_steps != expected.selected_steps:
        return False
    observed_values = (
        gate.selected_native_median_accuracy,
        gate.selected_native_median_reward_ratio,
        gate.selected_native_reward_delta_vs_shuffled,
        gate.accuracy_degradation_at_400k,
        gate.reward_ratio_degradation_at_400k,
        gate.preserved_native_seed_fraction,
    )
    expected_values = (
        expected.selected_native_median_accuracy,
        expected.selected_native_median_reward_ratio,
        expected.selected_native_reward_delta_vs_shuffled,
        expected.accuracy_degradation_at_400k,
        expected.reward_ratio_degradation_at_400k,
        expected.preserved_native_seed_fraction,
    )
    return gate.invalid_action_count == expected.invalid_action_count and all(
        math.isclose(actual, target, rel_tol=0, abs_tol=1e-12)
        for actual, target in zip(observed_values, expected_values, strict=True)
    )


def _valid_artifacts(
    paths: frozenset[str],
    captured: Mapping[str, bytes],
    rows: tuple[_Checkpoint, ...],
) -> bool:
    model_paths = frozenset(
        f"models/{reward}/seed-{seed}/steps-{steps}/model.zip"
        for reward in ("NATIVE", "SHUFFLED")
        for seed in range(3)
        for steps in CHECKPOINTS
    )
    outcome_paths = frozenset(path.replace("models/", "outcomes/").replace("/model.zip", ".json") for path in model_paths)
    observed_models = frozenset(path for path in paths if path.startswith("models/") and path.endswith("/model.zip"))
    observed_outcomes = frozenset(path for path in paths if path.startswith("outcomes/") and path.endswith(".json"))
    if observed_models != model_paths or observed_outcomes != outcome_paths:
        return False
    by_key = {(row.reward_arm, row.seed, row.total_steps): row for row in rows}
    for reward, seed, steps in by_key:
        path = f"outcomes/{reward}/seed-{seed}/steps-{steps}.json"
        try:
            outcome = _Outcome.model_validate_json(captured[path])
        except (KeyError, ValueError):
            return False
        if _Checkpoint.model_validate(outcome.model_dump(exclude={"events"})) != by_key[(reward, seed, steps)]:
            return False
    return True


def _matches_hmac(
    run_dir: Path,
    receipt: dict[str, JsonValue],
    digest: str,
    prereg_sha: str,
    episode_sha: str,
    approved_smoke: str,
) -> bool:
    try:
        key = bytes.fromhex(os.environ.get("KRONOS_D5S_APPROVAL_KEY_HEX", ""))
    except ValueError:
        return False
    if len(key) < 32:
        return False
    expected = primary_custody_signature(
        key,
        run_name=run_dir.name,
        prereg_sha=prereg_sha,
        episode_sha=episode_sha,
        manifest_sha=digest,
        approved_smoke=approved_smoke,
    )
    return hmac.compare_digest(str(receipt.get("primary_custody_hmac_sha256", "")), expected)


def _matches_custody(run_dir: Path, digest: str) -> bool:
    custody_path = Path(__file__).resolve().parents[1] / "docs" / "evidence" / f"{run_dir.name}.custody.json"
    try:
        custody = _Custody.model_validate_json(custody_path.read_bytes())
        summary_sha = hashlib.sha256((run_dir / "summary.json").read_bytes()).hexdigest()
        receipt_sha = hashlib.sha256((run_dir / "terminal_receipt.json").read_bytes()).hexdigest()
    except (OSError, ValueError):
        return False
    return (
        custody.run_name == run_dir.name
        and custody.artifact_manifest_sha256 == digest
        and custody.summary_sha256 == summary_sha
        and custody.terminal_receipt_sha256 == receipt_sha
    )
