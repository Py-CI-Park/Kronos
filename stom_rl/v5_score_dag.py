"""Candidate-only, byte-stable V5 engineering point scorer.

Assurance and terminal objects are deliberately not inputs to this module.
"""
from __future__ import annotations

import base64
import importlib.util
import hashlib
import json
from pathlib import Path
import re
from collections.abc import Callable, Mapping
from typing import Any, Final

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
_SOURCE_SPEC = importlib.util.spec_from_file_location("kronos_v5_source_identity", Path(__file__).resolve().parents[1] / "scripts" / "score_kronos_dashboard_v5.py")
if _SOURCE_SPEC is None or _SOURCE_SPEC.loader is None:
    raise RuntimeError("canonical V5 source identity module is unavailable")
source_identity = importlib.util.module_from_spec(_SOURCE_SPEC)
_SOURCE_SPEC.loader.exec_module(source_identity)
from stom_rl import v5_evidence_dag as evidence_dag


_SHA: Final = re.compile(r"^[0-9a-f]{64}$")
_REF_KEYS: Final = frozenset({"uri", "sha256", "byte_length", "schema"})
_CANDIDATE_KEYS: Final = frozenset({"schema", "complete", "candidate_source_ref", "scorecard_ref", "capabilities", "claims"})
_RECEIPT_KEYS: Final = frozenset({"schema", "claim_id", "candidate_source_sha256", "claim_definition_sha256", "verifier", "evidence_schema", "status", "authority_proof"})
_PROOF_KEYS: Final = frozenset({"schema", "claim_id", "candidate_source_sha256", "claim_definition_sha256", "verifier", "evidence_schema", "status", "violation_codes", "signature"})
CATEGORY_LIMITS: Final = {"A": (25, 23), "B": (25, 23), "C": (20, 18), "D": (15, 13), "E": (15, 13)}
VIOLATION_CAPS: Final = {"FRESH_OOS_MISREPRESENTATION": "fresh_oos_misrepresentation", "UNAPPROVED_CONTRACT_OR_API_CHANGE": "unapproved_contract_or_api_change"}
PINNED_SCORECARD_SHA256: Final = "4afa3656e8bed8e5adae8bc3e99f89d5b450f8c56561429cb121aa601458ec7b"


class ScoreDagError(ValueError):
    """Raised when a candidate-only V5 score input is not closed and authentic."""


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return rfc8785.dumps(value)
    except Exception as exc:
        raise ScoreDagError("value is not RFC8785 canonicalizable") from exc


def _parse_json(raw: bytes, label: str, *, canonical: bool) -> Mapping[str, Any]:
    if not isinstance(raw, bytes) or raw.startswith(b"\xef\xbb\xbf"):
        raise ScoreDagError(f"{label} must be UTF-8 bytes without a BOM")
    def duplicate_free(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ScoreDagError(f"{label} has a duplicate JSON member")
            result[key] = value
        return result
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=duplicate_free, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ScoreDagError(f"{label} is not strict JSON") from exc
    if not isinstance(parsed, dict) or (canonical and canonical_bytes(parsed) != raw):
        raise ScoreDagError(f"{label} is not raw canonical RFC8785 bytes")
    return parsed


def parse_canonical_json(raw: bytes, label: str) -> Mapping[str, Any]:
    return _parse_json(raw, label, canonical=True)


def object_ref(raw: bytes, *, uri: str, schema: str) -> dict[str, Any]:
    """Build an ObjectRef whose identity is the supplied raw bytes, not a parse."""
    if not isinstance(raw, bytes) or not isinstance(uri, str) or not uri or not isinstance(schema, str) or not schema:
        raise ScoreDagError("ObjectRef arguments are invalid")
    return {"uri": uri, "sha256": hashlib.sha256(raw).hexdigest(), "byte_length": len(raw), "schema": schema}


def _ref(value: Any, label: str, schema: str | None = None) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != _REF_KEYS or not isinstance(value["uri"], str) or not re.fullmatch(r"agent://[^/\s]+(?:/.+)?", value["uri"]) or not isinstance(value["byte_length"], int) or isinstance(value["byte_length"], bool) or value["byte_length"] < 0 or not isinstance(value["schema"], str) or not value["schema"] or not isinstance(value["sha256"], str) or not _SHA.fullmatch(value["sha256"]):
        raise ScoreDagError(f"{label} is not an ObjectRef")
    if schema is not None and value["schema"] != schema:
        raise ScoreDagError(f"{label} has the wrong schema")
    return value


def _resolve(ref: Mapping[str, Any], resolver: Callable[[Mapping[str, Any]], bytes], label: str, *, canonical: bool = True) -> tuple[bytes, Mapping[str, Any]]:
    try:
        raw = resolver(ref)
    except Exception as exc:
        raise ScoreDagError(f"{label} ObjectRef could not be resolved") from exc
    if not isinstance(raw, bytes) or len(raw) != ref["byte_length"] or hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ScoreDagError(f"{label} ObjectRef does not identify returned raw bytes")
    return raw, _parse_json(raw, label, canonical=canonical)


def _scorecard(value: Mapping[str, Any]) -> tuple[list[str], dict[str, list[str]]]:
    if value.get("schema") != "kronos_dashboard_v5_scorecard.v2" or value.get("total_claims") != 100 or not isinstance(value.get("categories"), dict) or not isinstance(value.get("claims"), dict):
        raise ScoreDagError("scorecard is not the immutable V5 scorecard")
    categories: dict[str, list[str]] = {}
    all_ids: list[str] = []
    for category, (weight, floor) in CATEGORY_LIMITS.items():
        item = value["categories"].get(category)
        if not isinstance(item, dict) or item.get("weight") != weight or item.get("floor") != floor or not isinstance(item.get("claim_ids"), list):
            raise ScoreDagError("scorecard category limits are invalid")
        categories[category] = item["claim_ids"]
        all_ids.extend(item["claim_ids"])
    if set(value["categories"]) != set(CATEGORY_LIMITS) or len(all_ids) != 100 or len(set(all_ids)) != 100 or set(value["claims"]) != set(all_ids):
        raise ScoreDagError("scorecard claim universe is not exactly 100 unique claims")
    return all_ids, categories
def validate_point_score(value: Mapping[str, Any]) -> None:
    """Reject syntactically valid point scores whose accounting is contradictory."""
    categories = {
        "A": [f"A{number:02d}" for number in range(1, 26)],
        "B": [f"B{number:02d}" for number in range(1, 26)],
        "C": [f"C{number:02d}" for number in range(1, 21)],
        "D": [f"D{number:02d}" for number in range(1, 16)],
        "E": ["E01", "E02", "E3.R", *[f"E{number:02d}" for number in range(4, 16)]],
    }
    locks = {"promotion_allowed": False, "model_build_allowed": False, "paper_forward_allowed": False, "live_broker_order_allowed": False, "profitability_claim_allowed": False, "go_summary_allowed": False}
    try:
        results = value["claim_results"]
        scores = {category: sum(results[claim_id] is True for claim_id in claim_ids) for category, claim_ids in categories.items()}
        caps = value["active_hard_caps"]
        if value["category_scores"] != scores or value["capability_option_ceilings"] != scores or caps not in ([], ["fresh_oos_misrepresentation"], ["unapproved_contract_or_api_change"], ["fresh_oos_misrepresentation", "unapproved_contract_or_api_change"]):
            raise ValueError
        raw_total = sum(scores.values())
        effective_total = min(raw_total, 89) if caps else raw_total
        floors = [category for category, (_, floor) in CATEGORY_LIMITS.items() if scores[category] < floor]
        gate = {"id": "engineering_90", "passed": effective_total >= 90 and not floors and not caps, "total_min": 90}
        if value["raw_total"] != raw_total or value["effective_total"] != effective_total or value["floor_failures"] != floors or value["gate"] != gate or value["six_locks_false"] != locks:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ScoreDagError("point score semantic equation invalid") from None
def validate_assurance_decision(value: Mapping[str, Any]) -> None:
    """Validate the closed decision projection independently of JSON Schema."""
    try:
        identical = value["point_scores_identical"]
        point_pass = value["point_pass"]
        eligible = value["assurance_eligible"]
        codes = value["blocking_codes"]
        expected = []
        if identical is False:
            expected.append("POINT_SCORE_MISMATCH")
        if point_pass is False:
            expected.append("POINT_SCORE_FAIL")
        if eligible is False:
            expected.append("ASSURANCE_BLOCK")
        if not all(isinstance(item, bool) for item in (identical, point_pass, eligible)) or codes != expected or (eligible and not (identical and point_pass)):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ScoreDagError("assurance decision semantic equation invalid") from None






def _verify_proof(proof: Mapping[str, Any], definition: Mapping[str, Any], receipt: Mapping[str, Any], source_sha: str, scorecard: Mapping[str, Any]) -> list[str]:
    if not isinstance(proof, Mapping) or set(proof) != _PROOF_KEYS or proof.get("schema") != "kronos_claim_authority_proof.v1":
        raise ScoreDagError("receipt authority proof has an invalid wire shape")
    unsigned = {key: proof[key] for key in _PROOF_KEYS - {"signature"}}
    if any(unsigned[key] != receipt[key] for key in ("claim_id", "candidate_source_sha256", "claim_definition_sha256", "verifier", "evidence_schema", "status")) or unsigned["candidate_source_sha256"] != source_sha or unsigned["claim_definition_sha256"] != hashlib.sha256(canonical_bytes(definition)).hexdigest() or unsigned["verifier"] != definition["verifier"] or unsigned["evidence_schema"] != definition["required_evidence_schema"] or unsigned["status"] not in ("PASS", "FAIL") or not isinstance(unsigned["violation_codes"], list) or any(not isinstance(code, str) for code in unsigned["violation_codes"]) or unsigned["violation_codes"] != sorted(set(unsigned["violation_codes"])) or any(code not in VIOLATION_CAPS for code in unsigned["violation_codes"]) or any(VIOLATION_CAPS[code] not in definition["hard_cap_ids"] for code in unsigned["violation_codes"]):
        raise ScoreDagError("receipt authority proof is not bound to its claim")
    signature = proof["signature"]
    pin = scorecard.get("authority_proof")
    if not isinstance(signature, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", signature) or not isinstance(pin, dict):
        raise ScoreDagError("receipt authority proof encoding is invalid")
    try:
        public_key = base64.urlsafe_b64decode(pin["public_key"] + "=" * (-len(pin["public_key"]) % 4))
        signed = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if len(signed) != 64 or base64.urlsafe_b64encode(signed).rstrip(b"=").decode() != signature:
            raise ValueError("noncanonical signature")
        Ed25519PublicKey.from_public_bytes(public_key).verify(signed, pin["domain_separator"].encode("ascii") + b"\0" + canonical_bytes(unsigned))
    except (KeyError, TypeError, ValueError, InvalidSignature) as exc:
        raise ScoreDagError("receipt authority proof signature is invalid") from exc
    return unsigned["violation_codes"]
def _validated_candidate_graph(candidate_raw: bytes, candidate: Mapping[str, Any], resolver: Callable[[Mapping[str, Any]], bytes], claim_ids: list[str]) -> None:
    """Reject anything the canonical evidence-DAG producer would reject."""
    try:
        objects: dict[str, bytes] = {}
        for label, ref in (("candidate source", candidate["candidate_source_ref"]), ("scorecard", candidate["scorecard_ref"])):
            checked = _ref(ref, label)
            raw, _ = _resolve(checked, resolver, label)
            objects[str(checked["uri"])] = raw
        records: dict[str, bytes] = {}
        for record in candidate["claims"]:
            checked = _ref(record["evidence_ref"], f"claim {record['claim_id']} evidence", "kronos_evidence_claim.v2")
            raw, claim = _resolve(checked, resolver, f"claim {record['claim_id']} record")
            objects[str(checked["uri"])] = raw
            if record["claim_id"] != "E3.R":
                records[str(record["claim_id"])] = raw
            for nested_ref in claim.get("evidence_refs", []):
                nested = _ref(nested_ref, f"claim {record['claim_id']} nested evidence")
                nested_raw, _ = _resolve(nested, resolver, f"claim {record['claim_id']} nested evidence")
                objects[str(nested["uri"])] = nested_raw
        pending = list(objects.values())
        while pending:
            value = _parse_json(pending.pop(), "evidence graph", canonical=True)
            stack = [value]
            while stack:
                item = stack.pop()
                if isinstance(item, dict):
                    if set(item) == _REF_KEYS:
                        nested = _ref(item, "evidence graph ObjectRef")
                        if nested["uri"] not in objects:
                            nested_raw, _ = _resolve(nested, resolver, "evidence graph ObjectRef")
                            objects[str(nested["uri"])] = nested_raw
                            pending.append(nested_raw)
                    else:
                        stack.extend(item.values())
                elif isinstance(item, list):
                    stack.extend(item)
        e3_record = next(record for record in candidate["claims"] if record["claim_id"] == "E3.R")
        e3_ref = _ref(e3_record["evidence_ref"], "E3.R evidence", "kronos_evidence_claim.v2")
        e3_claim = _parse_json(objects[str(e3_ref["uri"])], "E3.R evidence", canonical=True)
        preclosure_ref = next(_ref(ref, "E3.R preclosure", "kronos_preclosure.v2") for ref in e3_claim["evidence_refs"] if isinstance(ref, dict) and ref.get("schema") == "kronos_preclosure.v2")
        evidence_dag.validate_candidate_map(candidate_raw, [claim_id for claim_id in claim_ids if claim_id != "E3.R"], objects, preclosure_ref, e3_ref)
    except (evidence_dag.EvidenceDagError, KeyError, TypeError, AttributeError, StopIteration) as exc:
        raise ScoreDagError("candidate does not satisfy the canonical evidence DAG") from exc




def score_candidate_map(candidate_map_raw: bytes, *, resolver: Callable[[Mapping[str, Any]], bytes], process_label: str = "") -> bytes:
    """Return JCS point-score bytes. ``process_label`` is intentionally unscored."""
    del process_label
    candidate = parse_canonical_json(candidate_map_raw, "candidate map")
    if set(candidate) != _CANDIDATE_KEYS or candidate.get("schema") != "kronos_candidate_map.v2" or candidate.get("complete") is not True:
        raise ScoreDagError("candidate map must be a complete final kronos_candidate_map.v2")
    source_ref = _ref(candidate["candidate_source_ref"], "candidate_source_ref", "kronos_source_identity.v1")
    scorecard_ref = _ref(candidate["scorecard_ref"], "scorecard_ref", "kronos_dashboard_v5_scorecard.v2")
    _, source = _resolve(source_ref, resolver, "candidate source")
    scorecard_raw, scorecard = _resolve(scorecard_ref, resolver, "scorecard", canonical=False)
    try:
        source_identity.source_identity_sha256(source)
    except (source_identity.ScorecardError, TypeError, KeyError) as exc:
        raise ScoreDagError("candidate source is not a canonical source identity") from exc
    pinned_raw = (Path(__file__).resolve().parents[1] / "docs" / "kronos_dashboard_v5_scorecard_v2.json").read_bytes()
    if hashlib.sha256(pinned_raw).hexdigest() != PINNED_SCORECARD_SHA256 or canonical_bytes(_parse_json(pinned_raw, "pinned scorecard", canonical=True)) != pinned_raw:
        raise ScoreDagError("approved V2 scorecard pin is invalid")
    if scorecard_raw != pinned_raw or scorecard_ref["sha256"] != PINNED_SCORECARD_SHA256:
        raise ScoreDagError("scorecard raw canonical identity is not pinned")
    claim_ids, categories = _scorecard(scorecard)
    capabilities = candidate.get("capabilities")
    if not isinstance(capabilities, dict) or set(capabilities) != {"schema", "claim_ids"} or capabilities.get("schema") != "kronos_candidate_capabilities.v2" or not isinstance(capabilities.get("claim_ids"), list) or capabilities["claim_ids"] != sorted(set(capabilities["claim_ids"])) or not set(capabilities["claim_ids"]).issubset(set(claim_ids)):
        raise ScoreDagError("candidate capabilities are not a sorted subset of scorecard claims")
    claims = candidate.get("claims")
    if not isinstance(claims, list) or len(claims) != 100:
        raise ScoreDagError("candidate map must contain exactly 100 claim records")
    seen: set[str] = set()
    previous = ""
    records: dict[str, Mapping[str, Any]] = {}
    for record in claims:
        if not isinstance(record, dict) or set(record) != {"claim_id", "evidence_ref"} or not isinstance(record.get("claim_id"), str) or record["claim_id"] <= previous or record["claim_id"] in seen:
            raise ScoreDagError("candidate claim records are duplicated or unsorted")
        _ref(record["evidence_ref"], f"claim {record['claim_id']} evidence")
        previous, seen = record["claim_id"], seen | {record["claim_id"]}
        records[record["claim_id"]] = record
    if seen != set(claim_ids):
        raise ScoreDagError("candidate map has missing or foreign scorecard claims")
    _validated_candidate_graph(candidate_map_raw, candidate, resolver, claim_ids)
    source_sha = source_ref["sha256"]
    results: dict[str, bool] = {}
    active: set[str] = set()
    used_evidence: set[tuple[str, str]] = set()
    capability_ids = set(capabilities["claim_ids"])
    for claim_id in claim_ids:
        ref = _ref(records[claim_id]["evidence_ref"], f"claim {claim_id} record", "kronos_evidence_claim.v2")
        identity = (ref["uri"], ref["sha256"])
        if identity in used_evidence:
            raise ScoreDagError("an evidence claim object cannot support more than one claim")
        used_evidence.add(identity)
        claim_raw, evidence_claim = _resolve(ref, resolver, f"claim {claim_id} record")
        if set(evidence_claim) != {"schema", "kind", "claim_id", "evidence_refs"} or evidence_claim.get("schema") != "kronos_evidence_claim.v2" or evidence_claim.get("claim_id") != claim_id or evidence_claim.get("kind") != ("e3-runtime" if claim_id == "E3.R" else "claim-99") or not isinstance(evidence_claim.get("evidence_refs"), list) or canonical_bytes(evidence_claim) != claim_raw:
            raise ScoreDagError("candidate claim record has an invalid raw-bound identity or kind")
        receipt_refs = [item for item in evidence_claim["evidence_refs"] if isinstance(item, dict) and item.get("schema") == "kronos_claim_verification.v1"]
        if len(receipt_refs) != 1:
            raise ScoreDagError("claim record must contain exactly one point-bearing verification receipt")
        receipt_ref = _ref(receipt_refs[0], f"claim {claim_id} verification receipt", "kronos_claim_verification.v1")
        receipt_raw, receipt = _resolve(receipt_ref, resolver, f"claim {claim_id} verification receipt")
        if canonical_bytes(receipt) != receipt_raw:
            raise ScoreDagError("verification receipt lost raw-byte identity")
        if set(receipt) != _RECEIPT_KEYS or receipt.get("schema") != "kronos_claim_verification.v1" or receipt.get("claim_id") != claim_id or receipt.get("candidate_source_sha256") != source_sha or receipt.get("claim_definition_sha256") != hashlib.sha256(canonical_bytes(scorecard["claims"][claim_id])).hexdigest() or receipt.get("verifier") != scorecard["claims"][claim_id]["verifier"] or receipt.get("evidence_schema") != scorecard["claims"][claim_id]["required_evidence_schema"] or receipt.get("status") not in ("PASS", "FAIL"):
            raise ScoreDagError("fabricated or foreign claim evidence")
        violations = _verify_proof(receipt["authority_proof"], scorecard["claims"][claim_id], receipt, source_sha, scorecard)
        passed = receipt["status"] == "PASS"
        if passed and claim_id not in capability_ids:
            raise ScoreDagError("candidate capability overreach")
        results[claim_id] = passed
        for code in violations:
            active.add(VIOLATION_CAPS[code])
    if capability_ids != {claim_id for claim_id, passed in results.items() if passed}:
        raise ScoreDagError("candidate capabilities must be derived from valid PASS receipts")
    category_scores = {category: sum(results[claim_id] for claim_id in ids) for category, ids in categories.items()}
    option_ceilings = {category: sum(claim_id in capability_ids for claim_id in ids) for category, ids in categories.items()}
    floor_failures = [category for category, (_, floor) in CATEGORY_LIMITS.items() if category_scores[category] < floor]
    caps = {item["id"]: item for item in scorecard.get("hard_caps", []) if isinstance(item, dict) and isinstance(item.get("id"), str)}
    active_caps = [item["id"] for item in scorecard.get("hard_caps", []) if item.get("id") in active]
    raw_total = sum(category_scores.values())
    effective_total = raw_total
    for cap_id in active_caps:
        cap = caps[cap_id]
        effective_total = min(effective_total, cap.get("caps_total_at", cap.get("caps_total_below", 1) - 1))
    result = {"schema": "kronos_point_score.v2", "candidate_map_sha256": hashlib.sha256(candidate_map_raw).hexdigest(), "candidate_source_sha256": source_sha, "scorecard_sha256": scorecard_ref["sha256"], "category_scores": category_scores, "capability_option_ceilings": option_ceilings, "claim_results": {claim_id: results[claim_id] for claim_id in sorted(results)}, "floor_failures": floor_failures, "active_hard_caps": active_caps, "raw_total": raw_total, "effective_total": effective_total, "gate": {"id": "engineering_90", "passed": effective_total >= 90 and not floor_failures and not active_caps, "total_min": 90}, "six_locks_false": {"promotion_allowed": False, "model_build_allowed": False, "paper_forward_allowed": False, "live_broker_order_allowed": False, "profitability_claim_allowed": False, "go_summary_allowed": False}}
    validate_point_score(result)
    return canonical_bytes(result) + b"\n"
