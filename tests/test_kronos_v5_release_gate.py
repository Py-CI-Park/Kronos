from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("kronos_v5_release_gate", ROOT / "scripts" / "assemble_kronos_v5_release_gate.py")
assert SPEC and SPEC.loader
release_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_gate)

SCHEMA = json.loads((ROOT / "docs" / "schemas" / "kronos_v5_release_gate.v1.schema.json").read_text(encoding="utf-8"))
KEY = bytes(range(32))
SOURCE = "a" * 64
DIST = "b" * 64
HEAD = "c" * 64
TREE = "d" * 64
MAP = "e" * 64
ASSEMBLED_AT = "2026-07-15T00:00:00Z"
MISSING = object()


def _canonical(value: dict[str, Any]) -> bytes:
    return release_gate.canonical_bytes(value)


def _write_json(path: Path, value: dict[str, Any], *, lf: bool = False) -> Path:
    path.write_bytes(_canonical(value) + (b"\n" if lf else b""))
    return path


def _score(counts: dict[str, int] | None = None, *, caps: list[str] | None = None, locks: dict[str, bool] | None = None, source: str = SOURCE, candidate_map: str = MAP) -> dict[str, Any]:
    counts = counts or {"A": 23, "B": 23, "C": 18, "D": 13, "E": 13}
    claim_results: dict[str, bool] = {}
    for category, ids in release_gate.CATEGORY_CLAIMS.items():
        for index, claim_id in enumerate(ids):
            claim_results[claim_id] = index < counts[category]
    category_scores = {category: sum(claim_results[claim_id] for claim_id in ids) for category, ids in release_gate.CATEGORY_CLAIMS.items()}
    floor_failures = [category for category, floor in release_gate.CATEGORY_FLOORS.items() if category_scores[category] < floor]
    active_caps = list(caps or [])
    raw_total = sum(category_scores.values())
    effective_total = min(raw_total, 89) if active_caps else raw_total
    return {
        "schema": "kronos_point_score.v2",
        "candidate_map_sha256": candidate_map,
        "candidate_source_sha256": source,
        "scorecard_sha256": release_gate.PINNED_SCORECARD_SHA256,
        "category_scores": category_scores,
        "capability_option_ceilings": category_scores,
        "claim_results": {claim_id: claim_results[claim_id] for claim_id in sorted(claim_results)},
        "floor_failures": floor_failures,
        "active_hard_caps": active_caps,
        "raw_total": raw_total,
        "effective_total": effective_total,
        "gate": {"id": "engineering_90", "passed": effective_total >= 90 and not floor_failures and not active_caps, "total_min": 90},
        "six_locks_false": locks or dict(release_gate.SIX_LOCKS),
    }


def _state(**overrides: Any) -> dict[str, Any]:
    state = {
        "schema": release_gate.STATE_SCHEMA,
        "h_release": HEAD,
        "h_release_tree": TREE,
        "current_head": HEAD,
        "current_tree": TREE,
        "h_release_immutable": True,
        "worktree_clean": True,
        "current_source_sha256": SOURCE,
        "expected_dist_manifest_sha256": DIST,
        "current_dist_manifest_sha256": DIST,
    }
    state.update(overrides)
    return state


def _browser(**overrides: Any) -> dict[str, Any]:
    value = {
        "schema": "kronos_v5_live_browser_receipt.v1",
        "status": "PASS",
        "capture_kind": "live_browser_execution",
        "live_browser_execution": True,
        "synthetic_evidence": False,
        "source_sha256": SOURCE,
        "dist_manifest_sha256": DIST,
        "receipt_uid": "live-browser-receipt-1",
    }
    value.update(overrides)
    return value


def _platform(schema: str, **overrides: Any) -> dict[str, Any]:
    value = {"schema": schema, "status": "PASS", "source_sha256": SOURCE, "dist_manifest_sha256": DIST, "receipt_uid": schema}
    value.update(overrides)
    return value


def _model(**overrides: str) -> dict[str, str]:
    value: dict[str, str] = {"schema": release_gate.MODEL_STATE_SCHEMA, "model_verdict": "NOT_RUN", "d0": "NOT_RUN", "d1": "NOT_RUN", "oos": "NOT_RUN"}
    value.update(overrides)
    return value


def _assemble(
    tmp_path: Path,
    *,
    score_a: dict[str, Any] | None = None,
    score_b: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    browser: dict[str, Any] | object = MISSING,
    security: dict[str, Any] | object = MISSING,
    rollback: dict[str, Any] | object = MISSING,
    model: dict[str, str] | None = None,
) -> dict[str, Any]:
    score_a_path = _write_json(tmp_path / "score-a.json", score_a or _score(), lf=True)
    score_b_path = _write_json(tmp_path / "score-b.json", score_b or copy.deepcopy(score_a or _score()), lf=True)
    state_path = _write_json(tmp_path / "state.json", state or _state())
    browser_path = None if browser is None else _write_json(tmp_path / "browser.json", _browser() if browser is MISSING else browser)  # type: ignore[arg-type]
    security_path = None if security is None else _write_json(tmp_path / "security.json", _platform("kronos_v5_security_receipt.v1") if security is MISSING else security)  # type: ignore[arg-type]
    rollback_path = None if rollback is None else _write_json(tmp_path / "rollback.json", _platform("kronos_v5_rollback_receipt.v1") if rollback is MISSING else rollback)  # type: ignore[arg-type]
    model_path = _write_json(tmp_path / "model.json", model or _model())
    result = release_gate.assemble_release_gate(
        score_a_path=score_a_path,
        score_b_path=score_b_path,
        state_path=state_path,
        browser_receipt_path=browser_path,
        security_receipt_path=security_path,
        rollback_receipt_path=rollback_path,
        model_state_path=model_path,
        assembled_at=ASSEMBLED_AT,
        signing_key_seed=KEY,
    )
    release_gate.validate_release_gate(result)
    return result


def _validator() -> Draft202012Validator:
    Draft202012Validator.check_schema(SCHEMA)
    return Draft202012Validator(SCHEMA)


def test_happy_release_gate_is_schema_valid_signed_hashed_and_default_true(tmp_path: Path) -> None:
    result = _assemble(tmp_path)
    _validator().validate(result)
    unsigned = {key: result[key] for key in result if key not in {"release_gate_sha256", "signature"}}
    assert result["release_gate_sha256"] == hashlib.sha256(_canonical(unsigned)).hexdigest()
    assert result["signature"]["payload_sha256"] == result["release_gate_sha256"]
    assert result["default_equation"]["expression"] == release_gate.DEFAULT_EQUATION
    assert result["default_eligible"] is True
    assert result["release_eligible"] is True
    assert result["blockers"] == []
    assert all(result["default_equation"]["operands"].values())
    assert result["six_locks_false"] == release_gate.SIX_LOCKS
    assert result["platform_assurance"]["browser"]["capture_kind"] == "live_browser_execution"
    assert result["platform_assurance"]["browser"]["live_browser_execution"] is True
    assert result["platform_assurance"]["browser"]["synthetic_evidence"] is False


def test_release_gate_schema_rejects_open_or_inconsistent_payloads(tmp_path: Path) -> None:
    validator = _validator()
    result = _assemble(tmp_path)
    validator.validate(result)
    open_payload = copy.deepcopy(result)
    open_payload["unexpected"] = True
    assert list(validator.iter_errors(open_payload))
    inconsistent = copy.deepcopy(result)
    inconsistent["default_eligible"] = False
    assert list(validator.iter_errors(inconsistent))


OPERAND_CASES = [
    (
        "point_scores_byte_identical",
        {"score_b": _score(candidate_map="f" * 64)},
        {"SCORE_REPLAY_NOT_BYTE_IDENTICAL"},
    ),
    (
        "score_total_min_90",
        {"score_a": _score({"A": 23, "B": 23, "C": 18, "D": 13, "E": 12}), "score_b": _score({"A": 23, "B": 23, "C": 18, "D": 13, "E": 12})},
        {"SCORE_TOTAL_BELOW_90"},
    ),
    (
        "category_floors_passed",
        {"score_a": _score({"A": 24, "B": 23, "C": 18, "D": 13, "E": 12}), "score_b": _score({"A": 24, "B": 23, "C": 18, "D": 13, "E": 12})},
        {"CATEGORY_FLOOR_FAILURE"},
    ),
    (
        "hard_caps_absent",
        {"score_a": _score({"A": 25, "B": 25, "C": 20, "D": 15, "E": 15}, caps=["fresh_oos_misrepresentation"]), "score_b": _score({"A": 25, "B": 25, "C": 20, "D": 15, "E": 15}, caps=["fresh_oos_misrepresentation"])},
        {"ACTIVE_HARD_CAP"},
    ),
    (
        "six_locks_false",
        {"score_a": _score(locks={**release_gate.SIX_LOCKS, "promotion_allowed": True}), "score_b": _score(locks={**release_gate.SIX_LOCKS, "promotion_allowed": True})},
        {"SIX_LOCKS_NOT_FALSE"},
    ),
    ("source_hash_current", {"state": _state(current_source_sha256="1" * 64)}, {"SOURCE_HASH_MISMATCH"}),
    ("dist_hash_current", {"state": _state(current_dist_manifest_sha256="2" * 64)}, {"DIST_HASH_MISMATCH"}),
    ("head_matches_h_release", {"state": _state(current_head="3" * 64)}, {"HEAD_DRIFT"}),
    ("tree_matches_h_release", {"state": _state(current_tree="4" * 64)}, {"TREE_DRIFT"}),
    ("h_release_immutable", {"state": _state(h_release_immutable=False)}, {"H_RELEASE_NOT_IMMUTABLE"}),
    ("worktree_clean", {"state": _state(worktree_clean=False)}, {"DIRTY_WORKTREE"}),
    (
        "live_browser_pass",
        {"browser": _browser(capture_kind="synthetic_fixture_evidence", live_browser_execution=False, synthetic_evidence=True)},
        {"BROWSER_SYNTHETIC_SUBSTITUTION"},
    ),
    ("security_pass", {"security": _platform("kronos_v5_security_receipt.v1", status="FAIL")}, {"SECURITY_NOT_PASS"}),
    ("rollback_pass", {"rollback": _platform("kronos_v5_rollback_receipt.v1", status="FAIL")}, {"ROLLBACK_NOT_PASS"}),
]


@pytest.mark.parametrize(("operand", "kwargs", "expected_blockers"), OPERAND_CASES, ids=[case[0] for case in OPERAND_CASES])
def test_counterfactual_for_every_default_operand(tmp_path: Path, operand: str, kwargs: dict[str, Any], expected_blockers: set[str]) -> None:
    result = _assemble(tmp_path, **kwargs)
    assert result["default_eligible"] is False
    assert result["release_eligible"] is False
    assert result["default_equation"]["operands"][operand] is False
    assert expected_blockers.issubset(set(result["blockers"]))
    _validator().validate(result)


def test_synthetic_browser_substitution_is_distinct_from_live_receipt(tmp_path: Path) -> None:
    result = _assemble(tmp_path, browser=_browser(capture_kind="synthetic_fixture_evidence", live_browser_execution=False, synthetic_evidence=True))
    assert result["blockers"] == ["BROWSER_SYNTHETIC_SUBSTITUTION"]
    assert result["platform_assurance"]["browser"]["status"] == "PASS"
    assert result["platform_assurance"]["browser"]["synthetic_evidence"] is True
    assert result["default_eligible"] is False


def test_unknown_browser_capture_kind_is_rejected(tmp_path: Path) -> None:
    result = _assemble(tmp_path, browser=_browser(capture_kind="live_browser_evidence", live_browser_execution=True, synthetic_evidence=False))
    assert result["blockers"] == ["BROWSER_SYNTHETIC_SUBSTITUTION"]
    assert result["default_equation"]["operands"]["live_browser_pass"] is False
    assert result["default_eligible"] is False


@pytest.mark.parametrize(
    ("missing", "blocker"),
    [
        ("browser", "BROWSER_RECEIPT_MISSING"),
        ("security", "SECURITY_RECEIPT_MISSING"),
        ("rollback", "ROLLBACK_RECEIPT_MISSING"),
    ],
)
def test_absent_platform_assurance_has_exact_blocker(tmp_path: Path, missing: str, blocker: str) -> None:
    kwargs: dict[str, Any] = {missing: None}
    result = _assemble(tmp_path, **kwargs)
    assert result["blockers"] == [blocker]
    assert result["default_eligible"] is False


@pytest.mark.parametrize(
    ("field", "operand", "blocker"),
    [
        ("current_source_sha256", "source_hash_current", "SOURCE_HASH_MISMATCH"),
        ("expected_dist_manifest_sha256", "dist_hash_current", "DIST_HASH_MISMATCH"),
        ("current_dist_manifest_sha256", "dist_hash_current", "DIST_HASH_MISMATCH"),
        ("h_release", "head_matches_h_release", "HEAD_DRIFT"),
        ("current_head", "head_matches_h_release", "HEAD_DRIFT"),
        ("h_release_tree", "tree_matches_h_release", "TREE_DRIFT"),
        ("current_tree", "tree_matches_h_release", "TREE_DRIFT"),
        ("h_release_immutable", "h_release_immutable", "H_RELEASE_NOT_IMMUTABLE"),
        ("worktree_clean", "worktree_clean", "DIRTY_WORKTREE"),
    ],
)
def test_missing_release_gate_operand_evidence_has_explicit_blocker(tmp_path: Path, field: str, operand: str, blocker: str) -> None:
    state = _state()
    state.pop(field)
    result = _assemble(tmp_path, state=state)
    assert result["default_equation"]["operands"][operand] is False
    assert result["default_eligible"] is False
    assert blocker in result["blockers"]
    _validator().validate(result)


def test_score_replay_mismatch_blocks_even_when_each_score_is_valid(tmp_path: Path) -> None:
    result = _assemble(tmp_path, score_b=_score(candidate_map="f" * 64))
    assert result["score_replay"]["byte_identical"] is False
    assert result["blockers"] == ["SCORE_REPLAY_NOT_BYTE_IDENTICAL"]
    assert result["default_equation"]["operands"]["point_scores_byte_identical"] is False


def test_model_d0_d1_oos_fields_are_preserved_non_operands(tmp_path: Path) -> None:
    non_operands = _model(model_verdict="GO", d0="D0_BLOCKED", d1="D1_BLOCKED", oos="FRESH_OOS_NOT_RUN")
    result = _assemble(tmp_path, model=non_operands)
    assert result["non_operands"] == {"model_verdict": "GO", "d0": "D0_BLOCKED", "d1": "D1_BLOCKED", "oos": "FRESH_OOS_NOT_RUN"}
    assert result["default_equation"]["non_operand_fields"] == ["model_verdict", "d0", "d1", "oos"]
    assert result["default_eligible"] is True
    assert result["blockers"] == []


def test_dirty_worktree_has_exact_blocker(tmp_path: Path) -> None:
    result = _assemble(tmp_path, state=_state(worktree_clean=False))
    assert result["head_state"]["worktree_clean"] is False
    assert result["default_equation"]["operands"]["worktree_clean"] is False
    assert result["blockers"] == ["DIRTY_WORKTREE"]
    assert result["default_eligible"] is False
