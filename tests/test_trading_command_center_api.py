import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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

@pytest.fixture(autouse=True)
def isolated_trading_command_audit_root(tmp_path, monkeypatch):
    monkeypatch.setattr(trading_command, "DEFAULT_TRADING_COMMAND_AUDIT_ROOT", tmp_path / "trading_command_intents")
    trading_command._reset_trading_command_state_for_tests()
    yield



def _client():
    flask_app.config.update(TESTING=True)
    return flask_app.test_client()


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
    assert payload["first_viewport"]["cards"][1]["label"] == "23bp vs ts_imb RULE baseline"
    assert payload["first_viewport"]["cards"][4]["status"] == "NOT_STARTED"
    assert payload["evidence_health"]["missing"]["status"] == "MISSING"
    assert payload["evidence_health"]["stale"]["status"] == "STALE"
    assert payload["evidence_health"]["malformed"]["status"] == "MALFORMED"
    assert payload["evidence_health"]["no_go"]["status"] == "NO_GO"


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


def test_workflow_route_exposes_d0_d9_no_go_gate_and_forbidden_work():
    client = _client()

    response = client.get("/api/trading-command/workflow")

    assert response.status_code == 200
    payload = response.get_json()
    steps = {item["step"]: item for item in payload["process_map"]}
    assert list(steps) == [f"D{idx}" for idx in range(10)]
    assert steps["D9"]["status"] == "NO_GO"
    assert steps["D9"]["allowed"] is False
    assert "model_build" in payload["forbidden_work"]
    assert "profit_claim" in payload["forbidden_work"]


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


def test_unsafe_jobs_are_rejected_without_launching_work():
    client = _client()

    unsafe_cases = [
        {"workflow": "live_broker_order", "config": {}},
        {"workflow": "record_research_intent", "config": {"artifact_path": "../secrets.json"}},
        {"workflow": "record_research_intent", "config": {"symbols": [250]}},
        {"workflow": "record_research_intent", "config": {"mode": "profit_readiness"}},
    ]

    for payload in unsafe_cases:
        response = client.post("/api/trading-command/jobs", json=payload)
        assert response.status_code == 400
        body = response.get_json()
        assert body["status"] == "REJECTED"
        assert "job_id" not in body

    status = client.get("/api/trading-command/status").get_json()
    assert status["first_viewport"]["cards"][4]["value"]["recorded_intent_count"] == 0


def test_route_availability_and_unknown_ids_fail_closed():
    client = _client()

    for route in (
        "/api/trading-command/status",
        "/api/trading-command/workflow",
        "/api/trading-command/runs",
        "/api/trading-command/audit",
    ):
        assert client.get(route).status_code == 200

    assert client.get("/api/trading-command/runs/unknown/summary").status_code == 404
    assert client.get("/api/trading-command/runs/unknown/evidence").status_code == 404
    assert client.get("/api/trading-command/jobs/research-intent-0000000000000000").status_code == 404

    for invalid_job_id in ("..%5Csecret", "C:%5Csecret", "research-intent-nothex", "research-intent-00000000000000000"):
        response = client.get(f"/api/trading-command/jobs/{invalid_job_id}")
        assert response.status_code == 400
        assert response.get_json()["status"] == "INVALID_JOB_ID"
