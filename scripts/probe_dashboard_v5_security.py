#!/usr/bin/env python3
"""Fail-closed normalizer for supplied V5 fixture-security probe evidence; no server is started."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
import rfc8785

FALSE_LOCKS = {"promotion_allowed": False, "model_build_allowed": False, "paper_forward_allowed": False, "live_broker_order_allowed": False, "profitability_claim_allowed": False, "go_summary_allowed": False}
DENIAL_MATRIX = {
    "traversal": {"id": "SEC-DENY-TRAVERSAL", "method": "GET", "path": "/api/v5/download", "payload": "../../outside/registry.json", "status": 400},
    "reparse": {"id": "SEC-DENY-REPARSE", "method": "GET", "path": "/api/v5/download", "payload": "reparse:../artifact-junction/fixture.json", "status": 400},
    "oos": {"id": "SEC-DENY-OOS", "method": "GET", "path": "/api/v5/fresh-oos", "payload": "unsealed_fresh_oos_profile", "status": 403},
}
MUTATION_MATRIX = {
    "DELETE": {"id": "SEC-MUTATION-DELETE", "kind": "mutation", "method": "DELETE", "path": "/api/v5/jobs", "payload": "delete-job", "status": 405},
    "PATCH": {"id": "SEC-MUTATION-PATCH", "kind": "mutation", "method": "PATCH", "path": "/api/v5/jobs", "payload": "patch-job", "status": 405},
    "POST": {"id": "SEC-MUTATION-POST", "kind": "mutation", "method": "POST", "path": "/api/v5/jobs", "payload": "create-job", "status": 405},
    "PUT": {"id": "SEC-MUTATION-PUT", "kind": "mutation", "method": "PUT", "path": "/api/v5/jobs", "payload": "replace-job", "status": 405},
}
PROBE_FIELDS = {"id", "kind", "method", "path", "payload", "status", "accepted"}
INPUT_FIELDS = {"schema", "capture_kind", "live_browser_execution", "nonce", "fixture_ref", "source_ref", "downloads", "probes"}
PROHIBITED_CLAIMS = {"OOS_CONSUMED", "LIVE_READY", "PROFIT_READY", "GO_READY"}


def fail(message: str) -> None:
    raise ValueError(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> bytes:
    try:
        return rfc8785.dumps(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("input is outside the RFC8785 profile") from exc


def require_sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        fail(f"{name} must be a lowercase sha256")
    return value

def require_exact_fields(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        fail(f"{label} fields are not canonical")
    return value


def reject_prohibited_claims(value: Any, label: str) -> None:
    if isinstance(value, str):
        upper = value.upper()
        for claim in PROHIBITED_CLAIMS:
            if claim in upper:
                fail(f"{label} contains prohibited claim {claim}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_prohibited_claims(item, f"{label}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            reject_prohibited_claims(key, f"{label}.{key} key")
            reject_prohibited_claims(item, f"{label}.{key}")


def object_ref(root: Path, raw: Any, media_type: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) - {"relative_path", "sha256", "byte_length", "media_type", "schema_id", "captured_at"}:
        fail("ObjectRef is malformed")
    rel = raw.get("relative_path")
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or "\\" in rel or ".." in Path(rel).parts:
        fail("ObjectRef must use a safe relative_path")
    path = (root / rel).resolve()
    if root not in path.parents:
        fail("ObjectRef escapes evidence root")
    data = path.read_bytes()
    actual = {"relative_path": rel, "sha256": sha256_bytes(data), "byte_length": len(data), "media_type": media_type}
    for key, expected in actual.items():
        if raw.get(key) != expected:
            fail(f"ObjectRef {rel} has incorrect {key}")
    return actual


def validate_downloads(downloads: Any) -> tuple[int, int]:
    if not isinstance(downloads, list) or not downloads:
        fail("downloads must be a non-empty list")
    allowed = denied = 0
    ids: set[str] = set()
    for item in downloads:
        if not isinstance(item, dict) or set(item) != {"id", "disposition", "status", "relative_path"}:
            fail("download record is malformed")
        if not isinstance(item["id"], str) or not item["id"] or item["id"] in ids:
            fail("download ids must be unique")
        ids.add(item["id"])
        disposition, status, rel = item["disposition"], item["status"], item["relative_path"]
        if disposition == "allowed":
            if status != 200 or not isinstance(rel, str) or not rel or Path(rel).is_absolute() or "\\" in rel or ".." in Path(rel).parts:
                fail("allowed download is unsafe")
            allowed += 1
        elif disposition == "denied":
            if status not in (400, 403, 404, 405) or rel is not None:
                fail("denied download was not safely denied")
            denied += 1
        else:
            fail("unknown download disposition")
    if allowed < 1 or denied < 1:
        fail("downloads must include at least one allowed and one denied record")
    return allowed, denied


def validate_probe(probe: dict[str, Any]) -> tuple[str | None, str | None]:
    if set(probe) != PROBE_FIELDS:
        fail("probe record is malformed")
    if probe["accepted"] is not False:
        fail("an unsafe request was accepted")
    kind = probe["kind"]
    if kind in DENIAL_MATRIX:
        expected = DENIAL_MATRIX[kind]
        for field, expected_value in expected.items():
            if probe[field] != expected_value:
                fail(f"{kind} denial probe does not match the exact matrix")
        return kind, None
    if kind == "mutation":
        method = probe["method"]
        if method not in MUTATION_MATRIX:
            fail("unknown mutation denial method")
        expected = MUTATION_MATRIX[method]
        for field, expected_value in expected.items():
            if probe[field] != expected_value:
                fail(f"{method} mutation denial probe does not match the exact GET-only matrix")
        return None, method
    fail("unknown probe kind")


def validate_probes(probes: Any) -> tuple[set[str], set[str]]:
    if not isinstance(probes, list) or not probes:
        fail("probes must be a non-empty list")
    ids: set[str] = set()
    seen_denials: set[str] = set()
    seen_mutations: set[str] = set()
    for probe in probes:
        if not isinstance(probe, dict):
            fail("probe record is malformed")
        probe_id = probe.get("id")
        if not isinstance(probe_id, str) or not probe_id or probe_id in ids:
            fail("probe ids must be unique")
        ids.add(probe_id)
        denial, mutation = validate_probe(probe)
        if denial is not None:
            seen_denials.add(denial)
        if mutation is not None:
            seen_mutations.add(mutation)
    if seen_denials != set(DENIAL_MATRIX) or seen_mutations != set(MUTATION_MATRIX):
        fail("required denial or mutation matrix is incomplete")
    return seen_denials, seen_mutations


def produce(raw: dict[str, Any], root: Path) -> dict[str, Any]:
    reject_prohibited_claims(raw, "input")
    require_exact_fields(raw, INPUT_FIELDS, "input")
    if raw["schema"] != "kronos_v5_security_input.v1" or raw["capture_kind"] != "synthetic_fixture_evidence" or raw["live_browser_execution"] is not False:
        fail("input must be explicitly synthetic fixture evidence")
    nonce = require_sha(raw["nonce"], "nonce")
    fixture_ref = object_ref(root, raw["fixture_ref"], "application/json")
    source_ref = object_ref(root, raw["source_ref"], "text/x-python")
    allowed, denied = validate_downloads(raw["downloads"])
    seen_denials, seen_mutations = validate_probes(raw["probes"])
    result = {"schema": "kronos_v5_security_result.v1", "capture_kind": "synthetic_fixture_evidence", "live_browser_execution": False, "nonce": nonce, "fixture_ref": fixture_ref, "source_ref": source_ref, "probe_sha256": sha256_bytes(canonical({"downloads": raw["downloads"], "probes": raw["probes"]})), "allowed_downloads": allowed, "denied_downloads": denied, "denied_probe_kinds": sorted(seen_denials), "v5_mutation_methods_rejected": sorted(seen_mutations), "status": "passed", "false_locks": FALSE_LOCKS}
    result["result_sha256"] = sha256_bytes(canonical(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate deterministic V5 synthetic security evidence.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        root = Path(args.evidence_root).resolve()
        result = produce(json.loads(Path(args.input).read_text(encoding="utf-8")), root)
        Path(args.out).write_bytes(canonical(result) + b"\n")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"security failed closed: {exc}\n")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
