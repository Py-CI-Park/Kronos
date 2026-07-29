"""Fail-closed D5 dashboard evidence verification."""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from stom_rl.rl_discovery.d4_contract import D4RewardArmId
from stom_rl.rl_discovery.d5_approval import primary_custody_signature
from stom_rl.rl_discovery.storage import JsonValue


class _D5Custody(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    run_name: str
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_count: int
    outcome_count: int
    research_branch: str
    base_release: Literal["fork-v1.14.0-kronos-rl-d4-algorithm-objective"]
    producer_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    producer_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    release_status: Literal["PR_PENDING"]


class _D5Metric(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)

    accuracy: float
    reward_ratio: float
    dominant_action_rate: float
    invalid_action_count: Literal[0]


class _D5Model(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)

    algorithm_arm: Literal["C_DQN_DISCRETE"]
    algorithm_family: Literal["DQN"]
    rl_claim_allowed: Literal[True]
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: int = Field(ge=0, le=4)
    rl_timesteps: Literal[200000]
    training_round_trip_cost_bp: Literal[23]
    fit_23bp: _D5Metric
    native_23bp: _D5Metric
    native_0bp: _D5Metric


class _D5Claims(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)

    research_only: Literal[True]
    profitability_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    live_broker_order_allowed: Literal[False]
    reused_validation: Literal["NOT_RUN_NO_READ"]
    fresh_oos: Literal["NOT_RUN_NO_READ"]


class _D5PreregBoundary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)

    schema_version: Literal["kronos.rl-discovery.d5.prereg.v1"]
    claims_boundary: _D5Claims


def valid_d5_primary(
    run_dir: Path,
    payload: dict[str, JsonValue],
    receipt: dict[str, JsonValue],
    digest: str,
    relative_paths: frozenset[str],
    captured: Mapping[str, bytes],
) -> bool:
    """Accept only the exact authenticated D5 Primary evidence contract."""

    expected = {(reward.value, seed) for reward in D4RewardArmId for seed in range(5)}
    models = payload.get("models")
    gate = payload.get("gate")
    if not isinstance(models, list) or len(models) != 10 or not isinstance(gate, dict):
        return False
    parsed_models: dict[tuple[str, int], _D5Model] = {}
    for value in models:
        if not isinstance(value, dict):
            return False
        try:
            model = _D5Model.model_validate(value)
        except ValueError:
            return False
        parsed_models[(model.reward_arm, model.seed)] = model
    observed = set(parsed_models)
    verdict = payload.get("verdict")
    approved_smoke = payload.get("approved_smoke")
    if (
        observed != expected
        or verdict not in {"D5_FULL_TRAIN_COST_CONFIRMED", "D5_FULL_TRAIN_COST_NOT_CONFIRMED"}
        or gate.get("verdict") != verdict
        or not _valid_fraction(gate.get("native_passing_seed_fraction"))
        or not _valid_fraction(gate.get("shuffled_passing_seed_fraction"))
        or not isinstance(gate.get("native_delta_vs_shuffled"), (int, float))
        or gate.get("reused_validation") != "NOT_RUN_NO_READ"
        or gate.get("fresh_oos") != "NOT_RUN_NO_READ"
        or payload.get("reused_validation") != "NOT_RUN_NO_READ"
        or payload.get("fresh_oos") != "NOT_RUN_NO_READ"
        or payload.get("primary_round_trip_cost_bp") != 23
        or payload.get("diagnostic_round_trip_cost_bp") != 0
        or payload.get("promotion_allowed") is not False
        or payload.get("profitability_claim_allowed") is not False
        or not isinstance(approved_smoke, str)
        or not _valid_artifacts(relative_paths, captured, parsed_models)
    ):
        return False
    if _matches_operator_hmac(run_dir, payload, receipt, digest, approved_smoke):
        return True
    return _matches_committed_custody(run_dir, digest)


def _valid_artifacts(
    relative_paths: frozenset[str],
    captured: Mapping[str, bytes],
    models: Mapping[tuple[str, int], _D5Model],
) -> bool:
    try:
        prereg = _D5PreregBoundary.model_validate_json(captured["inputs/prereg.json"])
    except (KeyError, ValueError):
        return False
    if prereg.claims_boundary.live_broker_order_allowed is not False:
        return False
    model_paths = frozenset(
        f"models/C_DQN_DISCRETE__{reward.value}/seed-{seed}/model.zip"
        for reward in D4RewardArmId
        for seed in range(5)
    )
    outcome_paths = frozenset(
        f"outcomes/{reward.value}/seed-{seed}.json"
        for reward in D4RewardArmId
        for seed in range(5)
    )
    observed_models = frozenset(
        path for path in relative_paths if path.startswith("models/") and path.endswith("/model.zip")
    )
    observed_outcomes = frozenset(
        path for path in relative_paths if path.startswith("outcomes/") and path.endswith(".json")
    )
    if observed_models != model_paths or observed_outcomes != outcome_paths:
        return False
    for reward in D4RewardArmId:
        for seed in range(5):
            path = f"outcomes/{reward.value}/seed-{seed}.json"
            try:
                outcome = _D5Model.model_validate_json(captured[path])
            except (KeyError, ValueError):
                return False
            if outcome != models.get((reward.value, seed)):
                return False
    return True


def _valid_fraction(value: JsonValue) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1


def _matches_operator_hmac(
    run_dir: Path,
    payload: dict[str, JsonValue],
    receipt: dict[str, JsonValue],
    digest: str,
    approved_smoke: str,
) -> bool:
    raw_key = os.environ.get("KRONOS_D5_APPROVAL_KEY_HEX", "")
    try:
        key = bytes.fromhex(raw_key)
    except ValueError:
        return False
    if len(key) < 32:
        return False
    expected = primary_custody_signature(
        key,
        run_name=run_dir.name,
        prereg_sha=str(payload.get("prereg_sha256", "")),
        episode_sha=str(payload.get("episode_snapshot_sha256", "")),
        manifest_sha=digest,
        approved_smoke=approved_smoke,
    )
    return hmac.compare_digest(str(receipt.get("primary_custody_hmac_sha256", "")), expected)


def _matches_committed_custody(run_dir: Path, digest: str) -> bool:
    custody_path = Path(__file__).resolve().parents[1] / "docs" / "evidence" / f"{run_dir.name}.custody.json"
    try:
        custody = _D5Custody.model_validate_json(custody_path.read_bytes())
        summary_sha = hashlib.sha256((run_dir / "summary.json").read_bytes()).hexdigest()
        receipt_sha = hashlib.sha256((run_dir / "terminal_receipt.json").read_bytes()).hexdigest()
    except (OSError, ValueError):
        return False
    return (
        custody.schema_version == "kronos.rl-discovery.d5.custody.v1"
        and custody.run_name == run_dir.name
        and custody.artifact_manifest_sha256 == digest
        and custody.summary_sha256 == summary_sha
        and custody.terminal_receipt_sha256 == receipt_sha
        and custody.model_count == 10
        and custody.outcome_count == 10
    )
