"""Fail-closed generic GJC request-to-VALID-receipt authority bridge."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Mapping, Protocol, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from stom_rl.v5_authority import AuthorityVerificationError, InMemoryNonceReplayStore, NonceReplayStore, canonical_bytes, parse_canonical_json, verify_attestation

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
OBJECT_URI_RE = re.compile(r"^(?:agent://[^/:\s]+|kronos-run://[A-Za-z0-9_-]{43}/(?!\.{1,2}(?:/|$))[^/\\\0]+(?:/(?!\.{1,2}(?:/|$))[^/\\\0]+)*)\Z")
INPUT_SLOT_NAMES = ("fixture", "instrument", "trace_a", "trace_b", "machine_score_a", "machine_score_b", "preclosure", "candidate_map", "command_manifest", "qa_manifest", "final_map", "point_score_a", "point_score_b", "assurance_decision")
RULES = {
    "ASSIGN_OPERATOR": ("USABILITY_OPERATOR", frozenset({"OPERATOR_A", "OPERATOR_B"}), "DISTINCT_OPERATOR", "kronos_operator_trace.v2"),
    "ASSIGN_TASK_SCORE_REVIEWER": ("TASK_SCORE_REVIEWER", frozenset({"TASK_SCORE"}), "DISTINCT_TASK_REVIEWER", "kronos_task_score_review.v2"),
    "ASSIGN_ARCHITECT": ("ARCHITECT_REVIEWER", frozenset({"ARCHITECT_REVIEW"}), "DISTINCT_ARCHITECT", "kronos_architect_review.v2"),
    "ASSIGN_CRITIC": ("CRITIC_REVIEWER", frozenset({"CRITIC_REVIEW"}), "DISTINCT_CRITIC", "kronos_critic_review.v2"),
    "ASSIGN_EXECUTOR_QA": ("EXECUTOR_QA_REVIEWER", frozenset({"EXECUTOR_QA"}), "DISTINCT_EXECUTOR_QA", "kronos_executor_qa_review.v2"),
    "TERMINAL_CLOSURE": ("TERMINAL_CLOSURE_AUTHORITY", frozenset({"TERMINAL_CLOSURE"}), "DISTINCT_TERMINAL_AUTHORITY", "kronos_terminal_closure.v2"),
}
TASK_IDS = tuple(f"T{i:02d}" for i in range(1, 11))
DIMENSIONS = ("U", "L", "J")
FAILURE_CODES = ("TIMEOUT", "WRONG_RUN", "SOURCE_INSPECTION", "PRODUCER_HELP", "ACTION_LIMIT", "MISSING_TRACE", "INVALID_ASSIGNMENT", "RELOAD_NOT_REQUESTED", "OBJECTIVE_MISMATCH")
INVARIANTS = ("ACYCLIC_GRAPH", "CANONICAL_BYTES", "AUTHORITY_CHAIN", "CLAIM_PRESERVATION", "HEAD_DIST_IMMUTABILITY", "REGISTRY_API_CONTRACT", "ACCOUNTING_PROTOCOL")
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
TASK_BLOCKING_CODES = ("OBJECTIVE_FAILURE", "DIMENSION_BELOW_90", "TRACE_INVALID", "ASSIGNMENT_INVALID", "UNRESOLVED_DISPUTE")
ARCHITECT_BLOCKING_CODES = ("GRAPH_CYCLE", "SELF_OR_FUTURE_REFERENCE", "AUTHORITY_INVALID", "CLAIM_MUTATION", "HEAD_DIST_DRIFT", "API_SCHEMA_GAP", "ACCOUNTING_MISMATCH", "OTHER_BLOCKER")
CRITIC_BLOCKING_CODES = ("CLAIM_FALSE", "MISSING_EVIDENCE", "SCORE_CONTRACT_GAP", "TRUTH_CONFLICT", "MODEL_SCORE_LEAKAGE", "OTHER_BLOCKER")
EXECUTOR_FAILURE_CODES = ("NONZERO", "SKIP", "XFAIL", "XPASS", "WARNING_SUPPRESSION", "HEAD_DRIFT", "TREE_DRIFT", "DIST_DRIFT", "DIRTY_WORKTREE", "MISSING_RESULT")
TERMINAL_BLOCKING_CODES = ("POINT_SCORE_FAIL", "POINT_SCORE_MISMATCH", "ASSURANCE_BLOCK", "PRIOR_CHAIN_RERESOLUTION_FAIL", "HEAD_DRIFT", "TREE_DRIFT", "DIST_DRIFT", "DIRTY_WORKTREE", "TERMINAL_AUTHORITY_INVALID", "APPROVAL_MISSING")
PRIOR_SCOPES = ("OPERATOR_A", "OPERATOR_B", "TASK_SCORE", "ARCHITECT_REVIEW", "CRITIC_REVIEW", "EXECUTOR_QA")
# Each role may consume only these already-produced artifact schemas in its role payload.
# Every ObjectRef path in a role payload is closed to an earlier artifact schema.
# `*` denotes an array item or object member.
ROLE_PREDECESSOR_SCHEMAS = {
    "kronos_operator_trace.v2": {
        "fixture_ref": {"kronos_fixture.v2"}, "instrument_ref": {"kronos_instrument.v2"},
        "tasks.*.trace_ref": {"kronos_task_trace.v2"}, "tasks.*.screenshot_refs.*": {"kronos_screenshot.v2"},
        "objective_failures.*.evidence_ref": {"kronos_task_trace.v2"},
    },
    "kronos_task_score_review.v2": {
        "operator_trace_refs.*": {"kronos_operator_trace.v2"},
        "machine_score_refs.*": {"kronos_machine_task_score.v2"},
        "dimensions.*.*.evidence_refs.*": {"kronos_machine_task_score.v2", "kronos_operator_trace.v2"},
        "disputes.*.evidence_ref": {"kronos_operator_trace.v2", "kronos_machine_task_score.v2"},
        "objective_failures.*.evidence_ref": {"kronos_task_trace.v2"},
    },
    "kronos_architect_review.v2": {
        "preclosure_ref": {"kronos_preclosure.v2"}, "candidate_map_ref": {"kronos_candidate_map.v2"},
        "findings.*.evidence_refs.*": {"kronos_preclosure.v2", "kronos_candidate_map.v2"},
    },
    "kronos_critic_review.v2": {
        "preclosure_ref": {"kronos_preclosure.v2"}, "candidate_map_ref": {"kronos_candidate_map.v2"},
        "claim_checks.*.evidence_refs.*": {"kronos_preclosure.v2", "kronos_candidate_map.v2"},
    },
    "kronos_executor_qa_review.v2": {
        "preclosure_ref": {"kronos_preclosure.v2"}, "candidate_map_ref": {"kronos_candidate_map.v2"},
        "command_manifest_ref": {"kronos_command_manifest.v2"}, "qa_artifact_refs.*": {"kronos_qa_artifact.v2"},
        "commands.*.result_ref": {"kronos_qa_artifact.v2"},
        "failures.*.evidence_refs.*": {"kronos_qa_artifact.v2"},
    },
    "kronos_terminal_closure.v2": {
        "final_map_ref": {"kronos_final_map.v2"}, "score_ref_a": {"kronos_point_score.v2"},
        "score_ref_b": {"kronos_point_score.v2"}, "architect_output_ref": {"kronos_gjc_role_output.v2"},
        "critic_output_ref": {"kronos_gjc_role_output.v2"}, "executor_qa_output_ref": {"kronos_gjc_role_output.v2"},
        "operator_output_refs.*": {"kronos_gjc_role_output.v2"}, "task_score_output_ref": {"kronos_gjc_role_output.v2"},
        "re_resolutions.*.export_ref": {"kronos_gjc_export.v2"},
        "re_resolutions.*.assignment_ref": {"kronos_gjc_assignment.v2"},
        "re_resolutions.*.output_ref": {"kronos_gjc_role_output.v2"},
    },
}

class BridgeValidationError(ValueError):
    """An invalid wire graph; no receipt is issued."""

@dataclass(frozen=True)
class ResolutionRecord:
    uri: str
    selector: str
    raw: bytes
    resolved_at: str
    resolver: str
    resolver_principal_uri: str

class RawArtifactResolver(Protocol):
    def resolve_record(self, uri: str, selector: str) -> ResolutionRecord: ...

class RequestConsumptionStore(Protocol):
    def store_receipt_if_absent(self, request_identity: str, receipt: bytes) -> bytes | None: ...

class InMemoryRequestConsumptionStore:
    def __init__(self) -> None:
        self._receipts: dict[str, bytes] = {}
        self._lock = Lock()
    def store_receipt_if_absent(self, request_identity: str, receipt: bytes) -> bytes | None:
        with self._lock:
            if request_identity in self._receipts:
                return None
            self._receipts[request_identity] = receipt
            return receipt

@dataclass(frozen=True)
class AuthorityContext:
    referenced_lifecycle: bytes
    current_lifecycle: bytes
    lifecycle_history: Sequence[bytes]
    pinned_root_public_key: bytes | str
    pinned_root_key_id: str
    pinned_genesis_envelope_sha256: str
    role_validity_caps: Mapping[str, timedelta]
    nonce_store: NonceReplayStore
    validation_policy_bytes: bytes
    trusted_clock: Callable[[], datetime]
    independent_principals: Mapping[str, frozenset[str]]
    resolver_implementation: str = "functions.read.v1"
    resolver_principal_uri: str = "agent://functions-read"

class LiteralRawResolver:
    """Test resolver; AuthorityContext, not this object, authenticates its identity."""
    def __init__(self, objects: Mapping[str, bytes], *, resolved_at: str = "2026-01-01T00:00:00Z", principal_uri: str = "agent://functions-read") -> None:
        self._objects, self._resolved_at, self._principal = dict(objects), resolved_at, principal_uri
    def resolve_record(self, uri: str, selector: str) -> ResolutionRecord:
        if selector != "raw" or uri not in self._objects:
            raise BridgeValidationError("raw artifact is unavailable")
        return ResolutionRecord(uri, selector, self._objects[uri], self._resolved_at, "functions.read.v1", self._principal)

def _fail(message: str) -> None: raise BridgeValidationError(message)
def _time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value): _fail(f"{label} is not UTC seconds")
    try: return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc: raise BridgeValidationError(f"{label} is not UTC") from exc
def _whole_second(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None: _fail("trusted clock is not aware")
    return now.astimezone(timezone.utc).replace(microsecond=0)
def _ref(value: Any, schema: str | None = None) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != {"uri", "sha256", "byte_length", "schema"}: _fail("object reference has an invalid wire shape")
    if not isinstance(value.get("uri"), str) or not OBJECT_URI_RE.fullmatch(value["uri"]): _fail("object reference URI is invalid")
    if not isinstance(value.get("sha256"), str) or not SHA256_RE.fullmatch(value["sha256"]): _fail("object reference SHA-256 is invalid")
    if not isinstance(value.get("byte_length"), int) or isinstance(value["byte_length"], bool) or not 0 <= value["byte_length"] <= 9007199254740991: _fail("object reference byte length is invalid")
    if not isinstance(value.get("schema"), str) or not value["schema"] or schema is not None and value["schema"] != schema: _fail("object reference schema is invalid")
    return value

_SCHEMA = json.loads((Path(__file__).parents[1] / "docs" / "schemas" / "kronos_gjc_bridge.v2.schema.json").read_text(encoding="utf-8"))
_VALIDATORS = {
    name: Draft202012Validator(
        {"$schema": _SCHEMA["$schema"], "$defs": _SCHEMA["$defs"], "$ref": f"#/$defs/{name}"},
        format_checker=FormatChecker(),
    )
    for name in _SCHEMA["$defs"]
}
def _wire(name: str, value: Any) -> Mapping[str, Any]:
    if name not in _VALIDATORS or list(_VALIDATORS[name].iter_errors(value)): _fail("wire schema validation failed")
    return value

def _resolve(resolver: RawArtifactResolver, ref: Any, schema: str, authority: AuthorityContext) -> tuple[Mapping[str, Any], bytes, Mapping[str, Any], ResolutionRecord]:
    parsed = _ref(ref, schema)
    try: record = resolver.resolve_record(parsed["uri"], "raw")
    except BridgeValidationError: raise
    except Exception as exc: raise BridgeValidationError("raw artifact resolution failed") from exc
    if not isinstance(record, ResolutionRecord) or record.uri != parsed["uri"] or record.selector != "raw": _fail("resolver record is invalid")
    if record.resolver != authority.resolver_implementation or record.resolver_principal_uri != authority.resolver_principal_uri: _fail("resolver record mismatches pinned authority context")
    _time(record.resolved_at, "resolver resolved_at")
    if not isinstance(record.raw, bytes) or len(record.raw) != parsed["byte_length"] or hashlib.sha256(record.raw).hexdigest() != parsed["sha256"]: _fail("raw artifact hash or length mismatches reference")
    try: value = parse_canonical_json(record.raw, schema)
    except AuthorityVerificationError as exc: raise BridgeValidationError("stored object is not canonical JSON") from exc
    if value.get("schema") != parsed["schema"]: _fail("stored object schema mismatches reference")
    return parsed, record.raw, value, record

def _slots(slots: Any, bindings: Any) -> None:
    names = [x.get("name") if isinstance(x, dict) else None for x in slots] if isinstance(slots, list) else []
    bound = [x.get("name") if isinstance(x, dict) else None for x in bindings] if isinstance(bindings, list) else []
    if names != sorted(names, key=INPUT_SLOT_NAMES.index) or len(set(names)) != len(names) or bound != sorted(bound, key=INPUT_SLOT_NAMES.index) or len(set(bound)) != len(bound): _fail("input slots or bindings are not in frozen order")
    schemas = {slot["name"]: slot["schema"] for slot in slots}
    for binding in bindings:
        if binding["name"] not in schemas or _ref(binding["artifact_ref"])["schema"] != schemas[binding["name"]]: _fail("input binding is invalid")
    if any(slot["required"] and slot["name"] not in bound for slot in slots): _fail("required input binding is absent")
def _projection(value: Mapping[str, Any], schema: str, fields: Sequence[str]) -> bytes: return canonical_bytes({"schema": schema, **{field: value[field] for field in fields}})
def _verify(raw: bytes, payload: bytes, payload_schema: str, scope: str, authority: AuthorityContext, at: datetime) -> None:
    try: verify_attestation(raw, payload_bytes=payload, payload_schema=payload_schema, scope=scope, referenced_lifecycle=authority.referenced_lifecycle, current_lifecycle=authority.current_lifecycle, lifecycle_history=authority.lifecycle_history, pinned_root_public_key=authority.pinned_root_public_key, pinned_root_key_id=authority.pinned_root_key_id, pinned_genesis_envelope_sha256=authority.pinned_genesis_envelope_sha256, verification_time=at, role_validity_caps=authority.role_validity_caps, nonce_store=authority.nonce_store)
    except AuthorityVerificationError as exc: raise BridgeValidationError("attestation authority verification failed") from exc

def _ordered_refs(values: Any) -> None:
    if not isinstance(values, list) or values != sorted(values, key=lambda r: (r["schema"], r["sha256"], r["uri"])) or len({(r["uri"], r["sha256"]) for r in values}) != len(values): _fail("reference array is not ordered and unique")
def _codes(values: Any, allowed: Sequence[str], label: str) -> None:
    if not isinstance(values, list) or any(v not in allowed for v in values) or len(set(values)) != len(values) or values != sorted(values, key=allowed.index): _fail(f"{label} is not uniquely in frozen order")
def _path_refs(value: Any, path: tuple[str, ...] = ()) -> Sequence[tuple[tuple[str, ...], Mapping[str, Any]]]:
    if isinstance(value, dict):
        if set(value) == {"uri", "sha256", "byte_length", "schema"}:
            return ((path, _ref(value)),)
        return tuple(item for key, child in value.items() for item in _path_refs(child, path + (key,)))
    if isinstance(value, list):
        return tuple(item for child in value for item in _path_refs(child, path + ("*",)))
    return ()

def _same_ref(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return left["uri"] == right["uri"] and left["sha256"] == right["sha256"]

def _canonical_failures(tasks: Sequence[Mapping[str, Any]], operator_index: str) -> list[tuple[str, str, str, Mapping[str, Any], str]]:
    return [
        (operator_index, task["task_id"], code, task["trace_ref"], task["completed_at"])
        for task in tasks for code in task["failure_codes"]
    ]
def _machine_score(value: Mapping[str, Any]) -> None:
    if set(value) != {"schema", "operator_index", "bitmaps"} or value["schema"] != "kronos_machine_task_score.v2" or value["operator_index"] not in ("A", "B"):
        _fail("machine-score payload has an invalid wire shape")
    bitmaps = value["bitmaps"]
    if not isinstance(bitmaps, Mapping) or set(bitmaps) != set(DIMENSIONS):
        _fail("machine-score bitmaps are invalid")
    for dimension in DIMENSIONS:
        bitmap = bitmaps[dimension]
        if not isinstance(bitmap, list) or len(bitmap) != 10 or any(not isinstance(bit, bool) for bit in bitmap):
            _fail("machine-score bitmap is invalid")

def _predecessor_payloads(
    payload: Mapping[str, Any], schema: str, resolver: RawArtifactResolver, authority: AuthorityContext
) -> Mapping[tuple[str, str], Mapping[str, Any]]:
    resolved: dict[tuple[str, str], Mapping[str, Any]] = {}
    for _, ref in _path_refs(payload):
        parsed, _, value, _ = _resolve(resolver, ref, _ref(ref)["schema"], authority)
        if parsed["schema"] == "kronos_machine_task_score.v2":
            _machine_score(value)
        resolved[(parsed["uri"], parsed["sha256"])] = value
    return resolved
def _verify_prior_chain(resolution: Mapping[str, Any], resolver: RawArtifactResolver, authority: AuthorityContext, closed_at: datetime) -> None:
    scope = resolution["scope"]
    export_ref, _, export, export_record = _resolve(resolver, resolution["export_ref"], "kronos_gjc_export.v2", authority)
    assignment_ref, _, assignment, _ = _resolve(resolver, resolution["assignment_ref"], "kronos_gjc_assignment.v2", authority)
    output_ref, _, output, _ = _resolve(resolver, resolution["output_ref"], "kronos_gjc_role_output.v2", authority)
    _wire("export", export); _wire("assignment", assignment); _wire("output", output)
    if export["assignment_ref"] != assignment_ref or export["output_ref"] != output_ref or export["resolver"] != authority.resolver_implementation or export["selector"] != "raw" or export["resolver_principal_uri"] != authority.resolver_principal_uri or export["resolved_at"] != export_record.resolved_at:
        _fail("terminal prior export chain is invalid")
    request_ref, _, request, _ = _resolve(resolver, export["request_ref"], "kronos_gjc_request_instance.v2", authority)
    _wire("request", request)
    template_ref, template_raw, template, _ = _resolve(resolver, request["template_ref"], "kronos_gjc_request_template.v2", authority)
    _wire("template", template)
    template_fields = ("template_key", "request_type", "required_role", "scope", "candidate_head", "dist_manifest_sha256", "input_slots", "required_output_schema", "independence_policy")
    if template_raw != _projection(request, "kronos_gjc_request_template.v2", template_fields):
        _fail("terminal prior template projection mismatches")
    _slots(request["input_slots"], request["input_artifacts"])
    role, scopes, policy, output_schema = RULES.get(request["request_type"], (None, (), None, None))
    if scope not in PRIOR_SCOPES or request["scope"] != scope or request["scope"] not in scopes or (request["required_role"], request["independence_policy"], request["required_output_schema"]) != (role, policy, output_schema):
        _fail("terminal prior chain role or scope is invalid")
    aa_ref, aa_raw, aa, _ = _resolve(resolver, assignment["attestable_ref"], "kronos_gjc_assignment_attestable.v2", authority)
    oa_ref, oa_raw, oa, _ = _resolve(resolver, output["attestable_ref"], "kronos_gjc_role_output_attestable.v2", authority)
    aatt_ref, aatt_raw, aatt, _ = _resolve(resolver, assignment["attestation_ref"], "kronos_attestation.v2", authority)
    oatt_ref, oatt_raw, oatt, _ = _resolve(resolver, output["attestation_ref"], "kronos_attestation.v2", authority)
    _wire("assignmentAttestable", aa); _wire("outputAttestable", oa)
    afields = ("request_ref", "assignment_uid", "request_uid", "run_nonce", "subject_principal_uri", "role", "scope", "candidate_head", "dist_manifest_sha256", "input_slots", "input_artifacts", "issued_at", "expires_at")
    ofields = ("request_ref", "assignment_ref", "request_uid", "assignment_uid", "subject_principal_uri", "role", "scope", "candidate_head", "dist_manifest_sha256", "input_slots", "input_artifacts", "started_at", "completed_at", "status", "payload_schema", "payload")
    if aa_raw != _projection(assignment, "kronos_gjc_assignment_attestable.v2", afields) or oa_raw != _projection(output, "kronos_gjc_role_output_attestable.v2", ofields):
        _fail("terminal prior attestable projection mismatches")
    common = ("request_uid", "scope", "candidate_head", "dist_manifest_sha256", "input_slots", "input_artifacts")
    if assignment["request_ref"] != request_ref or any(assignment[field] != request[field] for field in ("request_uid", "run_nonce", "scope", "candidate_head", "dist_manifest_sha256", "input_slots", "input_artifacts")) or output["request_ref"] != request_ref or output["assignment_ref"] != assignment_ref or output["assignment_uid"] != assignment["assignment_uid"] or any(output[field] != request[field] for field in common) or (assignment["role"], output["role"], output["payload_schema"]) != (role, role, output_schema):
        _fail("terminal prior chain graph fields do not agree")
    validate_role_payload(output["payload"], output_schema, current_refs=(request_ref, assignment_ref, output_ref), predecessor_payloads=_predecessor_payloads(output["payload"], output_schema, resolver, authority))
    _slots(assignment["input_slots"], assignment["input_artifacts"])
    created, expires, issued, started, completed, resolved = (_time(value, label) for value, label in ((request["created_at"], "created_at"), (request["expires_at"], "expires_at"), (assignment["issued_at"], "issued_at"), (output["started_at"], "started_at"), (output["completed_at"], "completed_at"), (export["resolved_at"], "resolved_at")))
    if not created < expires <= created + timedelta(hours=1) or assignment["expires_at"] != request["expires_at"] or not (created <= issued <= started <= completed <= resolved <= closed_at <= expires) or not completed < expires:
        _fail("terminal prior chain chronology is invalid")
    if not isinstance(aatt.get("statement"), dict) or aatt["statement"].get("role") != "ORCHESTRATOR" or aatt["statement"].get("purpose") != "GJC_ASSIGNMENT" or assignment["subject_principal_uri"] == aatt["statement"].get("signer_principal_uri"):
        _fail("terminal prior assignment attestation is unauthorized")
    if not isinstance(oatt.get("statement"), dict) or (oatt["statement"].get("role"), oatt["statement"].get("purpose"), oatt["statement"].get("signer_principal_uri")) != (role, "GJC_ROLE_OUTPUT", assignment["subject_principal_uri"]):
        _fail("terminal prior output attestation is unauthorized")
    isolated = AuthorityContext(authority.referenced_lifecycle, authority.current_lifecycle, authority.lifecycle_history, authority.pinned_root_public_key, authority.pinned_root_key_id, authority.pinned_genesis_envelope_sha256, authority.role_validity_caps, InMemoryNonceReplayStore(), authority.validation_policy_bytes, authority.trusted_clock, authority.independent_principals, authority.resolver_implementation, authority.resolver_principal_uri)
    _verify(aatt_raw, aa_raw, "kronos_gjc_assignment_attestable.v2", scope, isolated, closed_at)
    _verify(oatt_raw, oa_raw, "kronos_gjc_role_output_attestable.v2", scope, isolated, closed_at)
def validate_role_payload(
    payload: Mapping[str, Any],
    schema: str,
    *,
    current_refs: Sequence[Mapping[str, Any]] = (),
    predecessor_payloads: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
    resolver: RawArtifactResolver | None = None,
    authority: AuthorityContext | None = None,
) -> None:
    """Public closed-role validator; current_refs rejects self/current graph links."""
    _wire("payload", payload)
    if payload.get("schema") != schema or schema not in ROLE_PREDECESSOR_SCHEMAS: _fail("payload schema mismatches request")
    declared = ROLE_PREDECESSOR_SCHEMAS[schema]
    for path, ref in _path_refs(payload):
        if not any(
            len(path) == len(pattern := tuple(declared_path.split(".")))
            and all(expected == "*" or expected == actual for expected, actual in zip(pattern, path))
            and ref["schema"] in schemas
            for declared_path, schemas in declared.items()
        ):
            _fail("role payload has an unauthorized predecessor")
    current = [_ref(ref) for ref in current_refs]
    if any(_same_ref(ref, old) for _, ref in _path_refs(payload) for old in current):
        _fail("role payload has a self/current reference")
    if schema == "kronos_operator_trace.v2":
        received, started, completed, destroyed = (
            _time(payload[key], key)
            for key in ("assignment_received_at", "attempt_started_at", "attempt_completed_at", "profile_destroyed_at")
        )
        if not received <= started <= completed <= destroyed: _fail("operator attempt chronology is invalid")
        tasks = payload["tasks"]
        if [task["task_id"] for task in tasks] != list(TASK_IDS): _fail("operator tasks are not T01 through T10")
        for task in tasks:
            task_started, task_completed = _time(task["started_at"], "task started_at"), _time(task["completed_at"], "task completed_at")
            if not started <= task_started <= task_completed <= completed or task["elapsed_ms"] > int((task_completed - task_started).total_seconds() * 1000):
                _fail("operator task chronology is invalid")
            _codes(task["failure_codes"], FAILURE_CODES, "task failure codes")
            if task["objective_valid"] != (not task["failure_codes"]): _fail("objective validity mismatches failure codes")
        expected = _canonical_failures(tasks, payload["operator_index"])
        actual = [
            (item["operator_index"], item["task_id"], item["failure_code"], item["evidence_ref"], item["detected_at"])
            for item in payload["objective_failures"]
        ]
        if len(actual) != len({(index, task_id, code) for index, task_id, code, _, _ in actual}):
            _fail("objective failures are not unique")
        if [(index, task_id, code) for index, task_id, code, _, _ in actual] != [(index, task_id, code) for index, task_id, code, _, _ in expected]:
            _fail("objective failures are not the canonical task/failure union")
        by_task = {task["task_id"]: task for task in tasks}
        for _, task_id, _, evidence_ref, detected_at in actual:
            task = by_task[task_id]
            if not _same_ref(evidence_ref, task["trace_ref"]) or not _time(task["completed_at"], "task completed_at") <= _time(detected_at, "failure detected_at") <= completed:
                _fail("objective failure evidence does not bind the completed task trace")
    elif schema == "kronos_task_score_review.v2":
        if len(payload["operator_trace_refs"]) != 2 or len(payload["machine_score_refs"]) != 2: _fail("task-score requires A/B refs")
        if predecessor_payloads is None: _fail("task-score authenticated predecessors are absent")
        traces = []
        machine_scores = []
        for ref in payload["operator_trace_refs"]:
            trace = predecessor_payloads.get((ref["uri"], ref["sha256"]))
            if trace is None or trace.get("schema") != "kronos_operator_trace.v2": _fail("task-score operator trace identity is unavailable")
            traces.append(trace)
        for ref in payload["machine_score_refs"]:
            machine_score = predecessor_payloads.get((ref["uri"], ref["sha256"]))
            if machine_score is None: _fail("task-score machine-score identity is unavailable")
            _machine_score(machine_score)
            machine_scores.append(machine_score)
        if [trace["operator_index"] for trace in traces] != ["A", "B"] or [score["operator_index"] for score in machine_scores] != ["A", "B"]:
            _fail("task-score predecessors are not A/B ordered")
        expected = []
        for trace in traces:
            validate_role_payload(trace, "kronos_operator_trace.v2")
            expected.extend(trace["objective_failures"])
        if canonical_bytes(payload["objective_failures"]) != canonical_bytes(expected):
            _fail("task-score objective failures are not the byte-exact canonical operator union")
        actual = [(item["operator_index"], item["task_id"], item["failure_code"]) for item in payload["objective_failures"]]
        if len(actual) != len(set(actual)): _fail("task-score objective failures are not unique")
        for o in ("A", "B"):
            for d in DIMENSIONS:
                if payload["dimensions"][o][d]["score"] != 10 * sum(payload["bitmaps"][o][d]): _fail("dimension must equal 10 times true bitmap count")
                if any(reviewed and not scored for reviewed, scored in zip(payload["bitmaps"][o][d], machine_scores[("A", "B").index(o)]["bitmaps"][d])):
                    _fail("reviewer bitmap raises a machine false bit")
        if payload["raised_false_bits"] != []: _fail("false-to-true bitmap changes are prohibited")
        order = [(("A", "B").index(x["operator_index"]), DIMENSIONS.index(x["dimension"]), x["bit_index"]) for x in payload["disputes"]]
        if order != sorted(order) or len(set(order)) != len(order): _fail("disputes are not semantically ordered")
        _codes(payload["blocking_codes"], TASK_BLOCKING_CODES, "task blocking codes")
        passed = all(payload["dimensions"][o][d]["score"] >= 90 for o in ("A", "B") for d in DIMENSIONS) and not payload["objective_failures"] and not payload["blocking_codes"]
        if (payload["verdict"] == "PASS") != passed: _fail("task-score PASS equation is invalid")
    elif schema == "kronos_architect_review.v2":
        if payload["invariants_checked"] != list(INVARIANTS): _fail("architect seven invariants are not in frozen order")
        order = [(SEVERITIES.index(x["severity"]), x["code"], x["location"]) for x in payload["findings"]]
        if order != sorted(order) or len({x["finding_uid"] for x in payload["findings"]}) != len(payload["findings"]): _fail("architect findings are not ordered or uniquely identified")
        if any(not x["evidence_refs"] for x in payload["findings"]): _fail("architect findings require evidence")
        for finding in payload["findings"]: _ordered_refs(finding["evidence_refs"])
        _codes(payload["blocking_codes"], ARCHITECT_BLOCKING_CODES, "architect blocking codes")
        expected = [x["code"] for x in payload["findings"] if x["severity"] in ("CRITICAL", "HIGH")]
        if payload["blocking_codes"] != [code for code in ARCHITECT_BLOCKING_CODES if code in expected]: _fail("architect blocking codes do not aggregate findings")
        if (payload["verdict"] == "PASS") != (not payload["blocking_codes"]): _fail("architect PASS equation is invalid")
    elif schema == "kronos_critic_review.v2":
        checks = payload["claim_checks"]
        if len(checks) != 100 or [x["claim_id"] for x in checks] != sorted(x["claim_id"] for x in checks) or len({x["claim_id"] for x in checks}) != 100: _fail("critic needs exactly 100 ordered claim checks")
        if any(not x["evidence_refs"] for x in checks): _fail("critic claim checks require evidence")
        for check in checks: _ordered_refs(check["evidence_refs"])
        if [(x["claim_id"], x["required_schema"]) for x in payload["missing_evidence"]] != sorted((x["claim_id"], x["required_schema"]) for x in payload["missing_evidence"]) or len({x["claim_id"] for x in payload["missing_evidence"]}) != len(payload["missing_evidence"]): _fail("missing evidence is not ordered")
        if [x["change_id"] for x in payload["required_changes"]] != sorted(x["change_id"] for x in payload["required_changes"]): _fail("required changes are not ordered")
        _codes(payload["blocking_codes"], CRITIC_BLOCKING_CODES, "critic blocking codes")
        expected = set()
        if any(x["result"] == "FAIL" for x in checks): expected.add("CLAIM_FALSE")
        if payload["missing_evidence"]: expected.add("MISSING_EVIDENCE")
        if payload["required_changes"]: expected.add("TRUTH_CONFLICT")
        if payload["blocking_codes"] != [code for code in CRITIC_BLOCKING_CODES if code in expected]: _fail("critic blocking codes do not aggregate findings")
        if (payload["verdict"] == "APPROVE") != (not payload["blocking_codes"]): _fail("critic APPROVE equation is invalid")
    elif schema == "kronos_executor_qa_review.v2":
        commands = payload["commands"]
        if predecessor_payloads is None: _fail("executor command manifest is absent")
        manifest = predecessor_payloads.get((payload["command_manifest_ref"]["uri"], payload["command_manifest_ref"]["sha256"]))
        if not isinstance(manifest, Mapping) or not isinstance(manifest.get("commands"), list): _fail("executor command manifest identity is unavailable")
        manifest_commands = manifest["commands"]
        if [command["command_id"] for command in commands] != [command.get("command_id") for command in manifest_commands]:
            _fail("executor commands are not in command-manifest order")
        if any(command["command_sha256"] != manifest_command.get("command_sha256") for command, manifest_command in zip(commands, manifest_commands)):
            _fail("executor command identities do not match the manifest")
        for failure in payload["failures"]: _ordered_refs(failure["evidence_refs"])
        positions = {command["command_id"]: index for index, command in enumerate(commands)}
        failure_order = [(positions.get(failure["command_id"], len(commands)), EXECUTOR_FAILURE_CODES.index(failure["code"])) for failure in payload["failures"]]
        if failure_order != sorted(failure_order) or len(set((failure["command_id"], failure["code"]) for failure in payload["failures"])) != len(payload["failures"]):
            _fail("executor failures are not in command-manifest order")
        expected = [("NONZERO", command["command_id"]) for command in commands if command["exit_code"] != 0]
        counter_codes = (("SKIP", "skip_count"), ("XFAIL", "xfail_count"), ("XPASS", "xpass_count"), ("WARNING_SUPPRESSION", "warning_suppression_count"))
        anchor = commands[0]["command_id"] if commands else ""
        expected.extend((code, anchor) for code, field in counter_codes if payload[field] != 0)
        if payload["head_before"] != payload["head_after"]: expected.append(("HEAD_DRIFT", anchor))
        if payload["tree_before"] != payload["tree_after"]: expected.append(("TREE_DRIFT", anchor))
        if payload["dist_before"] != payload["dist_after"]: expected.append(("DIST_DRIFT", anchor))
        if not payload["worktree_clean_before"] or not payload["worktree_clean_after"]: expected.append(("DIRTY_WORKTREE", anchor))
        expected.sort(key=lambda item: (positions.get(item[1], len(commands)), EXECUTOR_FAILURE_CODES.index(item[0])))
        actual = [(failure["code"], failure["command_id"]) for failure in payload["failures"]]
        if actual != expected: _fail("executor failures do not exactly aggregate QA state")
        identities_equal = (payload["head_before"], payload["tree_before"], payload["dist_before"]) == (payload["head_after"], payload["tree_after"], payload["dist_after"])
        passed = identities_equal and all(payload[field] == 0 for _, field in counter_codes) and not payload["failures"] and payload["worktree_clean_before"] and payload["worktree_clean_after"]
        if (payload["verdict"] == "PASS") != passed: _fail("executor PASS equation is invalid")
    else:
        _codes(payload["blocking_codes"], TERMINAL_BLOCKING_CODES, "terminal blocking codes")
        resolutions = payload["re_resolutions"]
        if [x["scope"] for x in resolutions] != list(PRIOR_SCOPES): _fail("terminal prior chains are not in frozen scope order")
        outputs = {
            "OPERATOR_A": payload["operator_output_refs"][0], "OPERATOR_B": payload["operator_output_refs"][1],
            "TASK_SCORE": payload["task_score_output_ref"], "ARCHITECT_REVIEW": payload["architect_output_ref"],
            "CRITIC_REVIEW": payload["critic_output_ref"], "EXECUTOR_QA": payload["executor_qa_output_ref"],
        }
        if any(resolution["output_ref"] != outputs[resolution["scope"]] for resolution in resolutions): _fail("terminal re-resolution output identity mismatches")
        if resolver is None or authority is None: _fail("terminal resolver context is absent")
        _, point_a_raw, _, _ = _resolve(resolver, payload["score_ref_a"], "kronos_point_score.v2", authority)
        _, point_b_raw, _, _ = _resolve(resolver, payload["score_ref_b"], "kronos_point_score.v2", authority)
        _resolve(resolver, payload["final_map_ref"], "kronos_final_map.v2", authority)
        if point_a_raw != point_b_raw: _fail("terminal point-score raw bytes mismatch")
        closed_at = _time(payload["closed_at"], "closed_at")
        for resolution in resolutions:
            _verify_prior_chain(resolution, resolver, authority, closed_at)
        if (payload["result"] == "CLOSED") != (not payload["blocking_codes"] and payload["release_eligible"] and payload["default_eligible"]): _fail("terminal closure equation is invalid")
def _payload(payload: Mapping[str, Any], schema: str) -> None:
    validate_role_payload(payload, schema)

def _validate_receipt_graph(*, request_ref: Mapping[str, Any], export_ref: Mapping[str, Any], resolver: RawArtifactResolver, authority: AuthorityContext, now: datetime) -> bytes:
    try:
        now = _whole_second(now)
        policy_digest = hashlib.sha256(authority.validation_policy_bytes).hexdigest()
        request_ref, request_raw, request, _ = _resolve(resolver, request_ref, "kronos_gjc_request_instance.v2", authority); _wire("request", request)
        export_ref, _, export, export_record = _resolve(resolver, export_ref, "kronos_gjc_export.v2", authority); _wire("export", export)
        if (export["resolver"], export["selector"], export_record.resolver, export_record.selector) != (authority.resolver_implementation, "raw", authority.resolver_implementation, "raw") or export_record.resolved_at != export["resolved_at"] or export_record.resolver_principal_uri != export["resolver_principal_uri"] or export["request_ref"] != request_ref: _fail("export does not bind pinned resolution")
        role, scopes, policy, output_schema = RULES.get(request["request_type"], (None, (), None, None))
        if (request["required_role"], request["independence_policy"], request["required_output_schema"]) != (role, policy, output_schema) or request["scope"] not in scopes: _fail("request tuple is unauthorized")
        created, expires = _time(request["created_at"], "created_at"), _time(request["expires_at"], "expires_at")
        if not created < expires <= created + timedelta(hours=1): _fail("request lifetime is invalid")
        _slots(request["input_slots"], request["input_artifacts"])
        template_ref, template_raw, template, _ = _resolve(resolver, request["template_ref"], "kronos_gjc_request_template.v2", authority); _wire("template", template)
        template_fields = ("template_key", "request_type", "required_role", "scope", "candidate_head", "dist_manifest_sha256", "input_slots", "required_output_schema", "independence_policy")
        if template_raw != _projection(request, "kronos_gjc_request_template.v2", template_fields): _fail("request template projection mismatches")
        assignment_ref, _, assignment, _ = _resolve(resolver, export["assignment_ref"], "kronos_gjc_assignment.v2", authority); _wire("assignment", assignment)
        output_ref, _, output, _ = _resolve(resolver, export["output_ref"], "kronos_gjc_role_output.v2", authority); _wire("output", output)
        aa_ref, aa_raw, aa, _ = _resolve(resolver, assignment["attestable_ref"], "kronos_gjc_assignment_attestable.v2", authority); _wire("assignmentAttestable", aa)
        oa_ref, oa_raw, oa, _ = _resolve(resolver, output["attestable_ref"], "kronos_gjc_role_output_attestable.v2", authority); _wire("outputAttestable", oa)
        aatt_ref, aatt_raw, aatt, _ = _resolve(resolver, assignment["attestation_ref"], "kronos_attestation.v2", authority)
        oatt_ref, oatt_raw, oatt, _ = _resolve(resolver, output["attestation_ref"], "kronos_attestation.v2", authority)
        afields = ("request_ref", "assignment_uid", "request_uid", "run_nonce", "subject_principal_uri", "role", "scope", "candidate_head", "dist_manifest_sha256", "input_slots", "input_artifacts", "issued_at", "expires_at")
        ofields = ("request_ref", "assignment_ref", "request_uid", "assignment_uid", "subject_principal_uri", "role", "scope", "candidate_head", "dist_manifest_sha256", "input_slots", "input_artifacts", "started_at", "completed_at", "status", "payload_schema", "payload")
        if aa_raw != _projection(assignment, "kronos_gjc_assignment_attestable.v2", afields) or oa_raw != _projection(output, "kronos_gjc_role_output_attestable.v2", ofields): _fail("attestable projection mismatches")
        common = ("request_uid", "scope", "candidate_head", "dist_manifest_sha256", "input_slots", "input_artifacts")
        if any(assignment[field] != request[field] for field in ("request_uid", "run_nonce", "scope", "candidate_head", "dist_manifest_sha256", "input_slots", "input_artifacts")) or assignment["request_ref"] != request_ref or any(output[field] != request[field] for field in common) or output["request_ref"] != request_ref or output["assignment_ref"] != assignment_ref or output["assignment_uid"] != assignment["assignment_uid"]: _fail("graph fields do not agree")
        if output["role"] != role or assignment["role"] != role or output["payload_schema"] != output_schema or output["subject_principal_uri"] != assignment["subject_principal_uri"]: _fail("role payload authorization mismatch")
        independent = authority.independent_principals.get(policy)
        if not isinstance(independent, frozenset) or not independent: _fail("authenticated independence evidence is absent")
        if assignment["subject_principal_uri"] in independent: _fail("trusted prior chain independence is violated")
        validate_role_payload(output["payload"], output_schema, current_refs=(request_ref, assignment_ref, output_ref), predecessor_payloads=_predecessor_payloads(output["payload"], output_schema, resolver, authority), resolver=resolver, authority=authority); _slots(assignment["input_slots"], assignment["input_artifacts"])
        issued, started, completed, resolved = (_time(value, label) for value, label in ((assignment["issued_at"], "issued_at"), (output["started_at"], "started_at"), (output["completed_at"], "completed_at"), (export["resolved_at"], "resolved_at")))
        if assignment["expires_at"] != request["expires_at"] or not (created <= issued <= started <= completed <= resolved <= now <= expires) or not completed < expires: _fail("bridge chronology is invalid")
        if not isinstance(aatt.get("statement"), dict) or aatt["statement"].get("role") != "ORCHESTRATOR" or aatt["statement"].get("purpose") != "GJC_ASSIGNMENT" or assignment["subject_principal_uri"] == aatt["statement"].get("signer_principal_uri"): _fail("assignment attestation signer is unauthorized")
        if not isinstance(oatt.get("statement"), dict) or (oatt["statement"].get("role"), oatt["statement"].get("purpose"), oatt["statement"].get("signer_principal_uri")) != (role, "GJC_ROLE_OUTPUT", assignment["subject_principal_uri"]): _fail("output attestation signer is unauthorized")
        _verify(aatt_raw, aa_raw, "kronos_gjc_assignment_attestable.v2", assignment["scope"], authority, now); _verify(oatt_raw, oa_raw, "kronos_gjc_role_output_attestable.v2", output["scope"], authority, now)
        receipt = {"schema":"kronos_gjc_validation_receipt.v2", "request_ref":request_ref, "template_ref":template_ref, "assignment_attestable_ref":aa_ref, "assignment_attestation_ref":aatt_ref, "assignment_ref":assignment_ref, "output_attestable_ref":oa_ref, "output_attestation_ref":oatt_ref, "output_ref":output_ref, "export_ref":export_ref, "validated_subject_principal_uri":assignment["subject_principal_uri"], "validated_role":role, "validated_scope":assignment["scope"], "candidate_head":assignment["candidate_head"], "dist_manifest_sha256":assignment["dist_manifest_sha256"], "input_slots":assignment["input_slots"], "input_artifacts":assignment["input_artifacts"], "validation_policy_sha256":policy_digest, "status":"VALID", "resolved_at":export["resolved_at"], "validated_at":now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        _wire("receipt", receipt)
        receipt_raw = canonical_bytes(receipt)
        return receipt_raw
    except BridgeValidationError: raise
    except (AttributeError, KeyError, TypeError, ValueError, AuthorityVerificationError) as exc: raise BridgeValidationError("bridge wire validation failed") from exc
def validate_and_issue_receipt(*, request_ref: Mapping[str, Any], export_ref: Mapping[str, Any], resolver: RawArtifactResolver, authority: AuthorityContext, request_store: RequestConsumptionStore) -> bytes:
    request_ref, request_raw, _, _ = _resolve(resolver, request_ref, "kronos_gjc_request_instance.v2", authority)
    receipt_raw = _validate_receipt_graph(
        request_ref=request_ref,
        export_ref=export_ref,
        resolver=resolver,
        authority=authority,
        now=authority.trusted_clock(),
    )
    try:
        stored = request_store.store_receipt_if_absent(hashlib.sha256(request_raw).hexdigest(), receipt_raw)
    except Exception as exc:
        raise BridgeValidationError("transactional receipt storage failed") from exc
    if stored is None:
        _fail("request was already consumed")
    if stored != receipt_raw:
        _fail("transactional receipt store returned different bytes")
    return stored

def validate_existing_receipt_graph(receipt_ref: Mapping[str, Any], resolver: RawArtifactResolver, authority: AuthorityContext) -> bytes:
    """Revalidate an already-issued receipt without consuming its request."""
    try:
        _, receipt_raw, receipt, _ = _resolve(resolver, receipt_ref, "kronos_gjc_validation_receipt.v2", authority)
        _wire("receipt", receipt)
        validated_at = _time(receipt["validated_at"], "validated_at")
        verification_authority = replace(authority, nonce_store=InMemoryNonceReplayStore())
        validated = _validate_receipt_graph(
            request_ref=receipt["request_ref"],
            export_ref=receipt["export_ref"],
            resolver=resolver,
            authority=verification_authority,
            now=validated_at,
        )
        if validated != receipt_raw:
            _fail("receipt field bindings mismatch")
        return receipt_raw
    except BridgeValidationError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, AuthorityVerificationError) as exc:
        raise BridgeValidationError("bridge wire validation failed") from exc
