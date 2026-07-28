#!/usr/bin/env python3
"""Fail-closed deterministic machine scorer for synthetic V5 task traces."""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import rfc8785

TASK_IDS = [f"T{i:02d}" for i in range(1, 11)]
DIMENSIONS = ("U", "L", "J")
FAILURE_CODES = ("TIMEOUT", "WRONG_RUN", "SOURCE_INSPECTION", "PRODUCER_HELP", "ACTION_LIMIT", "MISSING_TRACE", "INVALID_ASSIGNMENT", "RELOAD_NOT_REQUESTED", "OBJECTIVE_MISMATCH")
OPERATOR_KEYS = {"schema", "attempt_uid", "operator_index", "browser_pid", "profile_uid", "fixture_ref", "instrument_ref", "assignment_received_at", "attempt_started_at", "attempt_completed_at", "tasks", "objective_failures", "profile_destroyed_at"}
TASK_KEYS = {"task_id", "started_at", "completed_at", "elapsed_ms", "action_count", "objective_valid", "submitted_facts", "trace_ref", "screenshot_refs", "failure_codes"}
REF_KEYS = {"uri", "sha256", "byte_length", "schema"}
INSTRUMENT_SCHEMA = "kronos_dashboard_v5_usability_instrument.v1"
INSTRUMENT_PATH = Path(__file__).resolve().parents[1] / "docs" / "kronos_dashboard_v5_usability_instrument_v1.json"
RUN_INSTRUMENT_RE = re.compile(r"^kronos-run://([A-Za-z0-9_-]{43})/instrument$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

def canonical(value: Any) -> bytes:
    try:
        return rfc8785.dumps(value)
    except Exception as exc:
        raise ValueError("value is not RFC8785/JCS canonicalizable") from exc
def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result: raise ValueError(f"duplicate JSON member {key}")
        result[key] = value
    return result
def reject_constant(value: str) -> None:
    raise ValueError(value)
def parse_json(raw: bytes, label: str, *, require_canonical: bool) -> dict[str, Any]:
    if raw.startswith(b"\xef\xbb\xbf"): raise ValueError(f"{label} BOM is forbidden")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject_constant)
    if not isinstance(value, dict): raise ValueError(f"{label} JSON object required")
    if require_canonical and canonical(value) != raw: raise ValueError(f"{label} is not exact RFC8785/JCS bytes")
    return value
def load_raw(path: str | Path, label: str, *, require_canonical: bool = True) -> tuple[dict[str, Any], bytes]:
    raw = Path(path).read_bytes()
    return parse_json(raw, label, require_canonical=require_canonical), raw
def object_ref(raw: bytes, uri: str, schema: str) -> dict[str, Any]:
    return {"uri": uri, "sha256": hashlib.sha256(raw).hexdigest(), "byte_length": len(raw), "schema": schema}
def evidence_dirs(trace_path: str | Path, operator: str, explicit: str | None) -> list[Path]:
    roots: list[Path] = []
    if explicit is not None:
        roots.append(Path(explicit))
    parent = Path(trace_path).resolve().parent
    if operator in ("A", "B"):
        roots.extend((parent / f"evidence-{operator}", parent / f"evidence-{operator.lower()}"))
    roots.append(parent / "evidence")
    unique_roots: list[Path] = []
    for root in roots:
        if root not in unique_roots:
            unique_roots.append(root)
    return unique_roots
def resolve_ref_raw(ref: dict[str, Any], roots: list[Path], label: str) -> bytes:
    for root in roots:
        try:
            raw = (root / ref["sha256"]).read_bytes()
        except OSError:
            continue
        if len(raw) != ref["byte_length"] or hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise ValueError(f"{label} hash or length mismatches reference")
        return raw
    raise ValueError(f"{label} is not resolvable from capture evidence")
def utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str): raise ValueError(f"{label} is not UTC")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(f"{label} is not UTC") from exc
def require_ref(value: Any, schema: str) -> None:
    if not isinstance(value, dict) or set(value) != REF_KEYS or value["schema"] != schema or not isinstance(value["uri"], str) or not isinstance(value["sha256"], str) or SHA256_RE.fullmatch(value["sha256"]) is None or not isinstance(value["byte_length"], int) or value["byte_length"] < 0:
        raise ValueError(f"{schema} ref is invalid")
def require_fact(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {"code", "detail"} or not isinstance(value["code"], str) or not value["code"] or not isinstance(value["detail"], str) or not value["detail"]:
        raise ValueError("submitted fact is invalid")
def require_codes(values: Any) -> list[str]:
    if not isinstance(values, list) or any(code not in FAILURE_CODES for code in values) or len(set(values)) != len(values) or values != sorted(values, key=FAILURE_CODES.index):
        raise ValueError("task failure codes are not uniquely in frozen order")
    return values
def instrument_facts() -> tuple[dict[str, dict[str, dict[str, str]]], bytes]:
    instrument, raw = load_raw(INSTRUMENT_PATH, "frozen usability instrument", require_canonical=False)
    if instrument.get("schema") != INSTRUMENT_SCHEMA or instrument.get("objective_failure_codes") != list(FAILURE_CODES):
        raise ValueError("frozen instrument is invalid")
    tasks = instrument.get("tasks")
    if not isinstance(tasks, list) or [task.get("id") for task in tasks] != TASK_IDS:
        raise ValueError("frozen instrument task order is invalid")
    expected: dict[str, dict[str, dict[str, str]]] = {}
    for task in tasks:
        facts = task.get("facts")
        if not isinstance(facts, dict) or set(facts) != set(DIMENSIONS):
            raise ValueError("frozen expected facts are invalid")
        expected[task["id"]] = {}
        for dimension in DIMENSIONS:
            require_fact(facts[dimension])
            expected[task["id"]][dimension] = facts[dimension]
    return expected, raw
def validate_instrument_wrapper(ref: dict[str, Any], roots: list[Path], instrument_raw: bytes) -> None:
    require_ref(ref, "kronos_instrument.v2")
    match = RUN_INSTRUMENT_RE.fullmatch(ref["uri"])
    if match is None: raise ValueError("instrument wrapper URI is invalid")
    run_nonce = match.group(1)
    raw_ref = object_ref(instrument_raw, f"kronos-run://{run_nonce}/instrument/usability-v1.json", INSTRUMENT_SCHEMA)
    expected = {"schema": "kronos_instrument.v2", "kind": "dashboard-v5-usability-instrument", "instrument_ref": raw_ref, "objective_failure_codes": list(FAILURE_CODES), "task_ids": TASK_IDS}
    wrapper_raw = resolve_ref_raw(ref, roots, "instrument wrapper")
    wrapper = parse_json(wrapper_raw, "instrument wrapper", require_canonical=True)
    if wrapper != expected: raise ValueError("instrument wrapper does not bind the frozen usability instrument")
    if ref != object_ref(wrapper_raw, f"kronos-run://{run_nonce}/instrument", "kronos_instrument.v2"):
        raise ValueError("operator trace instrument ref does not bind the canonical wrapper")
    bound_raw = resolve_ref_raw(raw_ref, roots, "bound usability instrument")
    if bound_raw != instrument_raw: raise ValueError("bound usability instrument bytes do not match the frozen instrument")
def canonical_failures(tasks: list[dict[str, Any]], operator_index: str) -> list[dict[str, Any]]:
    return [{"operator_index": operator_index, "task_id": task["task_id"], "failure_code": code, "evidence_ref": task["trace_ref"], "detected_at": task["completed_at"]} for task in tasks for code in task["failure_codes"]]
def validate(trace: dict[str, Any], instrument_raw: bytes, roots: list[Path]) -> None:
    if set(trace) != OPERATOR_KEYS or trace.get("schema") != "kronos_operator_trace.v2" or trace.get("operator_index") not in ("A", "B"): raise ValueError("operator trace schema or index is invalid")
    received, started, completed, destroyed = (utc(trace[key], key) for key in ("assignment_received_at", "attempt_started_at", "attempt_completed_at", "profile_destroyed_at"))
    if not received <= started <= completed <= destroyed: raise ValueError("attempt chronology is invalid")
    require_ref(trace["fixture_ref"], "kronos_fixture.v2")
    validate_instrument_wrapper(trace["instrument_ref"], roots, instrument_raw)
    tasks = trace.get("tasks")
    if not isinstance(tasks, list) or [task.get("task_id") for task in tasks] != TASK_IDS: raise ValueError("trace must contain ordered T01 through T10")
    prior = started
    for task in tasks:
        if not isinstance(task, dict) or set(task) != TASK_KEYS: raise ValueError("task trace shape is invalid")
        task_started, task_completed = utc(task["started_at"], "task started_at"), utc(task["completed_at"], "task completed_at")
        if not started <= task_started <= task_completed <= completed or task_started < prior: raise ValueError("task chronology is invalid")
        if not isinstance(task["elapsed_ms"], int) or task["elapsed_ms"] < 0 or task["elapsed_ms"] > int((task_completed - task_started).total_seconds() * 1000): raise ValueError("task elapsed time is invalid")
        if not isinstance(task["action_count"], int) or task["action_count"] < 0: raise ValueError("action count is invalid")
        if not isinstance(task["submitted_facts"], list): raise ValueError("submitted facts are invalid")
        for fact in task["submitted_facts"]: require_fact(fact)
        require_ref(task["trace_ref"], "kronos_task_trace.v2")
        if not isinstance(task["screenshot_refs"], list) or not task["screenshot_refs"]: raise ValueError("screenshot evidence is required")
        for screenshot_ref in task["screenshot_refs"]: require_ref(screenshot_ref, "kronos_screenshot.v2")
        codes = require_codes(task["failure_codes"])
        if task.get("objective_valid") != (not codes): raise ValueError("objective failure state is invalid")
        prior = task_completed
    if trace.get("objective_failures") != canonical_failures(tasks, trace["operator_index"]): raise ValueError("objective failures are not the exact canonical task union")
def fact_matches(task: dict[str, Any], expected: dict[str, dict[str, dict[str, str]]], dimension: str) -> bool:
    submitted = task["submitted_facts"]
    return isinstance(submitted, list) and len(submitted) == len(DIMENSIONS) and submitted[DIMENSIONS.index(dimension)] == expected[task["task_id"]][dimension]
def compute_bits(trace: dict[str, Any], expected: dict[str, dict[str, dict[str, str]]]) -> dict[str, list[bool]]:
    bits: dict[str, list[bool]] = {dimension: [] for dimension in DIMENSIONS}
    for task in trace["tasks"]:
        for dimension in DIMENSIONS:
            bits[dimension].append(bool(task["objective_valid"] and fact_matches(task, expected, dimension)))
    return bits
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit closed kronos_machine_task_score.v2 evidence.")
    parser.add_argument("--trace", required=True); parser.add_argument("--out", required=True); parser.add_argument("--evidence-dir")
    args = parser.parse_args(argv)
    try:
        expected, instrument_raw = instrument_facts()
        trace, _ = load_raw(args.trace, "operator trace")
        validate(trace, instrument_raw, evidence_dirs(args.trace, trace.get("operator_index"), args.evidence_dir))
        score = {"schema": "kronos_machine_task_score.v2", "operator_index": trace["operator_index"], "bitmaps": compute_bits(trace, expected)}
        Path(args.out).write_bytes(canonical(score))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        print(f"V5_TASK_SCORE_REJECTED: {exc}", file=sys.stderr); return 2
    return 0
if __name__ == "__main__": raise SystemExit(main())
