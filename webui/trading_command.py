"""Research-only API helpers for the trading command center.

The command center is a backend-owned BFF surface.  It intentionally records
research intent only; it never starts live, broker, order, account, paper,
model-build, or profit-claim workflows.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

RESEARCH_LABELS = ["NO-GO", "RESEARCH_ONLY", "23bp", "ts_imb RULE baseline"]
COST_ASSUMPTION_BPS = 23
DEFAULT_RUN_ID = "research_ts_imb_rule_baseline_23bp"
DEFAULT_TRADING_COMMAND_AUDIT_ROOT = Path(__file__).resolve().parent / "rl_runs" / "trading_command_intents"
D9_RESEARCH_GATE_LABEL = "연구 검토 / NO-GO 게이트"
BLOCKED_CAPABILITY_STATE = "BLOCKED"
DEFAULT_SYMBOLS = ["000250", "005930", "035420"]
STAGE_NAMES = {
    "D0": "데이터·증거 발견",
    "D1": "룰 기준선 비교",
    "D2": "23bp 비용 게이트",
    "D3": "낙폭 검토",
    "D4": "거래 수·회전율 검토",
    "D5": "음성/셔플 통제",
    "D6": "OOS 분리 검토",
    "D7": "감사 증거 묶음",
    "D8": "사람 연구 검토",
    "D9": D9_RESEARCH_GATE_LABEL,
}
STAGE_STATUS = {
    "D0": "STALE",
    "D1": "NO_GO",
    "D2": "NO_GO",
    "D3": "MISSING",
    "D4": "STALE",
    "D5": "MISSING",
    "D6": "MISSING",
    "D7": "MALFORMED",
    "D8": "NOT_STARTED",
    "D9": "NO_GO",
}
STAGE_BLOCKERS = {
    "D0": "데이터/증거 발견 산출물이 오래되었습니다.",
    "D1": "ts_imb 룰 기준선 대비 신선한 비교가 필요합니다.",
    "D2": "23bp 비용 게이트가 통과되지 않았습니다.",
    "D3": "신선한 낙폭 증거가 없습니다.",
    "D4": "거래 수·회전율 증거가 오래되었습니다.",
    "D5": "음성/셔플 통제 산출물이 없습니다.",
    "D6": "OOS 분리 검토 산출물이 없습니다.",
    "D7": "감사 증거 묶음 형식이 올바르지 않습니다.",
    "D8": "사람 연구 검토가 아직 기록되지 않았습니다.",
    "D9": "연구 검토 기준상 NO-GO 게이트가 유지됩니다.",
}
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
    "trading_ready",
    "readiness",
)
_BLOCKED_KOREAN_PHRASES = (
    "실거래",
    "라이브 거래",
    "브로커",
    "증권사",
    "주문",
    "주문 전송",
    "계좌",
    "계좌 접근",
    "페이퍼",
    "페이퍼 트레이딩",
    "모델 빌드",
    "수익 " + "준비",
    "수익성 " + "준비",
    "수익 주장",
    "거래 " + "준비",
    "거래 " + "준비 판정",
)
_JOBS: dict[str, dict[str, Any]] = {}
_ARTIFACT_REQUIRED_FIELDS = [
    "artifact_id",
    "run_id",
    "series_source",
    "hash",
    "path",
    "timestamp",
    "freshness",
    "schema_status",
    "status",
    "blocker_reason",
    "source_stage",
    "source_run_id",
    "symbols",
]
_ACCEPTED_RESEARCH_EVIDENCE_SCHEMAS: dict[str, dict[str, Any]] = {
    "backend_series": {"source_stage": "D0", "row_count_required": True},
    "backend_table": {"source_stage": "D7", "row_count_required": True},
    "gate_table": {"source_stage": "D9", "row_count_required": True},
}
_ARTIFACT_FRESH_WINDOW = timedelta(days=7)
_AUDIT_EVENTS: list[dict[str, Any]] = []


def _clone(payload: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(payload)


def _canonical(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _payload_hash(payload: Any) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


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
def _read_json_any(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _artifact_allowed_roots() -> list[Path]:
    roots = [
        _audit_root(),
        Path(__file__).resolve().parents[1] / "artifacts" / "trading_command_center",
    ]
    return [root.resolve() for root in roots]


def _is_relative_safe_path(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    candidate = Path(value)
    if candidate.is_absolute():
        return False
    return ".." not in candidate.parts and not any(":" in part for part in candidate.parts)


def _is_under_allowed_root(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_artifact_rows(path: Path) -> int | None:
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = _read_json_any(path)
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            rows = data.get("rows")
            if isinstance(rows, list):
                return len(rows)
        return None
    if suffix in {".jsonl", ".ndjson"}:
        try:
            return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        except OSError:
            return None
    if suffix == ".csv":
        try:
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except OSError:
            return None
        if not lines:
            return 0
        return max(len(lines) - 1, 0)
    return None


def _parse_artifact_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fail_closed_artifact(
    artifact_id: str,
    kind: str,
    source_stage: str,
    status: str,
    blocker_reason: str,
    *,
    path: str | None = None,
    timestamp: str | None = None,
    symbols: list[str] | None = None,
    schema_status: str | None = None,
    series_source: str | None = None,
    source_run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "run_id": DEFAULT_RUN_ID,
        "kind": kind,
        "series_source": series_source or "BACKEND_OWNED",
        "hash": None,
        "path": path,
        "timestamp": timestamp,
        "freshness": status if status in {"STALE", "MISSING", "MALFORMED", "EMPTY"} else "UNKNOWN",
        "schema_status": schema_status or status,
        "status": status,
        "blocker_reason": blocker_reason,
        "source_stage": source_stage,
        "source_run_id": source_run_id or DEFAULT_RUN_ID,
        "symbols": list(symbols) if symbols is not None else list(DEFAULT_SYMBOLS),
    }


def _artifact_candidate_manifests(run_id: str) -> list[Path]:
    manifests: list[Path] = []
    for root in _artifact_allowed_roots():
        for directory in (root / run_id / "evidence", root / "evidence" / run_id):
            if directory.exists():
                manifests.extend(sorted(directory.glob("*.manifest.json")))
    return manifests


def _validate_discovered_artifact(manifest_path: Path, run_id: str) -> dict[str, Any]:
    roots = _artifact_allowed_roots()
    manifest = _read_json_any(manifest_path)
    default_id = manifest_path.stem
    if not isinstance(manifest, dict):
        return _fail_closed_artifact(default_id, "unknown", "D7", "MALFORMED", "증거 manifest JSON 형식이 올바르지 않습니다.", path=str(manifest_path.name))

    artifact_id = str(manifest.get("artifact_id") or default_id)
    kind = str(manifest.get("kind") or "unknown")
    source_stage = str(manifest.get("source_stage") or "D7")
    timestamp = manifest.get("timestamp") if isinstance(manifest.get("timestamp"), str) else None
    symbols = manifest.get("symbols") if isinstance(manifest.get("symbols"), list) else None

    if not _is_under_allowed_root(manifest_path, roots):
        return _fail_closed_artifact(artifact_id, kind, source_stage, "PATH_REJECTED", "증거 manifest가 허용된 생성 산출물 루트 밖에 있습니다.", path=str(manifest_path), timestamp=timestamp, symbols=symbols)

    required = {"artifact_id", "run_id", "kind", "series_source", "path", "timestamp", "source_stage", "source_run_id", "symbols"}
    missing = sorted(field for field in required if field not in manifest)
    schema = _ACCEPTED_RESEARCH_EVIDENCE_SCHEMAS.get(kind)
    if missing or schema is None:
        reason = "허용된 연구 증거 kind와 필수 manifest 필드를 통과하지 못했습니다."
        return _fail_closed_artifact(artifact_id, kind, source_stage, "MALFORMED", reason, path=manifest.get("path") if isinstance(manifest.get("path"), str) else None, timestamp=timestamp, symbols=symbols, schema_status="KIND_REJECTED" if schema is None else "MALFORMED")

    if manifest.get("run_id") != run_id or manifest.get("source_run_id") != run_id:
        return _fail_closed_artifact(artifact_id, kind, source_stage, "MALFORMED", "증거 run_id가 선택된 연구 실행과 일치하지 않습니다.", path=str(manifest.get("path")), timestamp=timestamp, symbols=symbols)

    if manifest.get("series_source") != "BACKEND_OWNED":
        return _fail_closed_artifact(artifact_id, kind, source_stage, "MALFORMED", "증거 series_source는 BACKEND_OWNED만 허용됩니다.", path=str(manifest.get("path")), timestamp=timestamp, symbols=symbols, series_source=str(manifest.get("series_source")))

    if source_stage != schema["source_stage"]:
        return _fail_closed_artifact(artifact_id, kind, source_stage, "MALFORMED", "증거 source_stage가 schema matrix와 일치하지 않습니다.", path=str(manifest.get("path")), timestamp=timestamp, symbols=symbols)

    if not isinstance(symbols, list) or not symbols or any(not isinstance(symbol, str) for symbol in symbols):
        return _fail_closed_artifact(artifact_id, kind, source_stage, "MALFORMED", "증거 symbols는 leading-zero 보존 문자열 목록이어야 합니다.", path=str(manifest.get("path")), timestamp=timestamp, symbols=[])

    artifact_path_value = manifest.get("path")
    if not _is_relative_safe_path(artifact_path_value):
        return _fail_closed_artifact(artifact_id, kind, source_stage, "PATH_REJECTED", "증거 path는 허용 루트 내부 상대 경로여야 합니다.", path=artifact_path_value if isinstance(artifact_path_value, str) else None, timestamp=timestamp, symbols=symbols)

    artifact_path = (manifest_path.parent / artifact_path_value).resolve()
    if not _is_under_allowed_root(artifact_path, roots):
        return _fail_closed_artifact(artifact_id, kind, source_stage, "PATH_REJECTED", "증거 path가 허용된 생성 산출물 루트 밖을 가리킵니다.", path=str(artifact_path_value), timestamp=timestamp, symbols=symbols)
    if not artifact_path.is_file():
        return _fail_closed_artifact(artifact_id, kind, source_stage, "MISSING", "증거 파일이 존재하지 않습니다.", path=str(artifact_path_value), timestamp=timestamp, symbols=symbols)

    row_count = _count_artifact_rows(artifact_path)
    if schema["row_count_required"] and (row_count is None or row_count <= 0):
        return _fail_closed_artifact(artifact_id, kind, source_stage, "EMPTY", "증거 파일에 검증 가능한 행이 없습니다.", path=str(artifact_path_value), timestamp=timestamp, symbols=symbols)

    parsed_timestamp = _parse_artifact_timestamp(timestamp)
    if parsed_timestamp is None:
        return _fail_closed_artifact(artifact_id, kind, source_stage, "MALFORMED", "증거 timestamp가 ISO-8601 형식이 아닙니다.", path=str(artifact_path_value), timestamp=timestamp, symbols=symbols)

    now = datetime.now(timezone.utc)
    if parsed_timestamp > now + timedelta(minutes=5) or now - parsed_timestamp > _ARTIFACT_FRESH_WINDOW:
        return _fail_closed_artifact(artifact_id, kind, source_stage, "STALE", "증거 timestamp가 신선도 창을 벗어났습니다.", path=str(artifact_path_value), timestamp=timestamp, symbols=symbols)

    hash_value = _sha256_file(artifact_path)
    expected_hash = manifest.get("hash")
    if isinstance(expected_hash, str) and expected_hash and expected_hash != hash_value:
        return _fail_closed_artifact(artifact_id, kind, source_stage, "MALFORMED", "증거 hash가 파일 내용과 일치하지 않습니다.", path=str(artifact_path_value), timestamp=timestamp, symbols=symbols)

    return _artifact_record(
        artifact_id,
        kind,
        source_stage,
        "FRESH",
        "",
        schema_status="VALID",
        path=str(artifact_path_value),
        hash_value=hash_value,
        timestamp=timestamp,
        run_id=run_id,
        series_source="BACKEND_OWNED",
        symbols=symbols,
        row_count=row_count,
    )


def _discovered_artifacts(run_id: str) -> list[dict[str, Any]]:
    return [_validate_discovered_artifact(path, run_id) for path in _artifact_candidate_manifests(run_id)]


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
        for phrase in _BLOCKED_KOREAN_PHRASES:
            if phrase in value:
                return phrase
        lower = value.lower().replace("_", "-")
        token_set = {token for token in re.split(r"[^a-z0-9]+", lower) if token}
        for blocked in _BLOCKED_TOKENS:
            blocked_tokens = [token for token in re.split(r"[^a-z0-9]+", blocked.lower().replace("_", "-")) if token]
            if blocked_tokens and all(token in token_set for token in blocked_tokens):
                return blocked
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
        "symbols": list(DEFAULT_SYMBOLS),
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


def _blocked_capability(label: str, reason: str) -> dict[str, Any]:
    return {
        "locked": False,
        "allowed": False,
        "enabled": False,
        "capability_state": BLOCKED_CAPABILITY_STATE,
        "status": "API_UNAVAILABLE",
        "label": label,
        "reason": reason,
    }


def _stage_artifact_ref(stage: str) -> str:
    return f"{DEFAULT_RUN_ID}:{stage.lower()}"


def _workflow_stage(stage: str) -> dict[str, Any]:
    return {
        "step": stage,
        "name": STAGE_NAMES[stage],
        "status": STAGE_STATUS[stage],
        "allowed": False,
        "enabled": False,
        "review_allowed": stage != "D9",
        "capability_state": BLOCKED_CAPABILITY_STATE,
        "blocker_reason": STAGE_BLOCKERS[stage],
        "source_run_id": DEFAULT_RUN_ID,
        "artifact_refs": [_stage_artifact_ref(stage)],
        "updated_at": None,
    }


def _artifact_record(
    artifact_id: str,
    kind: str,
    source_stage: str,
    status: str,
    blocker_reason: str,
    *,
    schema_status: str = "UNKNOWN",
    path: str | None = None,
    hash_value: str | None = None,
    timestamp: str | None = None,
    run_id: str = DEFAULT_RUN_ID,
    series_source: str = "BACKEND_OWNED",
    symbols: list[str] | None = None,
    row_count: int | None = None,
) -> dict[str, Any]:
    record = {
        "artifact_id": artifact_id,
        "run_id": run_id,
        "kind": kind,
        "series_source": series_source,
        "hash": hash_value,
        "path": path,
        "timestamp": timestamp,
        "freshness": status if status in {"FRESH", "STALE", "MISSING", "MALFORMED", "EMPTY", "UNKNOWN"} else "UNKNOWN",
        "schema_status": schema_status,
        "status": status,
        "blocker_reason": blocker_reason,
        "source_stage": source_stage,
        "source_run_id": run_id,
        "symbols": list(symbols) if symbols is not None else list(DEFAULT_SYMBOLS),
    }
    if row_count is not None:
        record["row_count"] = row_count
    return record


def _queue_summary(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for job in jobs:
        status = str(job.get("status", "UNKNOWN"))
        status_counts[status] = status_counts.get(status, 0) + 1
    latest = max(jobs, key=lambda job: str(job.get("recorded_at") or job.get("job_id") or "")) if jobs else None
    return {
        "mode": "RESEARCH_ONLY_QUEUE",
        "active_job_count": 0,
        "recorded_intent_count": len(jobs),
        "latest_status": latest.get("status") if latest else "NOT_STARTED",
        "latest_job_id": latest.get("job_id") if latest else None,
        "status_counts": status_counts,
        "allowed_workflows": sorted(_ALLOWED_WORKFLOWS),
        "unsafe_controls_allowed": False,
    }
def _public_job_record(job: dict[str, Any]) -> dict[str, Any]:
    public = _clone(job)
    config = public.get("config") if isinstance(public.get("config"), dict) else {}
    symbols = public.get("symbols")
    public["config_hash"] = _payload_hash(config)
    public["idempotency_key"] = str(public.get("job_id", ""))
    public["idempotent"] = bool(public.get("idempotent", False))
    public["active"] = False
    public["launched"] = False
    public["symbols"] = list(symbols) if isinstance(symbols, list) and all(isinstance(symbol, str) for symbol in symbols) else []
    audit = public.get("audit") if isinstance(public.get("audit"), dict) else {}
    public["audit_status"] = str(audit.get("status") or "AUDIT_NOT_RECORDED")
    public["unsafe_controls_allowed"] = False
    return public



def _first_viewport_cards() -> list[dict[str, Any]]:
    return [
        {
            "id": "selected_run_verdict",
            "title": "선택 산출물 판정",
            "value": "NO-GO",
            "status": "NO_GO",
            "label": "NO-GO / 연구 전용",
        },
        {
            "id": "cost_baseline_delta_23bp",
            "title": "23bp 비용·기준선 차이",
            "value": None,
            "status": "NO_GO_MISSING_FRESH_COMPARISON",
            "label": "23bp vs ts_imb 룰 기준선",
        },
        {
            "id": "drawdown",
            "title": "최대 낙폭",
            "value": None,
            "status": "MISSING",
            "label": "신선한 낙폭 증거가 없으면 차단",
        },
        {
            "id": "trade_count_turnover",
            "title": "거래 수·회전율",
            "value": {"trade_count": 0, "turnover": None},
            "status": "STALE",
            "label": "연구 전용 회전율 증거",
        },
        {
            "id": "job_progress",
            "title": "연구 의도 진행",
            "value": {"active_job_count": 0, "latest_status": "NOT_STARTED"},
            "status": "NOT_STARTED",
            "label": "연구 의도 기록만",
        },
        {
            "id": "d0_d9_gate_status",
            "title": "D0-D9 증거 게이트",
            "value": "NO-GO",
            "status": "NO_GO",
            "label": "D0-D9 게이트 NO-GO 유지",
        },
    ]


def load_trading_command_status() -> dict[str, Any]:
    jobs = _load_job_records()
    queue_summary = _queue_summary(jobs)
    cards = _first_viewport_cards()
    cards[4]["value"] = {
        "active_job_count": queue_summary["active_job_count"],
        "recorded_intent_count": queue_summary["recorded_intent_count"],
        "latest_status": queue_summary["latest_status"],
    }
    cards[4]["status"] = str(queue_summary["latest_status"])
    return {
        "surface": "trading_command_center",
        "api_status": "AVAILABLE",
        "mode": "RESEARCH_ONLY",
        "labels": list(RESEARCH_LABELS),
        "cost_assumption_bps": COST_ASSUMPTION_BPS,
        "claim_locks": _forbidden_claim_locks(),
        "status_locks": {
            "live": _blocked_capability("NO-GO · 실거래 경로 잠금", "실거래 기능은 연구 전용 대시보드에서 차단됩니다."),
            "broker": _blocked_capability("NO-GO · 브로커 연결 잠금", "브로커 연결 기능은 연구 전용 대시보드에서 차단됩니다."),
            "order": _blocked_capability("NO-GO · 주문 전송 경로 잠금", "주문 전송 기능은 연구 전용 대시보드에서 차단됩니다."),
            "account": _blocked_capability("NO-GO · 계좌 접근 잠금", "계좌 접근 기능은 연구 전용 대시보드에서 차단됩니다."),
            "paper": _blocked_capability("NO-GO · 페이퍼 트레이딩 잠금", "페이퍼 트레이딩 기능은 연구 전용 대시보드에서 차단됩니다."),
            "model": _blocked_capability("NO-GO · 모델 빌드 잠금", "모델 빌드 기능은 연구 전용 대시보드에서 차단됩니다."),
            "profit": _blocked_capability("NO-GO · 수익 주장 경로 잠금", "수익 주장은 연구 전용 대시보드에서 차단됩니다."),
        },
        "controls": {
            "research_intent_record_allowed": True,
            "unsafe_trading_controls_allowed": False,
            "job_post_endpoint": "/api/trading-command/jobs",
            "allowed_workflows": sorted(_ALLOWED_WORKFLOWS),
        },
        "queue_summary": queue_summary,
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
        "artifact_manifest_schema": {
            "required_fields": list(_ARTIFACT_REQUIRED_FIELDS),
            "row_count_required_when_applicable": True,
            "accepted_research_evidence_kinds": _clone(_ACCEPTED_RESEARCH_EVIDENCE_SCHEMAS),
            "symbols_are_strings": True,
            "capability_state": BLOCKED_CAPABILITY_STATE,
        },
    }


def load_trading_command_workflow() -> dict[str, Any]:
    return {
        "workflow_id": "trading_command_research_only",
        "status": "NO-GO",
        "labels": list(RESEARCH_LABELS),
        "process_map": [_workflow_stage(f"D{index}") for index in range(10)],
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
    artifacts = [
        _artifact_record(
            "summary-stale",
            "summary",
            "D0",
            "STALE",
            "요약 증거가 오래되어 신선한 비교로 사용할 수 없습니다.",
            schema_status="VALID",
        ),
        _artifact_record(
            "d0-d9-gate-missing",
            "d0_d9_gate",
            "D9",
            "MISSING",
            "D0-D9 게이트 산출물이 없습니다.",
            schema_status="MISSING",
        ),
        _artifact_record(
            "optional-manifest-malformed",
            "optional_manifest",
            "D7",
            "MALFORMED",
            "선택 산출물 manifest 형식이 올바르지 않습니다.",
            schema_status="MALFORMED",
        ),
        _artifact_record(
            "fresh-drawdown-missing",
            "drawdown",
            "D3",
            "MISSING",
            "신선한 낙폭 증거가 없습니다.",
            schema_status="MISSING",
        ),
        *_discovered_artifacts(run_id),
    ]
    return {
        "run_id": run_id,
        "status": "NO_GO",
        "labels": list(RESEARCH_LABELS),
        "symbols": list(DEFAULT_SYMBOLS),
        "artifact_schema": {
            "required_fields": list(_ARTIFACT_REQUIRED_FIELDS),
            "row_count_required_when_applicable": True,
            "accepted_research_evidence_kinds": _clone(_ACCEPTED_RESEARCH_EVIDENCE_SCHEMAS),
            "allowed_roots": [str(root) for root in _artifact_allowed_roots()],
        },
        "artifacts": artifacts,
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
def _drilldown_tab(tab_id: str, title: str, description: str, source: str, payload: Any) -> dict[str, Any]:
    rows = payload if isinstance(payload, list) else [payload]
    return {
        "id": tab_id,
        "title": title,
        "description": description,
        "source": source,
        "preview_hash": _payload_hash(payload),
        "path_safe": True,
        "hash_backed": True,
        "row_count": len(rows),
        "rows": rows,
        "raw_json": payload,
    }


def load_trading_command_drilldown(run_id: str) -> dict[str, Any]:
    summary = load_trading_command_run_summary(run_id)
    if summary.get("http_status") != 200:
        return summary

    evidence = load_trading_command_evidence(run_id)
    audit = load_trading_command_audit(run_id)
    jobs = list_trading_command_jobs()
    queue_summary = jobs["queue_summary"]
    job_rows = jobs["jobs"]

    manifest_rows = [
        {
            "artifact_id": artifact["artifact_id"],
            "source_stage": artifact["source_stage"],
            "source_run_id": artifact["source_run_id"],
            "status": artifact["status"],
            "freshness": artifact["freshness"],
            "schema_status": artifact["schema_status"],
            "hash": artifact["hash"],
            "path": artifact["path"],
            "timestamp": artifact["timestamp"],
            "row_count": artifact.get("row_count", 0),
            "blocker_reason": artifact["blocker_reason"],
            "symbols": artifact["symbols"],
            "path_safe": artifact["path"] is None or _is_relative_safe_path(artifact["path"]),
            "hash_backed": bool(artifact["hash"]),
        }
        for artifact in evidence["artifacts"]
    ]
    return {
        "run_id": run_id,
        "status": "NO_GO",
        "labels": list(RESEARCH_LABELS),
        "safe_preview_policy": {
            "max_preview_chars": 1400,
            "path_safe": True,
            "hash_backed": True,
            "allowed_roots": [str(root) for root in _artifact_allowed_roots()],
            "active_job_count": queue_summary["active_job_count"],
            "unsafe_controls_allowed": False,
        },
        "queue_summary": queue_summary,
        "tabs": [
            _drilldown_tab("manifest", "증거 manifest", "hash/path/timestamp/freshness/schema/blocker를 포함한 안전 manifest", "backend:load_trading_command_evidence", manifest_rows),
            _drilldown_tab("run_summary", "run 요약", "선택 run의 RULE baseline, 23bp, NO-GO 요약", "backend:load_trading_command_run_summary", summary),
            _drilldown_tab("audit_timeline", "감사 타임라인", "guardrail 및 연구 의도 기록 감사 이벤트", "backend:load_trading_command_audit", audit["events"]),
            _drilldown_tab("research_intents", "연구 의도 기록", "recorded-only job, idempotency, symbols, config_hash, audit_status, active count zero", "backend:list_trading_command_jobs", job_rows),
            _drilldown_tab("raw_json", "원본 JSON 일부", "해시가 부여된 읽기 전용 API payload 묶음", "backend:drilldown_payload", {"summary": summary, "evidence": evidence, "audit": audit, "jobs": jobs}),
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
        result = _public_job_record(existing)
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
        "config_hash": _payload_hash(config),
        "audit_status": "AUDITED_RESEARCH_INTENT",
        "http_status": 202,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_job_record(job)
    _JOBS[job_id] = _clone(job)
    _append_audit_event({"event": "research_intent_recorded", "job_id": job_id, "workflow": workflow, "status": "AUDITED", "recorded_at": job["recorded_at"]})
    return _public_job_record(job) | {"http_status": 202}


def list_trading_command_jobs() -> dict[str, Any]:
    jobs = _load_job_records()
    return {
        "status": "RESEARCH_ONLY_QUEUE",
        "labels": list(RESEARCH_LABELS),
        "queue_summary": _queue_summary(jobs),
        "jobs": [_public_job_record(job) for job in jobs],
        "http_status": 200,
    }


def load_trading_command_job(job_id: str) -> dict[str, Any]:
    error = _validate_job_id(job_id)
    if error:
        return {"status": "INVALID_JOB_ID", "error": error, "http_status": 400}
    job = _load_job_record(job_id)
    if job is None:
        return {"status": "NOT_FOUND", "error": f"Unknown job_id: {job_id}", "http_status": 404}
    result = _public_job_record(job)
    result["http_status"] = 200
    return result


def _reset_trading_command_state_for_tests() -> None:
    _JOBS.clear()
    _AUDIT_EVENTS.clear()
