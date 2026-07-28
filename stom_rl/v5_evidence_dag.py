"""Fail-closed construction and validation of the Kronos v5 evidence DAG.

All persisted values are RFC 8785/JCS bytes.  Claim records enter a candidate
map as raw JCS bytes and are never reconstructed or normalized by this module.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from stom_rl.v5_authority_bridge import (
    AuthorityContext,
    BridgeValidationError,
    RawArtifactResolver,
    validate_existing_receipt_graph,
)
import rfc8785


CLAIM_SCHEMA: Final = "kronos_evidence_claim.v2"
PRECLOSURE_SCHEMA: Final = "kronos_preclosure.v2"
CANDIDATE_MAP_SCHEMA: Final = "kronos_candidate_map.v2"
FINAL_MAP_SCHEMA: Final = "kronos_final_map.v2"
E3R: Final = "E3.R"
_OBJECT_URI = re.compile(r"(?:agent://[^/\s]+(?:/.+)?|kronos-run://[A-Za-z0-9_-]{43}/[^/\\\0]+(?:/[^/\\\0]+)*)\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_CLAIM_ID = re.compile(r"[A-Z][A-Z0-9.]{1,31}\Z")
_TEMPLATE_ID = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")
_ASSURANCE_ROLES: Final = (
    ("OPERATOR_A", "kronos_operator_trace.v2"),
    ("OPERATOR_B", "kronos_operator_trace.v2"),
    ("TASK_SCORE", "kronos_task_score_review.v2"),
    ("ARCHITECT_REVIEW", "kronos_architect_review.v2"),
    ("CRITIC_REVIEW", "kronos_critic_review.v2"),
    ("EXECUTOR_QA", "kronos_executor_qa_review.v2"),
)
_ASSURANCE_SCHEMA_BY_ROLE: Final = dict(_ASSURANCE_ROLES)


class EvidenceDagError(ValueError):
    """Raised when an evidence graph violates its immutable DAG contract."""


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    """Return RFC 8785/JCS bytes without adding a line terminator."""
    try:
        return rfc8785.dumps(value)
    except Exception as exc:
        raise EvidenceDagError("value is not RFC 8785 canonicalizable") from exc


def parse_raw_jcs(raw: bytes, label: str = "object") -> dict[str, Any]:
    """Parse a JSON object only when its supplied bytes are exact RFC 8785 bytes."""
    if not isinstance(raw, bytes) or raw.startswith(b"\xef\xbb\xbf"):
        raise EvidenceDagError(f"{label} must be UTF-8 bytes without a BOM")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise EvidenceDagError(f"{label} contains a duplicate member")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates,
                           parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise EvidenceDagError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict) or canonical_bytes(value) != raw:
        raise EvidenceDagError(f"{label} is not raw RFC 8785/JCS bytes")
    return value


def object_ref(uri: str, raw: bytes) -> dict[str, Any]:
    """Create an ObjectRef bound to the exact raw bytes of an existing object."""
    value = parse_raw_jcs(raw, "referenced object")
    schema = value.get("schema")
    if not isinstance(uri, str) or not _OBJECT_URI.fullmatch(uri) or not isinstance(schema, str) or not schema:
        raise EvidenceDagError("ObjectRef source URI or schema is invalid")
    return {"uri": uri, "sha256": hashlib.sha256(raw).hexdigest(), "byte_length": len(raw), "schema": schema}


def _shape(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise EvidenceDagError(f"{label} has an invalid wire shape")
    return value


def _ref(value: Any, label: str, objects: Mapping[str, bytes] | None = None) -> Mapping[str, Any]:
    value = _shape(value, {"uri", "sha256", "byte_length", "schema"}, label)
    uri, digest, length, schema = value["uri"], value["sha256"], value["byte_length"], value["schema"]
    if not isinstance(uri, str) or not _OBJECT_URI.fullmatch(uri) or not isinstance(digest, str) or not _SHA.fullmatch(digest) or not isinstance(length, int) or isinstance(length, bool) or length < 0 or not isinstance(schema, str) or not schema:
        raise EvidenceDagError(f"{label} is not an ObjectRef")
    if objects is not None:
        raw = objects.get(uri)
        if raw is None:
            raise EvidenceDagError(f"{label} does not resolve to an already-existing object")
        actual = object_ref(uri, raw)
        if canonical_bytes(dict(value)) != canonical_bytes(actual):
            raise EvidenceDagError(f"{label} does not preserve ObjectRef raw-byte identity")
    return value


def _claim(value: Mapping[str, Any], expected_id: str | None = None, expected_kind: str | None = None) -> None:
    value = _shape(value, {"schema", "kind", "claim_id", "evidence_refs"}, "claim")
    if value["schema"] != CLAIM_SCHEMA or value["kind"] not in {"claim-99", "e3-runtime"} or not isinstance(value["claim_id"], str) or not _CLAIM_ID.fullmatch(value["claim_id"]) or (expected_id is not None and value["claim_id"] != expected_id) or (expected_kind is not None and value["kind"] != expected_kind):
        raise EvidenceDagError("claim identity or kind is invalid")
    refs = value["evidence_refs"]
    if not isinstance(refs, list):
        raise EvidenceDagError("claim evidence_refs is invalid")
    encoded = [canonical_bytes(dict(_ref(ref, "claim evidence ref"))) for ref in refs]
    if len(encoded) != len(set(encoded)):
        raise EvidenceDagError("claim evidence_refs contains a duplicate ObjectRef")


def _raw_claims(records: Mapping[str, bytes], expected_ids: Sequence[str], kind: str, objects: Mapping[str, bytes]) -> dict[str, dict[str, Any]]:
    if not isinstance(records, Mapping) or set(records) != set(expected_ids):
        raise EvidenceDagError("claim records have missing, duplicate, or extra claim IDs")
    parsed: dict[str, dict[str, Any]] = {}
    for claim_id in sorted(expected_ids):
        raw = records[claim_id]
        claim = parse_raw_jcs(raw, f"claim {claim_id}")
        _claim(claim, claim_id, kind)
        for ref in claim["evidence_refs"]:
            _ref(ref, f"claim {claim_id} evidence ref", objects)
        parsed[claim_id] = claim
    return parsed


def _expected_99(claim_ids: Sequence[str]) -> list[str]:
    if not isinstance(claim_ids, Sequence) or isinstance(claim_ids, (str, bytes)):
        raise EvidenceDagError("expected claim IDs must be a sequence")
    ids = list(claim_ids)
    if len(ids) != 99 or ids != sorted(ids) or len(set(ids)) != 99 or E3R in ids or any(not isinstance(item, str) or not _CLAIM_ID.fullmatch(item) for item in ids):
        raise EvidenceDagError("expected claim IDs must be 99 sorted non-E3.R claim IDs")
    return ids


def build_preview_99(records: Mapping[str, bytes], expected_claim_ids: Sequence[str], objects: Mapping[str, bytes]) -> bytes:
    """Build the immutable keyed 99-claim baseline used by every candidate."""
    ids = _expected_99(expected_claim_ids)
    claims = _raw_claims(records, ids, "claim-99", objects)
    refs = {
        claim_id: _claim_ref_from_raw(records[claim_id], claim_id, "claim-99", objects)
        for claim_id in ids
    }
    return canonical_bytes({"schema": "kronos_preview_map.v2", "kind": "preview-99", "claims": claims,
                            "claim_refs": refs, "claim_ids": ids, "complete": False,
                            "missing_claim_ids": [E3R], "eligible_for_scoring": False})


def build_preclosure(required_dependencies: Mapping[str, Mapping[str, Any]], post_preclosure_templates: Sequence[Mapping[str, Any]], prior_objects: Mapping[str, bytes]) -> bytes:
    """Close the immutable 99-claim baseline before E3.R may be materialized."""
    if not isinstance(required_dependencies, Mapping) or not isinstance(post_preclosure_templates, Sequence) or isinstance(post_preclosure_templates, (str, bytes)):
        raise EvidenceDagError("preclosure dependencies or templates are invalid")
    required_names = {"preview_99", "candidate_source", "scorecard", "capabilities"}
    if set(required_dependencies) != required_names:
        raise EvidenceDagError("preclosure dependencies must be the exact closed dependency set")
    dependencies: dict[str, Mapping[str, Any]] = {}
    for name in sorted(required_names):
        dependencies[name] = dict(_ref(required_dependencies[name], f"required dependency {name}", prior_objects))
    if dependencies["preview_99"]["schema"] != "kronos_preview_map.v2" or dependencies["candidate_source"]["schema"] != "kronos_source_identity.v1" or dependencies["scorecard"]["schema"] != "kronos_dashboard_v5_scorecard.v2" or dependencies["capabilities"]["schema"] != "kronos_candidate_capabilities.v2":
        raise EvidenceDagError("preclosure dependency schemas are invalid")
    templates = []
    for template in post_preclosure_templates:
        template = _shape(template, {"template_id", "claim_id", "schema"}, "post-preclosure template")
        if not isinstance(template["template_id"], str) or not _TEMPLATE_ID.fullmatch(template["template_id"]) or template["claim_id"] != E3R or template["schema"] != "kronos_e3_runtime.v2":
            raise EvidenceDagError("post-preclosure template is not the deterministic E3.R template")
        templates.append(dict(template))
    if templates != [{"template_id": E3R, "claim_id": E3R, "schema": "kronos_e3_runtime.v2"}]:
        raise EvidenceDagError("preclosure must contain exactly one E3.R template")
    return canonical_bytes({"schema": PRECLOSURE_SCHEMA, "kind": "preclosure", "required_dependencies": dependencies,
                            "post_preclosure_templates": templates})


def _claim_ref_from_raw(raw: bytes, claim_id: str, kind: str, prior_objects: Mapping[str, bytes]) -> dict[str, Any]:
    claim = parse_raw_jcs(raw, f"claim {claim_id}")
    _claim(claim, claim_id, kind)
    for evidence_ref in claim["evidence_refs"]:
        _ref(evidence_ref, f"claim {claim_id} evidence ref", prior_objects)
    matches = [uri for uri, candidate in prior_objects.items() if candidate == raw]
    if len(matches) != 1:
        raise EvidenceDagError(f"claim {claim_id} must have exactly one existing raw object identity")
    return object_ref(matches[0], raw)


def _capabilities(value: Any, expected_ids: Sequence[str]) -> dict[str, Any]:
    value = _shape(value, {"schema", "claim_ids"}, "candidate capabilities")
    claim_ids = value["claim_ids"]
    if value["schema"] != "kronos_candidate_capabilities.v2" or not isinstance(claim_ids, list) or not all(isinstance(claim_id, str) for claim_id in claim_ids) or claim_ids != sorted(set(claim_ids)) or not set(claim_ids).issubset(set(expected_ids)):
        raise EvidenceDagError("candidate capabilities must be a sorted unique subset of claim IDs")
    return {"schema": value["schema"], "claim_ids": list(claim_ids)}
def _preclosure_dependencies(preclosure_ref: Mapping[str, Any], source: Mapping[str, Any], scorecard: Mapping[str, Any], capabilities: Mapping[str, Any], expected_ids: Sequence[str], prior_objects: Mapping[str, bytes]) -> dict[str, bytes]:
    preclosure = _ref(preclosure_ref, "preclosure_ref", prior_objects)
    if preclosure["schema"] != PRECLOSURE_SCHEMA:
        raise EvidenceDagError("candidate preclosure_ref has the wrong schema")
    value = parse_raw_jcs(prior_objects[str(preclosure["uri"])], "preclosure")
    _shape(value, {"schema", "kind", "required_dependencies", "post_preclosure_templates"}, "preclosure")
    capability_matches = [object_ref(uri, raw) for uri, raw in prior_objects.items() if raw == canonical_bytes(capabilities)]
    if len(capability_matches) != 1:
        raise EvidenceDagError("capabilities must have exactly one immutable raw object identity")
    dependencies = value["required_dependencies"]
    expected = {"candidate_source": source, "scorecard": scorecard, "capabilities": capability_matches[0]}
    if not isinstance(dependencies, Mapping) or set(dependencies) != {"preview_99", *expected}:
        raise EvidenceDagError("preclosure dependencies are incomplete or contain aliases")
    for name, ref in expected.items():
        if canonical_bytes(dict(_ref(dependencies[name], f"preclosure {name}", prior_objects))) != canonical_bytes(dict(ref)):
            raise EvidenceDagError(f"preclosure {name} does not bind the designated immutable identity")
    preview_ref = _ref(dependencies["preview_99"], "preclosure preview_99", prior_objects)
    if preview_ref["schema"] != "kronos_preview_map.v2":
        raise EvidenceDagError("preclosure preview_99 has the wrong schema")
    preview = parse_raw_jcs(prior_objects[str(preview_ref["uri"])], "preview-99")
    _shape(preview, {"schema", "kind", "claims", "claim_refs", "claim_ids", "complete", "missing_claim_ids", "eligible_for_scoring"}, "preview-99")
    if preview["schema"] != "kronos_preview_map.v2" or preview["kind"] != "preview-99" or preview["claim_ids"] != list(expected_ids) or preview["complete"] is not False or preview["missing_claim_ids"] != [E3R] or preview["eligible_for_scoring"] is not False:
        raise EvidenceDagError("preclosure preview_99 is not the designated 99-claim baseline")
    if not isinstance(preview["claims"], Mapping) or not isinstance(preview["claim_refs"], Mapping) or set(preview["claims"]) != set(expected_ids) or set(preview["claim_refs"]) != set(expected_ids):
        raise EvidenceDagError("preview-99 keyed baseline is incomplete")
    baseline: dict[str, bytes] = {}
    for claim_id in expected_ids:
        embedded = preview["claims"][claim_id]
        _claim(embedded, claim_id, "claim-99")
        ref = _ref(preview["claim_refs"][claim_id], f"preview claim {claim_id}", prior_objects)
        raw = prior_objects[str(ref["uri"])]
        if raw != canonical_bytes(embedded):
            raise EvidenceDagError("preview-99 embedded claim does not preserve its raw ObjectRef")
        baseline[claim_id] = raw
    if value["post_preclosure_templates"] != [{"template_id": E3R, "claim_id": E3R, "schema": "kronos_e3_runtime.v2"}]:
        raise EvidenceDagError("preclosure must bind exactly one E3.R template")
    return baseline


def _e3_references_preclosure(claim: Mapping[str, Any], prior_objects: Mapping[str, bytes]) -> None:
    for ref in claim["evidence_refs"]:
        resolved = _ref(ref, "E3.R evidence ref", prior_objects)
        if resolved["schema"] == PRECLOSURE_SCHEMA:
            return
    raise EvidenceDagError("E3.R must reference a preclosure object")


def build_candidate_map(preclosure_ref: Mapping[str, Any], candidate_source_ref: Mapping[str, Any], scorecard_ref: Mapping[str, Any], capabilities: Mapping[str, Any], records_99: Mapping[str, bytes], e3_runtime_raw: bytes, expected_claim_ids: Sequence[str], prior_objects: Mapping[str, bytes]) -> bytes:
    """Build the exact consumer candidate-map contract from existing raw claims."""
    ids = _expected_99(expected_claim_ids)
    source = _ref(candidate_source_ref, "candidate_source_ref", prior_objects)
    scorecard = _ref(scorecard_ref, "scorecard_ref", prior_objects)
    if source["schema"] != "kronos_source_identity.v1" or scorecard["schema"] != "kronos_dashboard_v5_scorecard.v2":
        raise EvidenceDagError("candidate source or scorecard has the wrong schema")
    capabilities_value = _capabilities(capabilities, [*ids, E3R])
    baseline = _preclosure_dependencies(preclosure_ref, source, scorecard, capabilities_value, ids, prior_objects)
    if not isinstance(records_99, Mapping) or set(records_99) != set(ids):
        raise EvidenceDagError("claim records have missing, duplicate, or extra claim IDs")
    if any(records_99[claim_id] != baseline[claim_id] for claim_id in ids):
        raise EvidenceDagError("candidate records do not match the independent preview-99 baseline")
    claims = [
        {"claim_id": claim_id, "evidence_ref": _claim_ref_from_raw(baseline[claim_id], claim_id, "claim-99", prior_objects)}
        for claim_id in ids
    ]
    e3 = parse_raw_jcs(e3_runtime_raw, E3R)
    _claim(e3, E3R, "e3-runtime")
    _e3_references_preclosure(e3, prior_objects)
    if not any(canonical_bytes(dict(_ref(ref, "E3.R evidence ref", prior_objects))) == canonical_bytes(dict(_ref(preclosure_ref, "preclosure_ref", prior_objects))) for ref in e3["evidence_refs"]):
        raise EvidenceDagError("E3.R must reference the designated preclosure")
    claims.append({"claim_id": E3R, "evidence_ref": _claim_ref_from_raw(e3_runtime_raw, E3R, "e3-runtime", prior_objects)})
    raw = canonical_bytes({"schema": CANDIDATE_MAP_SCHEMA, "complete": True, "candidate_source_ref": dict(source),
                           "scorecard_ref": dict(scorecard), "capabilities": capabilities_value, "claims": sorted(claims, key=lambda claim: claim["claim_id"])})
    validate_candidate_map(raw, ids, prior_objects, preclosure_ref, object_ref(_claim_ref_from_raw(e3_runtime_raw, E3R, "e3-runtime", prior_objects)["uri"], e3_runtime_raw))
    return raw


def validate_candidate_map(raw: bytes, expected_claim_ids: Sequence[str], prior_objects: Mapping[str, bytes], preclosure_ref: Mapping[str, Any], e3_runtime_ref: Mapping[str, Any]) -> dict[str, Any]:
    """Reject non-consumer maps and claim references that lack raw-byte identity."""
    ids = _expected_99(expected_claim_ids)
    value = dict(_shape(parse_raw_jcs(raw, "candidate map"), {"schema", "complete", "candidate_source_ref", "scorecard_ref", "capabilities", "claims"}, "candidate map"))
    if value["schema"] != CANDIDATE_MAP_SCHEMA or value["complete"] is not True:
        raise EvidenceDagError("candidate map identity or completeness is invalid")
    source = _ref(value["candidate_source_ref"], "candidate_source_ref", prior_objects)
    scorecard = _ref(value["scorecard_ref"], "scorecard_ref", prior_objects)
    if source["schema"] != "kronos_source_identity.v1" or scorecard["schema"] != "kronos_dashboard_v5_scorecard.v2":
        raise EvidenceDagError("candidate source or scorecard has the wrong schema")
    capabilities = _capabilities(value["capabilities"], [*ids, E3R])
    baseline = _preclosure_dependencies(preclosure_ref, source, scorecard, capabilities, ids, prior_objects)
    claims = value["claims"]
    expected = sorted([*ids, E3R])
    if not isinstance(claims, list) or len(claims) != 100:
        raise EvidenceDagError("candidate map must contain exactly 100 claim records")
    observed_ids: list[str] = []
    observed_refs: set[bytes] = set()
    for record in claims:
        record = _shape(record, {"claim_id", "evidence_ref"}, "candidate claim record")
        claim_id = record["claim_id"]
        if not isinstance(claim_id, str):
            raise EvidenceDagError("candidate claim ID is invalid")
        observed_ids.append(claim_id)
        ref = _ref(record["evidence_ref"], f"claim {claim_id} evidence ref", prior_objects)
        encoded_ref = canonical_bytes(dict(ref))
        if encoded_ref in observed_refs:
            raise EvidenceDagError("candidate map reuses an evidence claim reference")
        observed_refs.add(encoded_ref)
        if ref["schema"] != CLAIM_SCHEMA:
            raise EvidenceDagError("candidate claim reference has the wrong schema")
        claim_raw = prior_objects[str(ref["uri"])]
        claim = parse_raw_jcs(claim_raw, f"claim {claim_id}")
        _claim(claim, claim_id, "e3-runtime" if claim_id == E3R else "claim-99")
        for evidence_ref in claim["evidence_refs"]:
            _ref(evidence_ref, f"claim {claim_id} evidence ref", prior_objects)
        if claim_id == E3R:
            _e3_references_preclosure(claim, prior_objects)
            if canonical_bytes(dict(ref)) != canonical_bytes(dict(_ref(e3_runtime_ref, "E3.R ref", prior_objects))) or not any(canonical_bytes(dict(_ref(evidence_ref, "E3.R evidence ref", prior_objects))) == canonical_bytes(dict(_ref(preclosure_ref, "preclosure_ref", prior_objects))) for evidence_ref in claim["evidence_refs"]):
                raise EvidenceDagError("candidate E3.R does not bind the designated materialized proof and preclosure")
        elif claim_raw != baseline[claim_id]:
            raise EvidenceDagError("candidate map modified a scored claim's independent preview-99 raw bytes")
    if observed_ids != expected:
        raise EvidenceDagError("candidate map claim records are duplicated, reordered, missing, or foreign")
    return value




def _assurances(
    assurance_refs: Sequence[Mapping[str, Any]],
    prior_objects: Mapping[str, bytes],
    candidate: Mapping[str, Any],
    resolver: RawArtifactResolver,
    authority: AuthorityContext,
) -> list[dict[str, Any]]:
    """Resolve six bridge-issued VALID receipts in the frozen role order."""
    if not isinstance(assurance_refs, Sequence) or isinstance(assurance_refs, (str, bytes)) or len(assurance_refs) != len(_ASSURANCE_ROLES):
        raise EvidenceDagError("final map must contain exactly six authenticated assurances")
    receipts = [dict(_ref(ref, "assurance_ref")) for ref in assurance_refs]
    roles: list[str] = []
    candidate_raw = canonical_bytes(dict(candidate))
    candidate_map = parse_raw_jcs(prior_objects[str(candidate["uri"])], "assurance candidate map")
    try:
        e3_record = next(record for record in candidate_map["claims"] if record["claim_id"] == E3R)
        e3_ref = _ref(e3_record["evidence_ref"], "assurance E3.R ref", prior_objects)
        e3_claim = parse_raw_jcs(prior_objects[str(e3_ref["uri"])], "assurance E3.R claim")
        designated_preclosure = next(
            _ref(ref, "assurance designated preclosure", prior_objects)
            for ref in e3_claim["evidence_refs"]
            if ref.get("schema") == PRECLOSURE_SCHEMA
        )
    except (AttributeError, KeyError, StopIteration, TypeError) as exc:
        raise EvidenceDagError("final map candidate lacks the designated preclosure") from exc
    expected_roles = {
        "OPERATOR_A": "USABILITY_OPERATOR", "OPERATOR_B": "USABILITY_OPERATOR",
        "TASK_SCORE": "TASK_SCORE_REVIEWER", "ARCHITECT_REVIEW": "ARCHITECT_REVIEWER",
        "CRITIC_REVIEW": "CRITIC_REVIEWER", "EXECUTOR_QA": "EXECUTOR_QA_REVIEWER",
    }
    for receipt_ref in receipts:
        if receipt_ref["schema"] != "kronos_gjc_validation_receipt.v2":
            raise EvidenceDagError("final map assurance must be a bridge validation receipt")
        try:
            receipt_raw = validate_existing_receipt_graph(receipt_ref, resolver, authority)
        except BridgeValidationError as exc:
            raise EvidenceDagError("final map assurance receipt fails bridge provenance verification") from exc
        receipt = parse_raw_jcs(receipt_raw, "assurance receipt")
        required = {"schema", "assignment_ref", "output_ref", "export_ref", "validated_role", "validated_scope", "status"}
        if receipt.get("schema") != "kronos_gjc_validation_receipt.v2" or receipt.get("status") != "VALID" or not required.issubset(receipt):
            raise EvidenceDagError("final map assurance receipt is not a VALID bridge receipt")
        role = receipt["validated_scope"]
        if role not in _ASSURANCE_SCHEMA_BY_ROLE or receipt["validated_role"] != expected_roles[role]:
            raise EvidenceDagError("final map assurance receipt role is invalid")
        assignment_ref = _ref(receipt["assignment_ref"], "assurance assignment_ref")
        output_ref = _ref(receipt["output_ref"], "assurance output_ref")
        export_ref = _ref(receipt["export_ref"], "assurance export_ref")
        if output_ref["schema"] != "kronos_gjc_role_output.v2" or assignment_ref["schema"] != "kronos_gjc_assignment.v2" or export_ref["schema"] != "kronos_gjc_export.v2":
            raise EvidenceDagError("final map assurance receipt bindings have invalid schemas")

        def resolve(ref: Mapping[str, Any], label: str) -> dict[str, Any]:
            try:
                record = resolver.resolve_record(str(ref["uri"]), "raw")
            except Exception as exc:
                raise EvidenceDagError(f"{label} is unavailable from the authenticated resolver") from exc
            if record.uri != ref["uri"] or record.selector != "raw" or object_ref(str(ref["uri"]), record.raw) != dict(ref):
                raise EvidenceDagError(f"{label} does not preserve authenticated ObjectRef identity")
            return parse_raw_jcs(record.raw, label)

        assignment = resolve(assignment_ref, "assurance assignment")
        output = resolve(output_ref, "assurance output")
        export = resolve(export_ref, "assurance export")
        if export.get("assignment_ref") != assignment_ref or export.get("output_ref") != output_ref or output.get("assignment_ref") != assignment_ref:
            raise EvidenceDagError("final map assurance receipt bindings do not match export chain")
        expected_schema = _ASSURANCE_SCHEMA_BY_ROLE[role]
        if output.get("schema") != "kronos_gjc_role_output.v2" or output.get("payload_schema") != expected_schema or output.get("scope") != role or assignment.get("scope") != role:
            raise EvidenceDagError("final map assurance output does not match its fixed role")
        payload = output.get("payload")
        if not isinstance(payload, Mapping):
            raise EvidenceDagError("final map assurance output payload is invalid")
        predecessors: dict[tuple[str, str], Mapping[str, Any]] = {}
        # The bridge verifier above authenticated this payload and its predecessor graph.
        if role in {"ARCHITECT_REVIEW", "CRITIC_REVIEW", "EXECUTOR_QA"}:
            bound = _ref(payload.get("candidate_map_ref"), "assurance candidate_map_ref", prior_objects)
            if canonical_bytes(dict(bound)) != candidate_raw:
                raise EvidenceDagError("final map assurance is not bound to the designated candidate")
            preclosure = _ref(payload.get("preclosure_ref"), "assurance preclosure_ref", prior_objects)
            if canonical_bytes(dict(preclosure)) != canonical_bytes(dict(designated_preclosure)):
                raise EvidenceDagError("final map assurance is not bound to the designated preclosure")
        roles.append(role)
    if roles != [role for role, _ in _ASSURANCE_ROLES]:
        raise EvidenceDagError("final map assurances are not in fixed role order")
    if len({canonical_bytes(ref) for ref in receipts}) != len(receipts):
        raise EvidenceDagError("final map assurance_refs contains a duplicate ObjectRef")
    return receipts


def _graph_projection(objects: Mapping[str, bytes], final_raw: bytes) -> dict[str, bytes]:
    """Select the closed evidence graph; bridge chains are validated separately."""
    selected: dict[str, bytes] = {}
    pending = [
        uri for uri, raw in objects.items()
        if parse_raw_jcs(raw, uri).get("schema") in {
            CLAIM_SCHEMA, "kronos_preview_map.v2", PRECLOSURE_SCHEMA,
            CANDIDATE_MAP_SCHEMA, "kronos_gjc_validation_receipt.v2",
        }
    ]
    while pending:
        uri = pending.pop()
        if uri in selected:
            continue
        raw = objects.get(uri)
        if raw is None:
            raise EvidenceDagError("closed evidence topology has an unresolved object")
        value = parse_raw_jcs(raw, uri)
        selected[uri] = raw
        if value.get("schema") == "kronos_gjc_validation_receipt.v2":
            continue
        for ref in _all_refs(value):
            target = str(_ref(ref, f"reference in {uri}", objects)["uri"])
            if target not in selected:
                pending.append(target)
    selected["agent://evidence/final-map"] = final_raw
    return selected


def build_final_map(
    candidate_map_ref: Mapping[str, Any],
    assurance_refs: Sequence[Mapping[str, Any]],
    prior_objects: Mapping[str, bytes],
    resolver: RawArtifactResolver,
    authority: AuthorityContext,
) -> bytes:
    """Create a canonically ordered downstream assurance leaf."""
    candidate = _ref(candidate_map_ref, "candidate_map_ref", prior_objects)
    if candidate["schema"] != CANDIDATE_MAP_SCHEMA:
        raise EvidenceDagError("final map candidate is invalid")
    assurances = _assurances(assurance_refs, prior_objects, candidate, resolver, authority)
    raw = canonical_bytes({"schema": FINAL_MAP_SCHEMA, "kind": "final-map", "candidate_map_ref": dict(candidate),
                           "assurance_refs": assurances})
    validate_final_map(raw, prior_objects, candidate, resolver, authority)
    closed_objects = dict(prior_objects)
    for ref in assurances:
        try:
            closed_objects[str(ref["uri"])] = resolver.resolve_record(str(ref["uri"]), "raw").raw
        except Exception as exc:
            raise EvidenceDagError("authenticated assurance receipt is unavailable for topology validation") from exc
    validate_acyclic_graph(_graph_projection(closed_objects, raw))
    return raw


def validate_final_map(
    raw: bytes,
    prior_objects: Mapping[str, bytes],
    candidate_map_ref: Mapping[str, Any],
    resolver: RawArtifactResolver,
    authority: AuthorityContext,
) -> dict[str, Any]:
    value = dict(_shape(parse_raw_jcs(raw, "final map"), {"schema", "kind", "candidate_map_ref", "assurance_refs"}, "final map"))
    if value["schema"] != FINAL_MAP_SCHEMA or value["kind"] != "final-map":
        raise EvidenceDagError("final map identity is invalid")
    candidate = _ref(value["candidate_map_ref"], "final candidate_map_ref", prior_objects)
    if candidate["schema"] != CANDIDATE_MAP_SCHEMA or canonical_bytes(dict(candidate)) != canonical_bytes(dict(_ref(candidate_map_ref, "designated candidate_map_ref", prior_objects))):
        raise EvidenceDagError("final map does not bind the designated candidate")
    assurances = _assurances(value["assurance_refs"], prior_objects, candidate, resolver, authority)
    if assurances != value["assurance_refs"]:
        raise EvidenceDagError("final map assurances are not in fixed role order")
    return value


def _all_refs(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        if set(value) == {"uri", "sha256", "byte_length", "schema"}:
            return [value]
        return [ref for item in value.values() for ref in _all_refs(item)]
    if isinstance(value, list):
        return [ref for item in value for ref in _all_refs(item)]
    return []


def validate_acyclic_graph(objects: Mapping[str, bytes], ordered_uris: Sequence[str] | None = None) -> None:
    """Verify the persisted fixed stage topology, not a caller-supplied sort."""
    del ordered_uris
    parsed = {uri: parse_raw_jcs(raw, uri) for uri, raw in objects.items()}
    if set(parsed) != set(objects) or any(not isinstance(uri, str) or not _OBJECT_URI.fullmatch(uri) for uri in objects):
        raise EvidenceDagError("object graph contains an invalid URI")

    def stage(value: Mapping[str, Any]) -> int:
        if value.get("schema") == CLAIM_SCHEMA:
            return 4 if value.get("claim_id") == E3R else 1
        if value.get("schema") == "kronos_preview_map.v2":
            return 2
        if value.get("schema") == PRECLOSURE_SCHEMA:
            return 3
        if value.get("schema") == CANDIDATE_MAP_SCHEMA:
            return 5
        if value.get("schema") == "kronos_gjc_validation_receipt.v2":
            return 6
        if value.get("schema") == FINAL_MAP_SCHEMA:
            return 7
        return 0

    stages = {uri: stage(value) for uri, value in parsed.items()}
    if 7 in stages.values():
        counts = {number: sum(item == number for item in stages.values()) for number in range(1, 8)}
        if counts != {1: 99, 2: 1, 3: 1, 4: 1, 5: 1, 6: 6, 7: 1}:
            raise EvidenceDagError("evidence graph does not match the fixed 99→preview→preclosure→E3→candidate→six-assurance→final topology")
    edges: dict[str, list[str]] = {}
    for uri, value in parsed.items():
        edges[uri] = []
        if value.get("schema") == "kronos_gjc_validation_receipt.v2":
            continue
        for ref in _all_refs(value):
            if not isinstance(ref, Mapping) or not isinstance(ref.get("uri"), str):
                _ref(ref, f"reference in {uri}", objects)
                raise AssertionError("unreachable")
            target = ref["uri"]
            if target not in stages:
                _ref(ref, f"reference in {uri}", objects)
                raise AssertionError("unreachable")
            if target == uri:
                raise EvidenceDagError("evidence graph contains a self edge")
            edges[uri].append(target)
    active: set[str] = set()
    complete: set[str] = set()

    def visit(uri: str) -> None:
        if uri in active:
            raise EvidenceDagError("evidence graph contains a transitive cycle")
        if uri not in complete:
            active.add(uri)
            for target in edges[uri]:
                visit(target)
            active.remove(uri)
            complete.add(uri)

    for uri in edges:
        visit(uri)
    roots = [uri for uri in edges if not any(uri in targets for targets in edges.values())]
    final_roots = [uri for uri in roots if parsed[uri].get("schema") == FINAL_MAP_SCHEMA]
    if len(final_roots) != 1:
        raise EvidenceDagError("evidence graph must have exactly one final-map root")
    reachable: set[str] = set()
    stack = final_roots[:]
    while stack:
        uri = stack.pop()
        if uri not in reachable:
            reachable.add(uri)
            stack.extend(edges[uri])
    if reachable != set(objects):
        raise EvidenceDagError("evidence graph contains disconnected objects")
    for uri, targets in edges.items():
        for target in targets:
            if stages[target] >= stages[uri] and stages[uri] != 0:
                raise EvidenceDagError("evidence graph contains a non-backward future edge")
    for uri, value in parsed.items():
        if value.get("schema") != "kronos_gjc_validation_receipt.v2":
            for ref in _all_refs(value):
                _ref(ref, f"reference in {uri}", objects)
