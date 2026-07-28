from __future__ import annotations

import dataclasses
import importlib
import json
import sys
from pathlib import Path

import pytest

from stom_rl.v5_authority_bridge import (
    InMemoryRequestConsumptionStore,
    LiteralRawResolver,
    validate_and_issue_receipt,
)
from stom_rl.v5_evidence_dag import (
    EvidenceDagError,
    build_candidate_map,
    build_final_map,
    build_preclosure,
    build_preview_99,
    canonical_bytes,
    object_ref,
    validate_acyclic_graph,
    _graph_projection,
    parse_raw_jcs,
    validate_candidate_map,
    validate_final_map,
)


VECTORS = json.loads((Path(__file__).parent / "data" / "kronos_evidence_dag_v2_vectors.json").read_text(encoding="utf-8"))
IDS = [*[f"A{n:02d}" for n in range(1, 26)], *[f"B{n:02d}" for n in range(1, 26)], *[f"C{n:02d}" for n in range(1, 21)], *[f"D{n:02d}" for n in range(1, 16)], "E01", "E02", *[f"E{n:02d}" for n in range(4, 16)]]
SEED_URI = "agent://evidence/seed"
PREVIEW_URI = "agent://evidence/preview-99"
PRECLOSURE_URI = "agent://pre"
SOURCE_URI = "agent://evidence/source"
SCORECARD_URI = "agent://evidence/scorecard"
CANDIDATE_URI = "agent://map"
VECTOR_IDS = [case["id"] for case in VECTORS["cases"]]
CONSUMED_VECTOR_IDS: list[str] = []


@pytest.fixture(scope="module", autouse=True)
def _all_vector_ids_are_consumed_once() -> object:
    yield
    assert CONSUMED_VECTOR_IDS == VECTOR_IDS
    assert len(CONSUMED_VECTOR_IDS) == len(set(CONSUMED_VECTOR_IDS))


def _fixture() -> tuple[dict[str, bytes], dict[str, bytes], bytes, dict[str, object], dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    seed = canonical_bytes({"schema": "kronos_seed.v2", "kind": "seed"})
    source = canonical_bytes({"schema": "kronos_source_identity.v1", "kind": "source"})
    scorecard = canonical_bytes({"schema": "kronos_dashboard_v5_scorecard.v2", "kind": "scorecard"})
    capabilities = {"schema": "kronos_candidate_capabilities.v2", "claim_ids": ["A01", "E3.R"]}
    capabilities_raw = canonical_bytes(capabilities)
    objects = {SEED_URI: seed, SOURCE_URI: source, SCORECARD_URI: scorecard, "agent://evidence/capabilities": capabilities_raw}
    seed_ref = object_ref(SEED_URI, seed)
    records = {
        claim_id: canonical_bytes({"schema": "kronos_evidence_claim.v2", "kind": "claim-99", "claim_id": claim_id, "evidence_refs": [seed_ref]})
        for claim_id in IDS
    }
    objects.update({f"agent://evidence/claims/{claim_id}": raw for claim_id, raw in records.items()})
    preview = build_preview_99(records, IDS, objects)
    objects[PREVIEW_URI] = preview
    preclosure = build_preclosure({"preview_99": object_ref(PREVIEW_URI, preview), "candidate_source": object_ref(SOURCE_URI, source), "scorecard": object_ref(SCORECARD_URI, scorecard), "capabilities": object_ref("agent://evidence/capabilities", capabilities_raw)}, [{"template_id": "E3.R", "claim_id": "E3.R", "schema": "kronos_e3_runtime.v2"}], objects)
    objects[PRECLOSURE_URI] = preclosure
    preclosure_ref = object_ref(PRECLOSURE_URI, preclosure)
    e3 = canonical_bytes({"schema": "kronos_evidence_claim.v2", "kind": "e3-runtime", "claim_id": "E3.R", "evidence_refs": [preclosure_ref]})
    objects["agent://evidence/claims/E3.R"] = e3
    return objects, records, e3, object_ref(SOURCE_URI, source), object_ref(SCORECARD_URI, scorecard), capabilities, preclosure_ref, object_ref("agent://evidence/claims/E3.R", e3)


def _candidate(objects: dict[str, bytes], records: dict[str, bytes], e3: bytes, source_ref: dict[str, object], scorecard_ref: dict[str, object], capabilities: dict[str, object], preclosure_ref: dict[str, object]) -> bytes:
    return build_candidate_map(preclosure_ref, source_ref, scorecard_ref, capabilities, records, e3, IDS, objects)


def _authenticated_assurances(
    objects: dict[str, bytes],
    candidate_ref: dict[str, object],
    preclosure_ref: dict[str, object],
) -> tuple[list[dict[str, object]], LiteralRawResolver, object]:
    """Issue all six role receipts with the bridge's real signed test authority."""
    sys.path.insert(0, str(Path(__file__).parent))
    bridge = importlib.import_module("test_kronos_v5_authority_bridge")
    merged: dict[str, bytes] = dict(objects)
    receipts: list[dict[str, object]] = []
    authority = None
    for scope in ("OPERATOR_A", "OPERATOR_B", "TASK_SCORE", "ARCHITECT_REVIEW", "CRITIC_REVIEW", "EXECUTOR_QA"):
        def bind(payload: dict[str, object], role_resolver: LiteralRawResolver) -> None:
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
        receipt_uri = f"agent://receipt_{scope.lower()}"
        role_resolver._objects[receipt_uri] = receipt_raw
        merged.update(role_resolver._objects)
        receipts.append(object_ref(receipt_uri, receipt_raw))
        authority = role_authority
    assert authority is not None
    authority = dataclasses.replace(
        authority,
        independent_principals={rule[2]: frozenset({"agent://prior"}) for rule in bridge.RULES.values()},
    )
    return receipts, LiteralRawResolver(merged, resolved_at="2026-01-01T00:00:07Z"), authority


def test_deterministic_preview_and_complete_candidate_preserve_raw_claim_bytes() -> None:
    objects, records, e3, source_ref, scorecard_ref, capabilities, preclosure_ref, e3_ref = _fixture()
    preview = build_preview_99(records, IDS, objects)
    candidate = _candidate(objects, records, e3, source_ref, scorecard_ref, capabilities, preclosure_ref)
    assert preview == build_preview_99(records, IDS, objects)
    assert candidate == _candidate(objects, records, e3, source_ref, scorecard_ref, capabilities, preclosure_ref)
    value = validate_candidate_map(candidate, IDS, objects, preclosure_ref, e3_ref)
    assert set(value) == {"schema", "complete", "candidate_source_ref", "scorecard_ref", "capabilities", "claims"}
    assert [record["claim_id"] for record in value["claims"]] == sorted([*IDS, "E3.R"])
    assert set(VECTORS["candidate_contract"]["keys"]) == set(value)
    assert len(value["claims"]) == VECTORS["candidate_contract"]["claims"]
    assert all(set(record) == set(VECTORS["candidate_contract"]["claim_record_keys"]) and record["evidence_ref"]["schema"] == VECTORS["candidate_contract"]["claim_ref_schema"] for record in value["claims"])
    assert all(objects[record["evidence_ref"]["uri"]] == records[record["claim_id"]] for record in value["claims"] if record["claim_id"] != "E3.R")


def _final_context() -> tuple[dict[str, bytes], dict[str, object], list[dict[str, object]], LiteralRawResolver, object, bytes]:
    objects, records, e3, source_ref, scorecard_ref, capabilities, preclosure_ref, _ = _fixture()
    candidate = _candidate(objects, records, e3, source_ref, scorecard_ref, capabilities, preclosure_ref)
    objects[CANDIDATE_URI] = candidate
    candidate_ref = object_ref(CANDIDATE_URI, candidate)
    receipts, resolver, authority = _authenticated_assurances(objects, candidate_ref, preclosure_ref)
    final = build_final_map(candidate_ref, receipts, objects, resolver, authority)
    return objects, candidate_ref, receipts, resolver, authority, final
def test_final_map_requires_six_reverified_bridge_receipts() -> None:
    objects, candidate_ref, receipts, resolver, authority, final = _final_context()
    validate_final_map(final, objects, candidate_ref, resolver, authority)
    assert json.loads(final)["assurance_refs"] == receipts



def _candidate_context() -> tuple[dict[str, bytes], bytes, dict[str, object], dict[str, object], dict[str, object], dict[str, object], bytes]:
    objects, records, e3, source_ref, scorecard_ref, capabilities, preclosure_ref, e3_ref = _fixture()
    candidate = _candidate(objects, records, e3, source_ref, scorecard_ref, capabilities, preclosure_ref)
    return objects, candidate, source_ref, scorecard_ref, capabilities, preclosure_ref, e3_ref


def _reject_candidate(raw: bytes, objects: dict[str, bytes], preclosure_ref: dict[str, object], e3_ref: dict[str, object]) -> None:
    with pytest.raises(EvidenceDagError):
        validate_candidate_map(raw, IDS, objects, preclosure_ref, e3_ref)


def _closed_final_projection(
    objects: dict[str, bytes],
    receipts: list[dict[str, object]],
    resolver: LiteralRawResolver,
    final: bytes,
) -> dict[str, bytes]:
    closed_objects = dict(objects)
    for receipt in receipts:
        uri = str(receipt["uri"])
        closed_objects[uri] = resolver.resolve_record(uri, "raw").raw
    return _graph_projection(closed_objects, final)


def _rebind_parents(graph: dict[str, bytes], changed_uri: str) -> None:
    pending = [changed_uri]
    while pending:
        target = pending.pop()
        target_ref = object_ref(target, graph[target])
        for uri, raw in tuple(graph.items()):
            value = json.loads(raw)
            if value.get("schema") == "kronos_gjc_validation_receipt.v2":
                continue

            def rebind(item: object) -> bool:
                if isinstance(item, dict):
                    if set(item) == {"uri", "sha256", "byte_length", "schema"}:
                        if item["uri"] == target and item != target_ref:
                            item.clear()
                            item.update(target_ref)
                            return True
                        return False
                    return any(rebind(child) for child in item.values())
                if isinstance(item, list):
                    return any(rebind(child) for child in item)
                return False

            if uri != target and rebind(value):
                graph[uri] = canonical_bytes(value)
                pending.append(uri)


def _reject_topology(case: dict[str, object]) -> None:
    objects, _, receipts, resolver, _, final = _final_context()
    graph = _closed_final_projection(objects, receipts, resolver, final)
    validate_acyclic_graph(graph)
    mutation = case["mutation"]
    assert isinstance(mutation, dict)

    if case["id"] == "disconnected_edge":
        raw = mutation["raw"]
        assert isinstance(raw, dict)
        graph[str(mutation["uri"])] = canonical_bytes(raw)
    else:
        source = str(mutation["source"] if "source" in mutation else mutation["first"])
        value = json.loads(graph[source])
        if case["id"] == "self_edge":
            value[str(mutation["field"])]["uri"] = mutation["uri"]
        elif case["id"] == "future_edge":
            target = str(mutation["uri"])
            value[str(mutation["field"])] = object_ref(target, graph[target])
        elif case["id"] == "forward_edge":
            target = str(mutation["uri"])
            value["required_dependencies"][str(mutation["dependency"])] = object_ref(target, graph[target])
        else:
            first = json.loads(graph[str(mutation["first"])])
            second = json.loads(graph[str(mutation["second"])])
            first["required_dependencies"]["candidate_source"]["uri"] = mutation["second"]
            second["candidate_source_ref"]["uri"] = mutation["first"]
            graph[str(mutation["second"])] = canonical_bytes(second)
            value = first
        graph[source] = canonical_bytes(value)
        if case["id"] not in {"self_edge", "transitive_cycle"}:
            _rebind_parents(graph, source)

    with pytest.raises(EvidenceDagError, match=f"^{case['expected_error']}$"):
        validate_acyclic_graph(graph)


@pytest.mark.parametrize("case", VECTORS["cases"], ids=VECTOR_IDS)
def test_evidence_dag_v2_vector_dispatcher(case: dict[str, object]) -> None:
    """Execute every literal vector at its declared validation stage exactly once."""
    CONSUMED_VECTOR_IDS.append(case["id"])
    stage = case["stage"]

    if stage == "parse_raw_jcs":
        raw = case["raw"]
        assert isinstance(raw, str)
        with pytest.raises(EvidenceDagError):
            parse_raw_jcs(raw.encode("utf-8"))
        return

    if stage == "topology":
        _reject_topology(case)
        return

    if stage == "final":
        objects, candidate_ref, receipts, resolver, authority, final = _final_context()
        value = json.loads(final)
        mutation = case["mutation"]
        assert isinstance(mutation, dict)
        if case["id"] == "assurance_wrong_schema":
            value["assurance_refs"][0] = object_ref(SEED_URI, objects[SEED_URI])
        elif mutation.get("duplicate"):
            value["assurance_refs"][1] = dict(value["assurance_refs"][0])
        else:
            value["assurance_refs"].reverse()
        with pytest.raises(EvidenceDagError):
            validate_final_map(canonical_bytes(value), objects, candidate_ref, resolver, authority)
        return

    assert stage == "candidate"
    objects, candidate, source_ref, scorecard_ref, capabilities, preclosure_ref, e3_ref = _candidate_context()
    value = json.loads(candidate)
    mutation = case["mutation"]
    assert isinstance(mutation, dict)

    if case["id"] == "hash_consistent_claim_mutation":
        claim_id = str(mutation["claim_id"])
        claim_uri = f"agent://evidence/claims/{claim_id}"
        claim = json.loads(objects[claim_uri])
        claim["evidence_refs"] = mutation["evidence_refs"]
        objects[claim_uri] = canonical_bytes(claim)
        value["claims"][0]["evidence_ref"] = object_ref(claim_uri, objects[claim_uri])
    elif case["id"] == "preclosure_alias":
        preclosure = json.loads(objects[PRECLOSURE_URI])
        preclosure["required_dependencies"][str(mutation["dependency"])] = dict(preclosure["required_dependencies"][str(mutation["alias"])])
        objects[PRECLOSURE_URI] = canonical_bytes(preclosure)
        preclosure_ref = object_ref(PRECLOSURE_URI, objects[PRECLOSURE_URI])
        e3 = json.loads(objects["agent://evidence/claims/E3.R"])
        e3["evidence_refs"] = [preclosure_ref]
        objects["agent://evidence/claims/E3.R"] = canonical_bytes(e3)
        e3_ref = object_ref("agent://evidence/claims/E3.R", objects["agent://evidence/claims/E3.R"])
        _reject_candidate(candidate, objects, preclosure_ref, e3_ref)
        return
    elif case["id"] == "immutable_ref_tamper":
        value[str(mutation["field"])] = object_ref(str(mutation["uri"]), objects[str(mutation["uri"])])
    elif case["id"] == "embedded_claim":
        value[str(mutation["field"])] = mutation["value"]
    elif case["id"] == "reordered_claim_record":
        value["claims"].reverse()
    elif case["id"] == "duplicate_claim_ref":
        value["claims"][1] = dict(value["claims"][0])
    elif case["id"] == "missing_claim":
        value["claims"].pop(0)
    elif case["id"] == "foreign_claim_ref":
        foreign_uri = f"agent://evidence/claims/{mutation['claim_id']}"
        objects[foreign_uri] = canonical_bytes({"schema": "kronos_evidence_claim.v2", "kind": "claim-99", "claim_id": mutation["claim_id"], "evidence_refs": [object_ref(SEED_URI, objects[SEED_URI])]})
        value["claims"][0]["evidence_ref"] = object_ref(foreign_uri, objects[foreign_uri])
    elif case["id"] == "tampered_claim":
        claim_uri = f"agent://evidence/claims/{mutation['claim_id']}"
        claim = json.loads(objects[claim_uri])
        claim["evidence_refs"] = mutation["evidence_refs"]
        objects[claim_uri] = canonical_bytes(claim)
    elif case["id"] == "e3_without_preclosure":
        e3 = json.loads(objects["agent://evidence/claims/E3.R"])
        e3["evidence_refs"] = [object_ref(SEED_URI, objects[SEED_URI])]
        objects["agent://evidence/claims/E3.R"] = canonical_bytes(e3)
        with pytest.raises(EvidenceDagError):
            _candidate(objects, {claim_id: objects[f"agent://evidence/claims/{claim_id}"] for claim_id in IDS}, objects["agent://evidence/claims/E3.R"], source_ref, scorecard_ref, capabilities, preclosure_ref)
        return
    else:
        assert case["id"] == "candidate_incomplete"
        value[str(mutation["field"])] = mutation["value"]

    _reject_candidate(canonical_bytes(value), objects, preclosure_ref, e3_ref)
