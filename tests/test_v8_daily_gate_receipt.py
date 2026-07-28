import copy
import hashlib

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from stom_rl.daily_v8_gate_receipt import (
    ELIGIBLE_TOKEN,
    GateReceiptError,
    canonical_bytes,
    evidence_commitments,
    issue_gate_receipt,
    verify_gate_receipt,
)


def _sha(name):
    return hashlib.sha256(name.encode()).hexdigest()


def _manifest():
    passes = {str(seed): seed != 4 for seed in range(5)}
    metrics = {"nav": 60_100_000.0}
    picks = [0, 1, 10]
    return {
        "seeds": [0, 1, 2, 3, 4],
        "policy": {
            "score_rule": "unweighted_raw_member_score_mean_before_ranking_score_gt_0",
            "ranking": "top_10_distinct_by_score_then_symbol",
            "capital_krw": 60_000_000,
            "slot_budget_krw": 5_000_000,
            "slots": 10,
            "primary_cost_rate": 0.0023,
        },
        "ensemble": {"metrics": metrics, "pick_counts": picks},
        "jackknives": {str(seed): {"metrics": metrics, "pick_counts": picks, "passes": passes[str(seed)]} for seed in range(5)},
        "baselines": {name: {"nav": 60_000_000.0} for name in ("no_trade", "rule_topk_ret5", "rule_topk_low_vol", "rule_topk_inst", "random_topk")},
        "exposure_matched_random": {"reps": 20},
        "shuffled_label_ensemble": {
            "ensemble": {"metrics": metrics},
            "jackknives": {str(seed): {"metrics": metrics} for seed in range(5)},
            "controls": {"full": {"control_fails": False}, **{f"jackknife_{seed}": {"control_fails": False} for seed in range(5)}},
        },
        "verdict": {"value": ELIGIBLE_TOKEN, "passing_jackknives": ["0", "1", "2", "3"], "reasons": ["validation-only"]},
        "test": {"state": "NOT_RUN"},
        "false_research_locks": {"promotion_allowed": False, "go_summary_allowed": False},
        "artifact_commitments": {field: _sha(field) for field in ("trainer_sha256", "protocol_sha256", "public_artifact_sha256", "result_sha256", "baseline_sha256", "control_sha256")},
        "principals": {"trainer_principal_uri": "agent://trainer", "custodian_principal_uri": "agent://custodian"},
    }


def _inputs():
    private = Ed25519PrivateKey.generate()
    prereg = canonical_bytes({"status": "FROZEN", "prereg_id": "M3E"})
    members = tuple(_sha(f"member-{seed}") for seed in range(5))
    manifest_payload = _manifest()
    manifest_payload["artifact_commitments"].update(evidence_commitments(manifest_payload, members))
    manifest = canonical_bytes(manifest_payload)
    common = {"custody_uid": "m3e-custody-1", "test_sha256": _sha("sealed-test"), "gate_principal_uri": "agent://independent-gate", "gate_key_id": "m3e-gate-1", "issued_at": "2026-07-21T00:00:00Z", "expires_at": "2026-07-22T00:00:00Z"}
    return private, prereg, manifest, members, common


def _issue():
    private, prereg, manifest, members, common = _inputs()
    receipt = issue_gate_receipt(prereg, manifest, members, signing_key=private, **common)
    return private, prereg, manifest, members, common, receipt


def test_eligible_receipt_is_canonical_signed_commitments_only():
    private, prereg, manifest, members, common, receipt = _issue()
    statement = verify_gate_receipt(receipt, prereg, manifest, members, gate_public_key=private.public_key(), now="2026-07-21T12:00:00Z", expected_gate_principal_uri=common["gate_principal_uri"], expected_gate_key_id=common["gate_key_id"], custody_uid=common["custody_uid"], test_sha256=common["test_sha256"])
    assert statement["eligibility"] == ELIGIBLE_TOKEN
    assert set(statement) == {"schema", "prereg_sha256", "validation_manifest_sha256", "trainer_sha256", "protocol_sha256", "public_artifact_sha256", "member_artifact_sha256", "result_sha256", "baseline_sha256", "control_sha256", "custody_uid", "test_sha256", "eligibility", "issued_at", "expires_at", "gate_principal_uri", "gate_key_id"}
    assert b"path" not in receipt and b"label" not in receipt and b"credential" not in receipt


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(seeds=[0, 1, 2, 3]),
    lambda value: value["policy"].update(capital_krw=60_000_001),
    lambda value: value["policy"].update(slot_budget_krw=5_000_001),
    lambda value: value["policy"].update(primary_cost_rate=0.0022),
    lambda value: value["policy"].update(score_rule="weighted_mean"),
    lambda value: value["policy"].update(ranking="top_11"),
    lambda value: value["ensemble"].update(pick_counts=[11]),
    lambda value: value["jackknives"].pop("4"),
    lambda value: [entry.update(passes=False) for entry in value["jackknives"].values()],
    lambda value: value["baselines"].pop("random_topk"),
    lambda value: value["shuffled_label_ensemble"]["controls"]["full"].update(control_fails=True),
    lambda value: value["verdict"].update(value="GO_CANDIDATE_VALIDATION_ONLY"),
    lambda value: value["verdict"].update(value="INCONCLUSIVE"),
    lambda value: value["verdict"].update(value="NO_GO"),
    lambda value: value["false_research_locks"].update(go_summary_allowed=True),
    lambda value: value.update(test={"state": "RUN"}),
])
def test_issuance_fails_closed_for_invalid_evidence(mutation):
    private, prereg, _, members, common = _inputs()
    manifest = _manifest()
    mutation(manifest)
    with pytest.raises(GateReceiptError):
        issue_gate_receipt(prereg, canonical_bytes(manifest), members, signing_key=private, **common)


def test_rejects_wrong_key_expiry_swapped_commitments_and_replayable_shape():
    private, prereg, manifest, members, common, receipt = _issue()
    kwargs = {"gate_public_key": private.public_key(), "now": "2026-07-21T12:00:00Z", "custody_uid": common["custody_uid"], "test_sha256": common["test_sha256"]}
    with pytest.raises(GateReceiptError):
        verify_gate_receipt(receipt, prereg, manifest, members, gate_public_key=Ed25519PrivateKey.generate().public_key(), now=kwargs["now"], custody_uid=kwargs["custody_uid"], test_sha256=kwargs["test_sha256"])
    with pytest.raises(GateReceiptError):
        verify_gate_receipt(receipt, prereg, manifest, members, gate_public_key=kwargs["gate_public_key"], now="2026-07-23T00:00:00Z", custody_uid=kwargs["custody_uid"], test_sha256=kwargs["test_sha256"])
    with pytest.raises(GateReceiptError):
        verify_gate_receipt(receipt, prereg, manifest, tuple(reversed(members)), **kwargs)
    with pytest.raises(GateReceiptError):
        verify_gate_receipt(b'{"schema":"x"}', prereg, manifest, members, **kwargs)


def test_signer_cannot_be_trainer_or_custodian():
    private, prereg, manifest, members, common = _inputs()
    for principal in ("agent://trainer", "agent://custodian"):
        with pytest.raises(GateReceiptError):
            issue_gate_receipt(prereg, manifest, members, signing_key=private, **{**common, "gate_principal_uri": principal})
