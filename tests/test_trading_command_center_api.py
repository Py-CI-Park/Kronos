import hashlib
from datetime import datetime, timedelta, timezone
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from webui import app as app_module  # noqa: E402
from webui import trading_command  # noqa: E402
from webui.app import app as flask_app  # noqa: E402

import pytest


EXPECTED_CARD_ORDER = [
    "selected_run_verdict",
    "cost_baseline_delta_23bp",
    "drawdown",
    "trade_count_turnover",
    "job_progress",
    "d0_d9_gate_status",
]

FORBIDDEN_PRODUCT_COPY = [
    "수익 " + "준비",
    "수익성 " + "준비",
    "거래 " + "준비",
    "거래 " + "준비 판정",
    "거래 " + "준비 완료",
    "profit " + "ready",
    "profit " + "readiness",
    "live " + "ready",
    "trading " + "ready",
    "broker " + "ready",
    "order " + "ready",
    "paper " + "ready",
    "model " + "ready",
    "model-build " + "ready",
]


def _assert_no_forbidden_product_copy(payload):
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for term in FORBIDDEN_PRODUCT_COPY:
        assert term.lower() not in serialized

@pytest.fixture(autouse=True)
def isolated_trading_command_audit_root(tmp_path, monkeypatch):
    monkeypatch.setattr(trading_command, "DEFAULT_TRADING_COMMAND_AUDIT_ROOT", tmp_path / "trading_command_intents")
    trading_command._reset_trading_command_state_for_tests()
    yield



def _client():
    flask_app.config.update(TESTING=True)
    return flask_app.test_client()


def _evidence_dir() -> Path:
    path = trading_command.DEFAULT_TRADING_COMMAND_AUDIT_ROOT / trading_command.DEFAULT_RUN_ID / "evidence"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_manifest(name: str, manifest: dict, rows: list[dict] | None = None) -> tuple[Path, Path | None]:
    evidence_dir = _evidence_dir()
    data_path = None
    if rows is not None:
        data_path = evidence_dir / f"{name}.json"
        data_path.write_text(json.dumps({"rows": rows}, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        manifest.setdefault("path", data_path.name)
        manifest.setdefault("hash", hashlib.sha256(data_path.read_bytes()).hexdigest())
    manifest_path = evidence_dir / f"{name}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return manifest_path, data_path


def _valid_manifest(
    name: str,
    *,
    path: str | None = None,
    symbols: list | None = None,
    timestamp: str | None = None,
    kind: str = "backend_series",
    source_stage: str | None = None,
) -> dict:
    default_stage = "D0" if kind == "backend_series" else "D9" if kind == "gate_table" else "D7"
    return {
        "artifact_id": name,
        "run_id": trading_command.DEFAULT_RUN_ID,
        "kind": kind,
        "series_source": "BACKEND_OWNED",
        "path": path or f"{name}.json",
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "source_stage": source_stage or default_stage,
        "source_run_id": trading_command.DEFAULT_RUN_ID,
        "symbols": symbols if symbols is not None else ["000250", "005930"],
    }


def _artifact_by_id(payload: dict, artifact_id: str) -> dict:
    return next(artifact for artifact in payload["artifacts"] if artifact["artifact_id"] == artifact_id)


def test_status_guardrails_and_first_viewport_six_card_order():
    client = _client()

    response = client.get("/api/trading-command/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mode"] == "RESEARCH_ONLY"
    assert {"NO-GO", "RESEARCH_ONLY", "23bp", "ts_imb RULE baseline"}.issubset(set(payload["labels"]))
    assert payload["first_viewport"]["sections"] == ["status_locks", "workflow_process_map", "kpi_cards"]
    assert [card["id"] for card in payload["first_viewport"]["cards"]] == EXPECTED_CARD_ORDER
    assert len(payload["first_viewport"]["cards"]) == 6
    assert payload["first_viewport"]["cards"][1]["label"] == "23bp vs ts_imb 룰 기준선"
    assert payload["first_viewport"]["cards"][4]["status"] == "NOT_STARTED"
    assert payload["evidence_health"]["missing"]["status"] == "MISSING"
    assert payload["evidence_health"]["stale"]["status"] == "STALE"
    assert payload["evidence_health"]["malformed"]["status"] == "MALFORMED"
    assert payload["evidence_health"]["no_go"]["status"] == "NO_GO"
    assert payload["artifact_manifest_schema"]["symbols_are_strings"] is True
    assert {"hash", "path", "timestamp", "freshness", "schema_status", "blocker_reason", "source_stage", "source_run_id", "symbols"}.issubset(
        set(payload["artifact_manifest_schema"]["required_fields"])
    )
    _assert_no_forbidden_product_copy(payload)
    assert payload["queue_summary"]["mode"] == "RESEARCH_ONLY_QUEUE"
    assert payload["queue_summary"]["unsafe_controls_allowed"] is False
    assert payload["queue_summary"]["recorded_intent_count"] == 0


def test_forbidden_claim_locks_are_false_and_api_unavailable():
    client = _client()

    payload = client.get("/api/trading-command/status").get_json()

    assert payload["claim_locks"] == {
        "live": False,
        "broker": False,
        "order": False,
        "account": False,
        "paper": False,
        "model": False,
        "profit": False,
    }
    for lock_name in ("live", "broker", "order", "account", "paper", "model", "profit"):
        assert payload["status_locks"][lock_name]["locked"] is False
        assert payload["status_locks"][lock_name]["status"] == "API_UNAVAILABLE"
        assert "NO-GO" in payload["status_locks"][lock_name]["label"]
        assert payload["status_locks"][lock_name]["allowed"] is False
        assert payload["status_locks"][lock_name]["enabled"] is False
        assert payload["status_locks"][lock_name]["capability_state"] == "BLOCKED"
        assert "reason" in payload["status_locks"][lock_name]


def test_runs_summary_evidence_and_audit_preserve_leading_zero_symbols():
    client = _client()

    runs_payload = client.get("/api/trading-command/runs").get_json()
    run_id = runs_payload["selected_run_id"]
    assert run_id == "research_ts_imb_rule_baseline_23bp"
    assert runs_payload["runs"][0]["symbols"][0] == "000250"
    assert isinstance(runs_payload["runs"][0]["symbols"][0], str)

    summary = client.get(f"/api/trading-command/runs/{run_id}/summary").get_json()
    evidence = client.get(f"/api/trading-command/runs/{run_id}/evidence").get_json()
    audit = client.get(f"/api/trading-command/runs/{run_id}/audit").get_json()

    assert summary["strategy_type"] == "RULE_BASELINE"
    assert summary["baseline_label"] == "ts_imb RULE baseline"
    assert summary["cost_assumption_bps"] == 23
    assert summary["symbols"] == ["000250", "005930", "035420"]
    assert evidence["symbols"] == ["000250", "005930", "035420"]
    assert {artifact["status"] for artifact in evidence["artifacts"]} == {"STALE", "MISSING", "MALFORMED"}
    assert audit["status"] == "RESEARCH_ONLY_AUDIT"
    for artifact in evidence["artifacts"]:
        assert {"artifact_id", "hash", "path", "timestamp", "freshness", "schema_status", "blocker_reason", "source_stage", "source_run_id", "symbols"}.issubset(artifact)
        assert artifact["symbols"] == ["000250", "005930", "035420"]
    _assert_no_forbidden_product_copy(summary)
    _assert_no_forbidden_product_copy(evidence)
    _assert_no_forbidden_product_copy(audit)


def test_evidence_discovers_valid_backend_owned_artifact_with_hash_rows_and_leading_zero_symbols():
    client = _client()
    manifest = _valid_manifest("fresh-backend-series", symbols=["000250", "005930"])
    _write_manifest("fresh-backend-series", manifest, rows=[{"symbol": "000250", "value": 1.25}, {"symbol": "005930", "value": -0.5}])

    payload = client.get(f"/api/trading-command/runs/{trading_command.DEFAULT_RUN_ID}/evidence").get_json()

    artifact = _artifact_by_id(payload, "fresh-backend-series")
    assert artifact["status"] == "FRESH"
    assert artifact["freshness"] == "FRESH"
    assert artifact["schema_status"] == "VALID"
    assert artifact["series_source"] == "BACKEND_OWNED"
    assert artifact["run_id"] == trading_command.DEFAULT_RUN_ID
    assert artifact["source_run_id"] == trading_command.DEFAULT_RUN_ID
    assert artifact["symbols"] == ["000250", "005930"]
    assert all(isinstance(symbol, str) for symbol in artifact["symbols"])
    assert artifact["row_count"] == 2
    assert len(artifact["hash"]) == 64
    assert artifact["path"] == "fresh-backend-series.json"
    assert "backend_series" in payload["artifact_schema"]["accepted_research_evidence_kinds"]

def test_evidence_discovers_backend_table_and_gate_table_as_fresh_schema_gated_artifacts():
    client = _client()
    _write_manifest(
        "fresh-backend-table",
        _valid_manifest("fresh-backend-table", kind="backend_table"),
        rows=[{"symbol": "000250", "metric": "audit"}, {"symbol": "005930", "metric": "schema"}],
    )
    _write_manifest(
        "fresh-gate-table",
        _valid_manifest("fresh-gate-table", kind="gate_table"),
        rows=[{"symbol": "000250", "gate": "D9", "verdict": "NO-GO"}],
    )

    payload = client.get(f"/api/trading-command/runs/{trading_command.DEFAULT_RUN_ID}/evidence").get_json()

    table_artifact = _artifact_by_id(payload, "fresh-backend-table")
    gate_artifact = _artifact_by_id(payload, "fresh-gate-table")
    for artifact, expected_kind, expected_stage, expected_rows in (
        (table_artifact, "backend_table", "D7", 2),
        (gate_artifact, "gate_table", "D9", 1),
    ):
        assert artifact["status"] == "FRESH"
        assert artifact["schema_status"] == "VALID"
        assert artifact["kind"] == expected_kind
        assert artifact["source_stage"] == expected_stage
        assert artifact["source_run_id"] == trading_command.DEFAULT_RUN_ID
        assert artifact["series_source"] == "BACKEND_OWNED"
        assert artifact["row_count"] == expected_rows
        assert len(artifact["hash"]) == 64
        assert artifact["symbols"] == ["000250", "005930"]


def test_evidence_fail_closes_malformed_empty_path_rejected_numeric_symbol_and_stale_artifacts():
    client = _client()
    stale_timestamp = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    _write_manifest("malformed-artifact", {"artifact_id": "malformed-artifact", "path": "missing-kind.json"})
    _write_manifest("empty-artifact", _valid_manifest("empty-artifact"), rows=[])
    _write_manifest("path-rejected-artifact", _valid_manifest("path-rejected-artifact", path="../outside.json"))
    _write_manifest("numeric-symbol-artifact", _valid_manifest("numeric-symbol-artifact", symbols=[250]))
    _write_manifest("stale-artifact", _valid_manifest("stale-artifact", timestamp=stale_timestamp), rows=[{"symbol": "000250"}])

    payload = client.get(f"/api/trading-command/runs/{trading_command.DEFAULT_RUN_ID}/evidence").get_json()

    expected = {
        "malformed-artifact": "MALFORMED",
        "empty-artifact": "EMPTY",
        "path-rejected-artifact": "PATH_REJECTED",
        "numeric-symbol-artifact": "MALFORMED",
        "stale-artifact": "STALE",
    }
    for artifact_id, status in expected.items():
        artifact = _artifact_by_id(payload, artifact_id)
        assert artifact["status"] == status
        assert artifact["blocker_reason"]
        assert artifact["schema_status"]
        assert artifact["hash"] is None
    assert _artifact_by_id(payload, "path-rejected-artifact")["path"] == "../outside.json"


def test_evidence_rejects_generic_receipt_even_when_it_has_rows():
    client = _client()
    manifest = _valid_manifest("generic-receipt", kind="receipt")
    _write_manifest("generic-receipt", manifest, rows=[{"status": "ok"}])

    payload = client.get(f"/api/trading-command/runs/{trading_command.DEFAULT_RUN_ID}/evidence").get_json()

    artifact = _artifact_by_id(payload, "generic-receipt")
    assert artifact["status"] == "MALFORMED"
    assert artifact["schema_status"] == "KIND_REJECTED"
    assert artifact["freshness"] == "MALFORMED"
    assert artifact["hash"] is None


def test_workflow_route_exposes_d0_d9_no_go_gate_and_forbidden_work():
    client = _client()

    response = client.get("/api/trading-command/workflow")

    assert response.status_code == 200
    payload = response.get_json()
    steps = {item["step"]: item for item in payload["process_map"]}
    assert list(steps) == [f"D{idx}" for idx in range(10)]
    assert steps["D9"]["status"] == "NO_GO"
    assert steps["D9"]["allowed"] is False
    assert steps["D9"]["name"] == "연구 검토 / NO-GO 게이트"
    assert steps["D9"]["enabled"] is False
    assert steps["D9"]["capability_state"] == "BLOCKED"
    assert steps["D9"]["blocker_reason"]
    assert steps["D9"]["source_run_id"] == "research_ts_imb_rule_baseline_23bp"
    for step in steps.values():
        assert step["allowed"] is False
        assert isinstance(step["artifact_refs"], list)
        assert step["updated_at"] is None
    assert "model_build" in payload["forbidden_work"]
    assert "profit_claim" in payload["forbidden_work"]
    _assert_no_forbidden_product_copy(payload)


def test_job_post_is_allowlisted_idempotent_audited_and_detail_available():
    client = _client()
    request_payload = {
        "workflow": "record_research_intent",
        "config": {"run_id": "research_ts_imb_rule_baseline_23bp", "symbols": ["000250", "005930"]},
        "requested_by": "pytest",
    }

    first = client.post("/api/trading-command/jobs", json=request_payload)
    second = client.post("/api/trading-command/jobs", json=request_payload)

    assert first.status_code == 202
    assert second.status_code == 200
    first_payload = first.get_json()
    second_payload = second.get_json()
    assert first_payload["job_id"] == second_payload["job_id"]
    assert first_payload["launched"] is False
    assert first_payload["status"] == "RECORDED_RESEARCH_INTENT"
    assert first_payload["audit"]["status"] == "AUDITED_RESEARCH_INTENT"
    assert first_payload["symbols"] == ["000250", "005930"]
    assert second_payload["idempotent"] is True

    detail = client.get(f"/api/trading-command/jobs/{first_payload['job_id']}")
    assert detail.status_code == 200
    assert detail.get_json()["job_id"] == first_payload["job_id"]

    audit = client.get("/api/trading-command/audit").get_json()
    assert audit["events"][-1]["event"] == "research_intent_recorded"
    audit_root = trading_command.DEFAULT_TRADING_COMMAND_AUDIT_ROOT
    intent_path = audit_root / first_payload["job_id"] / "intent.json"
    ledger_path = audit_root / "audit.jsonl"
    assert intent_path.is_file()
    assert json.loads(intent_path.read_text(encoding="utf-8"))["symbols"] == ["000250", "005930"]
    assert ledger_path.is_file()
    assert "research_intent_recorded" in ledger_path.read_text(encoding="utf-8")

    jobs = client.get("/api/trading-command/jobs").get_json()
    assert jobs["status"] == "RESEARCH_ONLY_QUEUE"
    assert jobs["queue_summary"]["recorded_intent_count"] == 1
    assert jobs["queue_summary"]["active_job_count"] == 0
    assert jobs["jobs"][0]["symbols"] == ["000250", "005930"]
    assert jobs["jobs"][0]["config_hash"]
    assert jobs["jobs"][0]["idempotency_key"] == first_payload["job_id"]
    assert jobs["jobs"][0]["audit_status"] == "AUDITED_RESEARCH_INTENT"
    assert jobs["jobs"][0]["active"] is False
    assert first_payload["config_hash"] == jobs["jobs"][0]["config_hash"]

    _assert_no_forbidden_product_copy(jobs)


def test_drilldown_route_exposes_hash_backed_safe_tabs_and_research_history():
    client = _client()
    client.post(
        "/api/trading-command/jobs",
        json={
            "workflow": "record_research_intent",
            "config": {"run_id": trading_command.DEFAULT_RUN_ID, "symbols": ["000250", "005930"]},
            "requested_by": "pytest",
        },
    )

    response = client.get(f"/api/trading-command/runs/{trading_command.DEFAULT_RUN_ID}/drilldown")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["run_id"] == trading_command.DEFAULT_RUN_ID
    assert payload["safe_preview_policy"]["path_safe"] is True
    assert payload["safe_preview_policy"]["hash_backed"] is True
    assert payload["safe_preview_policy"]["active_job_count"] == 0
    tabs = {tab["id"]: tab for tab in payload["tabs"]}
    assert {"manifest", "run_summary", "audit_timeline", "research_intents", "raw_json"}.issubset(tabs)
    for tab in tabs.values():
        assert tab["path_safe"] is True
        assert tab["hash_backed"] is True
        assert len(tab["preview_hash"]) == 64
        assert isinstance(tab["rows"], list)
    job = tabs["research_intents"]["rows"][0]
    assert job["status"] == "RECORDED_RESEARCH_INTENT"
    assert job["config_hash"]
    assert job["idempotency_key"] == job["job_id"]
    assert job["audit_status"] == "AUDITED_RESEARCH_INTENT"
    assert job["symbols"] == ["000250", "005930"]
    assert job["active"] is False
    assert tabs["manifest"]["rows"][0]["path_safe"] is True
    _assert_no_forbidden_product_copy(payload)



def test_unsafe_jobs_are_rejected_without_launching_work():
    client = _client()

    unsafe_cases = [
        {"workflow": "live_broker_order", "config": {}},
        {"workflow": "record_research_intent", "config": {"artifact_path": "../secrets.json"}},
        {"workflow": "record_research_intent", "config": {"symbols": [250]}},
        {"workflow": "record_research_intent", "config": {"mode": "profit_readiness"}},
        {"workflow": "record_research_intent", "config": {"memo": "실거래 주문 수익 준비"}},
    ]

    for payload in unsafe_cases:
        response = client.post("/api/trading-command/jobs", json=payload)
        assert response.status_code == 400
        body = response.get_json()
        assert body["status"] == "REJECTED"
        assert "job_id" not in body

    status = client.get("/api/trading-command/status").get_json()
    assert status["first_viewport"]["cards"][4]["value"]["recorded_intent_count"] == 0

    safe_orderbook = client.post(
        "/api/trading-command/jobs",
        json={
            "workflow": "record_research_intent",
            "config": {"run_id": "research_ts_imb_rule_baseline_23bp", "experiment_preset": "orderbook_falsification", "symbols": ["000250"]},
        },
    )
    assert safe_orderbook.status_code == 202
    assert safe_orderbook.get_json()["symbols"] == ["000250"]

    trading_token = client.post(
        "/api/trading-command/jobs",
        json={"workflow": "record_research_intent", "config": {"mode": "trading_ready", "symbols": ["000250"]}},
    )
    assert trading_token.status_code == 400
    korean_token = client.post(
        "/api/trading-command/jobs",
        json={"workflow": "record_research_intent", "config": {"memo": "계좌 접근과 거래 준비 판정"}},
    )
    assert korean_token.status_code == 400



def test_route_availability_and_unknown_ids_fail_closed():
    client = _client()

    for route in (
        "/api/trading-command/status",
        "/api/trading-command/workflow",
        "/api/trading-command/runs",
        "/api/trading-command/audit",
        "/api/trading-command/jobs",
    ):
        assert client.get(route).status_code == 200

    assert client.get("/api/trading-command/runs/unknown/summary").status_code == 404
    assert client.get("/api/trading-command/runs/unknown/evidence").status_code == 404
    assert client.get("/api/trading-command/runs/unknown/drilldown").status_code == 404
    assert client.get("/api/trading-command/jobs/research-intent-0000000000000000").status_code == 404

    for invalid_job_id in ("..%5Csecret", "C:%5Csecret", "research-intent-nothex", "research-intent-00000000000000000"):
        response = client.get(f"/api/trading-command/jobs/{invalid_job_id}")
        assert response.status_code == 400
        assert response.get_json()["status"] == "INVALID_JOB_ID"


def test_trading_command_loader_failures_are_api_unavailable_and_safe(monkeypatch):
    client = _client()
    monkeypatch.setattr(app_module, "load_trading_command_status", None)

    response = client.get("/api/trading-command/status")

    assert response.status_code == 503
    payload = response.get_json()
    assert payload["status"] == "API_UNAVAILABLE"
    assert payload["api_status"] == "API_UNAVAILABLE"
    assert payload["mode"] == "RESEARCH_ONLY"
    assert payload["error_code"] == "TRADING_COMMAND_HELPER_UNAVAILABLE"
    assert payload["controls"]["research_intent_record_allowed"] is False
    assert payload["controls"]["unsafe_trading_controls_allowed"] is False
    assert payload["queue_summary"]["unsafe_controls_allowed"] is False
    assert "error" not in payload
    for lock in payload["status_locks"].values():
        assert lock["allowed"] is False
        assert lock["enabled"] is False
        assert lock["capability_state"] == "BLOCKED"
        assert lock["status"] == "API_UNAVAILABLE"
