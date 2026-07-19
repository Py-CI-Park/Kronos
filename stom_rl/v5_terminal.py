"""Fail-closed terminal authority boundary; terminal output never authenticates itself."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Final, Mapping, Protocol, Sequence

from stom_rl.v5_authority import AuthorityVerificationError, canonical_bytes, parse_canonical_json

TERMINAL_PRE_OUTPUT_BLOCKING_CODES: Final = ("POINT_SCORE_MISMATCH", "POINT_SCORE_FAIL", "ASSURANCE_BLOCK", "PRIOR_CHAIN_RERESOLUTION_FAIL", "HEAD_DRIFT", "TREE_DRIFT", "DIST_DRIFT", "DIRTY_WORKTREE", "APPROVAL_MISSING")
TERMINAL_VALIDATION_FAILURE_CODES: Final = ("MISSING_ASSIGNMENT", "MISSING_OUTPUT", "MISSING_EXPORT", "SCHEMA_INVALID", "PROJECTION_MISMATCH", "ATTESTATION_INVALID", "AUTHORITY_INVALID", "HASH_LENGTH_MISMATCH", "CHRONOLOGY_INVALID", "ROLE_SCOPE_PURPOSE_INVALID", "REQUEST_REPLAY", "RESULT_EQUATION_INVALID", "PRIOR_CHAIN_RERESOLUTION_FAIL", "HEAD_TREE_DIST_DRIFT")
RUNNER_PHASES: Final = ("BIND_HEAD", "PREFLIGHT", "QA", "GENERIC_CAPTURE", "OPERATOR_A", "OPERATOR_B", "TASK_SCORE", "EVIDENCE_99", "PRECLOSURE_CANDIDATE", "POINT_SCORE_ASSURANCE", "ASSURANCE_DECISION", "TERMINAL_PRECHECK", "TERMINAL_OUTPUT", "TERMINAL_POSTCHECK", "DONE")
RUNNER_STATUSES: Final = ("ACTIVE", "AWAITING_GJC", "TERMINAL_CLOSED", "TERMINAL_BLOCKED", "INVALID_TERMINAL", "FAILED", "INVALIDATED")
_PRIOR_SCOPES: Final = ("OPERATOR_A", "OPERATOR_B", "TASK_SCORE", "ARCHITECT_REVIEW", "CRITIC_REVIEW", "EXECUTOR_QA")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_PREDICATE_NAMES: Final = ("assignment_present", "output_present", "export_present", "schema_valid", "projection_matches", "attestation_valid", "authority_valid", "hash_length_matches", "chronological", "role_scope_purpose_valid", "request_fresh", "result_equation_valid", "prior_chains_resolved", "identities_match")


class TerminalValidationError(ValueError):
    """Terminal validation failed; no successful authority artifact may be emitted."""
class TerminalPredicateError(TerminalValidationError):
    """A structured post-output predicate failure."""
    def __init__(self, **predicates: bool) -> None:
        super().__init__("structured post-output predicate failure")
        self.predicates = predicates



class TerminalStoreError(TerminalValidationError):
    """A store violated the atomic terminal-transition contract."""


@dataclass(frozen=True)
class GenericTerminalValidation:
    raw: bytes
    ref: Mapping[str, Any]
    predicates: Mapping[str, bool]


class AuthenticatedGenericBridge(Protocol):
    """The generic boundary supplies receipt bytes plus all structured predicates."""
    def validate_and_issue_terminal_receipt(self, *, terminal_context: Mapping[str, Any]) -> GenericTerminalValidation: ...


class TerminalOutcomeStore(Protocol):
    """Atomically writes exact bytes, binds their ref, and CASes the durable runner state/ref."""
    def persist_terminal_transition(self, *, run_nonce: str, artifact_bytes: bytes, artifact_schema: str, expected_phase: str, expected_status: str, next_phase: str, next_status: str, ref_field: str) -> Mapping[str, Any]: ...


def _time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not _UTC.fullmatch(value): raise TerminalValidationError(f"{label} must be canonical UTC")
    try: return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as exc: raise TerminalValidationError(f"{label} is invalid") from exc


def _shape(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys: raise TerminalValidationError(f"{label} has invalid wire shape")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value): raise TerminalValidationError(f"{label} must be SHA-256")
    return value


def _ref(value: Any, label: str) -> Mapping[str, Any]:
    value = _shape(value, {"uri", "sha256", "byte_length", "schema"}, label)
    if not isinstance(value["uri"], str) or not re.fullmatch(r"agent://[^/\s]+/.+", value["uri"]) or not isinstance(value["byte_length"], int) or isinstance(value["byte_length"], bool) or value["byte_length"] < 0 or not isinstance(value["schema"], str) or not value["schema"]: raise TerminalValidationError(f"{label} is not ObjectRef")
    _sha(value["sha256"], f"{label}.sha256")
    return value


def _observed_chronological(observed: Mapping[str, Mapping[str, Any] | None], observed_at: Mapping[str, str | None], failed_at: str) -> bool:
    try:
        end = _time(failed_at, "failed_at")
        for name, value in observed.items():
            if value is not None and (observed_at.get(name) is None or _time(observed_at[name], f"observed_{name}_at") >= end):
                return False
    except TerminalValidationError:
        return False
    return True


def _raw_ref(raw: bytes, ref: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    _ref(ref, label)
    if not isinstance(raw, bytes) or ref["sha256"] != hashlib.sha256(raw).hexdigest() or ref["byte_length"] != len(raw): raise TerminalStoreError(f"{label} does not bind raw bytes")
    return ref


def _ordered(values: Any, allowed: Sequence[str], label: str, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)) or (nonempty and not values) or len(values) != len(set(values)) or any(item not in allowed for item in values): raise TerminalValidationError(f"{label} is not closed unique enum")
    answer = tuple(item for item in allowed if item in values)
    if tuple(values) != answer: raise TerminalValidationError(f"{label} is not enum ordered")
    return answer


@dataclass(frozen=True)
class TerminalPrecheck:
    points_identical: bool; point_pass_a: bool; point_pass_b: bool; assurance_eligible: bool; prior_chains_resolved: bool
    head_matches: bool; tree_matches: bool; dist_matches: bool; worktree_clean: bool; approvals_available: bool
    head: str; tree: str; dist_manifest_sha256: str
    def blockers(self) -> tuple[str, ...]:
        failed = ((not self.points_identical, "POINT_SCORE_MISMATCH"), (not (self.point_pass_a and self.point_pass_b), "POINT_SCORE_FAIL"), (not self.assurance_eligible, "ASSURANCE_BLOCK"), (not self.prior_chains_resolved, "PRIOR_CHAIN_RERESOLUTION_FAIL"), (not self.head_matches, "HEAD_DRIFT"), (not self.tree_matches, "TREE_DRIFT"), (not self.dist_matches, "DIST_DRIFT"), (not self.worktree_clean, "DIRTY_WORKTREE"), (not self.approvals_available, "APPROVAL_MISSING"))
        return tuple(code for failed_now, code in failed if failed_now)


def blockers_for(**kwargs: Any) -> tuple[str, ...]:
    return TerminalPrecheck(**kwargs, head="0" * 64, tree="0" * 64, dist_manifest_sha256="0" * 64).blockers()


def post_output_failure_codes(**predicates: bool) -> tuple[str, ...]:
    names = dict(zip(_PREDICATE_NAMES, TERMINAL_VALIDATION_FAILURE_CODES))
    if set(predicates) != set(names) or any(not isinstance(item, bool) for item in predicates.values()): raise TerminalValidationError("post-output predicates are incomplete")
    return tuple(code for name, code in names.items() if not predicates[name])


def validate_terminal_closure(payload_raw: bytes, *, precheck: TerminalPrecheck) -> Mapping[str, Any]:
    try: value = parse_canonical_json(payload_raw, "terminal closure")
    except AuthorityVerificationError as exc: raise TerminalValidationError("closure schema invalid") from exc
    keys = {"schema", "final_assurance_map_ref", "point_score_ref_a", "point_score_ref_b", "assurance_decision_ref", "prior_chain_re_resolutions", "head", "tree", "dist_manifest_sha256", "worktree_clean", "point_pass", "preterminal_assurance_eligible", "result", "blocking_codes", "closed_at"}
    _shape(value, keys, "terminal closure")
    if value["schema"] != "kronos_terminal_closure.v2": raise TerminalValidationError("closure schema invalid")
    for name in ("final_assurance_map_ref", "point_score_ref_a", "point_score_ref_b", "assurance_decision_ref"): _ref(value[name], name)
    for name in ("head", "tree", "dist_manifest_sha256"): _sha(value[name], name)
    if any(not isinstance(value[name], bool) for name in ("worktree_clean", "point_pass", "preterminal_assurance_eligible")): raise TerminalValidationError("closure booleans invalid")
    blockers = _ordered(value["blocking_codes"], TERMINAL_PRE_OUTPUT_BLOCKING_CODES, "blocking_codes")
    if blockers != precheck.blockers() or value["result"] != ("BLOCKED" if blockers else "CLOSED"): raise TerminalValidationError("result/blocker equation invalid")
    if value["point_pass"] != (precheck.points_identical and precheck.point_pass_a and precheck.point_pass_b) or value["preterminal_assurance_eligible"] != precheck.assurance_eligible or value["worktree_clean"] != precheck.worktree_clean: raise TerminalValidationError("payload precheck projection invalid")
    if (value["head"], value["tree"], value["dist_manifest_sha256"]) != (precheck.head, precheck.tree, precheck.dist_manifest_sha256): raise TerminalValidationError("payload identity drift")
    closed = _time(value["closed_at"], "closed_at")
    chains = value["prior_chain_re_resolutions"]
    if not isinstance(chains, list) or len(chains) != 6: raise TerminalValidationError("prior chains must be six")
    scopes: list[str] = []
    for item in chains:
        _shape(item, {"scope", "request_ref", "assignment_ref", "output_ref", "export_ref", "validation_receipt_ref", "re_resolved_assignment_sha256", "re_resolved_output_sha256", "re_resolved_at"}, "prior chain")
        scopes.append(item["scope"])
        for name in ("request_ref", "assignment_ref", "output_ref", "export_ref", "validation_receipt_ref"): _ref(item[name], name)
        if item["re_resolved_assignment_sha256"] != item["assignment_ref"]["sha256"] or item["re_resolved_output_sha256"] != item["output_ref"]["sha256"]: raise TerminalValidationError("prior re-resolution hash mismatch")
        if closed <= _time(item["re_resolved_at"], "re_resolved_at"): raise TerminalValidationError("closure chronology invalid")
    if tuple(scopes) != _PRIOR_SCOPES: raise TerminalValidationError("prior chain scope order invalid")
    return value


def validation_failure(*, run_nonce: str, terminal_request_ref: Mapping[str, Any], observed: Mapping[str, Mapping[str, Any] | None], observed_at: Mapping[str, str | None], failure_codes: Sequence[str], failed_at: str) -> dict[str, Any]:
    _ref(terminal_request_ref, "terminal request")
    codes = _ordered(failure_codes, TERMINAL_VALIDATION_FAILURE_CODES, "failure_codes", True)
    _time(failed_at, "failed_at")
    names = ("assignment_attestable_ref", "assignment_attestation_ref", "assignment_ref", "output_attestable_ref", "output_attestation_ref", "output_ref", "export_ref")
    if set(observed) != set(names) or set(observed_at) != set(names):
        raise TerminalValidationError("observed artifact fields incomplete")
    if not _observed_chronological(observed, observed_at, failed_at):
        raise TerminalValidationError("diagnostic chronology invalid")
    result: dict[str, Any] = {"schema":"kronos_terminal_validation_failure.v2", "run_nonce":run_nonce, "terminal_request_ref":dict(terminal_request_ref), "failure_codes":list(codes), "runner_state":"INVALID_TERMINAL", "failed_at":failed_at}
    for name in names:
        value = observed[name]
        if value is not None:
            _ref(value, f"observed_{name}")
        result[f"observed_{name}"] = value
    return result


def _generic_receipt(result: GenericTerminalValidation, context: Mapping[str, Any], closure: Mapping[str, Any]) -> Mapping[str, Any]:
    _ref(result.ref, "generic receipt")
    if not isinstance(result.raw, bytes) or result.ref["sha256"] != hashlib.sha256(result.raw).hexdigest() or result.ref["byte_length"] != len(result.raw):
        raise TerminalPredicateError(hash_length_matches=False)
    if set(result.predicates) != set(_PREDICATE_NAMES) or any(not isinstance(v, bool) for v in result.predicates.values()):
        raise TerminalValidationError("generic predicates incomplete")
    try: receipt = parse_canonical_json(result.raw, "generic receipt")
    except AuthorityVerificationError as exc: raise TerminalPredicateError(schema_valid=False) from exc
    required = {"schema", "request_ref", "template_ref", "assignment_attestable_ref", "assignment_attestation_ref", "assignment_ref", "output_attestable_ref", "output_attestation_ref", "output_ref", "export_ref", "validated_subject_principal_uri", "validated_role", "validated_scope", "candidate_head", "dist_manifest_sha256", "input_slots", "input_artifacts", "validation_policy_sha256", "status", "resolved_at", "validated_at"}
    _shape(receipt, required, "generic receipt")
    if receipt["schema"] != "kronos_gjc_validation_receipt.v2" or receipt["status"] != "VALID" or receipt["validated_role"] != "TERMINAL_CLOSURE_AUTHORITY" or receipt["validated_scope"] != "TERMINAL_CLOSURE": raise TerminalPredicateError(authority_valid=False, role_scope_purpose_valid=False)
    for name in ("request_ref", "template_ref", "assignment_attestable_ref", "assignment_attestation_ref", "assignment_ref", "output_attestable_ref", "output_attestation_ref", "output_ref", "export_ref"): _ref(receipt[name], name)
    for name in ("request_ref", "assignment_attestable_ref", "assignment_attestation_ref", "assignment_ref", "output_attestable_ref", "output_attestation_ref", "output_ref", "export_ref"):
        if receipt[name] != context[name]: raise TerminalPredicateError(attestation_valid=False)
    if receipt["candidate_head"] != closure["head"] or receipt["dist_manifest_sha256"] != closure["dist_manifest_sha256"]: raise TerminalPredicateError(identities_match=False)
    if _time(receipt["validated_at"], "validated_at") < _time(receipt["resolved_at"], "resolved_at") or _time(receipt["validated_at"], "validated_at") < _time(closure["closed_at"], "closed_at"): raise TerminalPredicateError(chronological=False)
    return receipt


@dataclass
class TerminalRunner:
    run_nonce: str; candidate_head: str; candidate_tree: str; dist_manifest_sha256: str
    phase: str = "TERMINAL_PRECHECK"; status: str = "ACTIVE"; precheck: TerminalPrecheck | None = None
    last_successful_artifact_ref: Mapping[str, Any] | None = None; terminal_diagnostic_ref: Mapping[str, Any] | None = None
    def capture_precheck(self, snapshot: TerminalPrecheck) -> None:
        if self.status in {"TERMINAL_CLOSED", "TERMINAL_BLOCKED", "INVALID_TERMINAL"}: raise TerminalValidationError("terminal state immutable")
        if (snapshot.head, snapshot.tree, snapshot.dist_manifest_sha256) != (self.candidate_head, self.candidate_tree, self.dist_manifest_sha256): raise TerminalValidationError("precheck candidate identity mismatch")
        self.precheck, self.phase = snapshot, "TERMINAL_OUTPUT"
    def _transition(self, store: TerminalOutcomeStore, raw: bytes, schema: str, status: str, field: str) -> Mapping[str, Any]:
        ref = store.persist_terminal_transition(run_nonce=self.run_nonce, artifact_bytes=raw, artifact_schema=schema, expected_phase=self.phase, expected_status=self.status, next_phase="DONE" if status != "INVALID_TERMINAL" else "TERMINAL_POSTCHECK", next_status=status, ref_field=field)
        return _raw_ref(raw, ref, field)
    def _invalid(self, *, store: TerminalOutcomeStore, request_ref: Mapping[str, Any], observed: Mapping[str, Mapping[str, Any] | None], observed_at: Mapping[str, str | None], codes: Sequence[str], failed_at: str) -> None:
        diagnostic = validation_failure(run_nonce=self.run_nonce, terminal_request_ref=request_ref, observed=observed, observed_at=observed_at, failure_codes=codes, failed_at=failed_at)
        raw = canonical_bytes(diagnostic)
        ref = self._transition(store, raw, "kronos_terminal_validation_failure.v2", "INVALID_TERMINAL", "terminal_diagnostic_ref")
        self.phase, self.status, self.terminal_diagnostic_ref = "TERMINAL_POSTCHECK", "INVALID_TERMINAL", ref
    def finalize(self, *, payload_raw: bytes, context: Mapping[str, Any], bridge: AuthenticatedGenericBridge, store: TerminalOutcomeStore, final_precheck: TerminalPrecheck, failed_at: str, default_preterminal_eligible: bool, retained_default_invariant: bool) -> Mapping[str, Any]:
        if self.status in {"TERMINAL_CLOSED", "TERMINAL_BLOCKED", "INVALID_TERMINAL"}: raise TerminalValidationError("terminal state immutable")
        request = context.get("request_ref"); _ref(request, "request_ref")
        names = ("assignment_attestable_ref", "assignment_attestation_ref", "assignment_ref", "output_attestable_ref", "output_attestation_ref", "output_ref", "export_ref")
        observed = {name: context.get(name) for name in names}
        observed_at = context.get("observed_at", {})
        if not isinstance(observed_at, Mapping): observed_at = {}
        observed_at = {name: observed_at.get(name) for name in names}
        predicates = {name: True for name in _PREDICATE_NAMES}
        predicates["assignment_present"] = all(observed[name] is not None for name in names[:3])
        predicates["output_present"] = all(observed[name] is not None for name in names[3:6])
        predicates["export_present"] = observed["export_ref"] is not None
        predicates["chronological"] = _observed_chronological(observed, observed_at, failed_at)
        transitioned = False
        try:
            if self.precheck is None or final_precheck != self.precheck: predicates["result_equation_valid"] = False; raise TerminalValidationError("final precheck drift")
            closure = validate_terminal_closure(payload_raw, precheck=self.precheck)
            if (final_precheck.head, final_precheck.tree, final_precheck.dist_manifest_sha256, final_precheck.worktree_clean) != (self.candidate_head, self.candidate_tree, self.dist_manifest_sha256, closure["worktree_clean"]): predicates["identities_match"] = False; raise TerminalValidationError("final identities/worktree drift")
            generic_result = bridge.validate_and_issue_terminal_receipt(terminal_context=context)
            if set(generic_result.predicates) != set(_PREDICATE_NAMES) or any(not isinstance(value, bool) for value in generic_result.predicates.values()):
                raise TerminalValidationError("generic predicates incomplete")
            predicates = {name: predicates[name] and generic_result.predicates[name] for name in _PREDICATE_NAMES}
            generic = _generic_receipt(generic_result, context, closure)
            codes = post_output_failure_codes(**predicates)
            if codes: raise TerminalValidationError("generic post-output predicates failed")
            receipt = _terminal_receipt(closure, self.run_nonce, context, generic_result.ref, generic, default_preterminal_eligible, retained_default_invariant)
            raw = canonical_bytes(receipt)
            receipt_ref = self._transition(store, raw, receipt["schema"], "TERMINAL_CLOSED" if closure["result"] == "CLOSED" else "TERMINAL_BLOCKED", "last_successful_artifact_ref")
            transitioned = True
        except TerminalStoreError:
            # The store contract forbids an invalid ref after persisting a transition; never mint a competing diagnostic.
            raise
        except TerminalPredicateError as exc:
            predicates.update(exc.predicates)
            self._invalid(store=store, request_ref=request, observed=observed, observed_at=observed_at, codes=post_output_failure_codes(**predicates), failed_at=failed_at)
            raise
        except Exception as exc:
            if not transitioned:
                codes = post_output_failure_codes(**predicates)
                if not codes: codes = ("SCHEMA_INVALID",)
                self._invalid(store=store, request_ref=request, observed=observed, observed_at=observed_at, codes=codes, failed_at=failed_at)
            raise exc if isinstance(exc, TerminalValidationError) else TerminalValidationError("generic bridge failure")
        self.phase, self.status, self.last_successful_artifact_ref = "DONE", ("TERMINAL_CLOSED" if closure["result"] == "CLOSED" else "TERMINAL_BLOCKED"), receipt_ref
        return receipt


def _terminal_receipt(closure: Mapping[str, Any], run_nonce: str, context: Mapping[str, Any], generic_ref: Mapping[str, Any], generic: Mapping[str, Any], default_preterminal_eligible: bool, retained_default_invariant: bool) -> dict[str, Any]:
    required = ("request_ref", "assignment_attestable_ref", "assignment_attestation_ref", "assignment_ref", "output_attestable_ref", "output_attestation_ref", "output_ref", "export_ref")
    for key in required: _ref(context.get(key), key)
    _raw_ref(canonical_bytes(generic), generic_ref, "terminal validation receipt")
    fields = {f"terminal_{key}": dict(context[key]) for key in required}
    closed = closure["result"] == "CLOSED"
    release = closed and closure["worktree_clean"] and closure["point_pass"] and closure["preterminal_assurance_eligible"]
    if closed != release: raise TerminalValidationError("release equation invalid")
    return {"schema":"kronos_terminal_release_receipt.v2" if closed else "kronos_terminal_blocked_receipt.v2", "run_nonce":run_nonce, **fields, "terminal_validation_receipt_ref":dict(generic_ref), "final_assurance_map_ref":dict(closure["final_assurance_map_ref"]), "assurance_decision_ref":dict(closure["assurance_decision_ref"]), "point_score_ref_a":dict(closure["point_score_ref_a"]), "point_score_ref_b":dict(closure["point_score_ref_b"]), "head":closure["head"], "tree":closure["tree"], "dist_manifest_sha256":closure["dist_manifest_sha256"], "worktree_clean":closure["worktree_clean"], "point_pass":closure["point_pass"], "preterminal_assurance_eligible":closure["preterminal_assurance_eligible"], "default_preterminal_eligible":bool(default_preterminal_eligible), "terminal_result":closure["result"], "release_eligible":release, "default_eligible":bool(release and default_preterminal_eligible and retained_default_invariant), "blocking_codes":list(closure["blocking_codes"]), "validated_at":generic["validated_at"]}
