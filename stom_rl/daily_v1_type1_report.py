"""Immutable report authority for the replacement Type1 public run.

This module deliberately has no fresh-OOS inputs.  A report is a hash-addressed
revision, not a request for the latest report in a directory.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sqlite3
import stat
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "docs" / "kronos_type1_g002_public_protocol_2026-07-23.json"
PREREG_PATH = REPO_ROOT / "docs" / "kronos_type1_closing_prereg_2026-07-23.json"
AMENDMENT_PATH = REPO_ROOT / "docs" / "kronos_type1_g002_recovery_amendment_v4_2026-07-24.json"
REPORT_ROOT = "type1_reports"
REVISION_SCHEMA = "kronos_type1_report_revision.v2"
MATERIALIZATION_SCHEMA = "kronos_type1_report_materialization.v2"
TIP_SCHEMA = "kronos_type1_committed_report_tip.v2"
BUILDER_VERSION = "kronos_type1_report_builder.v2"
REPLACEMENT_IDENTITY = {
    "authority_id": "type1-krx-authority-20260724-004",
    "dataset_id": "type1-close-20260803-005",
    "train_id": "type1-public-005",
    "train_run_id": "train_type1-public-005",
    "custody_uid": "type1-fresh-oos-20260803-005",
}
REPLACEMENT_OUTER_IDENTITY = {
    **REPLACEMENT_IDENTITY,
    "report_family": "kronos.type1.report.v1",
}
IDENTITY = {
    **REPLACEMENT_OUTER_IDENTITY,
    "domain": "kronos.type1",
    "algorithm_family": "MASKABLE_PPO",
}
POLICY = {"price_basis": "EXACT_15_20_BAR_CLOSE_PROXY", "official_close": False, "accounting": "FIXED_NOTIONAL_NON_SELF_FINANCING", "primary_cost_rate": "0.0023", "initial_nav_krw": "60000000", "slot_notional_krw": "5000000", "maximum_slots": 10, "seeds": [0, 1, 2, 3, 4], "checkpoint_selection": False, "synthetic_oracle_calibration": False}
LOCKS = {"promotion_allowed": False, "model_build_allowed": False, "paper_forward_allowed": False, "live_broker_order_allowed": False, "profitability_claim_allowed": False, "go_summary_allowed": False}
M3E_STATEMENT = "LINUCB_CONTEXTUAL_BANDIT_NO_GO_FIVE_SEEDS_23BP_FRESH_OOS_NOT_RUN_UNCHANGED"
RUNNER_MANIFEST_SCHEMA = "kronos_type1_g002_public_run.v1"
RUNNER_RECEIPT = {
    "execution_status": "COMPLETE",
    "verdict": "NO_GO",
    "fresh_oos": {"state": "NOT_RUN", "metrics": None},
}
REPORT_RESULT = {
    "run_state": "COMPLETE",
    "training_state": "COMPLETE",
    "reused_validation_state": "COMPLETE",
    "verdict": "NO_GO",
    "fresh_oos_state": "NOT_RUN",
    "fresh_oos_read_performed": False,
    "failures": [],
}
REPORT_CLAIMS = {
    "execution_outcome": "NO_GO_ONLY",
    "fresh_oos": "NOT_RUN_NO_READ",
    "m3e": M3E_STATEMENT,
    "profitability": "NOT_CLAIMED",
    "live": "NOT_CLAIMED",
}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_EVENT = re.compile(r"([0-9]{8})-([0-9a-f]{64})\.json\Z")
_OBJECT = re.compile(r"([A-Za-z0-9][A-Za-z0-9_.-]{0,80})-([0-9a-f]{64})\.html\Z")
# Names are fixed; callers cannot substitute a path for any authority artifact.
_SOURCE_LOCAL_PATHS = {
    "type1_identity": Path("type1_identity.json"),
    "public_run_seal": Path("p6_public_run_seal.json"),
    "deployment_lock": Path("deployment_lock.json"),
    "attempt_parent": Path("attempt_parent.json"),
    "authority": Path("authority.json"),
    "dataset_manifest": Path("..") / "dataset_manifest.json",
    "public_rows": Path("..") / "public_rows.json",
    "materializer_complete_receipt": Path("..") / "materializer_complete_receipt.json",
    "run_manifest": Path("run_manifest.json"),
    "run_receipt": Path("receipt.json"),
    **{f"{kind}_seed_{seed}_{artifact}": Path(kind) / f"seed_{seed}" / filename
       for kind in ("primary", "shuffled_reward") for seed in range(5)
       for artifact, filename in (("model", "final_model.zip"), ("normalizer", "normalizer.json"))},
}
_AUTHORITY_ARTIFACT_LABELS = ("type1_identity", "public_run_seal", "deployment_lock", "attempt_parent", "authority")
PARENT_ATTEMPT_IDENTITY = {
    "dataset_id": "type1-close-20260803-004",
    "train_id": "type1-public-004",
    "train_run_id": "train_type1-public-004",
}

class Type1ReportError(ValueError):
    """Raised when a Type1 immutable report authority is invalid or blocked."""

def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise Type1ReportError(f"{label} must be lowercase SHA-256")
    return value

def _is_reparse(path: Path) -> bool:
    try:
        mode = os.lstat(path).st_mode
        attrs = os.lstat(path).st_file_attributes if hasattr(os.lstat(path), "st_file_attributes") else 0
    except OSError as exc:
        raise Type1ReportError("authority path is unreadable") from exc
    return stat.S_ISLNK(mode) or bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))

def _safe_child(root: Path, relative: Path) -> Path:
    """Lexically contain a path and reject every symlink/junction component."""
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise Type1ReportError("authority path escapes fixed root")
    root = root.absolute()
    for ancestor in (root, *root.parents):
        if _is_reparse(ancestor):
            raise Type1ReportError("authority root contains a reparse point")
    candidate = root
    for part in relative.parts:
        candidate = candidate / part
        if candidate.exists() and _is_reparse(candidate):
            raise Type1ReportError("authority path contains reparse point")
    try:
        candidate.absolute().relative_to(root)
    except ValueError as exc:
        raise Type1ReportError("authority path escapes fixed root") from exc
    return candidate

def _read_bytes(path: Path, label: str, *, maximum: int = 64 * 1024 * 1024) -> bytes:
    if _is_reparse(path) or not path.is_file():
        raise Type1ReportError(f"required report source is missing: {label}")
    try:
        size = path.stat().st_size
        if size < 0 or size > maximum:
            raise Type1ReportError(f"required report source is oversized: {label}")
        with path.open("rb") as handle:
            raw = handle.read(maximum + 1)
    except OSError as exc:
        raise Type1ReportError(f"required report source is unreadable: {label}") from exc
    if len(raw) != size or len(raw) > maximum:
        raise Type1ReportError(f"required report source changed while read: {label}")
    return raw

def _read_canonical(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = _read_bytes(path, label)
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, Type1ReportError) as exc:
        raise Type1ReportError(f"{label} is invalid") from exc
    if not isinstance(value, dict) or raw != _canonical(value):
        raise Type1ReportError(f"{label} is not canonical JSON")
    return value, raw
def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(_read_bytes(path, label).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, Type1ReportError) as exc:
        raise Type1ReportError(f"{label} is invalid") from exc
    if not isinstance(value, dict):
        raise Type1ReportError(f"{label} is invalid")
    return value
def _is_authority_envelope(value: Mapping[str, Any]) -> bool:
    return set(value) == {"authority", "integrity", "schema"}

def _authority_payload(envelope: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    if not _is_authority_envelope(envelope):
        raise Type1ReportError(f"{label} must be the frozen authority envelope")
    authority = envelope.get("authority")
    sessions = authority.get("sessions") if isinstance(authority, Mapping) else None
    if (
        envelope.get("schema") != "kronos.type1.krx-public-authority.v2"
        or not isinstance(authority, Mapping)
        or authority.get("authority_id") != REPLACEMENT_IDENTITY["authority_id"]
        or authority.get("fresh_oos") != {"status": "NOT_RUN", "no_read": True}
        or not isinstance(sessions, Mapping)
        or not {"ordered", "pairs", "trailing_embargo"} <= set(sessions)
    ):
        raise Type1ReportError(f"{label} does not bind the frozen v5 authority")
    return authority

def _validate_frozen_authority_envelope(envelope: Mapping[str, Any], raw: bytes, label: str) -> None:
    try:
        from stom_rl.daily_type1_authority import canonical_json, validate_authority

        if raw != canonical_json(envelope):
            raise Type1ReportError(f"{label} is not canonical JSON")
        validate_authority(envelope)
        _authority_payload(envelope, label)
    except Type1ReportError:
        raise
    except Exception as exc:
        raise Type1ReportError(f"{label} is invalid") from exc

def _read_authority_source(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = _read_bytes(path, label)
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, Type1ReportError) as exc:
        raise Type1ReportError(f"{label} is invalid") from exc
    if not isinstance(value, dict):
        raise Type1ReportError(f"{label} is invalid")
    if _is_authority_envelope(value):
        _validate_frozen_authority_envelope(value, raw, label)
    elif raw != _canonical(value):
        raise Type1ReportError(f"{label} is not canonical JSON")
    return value, raw

def _read_frozen_authority_envelope(path: Path) -> tuple[dict[str, Any], Mapping[str, Any], bytes]:
    envelope, raw = _read_authority_source(path, "frozen authority")
    authority = _authority_payload(envelope, "frozen authority")
    return envelope, authority, raw

def _write_new(path: Path, raw: bytes) -> None:
    """Create and durably write an immutable object; accept only an exact orphan retry."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o644)
    except FileExistsError:
        if _read_bytes(path, "existing immutable catalog entry", maximum=len(raw)) != raw:
            raise Type1ReportError("immutable catalog entry already exists")
        return
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
    except Exception as exc:
        raise Type1ReportError("indeterminate immutable create; retry exact operation to recover") from exc

def _root(run_dir: str | Path, *, create: bool = False) -> Path:
    directory = Path(run_dir).absolute()
    if not directory.is_dir() or _is_reparse(directory):
        raise Type1ReportError("run directory is required")
    root = _safe_child(directory, Path(REPORT_ROOT))
    if create:
        try:
            root.mkdir(exist_ok=True); _safe_child(root, Path("events")).mkdir(exist_ok=True); _safe_child(root, Path("objects")).mkdir(exist_ok=True)
        except OSError as exc:
            raise Type1ReportError("cannot create report catalog root") from exc
    if not root.is_dir() or _is_reparse(root):
        raise Type1ReportError("report catalog root is invalid")
    for name in ("events", "objects"):
        child = _safe_child(root, Path(name))
        if not child.is_dir() or _is_reparse(child):
            raise Type1ReportError("report catalog root is invalid")
    return root

def _mutex(root: Path) -> sqlite3.Connection:
    db = _safe_child(root, Path("current_parent.sqlite3"))
    if db.exists() and _is_reparse(db):
        raise Type1ReportError("current-parent authority is invalid")
    try:
        con = sqlite3.connect(str(db), timeout=30, isolation_level=None)
        con.execute("PRAGMA journal_mode=WAL"); con.execute("PRAGMA synchronous=FULL")
        con.execute("CREATE TABLE IF NOT EXISTS current_parent (singleton INTEGER PRIMARY KEY CHECK(singleton=1), event_sha256 TEXT NOT NULL, state TEXT NOT NULL)")
        return con
    except sqlite3.Error as exc:
        raise Type1ReportError("current-parent authority is unavailable") from exc
def _identity_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    candidate = value.get("identity", value)
    if not isinstance(candidate, Mapping) or any(
        candidate.get(key) != expected for key, expected in REPLACEMENT_OUTER_IDENTITY.items()
    ):
        raise Type1ReportError("authority artifact does not bind exact replacement outer identity")
    return candidate


def _validate_authority_sources(fixed: Mapping[str, Mapping[str, Any]]) -> None:
    amendment = fixed["amendment"]
    expected_attempts = (
        ("type1-close-20260803-001", "type1-public-001", "train_type1-public-001", "INELIGIBLE_BLOCKED", None),
        ("type1-close-20260803-002", "type1-public-002", "train_type1-public-002", "INELIGIBLE_BLOCKED", None),
        ("type1-close-20260803-003", "type1-public-003", "train_type1-public-003", "NON_MATERIALIZED_INELIGIBLE", {"status": "NOT_RUN", "no_read": True}),
        ("type1-close-20260803-004", "type1-public-004", "train_type1-public-004", "MATERIALIZED_NOT_TRAINED_QUARANTINED", {"status": "NOT_RUN", "no_read": True}),
    )
    quarantined = [
        {"authority_id": "type1-krx-authority-20260723-002", "authority_sha256": "7d0ea6d76e3181da6caef232ce0c152645c290a290021e906d700667f8a059a2", "status": "QUARANTINED", "models_created": 0, "fresh_oos": {"status": "NOT_RUN", "no_read": True}},
        {"authority_id": "type1-krx-authority-20260724-003", "authority_sha256": "30e34b05fe65e31b2cbb826a48628946fa3f03dc7fc7f868ebd41ff36fcef1fe", "rows_sha256": "0af2be6cba26827f48ea00bf0caf700b1ce40e6fc1c2cfdebf1710ae39dfbd11", "status": "QUARANTINED_MATERIALIZED_NOT_TRAINED", "models_created": 0, "fresh_oos": {"status": "NOT_RUN", "no_read": True}},
    ]
    execution = amendment.get("execution_contract")
    fresh_oos = amendment.get("fresh_oos")
    preserved = amendment.get("preserved_aborted_evidence")
    if (
        amendment.get("schema_version") != "kronos.type1.g002-recovery-amendment.v4"
        or amendment.get("amendment_id") != "KRONOS-TYPE1-G002-RECOVERY-2026-07-24-004"
        or amendment.get("supersedes") != "KRONOS-TYPE1-G002-RECOVERY-2026-07-24-003"
        or amendment.get("status") != "FROZEN_BEFORE_V5_MATERIALIZATION_OR_TRAINING"
        or amendment.get("replacement_identity") != REPLACEMENT_IDENTITY
        or execution != {"proxy_time": "15:20:00", "cost_bps": 23, "fixed_notional": 60000000, "primary_seeds": 5, "shuffled_seeds": 5, "timesteps_per_seed": 200000, "outcome": "NO_GO_ONLY"}
        or fresh_oos != {"custody_uid": REPLACEMENT_IDENTITY["custody_uid"], "status": "NOT_RUN", "no_read": True, "no_price_or_oos_query_after": "2025-06-30"}
        or amendment.get("quarantined_authorities") != quarantined
        or not isinstance(preserved, list)
        or len(preserved) != len(expected_attempts)
    ):
        raise Type1ReportError("recovery amendment does not bind the frozen v5 replacement authority")
    for evidence, (dataset_id, train_id, train_run_id, status, evidence_oos) in zip(preserved, expected_attempts):
        if not isinstance(evidence, Mapping) or (
            evidence.get("dataset_id"), evidence.get("train_id"), evidence.get("train_run_id"),
            evidence.get("status"), evidence.get("models_created"), evidence.get("fresh_oos"),
        ) != (dataset_id, train_id, train_run_id, status, 0, evidence_oos):
            raise Type1ReportError("recovery amendment aborted history is invalid")
    authority_contract = amendment.get("authority_contract")
    if not isinstance(authority_contract, Mapping) or (
        authority_contract.get("authority_metadata_cutoff"),
        authority_contract.get("authority_metadata_scope"),
        authority_contract.get("per_market_capture"),
    ) != (
        "2026-07-24",
        "MDCSTAT23801 instrument-master metadata only; price, calendar, ranking, public-row, and fresh-OOS access end at 2025-06-30.",
        "Store and RFC8785-hash separate {query,response} captures for STK/KOSPI and KSQ/KOSDAQ; each row must retain matching market provenance.",
    ):
        raise Type1ReportError("recovery amendment authority metadata scope is invalid")

    protocol, preregistration = fixed["protocol"], fixed["preregistration"]
    if (protocol.get("protocol_id"), protocol.get("parent_prereg_id")) != (
        "KRONOS-TYPE1-G002-PUBLIC-2026-07-23", "KRONOS-TYPE1-CLOSING-2026-07-23",
    ):
        raise Type1ReportError("protocol ancestry is invalid")
    boundary, training = protocol.get("scientific_boundary"), protocol.get("training")
    if not isinstance(boundary, Mapping) or not isinstance(training, Mapping) or (
        boundary.get("price_basis"), boundary.get("primary_round_trip_cost_rate"),
        boundary.get("fresh_oos_state"), boundary.get("fresh_oos_read_performed"),
        training.get("seeds"), boundary.get("terminal_verdict"),
    ) != ("EXACT_15_20_BAR_CLOSE_PROXY", "0.0023", "NOT_RUN", False, [0, 1, 2, 3, 4], "NO_GO"):
        raise Type1ReportError("protocol Type1 boundary is invalid")
    m3e = preregistration.get("m3e_context")
    if preregistration.get("prereg_id") != "KRONOS-TYPE1-CLOSING-2026-07-23" or not isinstance(m3e, Mapping) or (
        m3e.get("classification"), m3e.get("verdict"), m3e.get("fresh_oos_status")
    ) != ("CONTEXTUAL_BANDIT_RESEARCH_EXPERIMENT", "NO_GO", "NOT_RUN"):
        raise Type1ReportError("preregistration M3E boundary is invalid")

    for label in ("type1_identity", "public_run_seal", "deployment_lock", "attempt_parent"):
        _identity_mapping(fixed[label])
    seal = fixed["public_run_seal"]
    fresh = seal.get("fresh_oos", seal)
    if not isinstance(fresh, Mapping) or (
        fresh.get("state", fresh.get("fresh_oos_state")), fresh.get("payload_read", fresh.get("fresh_oos_read_performed"))
    ) != ("NOT_RUN", False):
        raise Type1ReportError("P6 public run seal has unsafe fresh-OOS state")
    lock = fixed["deployment_lock"]
    if lock.get("false_research_locks", lock.get("locks")) != LOCKS:
        raise Type1ReportError("deployment lock does not preserve Type1 no-go locks")
    parent = fixed["attempt_parent"]
    prior = parent.get("parent_identity", parent.get("parent_attempt", parent.get("previous_attempt")))
    parent_fresh = parent.get("fresh_oos")
    parent_status = parent.get("parent_status", parent.get("status"))
    models_created = parent.get("models_created")
    if (
        not isinstance(prior, Mapping)
        or {key: prior.get(key) for key in PARENT_ATTEMPT_IDENTITY} != PARENT_ATTEMPT_IDENTITY
        or parent_status not in (None, "MATERIALIZED_NOT_TRAINED_QUARANTINED")
        or models_created not in (None, 0)
        or parent_fresh not in (None, {"status": "NOT_RUN", "no_read": True})
    ):
        raise Type1ReportError("attempt parent does not preserve quarantined -004 ancestry")
    authority = fixed["authority"]
    if _is_authority_envelope(authority):
        _authority_payload(authority, "authority source")
    else:
        authority_identity = _identity_mapping(authority)
        if authority.get("authority_id", authority_identity.get("authority_id")) != REPLACEMENT_OUTER_IDENTITY["authority_id"]:
            raise Type1ReportError("authority source does not bind replacement authority ID")

def _report_source_paths(directory: Path) -> dict[str, Path]:
    return {
        "amendment": _safe_child(REPO_ROOT, Path("docs") / AMENDMENT_PATH.name),
        "protocol": _safe_child(REPO_ROOT, Path("docs") / PROTOCOL_PATH.name),
        "preregistration": _safe_child(REPO_ROOT, Path("docs") / PREREG_PATH.name),
        "builder_source": _safe_child(REPO_ROOT, Path("stom_rl") / Path(__file__).name),
        **{label: _safe_child(directory, relative) for label, relative in _SOURCE_LOCAL_PATHS.items() if label not in {"dataset_manifest", "public_rows", "materializer_complete_receipt"}},
        "dataset_manifest": _safe_child(directory.parent, Path("dataset_manifest.json")),
        "public_rows": _safe_child(directory.parent, Path("public_rows.json")),
        "materializer_complete_receipt": _safe_child(directory.parent, Path("materializer_complete_receipt.json")),
    }

def report_source_sha256(run_dir: str | Path) -> dict[str, str]:
    directory = Path(run_dir).absolute()
    if not directory.is_dir() or _is_reparse(directory):
        raise Type1ReportError("run directory is required")
    paths = _report_source_paths(directory)
    fixed = {
        label: (
            _read_json(paths[label], label)
            if label in {"amendment", "protocol", "preregistration"}
            else _read_authority_source(paths[label], label)[0]
            if label == "authority"
            else _read_canonical(paths[label], label)[0]
        )
        for label in ("amendment", "protocol", "preregistration", "type1_identity", "public_run_seal", "deployment_lock", "attempt_parent", "authority")
    }
    _validate_authority_sources(fixed)
    return {label: _sha(_read_bytes(path, label)) for label, path in paths.items()}
def _verify_current_parent(root: Path, events: list[tuple[dict[str, Any], str]], state: str) -> None:
    """Read-only check of the SQLite CAS parent; reconciliation is runner-owned."""
    db = _safe_child(root, Path("current_parent.sqlite3"))
    if not db.is_file() or _is_reparse(db):
        raise Type1ReportError("current-parent authority is missing")
    expected = events[-1][1] if events else None
    expected_state = "COMMITTED" if state == "COMMITTED" else ("MATERIALIZED" if events and len(events) % 2 == 0 else ("REVISION" if events else "EMPTY"))
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row = con.execute("SELECT event_sha256,state FROM current_parent WHERE singleton=1").fetchone()
        finally:
            con.close()
    except sqlite3.Error as exc:
        raise Type1ReportError("current-parent authority is unreadable") from exc
    if row is None or row[0] != expected or row[1] != expected_state:
        raise Type1ReportError("current-parent authority mismatch")

def _read_completed_runner_manifest(root: Path, expected_manifest_sha256: Any = None) -> dict[str, Any]:
    manifest, manifest_raw = _read_canonical(_safe_child(root, Path("run_manifest.json")), "run manifest")
    receipt = _read_canonical(_safe_child(root, Path("receipt.json")), "run receipt")[0]
    manifest_sha256 = _sha(manifest_raw)
    if expected_manifest_sha256 is not None and manifest_sha256 != expected_manifest_sha256:
        raise Type1ReportError("runner manifest source hash mismatch")
    if (
        manifest.get("schema_version") != RUNNER_MANIFEST_SCHEMA
        or not isinstance(manifest.get("identities"), Mapping)
        or {key: manifest["identities"].get(key) for key in REPLACEMENT_IDENTITY} != REPLACEMENT_IDENTITY
        or manifest.get("execution_status") != "COMPLETE"
        or manifest.get("verdict") != "NO_GO"
        or manifest.get("fresh_oos") != RUNNER_RECEIPT["fresh_oos"]
        or manifest.get("false_research_locks") != LOCKS
        or receipt != {**RUNNER_RECEIPT, "manifest_sha256": manifest_sha256}
    ):
        raise Type1ReportError("runner manifest or receipt violates the frozen no-go contract")
    return manifest
def _validate_runner_evidence(run_dir: str | Path, sources: Mapping[str, Any]) -> None:
    root = Path(run_dir).absolute()
    manifest = _read_completed_runner_manifest(root, sources.get("run_manifest"))
    materializer_receipt, _ = _read_canonical(
        _safe_child(root.parent, Path("materializer_complete_receipt.json")),
        "materializer completion receipt",
    )
    dataset_manifest, dataset_manifest_bytes = _read_canonical(
        _safe_child(root.parent, Path("dataset_manifest.json")),
        "dataset manifest",
    )
    public_rows_bytes = _read_bytes(
        _safe_child(root.parent, Path("public_rows.json")),
        "public rows",
    )
    try:
        public_rows = json.loads(public_rows_bytes.decode("utf-8"))
        if not isinstance(public_rows, list) or public_rows_bytes != _canonical(public_rows):
            raise ValueError("public rows are not a canonical array")
        from stom_rl.daily_type1_public_data import RECEIPT_ROLE, _validate_complete_receipt

        _validate_complete_receipt(
            materializer_receipt,
            dataset_manifest,
            dataset_manifest_bytes,
            public_rows_bytes,
            {
                "public_rows.json": "CANONICAL_PUBLIC_ROWS",
                "dataset_manifest.json": "CANONICAL_DATASET_MANIFEST",
                "materializer_complete_receipt.json": RECEIPT_ROLE,
            },
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise Type1ReportError("materializer completion receipt does not prove the v5 dataset boundary") from exc
    if (
        materializer_receipt.get("dataset_manifest_sha256") != sources.get("dataset_manifest")
        or materializer_receipt.get("public_rows_sha256") != sources.get("public_rows")
        or materializer_receipt.get("amendment_sha256") != sources.get("amendment")
        or materializer_receipt.get("authority_sha256") != sources.get("authority")
    ):
        raise Type1ReportError("materializer completion receipt does not bind report sources")
    pretraining = manifest.get("pretraining_gate")
    if not isinstance(pretraining, Mapping) or set(pretraining) != {
        "accounting", "block_semantics", "validation_noninterference",
    }:
        raise Type1ReportError("runner pretraining evidence is missing or malformed")
    accounting = pretraining.get("accounting")
    noninterference = pretraining.get("validation_noninterference")
    if (
        not isinstance(accounting, Mapping)
        or (accounting.get("cost_bps"), accounting.get("slot_notional_krw"), accounting.get("max_slots")) != (23, 5000000, 10)
        or pretraining.get("block_semantics") != "BLOCK"
        or not isinstance(noninterference, Mapping)
        or noninterference.get("unchanged") is not True
        or noninterference.get("mutated_surfaces") != ["features", "gross_return", "entry_available"]
        or any(_SHA.fullmatch(str(noninterference.get(key, ""))) is None for key in ("train_only_normalizer_digest", "train_pairs_sha256"))
    ):
        raise Type1ReportError("runner pretraining evidence violates accounting or validation isolation")
    training = manifest.get("training")
    if not isinstance(training, Mapping) or training != {
        "seeds": [0, 1, 2, 3, 4],
        "timesteps_per_seed": 200000,
        "device": "cpu",
        "validation_visible_to_training": False,
        "eval_callback": False,
        "early_stopping": False,
        "best_model_selection": False,
        "checkpoint_selection": False,
        "member_selection": False,
        "saved_artifact": "FINAL_MODEL_ONLY",
        "synthetic_oracle_calibration": False,
    }:
        raise Type1ReportError("runner training contract is invalid")
    controls = manifest.get("controls")
    members = manifest.get("members")
    if not isinstance(controls, Mapping) or controls.get("integrity_ok") is not True or not isinstance(members, Mapping) or set(members) != {"primary", "shuffled_reward"}:
        raise Type1ReportError("runner controls or member families are invalid")
    for kind in ("primary", "shuffled_reward"):
        family = members[kind]
        if not isinstance(family, Mapping) or set(family) != {"0", "1", "2", "3", "4"}:
            raise Type1ReportError("runner member evidence is missing or extra")
        for seed in range(5):
            member = family[str(seed)]
            model_key = f"{kind}_seed_{seed}_model"
            normalizer_key = f"{kind}_seed_{seed}_normalizer"
            if not isinstance(member, Mapping) or member.get("seed") != seed or member.get("timesteps") != 200000 or member.get("actual_sb3_timesteps") != 200000 or member.get("device") != "cpu" or member.get("artifact") != "FINAL_MODEL_ONLY":
                raise Type1ReportError("runner member step or device receipt is invalid")
            artifacts, reload_receipt = member.get("artifacts"), member.get("reload_receipt")
            expected_artifacts = {"model_sha256": sources.get(model_key), "normalizer_sha256": sources.get(normalizer_key)}
            evidence = reload_receipt.get("evidence") if isinstance(reload_receipt, Mapping) else None
            normalizer, _ = _read_canonical(
                _safe_child(root, Path(kind) / f"seed_{seed}" / "normalizer.json"),
                f"{kind} seed {seed} normalizer",
            )
            try:
                from stom_rl.daily_type1_market import FeatureScale, TrainOnlyNormalizer

                scales = normalizer.get("scales")
                rebuilt_normalizer = TrainOnlyNormalizer(tuple(
                    FeatureScale(Decimal(item["center"]), Decimal(item["scale"]))
                    for item in scales
                )) if isinstance(scales, list) and len(scales) == 7 else None
                rebuilt_digest = rebuilt_normalizer.digest() if rebuilt_normalizer is not None else None
            except (InvalidOperation, KeyError, TypeError, ValueError):
                rebuilt_digest = None
            if (
                artifacts != expected_artifacts
                or not isinstance(reload_receipt, Mapping)
                or set(reload_receipt) != {"model_sha256", "normalizer_sha256", "deterministic", "evidence"}
                or reload_receipt.get("model_sha256") != expected_artifacts["model_sha256"]
                or reload_receipt.get("normalizer_sha256") != expected_artifacts["normalizer_sha256"]
                or reload_receipt.get("deterministic") is not True
                or not isinstance(evidence, Mapping)
                or set(evidence) != {
                    "model_sha256", "normalizer_sha256", "normalizer_digest",
                    "validation_pairs_sha256", "model_device", "num_timesteps",
                }
                or evidence.get("model_sha256") != expected_artifacts["model_sha256"]
                or evidence.get("normalizer_sha256") != expected_artifacts["normalizer_sha256"]
                or evidence.get("model_device") != "cpu"
                or evidence.get("num_timesteps") != 200000
                or _SHA.fullmatch(str(evidence.get("normalizer_digest", ""))) is None
                or _SHA.fullmatch(str(evidence.get("validation_pairs_sha256", ""))) is None
                or set(normalizer) != {"kind", "digest", "scales"}
                or normalizer.get("kind") != "market_type7_train_only"
                or normalizer.get("digest") != evidence.get("normalizer_digest")
                or rebuilt_digest != evidence.get("normalizer_digest")
                or not isinstance(normalizer.get("scales"), list)
            ):
                raise Type1ReportError("runner final artifact or persisted-normalizer replay receipt is invalid")

def _uninitialized_report_source_sha256(directory: Path, authority_sha256: str) -> dict[str, str]:
    paths = _report_source_paths(directory)
    skipped = set(_AUTHORITY_ARTIFACT_LABELS)
    sources = {label: _sha(_read_bytes(path, label)) for label, path in paths.items() if label not in skipped}
    sources["authority"] = authority_sha256
    return sources

def _validate_runner_authority_binding(manifest: Mapping[str, Any], authority: Mapping[str, Any], authority_sha256: str) -> None:
    identities = manifest.get("identities")
    if (
        not isinstance(identities, Mapping)
        or identities.get("authority_id") != authority.get("authority_id")
        or identities.get("authority_sha256") != authority_sha256
    ):
        raise Type1ReportError("frozen authority hash does not match runner identity")

def _report_authority_artifact_bytes(authority_raw: bytes, authority_sha256: str) -> dict[str, bytes]:
    outer = {"authority_sha256": authority_sha256, "identity": IDENTITY}
    return {
        "type1_identity": _canonical(outer),
        "public_run_seal": _canonical({**outer, "fresh_oos": {"state": "NOT_RUN", "payload_read": False}}),
        "deployment_lock": _canonical({**outer, "false_research_locks": LOCKS}),
        "attempt_parent": _canonical({
            **outer,
            "parent_identity": PARENT_ATTEMPT_IDENTITY,
            "parent_status": "MATERIALIZED_NOT_TRAINED_QUARANTINED",
            "models_created": 0,
            "fresh_oos": {"status": "NOT_RUN", "no_read": True},
        }),
        "authority": authority_raw,
    }

def _validate_pending_report_authority_sources(directory: Path, artifacts: Mapping[str, bytes]) -> None:
    paths = _report_source_paths(directory)
    fixed: dict[str, Mapping[str, Any]] = {
        label: _read_json(paths[label], label)
        for label in ("amendment", "protocol", "preregistration")
    }
    try:
        for label in _AUTHORITY_ARTIFACT_LABELS:
            value = json.loads(artifacts[label].decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError(f"{label} is not an object")
            fixed[label] = value
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise Type1ReportError("pending report authority artifact is invalid") from exc
    _validate_authority_sources(fixed)

def _preflight_report_authority_targets(directory: Path, artifacts: Mapping[str, bytes]) -> dict[str, Path]:
    targets = {label: _safe_child(directory, _SOURCE_LOCAL_PATHS[label]) for label in _AUTHORITY_ARTIFACT_LABELS}
    for label, path in targets.items():
        raw = artifacts[label]
        if path.exists() and _read_bytes(path, f"existing report authority artifact: {label}", maximum=len(raw)) != raw:
            raise Type1ReportError("report authority artifact already exists with different bytes")
    return targets

def initialize_report_authority(run_dir: str | Path, frozen_authority_envelope_path: str | Path) -> dict[str, str]:
    """Explicitly bridge a completed Type1 runner directory into immutable report sources."""
    directory = Path(run_dir).absolute()
    if not directory.is_dir() or _is_reparse(directory):
        raise Type1ReportError("run directory is required")
    manifest = _read_completed_runner_manifest(directory)
    _, authority, authority_raw = _read_frozen_authority_envelope(Path(frozen_authority_envelope_path).absolute())
    authority_sha256 = _sha(authority_raw)
    _validate_runner_authority_binding(manifest, authority, authority_sha256)
    sources = _uninitialized_report_source_sha256(directory, authority_sha256)
    _validate_runner_evidence(directory, sources)
    artifacts = _report_authority_artifact_bytes(authority_raw, authority_sha256)
    _validate_pending_report_authority_sources(directory, artifacts)
    targets = _preflight_report_authority_targets(directory, artifacts)
    for label in _AUTHORITY_ARTIFACT_LABELS:
        _write_new(targets[label], artifacts[label])
    return report_source_sha256(directory)

def _validate_revision(value: Mapping[str, Any]) -> None:
    required = {"schema_version", "revision_id", "revision_ordinal", "identity", "policy", "result", "source_sha256", "evidence", "false_research_locks", "claims", "catalog_ordinal", "previous_event_sha256", "previous_revision_event_sha256"}
    if set(value) != required or value.get("schema_version") != REVISION_SCHEMA or value.get("identity") != IDENTITY or value.get("policy") != POLICY:
        raise Type1ReportError("revision does not match frozen replacement Type1 contract")
    if not isinstance(value.get("revision_id"), str) or not re.fullmatch(r"type1-r[0-9]{4,}", value["revision_id"]): raise Type1ReportError("revision ID is invalid")
    if type(value.get("revision_ordinal")) is not int or value["revision_ordinal"] < 1: raise Type1ReportError("revision ordinal is invalid")
    if value.get("result") != REPORT_RESULT:
        raise Type1ReportError("report completion must be derived from validated runner evidence")
    sources, evidence = value.get("source_sha256"), value.get("evidence")
    required_evidence = {"type1_identity", "public_run_seal", "deployment_lock", "attempt_parent", "amendment", "protocol", "preregistration", "authority", "builder_source"}
    if not isinstance(sources, Mapping) or not isinstance(evidence, Mapping) or set(evidence) != required_evidence:
        raise Type1ReportError("replacement authority evidence is incomplete")
    for label, digest in sources.items():
        if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", label): raise Type1ReportError("source label is invalid")
        _require_sha(digest, "source SHA")
    for label in required_evidence:
        if evidence[label] != sources.get(label): raise Type1ReportError("authority evidence does not bind fixed source")
    if value.get("false_research_locks") != LOCKS or value.get("claims") != REPORT_CLAIMS:
        raise Type1ReportError("revision locks or claims are invalid")

def _render(revision: Mapping[str, Any], revision_sha: str) -> bytes:
    r = revision["result"]; failures = "".join(f"<li>{html.escape(str(x))}</li>" for x in r["failures"]) or "<li>None recorded.</li>"
    hashes = "".join(f"<li><code>{html.escape(k)}</code>: <code>{html.escape(v)}</code></li>" for k,v in sorted(revision["source_sha256"].items()))
    observed = f"<p>Observed completion — run: {html.escape(str(r['run_state']))}; training: {html.escape(str(r['training_state']))}; reused validation: {html.escape(str(r['reused_validation_state']))}.</p>"
    sections = (
        ("overview", "Overview", f"<p class=verdict>NO_GO</p>{observed}"),
        ("identity", "Type1 identity and scope", "<p>Replacement Type1 research-only evidence; not official close, alpha, profitability, paper, broker, live, or funded evidence.</p>"),
        ("protocol", "Protocol and accounting", "<p>Exact 15:20 close proxy and fixed-notional non-self-financing 23bp accounting.</p>"),
        ("training", "Training plan and observed completion", f"<p>Planned: five seeds × 200000 timesteps. This is a plan, not a completion claim.</p>{observed}"),
        ("validation", "Reused-validation controls", "<p>Reused validation can yield NO_GO only.</p>"),
        ("custody", "Fresh OOS and custody", f"<p>Fresh OOS: {html.escape(str(r['fresh_oos_state']))}; payload was not read.</p><p>M3E: {M3E_STATEMENT}</p>"),
        ("integrity", "Failures and integrity", f"<p>Revision SHA-256: <code>{revision_sha}</code></p><ul>{failures}</ul><ul>{hashes}</ul>"),
    )
    links = "".join(f'<a href="#{key}">{title}</a>' for key, title, _ in sections)
    body = "".join(f'<section id="{key}" aria-labelledby="{key}-heading"><h2 id="{key}-heading">{title}</h2>{content}</section>' for key, title, content in sections)
    text = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<title>Type1 immutable report</title><style>'
        'body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem;line-height:1.5}'
        'nav{display:flex;gap:.7rem;flex-wrap:wrap}'
        'section{border-top:1px solid #cbd5e1;margin-top:1rem}'
        '.verdict{font-weight:bold;padding:.6rem;background:#7f1d1d;color:white}'
        'code{overflow-wrap:anywhere}'
        '@media(max-width:600px){body{margin:1rem}nav{display:grid;grid-template-columns:1fr}}'
        '</style></head><body><h1>Type1 immutable reused-validation evidence</h1>'
        f'<nav aria-label="Report sections">{links}</nav><main>{body}</main></body></html>'
    )
    return text.encode("utf-8")

def verify_report_catalog(run_dir: str | Path, *, verify_parent: bool = True) -> dict[str, Any]:
    root=_root(run_dir); events_dir=_safe_child(root,Path("events")); objects_dir=_safe_child(root,Path("objects"))
    try: paths=list(events_dir.iterdir())
    except OSError as exc: raise Type1ReportError("events directory is unreadable") from exc
    if len(paths)>100000: raise Type1ReportError("event count exceeds bound")
    indexed=[]
    for p in paths:
        m=_EVENT.fullmatch(p.name)
        if not m or _is_reparse(p) or not p.is_file(): raise Type1ReportError("orphan or malformed event")
        indexed.append((int(m.group(1)),m.group(2),p))
    indexed.sort(); events=[]; revisions={}; materialized={}; previous=None
    for pos,(ordinal,name,p) in enumerate(indexed,1):
        if ordinal!=pos: raise Type1ReportError("event ordinal gap")
        event,raw=_read_canonical(p,"event"); digest=_sha(raw)
        if digest!=name or event.get("catalog_ordinal")!=ordinal or event.get("previous_event_sha256")!=previous: raise Type1ReportError("event identity or chain mismatch")
        if pos%2:
            _validate_revision(event)
            if event.get("previous_revision_event_sha256") != (events[-2][1] if len(events)>=2 else None) or event["revision_id"] in revisions or event["revision_ordinal"]!=(pos+1)//2: raise Type1ReportError("revision predecessor mismatch")
            sources = report_source_sha256(run_dir)
            if event["source_sha256"] != sources: raise Type1ReportError("revision source hashes differ from fixed evidence paths")
            _validate_runner_evidence(run_dir, sources)
            revisions[event["revision_id"]]=(event,digest)
        else:
            required={"schema_version","catalog_ordinal","previous_event_sha256","revision_event_sha256","builder_version","builder_source_sha256","object_id","html_sha256","byte_size"}
            if set(event)!=required or event.get("schema_version")!=MATERIALIZATION_SCHEMA or event.get("revision_event_sha256")!=events[-1][1] or event.get("builder_version")!=BUILDER_VERSION or event.get("builder_source_sha256")!=report_source_sha256(run_dir)["builder_source"]: raise Type1ReportError("materialization does not bind preceding revision")
            oid=event.get("object_id"); _require_sha(event.get("html_sha256"),"HTML SHA")
            if not isinstance(oid,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}",oid) or oid in materialized or type(event.get("byte_size")) is not int or event["byte_size"]<1: raise Type1ReportError("materialization is invalid")
            materialized[oid]=(event,digest)
        events.append((event,digest)); previous=digest
    opaths=list(objects_dir.iterdir())
    if len(opaths)!=len(materialized): raise Type1ReportError("orphan or missing object")
    for p in opaths:
        m=_OBJECT.fullmatch(p.name)
        if not m or _is_reparse(p) or not p.is_file() or m.group(1) not in materialized: raise Type1ReportError("orphan or malformed object")
        event,_=materialized[m.group(1)]; raw=_read_bytes(p,"object")
        if m.group(2)!=event["html_sha256"] or _sha(raw)!=event["html_sha256"] or len(raw)!=event["byte_size"]: raise Type1ReportError("object hash mismatch")
    tip_path=_safe_child(root,Path("committed_report_tip.json"))
    if not tip_path.exists():
        if events and verify_parent:
            _verify_current_parent(root, events, "DRAFT")
        return {"state":"DRAFT","event_count":len(events),"events":events,"root":root,"revisions":revisions}
    tip,tip_raw=_read_canonical(tip_path,"committed tip")
    required={"schema_version","identity","event_count","final_event_sha256","latest_revision_event_sha256","materialization_event_sha256","object_id","html_sha256"}
    if set(tip)!=required or tip.get("schema_version")!=TIP_SCHEMA or tip.get("identity")!=IDENTITY or tip.get("event_count")!=len(events) or not events or len(events)%2 or tip.get("final_event_sha256")!=events[-1][1] or tip.get("latest_revision_event_sha256")!=events[-2][1] or tip.get("materialization_event_sha256")!=events[-1][1] or tip.get("object_id")!=events[-1][0].get("object_id") or tip.get("html_sha256")!=events[-1][0].get("html_sha256"): raise Type1ReportError("committed tip is invalid")
    if verify_parent:
        _verify_current_parent(root, events, "COMMITTED")
    return {"state":"COMMITTED","event_count":len(events),"events":events,"root":root,"revisions":revisions,"tip":tip,"tip_sha256":_sha(tip_raw),"revision":events[-2][0],"materialization":events[-1][0]}

def _assert_parent(con: sqlite3.Connection, expected: str|None, state: str) -> None:
    row=con.execute("SELECT event_sha256,state FROM current_parent WHERE singleton=1").fetchone()
    if (row is None and expected is not None) or (row is not None and (row[0]!=expected or row[1]!=state)): raise Type1ReportError("current-parent authority mismatch")
def _reconcile_committed_tip(con: sqlite3.Connection, run_dir: str | Path) -> dict[str, Any] | None:
    """Repair only a tip file whose exact materialization CAS update was interrupted."""
    snapshot = verify_report_catalog(run_dir, verify_parent=False)
    if snapshot["state"] != "COMMITTED":
        return None
    expected = snapshot["tip"]["materialization_event_sha256"]
    row = con.execute("SELECT event_sha256,state FROM current_parent WHERE singleton=1").fetchone()
    if row == (expected, "COMMITTED"):
        return snapshot["tip"]
    if row != (expected, "MATERIALIZED"):
        raise Type1ReportError("tip reconciliation requires the exact materialized parent")
    updated = con.execute(
        "UPDATE current_parent SET state='COMMITTED' WHERE singleton=1 AND event_sha256=? AND state='MATERIALIZED'",
        (expected,),
    ).rowcount
    if updated != 1:
        raise Type1ReportError("tip reconciliation CAS failed")
    return snapshot["tip"]

def reconcile_report_tip(run_dir: str | Path) -> dict[str, Any]:
    """Explicit runner command for the sole recoverable MATERIALIZED-to-COMMITTED orphan."""
    root = _root(run_dir)
    con = _mutex(root)
    try:
        con.execute("BEGIN IMMEDIATE")
        tip = _reconcile_committed_tip(con, run_dir)
        if tip is None:
            raise Type1ReportError("no committed tip orphan is available for reconciliation")
        con.execute("COMMIT")
        return dict(tip)
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()

def insert_report_revision(run_dir: str|Path, revision: Mapping[str,Any])->dict[str,Any]:
    root=_root(run_dir,create=True); con=_mutex(root)
    try:
        con.execute("BEGIN IMMEDIATE"); snap=verify_report_catalog(run_dir)
        if snap["state"]=="COMMITTED" or len(snap["events"])%2: raise Type1ReportError("catalog is not open for a revision")
        expected=snap["events"][-1][1] if snap["events"] else None; _assert_parent(con,expected,"MATERIALIZED" if expected else "EMPTY")
        event=dict(revision); event.update({"catalog_ordinal":len(snap["events"])+1,"previous_event_sha256":expected,"previous_revision_event_sha256":snap["events"][-2][1] if snap["events"] else None})
        if event.get("revision_ordinal")!=(len(snap["events"])//2)+1: raise Type1ReportError("revision ordinal does not match catalog")
        _validate_revision(event)
        sources = report_source_sha256(run_dir)
        if event["source_sha256"]!=sources: raise Type1ReportError("revision source hashes differ from fixed evidence paths")
        _validate_runner_evidence(run_dir, sources)
        raw=_canonical(event); digest=_sha(raw); _write_new(_safe_child(root,Path("events")/f"{event['catalog_ordinal']:08d}-{digest}.json"),raw)
        con.execute("INSERT OR REPLACE INTO current_parent(singleton,event_sha256,state) VALUES(1,?,?)",(digest,"REVISION")); con.execute("COMMIT")
        return {"event_sha256":digest,"catalog_ordinal":event["catalog_ordinal"],"revision_id":event["revision_id"]}
    except Exception:
        con.execute("ROLLBACK"); raise
    finally: con.close()

def materialize_report_revision(run_dir: str|Path, revision_event_sha256:str)->dict[str,Any]:
    _require_sha(revision_event_sha256,"revision event SHA"); root=_root(run_dir); con=_mutex(root)
    try:
        con.execute("BEGIN IMMEDIATE"); snap=verify_report_catalog(run_dir)
        if snap["state"]=="COMMITTED" or not snap["events"] or len(snap["events"])%2==0 or snap["events"][-1][1]!=revision_event_sha256: raise Type1ReportError("only current unmaterialized revision may be materialized")
        _assert_parent(con,revision_event_sha256,"REVISION"); revision=snap["events"][-1][0]; data=_render(revision,revision_event_sha256); h=_sha(data); oid=revision["revision_id"]
        _write_new(_safe_child(root,Path("objects")/f"{oid}-{h}.html"),data)
        event={"schema_version":MATERIALIZATION_SCHEMA,"catalog_ordinal":len(snap["events"])+1,"previous_event_sha256":revision_event_sha256,"revision_event_sha256":revision_event_sha256,"builder_version":BUILDER_VERSION,"builder_source_sha256":report_source_sha256(run_dir)["builder_source"],"object_id":oid,"html_sha256":h,"byte_size":len(data)}; raw=_canonical(event); digest=_sha(raw)
        _write_new(_safe_child(root,Path("events")/f"{event['catalog_ordinal']:08d}-{digest}.json"),raw); con.execute("UPDATE current_parent SET event_sha256=?,state=? WHERE singleton=1",(digest,"MATERIALIZED")); con.execute("COMMIT")
        return {"event_sha256":digest,"object_id":oid,"html_sha256":h,"byte_size":len(data)}
    except Exception:
        con.execute("ROLLBACK"); raise
    finally: con.close()

def commit_report_tip(run_dir: str|Path, materialization_event_sha256:str)->dict[str,Any]:
    _require_sha(materialization_event_sha256,"materialization event SHA"); root=_root(run_dir); con=_mutex(root)
    try:
        con.execute("BEGIN IMMEDIATE")
        recovered = _reconcile_committed_tip(con, run_dir)
        if recovered is not None:
            con.execute("COMMIT")
            return dict(recovered)
        snap=verify_report_catalog(run_dir)
        if snap["state"]=="COMMITTED" or not snap["events"] or len(snap["events"])%2 or snap["events"][-1][1]!=materialization_event_sha256: raise Type1ReportError("only current materialization may be committed")
        _assert_parent(con,materialization_event_sha256,"MATERIALIZED"); m=snap["events"][-1][0]
        tip={"schema_version":TIP_SCHEMA,"identity":IDENTITY,"event_count":len(snap["events"]),"final_event_sha256":materialization_event_sha256,"latest_revision_event_sha256":snap["events"][-2][1],"materialization_event_sha256":materialization_event_sha256,"object_id":m["object_id"],"html_sha256":m["html_sha256"]}; _write_new(_safe_child(root,Path("committed_report_tip.json")),_canonical(tip)); con.execute("UPDATE current_parent SET state='COMMITTED' WHERE singleton=1"); con.execute("COMMIT"); return dict(tip)
    except Exception:
        con.execute("ROLLBACK"); raise
    finally: con.close()
