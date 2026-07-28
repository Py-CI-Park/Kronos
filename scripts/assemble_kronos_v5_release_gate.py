"""Assemble the signed Kronos V5 release-gate default artifact."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization


SCHEMA = "kronos_v5_release_gate.v1"
SIGNATURE_SCHEMA = "kronos_v5_release_gate_signature.v1"
EQUATION_SCHEMA = "kronos_v5_default_equation.v1"
STATE_SCHEMA = "kronos_v5_release_state.v1"
MODEL_STATE_SCHEMA = "kronos_v5_model_state.v1"
DOMAIN_SEPARATOR = "KRONOS-V5-RELEASE-GATE-V1"
PINNED_SCORECARD_SHA256 = "4afa3656e8bed8e5adae8bc3e99f89d5b450f8c56561429cb121aa601458ec7b"
DEFAULT_EQUATION = (
    "default_eligible = point_scores_byte_identical && score_total_min_90 && "
    "category_floors_passed && hard_caps_absent && six_locks_false && "
    "source_hash_current && dist_hash_current && head_matches_h_release && "
    "tree_matches_h_release && h_release_immutable && worktree_clean && "
    "live_browser_pass && security_pass && rollback_pass"
)

CATEGORY_CLAIMS: dict[str, tuple[str, ...]] = {
    "A": tuple(f"A{number:02d}" for number in range(1, 26)),
    "B": tuple(f"B{number:02d}" for number in range(1, 26)),
    "C": tuple(f"C{number:02d}" for number in range(1, 21)),
    "D": tuple(f"D{number:02d}" for number in range(1, 16)),
    "E": ("E01", "E02", "E3.R", *tuple(f"E{number:02d}" for number in range(4, 16))),
}
CATEGORY_FLOORS = {"A": 23, "B": 23, "C": 18, "D": 13, "E": 13}
CATEGORY_MAX = {"A": 25, "B": 25, "C": 20, "D": 15, "E": 15}
CLAIM_IDS = tuple(claim_id for ids in CATEGORY_CLAIMS.values() for claim_id in ids)
ALLOWED_CAPS = ("fresh_oos_misrepresentation", "unapproved_contract_or_api_change")
SIX_LOCKS = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}
OPERAND_ORDER = (
    "point_scores_byte_identical",
    "score_total_min_90",
    "category_floors_passed",
    "hard_caps_absent",
    "six_locks_false",
    "source_hash_current",
    "dist_hash_current",
    "head_matches_h_release",
    "tree_matches_h_release",
    "h_release_immutable",
    "worktree_clean",
    "live_browser_pass",
    "security_pass",
    "rollback_pass",
)
BLOCKER_ORDER = (
    "SCORE_REPLAY_NOT_BYTE_IDENTICAL",
    "SCORE_TOTAL_BELOW_90",
    "CATEGORY_FLOOR_FAILURE",
    "ACTIVE_HARD_CAP",
    "SIX_LOCKS_NOT_FALSE",
    "SOURCE_HASH_MISMATCH",
    "DIST_HASH_MISMATCH",
    "HEAD_DRIFT",
    "TREE_DRIFT",
    "H_RELEASE_NOT_IMMUTABLE",
    "DIRTY_WORKTREE",
    "BROWSER_RECEIPT_MISSING",
    "BROWSER_SYNTHETIC_SUBSTITUTION",
    "BROWSER_RECEIPT_NOT_PASS",
    "SECURITY_RECEIPT_MISSING",
    "SECURITY_NOT_PASS",
    "ROLLBACK_RECEIPT_MISSING",
    "ROLLBACK_NOT_PASS",
)
NON_OPERAND_FIELDS = ("model_verdict", "d0", "d1", "oos")
DEFAULT_NON_OPERANDS = {field: "NOT_RUN" for field in NON_OPERAND_FIELDS}

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HEX40_OR_64 = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_B64URL = re.compile(r"^[A-Za-z0-9_-]+$")


class ReleaseGateError(ValueError):
    """Raised when the release gate cannot be assembled or validated closed."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return rfc8785.dumps(value)
    except Exception as exc:  # pragma: no cover - rfc8785 exception types vary by version.
        raise ReleaseGateError("value is outside the pinned RFC8785/JCS profile") from exc


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str, *, length: int, label: str) -> bytes:
    if not isinstance(value, str) or not _B64URL.fullmatch(value):
        raise ReleaseGateError(f"{label} is not canonical base64url")
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as exc:
        raise ReleaseGateError(f"{label} is not canonical base64url") from exc
    if len(raw) != length or _b64encode(raw) != value:
        raise ReleaseGateError(f"{label} length or encoding is invalid")
    return raw


def _duplicate_free_json(raw: bytes, label: str) -> Any:
    if not isinstance(raw, bytes) or raw.startswith(b"\xef\xbb\xbf"):
        raise ReleaseGateError(f"{label} must be UTF-8 JSON bytes without a BOM")

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReleaseGateError(f"{label} has a duplicate JSON member")
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except ReleaseGateError:
        raise
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ReleaseGateError(f"{label} is not strict JSON") from exc


def _load_json(path: Path, label: str) -> tuple[bytes, Mapping[str, Any]]:
    raw = path.read_bytes()
    value = _duplicate_free_json(raw, label)
    if not isinstance(value, Mapping):
        raise ReleaseGateError(f"{label} must be a JSON object")
    return raw, value


def _file_ref(path: Path, schema: str, raw: bytes | None = None) -> dict[str, Any]:
    data = path.read_bytes() if raw is None else raw
    return {"path": path.as_posix(), "sha256": _sha(data), "byte_length": len(data), "schema": schema}


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ReleaseGateError(f"{label} must be a lowercase SHA-256")
    return value


def _require_hex40_or_64(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _HEX40_OR_64.fullmatch(value):
        raise ReleaseGateError(f"{label} must be a lowercase 40- or 64-hex identity")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ReleaseGateError(f"{label} must be boolean")
    return value


def _require_utc(value: str) -> str:
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        raise ReleaseGateError("assembled_at must be canonical UTC seconds")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as exc:
        raise ReleaseGateError("assembled_at must be a real UTC timestamp") from exc
    return value


def _locks_shape(value: Any) -> Mapping[str, bool]:
    if not isinstance(value, Mapping) or set(value) != set(SIX_LOCKS) or any(not isinstance(item, bool) for item in value.values()):
        raise ReleaseGateError("six_locks_false must be the closed six-lock boolean map")
    return value  # type: ignore[return-value]


def _category_map(value: Any, label: str) -> Mapping[str, int]:
    if not isinstance(value, Mapping) or set(value) != set(CATEGORY_CLAIMS):
        raise ReleaseGateError(f"{label} must contain the five V5 categories")
    for category, maximum in CATEGORY_MAX.items():
        item = value[category]
        if not isinstance(item, int) or isinstance(item, bool) or item < 0 or item > maximum:
            raise ReleaseGateError(f"{label}.{category} is outside category bounds")
    return value  # type: ignore[return-value]


def _ordered_caps(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) != len(set(value)) or any(item not in ALLOWED_CAPS for item in value):
        raise ReleaseGateError("active_hard_caps must be a closed hard-cap list")
    expected = [cap for cap in ALLOWED_CAPS if cap in value]
    if value != expected:
        raise ReleaseGateError("active_hard_caps must be canonical ordered")
    return value


def _ordered_floors(value: Any, category_scores: Mapping[str, int]) -> list[str]:
    if not isinstance(value, list) or len(value) != len(set(value)) or any(item not in CATEGORY_FLOORS for item in value):
        raise ReleaseGateError("floor_failures must be a closed category list")
    expected = [category for category, floor in CATEGORY_FLOORS.items() if category_scores[category] < floor]
    if value != expected:
        raise ReleaseGateError("floor_failures do not match category floors")
    return value


def _load_point_score(path: Path, label: str) -> tuple[bytes, Mapping[str, Any], dict[str, Any]]:
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise ReleaseGateError(f"{label} must be canonical point-score bytes with one LF terminator")
    body = raw[:-1]
    parsed = _duplicate_free_json(body, label)
    if not isinstance(parsed, Mapping) or canonical_bytes(parsed) != body:
        raise ReleaseGateError(f"{label} must be raw canonical RFC8785 bytes plus LF")
    score = parsed
    required = {
        "schema",
        "candidate_map_sha256",
        "candidate_source_sha256",
        "scorecard_sha256",
        "category_scores",
        "capability_option_ceilings",
        "claim_results",
        "floor_failures",
        "active_hard_caps",
        "raw_total",
        "effective_total",
        "gate",
        "six_locks_false",
    }
    if set(score) != required or score["schema"] != "kronos_point_score.v2":
        raise ReleaseGateError(f"{label} has the wrong point-score shape")
    _require_sha(score["candidate_map_sha256"], "candidate_map_sha256")
    _require_sha(score["candidate_source_sha256"], "candidate_source_sha256")
    if score["scorecard_sha256"] != PINNED_SCORECARD_SHA256:
        raise ReleaseGateError("scorecard_sha256 is not the pinned V5 scorecard")
    claims = score["claim_results"]
    if not isinstance(claims, Mapping) or set(claims) != set(CLAIM_IDS) or any(not isinstance(value, bool) for value in claims.values()):
        raise ReleaseGateError("claim_results must be the exact 100 V5 booleans")
    category_scores = _category_map(score["category_scores"], "category_scores")
    expected_scores = {category: sum(claims[claim_id] is True for claim_id in ids) for category, ids in CATEGORY_CLAIMS.items()}
    if dict(category_scores) != expected_scores:
        raise ReleaseGateError("category_scores do not match claim_results")
    ceilings = _category_map(score["capability_option_ceilings"], "capability_option_ceilings")
    if dict(ceilings) != expected_scores:
        raise ReleaseGateError("capability_option_ceilings do not match PASS claims")
    floors = _ordered_floors(score["floor_failures"], category_scores)
    caps = _ordered_caps(score["active_hard_caps"])
    raw_total = score["raw_total"]
    effective_total = score["effective_total"]
    if not isinstance(raw_total, int) or isinstance(raw_total, bool) or raw_total != sum(expected_scores.values()):
        raise ReleaseGateError("raw_total does not match category scores")
    expected_effective = min(raw_total, 89) if caps else raw_total
    if not isinstance(effective_total, int) or isinstance(effective_total, bool) or effective_total != expected_effective:
        raise ReleaseGateError("effective_total does not match hard-cap equation")
    expected_gate = {"id": "engineering_90", "passed": effective_total >= 90 and not floors and not caps, "total_min": 90}
    if score["gate"] != expected_gate:
        raise ReleaseGateError("engineering_90 gate equation is invalid")
    locks = _locks_shape(score["six_locks_false"])
    summary = {
        "candidate_map_sha256": score["candidate_map_sha256"],
        "candidate_source_sha256": score["candidate_source_sha256"],
        "scorecard_sha256": score["scorecard_sha256"],
        "category_scores": dict(category_scores),
        "capability_option_ceilings": dict(ceilings),
        "category_floors": dict(CATEGORY_FLOORS),
        "floor_failures": list(floors),
        "active_hard_caps": list(caps),
        "raw_total": raw_total,
        "effective_total": effective_total,
        "gate": expected_gate,
        "six_locks_false": dict(locks),
    }
    return raw, score, summary


def _load_state(path: Path) -> tuple[Mapping[str, Any], set[str]]:
    _, state = _load_json(path, "release state")
    required = {
        "schema",
        "h_release",
        "h_release_tree",
        "current_head",
        "current_tree",
        "h_release_immutable",
        "worktree_clean",
        "current_source_sha256",
        "expected_dist_manifest_sha256",
        "current_dist_manifest_sha256",
    }
    if not isinstance(state, Mapping) or state.get("schema") != STATE_SCHEMA or set(state) - required:
        raise ReleaseGateError("release state must be the closed kronos_v5_release_state.v1 object")
    missing = required - set(state)
    normalized = dict(state)
    missing_hash = "0" * 64
    for field in ("h_release", "h_release_tree", "current_head", "current_tree"):
        if field in missing:
            normalized[field] = missing_hash
        else:
            _require_hex40_or_64(normalized[field], field)
    for field in ("h_release_immutable", "worktree_clean"):
        if field in missing:
            normalized[field] = False
        else:
            _require_bool(normalized[field], field)
    for field in ("current_source_sha256", "expected_dist_manifest_sha256", "current_dist_manifest_sha256"):
        if field in missing:
            normalized[field] = missing_hash
        else:
            _require_sha(normalized[field], field)
    return normalized, missing


def _status(value: Any) -> str:
    return "PASS" if value == "PASS" else "FAIL"


def _maybe_sha(value: Mapping[str, Any] | None, key: str) -> str | None:
    if value is None:
        return None
    item = value.get(key)
    return item if isinstance(item, str) and _SHA256.fullmatch(item) else None


def _receipt(path: Path | None, label: str, default_schema: str) -> tuple[Mapping[str, Any] | None, dict[str, Any] | None]:
    if path is None:
        return None, None
    raw, value = _load_json(path, label)
    schema = value.get("schema") if isinstance(value.get("schema"), str) and value.get("schema") else default_schema
    return value, _file_ref(path, schema, raw)


def _browser_summary(path: Path | None) -> dict[str, Any]:
    receipt, ref = _receipt(path, "browser receipt", "kronos_v5_live_browser_receipt.v1")
    if receipt is None:
        return {
            "receipt_ref": None,
            "status": "MISSING",
            "capture_kind": None,
            "live_browser_execution": None,
            "synthetic_evidence": False,
            "source_sha256": None,
            "dist_manifest_sha256": None,
        }
    capture_kind = receipt.get("capture_kind") if isinstance(receipt.get("capture_kind"), str) else None
    live = receipt.get("live_browser_execution")
    synthetic = (
        capture_kind != "live_browser_execution"
        or live is not True
        or receipt.get("synthetic_evidence") is True
        or capture_kind == "synthetic_fixture_evidence"
    )
    return {
        "receipt_ref": ref,
        "status": _status(receipt.get("status")),
        "capture_kind": capture_kind,
        "live_browser_execution": live if isinstance(live, bool) else None,
        "synthetic_evidence": bool(synthetic),
        "source_sha256": _maybe_sha(receipt, "source_sha256"),
        "dist_manifest_sha256": _maybe_sha(receipt, "dist_manifest_sha256"),
    }


def _platform_summary(path: Path | None, label: str, default_schema: str) -> dict[str, Any]:
    receipt, ref = _receipt(path, label, default_schema)
    if receipt is None:
        return {"receipt_ref": None, "status": "MISSING", "source_sha256": None, "dist_manifest_sha256": None}
    return {
        "receipt_ref": ref,
        "status": _status(receipt.get("status")),
        "source_sha256": _maybe_sha(receipt, "source_sha256"),
        "dist_manifest_sha256": _maybe_sha(receipt, "dist_manifest_sha256"),
    }


def _load_non_operands(path: Path | None) -> dict[str, str]:
    if path is None:
        return dict(DEFAULT_NON_OPERANDS)
    _, value = _load_json(path, "model state")
    if value.get("schema") != MODEL_STATE_SCHEMA:
        raise ReleaseGateError("model state must be kronos_v5_model_state.v1")
    result: dict[str, str] = {}
    for field in NON_OPERAND_FIELDS:
        item = value.get(field)
        if not isinstance(item, str) or not item:
            raise ReleaseGateError(f"model state {field} must be a non-empty string")
        result[field] = item
    return result


def _platform_hashes_match(platforms: list[dict[str, Any]], key: str, current: str) -> bool:
    for platform in platforms:
        if platform["receipt_ref"] is not None and platform[key] != current:
            return False
    return True


def _ordered_blockers(codes: set[str]) -> list[str]:
    return [code for code in BLOCKER_ORDER if code in codes]


def _blockers_from_gate(gate: Mapping[str, Any]) -> list[str]:
    operands = gate["default_equation"]["operands"]
    browser = gate["platform_assurance"]["browser"]
    security = gate["platform_assurance"]["security"]
    rollback = gate["platform_assurance"]["rollback"]
    codes: set[str] = set()
    if not operands["point_scores_byte_identical"]:
        codes.add("SCORE_REPLAY_NOT_BYTE_IDENTICAL")
    if not operands["score_total_min_90"]:
        codes.add("SCORE_TOTAL_BELOW_90")
    if not operands["category_floors_passed"]:
        codes.add("CATEGORY_FLOOR_FAILURE")
    if not operands["hard_caps_absent"]:
        codes.add("ACTIVE_HARD_CAP")
    if not operands["six_locks_false"]:
        codes.add("SIX_LOCKS_NOT_FALSE")
    if not operands["source_hash_current"]:
        codes.add("SOURCE_HASH_MISMATCH")
    if not operands["dist_hash_current"]:
        codes.add("DIST_HASH_MISMATCH")
    if not operands["head_matches_h_release"]:
        codes.add("HEAD_DRIFT")
    if not operands["tree_matches_h_release"]:
        codes.add("TREE_DRIFT")
    if not operands["h_release_immutable"]:
        codes.add("H_RELEASE_NOT_IMMUTABLE")
    if not operands["worktree_clean"]:
        codes.add("DIRTY_WORKTREE")
    if not operands["live_browser_pass"]:
        if browser["receipt_ref"] is None:
            codes.add("BROWSER_RECEIPT_MISSING")
        elif browser["synthetic_evidence"] is True or browser["capture_kind"] != "live_browser_execution" or browser["live_browser_execution"] is not True:
            codes.add("BROWSER_SYNTHETIC_SUBSTITUTION")
        else:
            codes.add("BROWSER_RECEIPT_NOT_PASS")
    if not operands["security_pass"]:
        codes.add("SECURITY_RECEIPT_MISSING" if security["receipt_ref"] is None else "SECURITY_NOT_PASS")
    if not operands["rollback_pass"]:
        codes.add("ROLLBACK_RECEIPT_MISSING" if rollback["receipt_ref"] is None else "ROLLBACK_NOT_PASS")
    return _ordered_blockers(codes)


def _sign(unsigned: Mapping[str, Any], signing_key_seed: bytes) -> tuple[str, dict[str, Any]]:
    if not isinstance(signing_key_seed, bytes) or len(signing_key_seed) != 32:
        raise ReleaseGateError("Ed25519 signing key seed must be exactly 32 bytes")
    raw = canonical_bytes(unsigned)
    payload_sha256 = _sha(raw)
    private_key = Ed25519PrivateKey.from_private_bytes(signing_key_seed)
    signature = private_key.sign(DOMAIN_SEPARATOR.encode("ascii") + b"\0" + raw)
    public_key = private_key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    return payload_sha256, {
        "schema": SIGNATURE_SCHEMA,
        "algorithm": "Ed25519",
        "domain_separator": DOMAIN_SEPARATOR,
        "payload_sha256": payload_sha256,
        "public_key": _b64encode(public_key),
        "signature": _b64encode(signature),
    }


def assemble_release_gate(
    *,
    score_a_path: Path,
    score_b_path: Path,
    state_path: Path,
    browser_receipt_path: Path | None = None,
    security_receipt_path: Path | None = None,
    rollback_receipt_path: Path | None = None,
    model_state_path: Path | None = None,
    assembled_at: str,
    signing_key_seed: bytes,
) -> dict[str, Any]:
    assembled_at = _require_utc(assembled_at)
    score_a_raw, _, score_summary = _load_point_score(score_a_path, "point score A")
    score_b_raw, _, _ = _load_point_score(score_b_path, "point score B")
    state, missing_state = _load_state(state_path)
    browser = _browser_summary(browser_receipt_path)
    security = _platform_summary(security_receipt_path, "security receipt", "kronos_v5_security_receipt.v1")
    rollback = _platform_summary(rollback_receipt_path, "rollback receipt", "kronos_v5_rollback_receipt.v1")
    non_operands = _load_non_operands(model_state_path)
    platforms = [browser, security, rollback]

    point_scores_byte_identical = score_a_raw == score_b_raw
    score_total_min_90 = score_summary["effective_total"] >= 90
    category_floors_passed = score_summary["floor_failures"] == [] and all(
        score_summary["category_scores"][category] >= floor for category, floor in CATEGORY_FLOORS.items()
    )
    hard_caps_absent = score_summary["active_hard_caps"] == []
    six_locks_false = score_summary["six_locks_false"] == SIX_LOCKS
    source_hash_current = (
        "current_source_sha256" not in missing_state
        and score_summary["candidate_source_sha256"] == state["current_source_sha256"]
        and _platform_hashes_match(platforms, "source_sha256", state["current_source_sha256"])
    )
    dist_hash_current = (
        "expected_dist_manifest_sha256" not in missing_state
        and "current_dist_manifest_sha256" not in missing_state
        and state["expected_dist_manifest_sha256"] == state["current_dist_manifest_sha256"]
        and _platform_hashes_match(platforms, "dist_manifest_sha256", state["current_dist_manifest_sha256"])
    )
    head_matches_h_release = (
        "h_release" not in missing_state
        and "current_head" not in missing_state
        and state["current_head"] == state["h_release"]
    )
    tree_matches_h_release = (
        "h_release_tree" not in missing_state
        and "current_tree" not in missing_state
        and state["current_tree"] == state["h_release_tree"]
    )
    h_release_immutable = "h_release_immutable" not in missing_state and state["h_release_immutable"] is True
    worktree_clean = "worktree_clean" not in missing_state and state["worktree_clean"] is True
    live_browser_pass = (
        browser["receipt_ref"] is not None
        and browser["status"] == "PASS"
        and browser["capture_kind"] == "live_browser_execution"
        and browser["live_browser_execution"] is True
        and browser["synthetic_evidence"] is False
    )
    security_pass = security["receipt_ref"] is not None and security["status"] == "PASS"
    rollback_pass = rollback["receipt_ref"] is not None and rollback["status"] == "PASS"
    operands = {
        "point_scores_byte_identical": point_scores_byte_identical,
        "score_total_min_90": score_total_min_90,
        "category_floors_passed": category_floors_passed,
        "hard_caps_absent": hard_caps_absent,
        "six_locks_false": six_locks_false,
        "source_hash_current": source_hash_current,
        "dist_hash_current": dist_hash_current,
        "head_matches_h_release": head_matches_h_release,
        "tree_matches_h_release": tree_matches_h_release,
        "h_release_immutable": h_release_immutable,
        "worktree_clean": worktree_clean,
        "live_browser_pass": live_browser_pass,
        "security_pass": security_pass,
        "rollback_pass": rollback_pass,
    }
    if tuple(operands) != OPERAND_ORDER:
        raise AssertionError("operand order drifted")

    score_replay = {
        "score_a_ref": _file_ref(score_a_path, "kronos_point_score.v2", score_a_raw),
        "score_b_ref": _file_ref(score_b_path, "kronos_point_score.v2", score_b_raw),
        "byte_identical": point_scores_byte_identical,
    }
    source_dist_state = {
        "candidate_source_sha256": score_summary["candidate_source_sha256"],
        "current_source_sha256": state["current_source_sha256"],
        "source_hash_current": source_hash_current,
        "expected_dist_manifest_sha256": state["expected_dist_manifest_sha256"],
        "current_dist_manifest_sha256": state["current_dist_manifest_sha256"],
        "dist_hash_current": dist_hash_current,
    }
    head_state = {
        "h_release": state["h_release"],
        "current_head": state["current_head"],
        "head_matches_h_release": head_matches_h_release,
        "h_release_tree": state["h_release_tree"],
        "current_tree": state["current_tree"],
        "tree_matches_h_release": tree_matches_h_release,
        "h_release_immutable": h_release_immutable,
        "worktree_clean": worktree_clean,
    }
    default_equation = {
        "schema": EQUATION_SCHEMA,
        "expression": DEFAULT_EQUATION,
        "operands": operands,
        "non_operand_fields": list(NON_OPERAND_FIELDS),
    }
    blockers = _blockers_from_gate(
        {
            "default_equation": default_equation,
            "platform_assurance": {"browser": browser, "security": security, "rollback": rollback},
        }
    )
    default_eligible = blockers == [] and all(operands.values())
    unsigned = {
        "schema": SCHEMA,
        "assembled_at": assembled_at,
        "score_replay": score_replay,
        "score_gate": score_summary,
        "source_dist_state": source_dist_state,
        "head_state": head_state,
        "platform_assurance": {"browser": browser, "security": security, "rollback": rollback},
        "non_operands": non_operands,
        "default_equation": {**default_equation, "result": default_eligible},
        "six_locks_false": dict(SIX_LOCKS),
        "release_eligible": default_eligible,
        "default_eligible": default_eligible,
        "blockers": blockers,
    }
    payload_sha256, signature = _sign(unsigned, signing_key_seed)
    result = {**unsigned, "release_gate_sha256": payload_sha256, "signature": signature}
    validate_release_gate(result)
    return result


def validate_release_gate(value: Mapping[str, Any]) -> None:
    required = {
        "schema",
        "assembled_at",
        "score_replay",
        "score_gate",
        "source_dist_state",
        "head_state",
        "platform_assurance",
        "non_operands",
        "default_equation",
        "six_locks_false",
        "release_eligible",
        "default_eligible",
        "blockers",
        "release_gate_sha256",
        "signature",
    }
    if not isinstance(value, Mapping) or set(value) != required or value["schema"] != SCHEMA:
        raise ReleaseGateError("release gate has the wrong closed shape")
    unsigned = {key: value[key] for key in value if key not in {"release_gate_sha256", "signature"}}
    unsigned_raw = canonical_bytes(unsigned)
    if value["release_gate_sha256"] != _sha(unsigned_raw):
        raise ReleaseGateError("release_gate_sha256 does not bind the unsigned payload")
    signature = value["signature"]
    if not isinstance(signature, Mapping) or set(signature) != {"schema", "algorithm", "domain_separator", "payload_sha256", "public_key", "signature"}:
        raise ReleaseGateError("release gate signature has the wrong shape")
    if signature["schema"] != SIGNATURE_SCHEMA or signature["algorithm"] != "Ed25519" or signature["domain_separator"] != DOMAIN_SEPARATOR or signature["payload_sha256"] != value["release_gate_sha256"]:
        raise ReleaseGateError("release gate signature metadata is invalid")
    public_key = _b64decode(signature["public_key"], length=32, label="signature.public_key")
    signed = _b64decode(signature["signature"], length=64, label="signature.signature")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signed, DOMAIN_SEPARATOR.encode("ascii") + b"\0" + unsigned_raw)
    except InvalidSignature as exc:
        raise ReleaseGateError("release gate signature is invalid") from exc
    equation = value["default_equation"]
    if not isinstance(equation, Mapping) or equation.get("schema") != EQUATION_SCHEMA or equation.get("expression") != DEFAULT_EQUATION or equation.get("non_operand_fields") != list(NON_OPERAND_FIELDS):
        raise ReleaseGateError("default equation metadata drifted")
    operands = equation.get("operands")
    if not isinstance(operands, Mapping) or tuple(operands) != OPERAND_ORDER or any(not isinstance(operands[name], bool) for name in OPERAND_ORDER):
        raise ReleaseGateError("default equation operands are invalid")
    expected_blockers = _blockers_from_gate(value)
    default_eligible = all(operands.values()) and expected_blockers == []
    if value["blockers"] != expected_blockers or value["default_eligible"] is not default_eligible or value["release_eligible"] is not default_eligible or equation.get("result") is not default_eligible:
        raise ReleaseGateError("default equation result or blockers are invalid")
    if value["six_locks_false"] != SIX_LOCKS:
        raise ReleaseGateError("six-lock invariant drifted")


def _load_key_seed(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8").strip()
    if re.fullmatch(r"[0-9a-fA-F]{64}", text):
        seed = bytes.fromhex(text)
    else:
        seed = _b64decode(text, length=32, label="signing key")
    if len(seed) != 32:
        raise ReleaseGateError("signing key must decode to 32 bytes")
    return seed


def _write_atomically(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(raw)
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble a signed Kronos V5 release-gate artifact.")
    parser.add_argument("--score-a", required=True, type=Path)
    parser.add_argument("--score-b", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--browser-receipt", type=Path)
    parser.add_argument("--security-receipt", type=Path)
    parser.add_argument("--rollback-receipt", type=Path)
    parser.add_argument("--model-state", type=Path)
    parser.add_argument("--assembled-at", required=True)
    parser.add_argument("--signing-key", required=True, type=Path, help="Path containing a 32-byte Ed25519 seed as hex or base64url-no-pad.")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        gate = assemble_release_gate(
            score_a_path=args.score_a,
            score_b_path=args.score_b,
            state_path=args.state,
            browser_receipt_path=args.browser_receipt,
            security_receipt_path=args.security_receipt,
            rollback_receipt_path=args.rollback_receipt,
            model_state_path=args.model_state,
            assembled_at=args.assembled_at,
            signing_key_seed=_load_key_seed(args.signing_key),
        )
        _write_atomically(args.out, canonical_bytes(gate) + b"\n")
    except ReleaseGateError as exc:
        sys.stderr.write(f"release gate failed closed: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
