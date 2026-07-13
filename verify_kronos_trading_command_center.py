"""Focused verification wrapper for the Kronos Trading Command Center.

This helper is launched by verify_kronos_trading_command_center.bat.  It is
intentionally read-only for product behavior: it builds the static frontend,
runs focused pytest coverage, performs Flask API/HTML guardrail probes, and
writes verification receipts under artifacts/.  Those receipts are not stored
under the research-evidence allowlisted roots and are explicitly checked so they
cannot become FRESH research evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
ARTIFACT_DIR = REPO_ROOT / "artifacts"
RUN_ID = "research_ts_imb_rule_baseline_23bp"
REQUIRED_LABELS = ["NO-GO", "RESEARCH_ONLY", "23bp", "ts_imb RULE baseline"]
REQUIRED_HTML_MARKERS = [
    "data-kronos-trading-command-center",
    "강화학습 연구 커맨드 센터",
    "API 미연결(안전 잠금)",
    "실거래 꺼짐",
    "실제 학습 실행 잠금",
    "pixel_svg_v4.zip",
    "data-chart-source-gated",
    "data-evidence-empty-state",
    "data-drilldown-tabs",
    "data-research-intent-history",
    "config_hash",
    "active count zero",
]
FORBIDDEN_COPY = [
    "수익 준비",
    "수익성 준비",
    "거래 준비",
    "거래 준비 판정",
    "거래 준비 완료",
    "profit ready",
    "profit readiness",
    "live ready",
    "trading ready",
    "broker ready",
    "order ready",
    "paper ready",
    "model ready",
    "model-build ready",
]
RECEIPT_NAME_FRAGMENTS = (
    "g006_",
    "verification_wrapper",
    "quality_gate",
    "test_receipt",
    "browser_run",
    "final_score",
    "guardrail_copy_scan",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_tail(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


def run_command(command: list[str], *, cwd: Path, name: str) -> dict[str, Any]:
    started_at = utc_now()
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return {
        "name": name,
        "command": command,
        "cwd": str(cwd.relative_to(REPO_ROOT) if cwd != REPO_ROOT else "."),
        "startedAt": started_at,
        "completedAt": utc_now(),
        "returncode": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "outputTail": safe_tail(completed.stdout or ""),
    }


def assert_true(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def response_json(client: Any, path: str, failures: list[str]) -> dict[str, Any]:
    response = client.get(path)
    assert_true(response.status_code == 200, f"{path} returned {response.status_code}", failures)
    payload = response.get_json(silent=True)
    assert_true(isinstance(payload, dict), f"{path} did not return JSON object", failures)
    return payload if isinstance(payload, dict) else {}


def scan_forbidden(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in FORBIDDEN_COPY if term.lower() in lowered]


def api_and_html_probe() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from webui.app import app as flask_app  # noqa: WPS433

    flask_app.config.update(TESTING=True)
    client = flask_app.test_client()
    failures: list[str] = []

    status = response_json(client, "/api/trading-command/status", failures)
    runs = response_json(client, "/api/trading-command/runs", failures)
    workflow = response_json(client, "/api/trading-command/workflow", failures)
    evidence = response_json(client, f"/api/trading-command/runs/{RUN_ID}/evidence", failures)
    drilldown = response_json(client, f"/api/trading-command/runs/{RUN_ID}/drilldown", failures)
    audit = response_json(client, f"/api/trading-command/runs/{RUN_ID}/audit", failures)
    jobs = response_json(client, "/api/trading-command/jobs", failures)

    html_response = client.get("/rl")
    assert_true(html_response.status_code == 200, f"/rl returned {html_response.status_code}", failures)
    html = html_response.data.decode("utf-8", errors="replace")

    labels = set(status.get("labels", []))
    for label in REQUIRED_LABELS:
        assert_true(label in labels or label in html, f"required label missing: {label}", failures)
    assert_true(status.get("mode") == "RESEARCH_ONLY", "status mode is not RESEARCH_ONLY", failures)
    assert_true(status.get("cost_assumption_bps") == 23, "cost assumption is not 23bp", failures)
    assert_true(runs.get("selected_run_id") == RUN_ID, "selected run id changed", failures)
    assert_true(evidence.get("symbols", [None])[0] == "000250", "leading-zero 000250 not preserved", failures)
    assert_true(all(isinstance(symbol, str) for symbol in evidence.get("symbols", [])), "symbols are not strings", failures)
    assert_true(jobs.get("queue_summary", {}).get("active_job_count") == 0, "research intent queue has active work", failures)

    for lock_name, lock in (status.get("status_locks") or {}).items():
        assert_true(lock.get("allowed") is False, f"{lock_name} lock unexpectedly allowed", failures)
        assert_true(lock.get("enabled") is False, f"{lock_name} lock unexpectedly enabled", failures)
        assert_true(lock.get("capability_state") == "BLOCKED", f"{lock_name} lock not BLOCKED", failures)
    assert_true(status.get("controls", {}).get("unsafe_trading_controls_allowed") is False, "unsafe trading controls allowed", failures)
    assert_true(workflow.get("status") == "NO-GO", "workflow status is not NO-GO", failures)
    assert_true("model_build" in workflow.get("forbidden_work", []), "model_build not forbidden", failures)
    assert_true("profit_claim" in workflow.get("forbidden_work", []), "profit_claim not forbidden", failures)
    assert_true(drilldown.get("safe_preview_policy", {}).get("active_job_count") == 0, "drilldown active count not zero", failures)

    missing_markers = [marker for marker in REQUIRED_HTML_MARKERS if marker not in html]
    assert_true(not missing_markers, f"/rl missing markers: {missing_markers}", failures)

    combined = json.dumps(
        {
            "status": status,
            "runs": runs,
            "workflow": workflow,
            "evidence": evidence,
            "drilldown": drilldown,
            "audit": audit,
            "jobs": jobs,
            "html": html,
        },
        ensure_ascii=False,
    )
    forbidden = scan_forbidden(combined)
    assert_true(not forbidden, f"forbidden copy found: {forbidden}", failures)

    accepted_kinds = set((evidence.get("artifact_schema") or {}).get("accepted_research_evidence_kinds", {}))
    receipt_paths: list[str] = []
    for artifact in evidence.get("artifacts", []):
        artifact_path = str(artifact.get("path") or "")
        if any(fragment in artifact_path for fragment in RECEIPT_NAME_FRAGMENTS):
            receipt_paths.append(artifact_path)
        if artifact.get("status") == "FRESH":
            assert_true(artifact.get("kind") in accepted_kinds, f"FRESH artifact has unaccepted kind: {artifact.get('kind')}", failures)
            assert_true(artifact.get("series_source") == "BACKEND_OWNED", "FRESH artifact is not BACKEND_OWNED", failures)
    assert_true(not receipt_paths, f"verification receipts surfaced as research evidence: {receipt_paths}", failures)

    api_probe = {
        "schemaVersion": 1,
        "kind": "black-box-api-receipt",
        "generatedAt": utc_now(),
        "runId": RUN_ID,
        "status": status.get("api_status"),
        "mode": status.get("mode"),
        "labels": sorted(labels),
        "costAssumptionBps": status.get("cost_assumption_bps"),
        "symbols": evidence.get("symbols"),
        "workflowStatus": workflow.get("status"),
        "forbiddenWork": workflow.get("forbidden_work"),
        "queueSummary": jobs.get("queue_summary"),
        "drilldownPolicy": drilldown.get("safe_preview_policy"),
        "artifactCount": len(evidence.get("artifacts", [])),
        "freshArtifactKinds": [artifact.get("kind") for artifact in evidence.get("artifacts", []) if artifact.get("status") == "FRESH"],
        "receiptEvidencePaths": receipt_paths,
        "failures": failures,
        "verdict": "passed" if not failures else "failed",
    }
    guardrail_scan = {
        "schemaVersion": 1,
        "kind": "failure-mode-test",
        "generatedAt": utc_now(),
        "surface": "web/api",
        "requiredLabels": REQUIRED_LABELS,
        "missingHtmlMarkers": missing_markers,
        "forbiddenFindings": forbidden,
        "lockStates": status.get("status_locks"),
        "researchOnlyMode": status.get("mode") == "RESEARCH_ONLY",
        "unsafeControlsAllowed": status.get("controls", {}).get("unsafe_trading_controls_allowed"),
        "verdict": "passed" if not failures else "failed",
    }
    dom_probe = {
        "schemaVersion": 1,
        "kind": "browser-dom-marker-probe",
        "generatedAt": utc_now(),
        "route": "/rl",
        "statusCode": html_response.status_code,
        "htmlSha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "markers": {marker: (marker in html) for marker in REQUIRED_HTML_MARKERS},
        "verdict": "passed" if not missing_markers else "failed",
    }
    return api_probe, guardrail_scan, dom_probe


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Focused Kronos Trading Command Center verification")
    parser.add_argument("--skip-build", action="store_true", help="Skip npm build for local debugging only")
    parser.add_argument("--skip-pytest", action="store_true", help="Skip pytest for local debugging only")
    args = parser.parse_args()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []

    commands.append(run_command(["cmd", "/c", "start_kronos_dashboard.bat", "--check"], cwd=REPO_ROOT, name="launcher-preflight"))
    if not args.skip_build:
        commands.append(run_command(["cmd", "/c", "npm", "run", "build"], cwd=REPO_ROOT / "webui" / "trading_src", name="next-build"))
    if not args.skip_pytest:
        commands.append(
            run_command(
                [
                    "py",
                    "-3.11",
                    "-m",
                    "pytest",
                    "tests/test_trading_command_center_api.py",
                    "tests/test_v2_route.py",
                    "tests/test_v2_dist_marker.py",
                    "-q",
                ],
                cwd=REPO_ROOT,
                name="focused-pytest",
            )
        )

    api_probe, guardrail_scan, dom_probe = api_and_html_probe()

    write_json(ARTIFACT_DIR / "g006_api_probe.json", api_probe)
    write_json(ARTIFACT_DIR / "g006_guardrail_copy_scan.json", guardrail_scan)
    write_json(ARTIFACT_DIR / "g006_dom_marker_probe.json", dom_probe)

    receipt = {
        "schemaVersion": 1,
        "kind": "package-consumer-report",
        "goalId": "G006",
        "generatedAt": utc_now(),
        "commands": commands,
        "apiProbe": "artifacts/g006_api_probe.json",
        "guardrailCopyScan": "artifacts/g006_guardrail_copy_scan.json",
        "domMarkerProbe": "artifacts/g006_dom_marker_probe.json",
        "receiptEvidencePolicy": {
            "receiptDirectory": "artifacts/",
            "researchEvidenceReceiptPaths": api_probe.get("receiptEvidencePaths", []),
            "notUnderTradingEvidenceRoot": True,
            "verdict": "passed" if not api_probe.get("receiptEvidencePaths") else "failed",
        },
        "verdict": "passed",
    }
    failures = []
    failures.extend(command["name"] for command in commands if command["returncode"] != 0)
    if api_probe.get("verdict") != "passed":
        failures.append("api-probe")
    if guardrail_scan.get("verdict") != "passed":
        failures.append("guardrail-scan")
    if dom_probe.get("verdict") != "passed":
        failures.append("dom-marker-probe")
    if receipt["receiptEvidencePolicy"]["verdict"] != "passed":
        failures.append("receipt-evidence-policy")
    if failures:
        receipt["verdict"] = "failed"
        receipt["failures"] = failures
    write_json(ARTIFACT_DIR / "g006_verification_wrapper_receipt.json", receipt)
    print(json.dumps({"verdict": receipt["verdict"], "failures": failures, "receipt": "artifacts/g006_verification_wrapper_receipt.json"}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
