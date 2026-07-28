"""Sealed test-custody boundary for preregistered daily research datasets.

This module intentionally has no facility to load, list, or report sealed test rows.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

SCHEMA_VERSION = "kronos_v8_daily_h1_custody.v1"
PUBLIC_FILENAME = "train_validation.csv"
MANIFEST_FILENAME = "train_validation_manifest.json"
LEGACY_COMBINED_FILENAME = "dataset.csv"
SPLIT_BOUNDARIES = {
    "train_end": 20231231,
    "validation_start": 20240101,
    "validation_end": 20250630,
    "test_start": 20250701,
    "test_end": 20260612,
}
H1_FIELDS = (
    "symbol", "table", "session_yyyymmdd", "split",
    "ret_1d_prev", "ret_5d_prev", "ret_20d_prev", "vol_z_20",
    "foreign_ratio_prev", "foreign_ratio_delta_5", "inst_netbuy_norm_5",
    "entry_close_1520", "future_return_h1_1520_proxy", "label_reason_h1",
)


class CustodyError(ValueError):
    """Raised when a custody invariant is violated."""


class SealedTestSink(Protocol):
    def write(self, data: bytes) -> Any: ...
    def close(self) -> Any: ...


@dataclass(frozen=True)
class VerifiedEligibleGateReceipt:
    """Capability issued only after receipt validation by the independent gate."""

    commitment: str
    eligible: bool = True
    verified: bool = True


def _row_bytes(row: Mapping[str, Any]) -> bytes:
    buffer = __import__("io").StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=H1_FIELDS, lineterminator="\n", extrasaction="raise")
    writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in H1_FIELDS})
    return buffer.getvalue().encode("utf-8")


def _key(row: Mapping[str, Any]) -> tuple[str, str, int]:
    try:
        key = (str(row["symbol"]), str(row["table"]), int(row["session_yyyymmdd"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise CustodyError("rows require symbol, table, and integer session_yyyymmdd") from exc
    if not key[0] or not key[1]:
        raise CustodyError("row symbol and table must be non-empty")
    return key


def _expected_split(session: int) -> str:
    if session <= SPLIT_BOUNDARIES["train_end"]:
        return "train"
    if SPLIT_BOUNDARIES["validation_start"] <= session <= SPLIT_BOUNDARIES["validation_end"]:
        return "val"
    if SPLIT_BOUNDARIES["test_start"] <= session <= SPLIT_BOUNDARIES["test_end"]:
        return "test"
    raise CustodyError("row session is outside the preregistered split boundaries")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_partitioned_dataset(
    rows: Iterable[Mapping[str, Any]], *, public_root: Path | str,
    sealed_test_sink: SealedTestSink, source_db_sha256: str,
    source_fivemin_db_sha256: str, custody_uid: str, prereg_id: str,
    schema_version: str = SCHEMA_VERSION,
) -> dict[str, Any]:
    """Serialize each row directly to its permitted partition, never a combined file."""
    if schema_version != SCHEMA_VERSION:
        raise CustodyError("unexpected custody schema version")
    source_hashes = (source_db_sha256, source_fivemin_db_sha256)
    if not custody_uid or not prereg_id or any(len(value) != 64 for value in source_hashes):
        raise CustodyError("custody UID, prereg ID, and both source DB SHA-256 commitments are required")
    try:
        for value in source_hashes:
            int(value, 16)
    except ValueError as exc:
        raise CustodyError("source DB SHA-256 commitments must be hexadecimal") from exc
    root = Path(public_root)
    root.mkdir(parents=True, exist_ok=True)
    public_path = root / PUBLIC_FILENAME
    manifest_path = root / MANIFEST_FILENAME
    temporary = root / (PUBLIC_FILENAME + ".tmp")
    if public_path.exists() or manifest_path.exists() or temporary.exists():
        raise CustodyError("refusing to overwrite an existing public custody artifact")

    public_digest = hashlib.sha256()
    test_digest = hashlib.sha256()
    membership_digest = hashlib.sha256()
    public_length = test_length = 0
    seen: set[tuple[str, str, int]] = set()
    try:
        with temporary.open("xb") as public_handle:
            header = (",".join(H1_FIELDS) + "\n").encode("utf-8")
            public_handle.write(header)
            public_digest.update(header)
            public_length += len(header)
            sealed_test_sink.write(header)
            test_digest.update(header)
            test_length += len(header)
            for row in rows:
                key = _key(row)
                if key in seen:
                    raise CustodyError("duplicate row key")
                seen.add(key)
                split = str(row.get("split", ""))
                if split == "embargo_dropped":
                    continue
                if split != _expected_split(key[2]):
                    raise CustodyError("row split does not match preregistered boundary")
                encoded = _row_bytes(row)
                if split in ("train", "val"):
                    public_handle.write(encoded)
                    public_digest.update(encoded)
                    public_length += len(encoded)
                elif split == "test":
                    sealed_test_sink.write(encoded)
                    test_digest.update(encoded)
                    test_length += len(encoded)
                    membership_digest.update(("\x1f".join((key[0], key[1], str(key[2]))) + "\n").encode("utf-8"))
                else:
                    raise CustodyError("unknown custody split")
        sealed_test_sink.close()
        os.replace(temporary, public_path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "custody_uid": custody_uid,
        "prereg_id": prereg_id,
        "source_db_sha256": source_db_sha256,
        "source_fivemin_db_sha256": source_fivemin_db_sha256,
        "csv_schema": list(H1_FIELDS),
        "public_artifact": {
            "filename": PUBLIC_FILENAME,
            "sha256": public_digest.hexdigest(),
            "byte_length": public_length,
        },
        "allowed_public_splits": ["train", "val"],
        "split_boundaries": dict(SPLIT_BOUNDARIES),
        "sealed_test_commitment": {
            "sha256": test_digest.hexdigest(),
            "byte_length": test_length,
            "row_key_membership_sha256": membership_digest.hexdigest(),
        },
    }
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"manifest": manifest, "manifest_path": manifest_path, "public_path": public_path}


def _reject_reparse(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise CustodyError("custody path is inaccessible") from exc
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        raise CustodyError("symlink or reparse path is forbidden")


def _contained_regular_path(root: Path, path: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise CustodyError("path escapes public root") from exc
    current = root
    _reject_reparse(current)
    for part in relative.parts:
        current = current / part
        _reject_reparse(current)
    resolved = path.resolve(strict=True)
    if resolved.parent != resolved_root or not stat.S_ISREG(resolved.stat().st_mode):
        raise CustodyError("public artifact must be a direct regular file in public root")
    return resolved


def load_train_validation(manifest_path: Path | str, public_root: Path | str) -> list[dict[str, str]]:
    """Load only verified train/validation rows from the fixed public artifact."""
    root = Path(public_root)
    legacy = root / LEGACY_COMBINED_FILENAME
    if legacy.exists() or legacy.is_symlink():
        raise CustodyError("legacy combined dataset is forbidden")
    manifest_candidate = Path(manifest_path)
    if manifest_candidate.name != MANIFEST_FILENAME:
        raise CustodyError("manifest filename is not the fixed custody filename")
    manifest_file = _contained_regular_path(root, manifest_candidate)
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CustodyError("invalid public custody manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise CustodyError("unsupported custody manifest schema")
    if manifest.get("csv_schema") != list(H1_FIELDS):
        raise CustodyError("manifest CSV schema drifted")
    if manifest.get("allowed_public_splits") != ["train", "val"] or manifest.get("split_boundaries") != SPLIT_BOUNDARIES:
        raise CustodyError("manifest split contract drifted")
    artifact = manifest.get("public_artifact")
    if not isinstance(artifact, dict) or artifact.get("filename") != PUBLIC_FILENAME:
        raise CustodyError("manifest public artifact contract drifted")
    public_file = _contained_regular_path(root, root / PUBLIC_FILENAME)
    if public_file.stat().st_size != artifact.get("byte_length") or _sha256_file(public_file) != artifact.get("sha256"):
        raise CustodyError("public artifact integrity check failed")
    with public_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != H1_FIELDS:
            raise CustodyError("public CSV schema drifted")
        rows = list(reader)
    seen: set[tuple[str, str, int]] = set()
    for row in rows:
        key = _key(row)
        if key in seen:
            raise CustodyError("duplicate public row key")
        seen.add(key)
        if row.get("split") not in ("train", "val") or row["split"] != _expected_split(key[2]):
            raise CustodyError("public row violates split boundaries")
    return rows


class CustodyAccessLedger:
    """Append-only, single-use test-access ledger; it contains commitments only."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS custody_access (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                custody_uid TEXT NOT NULL UNIQUE,
                test_sha256 TEXT NOT NULL UNIQUE,
                gate_receipt_commitment TEXT NOT NULL UNIQUE,
                event TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE
            )""")

    def _connect(self) -> sqlite3.Connection:
        for attempt in range(20):
            conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
            try:
                conn.execute("PRAGMA busy_timeout=30000")
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=FULL")
                return conn
            except sqlite3.OperationalError as exc:
                conn.close()
                if "locked" not in str(exc).lower() or attempt == 19:
                    raise CustodyError("custody ledger is unavailable") from exc
                time.sleep(0.05)
        raise CustodyError("custody ledger is unavailable")

    def consume_first_access(self, custody_uid: str, test_sha256: str, gate_receipt_commitment: str) -> str:
        if not custody_uid or len(test_sha256) != 64 or len(gate_receipt_commitment) != 64:
            raise CustodyError("custody UID, test SHA-256, and gate receipt commitment are required")
        try:
            int(test_sha256, 16)
            int(gate_receipt_commitment, 16)
        except ValueError as exc:
            raise CustodyError("test and gate receipt commitments must be hexadecimal") from exc
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                prior = conn.execute("SELECT event_hash FROM custody_access ORDER BY sequence DESC LIMIT 1").fetchone()
                previous_hash = prior[0] if prior else "0" * 64
                body = {"custody_uid": custody_uid, "event": "FIRST_ACCESS", "gate_receipt_commitment": gate_receipt_commitment,
                        "previous_hash": previous_hash, "test_sha256": test_sha256}
                event_hash = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
                conn.execute("INSERT INTO custody_access (custody_uid, test_sha256, gate_receipt_commitment, event, previous_hash, event_hash) VALUES (?, ?, ?, 'FIRST_ACCESS', ?, ?)",
                             (custody_uid, test_sha256, gate_receipt_commitment, previous_hash, event_hash))
                conn.execute("COMMIT")
                return event_hash
            except sqlite3.IntegrityError as exc:
                conn.execute("ROLLBACK")
                raise CustodyError("sealed test access has already been consumed") from exc
            except Exception:
                conn.execute("ROLLBACK")
                raise


def open_test_once(*, ledger: CustodyAccessLedger, custody_uid: str, test_sha256: str,
                   receipt: VerifiedEligibleGateReceipt, vault: Any) -> bytes:
    """Burn access before invoking a vault reader; failed reads remain consumed."""
    if not isinstance(receipt, VerifiedEligibleGateReceipt) or not receipt.verified or not receipt.eligible:
        raise CustodyError("an already verified eligible gate receipt is required")
    ledger.consume_first_access(custody_uid, test_sha256, receipt.commitment)
    data = vault.read() if hasattr(vault, "read") else vault()
    if not isinstance(data, bytes) or hashlib.sha256(data).hexdigest() != test_sha256:
        raise CustodyError("sealed test vault integrity check failed after access burn")
    return data
