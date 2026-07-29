"""Fail-closed D5 dashboard evidence verification."""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from typing import ClassVar

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


def valid_d5_primary(
    run_dir: Path,
    payload: dict[str, JsonValue],
    receipt: dict[str, JsonValue],
    digest: str,
) -> bool:
    """Accept only the exact authenticated D5 Primary evidence contract."""

    expected = {(reward.value, seed) for reward in D4RewardArmId for seed in range(5)}
    models = payload.get("models")
    gate = payload.get("gate")
    if not isinstance(models, list) or len(models) != 10 or not isinstance(gate, dict):
        return False
    observed: set[tuple[str, int]] = set()
    for value in models:
        if not isinstance(value, dict) or not _valid_model(value):
            return False
        reward, seed = value.get("reward_arm"), value.get("seed")
        if not isinstance(reward, str) or not isinstance(seed, int):
            return False
        observed.add((reward, seed))
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
    ):
        return False
    if _matches_operator_hmac(run_dir, payload, receipt, digest, approved_smoke):
        return True
    return _matches_committed_custody(run_dir, digest)


def _valid_model(row: dict[str, JsonValue]) -> bool:
    return (
        row.get("algorithm_arm") == "C_DQN_DISCRETE"
        and row.get("algorithm_family") in {None, "DQN"}
        and row.get("seed") in range(5)
        and row.get("rl_timesteps") in {None, 200000}
        and row.get("training_round_trip_cost_bp") in {None, 23}
        and all(isinstance(row.get(metric), dict) for metric in ("fit_23bp", "native_23bp", "native_0bp"))
    )


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
