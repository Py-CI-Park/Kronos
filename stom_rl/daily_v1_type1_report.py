"""Immutable report authority for the replacement Type1 public run.

This module deliberately has no fresh-OOS inputs.  A report is a hash-addressed
revision, not a request for the latest report in a directory.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sqlite3
import stat
from datetime import date
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "docs" / "kronos_type1_g002_public_protocol_2026-07-23.json"
PREREG_PATH = REPO_ROOT / "docs" / "kronos_type1_closing_prereg_2026-07-23.json"
AMENDMENT_PATH = REPO_ROOT / "docs" / "kronos_type1_g002_recovery_amendment_v4_2026-07-24.json"
REPORT_ROOT = "type1_reports"
REVISION_SCHEMA = "kronos_type1_report_revision.v2"
MATERIALIZATION_SCHEMA = "kronos_type1_report_materialization.v2"
TIP_SCHEMA = "kronos_type1_committed_report_tip.v2"
BUILDER_VERSION = "kronos_type1_report_builder.v2"
_PUBLIC_ROWS_MAX_BYTES = 512 * 1024 * 1024
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
ORIGINAL_BLOCK_REASON = "conversion from numpy.int8 to Decimal is not supported"
BLOCKED_RUN_RECEIPT = {
    "execution_status": "BLOCK",
    "verdict": "NO_GO",
    "reason": ORIGINAL_BLOCK_REASON,
    "fresh_oos": {"state": "NOT_RUN", "metrics": None},
}
RECOVERY_MANIFEST_SCHEMA = "kronos_type1_g002_public_run_recovery.v1"
RECOVERY_RECEIPT_SCHEMA = "kronos.type1.public-run-recovery-receipt.v1"
RECOVERY_MANIFEST_ROLE = "TYPE1_PUBLIC_RUN_RECOVERY"
RECOVERY_RECEIPT_ROLE = "TYPE1_PUBLIC_RUN_RECOVERY_RECEIPT"
RECOVERY_MODE = "APPEND_ONLY_REEVALUATE_SAVED_MODELS"
RECOVERED_RUN_EVIDENCE_MODE = "RECOVERED_AFTER_BLOCK"
COMPLETED_RUN_EVIDENCE_MODE = "COMPLETED_RUN"
RECOVERY_FRESH_OOS = {"state": "NOT_RUN", "metrics": None, "read_performed": False}
RECOVERY_CLAIMS = {"profitability": "NOT_CLAIMED", "live": "NOT_CLAIMED", "fresh_oos": "NOT_RUN_NO_READ", "outcome": "NO_GO_ONLY"}
PUBLICATION_RECEIPT_NAME = "publication_receipt.json"
PUBLICATION_RECEIPT_SCHEMA_V1 = "kronos.type1.publication-receipt.v1"
PUBLICATION_RECEIPT_SCHEMA_V2 = "kronos.type1.publication-receipt.v2"
PUBLICATION_RECEIPT_SCHEMA = PUBLICATION_RECEIPT_SCHEMA_V1
PUBLICATION_RECEIPT_ROLE = "TYPE1_PUBLICATION_RECEIPT"
PUBLICATION_SOURCE_LOGICAL_PATH = "artifacts/type1-public-runs/train_type1-public-005"
PUBLICATION_DESTINATION_LOGICAL_PATH = "webui/rl_runs/v6_daily_h1/type1-close-20260803-005/train_type1-public-005"
PUBLICATION_MOVE_CONTRACT = {"operation": "same_volume_atomic_directory_rename", "copy_performed": False, "overwrite_performed": False, "delete_performed": False}
PUBLICATION_RECOVERED_MODE = "recovered"
PUBLICATION_RECOVERED_RUN_EVIDENCE_MODE = RECOVERED_RUN_EVIDENCE_MODE
PUBLICATION_RECOVERY_DISCLOSURE_KEY = "disclosure"
TYPE1_FEATURES = (
    "ret_1d_prev",
    "ret_5d_prev",
    "ret_20d_prev",
    "vol_z_20",
    "foreign_ratio_prev",
    "foreign_ratio_delta_5",
    "inst_netbuy_norm_5",
)
COMPLETED_REPORT_RUN_DIR = REPO_ROOT / PUBLICATION_DESTINATION_LOGICAL_PATH
FROZEN_AUTHORITY_ENVELOPE_PATH = (
    REPO_ROOT / "webui" / "rl_runs" / "v6_daily_h1" / "type1_authorities" / f"{REPLACEMENT_IDENTITY['authority_id']}.json"
)
COMPLETED_REPORT_EVIDENCE_LABELS = (
    "type1_identity",
    "public_run_seal",
    "deployment_lock",
    "attempt_parent",
    "amendment",
    "protocol",
    "preregistration",
    "authority",
    "builder_source",
    "publication_receipt",
)
RECOVERED_REPORT_EVIDENCE_LABELS = (
    "type1_identity",
    "public_run_seal",
    "deployment_lock",
    "attempt_parent",
    "amendment",
    "protocol",
    "preregistration",
    "authority",
    "builder_source",
    "blocked_receipt",
    "recovery_manifest",
    "recovery_receipt",
    "publication_receipt",
)
REPORT_EVIDENCE_LABELS = COMPLETED_REPORT_EVIDENCE_LABELS
MATERIALIZER_FRESH_OOS = {"state": "NOT_RUN", "read_performed": False}
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
RECOVERED_REPORT_CLAIMS = {
    **REPORT_CLAIMS,
    "recovery_from_blocked_controls": True,
    "recovery_mode": RECOVERY_MODE,
    "original_control_failure_reason": ORIGINAL_BLOCK_REASON,
    "original_block_receipt_preserved": True,
    "retraining_performed": False,
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
    "blocked_receipt": Path("receipt.json"),
    "recovery_manifest": Path("recovery_manifest.json"),
    "recovery_receipt": Path("recovery_receipt.json"),
    "publication_receipt": Path(PUBLICATION_RECEIPT_NAME),
    **{f"{kind}_seed_{seed}_{artifact}": Path(kind) / f"seed_{seed}" / filename
       for kind in ("primary", "shuffled_reward") for seed in range(5)
       for artifact, filename in (("model", "final_model.zip"), ("normalizer", "normalizer.json"))},
}
_AUTHORITY_ARTIFACT_LABELS = ("type1_identity", "public_run_seal", "deployment_lock", "attempt_parent", "authority")
_RECOVERY_SOURCE_SHA256_LABELS = (
    "runner",
    "market",
    "protocol",
    "amendment",
    "authority",
    "public_rows",
    "dataset_manifest",
    "materializer_manifest",
    "materializer_complete_receipt",
)
_RECOVERY_CUSTODY_BINDING_LABELS = (
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
)
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


def _canonical_copy(value: Any) -> Any:
    return json.loads(_canonical(value).decode("utf-8"))

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
def _runner_evidence_mode(directory: Path) -> str:
    has_completed = _safe_child(directory, Path("run_manifest.json")).exists()
    has_recovery_manifest = _safe_child(directory, Path("recovery_manifest.json")).exists()
    has_recovery_receipt = _safe_child(directory, Path("recovery_receipt.json")).exists()
    if has_completed and (has_recovery_manifest or has_recovery_receipt):
        raise Type1ReportError("runner evidence mode is ambiguous")
    if has_recovery_manifest != has_recovery_receipt:
        raise Type1ReportError("recovery evidence is incomplete")
    if has_recovery_manifest:
        return RECOVERED_RUN_EVIDENCE_MODE
    if has_completed:
        return COMPLETED_RUN_EVIDENCE_MODE
    raise Type1ReportError("runner evidence is missing")


def _source_evidence_mode(sources: Mapping[str, Any]) -> str:
    has_completed = "run_manifest" in sources or "run_receipt" in sources
    has_recovered = any(label in sources for label in ("blocked_receipt", "recovery_manifest", "recovery_receipt"))
    if has_completed and has_recovered:
        raise Type1ReportError("runner source evidence mode is ambiguous")
    if has_recovered and {"blocked_receipt", "recovery_manifest", "recovery_receipt"} <= set(sources):
        return RECOVERED_RUN_EVIDENCE_MODE
    if has_completed and {"run_manifest", "run_receipt"} <= set(sources):
        return COMPLETED_RUN_EVIDENCE_MODE
    raise Type1ReportError("runner source evidence is incomplete")


def _report_evidence_labels_for_sources(sources: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        RECOVERED_REPORT_EVIDENCE_LABELS
        if _source_evidence_mode(sources) == RECOVERED_RUN_EVIDENCE_MODE
        else COMPLETED_REPORT_EVIDENCE_LABELS
    )


def _report_claims_for_sources(sources: Mapping[str, Any]) -> dict[str, Any]:
    return (
        _canonical_copy(RECOVERED_REPORT_CLAIMS)
        if _source_evidence_mode(sources) == RECOVERED_RUN_EVIDENCE_MODE
        else _canonical_copy(REPORT_CLAIMS)
    )


def _expected_member_artifact_sha256(sources: Mapping[str, Any]) -> dict[str, Any]:
    members = {
        f"{kind}/seed_{seed}/final_model.zip": sources.get(f"{kind}_seed_{seed}_model")
        for kind in ("primary", "shuffled_reward")
        for seed in range(5)
    }
    members.update({
        f"{kind}/seed_{seed}/normalizer.json": sources.get(f"{kind}_seed_{seed}_normalizer")
        for kind in ("primary", "shuffled_reward")
        for seed in range(5)
    })
    return members




def _validate_publication_fresh_oos(value: Any) -> None:
    if not isinstance(value, Mapping) or value.get("read_performed") is not False:
        raise Type1ReportError("publication receipt fresh-OOS claim is unsafe")
    if value in (RECOVERY_FRESH_OOS, {"state": "NOT_RUN", "read_performed": False}):
        return
    for key, nested in value.items():
        if key == "read_performed":
            continue
        if not isinstance(nested, Mapping):
            raise Type1ReportError("publication receipt fresh-OOS claim is unsafe")
        state = nested.get("state", nested.get("status"))
        if state != "NOT_RUN":
            raise Type1ReportError("publication receipt fresh-OOS claim is unsafe")
        if nested.get("metrics") is not None:
            raise Type1ReportError("publication receipt fresh-OOS claim is unsafe")
        if nested.get("read_performed") is True or nested.get("no_read") is False:
            raise Type1ReportError("publication receipt fresh-OOS claim is unsafe")

def _read_bytes(path: Path, label: str, *, maximum: int = 64 * 1024 * 1024) -> bytes:
    if not path.is_file() or _is_reparse(path):
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

def _read_report_source_bytes(path: Path, label: str) -> bytes:
    maximum = _PUBLIC_ROWS_MAX_BYTES if label == "public_rows" else 64 * 1024 * 1024
    return _read_bytes(path, label, maximum=maximum)

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
def _expected_recovery_source_sha256(sources: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "runner": _sha(_read_bytes(REPO_ROOT / "stom_rl" / "daily_type1_public_run.py", "runner source")),
        "market": _sha(_read_bytes(REPO_ROOT / "stom_rl" / "daily_type1_market.py", "market source")),
        "protocol": sources.get("protocol"),
        "amendment": sources.get("amendment"),
        "authority": sources.get("authority"),
        "public_rows": sources.get("public_rows"),
        "dataset_manifest": sources.get("dataset_manifest"),
        "materializer_manifest": sources.get("dataset_manifest"),
        "materializer_complete_receipt": sources.get("materializer_complete_receipt"),
    }


def _validate_recovery_source_sha256(value: Any, sources: Mapping[str, Any], label: str) -> None:
    expected = _expected_recovery_source_sha256(sources)
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise Type1ReportError(f"{label} source hashes do not match the recovered runner schema")
    for source_label in _RECOVERY_SOURCE_SHA256_LABELS:
        expected_digest = _require_sha(expected.get(source_label), f"{label} expected {source_label} SHA")
        actual_digest = _require_sha(value.get(source_label), f"{label} {source_label} SHA")
        if actual_digest != expected_digest:
            raise Type1ReportError(f"{label} source hash mismatch")


def _parse_exact_iso_date(value: Any, label: str) -> date:
    if (
        not isinstance(value, str)
        or len(value) != 10
        or value[4] != "-"
        or value[7] != "-"
        or not (value[:4] + value[5:7] + value[8:]).isdigit()
    ):
        raise Type1ReportError(f"{label} authority session must be an exact ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise Type1ReportError(f"{label} authority session must be an exact ISO date") from exc
    if parsed.isoformat() != value:
        raise Type1ReportError(f"{label} authority session must be an exact ISO date")
    return parsed


def _validate_ordered_authority_dates(ordered: list[Any], label: str) -> None:
    previous: date | None = None
    seen: set[str] = set()
    for index, session in enumerate(ordered):
        parsed = _parse_exact_iso_date(session, f"{label} ordered session {index}")
        if session in seen or (previous is not None and parsed <= previous):
            raise Type1ReportError(f"{label} authority session ordered dates must be unique and strictly increasing ISO dates")
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


def _validate_authority_sessions(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _RECOVERY_AUTHORITY_SESSION_KEYS:
        raise Type1ReportError(f"{label} authority session schema is invalid")
    count = value["count"]
    first = value["first"]
    last = value["last"]
    ordered = value["ordered"]
    pairs = value["pairs"]
    parity = value["parity"]
    trailing_embargo = value["trailing_embargo"]
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
        raise Type1ReportError(f"{label} authority session count/first/last/parity are inconsistent")
    _validate_ordered_authority_dates(ordered, label)
    expected_pairs = [[index, index + 1] for index in range(0, count - parity, 2)]
    expected_trailing_embargo = [count - 1] if parity else []
    if not _exact_index_pairs(pairs, expected_pairs) or not _exact_index_list(trailing_embargo, expected_trailing_embargo):
        raise Type1ReportError(f"{label} authority session pairing is inconsistent")
    return value
def _validate_authority_sessions_match(actual: Any, expected: Any, label: str) -> Mapping[str, Any]:
    actual_sessions = _validate_authority_sessions(actual, label)
    expected_sessions = _validate_authority_sessions(expected, "frozen authority envelope")
    if actual_sessions != expected_sessions:
        raise Type1ReportError(f"{label} authority sessions do not match frozen authority envelope sessions")
    return actual_sessions




def _validate_recovery_identity(
    value: Any,
    sources: Mapping[str, Any],
    label: str,
    authority_sessions: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _RECOVERY_IDENTITY_KEYS:
        raise Type1ReportError(f"{label} does not match the recovered runner identity schema")
    if {key: value.get(key) for key in REPLACEMENT_IDENTITY} != REPLACEMENT_IDENTITY:
        raise Type1ReportError(f"{label} does not bind the replacement run identity")
    expected_source = _expected_recovery_source_sha256(sources)
    expected_hashes = {
        "amendment_sha256": sources.get("amendment"),
        "authority_sha256": sources.get("authority"),
        "materializer_sha256": sources.get("dataset_manifest"),
        "materializer_complete_receipt_sha256": sources.get("materializer_complete_receipt"),
        "preregistration_sha256": sources.get("preregistration"),
        "parent_protocol_sha256": sources.get("protocol"),
        "runner_source_sha256": expected_source["runner"],
    }
    for identity_key, expected_digest in expected_hashes.items():
        if _require_sha(value.get(identity_key), f"{label} {identity_key}") != _require_sha(expected_digest, f"{label} expected {identity_key}"):
            raise Type1ReportError(f"{label} source hash mismatch")
    _require_sha(value.get("materializer_source_sha256"), f"{label} materializer_source_sha256")
    if not isinstance(value.get("source_database_identity"), Mapping):
        raise Type1ReportError(f"{label} source database identity is missing")
    if authority_sessions is None:
        _validate_authority_sessions(value.get("authority_sessions"), label)
    else:
        _validate_authority_sessions_match(value.get("authority_sessions"), authority_sessions, label)
    return value


def _expected_recovery_custody_bindings(root: Path, sources: Mapping[str, Any], blocked_receipt_sha256: str) -> dict[str, dict[str, Any]]:
    source_sha256 = _expected_recovery_source_sha256(sources)
    authority_source = root / "frozen_authority_envelope.json"
    authority_path = authority_source if authority_source.exists() else FROZEN_AUTHORITY_ENVELOPE_PATH
    dataset_manifest_path = _safe_child(root.parent, Path("dataset_manifest.json"))
    return {
        "blocked_receipt": {"path": "receipt.json", "sha256": blocked_receipt_sha256},
        "protocol": {"path": _display_path(PROTOCOL_PATH), "sha256": sources.get("protocol")},
        "amendment": {"path": _display_path(AMENDMENT_PATH), "sha256": sources.get("amendment")},
        "public_rows": {"path": _display_path(_safe_child(root.parent, Path("public_rows.json"))), "sha256": sources.get("public_rows")},
        "dataset_manifest": {"path": _display_path(dataset_manifest_path), "sha256": sources.get("dataset_manifest")},
        "materializer_manifest": {"path": _display_path(dataset_manifest_path), "sha256": sources.get("dataset_manifest")},
        "materializer_complete_receipt": {"path": _display_path(_safe_child(root.parent, Path("materializer_complete_receipt.json"))), "sha256": sources.get("materializer_complete_receipt")},
        "authority": {"path": _display_path(authority_path), "sha256": sources.get("authority")},
        "runner": {"path": "stom_rl/daily_type1_public_run.py", "sha256": source_sha256["runner"]},
        "market": {"path": "stom_rl/daily_type1_market.py", "sha256": source_sha256["market"]},
    }


def _validate_recovery_custody_bindings(root: Path, value: Any, sources: Mapping[str, Any], blocked_receipt_sha256: str) -> None:
    expected = _expected_recovery_custody_bindings(root, sources, blocked_receipt_sha256)
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise Type1ReportError("recovery manifest custody bindings do not match the recovered runner schema")
    for label in _RECOVERY_CUSTODY_BINDING_LABELS:
        binding = value.get(label)
        expected_binding = expected[label]
        if not isinstance(binding, Mapping) or set(binding) != {"path", "sha256"}:
            raise Type1ReportError("recovery manifest custody binding is malformed")
        if binding.get("path") != expected_binding["path"]:
            raise Type1ReportError("recovery manifest custody path mismatch")
        expected_digest = _require_sha(expected_binding.get("sha256"), f"expected {label} custody SHA")
        actual_digest = _require_sha(binding.get("sha256"), f"{label} custody SHA")
        if actual_digest != expected_digest:
            raise Type1ReportError("recovery manifest custody hash mismatch")

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
    ):
        raise Type1ReportError(f"{label} does not bind the frozen v5 authority")
    _validate_authority_sessions(sessions, label)
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
    mode = _runner_evidence_mode(directory)
    excluded = {"dataset_manifest", "public_rows", "materializer_complete_receipt"}
    excluded.update(
        {"blocked_receipt", "recovery_manifest", "recovery_receipt"}
        if mode == COMPLETED_RUN_EVIDENCE_MODE
        else {"run_manifest", "run_receipt"}
    )
    return {
        "amendment": _safe_child(REPO_ROOT, Path("docs") / AMENDMENT_PATH.name),
        "protocol": _safe_child(REPO_ROOT, Path("docs") / PROTOCOL_PATH.name),
        "preregistration": _safe_child(REPO_ROOT, Path("docs") / PREREG_PATH.name),
        "builder_source": _safe_child(REPO_ROOT, Path("stom_rl") / Path(__file__).name),
        **{label: _safe_child(directory, relative) for label, relative in _SOURCE_LOCAL_PATHS.items() if label not in excluded},
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
    sources = {label: _sha(_read_report_source_bytes(path, label)) for label, path in paths.items()}
    authority_sessions = (
        _authority_payload(fixed["authority"], "authority source")["sessions"]
        if _source_evidence_mode(sources) == RECOVERED_RUN_EVIDENCE_MODE
        else None
    )
    _validate_publication_receipt(directory, sources, authority_sessions)
    return sources

def _publication_expected_materializer(sources: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "public_rows_sha256": sources.get("public_rows"),
        "dataset_manifest_sha256": sources.get("dataset_manifest"),
        "materializer_complete_receipt_sha256": sources.get("materializer_complete_receipt"),
    }


def _validate_publication_hash_maps(
    materializer: Any,
    members: Any,
    expected_materializer: Mapping[str, Any],
    expected_members: Mapping[str, Any],
) -> None:
    if not isinstance(materializer, Mapping):
        raise Type1ReportError("publication receipt materializer hashes are invalid")
    for label, digest in expected_materializer.items():
        _require_sha(digest, f"{label} source SHA")
        _require_sha(materializer.get(label), f"{label} publication SHA")
        if materializer.get(label) != digest:
            raise Type1ReportError("publication receipt materializer hash mismatch")
    if not isinstance(members, Mapping) or len(members) != 20:
        raise Type1ReportError("publication receipt member artifact hashes are invalid")
    for label, digest in expected_members.items():
        _require_sha(digest, f"{label} source SHA")
        _require_sha(members.get(label), f"{label} publication SHA")
        if members.get(label) != digest:
            raise Type1ReportError("publication receipt member artifact hash mismatch")


def _validate_completed_publication_receipt(receipt: Mapping[str, Any], sources: Mapping[str, Any], raw: bytes) -> None:
    materializer = receipt.get("materializer_sha256")
    expected_materializer = _publication_expected_materializer(sources)
    expected_members = _expected_member_artifact_sha256(sources)
    required = {
        "schema_version", "role", "status", "verdict", "identity",
        "source_logical_path", "destination_logical_path", "move_contract",
        "run_manifest_sha256", "run_receipt_sha256", "member_artifact_sha256",
        "materializer_sha256", "publisher_source_sha256", "fresh_oos",
    }
    if (
        set(receipt) != required
        or receipt.get("schema_version") != PUBLICATION_RECEIPT_SCHEMA_V1
        or receipt.get("role") != PUBLICATION_RECEIPT_ROLE
        or receipt.get("status") != "COMPLETE"
        or receipt.get("verdict") != "NO_GO"
        or receipt.get("identity") != REPLACEMENT_IDENTITY
        or receipt.get("source_logical_path") != PUBLICATION_SOURCE_LOGICAL_PATH
        or receipt.get("destination_logical_path") != PUBLICATION_DESTINATION_LOGICAL_PATH
        or receipt.get("move_contract") != PUBLICATION_MOVE_CONTRACT
        or _sha(raw) != sources.get("publication_receipt")
        or receipt.get("run_manifest_sha256") != sources.get("run_manifest")
        or receipt.get("run_receipt_sha256") != sources.get("run_receipt")
        or materializer != expected_materializer
        or receipt.get("member_artifact_sha256") != expected_members
        or receipt.get("fresh_oos") != {
            "run": RUNNER_RECEIPT["fresh_oos"],
            "materializer": MATERIALIZER_FRESH_OOS,
            "read_performed": False,
        }
    ):
        raise Type1ReportError("publication receipt does not prove the canonical v5 publication move")
    _require_sha(receipt.get("publisher_source_sha256"), "publisher source SHA")
    _require_sha(receipt.get("run_manifest_sha256"), "publication run manifest SHA")
    _require_sha(receipt.get("run_receipt_sha256"), "publication run receipt SHA")
    _validate_publication_hash_maps(materializer, receipt.get("member_artifact_sha256"), expected_materializer, expected_members)


def _validate_recovered_publication_receipt(
    receipt: Mapping[str, Any],
    sources: Mapping[str, Any],
    raw: bytes,
    authority_sessions: Mapping[str, Any] | None,
) -> None:
    materializer = receipt.get("materializer_sha256")
    expected_materializer = _publication_expected_materializer(sources)
    expected_members = _expected_member_artifact_sha256(sources)
    expected_publisher_source_sha256 = _sha(_read_bytes(REPO_ROOT / "stom_rl" / "daily_type1_publication.py", "publisher source"))
    required = {
        "schema_version", "role", "status", "verdict", "mode", "disclosure",
        "run_evidence_mode", "identity", "source_logical_path", "destination_logical_path",
        "move_contract", "recovery_receipt_sha256", "original_block_reason",
        "preserved_block_receipt", "retraining_performed", "fresh_oos",
        "false_research_locks", "materializer_sha256", "materializer_public_rows_sha256",
        "materializer_source_sha256", "materializer_source_hashes", "source_hashes",
        "publisher_source_sha256",
    }
    disclosure = receipt.get("disclosure")
    if (
        set(receipt) != required
        or receipt.get("schema_version") != PUBLICATION_RECEIPT_SCHEMA_V2
        or receipt.get("role") != PUBLICATION_RECEIPT_ROLE
        or receipt.get("status") != "COMPLETE"
        or receipt.get("verdict") != "NO_GO"
        or receipt.get("mode") != PUBLICATION_RECOVERED_MODE
        or receipt.get("run_evidence_mode") != PUBLICATION_RECOVERED_RUN_EVIDENCE_MODE
        or receipt.get("source_logical_path") != PUBLICATION_SOURCE_LOGICAL_PATH
        or receipt.get("destination_logical_path") != PUBLICATION_DESTINATION_LOGICAL_PATH
        or receipt.get("move_contract") != PUBLICATION_MOVE_CONTRACT
        or _sha(raw) != sources.get("publication_receipt")
        or receipt.get("recovery_receipt_sha256") != sources.get("recovery_receipt")
        or receipt.get("original_block_reason") != ORIGINAL_BLOCK_REASON
        or receipt.get("retraining_performed") is not False
        or receipt.get("preserved_block_receipt") is not True
        or receipt.get("fresh_oos") != RECOVERY_FRESH_OOS
        or receipt.get("false_research_locks") != LOCKS
        or materializer != expected_materializer
        or receipt.get("materializer_public_rows_sha256") != expected_materializer["public_rows_sha256"]
        or receipt.get("publisher_source_sha256") != expected_publisher_source_sha256
    ):
        raise Type1ReportError("publication receipt does not prove the recovered v5 publication move")
    _validate_recovery_identity(receipt.get("identity"), sources, "publication receipt identity", authority_sessions)
    _require_sha(receipt.get("recovery_receipt_sha256"), "publication recovery receipt SHA")
    _require_sha(receipt.get("materializer_source_sha256"), "publication materializer source SHA")
    _validate_publication_fresh_oos(receipt.get("fresh_oos"))
    if (
        not isinstance(disclosure, Mapping)
        or set(disclosure) != {"recovery_manifest_sha256", "blocked_receipt_sha256", "members"}
        or disclosure.get("recovery_manifest_sha256") != sources.get("recovery_manifest")
        or disclosure.get("blocked_receipt_sha256") != sources.get("blocked_receipt")
        or disclosure.get("members") != expected_members
    ):
        raise Type1ReportError("publication receipt append-only recovery disclosure is invalid")
    _validate_publication_hash_maps(materializer, disclosure.get("members"), expected_materializer, expected_members)
    expected_source_hashes = {
        "publisher_source": expected_publisher_source_sha256,
        **_expected_recovery_source_sha256(sources),
    }
    source_hashes = receipt.get("source_hashes")
    if not isinstance(source_hashes, Mapping) or set(source_hashes) != set(expected_source_hashes):
        raise Type1ReportError("publication receipt source hashes are invalid")
    for label, expected_digest in expected_source_hashes.items():
        _require_sha(expected_digest, f"expected publication {label} source SHA")
        if source_hashes.get(label) != expected_digest:
            raise Type1ReportError("publication receipt source hash mismatch")
    materializer_source_hashes = receipt.get("materializer_source_hashes")
    if not isinstance(materializer_source_hashes, Mapping) or set(materializer_source_hashes) != {"materializer", "protocol", "preregistration", "amendment", "authority"}:
        raise Type1ReportError("publication receipt materializer source hashes are invalid")
    for label in ("protocol", "preregistration", "amendment", "authority"):
        if materializer_source_hashes.get(label) != sources.get(label):
            raise Type1ReportError("publication receipt materializer source hash mismatch")
    if materializer_source_hashes.get("materializer") != receipt.get("materializer_source_sha256"):
        raise Type1ReportError("publication receipt materializer source hash mismatch")


def _validate_publication_receipt(root: Path, sources: Mapping[str, Any], authority_sessions: Mapping[str, Any] | None = None) -> None:
    receipt, raw = _read_canonical(_safe_child(root, Path(PUBLICATION_RECEIPT_NAME)), "publication receipt")
    mode = _source_evidence_mode(sources)
    if mode == COMPLETED_RUN_EVIDENCE_MODE and receipt.get("schema_version") == PUBLICATION_RECEIPT_SCHEMA_V1:
        _validate_completed_publication_receipt(receipt, sources, raw)
        return
    if mode == RECOVERED_RUN_EVIDENCE_MODE and receipt.get("schema_version") == PUBLICATION_RECEIPT_SCHEMA_V2:
        _validate_recovered_publication_receipt(receipt, sources, raw, authority_sessions)
        return
    raise Type1ReportError("publication receipt schema does not match runner evidence mode")

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


def _read_runner_manifest_for_authority(root: Path) -> dict[str, Any]:
    if _runner_evidence_mode(root) == COMPLETED_RUN_EVIDENCE_MODE:
        return _read_completed_runner_manifest(root)
    manifest = _read_canonical(_safe_child(root, Path("recovery_manifest.json")), "recovery manifest")[0]
    if not isinstance(manifest.get("identities"), Mapping):
        raise Type1ReportError("recovery manifest identity is missing")
    return manifest


def _read_original_block_receipt(root: Path, expected_receipt_sha256: Any = None) -> tuple[dict[str, Any], str]:
    receipt, raw = _read_canonical(_safe_child(root, Path("receipt.json")), "blocked receipt")
    receipt_sha256 = _sha(raw)
    if expected_receipt_sha256 is not None and receipt_sha256 != expected_receipt_sha256:
        raise Type1ReportError("blocked receipt source hash mismatch")
    if receipt != BLOCKED_RUN_RECEIPT:
        raise Type1ReportError("original blocked receipt violates the exact BLOCK control-failure reason")
    return receipt, receipt_sha256


def _read_recovery_manifest(
    root: Path,
    sources: Mapping[str, Any],
    blocked_receipt_sha256: str,
    authority_sessions: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    manifest, raw = _read_canonical(_safe_child(root, Path("recovery_manifest.json")), "recovery manifest")
    manifest_sha256 = _sha(raw)
    if manifest_sha256 != sources.get("recovery_manifest"):
        raise Type1ReportError("recovery manifest source hash mismatch")
    required = {
        "schema_version", "role", "status", "recovery_status", "recovery_mode",
        "source_commit", "original_run_id", "reused_original_run_id", "original_block",
        "protocol", "identities", "features", "public_splits", "session_pairing",
        "training", "members", "aggregation", "pretraining_gate", "controls",
        "source_sha256", "materializer_sha256", "custody_bindings", "fresh_oos",
        "false_research_locks", "execution_status", "verdict", "decision", "claims",
    }
    expected_original_block = {
        "path": "receipt.json",
        "receipt_sha256": blocked_receipt_sha256,
        "status": "BLOCK",
        "execution_status": "BLOCK",
        "verdict": "NO_GO",
        "reason": ORIGINAL_BLOCK_REASON,
        "fresh_oos": RECOVERY_FRESH_OOS,
        "preserved_byte_identical": True,
    }
    if (
        set(manifest) != required
        or {"run_manifest_sha256", "run_receipt_sha256"} & set(manifest)
        or manifest.get("schema_version") != RECOVERY_MANIFEST_SCHEMA
        or manifest.get("role") != RECOVERY_MANIFEST_ROLE
        or manifest.get("status") != "COMPLETE"
        or manifest.get("recovery_status") != "COMPLETE"
        or manifest.get("recovery_mode") != RECOVERY_MODE
        or manifest.get("source_commit") != "4ba930c"
        or manifest.get("original_run_id") != REPLACEMENT_IDENTITY["train_run_id"]
        or manifest.get("reused_original_run_id") is not True
        or manifest.get("original_block") != expected_original_block
        or manifest.get("protocol") != {
            "id": "KRONOS-TYPE1-G002-PUBLIC-2026-07-23",
            "sha256": sources.get("protocol"),
        }
        or manifest.get("features") != list(TYPE1_FEATURES)
        or not all(isinstance(manifest.get(label), Mapping) for label in ("public_splits", "session_pairing", "aggregation"))
        or manifest.get("materializer_sha256") != sources.get("dataset_manifest")
        or manifest.get("fresh_oos") != RECOVERY_FRESH_OOS
        or manifest.get("false_research_locks") != LOCKS
        or any(value is not False for value in manifest["false_research_locks"].values())
        or manifest.get("execution_status") != "COMPLETE"
        or manifest.get("verdict") != "NO_GO"
        or manifest.get("decision") != "NO_GO"
        or manifest.get("claims") != RECOVERY_CLAIMS
    ):
        raise Type1ReportError("recovery manifest violates the append-only no-go contract")
    _validate_recovery_source_sha256(manifest.get("source_sha256"), sources, "recovery manifest")
    identities = _validate_recovery_identity(manifest.get("identities"), sources, "recovery manifest identity", authority_sessions)
    if manifest["session_pairing"].get("trailing_embargo") != identities["authority_sessions"]["trailing_embargo"]:
        raise Type1ReportError("recovery manifest session pairing does not match authority sessions")
    _validate_recovery_custody_bindings(root, manifest.get("custody_bindings"), sources, blocked_receipt_sha256)
    return manifest, manifest_sha256


def _validate_recovery_receipt(root: Path, sources: Mapping[str, Any], recovery_manifest_sha256: str) -> None:
    receipt, raw = _read_canonical(_safe_child(root, Path("recovery_receipt.json")), "recovery receipt")
    expected_members = _expected_member_artifact_sha256(sources)
    required = {
        "schema_version", "role", "status", "execution_status", "verdict", "decision",
        "run_id", "recovery_manifest_sha256", "blocked_receipt_sha256", "blocked_receipt_path",
        "blocked_reason", "original_block_reason", "original_block_preserved",
        "retraining_performed", "overwrite_performed", "move_performed", "delete_performed",
        "fresh_oos", "member_artifact_sha256", "source_sha256", "materializer_sha256",
        "outcome",
    }
    if (
        set(receipt) != required
        or {"run_manifest_sha256", "run_receipt_sha256"} & set(receipt)
        or _sha(raw) != sources.get("recovery_receipt")
        or receipt.get("schema_version") != RECOVERY_RECEIPT_SCHEMA
        or receipt.get("role") != RECOVERY_RECEIPT_ROLE
        or receipt.get("status") != "COMPLETE"
        or receipt.get("execution_status") != "COMPLETE"
        or receipt.get("verdict") != "NO_GO"
        or receipt.get("decision") != "NO_GO"
        or receipt.get("run_id") != REPLACEMENT_IDENTITY["train_run_id"]
        or receipt.get("recovery_manifest_sha256") != recovery_manifest_sha256
        or receipt.get("blocked_receipt_sha256") != sources.get("blocked_receipt")
        or receipt.get("blocked_receipt_path") != "receipt.json"
        or receipt.get("blocked_reason") != ORIGINAL_BLOCK_REASON
        or receipt.get("original_block_reason") != ORIGINAL_BLOCK_REASON
        or receipt.get("original_block_preserved") is not True
        or receipt.get("retraining_performed") is not False
        or receipt.get("overwrite_performed") is not False
        or receipt.get("move_performed") is not False
        or receipt.get("delete_performed") is not False
        or receipt.get("fresh_oos") != RECOVERY_FRESH_OOS
        or receipt.get("member_artifact_sha256") != expected_members
        or receipt.get("materializer_sha256") != sources.get("dataset_manifest")
        or receipt.get("outcome") != "NO_GO_ONLY"
    ):
        raise Type1ReportError("recovery receipt violates the append-only no-go contract")
    _require_sha(receipt.get("recovery_manifest_sha256"), "recovery manifest SHA")
    _require_sha(receipt.get("blocked_receipt_sha256"), "blocked receipt SHA")
    if not isinstance(receipt.get("member_artifact_sha256"), Mapping) or len(receipt["member_artifact_sha256"]) != 20:
        raise Type1ReportError("recovery receipt member artifact hashes are invalid")
    _validate_recovery_source_sha256(receipt.get("source_sha256"), sources, "recovery receipt")


def _validate_materializer_evidence(root: Path, sources: Mapping[str, Any]) -> None:
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
        maximum=_PUBLIC_ROWS_MAX_BYTES,
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


def _validate_runner_manifest_body(root: Path, manifest: Mapping[str, Any], sources: Mapping[str, Any], *, recovered: bool) -> None:
    pretraining = manifest.get("pretraining_gate")
    if not isinstance(pretraining, Mapping) or set(pretraining) != {
        "accounting", "block_semantics", "validation_noninterference",
    }:
        raise Type1ReportError("runner pretraining evidence is missing or malformed")
    accounting = pretraining.get("accounting")
    noninterference = pretraining.get("validation_noninterference")
    train_pairs_sha256 = noninterference.get("train_pairs_sha256") if isinstance(noninterference, Mapping) else None
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
    session_pairing = manifest.get("session_pairing")
    expected_validation_pairs_sha256 = None
    expected_normalizer_digest = None
    if recovered:
        if (
            not isinstance(session_pairing, Mapping)
            or set(session_pairing) != {"authority_bound", "trailing_embargo", "validation_pairs_sha256", "normalizer_digest"}
            or session_pairing.get("authority_bound") is not True
            or not isinstance(session_pairing.get("trailing_embargo"), list)
            or _SHA.fullmatch(str(session_pairing.get("validation_pairs_sha256", ""))) is None
            or _SHA.fullmatch(str(session_pairing.get("normalizer_digest", ""))) is None
            or session_pairing.get("validation_pairs_sha256") == train_pairs_sha256
        ):
            raise Type1ReportError("recovery session-pairing validation hash is invalid")
        expected_validation_pairs_sha256 = session_pairing["validation_pairs_sha256"]
        expected_normalizer_digest = session_pairing["normalizer_digest"]
    elif isinstance(session_pairing, Mapping) and _SHA.fullmatch(str(session_pairing.get("validation_pairs_sha256", ""))) is not None:
        expected_validation_pairs_sha256 = session_pairing["validation_pairs_sha256"]
    training = manifest.get("training")
    if recovered:
        expected_training = {
            "primary_seeds": [0, 1, 2, 3, 4],
            "shuffled_reward_seeds": [0, 1, 2, 3, 4],
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
            "retraining_performed": False,
        }
    else:
        expected_training = {
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
        }
    if not isinstance(training, Mapping) or training != expected_training:
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
            expected_member_keys = {
                "seed", "timesteps", "actual_sb3_timesteps", "device",
                "artifact", "artifacts", "reload_receipt", "validation",
            }
            if recovered:
                expected_member_keys.add("artifact_paths")
            if (
                not isinstance(member, Mapping)
                or set(member) != expected_member_keys
                or member.get("seed") != seed
                or member.get("timesteps") != 200000
                or member.get("actual_sb3_timesteps") != 200000
                or member.get("device") != "cpu"
                or member.get("artifact") != "FINAL_MODEL_ONLY"
            ):
                raise Type1ReportError("runner member step or device receipt is invalid")
            if recovered and member.get("artifact_paths") != {
                "model": f"{kind}/seed_{seed}/final_model.zip",
                "normalizer": f"{kind}/seed_{seed}/normalizer.json",
            }:
                raise Type1ReportError("runner member artifact paths are invalid")
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
                or (
                    expected_validation_pairs_sha256 is not None
                    and evidence.get("validation_pairs_sha256") != expected_validation_pairs_sha256
                )
                or (
                    expected_normalizer_digest is not None
                    and evidence.get("normalizer_digest") != expected_normalizer_digest
                )
                or _SHA.fullmatch(str(evidence.get("normalizer_digest", ""))) is None
                or _SHA.fullmatch(str(evidence.get("validation_pairs_sha256", ""))) is None
                or set(normalizer) != {"kind", "digest", "scales"}
                or normalizer.get("kind") != "market_type7_train_only"
                or normalizer.get("digest") != evidence.get("normalizer_digest")
                or rebuilt_digest != evidence.get("normalizer_digest")
                or not isinstance(normalizer.get("scales"), list)
            ):
                raise Type1ReportError("runner final artifact or persisted-normalizer replay receipt is invalid")


def _validate_completed_runner_evidence(root: Path, sources: Mapping[str, Any]) -> None:
    manifest = _read_completed_runner_manifest(root, sources.get("run_manifest"))
    _validate_materializer_evidence(root, sources)
    _validate_publication_receipt(root, sources)
    _validate_runner_manifest_body(root, manifest, sources, recovered=False)


def _validate_recovered_runner_evidence(root: Path, sources: Mapping[str, Any], authority_sessions: Mapping[str, Any] | None) -> None:
    _, blocked_receipt_sha256 = _read_original_block_receipt(root, sources.get("blocked_receipt"))
    manifest, recovery_manifest_sha256 = _read_recovery_manifest(root, sources, blocked_receipt_sha256, authority_sessions)
    _validate_materializer_evidence(root, sources)
    _validate_runner_manifest_body(root, manifest, sources, recovered=True)
    _validate_recovery_receipt(root, sources, recovery_manifest_sha256)
    _validate_publication_receipt(root, sources, authority_sessions)


def _validate_runner_evidence(
    run_dir: str | Path,
    sources: Mapping[str, Any],
    authority_sessions: Mapping[str, Any] | None = None,
) -> None:
    root = Path(run_dir).absolute()
    mode = _runner_evidence_mode(root)
    if mode == COMPLETED_RUN_EVIDENCE_MODE:
        _validate_completed_runner_evidence(root, sources)
    else:
        expected_authority_sessions = authority_sessions
        if expected_authority_sessions is None:
            authority, raw = _read_authority_source(_safe_child(root, _SOURCE_LOCAL_PATHS["authority"]), "authority source")
            if _sha(raw) != sources.get("authority"):
                raise Type1ReportError("authority source hash mismatch")
            expected_authority_sessions = _authority_payload(authority, "authority source")["sessions"]
        _validate_recovered_runner_evidence(root, sources, expected_authority_sessions)

def _uninitialized_report_source_sha256(directory: Path, authority_sha256: str) -> dict[str, str]:
    paths = _report_source_paths(directory)
    skipped = set(_AUTHORITY_ARTIFACT_LABELS)
    sources = {label: _sha(_read_report_source_bytes(path, label)) for label, path in paths.items() if label not in skipped}
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
    missing_prefix = False
    for label, path in targets.items():
        raw = artifacts[label]
        if not path.exists():
            missing_prefix = True
            continue
        if missing_prefix:
            raise Type1ReportError("report authority artifacts are not an exact prefix")
        if _read_bytes(path, f"existing report authority artifact: {label}", maximum=len(raw)) != raw:
            raise Type1ReportError("report authority artifact already exists with different bytes")
    return targets

def initialize_report_authority(run_dir: str | Path, frozen_authority_envelope_path: str | Path) -> dict[str, str]:
    """Explicitly bridge completed or append-only recovered Type1 runner evidence into immutable report sources."""
    directory = Path(run_dir).absolute()
    if not directory.is_dir() or _is_reparse(directory):
        raise Type1ReportError("run directory is required")
    manifest = _read_runner_manifest_for_authority(directory)
    _, authority, authority_raw = _read_frozen_authority_envelope(Path(frozen_authority_envelope_path).absolute())
    authority_sha256 = _sha(authority_raw)
    _validate_runner_authority_binding(manifest, authority, authority_sha256)
    sources = _uninitialized_report_source_sha256(directory, authority_sha256)
    _validate_runner_evidence(directory, sources, authority_sessions=authority["sessions"])
    artifacts = _report_authority_artifact_bytes(authority_raw, authority_sha256)
    _validate_pending_report_authority_sources(directory, artifacts)
    targets = _preflight_report_authority_targets(directory, artifacts)
    for label in _AUTHORITY_ARTIFACT_LABELS:
        _write_new(targets[label], artifacts[label])
    return report_source_sha256(directory)

def build_completed_report_revision(
    run_dir: str | Path,
    revision_id: str = "type1-r0001",
    revision_ordinal: int = 1,
) -> dict[str, Any]:
    """Build the immutable completed/no-go report revision from validated completed or recovered custody only."""
    if not isinstance(revision_id, str) or re.fullmatch(r"type1-r[0-9]{4,}", revision_id) is None:
        raise Type1ReportError("revision ID is invalid")
    if type(revision_ordinal) is not int or revision_ordinal < 1:
        raise Type1ReportError("revision ordinal is invalid")
    sources = report_source_sha256(run_dir)
    _validate_runner_evidence(run_dir, sources)
    try:
        evidence_labels = _report_evidence_labels_for_sources(sources)
        evidence = {label: sources[label] for label in evidence_labels}
    except KeyError as exc:
        raise Type1ReportError("replacement authority evidence is incomplete") from exc
    return {
        "schema_version": REVISION_SCHEMA,
        "revision_id": revision_id,
        "revision_ordinal": revision_ordinal,
        "identity": _canonical_copy(IDENTITY),
        "policy": _canonical_copy(POLICY),
        "result": _canonical_copy(REPORT_RESULT),
        "source_sha256": dict(sources),
        "evidence": evidence,
        "false_research_locks": _canonical_copy(LOCKS),
        "claims": _report_claims_for_sources(sources),
    }


def _validate_revision(value: Mapping[str, Any]) -> None:
    required = {"schema_version", "revision_id", "revision_ordinal", "identity", "policy", "result", "source_sha256", "evidence", "false_research_locks", "claims", "catalog_ordinal", "previous_event_sha256", "previous_revision_event_sha256"}
    if set(value) != required or value.get("schema_version") != REVISION_SCHEMA or value.get("identity") != IDENTITY or value.get("policy") != POLICY:
        raise Type1ReportError("revision does not match frozen replacement Type1 contract")
    if not isinstance(value.get("revision_id"), str) or not re.fullmatch(r"type1-r[0-9]{4,}", value["revision_id"]): raise Type1ReportError("revision ID is invalid")
    if type(value.get("revision_ordinal")) is not int or value["revision_ordinal"] < 1: raise Type1ReportError("revision ordinal is invalid")
    if value.get("result") != REPORT_RESULT:
        raise Type1ReportError("report completion must be derived from validated runner evidence")
    sources, evidence = value.get("source_sha256"), value.get("evidence")
    if not isinstance(sources, Mapping) or not isinstance(evidence, Mapping):
        raise Type1ReportError("replacement authority evidence is incomplete")
    required_evidence = set(_report_evidence_labels_for_sources(sources))
    expected_claims = _report_claims_for_sources(sources)
    if set(evidence) != required_evidence:
        raise Type1ReportError("replacement authority evidence is incomplete")
    for label, digest in sources.items():
        if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", label): raise Type1ReportError("source label is invalid")
        _require_sha(digest, "source SHA")
    for label in required_evidence:
        if evidence[label] != sources.get(label): raise Type1ReportError("authority evidence does not bind fixed source")
    if value.get("false_research_locks") != LOCKS or value.get("claims") != expected_claims:
        raise Type1ReportError("revision locks or claims are invalid")

def _render(revision: Mapping[str, Any], revision_sha: str) -> bytes:
    r = revision["result"]
    failures = "".join(f"<li>{html.escape(str(x))}</li>" for x in r["failures"]) or "<li>None recorded.</li>"
    hashes = "".join(
        f"<li><code>{html.escape(k)}</code>: <code>{html.escape(v)}</code></li>"
        for k, v in sorted(revision["source_sha256"].items())
    )
    claims = "".join(
        f"<li><code>{html.escape(k)}</code>: <code>{html.escape(str(v))}</code></li>"
        for k, v in sorted(revision["claims"].items())
    )
    locks = "".join(
        f"<li><code>{html.escape(k)}</code>: <code>{html.escape(str(v))}</code></li>"
        for k, v in sorted(revision["false_research_locks"].items())
    )
    observed = (
        f"<p>Observed completion — run: {html.escape(str(r['run_state']))}; "
        f"training: {html.escape(str(r['training_state']))}; "
        f"reused validation: {html.escape(str(r['reused_validation_state']))}.</p>"
    )
    recovery_disclosure = ""
    if revision["claims"].get("recovery_from_blocked_controls") is True:
        reason = html.escape(str(revision["claims"]["original_control_failure_reason"]))
        recovery_disclosure = (
            "<p><strong>Append-only recovery disclosure:</strong> "
            "<code>recovery_from_blocked_controls:true</code>; "
            f"mode <code>{RECOVERY_MODE}</code>; original receipt remains <code>BLOCK</code>; "
            "retraining_performed:false; Fresh OOS remains NOT_RUN/no-read; "
            f"original control failure reason: <code>{reason}</code>.</p>"
        )
    sections = (
        ("overview", "Overview", f"<p class=verdict>NO_GO</p>{observed}{recovery_disclosure}<p>Outcome boundary: NO_GO_ONLY.</p>"),
        (
            "identity",
            "Type1 identity and scope",
            "<p>Replacement Type1 research-only evidence; not official close, alpha, "
            "profitability, paper, broker, live, or funded evidence.</p>",
        ),
        (
            "protocol",
            "Protocol and accounting",
            "<p>Exact 15:20 close proxy and fixed-notional non-self-financing 23bp accounting.</p>",
        ),
        (
            "training",
            "Training plan and observed completion",
            "<p>Planned: five seeds × 200000 timesteps. No checkpoint, member, validation, "
            f"profitability, paper, broker, live, or funded selection is claimed.</p>{observed}{recovery_disclosure}",
        ),
        ("validation", "Reused-validation controls", "<p>Reused validation can yield NO_GO only.</p>"),
        (
            "custody",
            "Fresh OOS and custody",
            f"<p>Fresh OOS: {html.escape(str(r['fresh_oos_state']))}; payload was not read.</p>"
            f"{recovery_disclosure}<p>M3E: {M3E_STATEMENT}</p>",
        ),
        (
            "integrity",
            "Failures, claims, locks, and source integrity",
            f"<p>Revision SHA-256: <code>{revision_sha}</code></p>"
            f"<h3>Failures</h3><ul>{failures}</ul>"
            f"<h3>Claims</h3><ul>{claims}</ul>"
            f"<h3>False-research locks</h3><ul>{locks}</ul>"
            f"<h3>Source SHA-256</h3><ul>{hashes}</ul>",
        ),
    )
    links = "".join(
        f'<a role="tab" id="{key}-tab" href="#{key}" aria-controls="{key}">{html.escape(title)}</a>'
        for key, title, _ in sections
    )
    body = "".join(
        f'<section role="tabpanel" id="{key}" aria-labelledby="{key}-tab" tabindex="0">'
        f"<h2>{html.escape(title)}</h2>{content}</section>"
        for key, title, content in sections
    )
    text = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<title>Type1 immutable report</title><style>'
        'body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem;line-height:1.5}'
        'nav[role=tablist]{display:flex;gap:.7rem;flex-wrap:wrap;border-bottom:1px solid #cbd5e1}'
        'a[role=tab]{padding:.45rem .7rem;border:1px solid #cbd5e1;border-bottom:0;text-decoration:none;color:#0f172a;background:#f8fafc}'
        'section[role=tabpanel]{border-top:1px solid #cbd5e1;margin-top:1rem}'
        '.verdict{font-weight:bold;padding:.6rem;background:#7f1d1d;color:white}'
        'code{overflow-wrap:anywhere}'
        '@media(max-width:600px){body{margin:1rem}nav[role=tablist]{display:grid;grid-template-columns:1fr}}'
        '</style></head><body><h1>Type1 immutable reused-validation evidence</h1>'
        f'<nav role="tablist" aria-label="Report sections">{links}</nav><main>{body}</main></body></html>'
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

def _catalog_root_path(run_dir: str | Path) -> Path:
    directory = Path(run_dir).absolute()
    if not directory.is_dir() or _is_reparse(directory):
        raise Type1ReportError("run directory is required")
    return _safe_child(directory, Path(REPORT_ROOT))


def _require_exact_completed_report_inputs(
    run_dir: str | Path,
    frozen_authority_envelope_path: str | Path,
) -> tuple[Path, Path]:
    run_path = Path(run_dir).absolute()
    authority_path = Path(frozen_authority_envelope_path).absolute()
    if run_path != Path(COMPLETED_REPORT_RUN_DIR).absolute():
        raise Type1ReportError(f"run directory must be the exact published destination: {PUBLICATION_DESTINATION_LOGICAL_PATH}")
    if authority_path != Path(FROZEN_AUTHORITY_ENVELOPE_PATH).absolute():
        raise Type1ReportError("frozen authority envelope path must be the exact type1_authorities -004 envelope")
    return run_path, authority_path


def _assert_one_shot_committed_snapshot(snapshot: Mapping[str, Any]) -> None:
    revision = snapshot.get("revision")
    materialization = snapshot.get("materialization")
    if (
        snapshot.get("state") != "COMMITTED"
        or snapshot.get("event_count") != 2
        or not isinstance(revision, Mapping)
        or not isinstance(materialization, Mapping)
        or revision.get("revision_id") != "type1-r0001"
        or revision.get("revision_ordinal") != 1
        or materialization.get("object_id") != "type1-r0001"
    ):
        raise Type1ReportError("one-shot report catalog must contain exactly one committed type1-r0001 revision")


def _completed_report_receipt(run_dir: str | Path, snapshot: Mapping[str, Any], mode: str) -> dict[str, Any]:
    _assert_one_shot_committed_snapshot(snapshot)
    revision = snapshot["revision"]
    materialization = snapshot["materialization"]
    tip = snapshot["tip"]
    return {
        "report_status": "COMMITTED",
        "mode": mode,
        "verdict": revision["result"]["verdict"],
        "fresh_oos": {
            "state": revision["result"]["fresh_oos_state"],
            "read_performed": revision["result"]["fresh_oos_read_performed"],
        },
        "run_dir": str(Path(run_dir).absolute()),
        "revision_id": revision["revision_id"],
        "revision_ordinal": revision["revision_ordinal"],
        "catalog_event_count": snapshot["event_count"],
        "object_count": 1,
        "revision_event_sha256": tip["latest_revision_event_sha256"],
        "materialization_event_sha256": tip["materialization_event_sha256"],
        "tip_sha256": snapshot["tip_sha256"],
        "object_id": materialization["object_id"],
        "html_sha256": materialization["html_sha256"],
        "publication_receipt_sha256": revision["evidence"]["publication_receipt"],
        "run_evidence_mode": _source_evidence_mode(revision["source_sha256"]),
        "evidence": dict(revision["evidence"]),
        "source_count": len(revision["source_sha256"]),
    }


def _existing_completed_report_receipt(run_dir: str | Path) -> dict[str, Any] | None:
    root = _catalog_root_path(run_dir)
    if not root.exists():
        return None
    try:
        snapshot = verify_report_catalog(run_dir)
    except Type1ReportError as verify_exc:
        try:
            tip_exists = _safe_child(root, Path("committed_report_tip.json")).exists()
        except Type1ReportError:
            tip_exists = False
        if not tip_exists:
            raise Type1ReportError("existing report catalog is partial or invalid") from verify_exc
        try:
            reconcile_report_tip(run_dir)
            snapshot = verify_report_catalog(run_dir)
        except Type1ReportError as reconcile_exc:
            raise Type1ReportError("existing report catalog is not an exact committed-tip orphan") from reconcile_exc
        return _completed_report_receipt(run_dir, snapshot, "RECONCILED")
    if snapshot.get("state") != "COMMITTED":
        raise Type1ReportError("existing report catalog is partial; one-shot completion refuses to append")
    return _completed_report_receipt(run_dir, snapshot, "VERIFIED")


def complete_report_one_shot(
    run_dir: str | Path,
    frozen_authority_envelope_path: str | Path,
) -> dict[str, Any]:
    """Create or verify the sole immutable completed Type1 report catalog."""
    run_path, authority_path = _require_exact_completed_report_inputs(run_dir, frozen_authority_envelope_path)
    existing = _existing_completed_report_receipt(run_path)
    if existing is not None:
        return existing
    initialize_report_authority(run_path, authority_path)
    revision = build_completed_report_revision(run_path)
    inserted = insert_report_revision(run_path, revision)
    materialized = materialize_report_revision(run_path, inserted["event_sha256"])
    commit_report_tip(run_path, materialized["event_sha256"])
    snapshot = verify_report_catalog(run_path)
    return _completed_report_receipt(run_path, snapshot, "CREATED")


def _display_path(path: Path) -> str:
    try:
        return str(Path(path).relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def build_parser() -> argparse.ArgumentParser:
    run_display = _display_path(Path(COMPLETED_REPORT_RUN_DIR))
    authority_display = _display_path(Path(FROZEN_AUTHORITY_ENVELOPE_PATH))
    command = (
        "py -3.11 -m stom_rl.daily_v1_type1_report "
        f"--run-dir {run_display} "
        f"--frozen-authority-envelope {authority_display}"
    )
    parser = argparse.ArgumentParser(
        description="Build exactly one immutable completed Type1 report revision from frozen custody.",
        epilog=f"Documented production command:\n  {command}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help=f"Required exact published run directory: {_display_path(Path(COMPLETED_REPORT_RUN_DIR))}",
    )
    parser.add_argument(
        "--frozen-authority-envelope",
        required=True,
        type=Path,
        help=f"Required exact frozen -004 authority envelope: {_display_path(Path(FROZEN_AUTHORITY_ENVELOPE_PATH))}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = complete_report_one_shot(args.run_dir, args.frozen_authority_envelope)
    except Exception as exc:
        print(json.dumps({
            "report_status": "BLOCKED",
            "verdict": "NO_GO",
            "fresh_oos": {"state": "NOT_RUN", "read_performed": False},
            "error": str(exc),
        }, sort_keys=True))
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
