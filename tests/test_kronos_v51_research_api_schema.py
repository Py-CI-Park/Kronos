from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "schemas" / "kronos_v51_research_api.v1.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)
SHA = "a" * 64
SOURCE_DB_SHA = "b" * 64
PROTOCOL_SHA = "c" * 64
ZERO_SHA = "0" * 64
UTC = "2026-07-18T00:00:00Z"

ROUTES = {
    "SOURCE_COVERAGE": "/api/daily-close-v51/source-coverage",
    "CAUSAL_PANEL": "/api/daily-close-v51/causal-panel",
    "ACCOUNTING": "/api/daily-close-v51/accounting",
    "EVALUATOR": "/api/daily-close-v51/evaluator",
    "BENCHMARK_OVERLAY": "/api/daily-close-v51/benchmark-overlay",
    "REPORTS": "/api/daily-close-v51/reports",
    "REPORT_READ": "/api/daily-close-v51/reports/{report_id}",
}

LOCKS = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}

CLAIMS = {
    "official_close_claim": False,
    "paper_forward_claim": False,
    "live_trading_claim": False,
    "broker_integration_claim": False,
    "profitability_claim": False,
    "go_readiness_claim": False,
}

ACCOUNTING_CONTRACT = {
    "initial_capital_krw": 60_000_000,
    "slot_count": 10,
    "slot_budget_krw": 5_000_000,
    "max_invested_krw": 50_000_000,
    "reserve_cash_krw": 10_000_000,
    "reserve_cash_display_percent": "16.6667%",
    "max_target_investment_display_percent": "83.3333%",
    "shorting_allowed": False,
    "leverage_allowed": False,
    "duplicate_symbol_slots_allowed": False,
}

COST_SCHEDULE = {
    "primary": {"internal_id": "base_23bp", "round_trip_cost_bp": 23, "display_percent": "0.23%"},
    "zero_cost_control": {"internal_id": "zero_control_0bp", "round_trip_cost_bp": 0, "display_percent": "0.00%"},
    "stress_control": {"internal_id": "stress_46bp", "round_trip_cost_bp": 46, "display_percent": "0.46%"},
}

HORIZON = {
    "primary_horizon": "H1",
    "validation_horizons": ["H3", "H5"],
    "label_columns": [
        "future_return_h1_1520_proxy",
        "future_return_h3_1520_proxy",
        "future_return_h5_1520_proxy",
    ],
}

SOURCE_POLICY = {
    "daily_1520_source_schema": "kronos_daily_1520_source.v1",
    "causal_panel_schema": "kronos_daily_v51_causal_panel.v1",
    "causal_cutoff_kst": "15:20:00",
    "price_basis": "15:20_bar_close_proxy",
    "official_close": False,
    "nearest_fallback_allowed": False,
    "full_day_daily_ohlcv_allowed": False,
    "price_volume_amount_approximation_allowed": False,
    "pykrx_offline_only": True,
    "naver_fallback_allowed": False,
    "network_required": False,
}

OVERLAY_POLICY = {
    "allowed_index_provider": "PYKRX",
    "offline_artifact_required": True,
    "naver_fallback_allowed": False,
    "forbidden_provider": "NAVER",
    "missing_index_state": "BLOCKED_INDEX_SERIES_SOURCE",
}

STABLE_ARTIFACT_IDS = {
    "source_coverage": "daily-close-v51-source-coverage",
    "causal_panel": "daily-close-v51-causal-panel",
    "accounting": "daily-close-v51-accounting",
    "evaluator": "daily-close-v51-evaluator",
    "benchmark_overlay": "daily-close-v51-benchmark-overlay",
}

ARTIFACT_KIND_BY_ROUTE = {
    "SOURCE_COVERAGE": "source_coverage",
    "CAUSAL_PANEL": "causal_panel",
    "ACCOUNTING": "accounting",
    "EVALUATOR": "evaluator",
    "BENCHMARK_OVERLAY": "benchmark_overlay",
}

PAYLOAD_NAME_BY_ROUTE = {
    "SOURCE_COVERAGE": "source_coverage",
    "CAUSAL_PANEL": "causal_panel",
    "ACCOUNTING": "accounting",
    "EVALUATOR": "evaluator",
    "BENCHMARK_OVERLAY": "benchmark_overlay",
}

ERROR_STATUS_BY_CODE = {
    "BAD_REQUEST": 400,
    "CONFLICT": 409,
    "VALIDATION_ERROR": 413,
    "METHOD_NOT_ALLOWED": 405,
    "INTERNAL_ERROR": 503,
}


def protocol(route_id: str) -> dict[str, Any]:
    return {
        "schema_version": "kronos_v51_research_api.v1",
        "api_version": "v5.1",
        "method": "GET",
        "read_only": True,
        "route_id": route_id,
        "route_path": ROUTES[route_id],
        "causal_cutoff_kst": "15:20:00",
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
        "accounting": copy.deepcopy(ACCOUNTING_CONTRACT),
        "cost_schedule": copy.deepcopy(COST_SCHEDULE),
        "horizon": copy.deepcopy(HORIZON),
        "source_policy": copy.deepcopy(SOURCE_POLICY),
        "overlay_policy": copy.deepcopy(OVERLAY_POLICY),
    }


def source(artifact_id: str) -> dict[str, Any]:
    return {
        "source_protocol": "kronos_daily_1520_source.v1",
        "source_artifact_id": artifact_id,
        "source_sha256": SHA,
        "source_db_sha256": SOURCE_DB_SHA,
        "generated_at": UTC,
        "causal_cutoff_kst": "15:20:00",
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
    }


def run() -> dict[str, Any]:
    return {
        "run_id": "run-1",
        "run_revision": 1,
        "run_artifact_id": "run-artifact",
        "source_sha256": SHA,
        "protocol_sha256": PROTOCOL_SHA,
        "stable_artifact_ids": copy.deepcopy(STABLE_ARTIFACT_IDS),
    }


def artifact(kind: str, artifact_id: str) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "artifact_kind": kind,
        "media_type": "application/json; charset=utf-8",
        "byte_length": 2,
        "sha256": SHA,
        "stable_id": True,
    }


def source_coverage() -> dict[str, Any]:
    return {
        "coverage_status": "READY",
        "exact_1520_row_count": 1739,
        "symbol_count": 1,
        "session_count": 1739,
        "first_valid_date": "2019-05-09",
        "last_valid_date": "2026-06-12",
        "sample_symbol": "000250",
        "sample_timestamp_yyyymmddhhmm": "202606121520",
        "volume_to_1520_status": "NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY",
        "amount_to_1520_status": "NOT_AVAILABLE_5MIN_DB_HAS_NO_AMOUNT_COLUMN_DO_NOT_APPROXIMATE_PRICE_X_VOLUME",
        "missing_policy": "MISSING_1520_BAR_BLOCKS_ROW_NO_NEAREST_FALLBACK",
    }


def causal_panel() -> dict[str, Any]:
    return {
        "panel_schema": "kronos_daily_v51_causal_panel.v1",
        "row_count": 1,
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
        "primary_horizon": "H1",
        "validation_horizons": ["H3", "H5"],
        "label_columns": [
            "future_return_h1_1520_proxy",
            "future_return_h3_1520_proxy",
            "future_return_h5_1520_proxy",
        ],
        "rows_preview": [
            {
                "symbol": "000250",
                "session_date": "2026-06-12",
                "timestamp_kst": "2026-06-12T15:20:00+09:00",
                "price_basis": "15:20_bar_close_proxy",
                "official_close": False,
                "entry_status": "READY",
                "h1_status": "READY",
                "h3_status": "READY",
                "h5_status": "READY",
            }
        ],
    }


def accounting_summary() -> dict[str, Any]:
    return {
        "accounting_status": "READY",
        "contract": copy.deepcopy(ACCOUNTING_CONTRACT),
        "cost_schedule": copy.deepcopy(COST_SCHEDULE),
        "economic_nav_krw": 60_000_000,
        "cash_reserve_krw": 10_000_000,
        "slots_used": 0,
        "max_slots": 10,
        "internal_cost_id": "base_23bp",
        "display_cost_percent": "0.23%",
    }


def evaluator() -> dict[str, Any]:
    return {
        "evaluation_status": "BLOCKED",
        "primary_horizon": "H1",
        "validation_horizons": ["H3", "H5"],
        "cost_schedule": copy.deepcopy(COST_SCHEDULE),
        "split_statuses": {"train": "READY", "validation": "BLOCKED", "test": "BLOCKED"},
        "metrics": [
            {
                "metric_id": "cumulative_return",
                "split": "validation",
                "horizon": "H1",
                "internal_cost_id": "base_23bp",
                "display_cost_percent": "0.23%",
                "value": 0.0,
                "display_percent": "0.00%",
            },
            {
                "metric_id": "turnover",
                "split": "validation",
                "horizon": "H1",
                "internal_cost_id": "zero_control_0bp",
                "display_cost_percent": "0.00%",
                "value": 0.0,
                "display_percent": "0.00%",
            },
        ],
    }


def benchmark_overlay() -> dict[str, Any]:
    return {
        "overlay_status": "BLOCKED",
        "provider_policy": copy.deepcopy(OVERLAY_POLICY),
        "common_start_index": 100,
        "series": [
            {
                "series_id": "KOSPI",
                "status": "BLOCKED",
                "source_state": "BLOCKED_INDEX_SERIES_SOURCE",
                "provider": None,
                "naver_used": False,
                "index_100": None,
                "cumulative_return_display_percent": None,
            },
            {
                "series_id": "KOSDAQ",
                "status": "BLOCKED",
                "source_state": "BLOCKED_INDEX_SERIES_SOURCE",
                "provider": None,
                "naver_used": False,
                "index_100": None,
                "cumulative_return_display_percent": None,
            },
            {
                "series_id": "RL_PORTFOLIO",
                "status": "BLOCKED",
                "source_state": "BLOCKED_INDEX_SERIES_SOURCE",
                "provider": None,
                "naver_used": False,
                "index_100": None,
                "cumulative_return_display_percent": None,
            },
        ],
    }


def ready_benchmark_overlay_payload() -> dict[str, Any]:
    body = benchmark_overlay()
    body["overlay_status"] = "READY"
    providers = ["PYKRX", "PYKRX", None]
    index_values = [101.0, 102.5, 105.0]
    display_values = ["1.00%", "2.50%", "5.00%"]
    for index, series in enumerate(body["series"]):
        series["status"] = "READY"
        series["source_state"] = "READY"
        series["provider"] = providers[index]
        series["index_100"] = index_values[index]
        series["cumulative_return_display_percent"] = display_values[index]
    return body


def ready_benchmark_overlay_root() -> dict[str, Any]:
    payload = research_payload("BENCHMARK_OVERLAY", ready_benchmark_overlay_payload())
    payload["status"] = "READY"
    payload["status_reason"] = "READY"
    return payload

def research_payload(route_id: str, body: dict[str, Any]) -> dict[str, Any]:
    status = "BLOCKED" if route_id in {"BENCHMARK_OVERLAY", "EVALUATOR"} else "READY"
    reason = "BLOCKED_INDEX_SERIES_SOURCE" if route_id == "BENCHMARK_OVERLAY" else "BLOCKED_ARTIFACT_UNAVAILABLE" if route_id == "EVALUATOR" else "READY"
    payload_name = PAYLOAD_NAME_BY_ROUTE[route_id]
    return {
        "route_id": route_id,
        "status": status,
        "status_reason": reason,
        "protocol": protocol(route_id),
        "source": source(STABLE_ARTIFACT_IDS[payload_name]),
        "run": run(),
        "artifact": artifact(ARTIFACT_KIND_BY_ROUTE[route_id], STABLE_ARTIFACT_IDS[payload_name]),
        "locks": copy.deepcopy(LOCKS),
        "claims": copy.deepcopy(CLAIMS),
        payload_name: body,
    }


def report_summary() -> dict[str, Any]:
    return {
        "report_id": "report-2026-07-17",
        "title": "V5.1 research requirements",
        "relative_path": "docs/kronos_daily_close_rl_v5_1_requirements_2026-07-17.md",
        "root_id": "docs",
        "media_type": "text/markdown; charset=utf-8",
        "byte_length": 1,
        "sha256": SHA,
        "updated_at": UTC,
        "source_protocol": "kronos_v51_report_catalog.v1",
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
    }


def report_source() -> dict[str, Any]:
    return {
        "source_protocol": "kronos_v51_report_catalog.v1",
        "catalog_artifact_id": "report-catalog",
        "catalog_sha256": SHA,
        "generated_at": UTC,
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
    }


def report_list_payload() -> dict[str, Any]:
    return {
        "route_id": "REPORTS",
        "status": "READY",
        "status_reason": "READY",
        "protocol": protocol("REPORTS"),
        "source": report_source(),
        "locks": copy.deepcopy(LOCKS),
        "claims": copy.deepcopy(CLAIMS),
        "reports": [report_summary()],
    }


def report_read_payload() -> dict[str, Any]:
    return {
        "route_id": "REPORT_READ",
        "status": "READY",
        "status_reason": "READY",
        "protocol": protocol("REPORT_READ"),
        "source": report_source(),
        "locks": copy.deepcopy(LOCKS),
        "claims": copy.deepcopy(CLAIMS),
        "report": report_summary(),
        "content": {"raw_text": "# 연구 보고서\n", "safe_html": '<article data-kronos-report-html="escaped-pre"><pre># 연구 보고서\n</pre></article>'},
    }

def error_source(route_id: str) -> dict[str, Any]:
    if route_id in {"REPORTS", "REPORT_READ"}:
        return report_source()
    payload_name = PAYLOAD_NAME_BY_ROUTE[route_id]
    return source(STABLE_ARTIFACT_IDS[payload_name])


def error_payload(route_id: str, code: str) -> dict[str, Any]:
    return {
        "route_id": route_id,
        "status": "ERROR",
        "protocol": protocol(route_id),
        "source": error_source(route_id),
        "locks": copy.deepcopy(LOCKS),
        "claims": copy.deepcopy(CLAIMS),
        "error": {"code": code, "message": f"{code} envelope", "status_code": ERROR_STATUS_BY_CODE[code]},
    }


def payload_for(route_id: str) -> dict[str, Any]:
    return {
        "SOURCE_COVERAGE": lambda: research_payload("SOURCE_COVERAGE", source_coverage()),
        "CAUSAL_PANEL": lambda: research_payload("CAUSAL_PANEL", causal_panel()),
        "ACCOUNTING": lambda: research_payload("ACCOUNTING", accounting_summary()),
        "EVALUATOR": lambda: research_payload("EVALUATOR", evaluator()),
        "BENCHMARK_OVERLAY": lambda: research_payload("BENCHMARK_OVERLAY", benchmark_overlay()),
        "REPORTS": report_list_payload,
        "REPORT_READ": report_read_payload,
    }[route_id]()


def reject_mutation(payload: dict[str, Any], path: tuple[Any, ...], value: Any = None, *, delete: bool = False) -> None:
    mutated = copy.deepcopy(payload)
    target: Any = mutated
    for key in path[:-1]:
        target = target[key]
    if delete:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    with pytest.raises(ValidationError):
        VALIDATOR.validate(mutated)

def validate_contract(payload: dict[str, Any]) -> None:
    VALIDATOR.validate(payload)
    route_id = payload.get("route_id")
    if payload.get("status") == "ERROR":
        assert payload["protocol"]["route_id"] == route_id
        assert payload["protocol"]["route_path"] == ROUTES[route_id]
        assert payload["locks"] == LOCKS
        assert payload["claims"] == CLAIMS
        assert payload["error"]["status_code"] == ERROR_STATUS_BY_CODE[payload["error"]["code"]]
        return
    if route_id not in PAYLOAD_NAME_BY_ROUTE:
        return
    payload_name = PAYLOAD_NAME_BY_ROUTE[str(route_id)]
    assert payload["source"]["source_sha256"] == payload["run"]["source_sha256"]
    assert payload["source"]["source_artifact_id"] == payload["run"]["stable_artifact_ids"][payload_name]
    assert payload["artifact"]["artifact_id"] == payload["run"]["stable_artifact_ids"][payload_name]


def reject_contract_mutation(payload: dict[str, Any], path: tuple[Any, ...], value: Any = None, *, delete: bool = False) -> None:
    mutated = copy.deepcopy(payload)
    target: Any = mutated
    for key in path[:-1]:
        target = target[key]
    if delete:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    with pytest.raises((ValidationError, AssertionError)):
        validate_contract(mutated)


def test_schema_is_closed_and_exports_exact_route_descriptors() -> None:
    Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["$id"] == "https://kronos.local/schemas/kronos_v51_research_api.v1.schema.json"
    descriptors = SCHEMA["$defs"]["routeDescriptors"]["const"]
    assert descriptors == {
        "SOURCE_COVERAGE": {"method": "GET", "path": ROUTES["SOURCE_COVERAGE"], "root": "sourceCoverageRoot", "path_bindings": [], "query": ["run_id", "artifact_id", "revision"]},
        "CAUSAL_PANEL": {"method": "GET", "path": ROUTES["CAUSAL_PANEL"], "root": "causalPanelRoot", "path_bindings": [], "query": ["run_id", "artifact_id", "revision"]},
        "ACCOUNTING": {"method": "GET", "path": ROUTES["ACCOUNTING"], "root": "accountingRoot", "path_bindings": [], "query": ["run_id", "artifact_id", "revision"]},
        "EVALUATOR": {"method": "GET", "path": ROUTES["EVALUATOR"], "root": "evaluatorRoot", "path_bindings": [], "query": ["run_id", "artifact_id", "revision"]},
        "BENCHMARK_OVERLAY": {"method": "GET", "path": ROUTES["BENCHMARK_OVERLAY"], "root": "benchmarkOverlayRoot", "path_bindings": [], "query": ["run_id", "artifact_id", "revision"]},
        "REPORTS": {"method": "GET", "path": ROUTES["REPORTS"], "root": "reportListRoot", "path_bindings": [], "query": []},
        "REPORT_READ": {"method": "GET", "path": ROUTES["REPORT_READ"], "root": "reportReadRoot", "path_bindings": ["report_id"], "query": []},
    }
    assert SCHEMA["$defs"]["falseResearchLocks"]["required"] == list(LOCKS)
    assert SCHEMA["$defs"]["noClaimFlags"]["required"] == list(CLAIMS)
    assert {"$ref": "#/$defs/errorRoot"} in SCHEMA["oneOf"]
    assert SCHEMA["$defs"]["errorBody"]["properties"]["message"]["maxLength"] == 240
    for route_id, descriptor in descriptors.items():
        assert descriptor["method"] == "GET"
        assert descriptor["path"].startswith("/api/daily-close-v51/")
        assert not descriptor["path"].startswith("/api/v5/rl/")


@pytest.mark.parametrize("route_id", list(ROUTES))
def test_all_research_and_report_payloads_accept_closed_goldens(route_id: str) -> None:
    payload = payload_for(route_id)
    validate_contract(payload)
    assert json.loads(json.dumps(payload, ensure_ascii=False))["route_id"] == route_id

@pytest.mark.parametrize("route_id", list(ROUTES))
@pytest.mark.parametrize("code,status_code", list(ERROR_STATUS_BY_CODE.items()))
def test_error_envelopes_accept_route_aware_backend_roots(route_id: str, code: str, status_code: int) -> None:
    payload = error_payload(route_id, code)
    validate_contract(payload)
    assert payload["status"] == "ERROR"
    assert payload["error"]["status_code"] == status_code


def test_error_envelopes_reject_open_mismatched_or_unbounded_roots() -> None:
    payload = error_payload("SOURCE_COVERAGE", "BAD_REQUEST")
    reject_mutation(payload, ("unexpected",), True)
    reject_mutation(payload, ("status",), "BLOCKED")
    reject_mutation(payload, ("status_reason",), "READY")
    reject_mutation(payload, ("protocol", "route_path"), ROUTES["CAUSAL_PANEL"])
    reject_mutation(payload, ("source", "source_artifact_id"), STABLE_ARTIFACT_IDS["causal_panel"])
    reject_mutation(payload, ("locks", "promotion_allowed"), True)
    reject_mutation(payload, ("claims", "profitability_claim"), True)
    reject_mutation(payload, ("error", "message"), "x" * 241)
    reject_mutation(payload, ("error", "status_code"), 405)
    reject_mutation(payload, ("error", "status_code"), 409)
    reject_mutation(payload, ("error", "code"), "CONFLICT")

    report_payload = error_payload("REPORTS", "INTERNAL_ERROR")
    reject_mutation(report_payload, ("source", "source_protocol"), "kronos_daily_1520_source.v1")

def test_schema_rejects_preview_and_report_path_upper_boundary_overflows() -> None:
    panel_payload = payload_for("CAUSAL_PANEL")
    preview_row = panel_payload["causal_panel"]["rows_preview"][0]
    twenty_one_preview_rows = [copy.deepcopy(preview_row) for _ in range(21)]
    assert len(twenty_one_preview_rows) == 21
    reject_mutation(panel_payload, ("causal_panel", "rows_preview"), twenty_one_preview_rows)

    safe_lowercase_path = f"{'a' * 510}.md"
    assert len(safe_lowercase_path) == 513
    assert safe_lowercase_path == safe_lowercase_path.lower()
    reject_mutation(payload_for("REPORTS"), ("reports", 0, "relative_path"), safe_lowercase_path)


def test_schema_rejects_open_payloads_identity_mismatch_locks_and_claims() -> None:
    payload = payload_for("SOURCE_COVERAGE")
    reject_mutation(payload, ("unexpected",), True)
    reject_mutation(payload, ("protocol", "route_id"), "CAUSAL_PANEL")
    reject_mutation(payload, ("protocol", "route_path"), ROUTES["CAUSAL_PANEL"])
    reject_mutation(payload, ("artifact", "artifact_kind"), "causal_panel")
    reject_mutation(payload, ("locks", "promotion_allowed"), True)
    reject_mutation(payload, ("locks", "unexpected"), False)
    reject_mutation(payload, ("claims", "profitability_claim"), True)
    reject_mutation(payload, ("claims", "broker_integration_claim"), True)
    reject_mutation(payload, ("run", "stable_artifact_ids", "source_coverage"), "../source")
    reject_mutation(payload, ("run", "stable_artifact_ids", "causal_panel"), None)
    reject_mutation(payload, ("source", "official_close"), True)
    reject_mutation(payload, ("source", "source_artifact_id"), STABLE_ARTIFACT_IDS["causal_panel"])
    reject_contract_mutation(payload, ("source", "source_sha256"), "d" * 64)
    reject_contract_mutation(payload, ("run", "source_sha256"), "d" * 64)
    reject_contract_mutation(payload, ("artifact", "artifact_id"), "other-source-coverage")
    reject_mutation(payload, ("artifact", "byte_length"), 9_007_199_254_740_992)


def test_ready_research_payloads_reject_sentinel_identity_values() -> None:
    payload = payload_for("SOURCE_COVERAGE")
    reject_mutation(payload, ("source", "source_sha256"), ZERO_SHA)
    reject_mutation(payload, ("source", "source_db_sha256"), ZERO_SHA)
    reject_mutation(payload, ("source", "generated_at"), "1970-01-01T00:00:00Z")
    reject_mutation(payload, ("run", "source_sha256"), ZERO_SHA)
    reject_mutation(payload, ("run", "protocol_sha256"), ZERO_SHA)
    reject_mutation(payload, ("artifact", "sha256"), ZERO_SHA)

    blocked_payload = payload_for("EVALUATOR")
    blocked_payload["source"]["source_sha256"] = ZERO_SHA
    blocked_payload["source"]["source_db_sha256"] = ZERO_SHA
    blocked_payload["source"]["generated_at"] = "1970-01-01T00:00:00Z"
    blocked_payload["run"]["source_sha256"] = ZERO_SHA
    blocked_payload["artifact"]["sha256"] = ZERO_SHA
    validate_contract(blocked_payload)

def test_status_reason_and_body_status_coherence_are_required() -> None:
    source_payload = payload_for("SOURCE_COVERAGE")
    reject_mutation(source_payload, ("status_reason",), "BLOCKED_SCHEMA_INVALID")
    reject_mutation(source_payload, ("source_coverage", "coverage_status"), "BLOCKED")

    accounting_payload = payload_for("ACCOUNTING")
    reject_mutation(accounting_payload, ("status_reason",), "BLOCKED_SCHEMA_INVALID")
    reject_mutation(accounting_payload, ("accounting", "accounting_status"), "BLOCKED")

    evaluator_payload = payload_for("EVALUATOR")
    reject_mutation(evaluator_payload, ("status_reason",), "READY")
    reject_mutation(evaluator_payload, ("evaluator", "evaluation_status"), "READY")

    overlay_payload = payload_for("BENCHMARK_OVERLAY")
    reject_mutation(overlay_payload, ("status_reason",), "READY")
    reject_mutation(overlay_payload, ("benchmark_overlay", "overlay_status"), "READY")
    reject_mutation(overlay_payload, ("benchmark_overlay", "series", 0, "status"), "READY")
    reject_mutation(overlay_payload, ("benchmark_overlay", "series", 2, "source_state"), "READY")

    report_payload = payload_for("REPORTS")
    reject_mutation(report_payload, ("status_reason",), "BLOCKED_REPORT_NOT_FOUND")
    reject_mutation(report_payload, ("status",), "BLOCKED")


def test_exact_1520_symbols_horizons_accounting_and_percent_display_are_required() -> None:
    source_payload = payload_for("SOURCE_COVERAGE")
    reject_mutation(source_payload, ("source_coverage", "sample_symbol"), "250")
    reject_mutation(source_payload, ("source_coverage", "sample_symbol"), "00AB12")
    reject_mutation(source_payload, ("source_coverage", "sample_timestamp_yyyymmddhhmm"), "202606121530")
    reject_mutation(source_payload, ("protocol", "price_basis"), "official_close")
    reject_mutation(source_payload, ("protocol", "source_policy", "official_close"), True)
    reject_mutation(source_payload, ("protocol", "source_policy", "nearest_fallback_allowed"), True)
    reject_mutation(source_payload, ("protocol", "source_policy", "full_day_daily_ohlcv_allowed"), True)

    panel_payload = payload_for("CAUSAL_PANEL")
    reject_mutation(panel_payload, ("causal_panel", "primary_horizon"), "H3")
    reject_mutation(panel_payload, ("causal_panel", "validation_horizons"), ["H1", "H5"])
    reject_mutation(panel_payload, ("causal_panel", "rows_preview", 0, "timestamp_kst"), "2026-06-12T15:30:00+09:00")
    reject_mutation(panel_payload, ("causal_panel", "rows_preview", 0, "symbol"), "00025")

    accounting_payload = payload_for("ACCOUNTING")
    reject_mutation(accounting_payload, ("accounting", "contract", "initial_capital_krw"), 50_000_000)
    reject_mutation(accounting_payload, ("accounting", "contract", "slot_count"), 9)
    reject_mutation(accounting_payload, ("accounting", "contract", "slot_budget_krw"), 4_000_000)
    reject_mutation(accounting_payload, ("accounting", "contract", "reserve_cash_krw"), 0)
    reject_mutation(accounting_payload, ("accounting", "cost_schedule", "primary", "internal_id"), "0.23%")
    reject_mutation(accounting_payload, ("accounting", "cost_schedule", "primary", "display_percent"), "23bp")
    reject_mutation(accounting_payload, ("accounting", "display_cost_percent"), "23bp")
    reject_mutation(accounting_payload, ("accounting", "cost_schedule", "primary", "round_trip_cost_bp"), 46)
    reject_mutation(accounting_payload, ("accounting", "cost_schedule", "primary", "display_percent"), "0.46%")
    reject_mutation(accounting_payload, ("accounting", "cost_schedule", "zero_cost_control", "internal_id"), "cost_00bp")
    reject_mutation(accounting_payload, ("accounting", "economic_nav_krw"), 9_007_199_254_740_992)
    reject_mutation(accounting_payload, ("accounting", "cash_reserve_krw"), 9_007_199_254_740_992)

    evaluator_payload = payload_for("EVALUATOR")
    validate_contract(evaluator_payload)
    assert evaluator_payload["evaluator"]["metrics"][1]["internal_cost_id"] == "zero_control_0bp"
    assert evaluator_payload["evaluator"]["metrics"][1]["display_cost_percent"] == "0.00%"
    reject_mutation(evaluator_payload, ("evaluator", "metrics", 0, "display_cost_percent"), "0.20%")
    reject_mutation(evaluator_payload, ("evaluator", "metrics", 0, "display_cost_percent"), "0.00%")
    reject_mutation(evaluator_payload, ("evaluator", "metrics", 0, "internal_cost_id"), "cost_00bp")
    reject_mutation(evaluator_payload, ("evaluator", "metrics", 0, "metric_id"), {"toString": "cumulative_return"})


def test_benchmark_overlay_is_pykrx_only_and_naver_never_ready_fallback() -> None:
    payload = payload_for("BENCHMARK_OVERLAY")
    validate_contract(payload)
    assert payload["benchmark_overlay"]["overlay_status"] == "BLOCKED"
    assert [series["series_id"] for series in payload["benchmark_overlay"]["series"]] == ["KOSPI", "KOSDAQ", "RL_PORTFOLIO"]
    ready_payload = ready_benchmark_overlay_root()
    validate_contract(ready_payload)
    assert [series["provider"] for series in ready_payload["benchmark_overlay"]["series"]] == ["PYKRX", "PYKRX", None]
    reject_mutation(ready_payload, ("benchmark_overlay", "series", 0, "provider"), None)
    reject_mutation(ready_payload, ("benchmark_overlay", "series", 1, "provider"), None)
    reject_mutation(ready_payload, ("benchmark_overlay", "series", 2, "provider"), "PYKRX")
    reject_mutation(payload, ("protocol", "overlay_policy", "allowed_index_provider"), "NAVER")
    reject_mutation(payload, ("protocol", "overlay_policy", "naver_fallback_allowed"), True)
    reject_mutation(payload, ("benchmark_overlay", "provider_policy", "forbidden_provider"), "NONE")
    reject_mutation(payload, ("benchmark_overlay", "series", 0, "provider"), "NAVER")
    reject_mutation(payload, ("benchmark_overlay", "series", 0, "provider"), "PYKRX")
    reject_mutation(payload, ("benchmark_overlay", "series", 0, "naver_used"), True)
    reject_mutation(payload, ("benchmark_overlay", "series", 1, "source_state"), "READY_FROM_NAVER")
    reject_mutation(payload, ("benchmark_overlay", "series"), [payload["benchmark_overlay"]["series"][2], payload["benchmark_overlay"]["series"][0], payload["benchmark_overlay"]["series"][1]])
    reject_mutation(payload, ("benchmark_overlay", "series", 1, "series_id"), "KOSPI")
    reject_mutation(payload, ("benchmark_overlay", "series", 2, "index_100"), 9_007_199_254_740_992)


def test_report_catalog_payloads_are_utf8_safe_and_path_traversal_closed() -> None:
    list_payload = payload_for("REPORTS")
    read_payload = payload_for("REPORT_READ")
    VALIDATOR.validate(list_payload)
    VALIDATOR.validate(read_payload)
    assert list_payload["reports"][0]["media_type"].endswith("charset=utf-8")
    assert "연구 보고서" in read_payload["content"]["raw_text"]
    assert read_payload["content"]["safe_html"].startswith('<article data-kronos-report-html="escaped-pre"><pre>')
    reject_mutation(list_payload, ("reports", 0, "relative_path"), "../secret.md")
    reject_mutation(list_payload, ("reports", 0, "relative_path"), "docs\\secret.md")
    reject_mutation(list_payload, ("reports", 0, "relative_path"), "C:/secret.md")
    reject_mutation(list_payload, ("reports", 0, "relative_path"), "Docs/secret.md")
    reject_mutation(list_payload, ("reports", 0, "relative_path"), "docs/Secret.md")
    reject_mutation(list_payload, ("reports", 0, "media_type"), "text/markdown")
    reject_mutation(list_payload, ("reports", 0, "report_id"), "report/unsafe")
    reject_mutation(read_payload, ("content", "unexpected"), "<script>alert(1)</script>")
    reject_mutation(read_payload, ("content", "safe_html"), "<h1>연구 보고서</h1>")
    reject_mutation(read_payload, ("content", "safe_html"), '<article data-kronos-report-html="escaped-pre"><pre><script>alert(1)</script></pre></article>')
    reject_mutation(read_payload, ("content", "safe_html"), '<article data-kronos-report-html="escaped-pre"><pre>javascript:alert(1)</pre></article>')
    reject_mutation(list_payload, ("reports", 0, "byte_length"), 9_007_199_254_740_992)
    reject_mutation(read_payload, ("report", "official_close"), True)
    reject_mutation(read_payload, ("source", "official_close"), True)
