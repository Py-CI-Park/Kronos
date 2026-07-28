"""Legacy V5 scorer is a byte-identical CLI wrapper around the score DAG."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from stom_rl import v5_evidence_dag as evidence
from stom_rl import v5_score_dag as dag

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "score_kronos_dashboard_v5.py"
SPEC = importlib.util.spec_from_file_location("v5_score", SCRIPT)
assert SPEC and SPEC.loader
v5_score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v5_score)
SCORECARD = json.loads((ROOT / "docs" / "kronos_dashboard_v5_scorecard_v2.json").read_text(encoding="utf-8"))
KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
SCORECARD_SHA256 = "4afa3656e8bed8e5adae8bc3e99f89d5b450f8c56561429cb121aa601458ec7b"
LOCKS = {"promotion_allowed": False, "model_build_allowed": False, "paper_forward_allowed": False, "live_broker_order_allowed": False, "profitability_claim_allowed": False, "go_summary_allowed": False}


def _raw(value: dict) -> bytes:
    return dag.canonical_bytes(value)


def _receipt(claim_id: str, source_sha: str, status: str, violations: list[str]) -> dict:
    definition = SCORECARD["claims"][claim_id]
    unsigned = {"schema": "kronos_claim_authority_proof.v1", "claim_id": claim_id, "candidate_source_sha256": source_sha, "claim_definition_sha256": hashlib.sha256(_raw(definition)).hexdigest(), "verifier": definition["verifier"], "evidence_schema": definition["required_evidence_schema"], "status": status, "violation_codes": sorted(violations)}
    signature = KEY.sign(SCORECARD["authority_proof"]["domain_separator"].encode("ascii") + b"\0" + _raw(unsigned))
    return {"schema": "kronos_claim_verification.v1", "claim_id": claim_id, "candidate_source_sha256": source_sha, "claim_definition_sha256": unsigned["claim_definition_sha256"], "verifier": unsigned["verifier"], "evidence_schema": unsigned["evidence_schema"], "status": status, "authority_proof": {**unsigned, "signature": base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")}}


def _candidate(passes: dict[str, int], violations: list[str] | None = None) -> tuple[bytes, dict[str, bytes]]:
    source = {"schema": "kronos_source_identity.v1", "source_commit": "a" * 40, "source_tree": "b" * 40, "scope_manifest_sha256": v5_score._CANONICAL_SCOPE_DIGEST, "files": [{"path": "stom_rl/v5_score_dag.py", "git_mode": "100644", "sha256": "d" * 64, "byte_length": 1}]}
    source_raw, scorecard_raw = _raw(source), _raw(SCORECARD)
    objects = {"agent://test/source": source_raw, "agent://test/scorecard": scorecard_raw}
    source_ref, scorecard_ref = evidence.object_ref("agent://test/source", source_raw), evidence.object_ref("agent://test/scorecard", scorecard_raw)
    capability_ids = [claim_id for category, item in SCORECARD["categories"].items() for claim_id in item["claim_ids"][:passes[category]]]
    capabilities = {"schema": "kronos_candidate_capabilities.v2", "claim_ids": sorted(capability_ids)}
    capabilities_raw = _raw(capabilities)
    objects["agent://test/capabilities"] = capabilities_raw
    source_sha, records = source_ref["sha256"], {}
    for category, item in SCORECARD["categories"].items():
        for index, claim_id in ((index, claim_id) for index, claim_id in enumerate(item["claim_ids"]) if claim_id != "E3.R"):
            status = "PASS" if (claim_id == "A01" and violations) or index < passes[category] else "FAIL"
            receipt_raw = _raw(_receipt(claim_id, source_sha, status, (violations or []) if claim_id == "A01" else []))
            receipt_uri = f"agent://test/receipt/{claim_id}"
            objects[receipt_uri] = receipt_raw
            records[claim_id] = _raw({"schema": "kronos_evidence_claim.v2", "kind": "claim-99", "claim_id": claim_id, "evidence_refs": [evidence.object_ref(receipt_uri, receipt_raw)]})
            objects[f"agent://test/claim/{claim_id}"] = records[claim_id]
    ids = sorted(claim_id for claim_id in SCORECARD["claims"] if claim_id != "E3.R")
    preview = evidence.build_preview_99({claim_id: records[claim_id] for claim_id in ids}, ids, objects)
    objects["agent://test/preview-99"] = preview
    preclosure_raw = evidence.build_preclosure({"preview_99": evidence.object_ref("agent://test/preview-99", preview), "candidate_source": source_ref, "scorecard": scorecard_ref, "capabilities": evidence.object_ref("agent://test/capabilities", capabilities_raw)}, [{"template_id": "E3.R", "claim_id": "E3.R", "schema": "kronos_e3_runtime.v2"}], objects)
    objects["agent://test/preclosure"] = preclosure_raw
    e3_receipt_raw = _raw(_receipt("E3.R", source_sha, "PASS" if "E3.R" in capability_ids else "FAIL", []))
    objects["agent://test/receipt/E3.R"] = e3_receipt_raw
    records["E3.R"] = _raw({"schema": "kronos_evidence_claim.v2", "kind": "e3-runtime", "claim_id": "E3.R", "evidence_refs": [evidence.object_ref("agent://test/preclosure", preclosure_raw), evidence.object_ref("agent://test/receipt/E3.R", e3_receipt_raw)]})
    objects["agent://test/claim/E3.R"] = records["E3.R"]
    candidate = evidence.build_candidate_map(evidence.object_ref("agent://test/preclosure", preclosure_raw), source_ref, scorecard_ref, capabilities, {claim_id: records[claim_id] for claim_id in ids}, records["E3.R"], ids, objects)
    return candidate, {hashlib.sha256(raw).hexdigest(): raw for raw in objects.values()}


def test_cli_and_legacy_core_match_authoritative_score_bytes(tmp_path: Path) -> None:
    candidate, objects = _candidate({"A": 23, "B": 23, "C": 18, "D": 13, "E": 13})
    expected = dag.score_candidate_map(candidate, resolver=lambda ref: objects[ref["sha256"]])
    assert v5_score.score_candidate_map(candidate, resolver=lambda ref: objects[ref["sha256"]]) == expected
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_bytes(candidate)
    objects_dir = tmp_path / "objects"
    objects_dir.mkdir()
    for digest, raw in objects.items():
        (objects_dir / digest).write_bytes(raw)
    output_path = tmp_path / "point-score.json"
    completed = subprocess.run([sys.executable, str(SCRIPT), "--candidate-map", str(candidate_path), "--objects-dir", str(objects_dir), "--out", str(output_path)], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert completed.stdout == expected == output_path.read_bytes()
    assert expected.endswith(b"\n") and not expected.endswith(b"\n\n")
    result = json.loads(expected)
    assert result["schema"] == "kronos_point_score.v2"
    assert result["scorecard_sha256"] == hashlib.sha256(_raw(SCORECARD)).hexdigest()
    assert result["category_scores"] == {"A": 23, "B": 23, "C": 18, "D": 13, "E": 13}
    assert result["floor_failures"] == []
    assert SCORECARD["schema"] == "kronos_dashboard_v5_scorecard.v2"
    assert v5_score._DEFAULT_SCORECARD.name == "kronos_dashboard_v5_scorecard_v2.json"
    assert v5_score._CANONICAL_SCORECARD_DIGEST == SCORECARD_SHA256 == hashlib.sha256(_raw(SCORECARD)).hexdigest()
    assert result["gate"] == {"id": "engineering_90", "passed": True, "total_min": 90}
    assert result["six_locks_false"] == LOCKS


def test_signed_ordinary_fail_is_zero_without_cap_but_signed_violation_caps() -> None:
    passes = {"A": 25, "B": 25, "C": 20, "D": 15, "E": 15}
    ordinary_candidate, ordinary_objects = _candidate({**passes, "A": 24})
    ordinary = json.loads(v5_score.score_candidate_map(ordinary_candidate, resolver=lambda ref: ordinary_objects[ref["sha256"]]))
    assert ordinary["raw_total"] == ordinary["effective_total"] == 99
    assert ordinary["active_hard_caps"] == []
    violating_candidate, violating_objects = _candidate(passes, ["UNAPPROVED_CONTRACT_OR_API_CHANGE"])
    violating = json.loads(v5_score.score_candidate_map(violating_candidate, resolver=lambda ref: violating_objects[ref["sha256"]]))
    assert violating["raw_total"] == 100
    assert violating["active_hard_caps"] == ["unapproved_contract_or_api_change"]
    assert violating["effective_total"] <= 89
