"""Fail-closed publication move for the completed Type 1 public run.

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
from pathlib import Path
from typing import Any, Mapping, Sequence

from stom_rl.daily_type1_contract import canonical_json_bytes, sha256_canonical
from stom_rl.daily_type1_public_data import (
    DATASET_ID,
    RECEIPT_ROLE as MATERIALIZER_RECEIPT_ROLE,
    _validate_complete_receipt,
    verify_public_materialization,
)
from stom_rl.daily_type1_public_run import (
    FALSE_RESEARCH_LOCKS,
    FINAL_MODEL_ONLY,
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
PUBLICATION_SCHEMA_VERSION = "kronos.type1.publication-receipt.v1"
PUBLICATION_ROLE = "TYPE1_PUBLICATION_RECEIPT"
_RUN_SCHEMA_VERSION = "kronos_type1_g002_public_run.v1"
_FRESH_RUN_NOT_RUN = {"state": "NOT_RUN", "metrics": None}
_FRESH_MATERIALIZER_NOT_RUN = {"state": "NOT_RUN", "read_performed": False}
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
_RUN_ROOT_ENTRIES_BEFORE_RECEIPT = frozenset({"receipt.json", "run_manifest.json", "primary", "shuffled_reward"})
_RUN_ROOT_ENTRIES_WITH_RECEIPT = _RUN_ROOT_ENTRIES_BEFORE_RECEIPT | frozenset({PUBLICATION_RECEIPT_NAME})


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
    if source_logical_path != SOURCE_LOGICAL_PATH or destination_logical_path != DESTINATION_LOGICAL_PATH:
        raise Type1PublicationError("publication receipt logical paths do not match the authorized contract")

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
    run_evidence = _verify_run_root(source, allow_publication_receipt=has_staged_receipt)

    # The immutable materialization verifier is intentionally called before the
    # move, while the destination parent still contains exactly the three
    # materializer artifacts.  After publication the run directory is an allowed
    # fourth child, so later checks verify the named artifacts directly.
    try:
        verify_public_materialization(destination_parent)
    except Exception as exc:
        raise Type1PublicationError("destination parent is not the canonical three-artifact materialization") from exc
    materializer = _verify_materializer_artifacts(destination_parent)

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

    staged_run = _verify_run_root(source, allow_publication_receipt=True)
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

    moved_run = _verify_run_root(destination, allow_publication_receipt=True)
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
    _reject_existing_indirection(destination)
    _reject_tree_indirection(destination)
    run_evidence = _verify_run_root(destination, allow_publication_receipt=True)
    materializer = _verify_materializer_artifacts(destination.parent)
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
        "publication_status": "COMPLETE",
        "mode": "RECOVERED" if recovered else "PUBLISHED",
        "verdict": "NO_GO",
        "destination": str(destination),
        "publication_receipt_path": str(receipt_path),
        "publication_receipt_sha256": _sha(raw),
        "fresh_oos": dict(_FRESH_RUN_NOT_RUN),
    }


def _verify_run_root(root: Path, *, allow_publication_receipt: bool) -> dict[str, Any]:
    if not root.is_dir():
        raise FileNotFoundError(root)
    _reject_tree_indirection(root)
    expected_entries = _RUN_ROOT_ENTRIES_WITH_RECEIPT if allow_publication_receipt else _RUN_ROOT_ENTRIES_BEFORE_RECEIPT
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
        "run_manifest_sha256": manifest_sha,
        "run_receipt_sha256": receipt_sha,
        "artifact_sha256": artifact_hashes,
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


def _verify_materializer_artifacts(parent: Path) -> dict[str, str]:
    _reject_existing_indirection(parent)
    rows_path = _required_file(parent / "public_rows.json", "public rows")
    manifest_path = _required_file(parent / "dataset_manifest.json", "dataset manifest")
    receipt_path = _required_file(parent / "materializer_complete_receipt.json", "materializer receipt")
    identities = [(path.stat().st_dev, path.stat().st_ino) for path in (rows_path, manifest_path, receipt_path)]
    if len(set(identities)) != 3:
        raise Type1PublicationError("materializer artifacts must remain physically distinct files")
    rows_raw = _read_bytes(rows_path, "public rows")
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
    if manifest.get("dataset_id") != DATASET_ID or manifest.get("fresh_oos") != _FRESH_MATERIALIZER_NOT_RUN or receipt.get("fresh_oos") != _FRESH_MATERIALIZER_NOT_RUN:
        raise Type1PublicationError("materializer does not preserve Fresh OOS NOT_RUN/no-read")
    return {
        "public_rows_sha256": _sha(rows_raw),
        "dataset_manifest_sha256": _sha(manifest_raw),
        "materializer_complete_receipt_sha256": _sha(receipt_raw),
    }


def _publication_receipt(
    *,
    source_logical_path: str,
    destination_logical_path: str,
    run_evidence: Mapping[str, Any],
    materializer_evidence: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "role": PUBLICATION_ROLE,
        "status": "COMPLETE",
        "verdict": "NO_GO",
        "identity": dict(_REPLACEMENT_IDENTITY),
        "source_logical_path": source_logical_path,
        "destination_logical_path": destination_logical_path,
        "move_contract": {
            "operation": "same_volume_atomic_directory_rename",
            "copy_performed": False,
            "overwrite_performed": False,
            "delete_performed": False,
        },
        "run_manifest_sha256": run_evidence["run_manifest_sha256"],
        "run_receipt_sha256": run_evidence["run_receipt_sha256"],
        "member_artifact_sha256": dict(run_evidence["artifact_sha256"]),
        "materializer_sha256": dict(materializer_evidence),
        "publisher_source_sha256": _sha_file(Path(__file__)),
        "fresh_oos": {
            "run": dict(_FRESH_RUN_NOT_RUN),
            "materializer": dict(_FRESH_MATERIALIZER_NOT_RUN),
            "read_performed": False,
        },
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
    return argparse.ArgumentParser(description="Publish the completed Type 1 public run into the exact V6 discovery root.")


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    try:
        result = publish_type1_run()
    except Exception as exc:
        print(json.dumps({
            "publication_status": "BLOCK",
            "verdict": "NO_GO",
            "fresh_oos": dict(_FRESH_RUN_NOT_RUN),
            "error": str(exc),
        }, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
