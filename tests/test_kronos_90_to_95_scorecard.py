"""Tests for the non-gameable Kronos 90->95 scorecard and its scorer.

Covers: scorecard structure (20 criteria x 5 fixed binary checks), attainable
integer totals and both gates' category floors, an exact-95 fixture, and the
four fail-closed rejections (missing evidence, non-binary value, floor
violation, active hard cap), plus byte-identical determinism across evaluators.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCORECARD_PATH = _REPO_ROOT / "docs" / "kronos_90_to_95_scorecard_v1.json"
_SCORER_PATH = _REPO_ROOT / "scripts" / "score_kronos_90_to_95.py"


def _load_scorer():
    spec = importlib.util.spec_from_file_location("score_kronos_90_to_95", _SCORER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


scorer = _load_scorer()
SCORECARD = json.loads(_SCORECARD_PATH.read_text(encoding="utf-8-sig"))


# --------------------------------------------------------------------------- #
# Evidence builders
# --------------------------------------------------------------------------- #
def _all_pass_checks() -> dict:
    checks = {}
    for cid in SCORECARD["criteria"]:
        for kind in SCORECARD["check_kinds"]:
            checks[f"{cid}.{kind}"] = {
                "passed": True,
                "evidence_ref": f".omo/evidence/{cid}/{kind}.json#sha256:deadbeef",
            }
    return checks


def _evidence(checks: dict, caps=None, verdict="NO-GO") -> dict:
    return {
        "checks": checks,
        "hard_caps_active": list(caps or []),
        "model_verdict": verdict,
    }


def _fail_one_check(checks: dict, criterion: str) -> None:
    """Flip the first check of ``criterion`` to a failing (unpassed) entry."""
    kind = SCORECARD["check_kinds"][0]
    checks[f"{criterion}.{kind}"] = {"passed": False, "evidence_ref": ""}


def _set_category(checks: dict, category: str, target: int) -> None:
    """Force a category (4 criteria x 5 checks = 20) to exactly ``target``."""
    assert 0 <= target <= 20
    ids = SCORECARD["categories"][category]["criteria"]
    keys = [f"{cid}.{kind}" for cid in ids for kind in SCORECARD["check_kinds"]]
    for i, key in enumerate(keys):
        passing = i < target
        checks[key] = {
            "passed": passing,
            "evidence_ref": f"ref#{key}" if passing else "",
        }


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #
def test_scorecard_has_20_criteria_each_with_5_fixed_checks():
    criteria = SCORECARD["criteria"]
    assert len(criteria) == 20
    kinds = SCORECARD["check_kinds"]
    assert kinds == ["contract", "happy_test", "failure_test", "runtime_evidence",
                     "independent_review_hash"]
    for cid, crit in criteria.items():
        assert list(crit["checks"].keys()) == kinds, cid
        # Every check has criterion-specific, non-empty wording.
        texts = list(crit["checks"].values())
        assert all(isinstance(t, str) and len(t) > 15 for t in texts), cid
        assert len(set(texts)) == 5, f"{cid} has duplicated check wording"


def test_categories_cover_all_criteria_and_carry_gate_floors():
    all_ids = []
    for cat_id, cat in SCORECARD["categories"].items():
        assert cat["max"] == 20
        assert cat["floor"]["gate_90"] >= 1 and cat["floor"]["gate_95"] >= 1
        all_ids.extend(cat["criteria"])
    assert sorted(all_ids) == sorted(SCORECARD["criteria"].keys())
    assert len(all_ids) == 20


def test_gate_floors_match_plan():
    f90 = {k: v["floor"]["gate_90"] for k, v in SCORECARD["categories"].items()}
    f95 = {k: v["floor"]["gate_95"] for k, v in SCORECARD["categories"].items()}
    assert f90 == {"A": 19, "B": 18, "C": 17, "D": 18, "E": 18}
    assert f95 == {"A": 19, "B": 19, "C": 19, "D": 19, "E": 19}
    assert SCORECARD["gates"]["gate_90"]["total_min"] == 90
    assert SCORECARD["gates"]["gate_95"]["total_min"] == 95


# --------------------------------------------------------------------------- #
# Attainable integer totals
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("k", [0, 1, 2, 3, 4, 5])
def test_criterion_scores_are_integers_0_to_5(k):
    checks = _all_pass_checks()
    # Fail (5 - k) checks of criterion A1 -> A1 scores exactly k.
    kinds = SCORECARD["check_kinds"]
    for kind in kinds[k:]:
        checks[f"A1.{kind}"] = {"passed": False, "evidence_ref": ""}
    result = scorer.score(SCORECARD, _evidence(checks))
    assert result["criterion_scores"]["A1"] == k
    assert 0 <= result["total"] <= 100
    assert all(0 <= v <= 20 for v in result["category_scores"].values())


def test_all_pass_scores_100_and_both_gates_pass():
    result = scorer.score(SCORECARD, _evidence(_all_pass_checks()))
    assert result["total"] == 100
    assert result["category_scores"] == {"A": 20, "B": 20, "C": 20, "D": 20, "E": 20}
    assert result["gates"]["gate_90"]["passed"] is True
    assert result["gates"]["gate_95"]["passed"] is True
    # Three separate outputs; model verdict is unscored passthrough.
    assert result["outputs"]["dashboard_release"]["score"] == 60
    assert result["outputs"]["research_pipeline"]["score"] == 40
    assert "model_verdict" not in result["outputs"]
    assert result["model_verdict"] == "NO-GO"


# --------------------------------------------------------------------------- #
# Exact-95 fixture (happy gate-95)
# --------------------------------------------------------------------------- #
def test_exact_95_fixture_passes_gate_95_with_every_floor_met():
    checks = _all_pass_checks()
    # 19 per category x 5 = 95, each category exactly at the gate-95 floor of 19.
    for cat in ("A", "B", "C", "D", "E"):
        _set_category(checks, cat, 19)
    result = scorer.score(SCORECARD, _evidence(checks))
    assert result["total"] == 95
    assert all(v == 19 for v in result["category_scores"].values())
    assert result["gates"]["gate_95"]["passed"] is True
    assert result["gates"]["gate_95"]["floor_failures"] == []
    assert result["gates"]["gate_90"]["passed"] is True


# --------------------------------------------------------------------------- #
# Rejection 1: missing evidence
# --------------------------------------------------------------------------- #
def test_passed_check_without_evidence_ref_is_rejected():
    checks = _all_pass_checks()
    checks["A1.contract"] = {"passed": True, "evidence_ref": ""}
    with pytest.raises(scorer.ScorecardError, match="missing evidence"):
        scorer.score(SCORECARD, _evidence(checks))


# --------------------------------------------------------------------------- #
# Rejection 2: non-binary value
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [0.5, 2, "partial", "true", None])
def test_non_binary_check_value_is_rejected(bad):
    checks = _all_pass_checks()
    checks["B2.happy_test"] = {"passed": bad, "evidence_ref": "ref"}
    with pytest.raises(scorer.ScorecardError):
        scorer.score(SCORECARD, _evidence(checks))


def test_unknown_check_id_is_rejected():
    checks = _all_pass_checks()
    checks["Z9.contract"] = {"passed": True, "evidence_ref": "ref"}
    with pytest.raises(scorer.ScorecardError, match="unknown check id"):
        scorer.score(SCORECARD, _evidence(checks))


# --------------------------------------------------------------------------- #
# Rejection 3: floor violation caps the gate
# --------------------------------------------------------------------------- #
def test_floor_violation_fails_gate_even_when_total_is_high():
    checks = _all_pass_checks()
    _set_category(checks, "A", 17)  # below gate-90 floor of 19
    result = scorer.score(SCORECARD, _evidence(checks))
    assert result["total"] == 97  # 17 + 20*4
    assert result["gates"]["gate_90"]["passed"] is False
    assert result["gates"]["gate_90"]["floor_failures"] == ["A"]
    assert result["gates"]["gate_95"]["passed"] is False


# --------------------------------------------------------------------------- #
# Rejection 4: active hard cap on a 100-point fixture
# --------------------------------------------------------------------------- #
def test_p0_defect_caps_perfect_score_below_90():
    checks = _all_pass_checks()
    result = scorer.score(
        SCORECARD, _evidence(checks, caps=["p0_evidence_fabrication"])
    )
    assert result["total"] == 100
    assert result["active_hard_caps"] == ["p0_evidence_fabrication"]
    assert result["gates"]["gate_90"]["passed"] is False
    assert result["gates"]["gate_90"]["blocking_caps"] == ["p0_evidence_fabrication"]
    assert result["gates"]["gate_95"]["passed"] is False


def test_cherry_pick_cap_blocks_95_but_not_90():
    checks = _all_pass_checks()
    result = scorer.score(
        SCORECARD, _evidence(checks, caps=["cherry_pick_or_trainval_as_oos"])
    )
    assert result["total"] == 100
    assert result["gates"]["gate_90"]["passed"] is True  # cap only blocks below 95
    assert result["gates"]["gate_90"]["blocking_caps"] == []
    assert result["gates"]["gate_95"]["passed"] is False
    assert result["gates"]["gate_95"]["blocking_caps"] == ["cherry_pick_or_trainval_as_oos"]


def test_unknown_hard_cap_is_rejected():
    checks = _all_pass_checks()
    with pytest.raises(scorer.ScorecardError, match="unknown hard cap"):
        scorer.score(SCORECARD, _evidence(checks, caps=["not_a_real_cap"]))


# --------------------------------------------------------------------------- #
# Determinism: two evaluators produce byte-identical JSON
# --------------------------------------------------------------------------- #
def test_two_evaluators_produce_byte_identical_json():
    checks = _all_pass_checks()
    for cat in ("A", "B", "C", "D", "E"):
        _set_category(checks, cat, 19)
    evidence = _evidence(checks)
    a = scorer.serialize(scorer.score(SCORECARD, evidence))
    b = scorer.serialize(scorer.score(SCORECARD, json.loads(json.dumps(evidence))))
    assert a == b
    # Re-serialization is stable (no set/time ordering leakage).
    assert scorer.serialize(json.loads(a)) == a
