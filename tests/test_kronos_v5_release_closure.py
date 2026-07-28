from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_closure", ROOT / "scripts" / "run_kronos_v5_release_closure.py")
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)

SCHEMA = ROOT / "docs" / "schemas" / "kronos_v5_release_closure.v1.schema.json"
CONTRACT = ROOT / "docs" / "kronos_dashboard_v5_release_closure_v1.json"
NOW = "2026-07-15T00:00:00Z"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _inspection(label: str = "base", **overrides: object) -> dict:
    value = {
        "head_sha256": release.sha256_text(f"head:{label}"),
        "tree_sha256": release.sha256_text(f"tree:{label}"),
        "dist_manifest_sha256": release.sha256_text(f"dist:{label}"),
        "config_sha256": release.release_config_sha256(),
        "worktree_clean": True,
        "command_log": [],
    }
    value.update(overrides)
    return release.normalize_inspection(value)


def _schema_validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def test_release_closure_contract_schema_and_constants_are_bound() -> None:
    validator = _schema_validator()
    contract = _load(CONTRACT)
    validator.validate(contract)
    assert contract["phase_machine"] == list(release.PHASES)
    assert contract["blocking_codes"] == list(release.BLOCKER_CODES)
    assert contract["six_locks_false"] == release.SIX_LOCKS_FALSE
    assert contract["default_equation"] == release.V5_DEFAULT_EQUATION
    assert contract["browser_inputs"]["synthetic_can_grant_browser_gate"] is False
    assert contract["worktree_policy"]["commit_push_tag_allowed"] is False


def test_pass_fail_and_hard_cap_equations_are_exact() -> None:
    passing = release.evaluate_v5_default_gate(release.fixture_release_inputs(live_browser=True))
    assert passing["default_eligible"] is True
    assert passing["default_decision"] == "SWITCH_TO_V5"
    assert passing["blocking_codes"] == []
    assert all(passing["six_locks_false"].values()) is False
    assert passing["six_locks_false"] == release.SIX_LOCKS_FALSE

    failing_inputs = release.fixture_release_inputs(live_browser=True, score_pass=False)
    failing = release.evaluate_v5_default_gate(failing_inputs)
    assert failing["default_eligible"] is False
    assert failing["default_decision"] == "RETAIN_V3"
    assert failing["blocking_codes"] == ["POINT_SCORE_FAIL"]

    capped = release.fixture_release_inputs(live_browser=True)
    capped["point_score_a"] = release.make_point_score(active_hard_caps=["fresh_oos_misrepresentation"])
    capped["point_score_b"] = json.loads(json.dumps(capped["point_score_a"]))
    capped_gate = release.evaluate_v5_default_gate(capped)
    assert capped["point_score_a"]["raw_total"] == 90
    assert capped["point_score_a"]["effective_total"] == 89
    assert capped_gate["blocking_codes"] == ["POINT_SCORE_FAIL"]


def test_live_browser_capture_kind_must_be_canonical() -> None:
    inputs = release.fixture_release_inputs(live_browser=True)
    assert inputs["browser"]["capture_kind"] == "live_browser_execution"
    gate = release.evaluate_v5_default_gate(inputs)
    assert gate["browser_gate"]["browser_live"] is True
    assert gate["browser_gate"]["passed"] is True

    legacy = release.fixture_release_inputs(live_browser=True)
    legacy["browser"]["capture_kind"] = "live_browser_evidence"
    legacy_gate = release.evaluate_v5_default_gate(legacy)
    assert legacy_gate["browser_gate"]["browser_live"] is False
    assert legacy_gate["default_decision"] == "RETAIN_V3"
    assert legacy_gate["blocking_codes"] == ["BROWSER_EVIDENCE_NOT_LIVE"]


def test_missing_positive_operands_fail_closed() -> None:
    cases = [
        (["assurance_decision"], "assurance_eligible", "ASSURANCE_BLOCK"),
        (["prior_chains_resolved"], "prior_chains_resolved", "PRIOR_CHAIN_RERESOLUTION_FAIL"),
        (["head_matches", "source.head_matches"], "head_match", "HEAD_DRIFT"),
        (["tree_matches", "source.tree_matches"], "tree_match", "TREE_DRIFT"),
        (["dist_matches", "dist.dist_matches"], "dist_match", "DIST_DRIFT"),
        (["config_matches"], "config_match", "CONFIG_DRIFT"),
        (["worktree_clean"], "worktree_clean", "DIRTY_WORKTREE"),
        (["source.identity_matches_head"], "source_identity_bound", "SOURCE_IDENTITY_MISMATCH"),
        (["rollback.v3_available"], "rollback_v3_available", "ROLLBACK_UNAVAILABLE"),
        (["rollback.query_contract_passed"], "rollback_query_pass", "ROLLBACK_QUERY_FAIL"),
        (["security.mutation_probes_rejected"], "security_clear", "SECURITY_GATE_FAIL"),
        (["security.download_policy_passed"], "security_clear", "SECURITY_GATE_FAIL"),
        (["security.publication_actions_attempted"], "security_clear", "SECURITY_GATE_FAIL"),
    ]

    for paths, term, blocker in cases:
        inputs = release.fixture_release_inputs(live_browser=True)
        for path in paths:
            target = inputs
            parts = path.split(".")
            for part in parts[:-1]:
                target = target[part]
            target.pop(parts[-1])
        gate = release.evaluate_v5_default_gate(inputs)
        assert gate["equation_terms"][term] is False
        assert blocker in gate["blocking_codes"]
        assert gate["default_decision"] == "RETAIN_V3"


def test_live_browser_evidence_only_satisfies_only_browser_operand() -> None:
    inputs = release.fixture_release_inputs(live_browser=True)
    for path in (
        "assurance_decision",
        "prior_chains_resolved",
        "head_matches",
        "source.head_matches",
        "tree_matches",
        "source.tree_matches",
        "dist_matches",
        "dist.dist_matches",
        "config_matches",
        "worktree_clean",
        "source.identity_matches_head",
        "rollback.v3_available",
        "rollback.query_contract_passed",
        "security.mutation_probes_rejected",
        "security.download_policy_passed",
        "security.publication_actions_attempted",
    ):
        target = inputs
        parts = path.split(".")
        for part in parts[:-1]:
            target = target[part]
        target.pop(parts[-1])

    gate = release.evaluate_v5_default_gate(inputs)
    assert gate["browser_gate"]["passed"] is True
    assert gate["equation_terms"]["live_browser_distinct"] is True
    assert gate["default_decision"] == "RETAIN_V3"
    assert "BROWSER_EVIDENCE_NOT_LIVE" not in gate["blocking_codes"]
    assert "BROWSER_EVIDENCE_SYNTHETIC" not in gate["blocking_codes"]
    assert "ASSURANCE_BLOCK" in gate["blocking_codes"]
    assert "SECURITY_GATE_FAIL" in gate["blocking_codes"]


def test_dry_run_fixture_labels_synthetic_non_browser_and_cannot_grant_browser_gate(tmp_path: Path) -> None:
    inputs = release.fixture_release_inputs(live_browser=False, dry_run_fixture_mode=True)
    gate = release.evaluate_v5_default_gate(inputs)
    assert gate["browser_gate"]["passed"] is False
    assert gate["browser_gate"]["browser_live"] is False
    assert gate["browser_gate"]["browser_synthetic"] is True
    assert gate["default_eligible"] is False
    assert gate["blocking_codes"] == [
        "BROWSER_EVIDENCE_NOT_LIVE",
        "BROWSER_EVIDENCE_SYNTHETIC",
        "DRY_RUN_FIXTURE_NOT_RELEASABLE",
    ]
    reused = release.fixture_release_inputs(live_browser=True)
    reused["browser"]["distinct_from_synthetic"] = False
    reused_gate = release.evaluate_v5_default_gate(reused)
    assert reused_gate["default_eligible"] is False
    assert reused_gate["blocking_codes"] == ["BROWSER_EVIDENCE_REUSED"]

    result = release.run_release_closure(inputs, temp_root=tmp_path, inspection=_inspection(), now=NOW)
    assert result["terminal"]["terminal_status"] == "TERMINAL_BLOCKED"
    run_root = Path(result["pointer"]["run_root"])
    generic_capture = json.loads((run_root / "artifacts" / "03-GENERIC_CAPTURE.json").read_text(encoding="utf-8"))
    assert generic_capture["capture_kind"] == "synthetic_fixture_evidence"
    assert generic_capture["live_browser_execution"] is False
    assert generic_capture["heavy_compute_run"] is False
    assert generic_capture["fresh_oos_accessed"] is False


def test_pointer_lifecycle_history_and_terminal_reuse_are_immutable(tmp_path: Path) -> None:
    inputs = release.fixture_release_inputs(live_browser=True)
    inspection = _inspection()
    result = release.run_release_closure(inputs, temp_root=tmp_path, inspection=inspection, now=NOW)
    validator = _schema_validator()
    validator.validate(result)
    assert result["terminal"]["terminal_status"] == "TERMINAL_CLOSED"
    assert result["state"]["immutable"] is True
    assert result["pointer"]["status"] == "TERMINAL_CLOSED"
    assert (tmp_path / "active-pointer.json").exists()
    assert len(list((tmp_path / "history").iterdir())) >= len(release.PHASES) + 1

    state_path = Path(result["pointer"]["run_root"]) / "state.json"
    before = state_path.read_bytes()
    reused = release.resume_closure_run(temp_root=tmp_path, inputs=inputs, current_inspection=inspection, now="2026-07-15T00:01:00Z")
    assert reused["reused_terminal"] is True
    assert reused["terminal"]["default_eligible"] is True
    assert state_path.read_bytes() == before


def test_active_head_dist_config_drift_invalidates_before_terminal(tmp_path: Path) -> None:
    inputs = release.fixture_release_inputs(live_browser=True)
    bound = _inspection("bound")
    start = release.start_closure_run(temp_root=tmp_path, inputs=inputs, inspection=bound, now=NOW)
    assert start["state"]["status"] == "ACTIVE"

    drifted = _inspection("bound", dist_manifest_sha256=release.sha256_text("new-dist"))
    result = release.resume_closure_run(temp_root=tmp_path, inputs=inputs, current_inspection=drifted, now="2026-07-15T00:02:00Z")
    assert result["state"]["status"] == "INVALIDATED"
    assert result["state"]["immutable"] is True
    assert result["blocking_codes"] == ["DIST_DRIFT"]
    invalidation_ref = result["state"]["invalidation_ref"]
    assert invalidation_ref["schema"] == "kronos_release_closure_invalidation.v1"


def test_score_and_model_verdict_are_independent_and_dirty_head_blocks() -> None:
    go_inputs = release.fixture_release_inputs(live_browser=True, model_verdict="GO")
    no_go_inputs = release.fixture_release_inputs(live_browser=True, model_verdict="NO-GO")
    go_gate = release.evaluate_v5_default_gate(go_inputs)
    no_go_gate = release.evaluate_v5_default_gate(no_go_inputs)
    assert go_gate["default_eligible"] == no_go_gate["default_eligible"] is True
    assert go_gate["blocking_codes"] == no_go_gate["blocking_codes"] == []
    assert go_gate["point_score"]["model_verdict_point_bearing"] is False
    assert no_go_gate["point_score"]["model_verdict_point_bearing"] is False

    dirty = release.evaluate_v5_default_gate(release.fixture_release_inputs(live_browser=True, dirty_worktree=True))
    assert dirty["default_eligible"] is False
    assert dirty["blocking_codes"] == ["DIRTY_WORKTREE"]


def test_no_publication_action_inspection_only_and_immutable_failed_roots(tmp_path: Path) -> None:
    for command in (["git", "commit", "-m", "no"], ["git", "push"], ["node", "build.js"], ["git", "tag", "v5"]):
        with pytest.raises(release.ReleaseClosureError):
            release._ensure_inspection_command(command)

    published = release.fixture_release_inputs(live_browser=True)
    published["security"]["forbidden_publication_actions"] = ["push"]
    published_gate = release.evaluate_v5_default_gate(published)
    assert published_gate["default_eligible"] is False
    assert published_gate["blocking_codes"] == ["SECURITY_GATE_FAIL", "PUBLICATION_ACTION_FORBIDDEN"]

    inputs = release.fixture_release_inputs(live_browser=True, dirty_worktree=True)
    result = release.run_release_closure(inputs, temp_root=tmp_path, inspection=_inspection(worktree_clean=False), now=NOW)
    assert result["terminal"]["terminal_status"] == "TERMINAL_BLOCKED"
    assert result["terminal"]["publication_actions_attempted"] is False
    assert result["terminal"]["mutated_tracked_files"] is False
    assert result["terminal"]["blocking_codes"] == ["DIRTY_WORKTREE"]

    store = release.ReleaseClosureStore(tmp_path)
    run_nonce = result["state"]["run_nonce"]
    state_path = store.state_path(run_nonce)
    before = state_path.read_bytes()
    with pytest.raises(release.ReleaseClosureError):
        store.write_artifact(run_nonce, "late-mutation.json", {"schema": "late", "value": True})
    reused = release.resume_closure_run(temp_root=tmp_path, inputs=inputs, current_inspection=_inspection(worktree_clean=False), now="2026-07-15T00:03:00Z")
    assert reused["reused_terminal"] is True
    assert state_path.read_bytes() == before
