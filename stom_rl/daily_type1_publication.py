"""Fail-closed publication move for the recovered Type 1 public run.

The publisher performs two mutations only: durable creation of the canonical
publication receipt inside the frozen staging run, followed by an atomic
same-volume directory rename into the V6 dashboard discovery root.  It never
copies, deletes, overwrites, or opens fresh-OOS evidence.
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import stat
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from stom_rl.daily_type1_contract import FEATURES, canonical_json_bytes, sha256_canonical
from stom_rl.daily_type1_public_data import (
    DATASET_ID,
    RECEIPT_ROLE as MATERIALIZER_RECEIPT_ROLE,
    _validate_complete_receipt,
    verify_public_materialization,
)
from stom_rl.daily_type1_public_run import (
    FALSE_RESEARCH_LOCKS,
    FINAL_MODEL_ONLY,
    ORIGINAL_BLOCKED_REASON,
    RECOVERY_MANIFEST_SCHEMA,
    RECOVERY_MODE,
    RECOVERY_RECEIPT_ROLE,
    RECOVERY_RECEIPT_SCHEMA,
    RECOVERY_ROLE,
    RECOVERY_SOURCE_COMMIT,
    REPLACEMENT_AUTHORITY_ID,
    REPLACEMENT_CUSTODY_UID,
    REPLACEMENT_RUN_ID,
    REPLACEMENT_TRAIN_ID,
    TIMESTEPS_PER_SEED,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGING_RUN_ROOT = REPO_ROOT / "artifacts" / "type1-public-runs" / REPLACEMENT_RUN_ID
DESTINATION_RUN_ROOT = REPO_ROOT / "webui" / "rl_runs" / "v6_daily_h1" / DATASET_ID / REPLACEMENT_RUN_ID
SOURCE_LOGICAL_PATH = "artifacts/type1-public-runs/train_type1-public-005"
DESTINATION_LOGICAL_PATH = "webui/rl_runs/v6_daily_h1/type1-close-20260803-005/train_type1-public-005"
PUBLICATION_RECEIPT_NAME = "publication_receipt.json"
PUBLICATION_SCHEMA_VERSION = "kronos.type1.publication-receipt.v2"
_COMPLETED_PUBLICATION_SCHEMA_VERSION = "kronos.type1.publication-receipt.v1"
PUBLICATION_ROLE = "TYPE1_PUBLICATION_RECEIPT"
_RUN_SCHEMA_VERSION = "kronos_type1_g002_public_run.v1"
_RUN_EVIDENCE_MODE_COMPLETED = "COMPLETED_RUN"
_RUN_EVIDENCE_MODE_RECOVERED = "RECOVERED_AFTER_BLOCK"
_ORIGINAL_BLOCK_REASON = ORIGINAL_BLOCKED_REASON
_FRESH_RUN_NOT_RUN = {"state": "NOT_RUN", "metrics": None}
_FRESH_NO_READ = {"state": "NOT_RUN", "metrics": None, "read_performed": False}
_PUBLIC_ROWS_MAX_BYTES = 512 * 1024 * 1024
_FRESH_MATERIALIZER_NOT_RUN = {"state": "NOT_RUN", "read_performed": False}
_ORIGINAL_BLOCK_RECEIPT = {
    "execution_status": "BLOCK",
    "fresh_oos": _FRESH_RUN_NOT_RUN,
    "reason": _ORIGINAL_BLOCK_REASON,
    "verdict": "NO_GO",
}
_REPLACEMENT_IDENTITY = {
    "authority_id": REPLACEMENT_AUTHORITY_ID,
    "dataset_id": DATASET_ID,
    "train_id": REPLACEMENT_TRAIN_ID,
    "train_run_id": REPLACEMENT_RUN_ID,
    "custody_uid": REPLACEMENT_CUSTODY_UID,
}
_TRAINING_CONTRACT = {
    "seeds": [0, 1, 2, 3, 4],
    "timesteps_per_seed": TIMESTEPS_PER_SEED,
    "device": "cpu",
    "validation_visible_to_training": False,
    "eval_callback": False,
    "early_stopping": False,
    "best_model_selection": False,
    "checkpoint_selection": False,
    "member_selection": False,
    "saved_artifact": FINAL_MODEL_ONLY,
    "synthetic_oracle_calibration": False,
}
_MATERIALIZER_ROLES = {
    "public_rows.json": "CANONICAL_PUBLIC_ROWS",
    "dataset_manifest.json": "CANONICAL_DATASET_MANIFEST",
    "materializer_complete_receipt.json": MATERIALIZER_RECEIPT_ROLE,
}
_COMPLETED_RUN_ROOT_ENTRIES_BEFORE_RECEIPT = frozenset({"receipt.json", "run_manifest.json", "primary", "shuffled_reward"})
_COMPLETED_RUN_ROOT_ENTRIES_WITH_RECEIPT = _COMPLETED_RUN_ROOT_ENTRIES_BEFORE_RECEIPT | frozenset({PUBLICATION_RECEIPT_NAME})
_RECOVERED_RUN_ROOT_ENTRIES_BEFORE_RECEIPT = frozenset({"receipt.json", "recovery_manifest.json", "recovery_receipt.json", "primary", "shuffled_reward"})
_RECOVERED_RUN_ROOT_ENTRIES_WITH_RECEIPT = _RECOVERED_RUN_ROOT_ENTRIES_BEFORE_RECEIPT | frozenset({PUBLICATION_RECEIPT_NAME})
_RECOVERY_FAMILIES = ("primary", "shuffled_reward")
_RECOVERY_SEEDS = (0, 1, 2, 3, 4)
_RECOVERY_MEMBER_ARTIFACT_NAMES = ("final_model.zip", "normalizer.json")
_RECOVERY_MANIFEST_KEYS = frozenset({
    "schema_version",
    "role",
    "status",
    "recovery_status",
    "recovery_mode",
    "source_commit",
    "original_run_id",
    "reused_original_run_id",
    "original_block",
    "protocol",
    "identities",
    "features",
    "public_splits",
    "session_pairing",
    "training",
    "members",
    "aggregation",
    "pretraining_gate",
    "controls",
    "source_sha256",
    "materializer_sha256",
    "custody_bindings",
    "fresh_oos",
    "false_research_locks",
    "execution_status",
    "verdict",
    "decision",
    "claims",
})
_RECOVERY_RECEIPT_KEYS = frozenset({
    "schema_version",
    "role",
    "status",
    "execution_status",
    "verdict",
    "decision",
    "run_id",
    "recovery_manifest_sha256",
    "blocked_receipt_sha256",
    "blocked_receipt_path",
    "blocked_reason",
    "original_block_reason",
    "original_block_preserved",
    "retraining_performed",
    "overwrite_performed",
    "move_performed",
    "delete_performed",
    "fresh_oos",
    "member_artifact_sha256",
    "source_sha256",
    "materializer_sha256",
    "outcome",
})
_RECOVERY_IDENTITY_KEYS = frozenset({
    "authority_id",
    "dataset_id",
    "train_id",
    "train_run_id",
    "custody_uid",
    "amendment_sha256",
    "authority_sha256",
    "materializer_sha256",
    "materializer_complete_receipt_sha256",
    "source_database_identity",
    "materializer_source_sha256",
    "preregistration_sha256",
    "parent_protocol_sha256",
    "runner_source_sha256",
    "authority_sessions",
})
_RECOVERY_AUTHORITY_SESSION_KEYS = frozenset({
    "count",
    "first",
    "last",
    "ordered",
    "pairs",
    "parity",
    "trailing_embargo",
})
_RECOVERY_SOURCE_SHA256_KEYS = frozenset({
    "runner",
    "market",
    "protocol",
    "amendment",
    "authority",
    "public_rows",
    "dataset_manifest",
    "materializer_manifest",
    "materializer_complete_receipt",
})
_RECOVERY_CUSTODY_BINDING_KEYS = frozenset({
    "blocked_receipt",
    "protocol",
    "amendment",
    "public_rows",
    "dataset_manifest",
    "materializer_manifest",
    "materializer_complete_receipt",
    "authority",
    "runner",
    "market",
})
_RECOVERY_ORIGINAL_BLOCK_KEYS = frozenset({
    "path",
    "receipt_sha256",
    "status",
    "execution_status",
    "verdict",
    "reason",
    "fresh_oos",
    "preserved_byte_identical",
})
_RECOVERY_TRAINING_CONTRACT = {
    "primary_seeds": list(_RECOVERY_SEEDS),
    "shuffled_reward_seeds": list(_RECOVERY_SEEDS),
    "timesteps_per_seed": TIMESTEPS_PER_SEED,
    "device": "cpu",
    "validation_visible_to_training": False,
    "eval_callback": False,
    "early_stopping": False,
    "best_model_selection": False,
    "checkpoint_selection": False,
    "member_selection": False,
    "saved_artifact": FINAL_MODEL_ONLY,
    "synthetic_oracle_calibration": False,
    "retraining_performed": False,
}
_RECOVERY_CLAIMS = {
    "profitability": "NOT_CLAIMED",
    "live": "NOT_CLAIMED",
    "fresh_oos": "NOT_RUN_NO_READ",
    "outcome": "NO_GO_ONLY",
}
_RECOVERY_PUBLICATION_DISCLOSURE_KEYS = frozenset({
    "recovery_manifest_sha256",
    "blocked_receipt_sha256",
    "members",
})
_RUN_ROOT_ENTRIES_BEFORE_RECEIPT = _COMPLETED_RUN_ROOT_ENTRIES_BEFORE_RECEIPT
_RUN_ROOT_ENTRIES_WITH_RECEIPT = _COMPLETED_RUN_ROOT_ENTRIES_WITH_RECEIPT


class Type1PublicationError(ValueError):
    """Raised when Type 1 run publication must fail closed."""


def publish_type1_run() -> dict[str, Any]:
    """Publish the one authorized Type 1 public run into the V6 discovery root."""
    return _publish_verified_run(
        STAGING_RUN_ROOT,
        DESTINATION_RUN_ROOT,
        source_logical_path=SOURCE_LOGICAL_PATH,
        destination_logical_path=DESTINATION_LOGICAL_PATH,
    )

def _select_run_evidence_mode(
    source: Path,
    destination: Path,
    *,
    source_logical_path: str,
    destination_logical_path: str,
) -> str:
    production_logical_paths = (
        source_logical_path == SOURCE_LOGICAL_PATH
        and destination_logical_path == DESTINATION_LOGICAL_PATH
    )
    production_identity = (
        production_logical_paths
        or source.name == REPLACEMENT_RUN_ID
        or destination.name == REPLACEMENT_RUN_ID
    )
    if production_identity:
        if not production_logical_paths:
            raise Type1PublicationError("recovered production publication logical paths do not match the authorized contract")
        return _RUN_EVIDENCE_MODE_RECOVERED
    if not source_logical_path or not destination_logical_path:
        raise Type1PublicationError("publication receipt logical paths must be non-empty")
    return _RUN_EVIDENCE_MODE_COMPLETED

def _publish_verified_run(
    source_root: Path | str,
    destination_root: Path | str,
    *,
    source_logical_path: str,
    destination_logical_path: str,
) -> dict[str, Any]:
    """Internal test seam for the exact production publication protocol."""
    source = Path(source_root)
    destination = Path(destination_root)
    destination_parent = destination.parent
    run_evidence_mode = _select_run_evidence_mode(
        source,
        destination,
        source_logical_path=source_logical_path,
        destination_logical_path=destination_logical_path,
    )

    source_exists = _exists_for_identity(source)
    destination_exists = _exists_for_identity(destination)
    if source_exists and destination_exists:
        raise Type1PublicationError("source and destination both exist; refusing overwrite or delete recovery")
    if not source_exists:
        if destination_exists:
            return _recover_published_destination(
                destination,
                source_logical_path=source_logical_path,
                destination_logical_path=destination_logical_path,
            )
        raise FileNotFoundError(source)
    if destination_exists:
        raise Type1PublicationError("destination already exists; refusing overwrite")

    _reject_existing_indirection(source)
    _reject_existing_indirection(destination_parent)
    _reject_absent_destination_indirection(destination)
    _reject_tree_indirection(source)

    receipt_path = source / PUBLICATION_RECEIPT_NAME
    has_staged_receipt = _exists_for_identity(receipt_path)
    run_evidence = _verify_run_root(source, allow_publication_receipt=has_staged_receipt, run_evidence_mode=run_evidence_mode)

    # The immutable materialization verifier is intentionally called before the
    # move, while the destination parent still contains exactly the three
    # materializer artifacts.  After publication the run directory is an allowed
    # fourth child, so later checks verify the named artifacts directly.
    try:
        verify_public_materialization(destination_parent)
    except Exception as exc:
        raise Type1PublicationError("destination parent is not the canonical three-artifact materialization") from exc
    materializer = _verify_materializer_artifacts(destination_parent)
    _verify_run_materializer_bindings(run_evidence, materializer)

    _require_same_volume(source, destination_parent)
    receipt = _publication_receipt(
        source_logical_path=source_logical_path,
        destination_logical_path=destination_logical_path,
        run_evidence=run_evidence,
        materializer_evidence=materializer,
    )
    if has_staged_receipt:
        _verify_publication_receipt(source, expected_receipt=receipt, recovered=False)
    else:
        _write_new_canonical(receipt_path, receipt)

    staged_run = _verify_run_root(source, allow_publication_receipt=True, run_evidence_mode=run_evidence_mode)
    if staged_run != run_evidence:
        raise Type1PublicationError("run evidence changed after publication receipt creation")
    _verify_publication_receipt(source, expected_receipt=receipt, recovered=False)
    staged_materializer = _verify_materializer_artifacts(destination_parent)
    if staged_materializer != materializer:
        raise Type1PublicationError("materializer evidence changed before atomic rename")

    try:
        os.rename(source, destination)
    except FileExistsError as exc:
        raise Type1PublicationError("destination appeared before atomic rename; refusing overwrite") from exc
    except OSError as exc:
        raise Type1PublicationError("same-volume atomic directory rename failed") from exc
    _fsync_rename_parent_directories(source.parent, destination_parent)

    moved_run = _verify_run_root(destination, allow_publication_receipt=True, run_evidence_mode=run_evidence_mode)
    if moved_run != run_evidence:
        raise Type1PublicationError("run evidence changed across atomic rename")
    moved_materializer = _verify_materializer_artifacts(destination_parent)
    if moved_materializer != materializer:
        raise Type1PublicationError("materializer evidence changed across atomic rename")
    return _verify_publication_receipt(
        destination,
        expected_receipt=receipt,
        recovered=False,
    )


def _recover_published_destination(
    destination: Path,
    *,
    source_logical_path: str,
    destination_logical_path: str,
) -> dict[str, Any]:
    run_evidence_mode = _select_run_evidence_mode(
        destination,
        destination,
        source_logical_path=source_logical_path,
        destination_logical_path=destination_logical_path,
    )
    _reject_existing_indirection(destination)
    _reject_tree_indirection(destination)
    run_evidence = _verify_run_root(destination, allow_publication_receipt=True, run_evidence_mode=run_evidence_mode)
    materializer = _verify_materializer_artifacts(destination.parent)
    _verify_run_materializer_bindings(run_evidence, materializer)
    expected = _publication_receipt(
        source_logical_path=source_logical_path,
        destination_logical_path=destination_logical_path,
        run_evidence=run_evidence,
        materializer_evidence=materializer,
    )
    return _verify_publication_receipt(destination, expected_receipt=expected, recovered=True)


def _verify_publication_receipt(
    destination: Path,
    *,
    expected_receipt: Mapping[str, Any],
    recovered: bool,
) -> dict[str, Any]:
    receipt_path = destination / PUBLICATION_RECEIPT_NAME
    actual, raw = _read_canonical_object(receipt_path, "publication receipt")
    if actual != dict(expected_receipt):
        raise Type1PublicationError("publication receipt is missing, partial, or does not bind this destination")
    return {
        "publication_status": actual["status"],
        "mode": "RECOVERED" if recovered else "PUBLISHED",
        "publication_mode": actual.get("mode", "completed"),
        "run_evidence_mode": actual.get("run_evidence_mode", _RUN_EVIDENCE_MODE_COMPLETED),
        "verdict": actual["verdict"],
        "destination": str(destination),
        "publication_receipt_path": str(receipt_path),
        "publication_receipt_sha256": _sha(raw),
        "fresh_oos": dict(actual.get("fresh_oos", _FRESH_RUN_NOT_RUN)),
    }


def _verify_run_root(root: Path, *, allow_publication_receipt: bool, run_evidence_mode: str) -> dict[str, Any]:
    if run_evidence_mode == _RUN_EVIDENCE_MODE_RECOVERED:
        return _verify_recovered_run_root(root, allow_publication_receipt=allow_publication_receipt)
    if run_evidence_mode == _RUN_EVIDENCE_MODE_COMPLETED:
        return _verify_completed_run_root(root, allow_publication_receipt=allow_publication_receipt)
    raise Type1PublicationError("unknown publication run evidence mode")


def _verify_completed_run_root(root: Path, *, allow_publication_receipt: bool) -> dict[str, Any]:
    if not root.is_dir():
        raise FileNotFoundError(root)
    _reject_tree_indirection(root)
    expected_entries = _COMPLETED_RUN_ROOT_ENTRIES_WITH_RECEIPT if allow_publication_receipt else _COMPLETED_RUN_ROOT_ENTRIES_BEFORE_RECEIPT
    try:
        actual_entries = {path.name for path in root.iterdir()}
    except OSError as exc:
        raise Type1PublicationError("run root is unreadable") from exc
    if actual_entries != expected_entries:
        required = ", ".join(sorted(expected_entries))
        raise Type1PublicationError(f"run root must contain exactly these top-level entries: {required}")

    manifest, manifest_raw = _read_canonical_object(root / "run_manifest.json", "run manifest")
    receipt, receipt_raw = _read_canonical_object(root / "receipt.json", "run receipt")
    manifest_sha = _sha(manifest_raw)
    receipt_sha = _sha(receipt_raw)
    if receipt != {
        "manifest_sha256": manifest_sha,
        "execution_status": "COMPLETE",
        "verdict": "NO_GO",
        "fresh_oos": _FRESH_RUN_NOT_RUN,
    }:
        raise Type1PublicationError("run receipt is not canonical COMPLETE/NO_GO evidence")
    _validate_run_manifest(manifest, manifest_sha)
    artifact_hashes = _verify_members(root, manifest)
    return {
        "run_evidence_mode": _RUN_EVIDENCE_MODE_COMPLETED,
        "run_manifest_sha256": manifest_sha,
        "run_receipt_sha256": receipt_sha,
        "artifact_sha256": artifact_hashes,
    }


def _verify_recovered_run_root(root: Path, *, allow_publication_receipt: bool) -> dict[str, Any]:
    if not root.is_dir():
        raise FileNotFoundError(root)
    _reject_tree_indirection(root)
    expected_entries = _RECOVERED_RUN_ROOT_ENTRIES_WITH_RECEIPT if allow_publication_receipt else _RECOVERED_RUN_ROOT_ENTRIES_BEFORE_RECEIPT
    try:
        actual_entries = {path.name for path in root.iterdir()}
    except OSError as exc:
        raise Type1PublicationError("run root is unreadable") from exc
    if actual_entries != expected_entries:
        required = ", ".join(sorted(expected_entries))
        raise Type1PublicationError(f"recovered run root must contain exactly these top-level entries: {required}")

    block_receipt, block_receipt_raw = _read_canonical_object(root / "receipt.json", "original BLOCK receipt")
    if block_receipt != _ORIGINAL_BLOCK_RECEIPT:
        raise Type1PublicationError("original BLOCK receipt/reason is not the immutable Decimal-mask control failure")
    blocked_receipt_sha = _sha(block_receipt_raw)
    recovery_manifest, recovery_manifest_raw = _read_canonical_object(root / "recovery_manifest.json", "recovery manifest")
    recovery_receipt, recovery_receipt_raw = _read_canonical_object(root / "recovery_receipt.json", "recovery receipt")
    recovery_manifest_sha = _sha(recovery_manifest_raw)
    recovery_receipt_sha = _sha(recovery_receipt_raw)
    source_hashes, identities, authority_custody_binding = _validate_recovery_manifest(recovery_manifest, recovery_manifest_sha, blocked_receipt_sha)
    member_artifact_sha256 = _verify_recovered_members(root, recovery_manifest)
    _validate_recovery_receipt(
        recovery_receipt,
        recovery_receipt_sha,
        recovery_manifest_sha=recovery_manifest_sha,
        blocked_receipt_sha=blocked_receipt_sha,
        source_hashes=source_hashes,
        member_artifact_sha256=member_artifact_sha256,
    )
    return {
        "run_evidence_mode": _RUN_EVIDENCE_MODE_RECOVERED,
        "blocked_receipt_sha256": blocked_receipt_sha,
        "recovery_manifest_sha256": recovery_manifest_sha,
        "recovery_receipt_sha256": recovery_receipt_sha,
        "original_block_reason": _ORIGINAL_BLOCK_REASON,
        "preserved_block_receipt": True,
        "retraining_performed": False,
        "fresh_oos": dict(_FRESH_NO_READ),
        "artifact_sha256": dict(member_artifact_sha256),
        "source_hashes": dict(source_hashes),
        "authority_custody_binding": dict(authority_custody_binding),
        "identities": dict(identities),
    }


def _validate_run_manifest(manifest: Mapping[str, Any], manifest_sha: str) -> None:
    identities = manifest.get("identities")
    controls = manifest.get("controls")
    if not isinstance(identities, Mapping):
        raise Type1PublicationError("run manifest does not bind the replacement identity")
    if any(identities.get(key) != value for key, value in _REPLACEMENT_IDENTITY.items()):
        raise Type1PublicationError("run manifest does not bind the exact v5 replacement identity")
    if identities.get("production_authoritative") is False:
        raise Type1PublicationError("non-authoritative fixture run cannot be published")
    if (
        manifest.get("schema_version") != _RUN_SCHEMA_VERSION
        or manifest.get("execution_status") != "COMPLETE"
        or manifest.get("verdict") != "NO_GO"
        or manifest.get("fresh_oos") != _FRESH_RUN_NOT_RUN
        or manifest.get("false_research_locks") != FALSE_RESEARCH_LOCKS
        or manifest.get("training") != _TRAINING_CONTRACT
        or not isinstance(controls, Mapping)
        or controls.get("integrity_ok") is not True
        or sha256_canonical(manifest) != manifest_sha
    ):
        raise Type1PublicationError("run manifest violates the frozen COMPLETE/NO_GO contract")
    if any(value is not False for value in manifest["false_research_locks"].values()):
        raise Type1PublicationError("false-research locks must all remain false")


def _verify_members(root: Path, manifest: Mapping[str, Any]) -> dict[str, str]:
    members = manifest.get("members")
    if not isinstance(members, Mapping) or set(members) != {"primary", "shuffled_reward"}:
        raise Type1PublicationError("run manifest must contain exactly primary and shuffled members")
    artifact_hashes: dict[str, str] = {}
    expected_seed_dirs = {f"seed_{seed}" for seed in range(5)}
    for kind in ("primary", "shuffled_reward"):
        family = members[kind]
        family_dir = root / kind
        if not isinstance(family, Mapping) or set(family) != {str(seed) for seed in range(5)}:
            raise Type1PublicationError("run manifest member seeds are incomplete or extra")
        if not family_dir.is_dir():
            raise Type1PublicationError("required member family directory is missing")
        _reject_existing_indirection(family_dir)
        actual_seed_dirs = {path.name for path in family_dir.iterdir() if path.is_dir()}
        if actual_seed_dirs != expected_seed_dirs or any(not (family_dir / name).is_dir() for name in expected_seed_dirs):
            raise Type1PublicationError("run must contain exactly ten expected primary/shuffled seed directories")
        if {path.name for path in family_dir.iterdir()} != expected_seed_dirs:
            raise Type1PublicationError("member family directory contains non-seed artifacts")
        for seed in range(5):
            member = family[str(seed)]
            seed_dir = family_dir / f"seed_{seed}"
            if not isinstance(member, Mapping):
                raise Type1PublicationError("member receipt is missing")
            if {path.name for path in seed_dir.iterdir()} != {"final_model.zip", "normalizer.json"}:
                raise Type1PublicationError("seed directory must contain only final_model.zip and normalizer.json")
            model_path = _required_file(seed_dir / "final_model.zip", f"{kind} seed {seed} final model")
            normalizer_path = _required_file(seed_dir / "normalizer.json", f"{kind} seed {seed} normalizer")
            model_raw = _read_bytes(model_path, f"{kind} seed {seed} final model")
            normalizer_raw = _read_bytes(normalizer_path, f"{kind} seed {seed} normalizer")
            _require_canonical_json_object(normalizer_raw, f"{kind} seed {seed} normalizer")
            model_sha = _sha(model_raw)
            normalizer_sha = _sha(normalizer_raw)
            expected_artifacts = {"model_sha256": model_sha, "normalizer_sha256": normalizer_sha}
            artifacts = member.get("artifacts")
            reload_receipt = member.get("reload_receipt")
            evidence = reload_receipt.get("evidence") if isinstance(reload_receipt, Mapping) else None
            if (
                member.get("seed") != seed
                or member.get("timesteps") != TIMESTEPS_PER_SEED
                or member.get("actual_sb3_timesteps") != TIMESTEPS_PER_SEED
                or member.get("device") != "cpu"
                or member.get("artifact") != FINAL_MODEL_ONLY
                or artifacts != expected_artifacts
                or not isinstance(reload_receipt, Mapping)
                or reload_receipt.get("model_sha256") != model_sha
                or reload_receipt.get("normalizer_sha256") != normalizer_sha
                or reload_receipt.get("deterministic") is not True
                or not isinstance(evidence, Mapping)
                or evidence.get("model_sha256") != model_sha
                or evidence.get("normalizer_sha256") != normalizer_sha
                or evidence.get("model_device") != "cpu"
                or evidence.get("num_timesteps") != TIMESTEPS_PER_SEED
            ):
                raise Type1PublicationError("member final artifacts do not match member receipts")
            artifact_hashes[f"{kind}/seed_{seed}/final_model.zip"] = model_sha
            artifact_hashes[f"{kind}/seed_{seed}/normalizer.json"] = normalizer_sha
    if len(artifact_hashes) != 20:
        raise Type1PublicationError("run must bind exactly twenty final model/normalizer artifacts")
    return artifact_hashes
def _validate_recovery_manifest(
    manifest: Mapping[str, Any],
    manifest_sha: str,
    blocked_receipt_sha: str,
) -> tuple[dict[str, str], Mapping[str, Any], Mapping[str, Any]]:
    _require_exact_keys(manifest, _RECOVERY_MANIFEST_KEYS, "recovery manifest")
    if manifest_sha != _sha(canonical_json_bytes(dict(manifest))):
        raise Type1PublicationError("recovery manifest is not canonical")
    if (
        manifest["schema_version"] != RECOVERY_MANIFEST_SCHEMA
        or manifest["role"] != RECOVERY_ROLE
        or manifest["status"] != "COMPLETE"
        or manifest["recovery_status"] != "COMPLETE"
        or manifest["execution_status"] != "COMPLETE"
        or manifest["verdict"] != "NO_GO"
        or manifest["decision"] != "NO_GO"
        or manifest["recovery_mode"] != RECOVERY_MODE
        or manifest["source_commit"] != RECOVERY_SOURCE_COMMIT
        or manifest["original_run_id"] != REPLACEMENT_RUN_ID
        or manifest["reused_original_run_id"] is not True
        or manifest["fresh_oos"] != _FRESH_NO_READ
        or manifest["false_research_locks"] != FALSE_RESEARCH_LOCKS
        or manifest["training"] != _RECOVERY_TRAINING_CONTRACT
        or manifest["claims"] != _RECOVERY_CLAIMS
        or manifest["features"] != list(FEATURES)
    ):
        raise Type1PublicationError("recovery manifest violates the exact recovered runner contract")
    if any(value is not False for value in manifest["false_research_locks"].values()):
        raise Type1PublicationError("false-research locks must all remain false")

    source_hashes = _validate_recovery_source_sha256(manifest["source_sha256"], "recovery manifest source_sha256")
    identities = _validate_recovery_identities(manifest["identities"])
    if (
        manifest["materializer_sha256"] != source_hashes["materializer_manifest"]
        or identities["materializer_sha256"] != source_hashes["materializer_manifest"]
        or identities["materializer_complete_receipt_sha256"] != source_hashes["materializer_complete_receipt"]
        or identities["authority_sha256"] != source_hashes["authority"]
        or identities["amendment_sha256"] != source_hashes["amendment"]
        or identities["parent_protocol_sha256"] != source_hashes["protocol"]
        or identities["runner_source_sha256"] != source_hashes["runner"]
    ):
        raise Type1PublicationError("recovery manifest identity/source hashes are not cross-bound")

    _validate_recovery_original_block(manifest["original_block"], blocked_receipt_sha)
    _validate_recovery_protocol(manifest["protocol"], source_hashes["protocol"])
    session_pairing = _validate_recovery_session_pairing(manifest["session_pairing"])
    if session_pairing["trailing_embargo"] != identities["authority_sessions"]["trailing_embargo"]:
        raise Type1PublicationError("recovery manifest session pairing does not match authority sessions")
    custody_bindings = _validate_recovery_custody_bindings(manifest["custody_bindings"], source_hashes, blocked_receipt_sha)
    controls = manifest["controls"]
    if not isinstance(controls, Mapping) or controls.get("integrity_ok") is not True:
        raise Type1PublicationError("recovery controls integrity is not complete")
    return source_hashes, identities, custody_bindings["authority"]


def _validate_recovery_receipt(
    receipt: Mapping[str, Any],
    receipt_sha: str,
    *,
    recovery_manifest_sha: str,
    blocked_receipt_sha: str,
    source_hashes: Mapping[str, str],
    member_artifact_sha256: Mapping[str, str],
) -> None:
    if not receipt_sha:
        raise Type1PublicationError("recovery receipt hash is unavailable")
    _require_exact_keys(receipt, _RECOVERY_RECEIPT_KEYS, "recovery receipt")
    if (
        receipt["schema_version"] != RECOVERY_RECEIPT_SCHEMA
        or receipt["role"] != RECOVERY_RECEIPT_ROLE
        or receipt["status"] != "COMPLETE"
        or receipt["execution_status"] != "COMPLETE"
        or receipt["verdict"] != "NO_GO"
        or receipt["decision"] != "NO_GO"
        or receipt["run_id"] != REPLACEMENT_RUN_ID
        or receipt["recovery_manifest_sha256"] != recovery_manifest_sha
        or receipt["blocked_receipt_sha256"] != blocked_receipt_sha
        or receipt["blocked_receipt_path"] != "receipt.json"
        or receipt["blocked_reason"] != _ORIGINAL_BLOCK_REASON
        or receipt["original_block_reason"] != _ORIGINAL_BLOCK_REASON
        or receipt["original_block_preserved"] is not True
        or receipt["retraining_performed"] is not False
        or receipt["overwrite_performed"] is not False
        or receipt["move_performed"] is not False
        or receipt["delete_performed"] is not False
        or receipt["fresh_oos"] != _FRESH_NO_READ
        or receipt["source_sha256"] != dict(source_hashes)
        or receipt["materializer_sha256"] != source_hashes["materializer_manifest"]
        or receipt["outcome"] != "NO_GO_ONLY"
    ):
        raise Type1PublicationError("recovery receipt violates the exact recovered runner contract")
    receipt_artifacts = _validate_member_artifact_map(receipt["member_artifact_sha256"], "recovery receipt member_artifact_sha256")
    if receipt_artifacts != dict(member_artifact_sha256):
        raise Type1PublicationError("recovery receipt artifact hashes do not bind the recovered files")


def _verify_recovered_members(root: Path, manifest: Mapping[str, Any]) -> dict[str, str]:
    members = _require_exact_keys(manifest["members"], set(_RECOVERY_FAMILIES), "recovery manifest members")
    session_pairing = _validate_recovery_session_pairing(manifest["session_pairing"])
    expected_validation_pairs_sha = session_pairing["validation_pairs_sha256"]
    expected_normalizer_digest = session_pairing["normalizer_digest"]
    expected_seed_dirs = {f"seed_{seed}" for seed in _RECOVERY_SEEDS}
    artifact_hashes: dict[str, str] = {}
    for family in _RECOVERY_FAMILIES:
        family_dir = root / family
        if not family_dir.is_dir():
            raise Type1PublicationError("required recovered member family directory is missing")
        _reject_existing_indirection(family_dir)
        if {path.name for path in family_dir.iterdir()} != expected_seed_dirs:
            raise Type1PublicationError("recovered member family directory contains missing or extra seed artifacts")
        family_members = _require_exact_keys(members[family], {str(seed) for seed in _RECOVERY_SEEDS}, f"recovery {family} members")
        for seed in _RECOVERY_SEEDS:
            member = _require_exact_keys(
                family_members[str(seed)],
                {
                    "seed",
                    "timesteps",
                    "actual_sb3_timesteps",
                    "device",
                    "artifact",
                    "artifact_paths",
                    "artifacts",
                    "reload_receipt",
                    "validation",
                },
                f"recovery {family} seed {seed} member",
            )
            directory = f"{family}/seed_{seed}"
            seed_dir = root / family / f"seed_{seed}"
            if {path.name for path in seed_dir.iterdir()} != set(_RECOVERY_MEMBER_ARTIFACT_NAMES):
                raise Type1PublicationError("recovered seed directory must contain only final_model.zip and normalizer.json")
            model_path = _required_file(seed_dir / "final_model.zip", f"{family} seed {seed} final model")
            normalizer_path = _required_file(seed_dir / "normalizer.json", f"{family} seed {seed} normalizer")
            model_raw = _read_bytes(model_path, f"{family} seed {seed} final model")
            normalizer_raw = _read_bytes(normalizer_path, f"{family} seed {seed} normalizer")
            normalizer = _canonical_json_mapping(normalizer_raw, f"{family} seed {seed} normalizer")
            model_sha = _sha(model_raw)
            normalizer_sha = _sha(normalizer_raw)
            normalizer_digest = normalizer.get("digest")
            if not _is_sha256(normalizer_digest):
                raise Type1PublicationError("recovered normalizer digest is invalid")
            artifact_paths = _require_exact_keys(member["artifact_paths"], {"model", "normalizer"}, f"recovery {family} seed {seed} artifact_paths")
            artifacts = _require_exact_keys(member["artifacts"], {"model_sha256", "normalizer_sha256"}, f"recovery {family} seed {seed} artifacts")
            reload_receipt = _require_exact_keys(
                member["reload_receipt"],
                {"model_sha256", "normalizer_sha256", "deterministic", "evidence"},
                f"recovery {family} seed {seed} reload_receipt",
            )
            reload_evidence = _require_exact_keys(
                reload_receipt["evidence"],
                {"model_sha256", "normalizer_sha256", "normalizer_digest", "validation_pairs_sha256", "model_device", "num_timesteps"},
                f"recovery {family} seed {seed} reload evidence",
            )
            validation = member["validation"]
            if (
                member["seed"] != seed
                or member["timesteps"] != TIMESTEPS_PER_SEED
                or member["actual_sb3_timesteps"] != TIMESTEPS_PER_SEED
                or member["device"] != "cpu"
                or member["artifact"] != FINAL_MODEL_ONLY
                or _normal_relative_path(artifact_paths["model"]) != f"{directory}/final_model.zip"
                or _normal_relative_path(artifact_paths["normalizer"]) != f"{directory}/normalizer.json"
                or artifacts != {"model_sha256": model_sha, "normalizer_sha256": normalizer_sha}
                or reload_receipt["model_sha256"] != model_sha
                or reload_receipt["normalizer_sha256"] != normalizer_sha
                or reload_receipt["deterministic"] is not True
                or reload_evidence["model_sha256"] != model_sha
                or reload_evidence["normalizer_sha256"] != normalizer_sha
                or reload_evidence["normalizer_digest"] != normalizer_digest
                or reload_evidence["normalizer_digest"] != expected_normalizer_digest
                or reload_evidence["validation_pairs_sha256"] != expected_validation_pairs_sha
                or reload_evidence["model_device"] != "cpu"
                or type(reload_evidence["num_timesteps"]) is not int
                or reload_evidence["num_timesteps"] != TIMESTEPS_PER_SEED
                or not isinstance(validation, Mapping)
                or validation.get("deterministic") is not True
            ):
                raise Type1PublicationError("recovered member final artifacts do not match runner member receipts")
            artifact_hashes[f"{directory}/final_model.zip"] = model_sha
            artifact_hashes[f"{directory}/normalizer.json"] = normalizer_sha
    return _validate_member_artifact_map(artifact_hashes, "recovered member artifacts")


def _require_exact_keys(value: Any, expected: set[str] | frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(expected):
        required = ", ".join(sorted(expected))
        raise Type1PublicationError(f"{label} must contain exactly these fields: {required}")
    return value

def _parse_exact_iso_date(value: Any, label: str) -> date:
    if (
        not isinstance(value, str)
        or len(value) != 10
        or value[4] != "-"
        or value[7] != "-"
        or not (value[:4] + value[5:7] + value[8:]).isdigit()
    ):
        raise Type1PublicationError(f"{label} must be an exact ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise Type1PublicationError(f"{label} must be an exact ISO date") from exc
    if parsed.isoformat() != value:
        raise Type1PublicationError(f"{label} must be an exact ISO date")
    return parsed


def _validate_ordered_authority_dates(ordered: list[Any], label: str) -> None:
    previous: date | None = None
    seen: set[str] = set()
    for index, session in enumerate(ordered):
        parsed = _parse_exact_iso_date(session, f"{label} ordered session {index}")
        if session in seen or (previous is not None and parsed <= previous):
            raise Type1PublicationError(f"{label} ordered sessions must be unique and strictly increasing ISO dates")
        seen.add(session)
        previous = parsed


def _exact_index_pairs(value: Any, expected: list[list[int]]) -> bool:
    return (
        isinstance(value, list)
        and len(value) == len(expected)
        and all(
            isinstance(pair, list)
            and len(pair) == 2
            and all(type(item) is int for item in pair)
            for pair in value
        )
        and value == expected
    )


def _exact_index_list(value: Any, expected: list[int]) -> bool:
    return isinstance(value, list) and all(type(item) is int for item in value) and value == expected




def _validate_recovery_authority_sessions(value: Any, label: str) -> Mapping[str, Any]:
    sessions = _require_exact_keys(value, _RECOVERY_AUTHORITY_SESSION_KEYS, label)
    count = sessions["count"]
    first = sessions["first"]
    last = sessions["last"]
    ordered = sessions["ordered"]
    pairs = sessions["pairs"]
    parity = sessions["parity"]
    trailing_embargo = sessions["trailing_embargo"]
    if (
        type(count) is not int
        or type(parity) is not int
        or not isinstance(first, str)
        or not isinstance(last, str)
        or not isinstance(ordered, list)
        or not isinstance(pairs, list)
        or not isinstance(trailing_embargo, list)
        or count <= 0
        or len(ordered) != count
        or first != ordered[0]
        or last != ordered[-1]
        or parity != count % 2
    ):
        raise Type1PublicationError(f"{label} count/first/last/parity do not match ordered sessions")
    _validate_ordered_authority_dates(ordered, label)
    expected_pairs = [[index, index + 1] for index in range(0, count - parity, 2)]
    expected_trailing_embargo = [count - 1] if parity else []
    if not _exact_index_pairs(pairs, expected_pairs) or not _exact_index_list(trailing_embargo, expected_trailing_embargo):
        raise Type1PublicationError(f"{label} pairs and trailing_embargo do not match ordered session parity")
    return sessions

def _authority_sessions_from_artifact(value: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    if set(value) == {"authority", "integrity", "schema"}:
        authority = value.get("authority")
        if value.get("schema") != "kronos.type1.krx-public-authority.v2" or not isinstance(authority, Mapping):
            raise Type1PublicationError(f"{label} does not bind the frozen authority envelope")
    else:
        authority = value
    if not isinstance(authority, Mapping) or authority.get("authority_id") != REPLACEMENT_AUTHORITY_ID:
        raise Type1PublicationError(f"{label} does not bind the frozen authority identity")
    return _validate_recovery_authority_sessions(authority.get("sessions"), f"{label} authority_sessions")


def _resolve_bound_authority_path(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise Type1PublicationError("recovery custody authority path is missing")
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    normalized = value.replace("\\", "/").strip("/")
    if normalized.startswith("../") or "/../" in normalized or normalized in {".", ".."}:
        raise Type1PublicationError("recovery custody authority path escapes the repository")
    return REPO_ROOT / Path(normalized)


def _read_bound_authority_sessions(binding: Any, expected_sha256: str) -> Mapping[str, Any]:
    ref = _require_exact_keys(binding, {"path", "sha256"}, "recovery custody authority")
    if ref["sha256"] != expected_sha256:
        raise Type1PublicationError("recovery custody authority sha256 does not match")
    authority, raw = _read_canonical_object(_resolve_bound_authority_path(ref["path"]), "frozen authority artifact")
    if _sha(raw) != expected_sha256:
        raise Type1PublicationError("frozen authority artifact hash does not match recovery custody")
    return _authority_sessions_from_artifact(authority, "frozen authority artifact")


def _validate_authority_sessions_match(actual: Any, expected: Any, label: str) -> Mapping[str, Any]:
    actual_sessions = _validate_recovery_authority_sessions(actual, label)
    expected_sessions = _validate_recovery_authority_sessions(expected, "frozen authority artifact authority_sessions")
    if actual_sessions != expected_sessions:
        raise Type1PublicationError(f"{label} do not match frozen authority artifact sessions")
    return actual_sessions

def _validate_recovery_identities(value: Any) -> Mapping[str, Any]:
    identities = _require_exact_keys(value, _RECOVERY_IDENTITY_KEYS, "recovery manifest identities")
    if any(identities.get(key) != expected for key, expected in _REPLACEMENT_IDENTITY.items()):
        raise Type1PublicationError("recovery manifest does not bind the exact replacement identity")
    for key in (
        "amendment_sha256",
        "authority_sha256",
        "materializer_sha256",
        "materializer_complete_receipt_sha256",
        "materializer_source_sha256",
        "preregistration_sha256",
        "parent_protocol_sha256",
        "runner_source_sha256",
    ):
        _require_sha256(identities[key], f"recovery identity {key}")
    if not isinstance(identities["source_database_identity"], Mapping):
        raise Type1PublicationError("recovery identity source database must be a bound mapping")
    _validate_recovery_authority_sessions(identities["authority_sessions"], "recovery identity authority_sessions")
    return identities


def _validate_recovery_source_sha256(value: Any, label: str) -> dict[str, str]:
    source_hashes = _require_exact_keys(value, _RECOVERY_SOURCE_SHA256_KEYS, label)
    return {name: _require_sha256(source_hashes[name], f"{label} {name}") for name in sorted(_RECOVERY_SOURCE_SHA256_KEYS)}


def _validate_recovery_original_block(value: Any, blocked_receipt_sha: str) -> None:
    block = _require_exact_keys(value, _RECOVERY_ORIGINAL_BLOCK_KEYS, "recovery manifest original_block")
    if block != {
        "path": "receipt.json",
        "receipt_sha256": blocked_receipt_sha,
        "status": "BLOCK",
        "execution_status": "BLOCK",
        "verdict": "NO_GO",
        "reason": _ORIGINAL_BLOCK_REASON,
        "fresh_oos": _FRESH_NO_READ,
        "preserved_byte_identical": True,
    }:
        raise Type1PublicationError("recovery manifest original_block does not preserve the immutable BLOCK receipt")


def _validate_recovery_protocol(value: Any, protocol_sha256: str) -> None:
    protocol = _require_exact_keys(value, {"id", "sha256"}, "recovery manifest protocol")
    if not isinstance(protocol["id"], str) or not protocol["id"] or protocol["sha256"] != protocol_sha256:
        raise Type1PublicationError("recovery manifest protocol does not bind the public protocol source hash")


def _validate_recovery_session_pairing(value: Any) -> Mapping[str, str]:
    session_pairing = _require_exact_keys(
        value,
        {"authority_bound", "trailing_embargo", "validation_pairs_sha256", "normalizer_digest"},
        "recovery manifest session_pairing",
    )
    if session_pairing["authority_bound"] is not True or not isinstance(session_pairing["trailing_embargo"], list):
        raise Type1PublicationError("recovery manifest session pairing is not authority-bound")
    _require_sha256(session_pairing["validation_pairs_sha256"], "recovery manifest validation_pairs_sha256")
    _require_sha256(session_pairing["normalizer_digest"], "recovery manifest normalizer_digest")
    return session_pairing


def _validate_recovery_custody_bindings(
    value: Any,
    source_hashes: Mapping[str, str],
    blocked_receipt_sha: str,
) -> Mapping[str, Any]:
    custody = _require_exact_keys(value, _RECOVERY_CUSTODY_BINDING_KEYS, "recovery manifest custody_bindings")
    expected = {
        "blocked_receipt": ("receipt.json", blocked_receipt_sha),
        "protocol": ("kronos_type1_g002_public_protocol_2026-07-23.json", source_hashes["protocol"]),
        "amendment": ("kronos_type1_g002_recovery_amendment_v4_2026-07-24.json", source_hashes["amendment"]),
        "public_rows": ("public_rows.json", source_hashes["public_rows"]),
        "dataset_manifest": ("dataset_manifest.json", source_hashes["dataset_manifest"]),
        "materializer_manifest": ("dataset_manifest.json", source_hashes["materializer_manifest"]),
        "materializer_complete_receipt": ("materializer_complete_receipt.json", source_hashes["materializer_complete_receipt"]),
        "authority": (None, source_hashes["authority"]),
        "runner": ("stom_rl/daily_type1_public_run.py", source_hashes["runner"]),
        "market": ("stom_rl/daily_type1_market.py", source_hashes["market"]),
    }
    for name, (path_suffix, expected_sha) in expected.items():
        _validate_custody_ref(custody[name], path_suffix, expected_sha, f"recovery custody {name}")
    return custody


def _validate_custody_ref(value: Any, expected_path_suffix: str | None, expected_sha256: str, label: str) -> None:
    ref = _require_exact_keys(value, {"path", "sha256"}, label)
    if ref["sha256"] != expected_sha256:
        raise Type1PublicationError(f"{label} sha256 does not match")
    if not isinstance(ref["path"], str) or not ref["path"]:
        raise Type1PublicationError(f"{label} path is missing")
    normalized = ref["path"].replace("\\", "/")
    if expected_path_suffix is not None and not normalized.endswith(expected_path_suffix):
        raise Type1PublicationError(f"{label} path does not bind {expected_path_suffix}")


def _validate_member_artifact_map(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise Type1PublicationError(f"{label} must be an artifact hash map")
    expected_paths = {
        f"{family}/seed_{seed}/{artifact}"
        for family in _RECOVERY_FAMILIES
        for seed in _RECOVERY_SEEDS
        for artifact in _RECOVERY_MEMBER_ARTIFACT_NAMES
    }
    if set(value) != expected_paths:
        raise Type1PublicationError(f"{label} must bind exactly twenty recovered member artifacts")
    return {path: _require_sha256(value[path], f"{label} {path}") for path in sorted(expected_paths)}


def _verify_run_materializer_bindings(run_evidence: Mapping[str, Any], materializer_evidence: Mapping[str, Any]) -> None:
    if run_evidence.get("run_evidence_mode") != _RUN_EVIDENCE_MODE_RECOVERED:
        return
    recovery_hashes = run_evidence.get("source_hashes")
    identities = run_evidence.get("identities")
    materializer_hashes = materializer_evidence.get("materializer_source_hashes")
    if not isinstance(recovery_hashes, Mapping) or not isinstance(identities, Mapping) or not isinstance(materializer_hashes, Mapping):
        raise Type1PublicationError("recovery source hashes do not bind materializer source evidence")
    if (
        recovery_hashes["protocol"] != materializer_hashes.get("protocol")
        or recovery_hashes["amendment"] != materializer_hashes.get("amendment")
        or recovery_hashes["authority"] != materializer_hashes.get("authority")
        or identities["materializer_source_sha256"] != materializer_hashes.get("materializer")
        or identities["materializer_source_sha256"] != materializer_evidence["materializer_source_sha256"]
        or recovery_hashes["public_rows"] != materializer_evidence["public_rows_sha256"]
        or recovery_hashes["dataset_manifest"] != materializer_evidence["dataset_manifest_sha256"]
        or recovery_hashes["materializer_manifest"] != materializer_evidence["dataset_manifest_sha256"]
        or recovery_hashes["materializer_complete_receipt"] != materializer_evidence["materializer_complete_receipt_sha256"]
    ):
        raise Type1PublicationError("recovery source hashes do not match the materializer evidence")
    frozen_sessions = _read_bound_authority_sessions(run_evidence.get("authority_custody_binding"), recovery_hashes["authority"])
    _validate_authority_sessions_match(identities.get("authority_sessions"), frozen_sessions, "recovery identity authority_sessions")


def _materializer_receipt_hashes(materializer_evidence: Mapping[str, Any]) -> dict[str, str]:
    return {
        "public_rows_sha256": str(materializer_evidence["public_rows_sha256"]),
        "dataset_manifest_sha256": str(materializer_evidence["dataset_manifest_sha256"]),
        "materializer_complete_receipt_sha256": str(materializer_evidence["materializer_complete_receipt_sha256"]),
    }



def _require_sha256(value: Any, label: str) -> str:
    if not _is_sha256(value):
        raise Type1PublicationError(f"{label} is not a sha256 hex digest")
    return str(value)


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _normal_relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise Type1PublicationError("artifact path is missing")
    normalized = value.replace("\\", "/").strip("/")
    if normalized.startswith("../") or "/../" in normalized or normalized in {".", ".."}:
        raise Type1PublicationError("artifact path escapes the recovered run root")
    return normalized


def _canonical_json_mapping(raw: bytes, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Type1PublicationError(f"{label} is not canonical JSON") from exc
    if not isinstance(value, Mapping) or canonical_json_bytes(value) != raw:
        raise Type1PublicationError(f"{label} is not canonical JSON")
    return value



def _verify_materializer_artifacts(parent: Path) -> dict[str, Any]:
    _reject_existing_indirection(parent)
    rows_path = _required_file(parent / "public_rows.json", "public rows")
    manifest_path = _required_file(parent / "dataset_manifest.json", "dataset manifest")
    receipt_path = _required_file(parent / "materializer_complete_receipt.json", "materializer receipt")
    identities = [(path.stat().st_dev, path.stat().st_ino) for path in (rows_path, manifest_path, receipt_path)]
    if len(set(identities)) != 3:
        raise Type1PublicationError("materializer artifacts must remain physically distinct files")
    rows_raw = _read_bytes(rows_path, "public rows", maximum=_PUBLIC_ROWS_MAX_BYTES)
    manifest, manifest_raw = _read_canonical_object(manifest_path, "dataset manifest")
    receipt, receipt_raw = _read_canonical_object(receipt_path, "materializer receipt")
    try:
        rows = json.loads(rows_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Type1PublicationError("public rows are not canonical JSON") from exc
    if not isinstance(rows, list) or canonical_json_bytes(rows) != rows_raw:
        raise Type1PublicationError("public rows are not canonical JSON")
    try:
        _validate_complete_receipt(receipt, manifest, manifest_raw, rows_raw, _MATERIALIZER_ROLES)
    except ValueError as exc:
        raise Type1PublicationError("materializer completion receipt does not bind the canonical dataset") from exc
    rows_sha = _sha(rows_raw)
    manifest_sha = _sha(manifest_raw)
    receipt_sha = _sha(receipt_raw)
    source_hashes = manifest.get("source_hashes")
    materializer_source_sha = manifest.get("materializer_source_sha256")
    if (
        manifest.get("dataset_id") != DATASET_ID
        or manifest.get("fresh_oos") != _FRESH_MATERIALIZER_NOT_RUN
        or receipt.get("fresh_oos") != _FRESH_MATERIALIZER_NOT_RUN
        or manifest.get("output_sha256") != rows_sha
        or not isinstance(source_hashes, Mapping)
        or not _is_sha256(materializer_source_sha)
        or source_hashes.get("materializer") != materializer_source_sha
    ):
        raise Type1PublicationError("materializer does not preserve Fresh OOS NOT_RUN/no-read and source hashes")
    required_source_hashes = {"protocol", "amendment", "authority", "materializer"}
    if not required_source_hashes <= set(source_hashes) or any(not _is_sha256(source_hashes.get(name)) for name in required_source_hashes):
        raise Type1PublicationError("materializer source hashes are incomplete")
    return {
        "public_rows_sha256": rows_sha,
        "dataset_manifest_sha256": manifest_sha,
        "materializer_complete_receipt_sha256": receipt_sha,
        "materializer_output_sha256": rows_sha,
        "materializer_source_sha256": str(materializer_source_sha),
        "materializer_source_hashes": {str(key): str(value) for key, value in source_hashes.items() if isinstance(value, str)},
    }


def _publication_receipt(
    *,
    source_logical_path: str,
    destination_logical_path: str,
    run_evidence: Mapping[str, Any],
    materializer_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    publisher_source_sha = _sha_file(Path(__file__))
    move_contract = {
        "operation": "same_volume_atomic_directory_rename",
        "copy_performed": False,
        "overwrite_performed": False,
        "delete_performed": False,
    }
    materializer_hashes = _materializer_receipt_hashes(materializer_evidence)
    if run_evidence.get("run_evidence_mode") != _RUN_EVIDENCE_MODE_RECOVERED:
        return {
            "schema_version": _COMPLETED_PUBLICATION_SCHEMA_VERSION,
            "role": PUBLICATION_ROLE,
            "status": "COMPLETE",
            "verdict": "NO_GO",
            "identity": dict(_REPLACEMENT_IDENTITY),
            "source_logical_path": source_logical_path,
            "destination_logical_path": destination_logical_path,
            "move_contract": move_contract,
            "run_manifest_sha256": run_evidence["run_manifest_sha256"],
            "run_receipt_sha256": run_evidence["run_receipt_sha256"],
            "member_artifact_sha256": dict(run_evidence["artifact_sha256"]),
            "materializer_sha256": materializer_hashes,
            "publisher_source_sha256": publisher_source_sha,
            "fresh_oos": {
                "run": dict(_FRESH_RUN_NOT_RUN),
                "materializer": dict(_FRESH_MATERIALIZER_NOT_RUN),
                "read_performed": False,
            },
        }

    source_hashes = dict(run_evidence["source_hashes"])
    disclosure = {
        "recovery_manifest_sha256": run_evidence["recovery_manifest_sha256"],
        "blocked_receipt_sha256": run_evidence["blocked_receipt_sha256"],
        "members": dict(run_evidence["artifact_sha256"]),
    }
    if set(disclosure) != _RECOVERY_PUBLICATION_DISCLOSURE_KEYS:
        raise Type1PublicationError("recovered publication disclosure schema is not exact")
    return {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "role": PUBLICATION_ROLE,
        "status": "COMPLETE",
        "verdict": "NO_GO",
        "mode": "recovered",
        "disclosure": disclosure,
        "run_evidence_mode": _RUN_EVIDENCE_MODE_RECOVERED,
        "identity": dict(run_evidence["identities"]),
        "source_logical_path": source_logical_path,
        "destination_logical_path": destination_logical_path,
        "move_contract": move_contract,
        "recovery_receipt_sha256": run_evidence["recovery_receipt_sha256"],
        "original_block_reason": run_evidence["original_block_reason"],
        "preserved_block_receipt": True,
        "retraining_performed": False,
        "fresh_oos": dict(_FRESH_NO_READ),
        "false_research_locks": dict(FALSE_RESEARCH_LOCKS),
        "materializer_sha256": materializer_hashes,
        "materializer_public_rows_sha256": materializer_hashes["public_rows_sha256"],
        "materializer_source_sha256": materializer_evidence["materializer_source_sha256"],
        "materializer_source_hashes": dict(materializer_evidence["materializer_source_hashes"]),
        "source_hashes": {
            "publisher_source": publisher_source_sha,
            **source_hashes,
        },
        "publisher_source_sha256": publisher_source_sha,
    }


def _required_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise Type1PublicationError(f"required artifact is missing: {label}")
    _reject_existing_indirection(path)
    return path


def _read_canonical_object(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    raw = _read_bytes(_required_file(path, label), label)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Type1PublicationError(f"{label} is not canonical JSON") from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise Type1PublicationError(f"{label} is not canonical JSON")
    return value, raw


def _require_canonical_json_object(raw: bytes, label: str) -> None:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Type1PublicationError(f"{label} is not canonical JSON") from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise Type1PublicationError(f"{label} is not canonical JSON")


def _read_bytes(path: Path, label: str, *, maximum: int = 256 * 1024 * 1024) -> bytes:
    _reject_existing_indirection(path)
    try:
        size = path.stat().st_size
        if size < 0 or size > maximum:
            raise Type1PublicationError(f"required artifact is oversized: {label}")
        raw = path.read_bytes()
    except OSError as exc:
        raise Type1PublicationError(f"required artifact is unreadable: {label}") from exc
    if len(raw) != size:
        raise Type1PublicationError(f"required artifact changed while read: {label}")
    return raw


def _write_new_canonical(path: Path, value: Mapping[str, Any]) -> None:
    raw = canonical_json_bytes(value)
    _reject_absent_destination_indirection(path)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o644)
    except FileExistsError as exc:
        raise Type1PublicationError("publication receipt already exists; refusing overwrite") from exc
    except OSError as exc:
        raise Type1PublicationError("publication receipt cannot be created") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory_if_supported(path.parent)
    except Exception as exc:
        raise Type1PublicationError("indeterminate publication receipt create; retry recovery is required") from exc

def _fsync_rename_parent_directories(source_parent: Path, destination_parent: Path) -> None:
    seen: set[Path] = set()
    for parent in (source_parent, destination_parent):
        key = parent.absolute()
        if key in seen:
            continue
        seen.add(key)
        _fsync_directory_if_supported(parent)


def _fsync_directory_if_supported(path: Path) -> None:
    if not path.is_dir():
        raise Type1PublicationError("publication directory is missing")
    _reject_existing_indirection(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_DIRECTORY", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if _is_unsupported_directory_fsync(exc):
            return
        raise Type1PublicationError("publication directory cannot be opened for fsync") from exc
    try:
        try:
            os.fsync(fd)
        except OSError as exc:
            if _is_unsupported_directory_fsync(exc):
                return
            raise Type1PublicationError("publication directory fsync failed") from exc
    finally:
        os.close(fd)


def _is_unsupported_directory_fsync(exc: OSError) -> bool:
    unsupported = {errno.EINVAL, errno.EBADF, errno.EACCES, errno.EPERM}
    for name in ("ENOTSUP", "EOPNOTSUPP"):
        value = getattr(errno, name, None)
        if value is not None:
            unsupported.add(value)
    return exc.errno in unsupported


def _require_same_volume(source: Path, destination_parent: Path) -> None:
    try:
        source_dev = source.stat().st_dev
        parent_dev = destination_parent.stat().st_dev
    except OSError as exc:
        raise Type1PublicationError("cannot prove source and destination are on the same volume") from exc
    if source_dev != parent_dev:
        raise Type1PublicationError("source and destination parent are not on the same volume")


def _exists_for_identity(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False


def _reject_tree_indirection(root: Path) -> None:
    _reject_existing_indirection(root)
    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        _reject_existing_indirection(current_path)
        for name in tuple(dirnames):
            _reject_existing_indirection(current_path / name)
        for name in filenames:
            _reject_existing_indirection(current_path / name)


def _reject_absent_destination_indirection(path: Path) -> None:
    if _exists_for_identity(path):
        _reject_existing_indirection(path)
        return
    for candidate in path.absolute().parents:
        if _exists_for_identity(candidate):
            _reject_existing_indirection(candidate)


def _reject_existing_indirection(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise
    attrs = getattr(info, "st_file_attributes", 0)
    if stat.S_ISLNK(info.st_mode) or bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
        raise Type1PublicationError("symlink or reparse path is not permitted")
    for parent in path.absolute().parents:
        if _exists_for_identity(parent):
            try:
                parent_info = parent.lstat()
            except FileNotFoundError:
                continue
            parent_attrs = getattr(parent_info, "st_file_attributes", 0)
            if stat.S_ISLNK(parent_info.st_mode) or bool(parent_attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                raise Type1PublicationError("symlink or reparse path is not permitted")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Publish the recovered Type 1 public run into the exact V6 discovery root.")


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    try:
        result = publish_type1_run()
    except Exception as exc:
        print(json.dumps({
            "publication_status": "BLOCK",
            "verdict": "NO_GO",
            "fresh_oos": dict(_FRESH_NO_READ),
            "error": str(exc),
        }, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
