"""Contract vectors for the candidate-only V5 score DAG."""
from __future__ import annotations

import base64
import dataclasses
import hashlib
import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from stom_rl import v5_evidence_dag as evidence
from stom_rl import v5_score_dag as dag

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("v5_score", ROOT / "scripts" / "score_kronos_dashboard_v5.py")
assert SPEC and SPEC.loader
source_identity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source_identity)
SCORECARD = json.loads((ROOT / "docs" / "kronos_dashboard_v5_scorecard_v2.json").read_bytes())
VECTORS = json.loads((ROOT / "tests" / "data" / "kronos_score_assurance_v2_vectors.json").read_text(encoding="utf-8"))
KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
LOCKS = {"promotion_allowed": False, "model_build_allowed": False, "paper_forward_allowed": False, "live_broker_order_allowed": False, "profitability_claim_allowed": False, "go_summary_allowed": False}


def _raw(value: dict) -> bytes:
    return dag.canonical_bytes(value)


def _signed_receipt(claim_id: str, source_sha: str, status: str, violations: list[str]) -> dict:
    definition = SCORECARD["claims"][claim_id]
    unsigned = {"schema": "kronos_claim_authority_proof.v1", "claim_id": claim_id, "candidate_source_sha256": source_sha, "claim_definition_sha256": hashlib.sha256(_raw(definition)).hexdigest(), "verifier": definition["verifier"], "evidence_schema": definition["required_evidence_schema"], "status": status, "violation_codes": sorted(violations)}
    signed = KEY.sign(SCORECARD["authority_proof"]["domain_separator"].encode("ascii") + b"\0" + _raw(unsigned))
    return {"schema": "kronos_claim_verification.v1", "claim_id": claim_id, "candidate_source_sha256": source_sha, "claim_definition_sha256": unsigned["claim_definition_sha256"], "verifier": unsigned["verifier"], "evidence_schema": unsigned["evidence_schema"], "status": status, "authority_proof": {**unsigned, "signature": base64.urlsafe_b64encode(signed).rstrip(b"=").decode("ascii")}}


def _fixture_objects(passes: dict[str, int], capabilities: dict[str, int] | None = None, violations: list[str] | None = None) -> tuple[bytes, dict[str, bytes]]:
    source = {"schema": "kronos_source_identity.v1", "source_commit": "a" * 40, "source_tree": "b" * 40, "scope_manifest_sha256": source_identity._CANONICAL_SCOPE_DIGEST, "files": [{"path": "stom_rl/v5_score_dag.py", "git_mode": "100644", "sha256": "d" * 64, "byte_length": 1}]}
    source_raw, scorecard_raw = _raw(source), _raw(SCORECARD)
    objects = {"agent://test/source": source_raw, "agent://test/scorecard": scorecard_raw}
    source_ref, scorecard_ref = evidence.object_ref("agent://test/source", source_raw), evidence.object_ref("agent://test/scorecard", scorecard_raw)
    capability_ids = [claim_id for category, item in SCORECARD["categories"].items() for claim_id in item["claim_ids"][:(capabilities or passes)[category]]]
    capabilities_value = {"schema": "kronos_candidate_capabilities.v2", "claim_ids": sorted(capability_ids)}
    capabilities_raw = _raw(capabilities_value)
    objects["agent://capabilities"] = capabilities_raw
    source_sha, records = source_ref["sha256"], {}
    for category, item in SCORECARD["categories"].items():
        for index, claim_id in ((index, claim_id) for index, claim_id in enumerate(item["claim_ids"]) if claim_id != "E3.R"):
            status = "PASS" if (claim_id == "A01" and violations) or index < passes[category] else "FAIL"
            receipt_raw = _raw(_signed_receipt(claim_id, source_sha, status, (violations or []) if claim_id == "A01" else []))
            receipt_uri = f"agent://receipt-{claim_id}"
            objects[receipt_uri] = receipt_raw
            refs = [evidence.object_ref(receipt_uri, receipt_raw)]
            claim_raw = _raw({"schema": "kronos_evidence_claim.v2", "kind": "e3-runtime" if claim_id == "E3.R" else "claim-99", "claim_id": claim_id, "evidence_refs": refs})
            records[claim_id] = claim_raw
            objects[f"agent://claim-{claim_id}"] = claim_raw
    ids = sorted(claim_id for claim_id in SCORECARD["claims"] if claim_id != "E3.R")
    preview = evidence.build_preview_99({claim_id: records[claim_id] for claim_id in ids}, ids, objects)
    objects["agent://preview"] = preview
    pre_raw = evidence.build_preclosure({"preview_99": evidence.object_ref("agent://preview", preview), "candidate_source": source_ref, "scorecard": scorecard_ref, "capabilities": evidence.object_ref("agent://capabilities", capabilities_raw)}, [{"template_id": "E3.R", "claim_id": "E3.R", "schema": "kronos_e3_runtime.v2"}], objects)
    objects["agent://pre"] = pre_raw
    e3_receipt_raw = _raw(_signed_receipt("E3.R", source_sha, "PASS" if "E3.R" in capability_ids else "FAIL", []))
    objects["agent://receipt-E3.R"] = e3_receipt_raw
    records["E3.R"] = _raw({"schema": "kronos_evidence_claim.v2", "kind": "e3-runtime", "claim_id": "E3.R", "evidence_refs": [evidence.object_ref("agent://pre", pre_raw), evidence.object_ref("agent://receipt-E3.R", e3_receipt_raw)]})
    objects["agent://claim-E3.R"] = records["E3.R"]
    candidate = evidence.build_candidate_map(evidence.object_ref("agent://pre", pre_raw), source_ref, scorecard_ref, capabilities_value, {claim_id: records[claim_id] for claim_id in ids}, records["E3.R"], ids, objects)
    return candidate, objects
def _fixture(passes: dict[str, int], capabilities: dict[str, int] | None = None, violations: list[str] | None = None) -> tuple[bytes, dict[str, bytes]]:
    candidate, objects = _fixture_objects(passes, capabilities, violations)
    return candidate, {hashlib.sha256(value).hexdigest(): value for value in objects.values()}


def _authenticated_assurances(
    objects: dict[str, bytes],
    candidate_ref: dict[str, object],
    preclosure_ref: dict[str, object],
    namespace: str,
) -> tuple[list[dict[str, object]], object, object]:
    """Issue independent role receipts through the test bridge authority."""
    from stom_rl.v5_authority_bridge import (
        InMemoryRequestConsumptionStore,
        LiteralRawResolver,
        validate_and_issue_receipt,
    )

    tests_dir = str(Path(__file__).parent)
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    bridge = importlib.import_module("test_kronos_v5_authority_bridge")
    merged = dict(objects)
    receipts: list[dict[str, object]] = []
    authority = None
    for scope in ("OPERATOR_A", "OPERATOR_B", "TASK_SCORE", "ARCHITECT_REVIEW", "CRITIC_REVIEW", "EXECUTOR_QA"):
        def bind(payload: dict[str, object], role_resolver: object) -> None:
            role_resolver._objects.update(objects)

            def replace_designated_refs(value: object) -> None:
                if isinstance(value, dict):
                    if value.get("uri") == "agent://map":
                        value.clear()
                        value.update(candidate_ref)
                    elif value.get("uri") == "agent://pre":
                        value.clear()
                        value.update(preclosure_ref)
                    else:
                        for child in value.values():
                            replace_designated_refs(child)
                elif isinstance(value, list):
                    for child in value:
                        replace_designated_refs(child)

            replace_designated_refs(payload)

        request_ref, export_ref, role_resolver, role_authority = bridge._rebuild_payload(scope, bind)
        receipt_raw = validate_and_issue_receipt(
            request_ref=request_ref,
            export_ref=export_ref,
            resolver=role_resolver,
            authority=role_authority,
            request_store=InMemoryRequestConsumptionStore(),
        )
        receipt_uri = f"agent://receipt-{namespace}-{scope.lower()}"
        role_resolver._objects[receipt_uri] = receipt_raw
        merged.update(role_resolver._objects)
        receipts.append(evidence.object_ref(receipt_uri, receipt_raw))
        authority = role_authority
    assert authority is not None
    authority = dataclasses.replace(
        authority,
        independent_principals={rule[2]: frozenset({"agent://prior"}) for rule in bridge.RULES.values()},
    )
    return receipts, LiteralRawResolver(merged, resolved_at="2026-01-01T00:00:07Z"), authority


def _result(raw: bytes, objects: dict[str, bytes]) -> dict:
    out = dag.score_candidate_map(raw, resolver=lambda ref: objects[ref["sha256"]])
    assert out.endswith(b"\n")
    return json.loads(out)


def test_all_score_vectors_and_real_signatures() -> None:
    for case in VECTORS["cases"]:
        if "passes" not in case:
            continue
        raw, objects = _fixture(case["passes"], case.get("capabilities"), case.get("violations"))
        result = _result(raw, objects)
        assert result["raw_total"] == case["expected_raw_total"]
        assert result["gate"]["passed"] is case.get("expected_gate", True)
        assert result["six_locks_false"] == LOCKS
        for field in ("expected_floor_failures", "expected_option_ceilings", "expected_effective_total"):
            if field in case: assert result[{"expected_floor_failures":"floor_failures", "expected_option_ceilings":"capability_option_ceilings", "expected_effective_total":"effective_total"}[field]] == case[field]


def test_real_signature_tamper_malformed_proof_and_producer_invalid_candidates_reject() -> None:
    raw, objects = _fixture({"A": 23, "B": 23, "C": 18, "D": 13, "E": 13})
    candidate = json.loads(raw); claim_ref = candidate["claims"][0]["evidence_ref"]; claim = json.loads(objects[claim_ref["sha256"]]); receipt_ref = claim["evidence_refs"][0]; receipt = json.loads(objects[receipt_ref["sha256"]])
    receipt["authority_proof"]["signature"] = "A" * 86
    bad = _raw(receipt); objects[hashlib.sha256(bad).hexdigest()] = bad; receipt_ref.update(sha256=hashlib.sha256(bad).hexdigest(), byte_length=len(bad))
    bad_claim = _raw(claim); objects[hashlib.sha256(bad_claim).hexdigest()] = bad_claim; claim_ref.update(sha256=hashlib.sha256(bad_claim).hexdigest(), byte_length=len(bad_claim))
    with pytest.raises(dag.ScoreDagError): _result(_raw(candidate), objects)
    candidate = json.loads(raw); candidate["claims"][1]["claim_id"] = candidate["claims"][0]["claim_id"]
    with pytest.raises(dag.ScoreDagError): _result(_raw(candidate), objects)
def test_score_dag_rejects_boolean_source_byte_length_before_scoring() -> None:
    raw, objects = _fixture({"A": 23, "B": 23, "C": 18, "D": 13, "E": 13})
    candidate = json.loads(raw)
    source_ref = candidate["candidate_source_ref"]
    source = json.loads(objects[source_ref["sha256"]])
    source["files"][0]["byte_length"] = True
    source_raw = _raw(source)
    source_ref.update(sha256=hashlib.sha256(source_raw).hexdigest(), byte_length=len(source_raw))
    objects[source_ref["sha256"]] = source_raw
    with pytest.raises(dag.ScoreDagError, match="canonical source identity"):
        _result(_raw(candidate), objects)

def test_malformed_proof_boundaries_raise_stable_score_dag_errors() -> None:
    raw, objects = _fixture({"A": 23, "B": 23, "C": 18, "D": 13, "E": 13})
    candidate = json.loads(raw)
    claim = json.loads(objects[candidate["claims"][0]["evidence_ref"]["sha256"]])
    receipt = json.loads(objects[claim["evidence_refs"][0]["sha256"]])
    definition = SCORECARD["claims"]["A01"]
    source_sha = candidate["candidate_source_ref"]["sha256"]
    valid = receipt["authority_proof"]
    assert VECTORS["malformed_proof_cases"] == ["null", "list", "non_array_codes", "duplicate_codes", "unsorted_codes", "unknown_code", "signed_field_mismatch", "status_mismatch"]
    malformed = [
        None,
        [],
        {**valid, "violation_codes": "UNAPPROVED_CONTRACT_OR_API_CHANGE"},
        {**valid, "violation_codes": ["UNAPPROVED_CONTRACT_OR_API_CHANGE", "UNAPPROVED_CONTRACT_OR_API_CHANGE"]},
        {**valid, "violation_codes": ["UNAPPROVED_CONTRACT_OR_API_CHANGE", "FRESH_OOS_MISREPRESENTATION"]},
        {**valid, "violation_codes": ["UNKNOWN"]},
        {**valid, "claim_id": "A02"},
        {**valid, "status": "FAIL"},
    ]
    for proof in malformed:
        with pytest.raises(dag.ScoreDagError):
            dag._verify_proof(proof, definition, receipt, source_sha, SCORECARD)

def test_every_rejection_vector_is_materialized() -> None:
    base_raw, base_objects = _fixture({"A": 23, "B": 23, "C": 18, "D": 13, "E": 13})
    mutations = {case["mutation"] for case in VECTORS["cases"] if "mutation" in case}
    assert mutations == {"wrong_evidence_claim_kind", "no_verification_receipt", "multiple_verification_receipts", "duplicate_claim_id", "remove_claim", "complete_false", "evidence_raw_sha_mismatch", "pass_unavailable_claim"}
    for mutation in mutations:
        candidate, objects = json.loads(base_raw), dict(base_objects)
        if mutation == "duplicate_claim_id":
            candidate["claims"][1]["claim_id"] = candidate["claims"][0]["claim_id"]
        elif mutation == "remove_claim":
            candidate["claims"].pop()
        elif mutation == "complete_false":
            candidate["complete"] = False
        elif mutation == "evidence_raw_sha_mismatch":
            candidate["claims"][0]["evidence_ref"]["sha256"] = "0" * 64
        elif mutation == "pass_unavailable_claim":
            candidate["capabilities"]["claim_ids"].remove("A01")
        else:
            record = candidate["claims"][0]
            claim = json.loads(objects[record["evidence_ref"]["sha256"]])
            if mutation == "wrong_evidence_claim_kind":
                claim["kind"] = "wrong"
            elif mutation == "no_verification_receipt":
                claim["evidence_refs"] = []
            else:
                claim["evidence_refs"].append(dict(claim["evidence_refs"][0]))
            claim_raw = _raw(claim)
            objects[hashlib.sha256(claim_raw).hexdigest()] = claim_raw
            record["evidence_ref"].update(sha256=hashlib.sha256(claim_raw).hexdigest(), byte_length=len(claim_raw))
        with pytest.raises(dag.ScoreDagError):
            _result(_raw(candidate), objects)



def test_ab_bytes_are_invariant_to_authenticated_downstream_final_maps() -> None:
    raw, objects = _fixture_objects({"A": 23, "B": 23, "C": 18, "D": 13, "E": 13})
    candidate_uri = "agent://map"
    objects[candidate_uri] = raw
    candidate_ref = evidence.object_ref(candidate_uri, raw)
    preclosure_ref = evidence.object_ref("agent://pre", objects["agent://pre"])

    snapshots: list[dict[str, bytes]] = []
    final_maps: list[bytes] = []
    for namespace in ("downstream-a", "downstream-b"):
        receipts, resolver, authority = _authenticated_assurances(objects, candidate_ref, preclosure_ref, namespace)
        assert len(receipts) == 6
        final_raw = evidence.build_final_map(candidate_ref, receipts, objects, resolver, authority)
        evidence.validate_final_map(final_raw, objects, candidate_ref, resolver, authority)
        final_value = evidence.parse_raw_jcs(final_raw)
        assert set(final_value) == {"schema", "kind", "candidate_map_ref", "assurance_refs"}
        assert final_value["candidate_map_ref"] == candidate_ref
        final_maps.append(final_raw)
        snapshot = {hashlib.sha256(value).hexdigest(): value for value in resolver._objects.values()}
        snapshot[hashlib.sha256(final_raw).hexdigest()] = final_raw
        snapshots.append(snapshot)

    assert final_maps[0] != final_maps[1]
    point_a = dag.score_candidate_map(raw, resolver=lambda ref: snapshots[0][ref["sha256"]], process_label="A")
    point_b = dag.score_candidate_map(raw, resolver=lambda ref: snapshots[1][ref["sha256"]], process_label="B")
    assert point_a == point_b


def test_score_assurance_schema_accepts_exact_score_and_rejects_open_shapes() -> None:
    raw, objects = _fixture({"A": 23, "B": 23, "C": 18, "D": 13, "E": 13})
    score = _result(raw, objects)
    schema = json.loads((ROOT / "docs" / "schemas" / "kronos_score_assurance.v2.schema.json").read_text(encoding="utf-8"))
    external = [json.loads((ROOT / "docs" / "schemas" / name).read_text(encoding="utf-8")) for name in ("kronos_evidence_dag.v2.schema.json", "kronos_terminal_closure.v2.schema.json")]
    registry = Registry().with_resources([(item["$id"], Resource.from_contents(item)) for item in external])
    validator = Draft202012Validator(schema, registry=registry)
    assert not list(validator.iter_errors(score))
    dag.validate_point_score(score)
    score["claim_results"].pop("A01")
    assert list(validator.iter_errors(score))
    with pytest.raises(dag.ScoreDagError, match="semantic equation"):
        dag.validate_point_score(score)
    digest = "a" * 64
    ref = lambda schema_name: {"uri": f"agent://test/{schema_name}", "sha256": digest, "byte_length": 1, "schema": schema_name}
    assurance = {"schema": "kronos_score_assurance.v2", "candidate_map_ref": ref("kronos_candidate_map.v2"), "point_score_ref_a": ref("kronos_point_score.v2"), "point_score_ref_b": ref("kronos_point_score.v2"), "assurance_decision_ref": ref("kronos_assurance_decision.v2"), "preterminal_ref": ref("kronos_preterminal_assurance.v2"), "terminal_ref": ref("kronos_terminal_closure.v2")}
    assert not list(validator.iter_errors(assurance))
    assurance["terminal_ref"]["schema"] = "wrong"
    assert list(validator.iter_errors(assurance))
    decision = {"schema": "kronos_assurance_decision.v2", "point_scores_identical": True, "point_pass": True, "assurance_eligible": True, "blocking_codes": []}
    assert not list(validator.iter_errors(decision))
    decision["point_pass"] = False
    assert list(validator.iter_errors(decision))
    candidate = json.loads(raw)
    claim = json.loads(objects[candidate["claims"][0]["evidence_ref"]["sha256"]])
    receipt = json.loads(objects[claim["evidence_refs"][0]["sha256"]])
    assert not list(validator.iter_errors(receipt))
    receipt["authority_proof"] = None
    assert list(validator.iter_errors(receipt))
    for value in VECTORS["assurance_decision_cases"]:
        value = {"schema": "kronos_assurance_decision.v2", **value}
        assert not list(validator.iter_errors(value))
        dag.validate_assurance_decision(value)
    with pytest.raises(dag.ScoreDagError, match="assurance decision"):
        dag.validate_assurance_decision({"point_scores_identical": True, "point_pass": True, "assurance_eligible": False, "blocking_codes": ["POINT_SCORE_MISMATCH", "ASSURANCE_BLOCK"]})
