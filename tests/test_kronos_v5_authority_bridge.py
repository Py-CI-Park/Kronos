"""Golden request-to-receipt graphs and semantic tamper coverage for the GJC bridge."""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from stom_rl.v5_authority import ATTESTATION_DOMAIN, LIFECYCLE_DOMAIN, InMemoryNonceReplayStore, canonical_bytes, sha256_identity
from stom_rl.v5_authority_bridge import AuthorityContext, BridgeValidationError, INPUT_SLOT_NAMES, InMemoryRequestConsumptionStore, LiteralRawResolver, PRIOR_SCOPES, RULES, validate_and_issue_receipt, validate_existing_receipt_graph, validate_role_payload

ROOT = Path(__file__).resolve().parents[1]
VECTOR = json.loads((ROOT / "tests" / "data" / "kronos_gjc_bridge_v2_vectors.json").read_text(encoding="utf-8"))
CAPTURE = ROOT / "scripts" / "capture_dashboard_v5_tasks.mjs"
SCORE = ROOT / "scripts" / "score_dashboard_v5_tasks.py"
REVIEW = ROOT / "scripts" / "review_dashboard_v5_task_scores.py"
TASK_FIXTURE = ROOT / "tests" / "data" / "kronos_v5_task_fixture.json"
UTC = "2026-01-01T00:00:00Z"
SCOPES = tuple(scope for _, scopes, _, _ in RULES.values() for scope in sorted(scopes))
TASK_IDS = tuple(f"T{i:02d}" for i in range(1, 11))
DIMENSIONS = ("U", "L", "J")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _sign(key: Ed25519PrivateKey, domain: bytes, statement: dict[str, Any]) -> str:
    return _b64(key.sign(domain + canonical_bytes(statement)))


def _ref(uri: str, raw: bytes, schema: str) -> dict[str, Any]:
    return {"uri": uri, "sha256": hashlib.sha256(raw).hexdigest(), "byte_length": len(raw), "schema": schema}


def _stub(name: str, schema: str) -> dict[str, Any]:
    return _ref(f"agent://{name}", canonical_bytes({"schema": schema}), schema)


def _capture_trace_files(tmp_path: Path, operator: str) -> tuple[Path, Path]:
    trace_path = tmp_path / f"trace-{operator}.json"
    evidence_dir = tmp_path / f"evidence-{operator}"
    result = subprocess.run(
        ["node", str(CAPTURE), "--fixture", str(TASK_FIXTURE), "--operator", operator, "--evidence-dir", str(evidence_dir), "--out", str(trace_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return trace_path, evidence_dir


def _load_capture_objects(trace_path: Path, evidence_dir: Path) -> tuple[dict[str, Any], bytes, dict[str, bytes]]:
    raw = trace_path.read_bytes()
    trace = json.loads(raw)
    assert raw == canonical_bytes(trace)
    objects: dict[str, bytes] = {}
    refs = [trace["fixture_ref"], trace["instrument_ref"]]
    for task in trace["tasks"]:
        refs.append(task["trace_ref"])
        refs.extend(task["screenshot_refs"])
    for ref in refs:
        objects[ref["uri"]] = (evidence_dir / ref["sha256"]).read_bytes()
    return trace, raw, objects


def _capture_trace(tmp_path: Path, operator: str) -> tuple[dict[str, Any], bytes, dict[str, bytes]]:
    return _load_capture_objects(*_capture_trace_files(tmp_path, operator))


def _task_review_ref(path: Path, raw: bytes, schema: str) -> dict[str, Any]:
    return _ref(f"agent://task-review-{path.name}", raw, schema)


def _score_trace(tmp_path: Path, trace_path: Path, evidence_dir: Path, operator: str) -> tuple[dict[str, Any], bytes, Path]:
    score_path = tmp_path / f"score-{operator}.json"
    result = subprocess.run(
        [sys.executable, str(SCORE), "--trace", str(trace_path), "--evidence-dir", str(evidence_dir), "--out", str(score_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    raw = score_path.read_bytes()
    value = json.loads(raw)
    assert raw == canonical_bytes(value)
    return value, raw, score_path


def _review_scores(tmp_path: Path, trace_a: Path, evidence_a: Path, trace_b: Path, evidence_b: Path, score_a: Path, score_b: Path) -> tuple[dict[str, Any], bytes, Path]:
    review_path = tmp_path / "task-review.json"
    result = subprocess.run(
        [sys.executable, str(REVIEW), "--trace-a", str(trace_a), "--evidence-dir-a", str(evidence_a), "--trace-b", str(trace_b), "--evidence-dir-b", str(evidence_b), "--machine-score-a", str(score_a), "--machine-score-b", str(score_b), "--out", str(review_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    raw = review_path.read_bytes()
    value = json.loads(raw)
    assert raw == canonical_bytes(value)
    return value, raw, review_path


def _freeze_referenced_objects(objects: dict[str, bytes]) -> None:
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if set(value) == {"uri", "sha256", "byte_length", "schema"} and value["uri"] not in objects:
                raw = canonical_bytes({"schema": value["schema"]})
                objects[value["uri"]] = raw
                value.update(_ref(value["uri"], raw, value["schema"]))
            else:
                for child in value.values():
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    for raw in tuple(objects.values()):
        visit(json.loads(raw))


def _keys() -> dict[str, Ed25519PrivateKey]:
    return {name: Ed25519PrivateKey.from_private_bytes(bytes([index]) * 32) for index, name in enumerate(("root", "orch", *SCOPES))}


def _lifecycle(keys: dict[str, Ed25519PrivateKey]) -> bytes:
    principals = []
    for scope in SCOPES:
        role = next(role for role, scopes, _, _ in RULES.values() if scope in scopes)
        key = keys[scope]
        principals.append({"principal_uri": f"agent://{scope.lower()}", "roles": [role], "scopes": [scope], "status": "ACTIVE", "keys": [{"key_id": f"00000000-0000-4000-8000-{SCOPES.index(scope)+10:012d}", "algorithm": "Ed25519", "public_key_encoding": "base64url-no-pad", "public_key": _b64(key.public_key().public_bytes_raw()), "status": "ACTIVE", "not_before": UTC, "not_after": "2026-01-02T00:00:00Z", "revoked_at": None, "revocation_reason": None}]})
    principals.append({"principal_uri": "agent://orchestrator", "roles": ["ORCHESTRATOR"], "scopes": sorted([*SCOPES, "AUTHORITY_LIFECYCLE"]), "status": "ACTIVE", "keys": [{"key_id": "00000000-0000-4000-8000-000000000001", "algorithm": "Ed25519", "public_key_encoding": "base64url-no-pad", "public_key": _b64(keys["orch"].public_key().public_bytes_raw()), "status": "ACTIVE", "not_before": UTC, "not_after": "2026-01-02T00:00:00Z", "revoked_at": None, "revocation_reason": None}]})
    statement = {"schema": "kronos_authority_lifecycle_statement.v2", "authority_epoch": "00000000-0000-4000-8000-0000000000aa", "sequence": 1, "previous_authority_envelope_sha256": "0" * 64, "roster_version": 1, "principals": sorted(principals, key=lambda x: x["principal_uri"]), "issued_at": UTC, "effective_at": UTC, "expires_at": "2026-01-02T00:00:00Z", "signer_principal_uri": "agent://orchestrator", "signer_key_id": "00000000-0000-4000-8000-000000000001", "algorithm": "Ed25519", "signature_encoding": "base64url-no-pad"}
    return canonical_bytes({"schema": "kronos_authority_lifecycle.v2", "statement": statement, "signature": _sign(keys["root"], LIFECYCLE_DOMAIN, statement)})


def _attestation(key: Ed25519PrivateKey, lifecycle: bytes, *, uid: str, signer: str, key_id: str, role: str, scope: str, purpose: str, payload: bytes, nonce: bytes) -> bytes:
    statement = {"schema": "kronos_attestation_statement.v2", "attestation_uid": uid, "payload_schema": "kronos_gjc_assignment_attestable.v2" if purpose == "GJC_ASSIGNMENT" else "kronos_gjc_role_output_attestable.v2", "payload_sha256": hashlib.sha256(payload).hexdigest(), "payload_byte_length": len(payload), "signer_principal_uri": signer, "role": role, "key_id": key_id, "algorithm": "Ed25519", "signature_encoding": "base64url-no-pad", "authority_envelope_sha256": sha256_identity(json.loads(lifecycle)), "issued_at": "2026-01-01T00:00:04Z", "expires_at": "2026-01-01T01:00:00Z", "nonce": _b64(nonce), "purpose": purpose}
    return canonical_bytes({"schema": "kronos_attestation.v2", "statement": statement, "signature": _sign(key, ATTESTATION_DOMAIN, statement)})


def _screenshot(scope: str, n: int, put: Any | None = None) -> dict[str, Any]:
    operator = "A" if scope == "OPERATOR_A" else "B"
    png_raw = f"png:{scope}:{n}".encode()
    png_ref = _ref(f"agent://png-{scope.lower()}-{n}", png_raw, "image/png")
    wrapper = {"schema": "kronos_screenshot.v2", "png_ref": png_ref, "dimensions": {"width": 2, "height": 1}, "scenario": {"operator_index": operator, "task_id": f"T{n:02d}", "surface": "mission-control", "viewport": {"width": 1280, "height": 960, "theme": "light", "keyboard_only": False}}}
    if put is None:
        raw = canonical_bytes(wrapper)
        return _ref(f"agent://screenshot-{scope.lower()}-{n}", raw, "kronos_screenshot.v2")
    return put(f"screenshot-{scope.lower()}-{n}", wrapper, "kronos_screenshot.v2")


def _operator(scope: str, put: Any | None = None) -> dict[str, Any]:
    task = lambda n: {"task_id": f"T{n:02d}", "started_at": "2026-01-01T00:00:05Z", "completed_at": "2026-01-01T00:00:05Z", "elapsed_ms": 0, "action_count": 0, "objective_valid": True, "submitted_facts": [{"code": "/fixture/fact", "detail": f"{scope}-{n}"}], "trace_ref": _stub(f"trace-{scope}-{n}", "kronos_task_trace.v2"), "screenshot_refs": [_screenshot(scope, n, put)], "failure_codes": []}
    return {"schema": "kronos_operator_trace.v2", "attempt_uid": f"00000000-0000-4000-8000-{SCOPES.index(scope)+100:012d}", "operator_index": "A" if scope == "OPERATOR_A" else "B", "browser_pid": 1, "profile_uid": "00000000-0000-4000-8000-000000000222", "fixture_ref": _stub("fixture", "kronos_fixture.v2"), "instrument_ref": _stub("instrument", "kronos_instrument.v2"), "assignment_received_at": "2026-01-01T00:00:04Z", "attempt_started_at": "2026-01-01T00:00:05Z", "attempt_completed_at": "2026-01-01T00:00:06Z", "tasks": [task(n) for n in range(1, 11)], "objective_failures": [], "profile_destroyed_at": "2026-01-01T00:00:07Z"}


def _payload(scope: str, put: Any, prior_chains: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] | None = None) -> dict[str, Any]:
    pre, cmap = _stub("pre", "kronos_preclosure.v2"), _stub("map", "kronos_candidate_map.v2")
    if scope.startswith("OPERATOR_"):
        return _operator(scope, put)
    if scope == "TASK_SCORE":
        a, b = put("operator-a", _operator("OPERATOR_A", put), "kronos_operator_trace.v2"), put("operator-b", _operator("OPERATOR_B", put), "kronos_operator_trace.v2")
        ma = put("score-a", {"schema": "kronos_machine_task_score.v2", "operator_index": "A", "bitmaps": {d: [True] * 10 for d in "ULJ"}}, "kronos_machine_task_score.v2")
        mb = put("score-b", {"schema": "kronos_machine_task_score.v2", "operator_index": "B", "bitmaps": {d: [True] * 10 for d in "ULJ"}}, "kronos_machine_task_score.v2")
        bitmaps = {o: {d: [True] * 10 for d in "ULJ"} for o in "AB"}
        dimensions = {o: {d: {"score": 100, "evidence_refs": [ma if o == "A" else mb]} for d in "ULJ"} for o in "AB"}
        return {"schema": "kronos_task_score_review.v2", "operator_trace_refs": [a, b], "machine_score_refs": [ma, mb], "verdict": "PASS", "dimensions": dimensions, "disputes": [], "raised_false_bits": [], "objective_failures": [], "bitmaps": bitmaps, "blocking_codes": []}
    if scope == "ARCHITECT_REVIEW":
        return {"schema": "kronos_architect_review.v2", "preclosure_ref": pre, "candidate_map_ref": cmap, "verdict": "PASS", "invariants_checked": ["ACYCLIC_GRAPH", "CANONICAL_BYTES", "AUTHORITY_CHAIN", "CLAIM_PRESERVATION", "HEAD_DIST_IMMUTABILITY", "REGISTRY_API_CONTRACT", "ACCOUNTING_PROTOCOL"], "findings": [], "blocking_codes": []}
    if scope == "CRITIC_REVIEW":
        checks = [{"claim_id": f"C{i:03d}", "result": "PASS", "evidence_refs": [pre], "reason_code": "OK"} for i in range(1, 101)]
        return {"schema": "kronos_critic_review.v2", "preclosure_ref": pre, "candidate_map_ref": cmap, "verdict": "APPROVE", "claim_checks": checks, "missing_evidence": [], "required_changes": [], "blocking_codes": []}
    if scope == "EXECUTOR_QA":
        artifact = _stub("qa", "kronos_qa_artifact.v2"); manifest = put("manifest", {"schema": "kronos_command_manifest.v2", "commands": [{"command_id": "cmd", "command_sha256": "c" * 64}]}, "kronos_command_manifest.v2")
        return {"schema": "kronos_executor_qa_review.v2", "preclosure_ref": pre, "candidate_map_ref": cmap, "command_manifest_ref": manifest, "qa_artifact_refs": [artifact], "head_before": "head", "head_after": "head", "tree_before": "tree", "tree_after": "tree", "dist_before": "d" * 64, "dist_after": "d" * 64, "skip_count": 0, "xfail_count": 0, "xpass_count": 0, "warning_suppression_count": 0, "verdict": "PASS", "failures": [], "worktree_clean_before": True, "worktree_clean_after": True, "commands": [{"command_id": "cmd", "command_sha256": "c" * 64, "exit_code": 0, "duration_ms": 0, "result_ref": artifact}]}
    if prior_chains is None:
        outputs = [_stub(f"output-{s}", "kronos_gjc_role_output.v2") for s in PRIOR_SCOPES]
        resolutions = [{"scope": s, "export_ref": _stub(f"export-{s}", "kronos_gjc_export.v2"), "assignment_ref": _stub(f"assignment-{s}", "kronos_gjc_assignment.v2"), "output_ref": outputs[i]} for i, s in enumerate(PRIOR_SCOPES)]
    else:
        outputs = [prior_chains[s][2] for s in PRIOR_SCOPES]
        resolutions = [{"scope": s, "export_ref": prior_chains[s][0], "assignment_ref": prior_chains[s][1], "output_ref": prior_chains[s][2]} for s in PRIOR_SCOPES]
    point = put("point", {"schema": "kronos_point_score.v2"}, "kronos_point_score.v2")
    return {"schema": "kronos_terminal_closure.v2", "final_map_ref": _stub("final", "kronos_final_map.v2"), "score_ref_a": point, "score_ref_b": point, "architect_output_ref": outputs[3], "critic_output_ref": outputs[4], "executor_qa_output_ref": outputs[5], "operator_output_refs": outputs[:2], "task_score_output_ref": outputs[2], "re_resolutions": resolutions, "head": "head", "tree": "tree", "dist_manifest_sha256": "d" * 64, "worktree_clean": True, "score_effective_total": 100, "category_totals": {"U": 1, "L": 1, "J": 1}, "release_eligible": True, "default_eligible": True, "result": "CLOSED", "blocking_codes": [], "closed_at": "2026-01-01T00:00:08Z"}


def _graph(scope: str) -> tuple[dict[str, Any], dict[str, Any], LiteralRawResolver, AuthorityContext]:
    keys, lifecycle, objects = _keys(), None, {}
    lifecycle = _lifecycle(keys)
    def put(name: str, value: dict[str, Any], schema: str) -> dict[str, Any]:
        raw = canonical_bytes(value); uri = f"agent://{scope.lower()}-{name}"; objects[uri] = raw; return _ref(uri, raw, schema)
    kind, (role, scopes, policy, output_schema) = next((kind, rule) for kind, rule in RULES.items() if scope in rule[1])
    slots, bindings = [{"name": "fixture", "schema": "kronos_fixture.v2", "required": True}], [{"name": "fixture", "artifact_ref": _stub("bound-fixture", "kronos_fixture.v2")}]
    template = {"schema": "kronos_gjc_request_template.v2", "template_key": scope.lower(), "request_type": kind, "required_role": role, "scope": scope, "candidate_head": "a" * 40, "dist_manifest_sha256": "b" * 64, "input_slots": slots, "required_output_schema": output_schema, "independence_policy": policy}
    template_ref = put("template", template, "kronos_gjc_request_template.v2")
    request = {"schema": "kronos_gjc_request_instance.v2", "template_ref": template_ref, **{k: template[k] for k in template if k != "schema"}, "input_artifacts": bindings, "request_uid": f"00000000-0000-4000-8000-{SCOPES.index(scope)+1:012d}", "run_nonce": "A" * 43, "nonce": "B" * 43, "created_at": "2026-01-01T00:00:01Z", "expires_at": "2026-01-01T01:00:00Z"}
    request_ref = put("request", request, "kronos_gjc_request_instance.v2")
    subject = f"agent://{scope.lower()}"; key_id = f"00000000-0000-4000-8000-{SCOPES.index(scope)+10:012d}"
    aa = {"schema": "kronos_gjc_assignment_attestable.v2", "request_ref": request_ref, "assignment_uid": f"00000000-0000-4000-8000-{SCOPES.index(scope)+50:012d}", "request_uid": request["request_uid"], "run_nonce": request["run_nonce"], "subject_principal_uri": subject, "role": role, "scope": scope, "candidate_head": request["candidate_head"], "dist_manifest_sha256": request["dist_manifest_sha256"], "input_slots": slots, "input_artifacts": bindings, "issued_at": "2026-01-01T00:00:04Z", "expires_at": request["expires_at"]}
    aa_ref = put("aa", aa, "kronos_gjc_assignment_attestable.v2")
    aatt_ref = put("aatt", json.loads(_attestation(keys["orch"], lifecycle, uid=f"00000000-0000-4000-8000-{SCOPES.index(scope)+70:012d}", signer="agent://orchestrator", key_id="00000000-0000-4000-8000-000000000001", role="ORCHESTRATOR", scope=scope, purpose="GJC_ASSIGNMENT", payload=objects[aa_ref["uri"]], nonce=bytes([20 + SCOPES.index(scope)]) * 32)), "kronos_attestation.v2")
    assignment = {"schema": "kronos_gjc_assignment.v2", "attestable_ref": aa_ref, "attestation_ref": aatt_ref, **{k: aa[k] for k in aa if k != "schema"}}
    assignment_ref = put("assignment", assignment, "kronos_gjc_assignment.v2")
    prior_chains: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] | None = None
    if scope == "TERMINAL_CLOSURE":
        prior_chains = {}
        for prior_scope in PRIOR_SCOPES:
            _, prior_export, prior_resolver, _ = _graph(prior_scope)
            objects.update(prior_resolver._objects)
            prior_export_object = json.loads(prior_resolver._objects[prior_export["uri"]])
            prior_chains[prior_scope] = (prior_export, prior_export_object["assignment_ref"], prior_export_object["output_ref"])
    payload = _payload(scope, put, prior_chains)
    oa = {"schema": "kronos_gjc_role_output_attestable.v2", "request_ref": request_ref, "assignment_ref": assignment_ref, "request_uid": request["request_uid"], "assignment_uid": aa["assignment_uid"], "subject_principal_uri": subject, "role": role, "scope": scope, "candidate_head": request["candidate_head"], "dist_manifest_sha256": request["dist_manifest_sha256"], "input_slots": slots, "input_artifacts": bindings, "started_at": "2026-01-01T00:00:05Z", "completed_at": "2026-01-01T00:00:06Z", "status": "COMPLETED", "payload_schema": output_schema, "payload": payload}
    oa_ref = put("oa", oa, "kronos_gjc_role_output_attestable.v2")
    oatt_ref = put("oatt", json.loads(_attestation(keys[scope], lifecycle, uid=f"00000000-0000-4000-8000-{SCOPES.index(scope)+80:012d}", signer=subject, key_id=key_id, role=role, scope=scope, purpose="GJC_ROLE_OUTPUT", payload=objects[oa_ref["uri"]], nonce=bytes([40 + SCOPES.index(scope)]) * 32)), "kronos_attestation.v2")
    output_ref = put("output", {"schema": "kronos_gjc_role_output.v2", "attestable_ref": oa_ref, "attestation_ref": oatt_ref, **{k: oa[k] for k in oa if k != "schema"}}, "kronos_gjc_role_output.v2")
    export_ref = put("export", {"schema": "kronos_gjc_export.v2", "request_ref": request_ref, "assignment_ref": assignment_ref, "output_ref": output_ref, "resolver": "functions.read.v1", "selector": "raw", "resolved_at": "2026-01-01T00:00:07Z", "resolver_principal_uri": "agent://functions-read"}, "kronos_gjc_export.v2")
    _freeze_referenced_objects(objects)
    authority = AuthorityContext(lifecycle, lifecycle, (), keys["root"].public_key().public_bytes_raw(), "00000000-0000-4000-8000-000000000001", sha256_identity(json.loads(lifecycle)), {r: timedelta(hours=1) for r, _, _, _ in RULES.values()} | {"ORCHESTRATOR": timedelta(hours=1)}, InMemoryNonceReplayStore(), b"bridge-policy", lambda: datetime(2026, 1, 1, 0, 0, 8, tzinfo=timezone.utc), {policy: frozenset({"agent://prior"})})
    return request_ref, export_ref, LiteralRawResolver(objects, resolved_at="2026-01-01T00:00:07Z"), authority


def _issue(scope: str, store: InMemoryRequestConsumptionStore | None = None) -> bytes:
    request, export, resolver, authority = _graph(scope)
    return validate_and_issue_receipt(request_ref=request, export_ref=export, resolver=resolver, authority=authority, request_store=store or InMemoryRequestConsumptionStore())
def _put(resolver: LiteralRawResolver, uri: str, value: dict[str, Any], schema: str) -> dict[str, Any]:
    raw = canonical_bytes(value)
    resolver._objects[uri] = raw
    return _ref(uri, raw, schema)


def _export(resolver: LiteralRawResolver, scope: str, *, request: dict[str, Any] | None = None, assignment: dict[str, Any] | None = None, output: dict[str, Any] | None = None) -> dict[str, Any]:
    export = json.loads(resolver._objects[f"agent://{scope.lower()}-export"])
    if request is not None: export["request_ref"] = request
    if assignment is not None: export["assignment_ref"] = assignment
    if output is not None: export["output_ref"] = output
    return _put(resolver, f"agent://{scope.lower()}-export", export, "kronos_gjc_export.v2")


def _rebuild_payload(scope: str, mutate: Any) -> tuple[dict[str, Any], dict[str, Any], LiteralRawResolver, AuthorityContext]:
    request, export, resolver, authority = _graph(scope)
    keys, lifecycle = _keys(), _lifecycle(_keys())
    output = json.loads(resolver._objects[f"agent://{scope.lower()}-output"])
    oa = json.loads(resolver._objects[output["attestable_ref"]["uri"]])
    mutate(oa["payload"], resolver)
    oa_ref = _put(resolver, oa["request_ref"]["uri"].rsplit("-request", 1)[0] + "-oa", oa, "kronos_gjc_role_output_attestable.v2")
    index = SCOPES.index(scope)
    oatt_ref = _put(resolver, f"agent://{scope.lower()}-oatt", json.loads(_attestation(keys[scope], lifecycle, uid=f"00000000-0000-4000-8000-{index+80:012d}", signer=f"agent://{scope.lower()}", key_id=f"00000000-0000-4000-8000-{index+10:012d}", role=oa["role"], scope=scope, purpose="GJC_ROLE_OUTPUT", payload=resolver._objects[oa_ref["uri"]], nonce=bytes([40 + index]) * 32)), "kronos_attestation.v2")
    output = {"schema": "kronos_gjc_role_output.v2", "attestable_ref": oa_ref, "attestation_ref": oatt_ref, **{key: oa[key] for key in oa if key != "schema"}}
    output_ref = _put(resolver, f"agent://{scope.lower()}-output", output, "kronos_gjc_role_output.v2")
    return request, _export(resolver, scope, output=output_ref), resolver, authority


def _assert_issue_error(request: dict[str, Any], export: dict[str, Any], resolver: LiteralRawResolver, authority: AuthorityContext, message: str) -> None:
    with pytest.raises(BridgeValidationError, match=message):
        validate_and_issue_receipt(request_ref=request, export_ref=export, resolver=resolver, authority=authority, request_store=InMemoryRequestConsumptionStore())
def _rebuild_expiry(expires_at: str) -> tuple[dict[str, Any], dict[str, Any], LiteralRawResolver, AuthorityContext]:
    request, _, resolver, authority = _graph("OPERATOR_A")
    keys, lifecycle = _keys(), _lifecycle(_keys())
    request_value = json.loads(resolver._objects[request["uri"]]); request_value["expires_at"] = expires_at
    request_ref = _put(resolver, request["uri"], request_value, "kronos_gjc_request_instance.v2")
    assignment = json.loads(resolver._objects["agent://operator_a-assignment"])
    aa = json.loads(resolver._objects[assignment["attestable_ref"]["uri"]])
    aa.update(request_ref=request_ref, expires_at=expires_at)
    aa_ref = _put(resolver, aa["request_ref"]["uri"].rsplit("-request", 1)[0] + "-aa", aa, "kronos_gjc_assignment_attestable.v2")
    aatt_ref = _put(resolver, "agent://operator_a-aatt", json.loads(_attestation(keys["orch"], lifecycle, uid="00000000-0000-4000-8000-000000000070", signer="agent://orchestrator", key_id="00000000-0000-4000-8000-000000000001", role="ORCHESTRATOR", scope="OPERATOR_A", purpose="GJC_ASSIGNMENT", payload=resolver._objects[aa_ref["uri"]], nonce=bytes([20]) * 32)), "kronos_attestation.v2")
    assignment = {"schema": "kronos_gjc_assignment.v2", "attestable_ref": aa_ref, "attestation_ref": aatt_ref, **{key: aa[key] for key in aa if key != "schema"}}
    assignment_ref = _put(resolver, "agent://operator_a-assignment", assignment, "kronos_gjc_assignment.v2")
    output = json.loads(resolver._objects["agent://operator_a-output"])
    oa = json.loads(resolver._objects[output["attestable_ref"]["uri"]]); oa.update(request_ref=request_ref, assignment_ref=assignment_ref)
    oa_ref = _put(resolver, "agent://operator_a-oa", oa, "kronos_gjc_role_output_attestable.v2")
    oatt_ref = _put(resolver, "agent://operator_a-oatt", json.loads(_attestation(keys["OPERATOR_A"], lifecycle, uid="00000000-0000-4000-8000-000000000080", signer="agent://operator_a", key_id="00000000-0000-4000-8000-000000000010", role="USABILITY_OPERATOR", scope="OPERATOR_A", purpose="GJC_ROLE_OUTPUT", payload=resolver._objects[oa_ref["uri"]], nonce=bytes([40]) * 32)), "kronos_attestation.v2")
    output = {"schema": "kronos_gjc_role_output.v2", "attestable_ref": oa_ref, "attestation_ref": oatt_ref, **{key: oa[key] for key in oa if key != "schema"}}
    output_ref = _put(resolver, "agent://operator_a-output", output, "kronos_gjc_role_output.v2")
    return request_ref, _export(resolver, "OPERATOR_A", request=request_ref, assignment=assignment_ref, output=output_ref), resolver, authority


def test_vectors_cover_authorized_tuples_and_frozen_golden_receipts() -> None:
    assert tuple(VECTOR["input_slot_order"]) == INPUT_SLOT_NAMES
    assert {(r[0], r[2]) for r in VECTOR["request_tuples"]} == {(kind, scope) for kind, (_, scopes, _, _) in RULES.items() for scope in scopes}
    for scope in SCOPES:
        receipt = json.loads(_issue(scope))
        assert receipt["status"] == "VALID"
        assert receipt["validated_scope"] == scope


@pytest.mark.parametrize("scope", SCOPES)
def test_every_role_scope_purpose_lane_issues(scope: str) -> None:
    assert json.loads(_issue(scope))["validated_scope"] == scope
def test_operator_payload_screenshot_wrappers_are_canonical_and_receipted() -> None:
    request, export, resolver, authority = _graph("OPERATOR_A")
    output = json.loads(resolver._objects["agent://operator_a-output"])
    screenshot_refs = [task["screenshot_refs"][0] for task in output["payload"]["tasks"]]
    assert len(screenshot_refs) == 10
    for ref in screenshot_refs:
        raw = resolver._objects[ref["uri"]]
        wrapper = json.loads(raw)
        assert raw == canonical_bytes(wrapper)
        assert hashlib.sha256(raw).hexdigest() == ref["sha256"]
        assert wrapper["schema"] == "kronos_screenshot.v2"
        assert wrapper["png_ref"]["schema"] == "image/png"
        assert wrapper["dimensions"] == {"width": 2, "height": 1}
        assert wrapper["scenario"]["operator_index"] == "A"
    receipt = validate_and_issue_receipt(request_ref=request, export_ref=export, resolver=resolver, authority=authority, request_store=InMemoryRequestConsumptionStore())
    assert json.loads(receipt)["status"] == "VALID"


def test_captured_task_artifacts_are_g002_consumable_end_to_end(tmp_path: Path) -> None:
    trace_path_a, evidence_a = _capture_trace_files(tmp_path / "capture-a", "A")
    trace_path_b, evidence_b = _capture_trace_files(tmp_path / "capture-b", "B")
    trace_a, raw_a, objects_a = _load_capture_objects(trace_path_a, evidence_a)
    trace_b, raw_b, objects_b = _load_capture_objects(trace_path_b, evidence_b)
    assert {trace_a["fixture_ref"]["uri"], trace_a["instrument_ref"]["uri"]} <= set(objects_a)
    assert {trace_b["fixture_ref"]["uri"], trace_b["instrument_ref"]["uri"]} <= set(objects_b)
    for scope, trace, objects in (("OPERATOR_A", trace_a, objects_a), ("OPERATOR_B", trace_b, objects_b)):
        def replace_payload(payload: dict[str, Any], resolver: LiteralRawResolver, trace: dict[str, Any] = trace, objects: dict[str, bytes] = objects) -> None:
            payload.clear()
            payload.update(trace)
            resolver._objects.update(objects)
        request, export, resolver, authority = _rebuild_payload(scope, replace_payload)
        receipt = validate_and_issue_receipt(request_ref=request, export_ref=export, resolver=resolver, authority=authority, request_store=InMemoryRequestConsumptionStore())
        assert json.loads(receipt)["validated_scope"] == scope
    score_value_a, score_raw_a, score_path_a = _score_trace(tmp_path, trace_path_a, evidence_a, "A")
    score_value_b, score_raw_b, score_path_b = _score_trace(tmp_path, trace_path_b, evidence_b, "B")
    assert score_value_a["bitmaps"] == score_value_b["bitmaps"] == {dimension: [True] * 10 for dimension in DIMENSIONS}
    review, _, _ = _review_scores(tmp_path, trace_path_a, evidence_a, trace_path_b, evidence_b, score_path_a, score_path_b)
    trace_refs = [_task_review_ref(trace_path_a, raw_a, "kronos_operator_trace.v2"), _task_review_ref(trace_path_b, raw_b, "kronos_operator_trace.v2")]
    score_refs = [_task_review_ref(score_path_a, score_raw_a, "kronos_machine_task_score.v2"), _task_review_ref(score_path_b, score_raw_b, "kronos_machine_task_score.v2")]
    assert review["operator_trace_refs"] == trace_refs
    assert review["machine_score_refs"] == score_refs
    assert review["verdict"] == "PASS"
    review_objects = {trace_refs[0]["uri"]: raw_a, trace_refs[1]["uri"]: raw_b, score_refs[0]["uri"]: score_raw_a, score_refs[1]["uri"]: score_raw_b}
    def replace_review(payload: dict[str, Any], resolver: LiteralRawResolver) -> None:
        payload.clear()
        payload.update(review)
        resolver._objects.update(review_objects)
    request, export, resolver, authority = _rebuild_payload("TASK_SCORE", replace_review)
    receipt = validate_and_issue_receipt(request_ref=request, export_ref=export, resolver=resolver, authority=authority, request_store=InMemoryRequestConsumptionStore())
    assert json.loads(receipt)["validated_scope"] == "TASK_SCORE"


@pytest.mark.parametrize(("ref_name", "field"), (("fixture_ref", "sha256"), ("fixture_ref", "schema"), ("fixture_ref", "byte_length"), ("instrument_ref", "sha256"), ("instrument_ref", "schema"), ("instrument_ref", "byte_length")))
def test_captured_wrapper_ref_tamper_is_not_g002_consumable(tmp_path: Path, ref_name: str, field: str) -> None:
    trace, _, objects = _capture_trace(tmp_path, "A")
    if field == "sha256":
        trace[ref_name][field] = "0" * 64
    elif field == "schema":
        trace[ref_name][field] = "kronos_task_trace.v2"
    else:
        trace[ref_name][field] += 1
    def replace_payload(payload: dict[str, Any], resolver: LiteralRawResolver) -> None:
        payload.clear()
        payload.update(trace)
        resolver._objects.update(objects)
    request, export, resolver, authority = _rebuild_payload("OPERATOR_A", replace_payload)
    _assert_issue_error(request, export, resolver, authority, "wire schema validation failed|raw artifact hash or length mismatches reference|stored object schema mismatches reference|role payload has an unauthorized predecessor")



def test_semantic_role_branches_and_nested_reference_guards() -> None:
    for scope, mutate in (("OPERATOR_A", lambda p: p["tasks"][0].update(failure_codes=["TIMEOUT"])), ("TASK_SCORE", lambda p: p.update(raised_false_bits=["A/U/1"])), ("ARCHITECT_REVIEW", lambda p: p.update(findings=[{"severity": "HIGH", "code": "GRAPH_CYCLE", "location": "z", "evidence_refs": [_stub("pre", "kronos_preclosure.v2")], "finding_uid": "00000000-0000-4000-8000-000000000999"}, {"severity": "CRITICAL", "code": "GRAPH_CYCLE", "location": "a", "evidence_refs": [_stub("pre", "kronos_preclosure.v2")], "finding_uid": "00000000-0000-4000-8000-000000000998"}])), ("CRITIC_REVIEW", lambda p: p["claim_checks"].reverse()), ("EXECUTOR_QA", lambda p: p.update(skip_count=1)), ("TERMINAL_CLOSURE", lambda p: p.update(result="BLOCKED"))):
        request, export, resolver, authority = _graph(scope)
        output = json.loads(resolver._objects[f"agent://{scope.lower()}-output"])
        mutate(output["payload"])
        predecessors: dict[tuple[str, str], dict[str, Any]] = {}
        for ref in tuple(output["payload"].get("operator_trace_refs", ())) + (output["payload"].get("command_manifest_ref"),):
            if ref:
                predecessors[(ref["uri"], ref["sha256"])] = json.loads(resolver._objects[ref["uri"]])
        with pytest.raises(BridgeValidationError):
            validate_role_payload(output["payload"], output["payload_schema"], predecessor_payloads=predecessors or None, resolver=resolver, authority=authority)
    payload = _operator("OPERATOR_A"); payload["fixture_ref"] = _stub("future", "kronos_gjc_role_output.v2")
    with pytest.raises(BridgeValidationError): validate_role_payload(payload, payload["schema"], current_refs=[payload["fixture_ref"]])


def test_expiry_replay_concurrency_and_transaction_failure() -> None:
    request, export, resolver, authority = _graph("OPERATOR_A")
    bad = json.loads(resolver._objects[request["uri"]]); bad["expires_at"] = bad["created_at"]
    resolver._objects[request["uri"]] = canonical_bytes(bad)
    with pytest.raises(BridgeValidationError): validate_and_issue_receipt(request_ref=_ref(request["uri"], resolver._objects[request["uri"]], "kronos_gjc_request_instance.v2"), export_ref=export, resolver=resolver, authority=authority, request_store=InMemoryRequestConsumptionStore())
    request, export, resolver, authority = _graph("OPERATOR_B"); store = InMemoryRequestConsumptionStore()
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(lambda _: _try_issue(request, export, resolver, authority, store), range(2)))
    assert sum(x is not None for x in results) == 1
    class Broken:
        def store_receipt_if_absent(self, request_identity: str, receipt: bytes) -> bytes | None: raise RuntimeError("transaction failed")
    request, export, resolver, authority = _graph("TASK_SCORE")
    with pytest.raises(BridgeValidationError): validate_and_issue_receipt(request_ref=request, export_ref=export, resolver=resolver, authority=authority, request_store=Broken())


@pytest.mark.parametrize("field,value", [
    ("request_ref", _stub("alternate-request", "kronos_gjc_request_instance.v2")),
    ("assignment_uid", "00000000-0000-4000-8000-000000000999"),
    ("request_uid", "00000000-0000-4000-8000-000000000998"),
    ("run_nonce", "C" * 43), ("subject_principal_uri", "agent://alternate"),
    ("role", "TASK_SCORE_REVIEWER"), ("scope", "TASK_SCORE"),
    ("candidate_head", "c" * 40), ("dist_manifest_sha256", "c" * 64),
    ("input_artifacts", []),
    ("issued_at", "2026-01-01T00:00:03Z"), ("expires_at", "2026-01-01T00:59:59Z"),
])
def test_assignment_projection_leaves_reach_primary_api(field: str, value: Any) -> None:
    request, _, resolver, authority = _graph("OPERATOR_A")
    assignment = json.loads(resolver._objects["agent://operator_a-assignment"])
    assignment[field] = value
    assignment_ref = _put(resolver, "agent://operator_a-assignment", assignment, "kronos_gjc_assignment.v2")
    _assert_issue_error(request, _export(resolver, "OPERATOR_A", assignment=assignment_ref), resolver, authority, "attestable projection mismatches")


@pytest.mark.parametrize("field,value", [
    ("request_ref", _stub("alternate-request", "kronos_gjc_request_instance.v2")),
    ("assignment_ref", _stub("alternate-assignment", "kronos_gjc_assignment.v2")),
    ("request_uid", "00000000-0000-4000-8000-000000000998"),
    ("assignment_uid", "00000000-0000-4000-8000-000000000999"),
    ("subject_principal_uri", "agent://alternate"), ("role", "TASK_SCORE_REVIEWER"),
    ("scope", "TASK_SCORE"), ("candidate_head", "c" * 40), ("dist_manifest_sha256", "c" * 64),
    ("input_artifacts", []), ("started_at", "2026-01-01T00:00:04Z"),
    ("completed_at", "2026-01-01T00:00:05Z"),
])
def test_output_projection_leaves_reach_primary_api(field: str, value: Any) -> None:
    request, _, resolver, authority = _graph("OPERATOR_A")
    output = json.loads(resolver._objects["agent://operator_a-output"])
    output[field] = value
    output_ref = _put(resolver, "agent://operator_a-output", output, "kronos_gjc_role_output.v2")
    _assert_issue_error(request, _export(resolver, "OPERATOR_A", output=output_ref), resolver, authority, "attestable projection mismatches")


@pytest.mark.parametrize("expires", ["2026-01-01T00:00:01Z", "2026-01-01T00:00:02Z"])
def test_expiry_edges_reach_request_lifetime(expires: str) -> None:
    request, _, resolver, authority = _graph("OPERATOR_A")
    value = json.loads(resolver._objects[request["uri"]]); value["expires_at"] = expires
    request_ref = _put(resolver, request["uri"], value, "kronos_gjc_request_instance.v2")
    _assert_issue_error(request_ref, _export(resolver, "OPERATOR_A", request=request_ref), resolver, authority, "request lifetime is invalid" if expires.endswith("01Z") else "graph fields do not agree")


def test_root_schema_mismatch_reaches_primary_api() -> None:
    request, _, resolver, authority = _graph("OPERATOR_A")
    bad = _put(resolver, request["uri"], {"schema": "wrong.v2"}, "kronos_gjc_request_instance.v2")
    _assert_issue_error(bad, _export(resolver, "OPERATOR_A", request=bad), resolver, authority, "stored object schema mismatches reference")


def test_machine_false_to_true_reaches_primary_api() -> None:
    def mutate(payload: dict[str, Any], resolver: LiteralRawResolver) -> None:
        ref = payload["machine_score_refs"][0]
        raw = json.loads(resolver._objects[ref["uri"]]); raw["bitmaps"]["U"][0] = False
        updated = _put(resolver, ref["uri"], raw, "kronos_machine_task_score.v2")
        payload["machine_score_refs"][0] = updated
        for dimension in "ULJ":
            payload["dimensions"]["A"][dimension]["evidence_refs"] = [updated]
    request, export, resolver, authority = _rebuild_payload("TASK_SCORE", mutate)
    _assert_issue_error(request, export, resolver, authority, "reviewer bitmap raises a machine false bit")
@pytest.mark.parametrize("alias", ["kronos_machine_score.v2", "kronos_machine_score_a.v2", "kronos_machine_score_b.v2", "kronos_operator_trace.v2"])
def test_task_score_evidence_refs_reject_machine_score_aliases(alias: str) -> None:
    def mutate(payload: dict[str, Any], resolver: LiteralRawResolver) -> None:
        payload["dimensions"]["A"]["U"]["evidence_refs"] = [_stub(f"alias-{alias.replace('.', '-')}", alias)]
    request, export, resolver, authority = _rebuild_payload("TASK_SCORE", mutate)
    _assert_issue_error(request, export, resolver, authority, "wire schema validation failed")





def test_assignment_input_slots_reaches_projection_branch() -> None:
    request, _, resolver, authority = _graph("OPERATOR_A")
    assignment = json.loads(resolver._objects["agent://operator_a-assignment"])
    assignment["input_slots"][0]["required"] = False
    assignment_ref = _put(resolver, "agent://operator_a-assignment", assignment, "kronos_gjc_assignment.v2")
    _assert_issue_error(request, _export(resolver, "OPERATOR_A", assignment=assignment_ref), resolver, authority, "attestable projection mismatches")


@pytest.mark.parametrize(("field", "value", "message"), [
    ("input_slots", [{"name": "fixture", "schema": "kronos_fixture.v2", "required": False}], "attestable projection mismatches"),
    ("status", "FAILED", "wire schema validation failed"),
    ("payload_schema", "kronos_task_score_review.v2", "attestable projection mismatches"),
    ("payload", {**_operator("OPERATOR_A"), "browser_pid": 2}, "attestable projection mismatches"),
])
def test_remaining_output_projection_leaves_reach_primary_api(field: str, value: Any, message: str) -> None:
    request, _, resolver, authority = _graph("OPERATOR_A")
    output = json.loads(resolver._objects["agent://operator_a-output"])
    output[field] = value
    output_ref = _put(resolver, "agent://operator_a-output", output, "kronos_gjc_role_output.v2")
    _assert_issue_error(request, _export(resolver, "OPERATOR_A", output=output_ref), resolver, authority, message)


def test_expiry_equal_trusted_validation_time_issues() -> None:
    request, export, resolver, authority = _rebuild_expiry("2026-01-01T00:00:08Z")
    authority = replace(authority, trusted_clock=lambda: datetime(2026, 1, 1, 0, 0, 8, tzinfo=timezone.utc))
    assert json.loads(validate_and_issue_receipt(request_ref=request, export_ref=export, resolver=resolver, authority=authority, request_store=InMemoryRequestConsumptionStore()))["status"] == "VALID"


@pytest.mark.parametrize(("expires_at", "expects_error"), (("2026-01-01T00:00:07Z", True), ("2026-01-01T00:00:09Z", False)))
def test_expiry_one_second_boundaries_reach_primary_api(expires_at: str, expects_error: bool) -> None:
    request, export, resolver, authority = _rebuild_expiry(expires_at)
    authority = replace(authority, trusted_clock=lambda: datetime(2026, 1, 1, 0, 0, 8, tzinfo=timezone.utc))
    if expects_error:
        _assert_issue_error(request, export, resolver, authority, "bridge chronology is invalid")
    else:
        assert json.loads(validate_and_issue_receipt(request_ref=request, export_ref=export, resolver=resolver, authority=authority, request_store=InMemoryRequestConsumptionStore()))["status"] == "VALID"


@pytest.mark.parametrize("uri", (
    "kronos-run://AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/./request",
    "kronos-run://AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/a/./request",
    "kronos-run://AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/../request",
    "kronos-run://AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/a/../request",
))
@pytest.mark.parametrize("target", ("request", "export"))
def test_kronos_run_dot_segment_refs_rejected_by_primary_api(uri: str, target: str) -> None:
    request, export, resolver, authority = _graph("OPERATOR_A")
    if target == "request":
        request = _ref(uri, resolver._objects[request["uri"]], "kronos_gjc_request_instance.v2")
    else:
        export = _ref(uri, resolver._objects[export["uri"]], "kronos_gjc_export.v2")
    _assert_issue_error(request, export, resolver, authority, "object reference URI is invalid")

def test_terminal_point_bytes_mismatch_reaches_primary_api() -> None:
    def mutate(payload: dict[str, Any], resolver: LiteralRawResolver) -> None:
        payload["score_ref_b"] = _put(resolver, "agent://terminal_closure-point-b", {"schema": "kronos_point_score.v2", "different": True}, "kronos_point_score.v2")
    request, export, resolver, authority = _rebuild_payload("TERMINAL_CLOSURE", mutate)
    _assert_issue_error(request, export, resolver, authority, "terminal point-score raw bytes mismatch")


@pytest.mark.parametrize("scope", PRIOR_SCOPES)
def test_each_terminal_prior_chain_tamper_reaches_terminal_rule(scope: str) -> None:
    def mutate(payload: dict[str, Any], resolver: LiteralRawResolver) -> None:
        resolution = next(item for item in payload["re_resolutions"] if item["scope"] == scope)
        prior_export = json.loads(resolver._objects[resolution["export_ref"]["uri"]])
        prior_request = json.loads(resolver._objects[prior_export["request_ref"]["uri"]])
        prior_request["template_key"] = "tampered"
        prior_request_ref = _put(resolver, prior_export["request_ref"]["uri"], prior_request, "kronos_gjc_request_instance.v2")
        prior_export["request_ref"] = prior_request_ref
        resolution["export_ref"] = _put(resolver, resolution["export_ref"]["uri"], prior_export, "kronos_gjc_export.v2")
    request, export, resolver, authority = _rebuild_payload("TERMINAL_CLOSURE", mutate)
    _assert_issue_error(request, export, resolver, authority, "terminal prior template projection mismatches")

def _try_issue(request: dict[str, Any], export: dict[str, Any], resolver: LiteralRawResolver, authority: AuthorityContext, store: InMemoryRequestConsumptionStore) -> bytes | None:
    try: return validate_and_issue_receipt(request_ref=request, export_ref=export, resolver=resolver, authority=authority, request_store=store)
    except BridgeValidationError: return None
    

@pytest.mark.parametrize("scope", SCOPES)
def test_existing_receipt_graph_revalidates_without_request_store_side_effect(scope: str) -> None:
    request, export, resolver, authority = _graph(scope)
    store = InMemoryRequestConsumptionStore()
    receipt_raw = validate_and_issue_receipt(
        request_ref=request, export_ref=export, resolver=resolver, authority=authority, request_store=store
    )
    receipt_ref = _put(resolver, f"agent://{scope.lower()}-receipt", json.loads(receipt_raw), "kronos_gjc_validation_receipt.v2")
    stored_before = dict(store._receipts)

    assert validate_existing_receipt_graph(receipt_ref, resolver, authority) == receipt_raw
    assert store._receipts == stored_before


@pytest.mark.parametrize(
    "receipt_field",
    (
        "request_ref",
        "template_ref",
        "assignment_attestable_ref",
        "assignment_attestation_ref",
        "assignment_ref",
        "output_attestable_ref",
        "output_attestation_ref",
        "output_ref",
        "export_ref",
    ),
)
def test_existing_receipt_graph_rejects_each_tampered_chain_component(receipt_field: str) -> None:
    request, export, resolver, authority = _graph("OPERATOR_A")
    receipt_raw = validate_and_issue_receipt(
        request_ref=request, export_ref=export, resolver=resolver, authority=authority, request_store=InMemoryRequestConsumptionStore()
    )
    receipt = json.loads(receipt_raw)
    receipt_ref = _put(resolver, "agent://operator_a-receipt", receipt, "kronos_gjc_validation_receipt.v2")
    target_uri = receipt[receipt_field]["uri"]
    resolver._objects[target_uri] += b" "

    with pytest.raises(BridgeValidationError):
        validate_existing_receipt_graph(receipt_ref, resolver, authority)
