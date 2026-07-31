"""Fail-closed D6 reused-validation evidence verification."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import math
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, TypeAdapter

from stom_rl.rl_discovery.d3_env import D3Episode
from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d6_contract import D6GateContract, load_d6_prereg_bytes
from stom_rl.rl_discovery.d6_gate import D6Evaluation, D6GateThresholds, evaluate_d6_gate
from stom_rl.rl_discovery.storage import JsonValue

_EPISODES = TypeAdapter(tuple[D3Episode, ...])


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


class _Evaluation(_Frozen):
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: int = Field(ge=0, le=2)
    selected_steps: Literal[100000]
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_23bp: _Metric
    validation_0bp: _Metric
    maximum_drawdown_23bp: FiniteFloat = Field(ge=0)


class _TradeEvent(_Frozen):
    action: int = Field(ge=0, le=5)
    cost_bp: Literal[0, 23]
    decision_date: str = Field(min_length=1)
    expected_action: int = Field(ge=0, le=5)
    gross_return: FiniteFloat
    reward: FiniteFloat
    symbol: str | None


class _Events(_Frozen):
    validation_23bp: tuple[_TradeEvent, ...]
    validation_0bp: tuple[_TradeEvent, ...]


class _Outcome(_Evaluation):
    events: _Events


class _Gate(_Frozen):
    verdict: Literal["D6_REUSED_VALIDATION_CONFIRMED", "D6_REUSED_VALIDATION_NOT_CONFIRMED"]
    native_median_accuracy: FiniteFloat
    native_median_reward_ratio: FiniteFloat
    native_median_total_reward: FiniteFloat
    shuffled_median_reward_ratio: FiniteFloat
    native_reward_delta_vs_shuffled: FiniteFloat
    native_passing_seed_fraction: FiniteFloat
    native_median_reward_drawdown: FiniteFloat
    invalid_action_count: Literal[0]
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    promotion_allowed: Literal[False]
    profitability_claim_allowed: Literal[False]


class _Receipt(_Frozen):
    schema_version: Literal["kronos.rl-discovery.d6.receipt.v1"]
    profile: Literal["PRIMARY"]
    status: Literal["COMPLETE"]
    verdict: Literal["D6_REUSED_VALIDATION_CONFIRMED", "D6_REUSED_VALIDATION_NOT_CONFIRMED"]
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_episode_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_origin: Literal["FAILED_RUN_SNAPSHOT"]
    recovery_run: Literal["type2-d6-primary-20260731-001"]
    reused_validation: Literal["COMPLETE"]
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    live_broker_order_allowed: Literal[False]


class _Custody(_Frozen):
    schema_version: Literal["kronos.rl-discovery.d6.custody.v1"]
    run_name: str
    failed_run_name: Literal["type2-d6-primary-20260731-001"]
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_episode_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_episode_count: Literal[128]
    source_model_count: Literal[6]
    outcome_count: Literal[6]
    validation_read_count: Literal[1]
    validation_origin: Literal["FAILED_RUN_SNAPSHOT"]
    verdict: Literal["D6_REUSED_VALIDATION_CONFIRMED", "D6_REUSED_VALIDATION_NOT_CONFIRMED"]
    prereg_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    producer_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    producer_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    research_branch: str
    base_release: Literal["fork-v1.17.0-kronos-rl-d5s-stability-earlystop"]
    release_status: Literal["PR_PENDING"]


def valid_d6_primary(
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
        prereg = load_d6_prereg_bytes(captured["inputs/prereg.json"])
        rows = tuple(_Evaluation.model_validate(row) for row in rows_value)
        gate = _Gate.model_validate(payload.get("gate"))
        parsed_receipt = _Receipt.model_validate(receipt)
        episodes = _EPISODES.validate_json(captured["inputs/validation_episodes.json"])
    except (KeyError, TypeError, ValueError):
        return False
    expected = {(arm, seed) for arm in ("NATIVE", "SHUFFLED") for seed in range(3)}
    validation_sha = hashlib.sha256(captured["inputs/validation_episodes.json"]).hexdigest()
    if (
        len(rows) != 6
        or {(row.reward_arm, row.seed) for row in rows} != expected
        or len(episodes) != 128
        or payload.get("verdict") != gate.verdict
        or parsed_receipt.verdict != gate.verdict
        or payload.get("source_run") != prereg.source_run.run_name
        or payload.get("selected_steps") != 100_000
        or payload.get("validation_episode_count") != 128
        or payload.get("validation_episode_sha256") != validation_sha
        or parsed_receipt.validation_episode_sha256 != validation_sha
        or payload.get("validation_origin") != "FAILED_RUN_SNAPSHOT"
        or payload.get("recovery_run") != "type2-d6-primary-20260731-001"
        or payload.get("validation_read_count") != 1
        or payload.get("reused_validation") != "COMPLETE"
        or payload.get("fresh_oos") != "NOT_RUN_NO_READ"
        or payload.get("promotion_allowed") is not False
        or payload.get("profitability_claim_allowed") is not False
        or payload.get("live_broker_order_allowed") is not False
        or not _valid_artifacts(relative_paths, captured, rows)
        or not _gate_matches(gate, rows, prereg.gate)
    ):
        return False
    return _matches_custody(run_dir, digest)


def _valid_artifacts(
    paths: frozenset[str],
    captured: Mapping[str, bytes],
    rows: tuple[_Evaluation, ...],
) -> bool:
    expected = frozenset(
        f"outcomes/{arm}/seed-{seed}.json"
        for arm in ("NATIVE", "SHUFFLED")
        for seed in range(3)
    )
    observed = frozenset(path for path in paths if path.startswith("outcomes/") and path.endswith(".json"))
    if observed != expected or any(path.startswith("models/") for path in paths):
        return False
    indexed = {(row.reward_arm, row.seed): row for row in rows}
    for key, row in indexed.items():
        path = f"outcomes/{key[0]}/seed-{key[1]}.json"
        try:
            outcome = _Outcome.model_validate_json(captured[path])
        except (KeyError, ValueError):
            return False
        if _Evaluation.model_validate(outcome.model_dump(exclude={"events"})) != row:
            return False
    return True


def _gate_matches(
    gate: _Gate,
    rows: tuple[_Evaluation, ...],
    prereg_gate: D6GateContract,
) -> bool:
    thresholds = D6GateThresholds(
        prereg_gate.minimum_native_median_accuracy,
        prereg_gate.minimum_native_median_reward_ratio,
        prereg_gate.minimum_native_median_total_reward,
        prereg_gate.minimum_native_reward_delta_vs_shuffled,
        prereg_gate.minimum_passing_native_seed_fraction,
        prereg_gate.maximum_native_median_reward_drawdown,
        prereg_gate.zero_invalid_actions,
    )
    expected = evaluate_d6_gate(
        tuple(
            D6Evaluation(
                row.reward_arm,
                row.seed,
                _metrics(row.validation_23bp),
                row.maximum_drawdown_23bp,
            )
            for row in rows
        ),
        thresholds=thresholds,
    )
    observed_values = (
        gate.native_median_accuracy,
        gate.native_median_reward_ratio,
        gate.native_median_total_reward,
        gate.shuffled_median_reward_ratio,
        gate.native_reward_delta_vs_shuffled,
        gate.native_passing_seed_fraction,
        gate.native_median_reward_drawdown,
    )
    expected_values = (
        expected.native_median_accuracy,
        expected.native_median_reward_ratio,
        expected.native_median_total_reward,
        expected.shuffled_median_reward_ratio,
        expected.native_reward_delta_vs_shuffled,
        expected.native_passing_seed_fraction,
        expected.native_median_reward_drawdown,
    )
    return gate.verdict == expected.verdict and all(
        math.isclose(actual, target, rel_tol=0, abs_tol=1e-12)
        for actual, target in zip(observed_values, expected_values, strict=True)
    )


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


def _matches_custody(run_dir: Path, digest: str) -> bool:
    custody_path = Path(__file__).resolve().parents[1] / "docs/evidence" / f"{run_dir.name}.custody.json"
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
        and custody.verdict == "D6_REUSED_VALIDATION_NOT_CONFIRMED"
    )
