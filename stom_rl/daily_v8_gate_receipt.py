"""M3E validation-only independent gate receipts.

This module accepts already-frozen bytes only.  It never opens a dataset or test
artifact; the receipt contains digests and non-sensitive gate metadata only.
"""
from __future__ import annotations

import base64
import hashlib
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Final

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from stom_rl.v5_oos_custody import canonical_bytes, parse_canonical_json

DOMAIN: Final = b"KRONOS-M3E-INDEPENDENT-GATE-RECEIPT-V1\x00"
RECEIPT_SCHEMA: Final = "kronos_m3e_independent_gate_receipt.v1"
STATEMENT_SCHEMA: Final = "kronos_m3e_independent_gate_statement.v1"
ELIGIBLE_TOKEN: Final = "OOS_OPEN_ELIGIBLE_REUSED_VALIDATION_SCREEN"
_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_PRINCIPAL_RE: Final = re.compile(r"agent://[^/\s]+\Z")
_KEY_ID_RE: Final = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")
_UTC_RE: Final = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_B64U_RE: Final = re.compile(r"[A-Za-z0-9_-]+\Z")


class GateReceiptError(ValueError):
    """Raised when an M3E receipt or its validation evidence is unacceptable."""


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
def evidence_commitments(manifest: Mapping[str, Any], member_artifact_hashes: Sequence[str]) -> dict[str, str]:
    """Hash the exact result, baseline, and control evidence bound by a receipt."""
    members = list(_member_hashes(member_artifact_hashes))
    result = {
        "ensemble": manifest.get("ensemble"),
        "jackknives": manifest.get("jackknives"),
        "verdict": manifest.get("verdict"),
        "member_hashes": members,
    }
    baseline = {
        "baselines": manifest.get("baselines"),
        "exposure_matched_random": manifest.get("exposure_matched_random"),
    }
    controls = {"shuffled_label_ensemble": manifest.get("shuffled_label_ensemble")}
    return {
        "result_sha256": sha256_hex(canonical_bytes(result)),
        "baseline_sha256": sha256_hex(canonical_bytes(baseline)),
        "control_sha256": sha256_hex(canonical_bytes(controls)),
    }



def issue_gate_receipt(
    frozen_prereg_bytes: bytes,
    validation_manifest_bytes: bytes,
    member_artifact_hashes: Sequence[str],
    *,
    custody_uid: str,
    test_sha256: str,
    gate_principal_uri: str,
    gate_key_id: str,
    signing_key: Ed25519PrivateKey | bytes,
    issued_at: datetime | str,
    expires_at: datetime | str,
) -> bytes:
    """Validate frozen validation evidence and issue a domain-separated receipt."""
    prereg = _canonical_object(frozen_prereg_bytes, "frozen preregistration")
    manifest = _canonical_object(validation_manifest_bytes, "validation manifest")
    members = _member_hashes(member_artifact_hashes)
    _validate_prereg(prereg)
    _validate_manifest(manifest, members)
    _assert_independent_gate(manifest, gate_principal_uri)
    _uid(custody_uid)
    _sha(test_sha256, "test SHA-256")
    _principal(gate_principal_uri, "gate principal")
    _key_id(gate_key_id)
    issued = _coerce_utc(issued_at, "issued_at")
    expires = _coerce_utc(expires_at, "expires_at")
    if expires <= issued:
        raise GateReceiptError("receipt expiry must be after issuance")
    statement = {
        "schema": STATEMENT_SCHEMA,
        "prereg_sha256": sha256_hex(frozen_prereg_bytes),
        "validation_manifest_sha256": sha256_hex(validation_manifest_bytes),
        "trainer_sha256": manifest["artifact_commitments"]["trainer_sha256"],
        "protocol_sha256": manifest["artifact_commitments"]["protocol_sha256"],
        "public_artifact_sha256": manifest["artifact_commitments"]["public_artifact_sha256"],
        "member_artifact_sha256": members,
        "result_sha256": manifest["artifact_commitments"]["result_sha256"],
        "baseline_sha256": manifest["artifact_commitments"]["baseline_sha256"],
        "control_sha256": manifest["artifact_commitments"]["control_sha256"],
        "custody_uid": custody_uid,
        "test_sha256": test_sha256,
        "eligibility": ELIGIBLE_TOKEN,
        "issued_at": _timestamp(issued),
        "expires_at": _timestamp(expires),
        "gate_principal_uri": gate_principal_uri,
        "gate_key_id": gate_key_id,
    }
    key = _private_key(signing_key)
    signature = _b64u(key.sign(DOMAIN + canonical_bytes(statement)))
    return canonical_bytes({"schema": RECEIPT_SCHEMA, "statement": statement, "signature": signature})


def verify_gate_receipt(
    receipt_bytes: bytes,
    frozen_prereg_bytes: bytes,
    validation_manifest_bytes: bytes,
    member_artifact_hashes: Sequence[str],
    *,
    custody_uid: str,
    test_sha256: str,
    gate_public_key: bytes | Ed25519PublicKey,
    now: datetime | str,
    expected_gate_principal_uri: str | None = None,
    expected_gate_key_id: str | None = None,
) -> dict[str, Any]:
    """Verify a receipt against the exact frozen bytes and independent evidence."""
    envelope = _canonical_object(receipt_bytes, "gate receipt")
    _shape(envelope, {"schema", "statement", "signature"}, "gate receipt")
    if envelope["schema"] != RECEIPT_SCHEMA:
        raise GateReceiptError("unsupported receipt schema")
    statement = envelope["statement"]
    _shape(statement, {
        "schema", "prereg_sha256", "validation_manifest_sha256", "trainer_sha256", "protocol_sha256",
        "public_artifact_sha256", "member_artifact_sha256", "result_sha256", "baseline_sha256",
        "control_sha256", "custody_uid", "test_sha256", "eligibility", "issued_at", "expires_at",
        "gate_principal_uri", "gate_key_id",
    }, "receipt statement")
    if statement["schema"] != STATEMENT_SCHEMA or statement["eligibility"] != ELIGIBLE_TOKEN:
        raise GateReceiptError("receipt has an invalid eligibility statement")
    members = _member_hashes(member_artifact_hashes)
    for field in ("prereg_sha256", "validation_manifest_sha256", "trainer_sha256", "protocol_sha256",
                  "public_artifact_sha256", "result_sha256", "baseline_sha256", "control_sha256", "test_sha256"):
        _sha(statement[field], field)
    _member_hashes(statement["member_artifact_sha256"])
    _uid(statement["custody_uid"])
    _principal(statement["gate_principal_uri"], "gate principal")
    _key_id(statement["gate_key_id"])
    issued, expires = _utc(statement["issued_at"], "issued_at"), _utc(statement["expires_at"], "expires_at")
    if expires <= issued or _coerce_utc(now, "now") > expires:
        raise GateReceiptError("receipt is expired or has invalid lifetime")
    if expected_gate_principal_uri is not None and statement["gate_principal_uri"] != expected_gate_principal_uri:
        raise GateReceiptError("receipt has the wrong gate principal")
    if expected_gate_key_id is not None and statement["gate_key_id"] != expected_gate_key_id:
        raise GateReceiptError("receipt has the wrong gate key identifier")
    _verify_signature(gate_public_key, envelope["signature"], statement)
    prereg = _canonical_object(frozen_prereg_bytes, "frozen preregistration")
    manifest = _canonical_object(validation_manifest_bytes, "validation manifest")
    _validate_prereg(prereg)
    _validate_manifest(manifest, members)
    _assert_independent_gate(manifest, statement["gate_principal_uri"])
    expected = {
        "prereg_sha256": sha256_hex(frozen_prereg_bytes), "validation_manifest_sha256": sha256_hex(validation_manifest_bytes),
        "trainer_sha256": manifest["artifact_commitments"]["trainer_sha256"], "protocol_sha256": manifest["artifact_commitments"]["protocol_sha256"],
        "public_artifact_sha256": manifest["artifact_commitments"]["public_artifact_sha256"],
        "member_artifact_sha256": list(members), "result_sha256": manifest["artifact_commitments"]["result_sha256"],
        "baseline_sha256": manifest["artifact_commitments"]["baseline_sha256"], "control_sha256": manifest["artifact_commitments"]["control_sha256"],
        "custody_uid": custody_uid, "test_sha256": test_sha256,
    }
    if any(statement[key] != value for key, value in expected.items()):
        raise GateReceiptError("receipt commitments do not match supplied evidence")
    return dict(statement)


def _validate_prereg(prereg: Mapping[str, Any]) -> None:
    if prereg.get("status") != "FROZEN":
        raise GateReceiptError("preregistration is not frozen")


def _validate_manifest(manifest: Mapping[str, Any], members: tuple[str, ...]) -> None:
    if manifest.get("seeds") != [0, 1, 2, 3, 4]:
        raise GateReceiptError("M3E requires exactly frozen seeds 0 through 4")
    policy = manifest.get("policy")
    _shape(policy, {"score_rule", "ranking", "capital_krw", "slot_budget_krw", "slots", "primary_cost_rate"}, "policy")
    if policy != {"score_rule": "unweighted_raw_member_score_mean_before_ranking_score_gt_0", "ranking": "top_10_distinct_by_score_then_symbol", "capital_krw": 60000000, "slot_budget_krw": 5000000, "slots": 10, "primary_cost_rate": 0.0023}:
        raise GateReceiptError("policy/accounting contract differs from M3E")
    ensemble = manifest.get("ensemble")
    _shape(ensemble, {"metrics", "pick_counts"}, "ensemble")
    _valid_metrics(ensemble["metrics"], "ensemble metrics")
    _valid_pick_counts(ensemble["pick_counts"], "ensemble pick counts")
    jackknives = manifest.get("jackknives")
    if not isinstance(jackknives, Mapping) or set(jackknives) != {str(seed) for seed in range(5)}:
        raise GateReceiptError("all five leave-one-out jackknives are required")
    for seed, row in jackknives.items():
        _shape(row, {"metrics", "pick_counts", "passes"}, f"jackknife {seed}")
        _valid_metrics(row["metrics"], f"jackknife {seed} metrics")
        _valid_pick_counts(row["pick_counts"], f"jackknife {seed} pick counts")
        if not isinstance(row["passes"], bool):
            raise GateReceiptError("jackknife pass flag is invalid")
    if sum(row["passes"] for row in jackknives.values()) < 4:
        raise GateReceiptError("at least four jackknives must pass")
    baselines = manifest.get("baselines")
    if not isinstance(baselines, Mapping) or not {"no_trade", "rule_topk_ret5", "rule_topk_low_vol", "rule_topk_inst", "random_topk"}.issubset(baselines):
        raise GateReceiptError("all frozen baselines are required")
    if not isinstance(manifest.get("exposure_matched_random"), Mapping):
        raise GateReceiptError("exposure-matched baseline is required")
    shuffled = manifest.get("shuffled_label_ensemble")
    if not isinstance(shuffled, Mapping) or not isinstance(shuffled.get("ensemble"), Mapping) or not isinstance(shuffled.get("jackknives"), Mapping) or set(shuffled["jackknives"]) != {str(seed) for seed in range(5)}:
        raise GateReceiptError("full shuffled ensemble and all jackknives are required")
    controls = shuffled.get("controls")
    required_controls = {"full", *(f"jackknife_{seed}" for seed in range(5))}
    if not isinstance(controls, Mapping) or set(controls) != required_controls:
        raise GateReceiptError("all shuffled controls are required")
    if any(not isinstance(row, Mapping) or row.get("control_fails") is not False for row in controls.values()):
        raise GateReceiptError("a shuffled control failed")
    verdict = manifest.get("verdict")
    _shape(verdict, {"value", "passing_jackknives", "reasons"}, "verdict")
    if verdict["value"] != ELIGIBLE_TOKEN or not isinstance(verdict["reasons"], list) or sorted(verdict["passing_jackknives"]) != sorted(seed for seed, row in jackknives.items() if row["passes"]):
        raise GateReceiptError("validation result is not eligible")
    if manifest.get("test") != {"state": "NOT_RUN"}:
        raise GateReceiptError("untouched test must remain NOT_RUN")
    locks = manifest.get("false_research_locks")
    if not isinstance(locks, Mapping) or locks.get("go_summary_allowed") is not False or any(value is not False for value in locks.values()):
        raise GateReceiptError("research locks must all remain false")
    commitments = manifest.get("artifact_commitments")
    _shape(commitments, {"trainer_sha256", "protocol_sha256", "public_artifact_sha256", "result_sha256", "baseline_sha256", "control_sha256"}, "artifact commitments")
    for field, value in commitments.items():
        _sha(value, field)
    computed_commitments = evidence_commitments(manifest, members)
    if any(commitments[name] != value for name, value in computed_commitments.items()):
        raise GateReceiptError("validation evidence differs from its artifact commitments")
    principals = manifest.get("principals")
    if not isinstance(principals, Mapping):
        raise GateReceiptError("trainer and custodian principals are required")
    # The issuing principal is compared by caller through this retained validation context.
    _principal(principals.get("trainer_principal_uri"), "trainer principal")
    _principal(principals.get("custodian_principal_uri"), "custodian principal")
    if len(set(members)) != 5:
        raise GateReceiptError("five unique member artifacts are required")


def _valid_metrics(value: Any, label: str) -> None:
    if not isinstance(value, Mapping) or not isinstance(value.get("nav"), (int, float)):
        raise GateReceiptError(f"{label} is invalid")


def _valid_pick_counts(value: Any, label: str) -> None:
    if not isinstance(value, list) or any(type(count) is not int or count < 0 or count > 10 for count in value):
        raise GateReceiptError(f"{label} must be 0 through 10")

def _assert_independent_gate(manifest: Mapping[str, Any], gate_principal_uri: str) -> None:
    principals = manifest["principals"]
    if gate_principal_uri in {principals["trainer_principal_uri"], principals["custodian_principal_uri"]}:
        raise GateReceiptError("gate signer must be independent of trainer and custodian")


def _canonical_object(raw: bytes, label: str) -> Mapping[str, Any]:
    if not isinstance(raw, bytes):
        raise GateReceiptError(f"{label} must be bytes")
    try:
        return parse_canonical_json(raw, label)
    except Exception as exc:
        raise GateReceiptError(f"{label} is not canonical JSON") from exc


def _shape(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise GateReceiptError(f"{label} has an invalid wire shape")
    return value


def _member_hashes(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or len(values) != 5:
        raise GateReceiptError("exactly five member artifact hashes are required")
    result = tuple(values)
    for value in result:
        _sha(value, "member artifact SHA-256")
    if len(set(result)) != 5:
        raise GateReceiptError("member artifact hashes must be unique")
    return result


def _verify_signature(key: bytes | Ed25519PublicKey, signature: Any, statement: Mapping[str, Any]) -> None:
    try:
        _public_key(key).verify(_unb64u(signature), DOMAIN + canonical_bytes(statement))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise GateReceiptError("gate receipt signature verification failed") from exc


def _private_key(value: Ed25519PrivateKey | bytes) -> Ed25519PrivateKey:
    if isinstance(value, Ed25519PrivateKey):
        return value
    if isinstance(value, bytes) and len(value) == 32:
        return Ed25519PrivateKey.from_private_bytes(value)
    raise GateReceiptError("signing key must be an Ed25519 private key or 32 bytes")


def _public_key(value: bytes | Ed25519PublicKey) -> Ed25519PublicKey:
    if isinstance(value, Ed25519PublicKey):
        return value
    if isinstance(value, bytes) and len(value) == 32:
        return Ed25519PublicKey.from_public_bytes(value)
    raise GateReceiptError("gate public key must be Ed25519 bytes")


def _b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64u(value: Any) -> bytes:
    if not isinstance(value, str) or not _B64U_RE.fullmatch(value):
        raise GateReceiptError("signature is malformed")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except ValueError as exc:
        raise GateReceiptError("signature is malformed") from exc


def _sha(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise GateReceiptError(f"{label} is not a SHA-256 digest")


def _uid(value: Any) -> None:
    if not isinstance(value, str) or not value or len(value) > 128 or "/" in value or "\\" in value:
        raise GateReceiptError("custody UID is invalid")


def _principal(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _PRINCIPAL_RE.fullmatch(value):
        raise GateReceiptError(f"{label} is invalid")


def _key_id(value: Any) -> None:
    if not isinstance(value, str) or not _KEY_ID_RE.fullmatch(value):
        raise GateReceiptError("gate key ID is invalid")


def _utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not _UTC_RE.fullmatch(value):
        raise GateReceiptError(f"{label} must be canonical UTC")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise GateReceiptError(f"{label} is invalid") from exc


def _coerce_utc(value: datetime | str, label: str) -> datetime:
    if isinstance(value, str):
        return _utc(value, label)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise GateReceiptError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")
