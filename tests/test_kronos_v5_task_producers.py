from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import rfc8785

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/kronos_v5_task_fixture.json"
CAPTURE = ROOT / "scripts/capture_dashboard_v5_tasks.mjs"
SCORE = ROOT / "scripts/score_dashboard_v5_tasks.py"
REVIEW = ROOT / "scripts/review_dashboard_v5_task_scores.py"
INSTRUMENT = ROOT / "docs/kronos_dashboard_v5_usability_instrument_v1.json"
TASK_IDS = [f"T{i:02d}" for i in range(1, 11)]
DIMENSIONS = ("U", "L", "J")
FAILURE_CODES = ("TIMEOUT", "WRONG_RUN", "SOURCE_INSPECTION", "PRODUCER_HELP", "ACTION_LIMIT", "MISSING_TRACE", "INVALID_ASSIGNMENT", "RELOAD_NOT_REQUESTED", "OBJECTIVE_MISMATCH")
CAPTURE_KIND = "synthetic_fixture_evidence"
LIVE_BROWSER_EXECUTION = False
OPERATOR_KEYS = {"schema", "attempt_uid", "operator_index", "browser_pid", "profile_uid", "fixture_ref", "instrument_ref", "assignment_received_at", "attempt_started_at", "attempt_completed_at", "tasks", "objective_failures", "profile_destroyed_at"}
REF_KEYS = {"uri", "sha256", "byte_length", "schema"}
TASK_TRACE_KEYS = {"schema", "capture_kind", "live_browser_execution", "operator_index", "task_id", "started_at", "completed_at", "actions", "submitted_facts", "objective_valid", "failure_codes"}


def canonical(value: dict[str, Any]) -> bytes:
    return rfc8785.dumps(value)


def object_ref(raw: bytes, uri: str, schema: str) -> dict[str, Any]:
    return {"uri": uri, "sha256": hashlib.sha256(raw).hexdigest(), "byte_length": len(raw), "schema": schema}


def instrument_wrapper_ref(run_nonce: str) -> dict[str, Any]:
    raw = INSTRUMENT.read_bytes()
    wrapper = {"schema": "kronos_instrument.v2", "kind": "dashboard-v5-usability-instrument", "instrument_ref": object_ref(raw, f"kronos-run://{run_nonce}/instrument/usability-v1.json", "kronos_dashboard_v5_usability_instrument.v1"), "objective_failure_codes": list(FAILURE_CODES), "task_ids": TASK_IDS}
    return object_ref(canonical(wrapper), f"kronos-run://{run_nonce}/instrument", "kronos_instrument.v2")


def rebind_fixture(value: dict[str, Any]) -> dict[str, Any]:
    rebound = json.loads(json.dumps(value))
    run_nonce = rebound["run_nonce"]
    rebound["instrument_ref"] = instrument_wrapper_ref(run_nonce)
    content = {key: child for key, child in rebound.items() if key != "fixture_ref"}
    content_ref = object_ref(canonical(content), f"kronos-run://{run_nonce}/fixture/task-fixture.json", "kronos_task_fixture.v2")
    descriptor = {"schema": "kronos_fixture.v2", "capture_kind": CAPTURE_KIND, "live_browser_execution": LIVE_BROWSER_EXECUTION, "kind": "synthetic-dashboard-v5-task-fixture", "run_nonce": run_nonce, "instrument_ref": rebound["instrument_ref"], "task_fixture_ref": content_ref, "operator_indices": ["A", "B"], "task_ids": TASK_IDS}
    rebound["fixture_ref"] = object_ref(canonical(descriptor), f"kronos-run://{run_nonce}/fixture", "kronos_fixture.v2")
    return rebound


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def capture(tmp_path: Path, operator: str, fixture: Path = FIXTURE) -> tuple[Path, Path]:
    output = tmp_path / f"trace-{operator}.json"
    evidence = tmp_path / f"evidence-{operator}"
    result = run("node", str(CAPTURE), "--fixture", str(fixture), "--operator", operator, "--evidence-dir", str(evidence), "--out", str(output))
    assert result.returncode == 0, result.stderr
    return output, evidence


def score_trace(tmp_path: Path, trace: Path, evidence: Path, operator: str) -> Path:
    output = tmp_path / f"score-{operator}.json"
    result = run(sys.executable, str(SCORE), "--trace", str(trace), "--evidence-dir", str(evidence), "--out", str(output))
    assert result.returncode == 0, result.stderr
    return output


def review_scores(tmp_path: Path, trace_a: Path, evidence_a: Path, trace_b: Path, evidence_b: Path, score_a: Path, score_b: Path) -> Path:
    output = tmp_path / "task-review.json"
    result = run(sys.executable, str(REVIEW), "--trace-a", str(trace_a), "--evidence-dir-a", str(evidence_a), "--trace-b", str(trace_b), "--evidence-dir-b", str(evidence_b), "--machine-score-a", str(score_a), "--machine-score-b", str(score_b), "--out", str(output))
    assert result.returncode == 0, result.stderr
    return output


def assert_canonical_path(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    assert raw == canonical(value)
    assert not raw.endswith(b"\n")
    return value


def write_fixture(tmp_path: Path, value: dict[str, Any], *, rebind: bool = True) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "fixture.json"
    path.write_bytes(canonical(rebind_fixture(value) if rebind else value))
    return path


def refs_in(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        if set(value) == REF_KEYS:
            return [value]
        return [ref for child in value.values() for ref in refs_in(child)]
    if isinstance(value, list):
        return [ref for child in value for ref in refs_in(child)]
    return []


def assert_json_ref(ref: dict[str, Any], raw: bytes, schema: str) -> dict[str, Any]:
    assert set(ref) == REF_KEYS
    assert ref["schema"] == schema
    assert ref["sha256"] == hashlib.sha256(raw).hexdigest()
    assert ref["byte_length"] == len(raw)
    value = json.loads(raw.decode("utf-8"))
    assert value["schema"] == schema
    assert raw == canonical(value)
    return value


def resolve_json(evidence: Path, ref: dict[str, Any], schema: str) -> dict[str, Any]:
    return assert_json_ref(ref, (evidence / ref["sha256"]).read_bytes(), schema)


def assert_binary_ref(evidence: Path, ref: dict[str, Any], schema: str) -> bytes:
    raw = (evidence / ref["sha256"]).read_bytes()
    assert set(ref) == REF_KEYS
    assert ref["schema"] == schema
    assert ref["sha256"] == hashlib.sha256(raw).hexdigest()
    assert ref["byte_length"] == len(raw)
    return raw


def compute_bits(trace: dict[str, Any], fixture: dict[str, Any]) -> dict[str, list[bool]]:
    expected = {task["task_id"]: task["submissions"] for task in fixture["tasks"]}
    return {dimension: [bool(task["objective_valid"] and len(task["submitted_facts"]) == 3 and task["submitted_facts"][DIMENSIONS.index(dimension)] == expected[task["task_id"]][dimension]) for task in trace["tasks"]] for dimension in DIMENSIONS}


def test_two_paths_are_deterministic_closed_and_refs_resolve_to_canonical_wrappers(tmp_path: Path) -> None:
    (a, evidence_a), (b, evidence_b) = capture(tmp_path, "A"), capture(tmp_path, "B")
    a2, _ = capture(tmp_path / "repeat", "A")
    assert a.read_bytes() == a2.read_bytes()
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["capture_kind"] == CAPTURE_KIND
    assert fixture["live_browser_execution"] is LIVE_BROWSER_EXECUTION
    for trace_path, evidence, operator in ((a, evidence_a, "A"), (b, evidence_b, "B")):
        raw = trace_path.read_bytes()
        trace = json.loads(raw.decode("utf-8"))
        assert raw == canonical(trace)
        assert set(trace) == OPERATOR_KEYS
        assert trace["operator_index"] == operator
        assert [task["task_id"] for task in trace["tasks"]] == TASK_IDS
        assert all(len(task["submitted_facts"]) == 3 and set(fact) == {"code", "detail"} for task in trace["tasks"] for fact in task["submitted_facts"])
        assert all(ref["sha256"] != "1" * 64 for ref in refs_in(trace))
        assert trace["fixture_ref"] == fixture["fixture_ref"]
        assert trace["instrument_ref"] == fixture["instrument_ref"]
        instrument = resolve_json(evidence, trace["instrument_ref"], "kronos_instrument.v2")
        assert instrument["instrument_ref"] == object_ref(INSTRUMENT.read_bytes(), f"kronos-run://{fixture['run_nonce']}/instrument/usability-v1.json", "kronos_dashboard_v5_usability_instrument.v1")
        assert (evidence / instrument["instrument_ref"]["sha256"]).read_bytes() == INSTRUMENT.read_bytes()
        descriptor = resolve_json(evidence, trace["fixture_ref"], "kronos_fixture.v2")
        assert descriptor["instrument_ref"] == trace["instrument_ref"]
        assert descriptor["capture_kind"] == CAPTURE_KIND
        assert descriptor["live_browser_execution"] is LIVE_BROWSER_EXECUTION
        content = resolve_json(evidence, descriptor["task_fixture_ref"], "kronos_task_fixture.v2")
        assert "fixture_ref" not in content
        assert content["instrument_ref"] == trace["instrument_ref"]
        assert content["capture_kind"] == CAPTURE_KIND
        assert content["live_browser_execution"] is LIVE_BROWSER_EXECUTION
        assert content["tasks"] == fixture["tasks"]
        for task in trace["tasks"]:
            task_trace = resolve_json(evidence, task["trace_ref"], "kronos_task_trace.v2")
            assert set(task_trace) == TASK_TRACE_KEYS
            assert task_trace["capture_kind"] == CAPTURE_KIND
            assert task_trace["live_browser_execution"] is LIVE_BROWSER_EXECUTION
            assert task_trace["task_id"] == task["task_id"]
            assert task_trace["submitted_facts"] == task["submitted_facts"]
            assert len(task["screenshot_refs"]) == 1
            screenshot = resolve_json(evidence, task["screenshot_refs"][0], "kronos_screenshot.v2")
            assert screenshot["scenario"]["operator_index"] == operator
            assert screenshot["scenario"]["task_id"] == task["task_id"]
            assert screenshot["dimensions"] == {"width": 2, "height": 1}
            assert assert_binary_ref(evidence, screenshot["png_ref"], "image/png").startswith(b"\x89PNG\r\n\x1a\n")
    approved = fixture["tasks"][0]["submissions"]
    assert json.loads(a.read_text(encoding="utf-8"))["tasks"][0]["submitted_facts"] == [approved[d] for d in DIMENSIONS]


def test_objective_failures_are_canonical_and_force_false_bits(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture["tasks"][0]["failure_codes"] = ["TIMEOUT", "WRONG_RUN"]
    fixture["tasks"][1]["actions"] = ["source_inspection", "producer_help", "reload", "x", "y"]
    fixture["tasks"][1]["reload_requested"] = False
    fixture["tasks"][2]["submitted_facts"] = [{"code": "run_id", "detail": "wrong"}]
    trace_path, _ = capture(tmp_path, "A", write_fixture(tmp_path, fixture))
    value = json.loads(trace_path.read_text(encoding="utf-8"))
    assert [(item["task_id"], item["failure_code"]) for item in value["objective_failures"]] == [(task["task_id"], code) for task in value["tasks"] for code in task["failure_codes"]]
    assert {x["failure_code"] for x in value["objective_failures"]} >= {"TIMEOUT", "WRONG_RUN", "SOURCE_INSPECTION", "PRODUCER_HELP", "ACTION_LIMIT", "RELOAD_NOT_REQUESTED", "OBJECTIVE_MISMATCH"}
    bitmaps = compute_bits(value, rebind_fixture(fixture))
    assert all(not bitmaps[dimension][0] for dimension in DIMENSIONS)
    assert all(not bitmaps[dimension][2] for dimension in DIMENSIONS)


def test_score_bits_are_exact_fact_matches_not_actions_or_screenshots(tmp_path: Path) -> None:
    trace_path, _ = capture(tmp_path, "A")
    broken = json.loads(trace_path.read_text(encoding="utf-8"))
    broken["tasks"][0]["action_count"] = 0
    broken["tasks"][0]["screenshot_refs"].append(broken["tasks"][0]["screenshot_refs"][0])
    broken["tasks"][0]["submitted_facts"][0]["detail"] = "mutated"
    bitmaps = compute_bits(broken, json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert bitmaps["U"][0] is False
    assert bitmaps["L"][0] is True
    assert bitmaps["J"][0] is True


def test_actual_score_review_pipeline_binds_wrapper_and_writes_canonical_bytes(tmp_path: Path) -> None:
    (a, evidence_a), (b, evidence_b) = capture(tmp_path, "A"), capture(tmp_path, "B")
    score_a, score_b = score_trace(tmp_path, a, evidence_a, "A"), score_trace(tmp_path, b, evidence_b, "B")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    trace_a, trace_b = json.loads(a.read_bytes()), json.loads(b.read_bytes())
    assert assert_canonical_path(score_a) == {"schema": "kronos_machine_task_score.v2", "operator_index": "A", "bitmaps": compute_bits(trace_a, fixture)}
    assert assert_canonical_path(score_b) == {"schema": "kronos_machine_task_score.v2", "operator_index": "B", "bitmaps": compute_bits(trace_b, fixture)}
    review_path = review_scores(tmp_path, a, evidence_a, b, evidence_b, score_a, score_b)
    review = assert_canonical_path(review_path)
    assert review["verdict"] == "PASS"
    assert review["blocking_codes"] == []
    assert review["operator_trace_refs"] == [object_ref(a.read_bytes(), f"agent://task-review-{a.name}", "kronos_operator_trace.v2"), object_ref(b.read_bytes(), f"agent://task-review-{b.name}", "kronos_operator_trace.v2")]
    assert review["machine_score_refs"] == [object_ref(score_a.read_bytes(), f"agent://task-review-{score_a.name}", "kronos_machine_task_score.v2"), object_ref(score_b.read_bytes(), f"agent://task-review-{score_b.name}", "kronos_machine_task_score.v2")]
    review_blob = json.dumps(review, sort_keys=True).lower()
    assert "browser" not in review_blob
    assert "live_browser_execution" not in review_blob


def test_score_review_reject_noncanonical_inputs_and_stale_raw_instrument_ref(tmp_path: Path) -> None:
    (a, evidence_a), (b, evidence_b) = capture(tmp_path, "A"), capture(tmp_path, "B")
    score_a, score_b = score_trace(tmp_path, a, evidence_a, "A"), score_trace(tmp_path, b, evidence_b, "B")

    newline_trace = tmp_path / "trace-A-newline.json"
    newline_trace.write_bytes(a.read_bytes() + b"\n")
    result = run(sys.executable, str(SCORE), "--trace", str(newline_trace), "--evidence-dir", str(evidence_a), "--out", str(tmp_path / "bad-score-newline.json"))
    assert result.returncode == 2
    utf16_trace = tmp_path / "trace-A-utf16.json"
    utf16_trace.write_bytes(a.read_bytes().decode("utf-8").encode("utf-16"))
    result = run(sys.executable, str(SCORE), "--trace", str(utf16_trace), "--evidence-dir", str(evidence_a), "--out", str(tmp_path / "bad-score-utf16.json"))
    assert result.returncode == 2

    trace = json.loads(a.read_bytes())
    stale = json.loads(json.dumps(trace))
    stale["instrument_ref"] = object_ref(INSTRUMENT.read_bytes(), trace["instrument_ref"]["uri"], "kronos_instrument.v2")
    stale_trace = tmp_path / "trace-A-stale-raw-instrument.json"
    stale_trace.write_bytes(canonical(stale))
    result = run(sys.executable, str(SCORE), "--trace", str(stale_trace), "--evidence-dir", str(evidence_a), "--out", str(tmp_path / "bad-score-stale.json"))
    assert result.returncode == 2
    result = run(sys.executable, str(REVIEW), "--trace-a", str(stale_trace), "--evidence-dir-a", str(evidence_a), "--trace-b", str(b), "--evidence-dir-b", str(evidence_b), "--machine-score-a", str(score_a), "--machine-score-b", str(score_b), "--out", str(tmp_path / "bad-review-stale.json"))
    assert result.returncode == 2

    wrapper = resolve_json(evidence_a, trace["instrument_ref"], "kronos_instrument.v2")
    alternate_wrapper_raw = json.dumps(wrapper, ensure_ascii=False, indent=2).encode("utf-8")
    (evidence_a / hashlib.sha256(alternate_wrapper_raw).hexdigest()).write_bytes(alternate_wrapper_raw)
    alternate = json.loads(json.dumps(trace))
    alternate["instrument_ref"] = object_ref(alternate_wrapper_raw, trace["instrument_ref"]["uri"], "kronos_instrument.v2")
    alternate_trace = tmp_path / "trace-A-alternate-wrapper.json"
    alternate_trace.write_bytes(canonical(alternate))
    result = run(sys.executable, str(SCORE), "--trace", str(alternate_trace), "--evidence-dir", str(evidence_a), "--out", str(tmp_path / "bad-score-wrapper.json"))
    assert result.returncode == 2

    newline_score = tmp_path / "score-A-newline.json"
    newline_score.write_bytes(score_a.read_bytes() + b"\n")
    result = run(sys.executable, str(REVIEW), "--trace-a", str(a), "--evidence-dir-a", str(evidence_a), "--trace-b", str(b), "--evidence-dir-b", str(evidence_b), "--machine-score-a", str(newline_score), "--machine-score-b", str(score_b), "--out", str(tmp_path / "bad-review-newline.json"))
    assert result.returncode == 2

def test_capture_rejects_synthetic_trace_label_omission_true_and_alias(tmp_path: Path) -> None:
    cases = (
        lambda fixture: fixture.pop("capture_kind"),
        lambda fixture: fixture.__setitem__("capture_kind", "browser_execution"),
        lambda fixture: fixture.pop("live_browser_execution"),
        lambda fixture: fixture.__setitem__("live_browser_execution", True),
    )
    for mutate in cases:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        mutate(fixture)
        path = write_fixture(tmp_path, fixture, rebind=False)
        result = run("node", str(CAPTURE), "--fixture", str(path), "--operator", "A", "--evidence-dir", str(tmp_path / "evidence"), "--out", str(tmp_path / "trace.json"))
        assert result.returncode == 2
        assert "synthetic fixture evidence" in result.stderr


def test_capture_rejects_failure_aliases_wrapper_tamper_and_max_action_drift(tmp_path: Path) -> None:
    cases = (
        (lambda fixture: fixture["tasks"][0].__setitem__("failure_codes", ["WRONG_RUN_SUBMISSION"]), True),
        (lambda fixture: fixture["tasks"][0].__setitem__("max_actions", fixture["tasks"][0]["max_actions"] + 1), True),
        (lambda fixture: fixture["instrument_ref"].__setitem__("sha256", "0" * 64), False),
        (lambda fixture: fixture["instrument_ref"].__setitem__("schema", "kronos_task_trace.v2"), False),
        (lambda fixture: fixture["instrument_ref"].__setitem__("byte_length", fixture["instrument_ref"]["byte_length"] + 1), False),
        (lambda fixture: fixture["fixture_ref"].__setitem__("sha256", "0" * 64), False),
        (lambda fixture: fixture["fixture_ref"].__setitem__("schema", "kronos_task_trace.v2"), False),
        (lambda fixture: fixture["fixture_ref"].__setitem__("byte_length", fixture["fixture_ref"]["byte_length"] + 1), False),
    )
    for mutate, rebind in cases:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        mutate(fixture)
        path = write_fixture(tmp_path, fixture, rebind=rebind)
        result = run("node", str(CAPTURE), "--fixture", str(path), "--operator", "A", "--evidence-dir", str(tmp_path / "evidence"), "--out", str(tmp_path / "trace.json"))
        assert result.returncode == 2
