"""Fail-closed D5R capacity evidence verification."""

from __future__ import annotations

import hashlib
import hmac
import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from stom_rl.rl_discovery.d5_approval import primary_custody_signature
from stom_rl.rl_discovery.d5r_contract import D5RPreregistration
from stom_rl.rl_discovery.storage import JsonValue


class _Frozen(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)


class _Metric(_Frozen):
    accuracy: FiniteFloat
    reward_ratio: FiniteFloat
    dominant_action_rate: FiniteFloat
    invalid_action_count: Literal[0]


class _Checkpoint(_Frozen):
    reward_arm: Literal["NATIVE", "SHUFFLED"]
    seed: int = Field(ge=0, le=2)
    total_steps: Literal[400000, 800000]
    fit_23bp: _Metric
    native_23bp: _Metric
    native_0bp: _Metric


class _Gate(_Frozen):
    verdict: Literal["D5R_CAPACITY_CONFIRMED", "D5R_CAPACITY_NOT_CONFIRMED"]
    native_accuracy_lift: FiniteFloat
    native_reward_ratio_lift: FiniteFloat
    native_reward_delta_vs_shuffled: FiniteFloat
    improving_seed_fraction: FiniteFloat
    invalid_action_count: Literal[0]


class _Custody(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos.rl-discovery.d5r.custody.v1"]
    run_name: str
    artifact_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_count: Literal[12]
    outcome_count: Literal[12]
    research_branch: str
    base_release: Literal["fork-v1.15.0-kronos-rl-d5-full-train-cost"]
    producer_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    producer_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    release_status: Literal["PR_PENDING"]


def valid_d5r_primary(
    run_dir: Path,
    payload: dict[str, JsonValue],
    receipt: dict[str, JsonValue],
    digest: str,
    relative_paths: frozenset[str],
    captured: Mapping[str, bytes],
) -> bool:
    """Accept only the registered, authenticated 12-checkpoint Primary matrix."""

    try:
        prereg = D5RPreregistration.model_validate_json(captured["inputs/prereg.json"])
        rows = tuple(_Checkpoint.model_validate(row) for row in payload.get("models", []))
        gate = _Gate.model_validate(payload.get("gate"))
    except (KeyError, TypeError, ValueError):
        return False
    expected = {
        (reward, seed, steps)
        for reward in ("NATIVE", "SHUFFLED")
        for seed in range(3)
        for steps in (400_000, 800_000)
    }
    observed = {(row.reward_arm, row.seed, row.total_steps) for row in rows}
    verdict = payload.get("verdict")
    approved_smoke = payload.get("approved_smoke")
    if (
        len(rows) != 12
        or observed != expected
        or verdict != gate.verdict
        or receipt.get("verdict") != verdict
        or payload.get("profile") != "PRIMARY"
        or payload.get("status") != "COMPLETE"
        or payload.get("fresh_oos") != "NOT_RUN_NO_READ"
        or payload.get("reused_validation") != "NOT_RUN_NO_READ"
        or payload.get("promotion_allowed") is not False
        or payload.get("profitability_claim_allowed") is not False
        or payload.get("live_broker_order_allowed") is not False
        or payload.get("d5_verdict_unchanged") != "D5_FULL_TRAIN_COST_NOT_CONFIRMED"
        or not isinstance(approved_smoke, str)
        or not math.isfinite(gate.improving_seed_fraction)
        or not 0 <= gate.improving_seed_fraction <= 1
        or not _valid_artifacts(relative_paths, captured, rows)
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


def _valid_artifacts(
    paths: frozenset[str],
    captured: Mapping[str, bytes],
    rows: tuple[_Checkpoint, ...],
) -> bool:
    model_paths = frozenset(
        f"models/{reward}/seed-{seed}/steps-{steps}/model.zip"
        for reward in ("NATIVE", "SHUFFLED")
        for seed in range(3)
        for steps in (400_000, 800_000)
    )
    outcome_paths = frozenset(
        f"outcomes/{reward}/seed-{seed}/steps-{steps}.json"
        for reward in ("NATIVE", "SHUFFLED")
        for seed in range(3)
        for steps in (400_000, 800_000)
    )
    observed_models = frozenset(path for path in paths if path.startswith("models/") and path.endswith("/model.zip"))
    observed_outcomes = frozenset(path for path in paths if path.startswith("outcomes/") and path.endswith(".json"))
    if observed_models != model_paths or observed_outcomes != outcome_paths:
        return False
    by_key = {(row.reward_arm, row.seed, row.total_steps): row for row in rows}
    for reward, seed, steps in by_key:
        path = f"outcomes/{reward}/seed-{seed}/steps-{steps}.json"
        try:
            outcome = _Checkpoint.model_validate_json(captured[path])
        except (KeyError, ValueError):
            return False
        if outcome != by_key[(reward, seed, steps)]:
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
        key = bytes.fromhex(os.environ.get("KRONOS_D5R_APPROVAL_KEY_HEX", ""))
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
