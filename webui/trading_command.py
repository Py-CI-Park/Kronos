"""Research-only API helpers for the trading command center.

The command center is a backend-owned BFF surface.  It intentionally records
research intent only; it never starts live, broker, order, account, paper,
model-build, or profit-readiness workflows.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

RESEARCH_LABELS = ["NO-GO", "RESEARCH_ONLY", "23bp", "ts_imb RULE baseline"]
COST_ASSUMPTION_BPS = 23
DEFAULT_RUN_ID = "research_ts_imb_rule_baseline_23bp"
DEFAULT_TRADING_COMMAND_AUDIT_ROOT = Path(__file__).resolve().parent / "rl_runs" / "trading_command_intents"
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")
_JOB_ID_RE = re.compile(r"^research-intent-[0-9a-f]{16}$")
_ALLOWED_WORKFLOWS = {
    "record_research_intent",
    "refresh_research_snapshot",
    "audit_evidence_manifest",
}
_BLOCKED_TOKENS = (
    "live",
    "broker",
    "order",
    "account",
    "paper",
    "model_build",
    "model-build",
    "profit",
    "ready_for_trading",
    "readiness",
)
_JOBS: dict[str, dict[str, Any]] = {}
_AUDIT_EVENTS: list[dict[str, Any]] = []


def _clone(payload: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(payload)


def _canonical(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _job_id(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:16]
    return f"research-intent-{digest}"

def _audit_root() -> Path:
    return Path(DEFAULT_TRADING_COMMAND_AUDIT_ROOT)


def _job_record_path(job_id: str) -> Path:
    return _audit_root() / job_id / "intent.json"


def _ledger_path() -> Path:
    return _audit_root() / "audit.jsonl"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_job_record(job_id: str) -> dict[str, Any] | None:
    cached = _JOBS.get(job_id)
    if cached is not None:
        return _clone(cached)
    record = _read_json(_job_record_path(job_id))
    if record is not None:
        _JOBS[job_id] = _clone(record)
    return record


def _load_job_records() -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {job_id: _clone(job) for job_id, job in _JOBS.items()}
    root = _audit_root()
    if root.exists():
        for path in sorted(root.glob("research-intent-*/intent.json")):
            record = _read_json(path)
            if record and isinstance(record.get("job_id"), str):
                records[record["job_id"]] = record
    return [records[key] for key in sorted(records)]


def _write_job_record(job: dict[str, Any]) -> None:
    path = _job_record_path(str(job["job_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(job, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")


def _append_audit_event(event: dict[str, Any]) -> None:
    _AUDIT_EVENTS.append(_clone(event))
    ledger = _ledger_path()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _load_audit_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    ledger = _ledger_path()
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    if events:
        return events
    return [_clone(event) for event in _AUDIT_EVENTS]



def _contains_path_traversal(value: Any) -> bool:
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        return ".." in normalized.split("/") or normalized.startswith("/") or ":" in normalized[:3]
    if isinstance(value, dict):
        return any(_contains_path_traversal(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_path_traversal(item) for item in value)
    return False


def _contains_blocked_token(value: Any) -> str | None:
    if isinstance(value, str):
        lower = value.lower()
        for token in _BLOCKED_TOKENS:
            if token in lower:
                return token
    if isinstance(value, dict):
        for key, item in value.items():
            found = _contains_blocked_token(key) or _contains_blocked_token(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _contains_blocked_token(item)
            if found:
                return found
    return None


def _validate_safe_id(name: str, value: Any) -> str | None:
    if not isinstance(value, str) or not _SAFE_ID_RE.match(value):
        return f"{name} must be a safe string id"
    return None

def _validate_job_id(value: Any) -> str | None:
    if not isinstance(value, str) or not _JOB_ID_RE.match(value):
        return "job_id must match a generated research intent id"
    return None


def _selected_run_summary() -> dict[str, Any]:
    return {
        "run_id": DEFAULT_RUN_ID,
        "name": "ts_imb opening rule baseline research snapshot",
        "strategy_type": "RULE_BASELINE",
        "baseline_label": "ts_imb RULE baseline",
        "cost_assumption_bps": COST_ASSUMPTION_BPS,
        "verdict": "NO-GO",
        "research_only": True,
        "symbols": ["000250", "005930", "035420"],
        "reason_codes": ["NO-GO", "STALE_EVIDENCE", "MISSING_D0_D9_GATE", "MALFORMED_OPTIONAL_ARTIFACT"],
        "forbidden_claim_locks": _forbidden_claim_locks(),
        "metrics": {
            "selected_run_verdict": "NO-GO",
            "baseline_delta_after_23bp": None,
            "baseline_delta_status": "NO_GO_MISSING_FRESH_COMPARISON",
            "max_drawdown_pct": None,
            "drawdown_status": "MISSING",
            "trade_count": 0,
            "turnover": None,
            "trade_count_status": "STALE",
            "d0_d9_gate_status": "NO-GO",
        },
    }


def _forbidden_claim_locks() -> dict[str, bool]:
    return {
        "live": False,
        "broker": False,
        "order": False,
        "account": False,
        "paper": False,
        "model": False,
        "profit": False,
    }


def _first_viewport_cards() -> list[dict[str, Any]]:
    return [
        {
            "id": "selected_run_verdict",
            "title": "Selected run verdict",
            "value": "NO-GO",
            "status": "NO_GO",
            "label": "NO-GO / RESEARCH_ONLY",
        },
        {
            "id": "cost_baseline_delta_23bp",
            "title": "23bp cost/baseline delta",
            "value": None,
            "status": "NO_GO_MISSING_FRESH_COMPARISON",
            "label": "23bp vs ts_imb RULE baseline",
        },
        {
            "id": "drawdown",
            "title": "Drawdown",
            "value": None,
            "status": "MISSING",
            "label": "NO-GO until fresh drawdown evidence exists",
        },
        {
            "id": "trade_count_turnover",
            "title": "Trade count/turnover",
            "value": {"trade_count": 0, "turnover": None},
            "status": "STALE",
            "label": "RESEARCH_ONLY turnover evidence",
        },
        {
            "id": "job_progress",
            "title": "Job progress",
            "value": {"active_job_count": 0, "latest_status": "NOT_STARTED"},
            "status": "NOT_STARTED",
            "label": "Research intent only",
        },
        {
            "id": "d0_d9_gate_status",
            "title": "D0-D9 gate status",
            "value": "NO-GO",
            "status": "NO_GO",
            "label": "D0-D9 gate remains NO-GO",
        },
    ]


def load_trading_command_status() -> dict[str, Any]:
    jobs = _load_job_records()
    latest_status = jobs[-1]["status"] if jobs else "NOT_STARTED"
    cards = _first_viewport_cards()
    cards[4]["value"] = {"active_job_count": 0, "recorded_intent_count": len(jobs), "latest_status": latest_status}
    cards[4]["status"] = latest_status
    return {
        "surface": "trading_command_center",
        "api_status": "AVAILABLE",
        "mode": "RESEARCH_ONLY",
        "labels": list(RESEARCH_LABELS),
        "cost_assumption_bps": COST_ASSUMPTION_BPS,
        "claim_locks": _forbidden_claim_locks(),
        "status_locks": {
            "live": {"locked": False, "status": "API_UNAVAILABLE", "label": "NO-GO live trading disabled"},
            "broker": {"locked": False, "status": "API_UNAVAILABLE", "label": "NO-GO broker disabled"},
            "order": {"locked": False, "status": "API_UNAVAILABLE", "label": "NO-GO order routing disabled"},
            "account": {"locked": False, "status": "API_UNAVAILABLE", "label": "NO-GO account access disabled"},
            "paper": {"locked": False, "status": "API_UNAVAILABLE", "label": "NO-GO paper trading disabled"},
            "model": {"locked": False, "status": "API_UNAVAILABLE", "label": "NO-GO model build disabled"},
            "profit": {"locked": False, "status": "API_UNAVAILABLE", "label": "NO-GO profit readiness disabled"},
        },
        "controls": {
            "research_intent_record_allowed": True,
            "unsafe_trading_controls_allowed": False,
            "job_post_endpoint": "/api/trading-command/jobs",
            "allowed_workflows": sorted(_ALLOWED_WORKFLOWS),
        },
        "first_viewport": {
            "sections": ["status_locks", "workflow_process_map", "kpi_cards"],
            "cards": cards,
        },
        "evidence_health": {
            "missing": {"present": True, "status": "MISSING", "fields": ["fresh_drawdown", "d0_d9_gate_artifact"]},
            "stale": {"present": True, "status": "STALE", "fields": ["trade_count_turnover"]},
            "malformed": {"present": True, "status": "MALFORMED", "fields": ["optional_run_manifest"]},
            "no_go": {"present": True, "status": "NO_GO", "fields": ["selected_run_verdict"]},
        },
    }


def load_trading_command_workflow() -> dict[str, Any]:
    return {
        "workflow_id": "trading_command_research_only",
        "status": "NO-GO",
        "labels": list(RESEARCH_LABELS),
        "process_map": [
            {"step": "D0", "name": "Data/evidence discovery", "status": "STALE", "allowed": True},
            {"step": "D1", "name": "Rule baseline comparison", "status": "NO_GO", "allowed": True},
            {"step": "D2", "name": "23bp cost gate", "status": "NO_GO", "allowed": True},
            {"step": "D3", "name": "Drawdown review", "status": "MISSING", "allowed": True},
            {"step": "D4", "name": "Trade count/turnover review", "status": "STALE", "allowed": True},
            {"step": "D5", "name": "Negative controls", "status": "MISSING", "allowed": True},
            {"step": "D6", "name": "OOS split review", "status": "MISSING", "allowed": True},
            {"step": "D7", "name": "Audit/evidence manifest", "status": "MALFORMED", "allowed": True},
            {"step": "D8", "name": "Human research review", "status": "NOT_STARTED", "allowed": True},
            {"step": "D9", "name": "Trading readiness", "status": "NO_GO", "allowed": False},
        ],
        "forbidden_work": ["live", "broker", "order", "account", "paper", "model_build", "profit_claim"],
    }


def list_trading_command_runs() -> dict[str, Any]:
    return {
        "status": "NO-GO",
        "labels": list(RESEARCH_LABELS),
        "selected_run_id": DEFAULT_RUN_ID,
        "runs": [_selected_run_summary()],
    }


def load_trading_command_run_summary(run_id: str) -> dict[str, Any]:
    error = _validate_safe_id("run_id", run_id)
    if error:
        return {"status": "INVALID_RUN_ID", "error": error, "http_status": 400}
    if run_id != DEFAULT_RUN_ID:
        return {"status": "NOT_FOUND", "error": f"Unknown run_id: {run_id}", "http_status": 404}
    payload = _selected_run_summary()
    payload["http_status"] = 200
    return payload


def load_trading_command_evidence(run_id: str) -> dict[str, Any]:
    summary = load_trading_command_run_summary(run_id)
    if summary.get("http_status") != 200:
        return summary
    return {
        "run_id": run_id,
        "status": "NO_GO",
        "labels": list(RESEARCH_LABELS),
        "symbols": ["000250", "005930", "035420"],
        "artifacts": [
            {"kind": "summary", "status": "STALE", "path": None},
            {"kind": "d0_d9_gate", "status": "MISSING", "path": None},
            {"kind": "optional_manifest", "status": "MALFORMED", "path": None},
        ],
        "http_status": 200,
    }


def load_trading_command_audit(run_id: str | None = None) -> dict[str, Any]:
    if run_id is not None and run_id != DEFAULT_RUN_ID:
        return {"status": "NOT_FOUND", "error": f"Unknown run_id: {run_id}", "http_status": 404}
    return {
        "status": "RESEARCH_ONLY_AUDIT",
        "labels": list(RESEARCH_LABELS),
        "run_id": run_id or DEFAULT_RUN_ID,
        "events": [
            {
                "event": "guardrails_loaded",
                "status": "NO_GO",
                "details": "live/broker/order/account/paper/model/profit claims locked false",
            },
            *_load_audit_events(),
        ],
        "http_status": 200,
    }


def create_trading_command_job(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"status": "REJECTED", "reason": "JSON object required", "http_status": 400}

    workflow = payload.get("workflow") or payload.get("workflow_id")
    error = _validate_safe_id("workflow", workflow)
    if error:
        return {"status": "REJECTED", "reason": error, "http_status": 400}
    if workflow not in _ALLOWED_WORKFLOWS:
        return {"status": "REJECTED", "reason": "workflow is not allowlisted for research intent recording", "http_status": 400}

    config = payload.get("config", {})
    if config is None:
        config = {}
    if not isinstance(config, dict):
        return {"status": "REJECTED", "reason": "config must be an object", "http_status": 400}
    run_id = config.get("run_id", DEFAULT_RUN_ID)
    error = _validate_safe_id("run_id", run_id)
    if error:
        return {"status": "REJECTED", "reason": error, "http_status": 400}
    if _contains_path_traversal(payload):
        return {"status": "REJECTED", "reason": "path traversal and absolute paths are not allowed", "http_status": 400}
    blocked = _contains_blocked_token(payload)
    if blocked:
        return {"status": "REJECTED", "reason": f"unsafe research command token rejected: {blocked}", "http_status": 400}

    symbols = config.get("symbols", [])
    if symbols is not None and (not isinstance(symbols, list) or any(not isinstance(symbol, str) for symbol in symbols)):
        return {"status": "REJECTED", "reason": "symbols must be strings to preserve leading zeros", "http_status": 400}

    canonical_payload = {"workflow": workflow, "config": config, "requested_by": payload.get("requested_by", "api")}
    job_id = _job_id(canonical_payload)
    existing = _load_job_record(job_id)
    if existing is not None:
        result = _clone(existing)
        result["idempotent"] = True
        result["http_status"] = 200
        return result

    job = {
        "job_id": job_id,
        "status": "RECORDED_RESEARCH_INTENT",
        "mode": "RESEARCH_ONLY",
        "workflow": workflow,
        "config": _clone(config),
        "symbols": list(symbols or []),
        "run_id": run_id,
        "idempotent": False,
        "launched": False,
        "blocked_side_effects": ["live", "broker", "order", "account", "paper", "model_build", "profit_claim"],
        "labels": list(RESEARCH_LABELS),
        "audit": {"recorded": True, "status": "AUDITED_RESEARCH_INTENT"},
        "http_status": 202,
    }
    _write_job_record(job)
    _JOBS[job_id] = _clone(job)
    _append_audit_event({"event": "research_intent_recorded", "job_id": job_id, "workflow": workflow, "status": "AUDITED"})
    return job


def load_trading_command_job(job_id: str) -> dict[str, Any]:
    error = _validate_job_id(job_id)
    if error:
        return {"status": "INVALID_JOB_ID", "error": error, "http_status": 400}
    job = _load_job_record(job_id)
    if job is None:
        return {"status": "NOT_FOUND", "error": f"Unknown job_id: {job_id}", "http_status": 404}
    result = _clone(job)
    result["http_status"] = 200
    return result


def _reset_trading_command_state_for_tests() -> None:
    _JOBS.clear()
    _AUDIT_EVENTS.clear()
