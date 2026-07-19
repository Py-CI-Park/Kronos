"""Executable v5 terminal authority vectors."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator
from stom_rl.v5_authority import canonical_bytes
from stom_rl.v5_terminal import (GenericTerminalValidation, TERMINAL_PRE_OUTPUT_BLOCKING_CODES, TERMINAL_VALIDATION_FAILURE_CODES, TerminalPrecheck, TerminalRunner, TerminalStoreError, TerminalValidationError, post_output_failure_codes, validate_terminal_closure, validation_failure)

ROOT = Path(__file__).resolve().parents[1]
V = json.loads((ROOT / "tests/data/kronos_terminal_v2_vectors.json").read_text())

def ref(schema="x.v2", seed="a"):
    raw = hashlib.sha256(seed.encode()).hexdigest()
    return {"uri": "agent://store/" + seed, "sha256": raw, "byte_length": 1, "schema": schema}

def snapshot(**changes):
    value = dict(points_identical=True, point_pass_a=True, point_pass_b=True, assurance_eligible=True, prior_chains_resolved=True, head_matches=True, tree_matches=True, dist_matches=True, worktree_clean=True, approvals_available=True, head="a" * 64, tree="b" * 64, dist_manifest_sha256="c" * 64)
    value.update(changes)
    return TerminalPrecheck(**value)

def closure(s, blockers=()):
    chains = [{"scope": scope, "request_ref": ref(seed="request-" + scope), "assignment_ref": ref(seed="assignment-" + scope), "output_ref": ref(seed="output-" + scope), "export_ref": ref(seed="export-" + scope), "validation_receipt_ref": ref(seed="validation-" + scope), "re_resolved_assignment_sha256": ref(seed="assignment-" + scope)["sha256"], "re_resolved_output_sha256": ref(seed="output-" + scope)["sha256"], "re_resolved_at": "2026-07-15T00:00:00Z"} for scope in ("OPERATOR_A", "OPERATOR_B", "TASK_SCORE", "ARCHITECT_REVIEW", "CRITIC_REVIEW", "EXECUTOR_QA")]
    return {"schema": "kronos_terminal_closure.v2", "final_assurance_map_ref": ref(seed="map"), "point_score_ref_a": ref(seed="score-a"), "point_score_ref_b": ref(seed="score-b"), "assurance_decision_ref": ref(seed="decision"), "prior_chain_re_resolutions": chains, "head": s.head, "tree": s.tree, "dist_manifest_sha256": s.dist_manifest_sha256, "worktree_clean": s.worktree_clean, "point_pass": s.points_identical and s.point_pass_a and s.point_pass_b, "preterminal_assurance_eligible": s.assurance_eligible, "result": "BLOCKED" if blockers else "CLOSED", "blocking_codes": list(blockers), "closed_at": "2026-07-15T00:00:01Z"}

def context():
    names = ("request_ref", "assignment_attestable_ref", "assignment_attestation_ref", "assignment_ref", "output_attestable_ref", "output_attestation_ref", "output_ref", "export_ref")
    data = {name: ref(seed=name) for name in names}
    data["observed_at"] = {name: "2026-07-15T00:00:02Z" for name in names if name != "request_ref"}
    return data

class Store:
    def __init__(self, bad_ref=False): self.calls = []; self.bad_ref = bad_ref
    def persist_terminal_transition(self, **kwargs):
        self.calls.append(kwargs)
        raw = kwargs["artifact_bytes"]
        return {"uri": "agent://store/" + kwargs["ref_field"], "sha256": "0" * 64 if self.bad_ref else hashlib.sha256(raw).hexdigest(), "byte_length": len(raw), "schema": kwargs["artifact_schema"]}

class Bridge:
    def __init__(self, predicates=None, mutate=None, bad_ref=False): self.predicates = predicates or {name: True for name in V["validation_failure_code_order"]}; self.mutate = mutate; self.bad_ref = bad_ref
    def validate_and_issue_terminal_receipt(self, *, terminal_context):
        predicates = {"assignment_present": True, "output_present": True, "export_present": True, "schema_valid": True, "projection_matches": True, "attestation_valid": True, "authority_valid": True, "hash_length_matches": True, "chronological": True, "role_scope_purpose_valid": True, "request_fresh": True, "result_equation_valid": True, "prior_chains_resolved": True, "identities_match": True}
        if self.predicates and set(self.predicates) == set(predicates): predicates = self.predicates
        receipt = {"schema":"kronos_gjc_validation_receipt.v2", "request_ref":terminal_context["request_ref"], "template_ref":ref(seed="template"), "assignment_attestable_ref":terminal_context["assignment_attestable_ref"], "assignment_attestation_ref":terminal_context["assignment_attestation_ref"], "assignment_ref":terminal_context["assignment_ref"], "output_attestable_ref":terminal_context["output_attestable_ref"], "output_attestation_ref":terminal_context["output_attestation_ref"], "output_ref":terminal_context["output_ref"], "export_ref":terminal_context["export_ref"], "validated_subject_principal_uri":"agent://terminal", "validated_role":"TERMINAL_CLOSURE_AUTHORITY", "validated_scope":"TERMINAL_CLOSURE", "candidate_head":"a" * 64, "dist_manifest_sha256":"c" * 64, "input_slots":[], "input_artifacts":[], "validation_policy_sha256":"0" * 64, "status":"VALID", "resolved_at":"2026-07-15T00:00:01Z", "validated_at":"2026-07-15T00:00:02Z"}
        if self.mutate: self.mutate(receipt)
        raw = canonical_bytes(receipt)
        return GenericTerminalValidation(raw, {"uri":"agent://store/generic", "sha256":"0" * 64 if self.bad_ref else hashlib.sha256(raw).hexdigest(), "byte_length":len(raw), "schema":"kronos_gjc_validation_receipt.v2"}, predicates)

def test_literal_enum_orders():
    assert tuple(V["pre_output_blocking_code_order"]) == TERMINAL_PRE_OUTPUT_BLOCKING_CODES
    assert tuple(V["validation_failure_code_order"]) == TERMINAL_VALIDATION_FAILURE_CODES

@pytest.mark.parametrize("case", V["pre_output_one_hot"])
def test_pre_output_vectors(case):
    assert snapshot(**{case["field"]: False}).blockers() == tuple(case["expected"])

@pytest.mark.parametrize("case", V["post_output_one_hot"])
def test_post_output_vectors(case):
    predicates = {name: True for name in ("assignment_present", "output_present", "export_present", "schema_valid", "projection_matches", "attestation_valid", "authority_valid", "hash_length_matches", "chronological", "role_scope_purpose_valid", "request_fresh", "result_equation_valid", "prior_chains_resolved", "identities_match")}
    predicates[case["predicate"]] = False
    assert post_output_failure_codes(**predicates) == tuple(case["expected"])
@pytest.mark.parametrize("case", V["post_output_one_hot"])
def test_post_output_vectors_finalize_to_exact_invalid_diagnostic(case):
    s = snapshot(); r = TerminalRunner("nonce", "a" * 64, "b" * 64, "c" * 64); r.capture_precheck(s); store = Store()
    predicates = {name: True for name in ("assignment_present", "output_present", "export_present", "schema_valid", "projection_matches", "attestation_valid", "authority_valid", "hash_length_matches", "chronological", "role_scope_purpose_valid", "request_fresh", "result_equation_valid", "prior_chains_resolved", "identities_match")}
    predicates[case["predicate"]] = False
    with pytest.raises(TerminalValidationError):
        r.finalize(payload_raw=canonical_bytes(closure(s)), context=context(), bridge=Bridge(predicates=predicates), store=store, final_precheck=s, failed_at="2026-07-15T00:00:03Z", default_preterminal_eligible=True, retained_default_invariant=True)
    diagnostic = json.loads(store.calls[-1]["artifact_bytes"])
    assert r.status == "INVALID_TERMINAL" and diagnostic["failure_codes"] == case["expected"]
    assert set(diagnostic) == {"schema", "run_nonce", "terminal_request_ref", "failure_codes", "runner_state", "failed_at", "observed_assignment_attestable_ref", "observed_assignment_attestation_ref", "observed_assignment_ref", "observed_output_attestable_ref", "observed_output_attestation_ref", "observed_output_ref", "observed_export_ref"}

def test_generic_hash_length_mismatch_finalizes_atomically():
    s = snapshot(); r = TerminalRunner("nonce", "a" * 64, "b" * 64, "c" * 64); r.capture_precheck(s); store = Store()
    with pytest.raises(TerminalValidationError):
        r.finalize(payload_raw=canonical_bytes(closure(s)), context=context(), bridge=Bridge(bad_ref=True), store=store, final_precheck=s, failed_at="2026-07-15T00:00:03Z", default_preterminal_eligible=True, retained_default_invariant=True)
    diagnostic = json.loads(store.calls[-1]["artifact_bytes"])
    assert r.status == "INVALID_TERMINAL" and diagnostic["failure_codes"] == ["HASH_LENGTH_MISMATCH"] and store.calls[-1]["ref_field"] == "terminal_diagnostic_ref"

def test_combined_post_output_vector():
    assert post_output_failure_codes(**V["combined_failure"]["predicates"]) == tuple(V["combined_failure"]["expected"])

@pytest.mark.parametrize("case", V["outcome_cases"])
def test_closed_and_blocked_success_vectors(case):
    s = snapshot(**case["precheck"]); r = TerminalRunner("nonce", "a" * 64, "b" * 64, "c" * 64); r.capture_precheck(s); store = Store()
    receipt = r.finalize(payload_raw=canonical_bytes(closure(s, s.blockers())), context=context(), bridge=Bridge(), store=store, final_precheck=s, failed_at="2026-07-15T00:00:03Z", default_preterminal_eligible=True, retained_default_invariant=True)
    assert receipt["terminal_result"] == case["expected_result"] and r.status == case["expected_status"] and len(store.calls) == 1

def test_blocker_order_omission_and_prior_adversaries_fail():
    s = snapshot(); p = closure(s)
    p["blocking_codes"] = ["APPROVAL_MISSING", "POINT_SCORE_FAIL"]
    with pytest.raises(TerminalValidationError): validate_terminal_closure(canonical_bytes(p), precheck=s)
    s = snapshot(approvals_available=False); p = closure(s, ())
    with pytest.raises(TerminalValidationError): validate_terminal_closure(canonical_bytes(p), precheck=s)
    p = closure(snapshot()); p["prior_chain_re_resolutions"][0]["re_resolved_assignment_sha256"] = "0" * 64
    with pytest.raises(TerminalValidationError): validate_terminal_closure(canonical_bytes(p), precheck=snapshot())
    p = closure(snapshot()); p["prior_chain_re_resolutions"][0]["re_resolved_output_sha256"] = "0" * 64
    with pytest.raises(TerminalValidationError): validate_terminal_closure(canonical_bytes(p), precheck=snapshot())
    p = closure(snapshot()); p["prior_chain_re_resolutions"][0]["re_resolved_at"] = p["closed_at"]
    with pytest.raises(TerminalValidationError): validate_terminal_closure(canonical_bytes(p), precheck=snapshot())

def test_generic_attestable_attestation_and_final_drift_invalidate():
    for field in ("assignment_attestable_ref", "assignment_attestation_ref"):
        s = snapshot(); r = TerminalRunner("nonce", "a" * 64, "b" * 64, "c" * 64); r.capture_precheck(s); store = Store()
        with pytest.raises(TerminalValidationError): r.finalize(payload_raw=canonical_bytes(closure(s)), context=context(), bridge=Bridge(mutate=lambda receipt, f=field: receipt.__setitem__(f, ref(seed="wrong"))), store=store, final_precheck=s, failed_at="2026-07-15T00:00:03Z", default_preterminal_eligible=True, retained_default_invariant=True)
        assert r.status == "INVALID_TERMINAL" and store.calls[-1]["ref_field"] == "terminal_diagnostic_ref"
    s = snapshot(); r = TerminalRunner("nonce", "a" * 64, "b" * 64, "c" * 64); r.capture_precheck(s)
    with pytest.raises(TerminalValidationError): r.finalize(payload_raw=canonical_bytes(closure(s)), context=context(), bridge=Bridge(), store=Store(), final_precheck=snapshot(head_matches=False), failed_at="2026-07-15T00:00:03Z", default_preterminal_eligible=True, retained_default_invariant=True)

def test_persisted_ref_mismatch_never_mints_diagnostic_and_terminal_replay_is_immutable():
    s = snapshot(); r = TerminalRunner("nonce", "a" * 64, "b" * 64, "c" * 64); r.capture_precheck(s); store = Store(bad_ref=True)
    with pytest.raises(TerminalStoreError): r.finalize(payload_raw=canonical_bytes(closure(s)), context=context(), bridge=Bridge(), store=store, final_precheck=s, failed_at="2026-07-15T00:00:03Z", default_preterminal_eligible=True, retained_default_invariant=True)
    assert len(store.calls) == 1 and r.status == "ACTIVE"
    r = TerminalRunner("nonce", "a" * 64, "b" * 64, "c" * 64); r.capture_precheck(s); r.finalize(payload_raw=canonical_bytes(closure(s)), context=context(), bridge=Bridge(), store=Store(), final_precheck=s, failed_at="2026-07-15T00:00:03Z", default_preterminal_eligible=True, retained_default_invariant=True)
    with pytest.raises(TerminalValidationError, match="immutable"): r.finalize(payload_raw=canonical_bytes(closure(s)), context=context(), bridge=Bridge(), store=Store(), final_precheck=s, failed_at="2026-07-15T00:00:03Z", default_preterminal_eligible=True, retained_default_invariant=True)
def test_terminal_wire_schema_rejects_incomplete_or_inconsistent_closure_and_receipt():
    schema = json.loads((ROOT / "docs/schemas/kronos_terminal_closure.v2.schema.json").read_text())
    validator = Draft202012Validator(schema)
    s = snapshot()
    valid_closure = closure(s)
    assert not list(validator.iter_errors(valid_closure))
    incomplete_closure = dict(valid_closure)
    incomplete_closure.pop("head")
    assert list(validator.iter_errors(incomplete_closure))

    runner = TerminalRunner("nonce", "a" * 64, "b" * 64, "c" * 64)
    runner.capture_precheck(s)
    receipt = runner.finalize(payload_raw=canonical_bytes(valid_closure), context=context(), bridge=Bridge(), store=Store(), final_precheck=s, failed_at="2026-07-15T00:00:03Z", default_preterminal_eligible=True, retained_default_invariant=True)
    assert not list(validator.iter_errors(receipt))
    malformed_receipt = dict(receipt)
    malformed_receipt["schema"] = "kronos_terminal_blocked_receipt.v2"
    assert list(validator.iter_errors(malformed_receipt))
    malformed_receipt = dict(receipt)
    malformed_receipt["extra"] = True
    assert list(validator.iter_errors(malformed_receipt))


def test_diagnostic_failed_at_must_follow_observed_artifacts_even_with_chronology_code():
    observed = {name: ref(seed=name) for name in ("assignment_attestable_ref", "assignment_attestation_ref", "assignment_ref", "output_attestable_ref", "output_attestation_ref", "output_ref", "export_ref")}
    observed_at = {name: "2026-07-15T00:00:03Z" for name in observed}
    with pytest.raises(TerminalValidationError, match="chronology"):
        validation_failure(run_nonce="nonce", terminal_request_ref=ref(seed="request"), observed=observed, observed_at=observed_at, failure_codes=("CHRONOLOGY_INVALID",), failed_at="2026-07-15T00:00:03Z")
