from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from flask import Flask
from jsonschema import Draft202012Validator
import webui.v51_research_api as v51_api_module

from webui.v51_research_api import (
    ROUTE_SPECS,
    V51_API_FALSE_LOCKS,
    V51_RESEARCH_CLAIMS,
    V51_RESEARCH_ARTIFACT_IDS,
    create_v51_research_api_blueprint,
)

ROOT = Path(__file__).resolve().parents[1]
V51_SCHEMA_PATH = ROOT / "docs" / "schemas" / "kronos_v51_research_api.v1.schema.json"
V51_SCHEMA_VALIDATOR = Draft202012Validator(json.loads(V51_SCHEMA_PATH.read_text(encoding="utf-8")))


class FakeReportCatalog:
    def __init__(self) -> None:
        self.read_ids: list[str] = []
        self.list_calls = 0
        self.service_report_id = "approved/safe.md"

    def list_reports(self) -> list[dict[str, object]]:
        self.list_calls += 1
        return [
            {
                "report_id": self.service_report_id,
                "title": "<script>alert(1)</script> Safe report",
                "relative_path": "approved/safe.md",
                "root_id": "approved",
                "media_type": "text/markdown; charset=utf-8",
                "byte_length": 26,
                "sha256": hashlib.sha256(b"# Safe\n<script>x</script>\n").hexdigest(),
                "updated_at": "2026-07-18T00:00:00Z",
            }
        ]

    def read_report(self, report_id: str) -> dict[str, object]:
        self.read_ids.append(report_id)
        assert report_id == self.service_report_id
        return {
            **self.list_reports()[0],
            "raw_text": "# Safe\n<script>alert(1)</script>\n",
            "safe_html": '<article data-kronos-report-html="escaped-pre"><pre># Safe\n&lt;script&gt;alert(1)&lt;/script&gt;\n</pre></article>',
        }

class UnsafeHtmlReportCatalog(FakeReportCatalog):
    def read_report(self, report_id: str) -> dict[str, object]:
        record = super().read_report(report_id)
        record["safe_html"] = '<img src=x onerror="alert(1)"><script>alert(1)</script>'
        return record


class CandidateHtmlReportCatalog(FakeReportCatalog):
    def read_report(self, report_id: str) -> dict[str, object]:
        record = super().read_report(report_id)
        record["raw_text"] = "# Safe\n<em>raw text only</em>\n"
        record["safe_html"] = "<article><pre><strong>candidate html must not pass through</strong></pre></article>"
        record["html"] = "<p>candidate html must not pass through</p>"
        return record


class OversizedReportCatalog(FakeReportCatalog):
    def read_report(self, report_id: str) -> dict[str, object]:
        raise v51_api_module.ResearchReportCatalogError(
            413,
            "REPORT_TOO_LARGE",
            "D:/secret\\approved\\safe.md exceeds the byte limit",
        )


class LargeEnvelopeReportCatalog(FakeReportCatalog):
    def read_report(self, report_id: str) -> dict[str, object]:
        record = super().read_report(report_id)
        record["raw_text"] = "# Large\n" + ("x" * 5000)
        record["safe_html"] = "<p>candidate html must not pass through</p>"
        return record

class UppercaseExtensionReportCatalog(FakeReportCatalog):
    def list_reports(self) -> list[dict[str, object]]:
        records = super().list_reports()
        records[0]["relative_path"] = "approved/SAFE.MD"
        return records


class RuntimeErrorListReportCatalog(FakeReportCatalog):
    def list_reports(self) -> list[dict[str, object]]:
        raise RuntimeError("D:/secret\\reports\\catalog.json exploded")


class RuntimeErrorReadReportCatalog(FakeReportCatalog):
    def read_report(self, report_id: str) -> dict[str, object]:
        self.read_ids.append(report_id)
        raise RuntimeError("C:/secret\\approved\\safe.md exploded")


def _source_artifact_payload() -> dict[str, object]:
    source_db_path = "D:/Kronos/_database/Stock_Database_ohlcv_5min.db"
    source_db_sha256 = "b" * 64
    source_columns = ["date", "open", "high", "low", "close", "volume"]
    return {
        "schema_version": "kronos_daily_1520_source.v1",
        "source_db_path": source_db_path,
        "source_snapshot": {
            "sha256": source_db_sha256,
            "byte_length": 1,
            "hash_basis": "ACTUAL_FILE_BYTES_STREAMING_SHA256",
        },
        "source_db_sha256": source_db_sha256,
        "source_hash_basis": "ACTUAL_FILE_BYTES_STREAMING_SHA256",
        "read_only": True,
        "query_only": True,
        "causal_cutoff_kst": "15:20:00",
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
        "source_calendar": ["2026-07-17"],
        "first_valid_date": "2026-07-17",
        "last_valid_date": "2026-07-17",
        "exact_1520_row_count": 1,
        "missing_1520_date_count": 0,
        "missing_date_policy": (
            "Expected dates are each table's own observed valid intraday source calendar within the requested range; "
            "missing dates are explicit and source rows are never synthesized."
        ),
        "missing_rows_synthesized": False,
        "false_research_locks": dict(V51_API_FALSE_LOCKS),
        "six_locks_false": dict(V51_API_FALSE_LOCKS),
        "no_claim_flags": {
            "official_close_claim": False,
            "daily_ohlcv_fallback_claim": False,
            "nearest_bar_fallback_claim": False,
            "paper_forward_claim": False,
            "live_broker_order_claim": False,
            "profitability_claim": False,
        },
        "tables": [
            {
                "requested": "000250",
                "symbol": "000250",
                "table": "A000250",
                "source_columns": source_columns,
                "first_valid_date": "2026-07-17",
                "last_valid_date": "2026-07-17",
                "exact_1520_row_count": 1,
                "valid_session_count": 1,
                "duplicate_1520_date_count": 0,
                "expected_session_count": 1,
                "missing_1520_date_count": 0,
                "missing_dates": [],
                "missing_exclusion_reason": "MISSING_1520_BAR",
                "missing_rows_synthesized": False,
                "tradable_when_missing": False,
            }
        ],
        "rows": [
            {
                "schema_version": "kronos_daily_1520_source.v1",
                "session_date": "2026-07-17",
                "date": "2026-07-17",
                "timestamp_kst": "2026-07-17T15:20:00+09:00",
                "timestamp_yyyymmddhhmm": "202607171520",
                "symbol": "000250",
                "table": "A000250",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "price_1520_close_proxy": 100.0,
                "bar_volume_1520": 1000,
                "bar_volume_status": "SINGLE_5MIN_BAR_VOLUME_AT_15_20_ONLY",
                "volume_to_1520": None,
                "volume_to_1520_status": "NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY",
                "cumulative_volume_to_1520": None,
                "cumulative_volume_to_1520_status": "NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY",
                "amount_to_1520": None,
                "amount_to_1520_status": "NOT_AVAILABLE_5MIN_DB_HAS_NO_AMOUNT_COLUMN_DO_NOT_APPROXIMATE_PRICE_X_VOLUME",
                "tradable": True,
                "exclusion_reason": None,
                "official_close": False,
                "price_basis": "15:20_bar_close_proxy",
                "causal_cutoff_kst": "15:20:00",
                "source_db_path": source_db_path,
                "source_table": "A000250",
                "source_columns": source_columns,
                "source_timestamp_column": "date",
                "source_price_column": "close",
                "source_volume_column": "volume",
            }
        ],
    }


def _artifact_envelope(
    artifact_id: str,
    payload: dict[str, object],
    *,
    run_id: str = "run-1",
    revision: int = 7,
    run_artifact_id: str = "run-artifact-1",
    generated_at: str = "2026-07-18T00:00:00Z",
) -> dict[str, object]:
    return {
        "artifact_id": artifact_id,
        "run_id": run_id,
        "run_revision": revision,
        "run_artifact_id": run_artifact_id,
        "generated_at": generated_at,
        "payload": payload,
    }


class SourceArtifactProvider:
    def __init__(self, *, run_id: str = "run-1", revision: int = 7) -> None:
        self.run_id = run_id
        self.revision = revision
        self.calls: list[str] = []

    def read_json(self, artifact_id: str) -> dict[str, object]:
        self.calls.append(artifact_id)
        return _artifact_envelope(
            artifact_id,
            _source_artifact_payload(),
            run_id=self.run_id,
            revision=self.revision,
        )


class CountingArtifactProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def read_json(self, artifact_id: str) -> dict[str, object]:
        self.calls.append(artifact_id)
        raise KeyError(artifact_id)

class StaticArtifactProvider:
    def __init__(self, payloads: dict[str, dict[str, object]]) -> None:
        self.payloads = payloads
        self.calls: list[str] = []

    def read_json(self, artifact_id: str) -> dict[str, object]:
        self.calls.append(artifact_id)
        return self.payloads[artifact_id]


def _client(
    *,
    artifact_provider: Any | None = None,
    artifact_dir: Path | None = None,
    report_catalog: Any | None = None,
    max_json_bytes: int = v51_api_module.MAX_JSON_BYTES,
):
    app = Flask(__name__)
    app.register_blueprint(
        create_v51_research_api_blueprint(
            artifact_provider=artifact_provider,
            artifact_dir=artifact_dir,
            report_catalog=report_catalog,
            max_json_bytes=max_json_bytes,
        )
    )
    return app.test_client()


def _json(response) -> dict[str, Any]:
    payload = response.get_json()
    assert isinstance(payload, dict)
    return payload


def _assert_v51_schema(payload: dict[str, Any]) -> None:
    V51_SCHEMA_VALIDATOR.validate(payload)


def _attach_evaluator_digest(payload: dict[str, object], *, digest_field: str = "manifest_sha256") -> dict[str, object]:
    from stom_rl.daily_v51_evaluator import canonical_manifest_sha256

    payload[digest_field] = canonical_manifest_sha256(payload, digest_field=digest_field)
    return payload


def _ready_evaluator_payload() -> dict[str, object]:
    from stom_rl.daily_v51_evaluator import (
        EVALUATOR_SCHEMA_VERSION,
        HORIZON_GATE_SCHEMA_VERSION,
        HORIZON_RESULT_SCHEMA_VERSION,
        HORIZON_VARIANTS,
        PRIMARY_VARIANT_ID,
        VALIDATION_VARIANT_IDS,
        VARIANT_ORDER,
    )

    source_db_sha256 = "b" * 64
    false_locks = {
        "official_close": False,
        "full_day_daily_ohlcv": False,
        "live_trading": False,
        "profit_claim": False,
        "paper_trading": False,
        "broker_integration": False,
    }
    promotion_claims = {
        "live_trading": False,
        "profit": False,
        "paper_trading": False,
        "broker_integration": False,
    }
    horizon_results: list[dict[str, object]] = []
    for index, variant in enumerate(HORIZON_VARIANTS):
        metrics = {
            "schema_version": "kronos_daily_v51_horizon_metrics.v1",
            "variant_id": variant["variant_id"],
            "horizon_id": variant["horizon_id"],
            "horizon_days": variant["horizon_days"],
            "cost_scenario_id": "base_23bp",
            "round_trip_cost_bp": 23,
            "selected_count": 5 + index,
            "slot_count": 10,
            "account_nav": 60_300_000 + (index * 100_000),
            "reserve_krw": 10_000_000,
            "deployed_principal_krw": 25_000_000,
            "accounting_blocker_count": 0,
            "accounting_manifest_sha256": "c" * 64,
            "accounting_input_sha256": "d" * 64,
        }
        gate = {
            "schema_version": HORIZON_GATE_SCHEMA_VERSION,
            "variant_id": variant["variant_id"],
            "horizon_id": variant["horizon_id"],
            "role": variant["role"],
            "primary": variant["variant_id"] == PRIMARY_VARIANT_ID,
            "status": "PASS",
            "reason_codes": [],
            "blockers": [],
            "requires_exact_1520_entry_exit": True,
            "requires_pre_test_oos_freeze": True,
            "economic_nav_from_accounting": True,
            "live_trading_claim": False,
            "paper_trading_claim": False,
            "broker_integration_claim": False,
            "profit_claim": False,
        }
        horizon_results.append(
            _attach_evaluator_digest(
                {
                    "schema_version": HORIZON_RESULT_SCHEMA_VERSION,
                    "variant_id": variant["variant_id"],
                    "role": variant["role"],
                    "horizon_id": variant["horizon_id"],
                    "horizon_days": variant["horizon_days"],
                    "label_column": variant["label_column"],
                    "price_basis": "15:20_bar_close_proxy",
                    "panel_sha256": "e" * 64,
                    "source_hashes": {
                        "source_db_path": "D:/Kronos/_database/Stock_Database_ohlcv_5min.db",
                        "source_db_sha256": source_db_sha256,
                        "source_identity_sha256": "f" * 64,
                        "panel_sha256": "e" * 64,
                    },
                    "freeze_manifest_sha256": "a" * 64,
                    "horizon_manifest_sha256": "9" * 64,
                    "split_identity_sha256": "8" * 64,
                    "selection_fixed_at": "2026-07-18T00:00:00Z",
                    "selection_sequence": index + 1,
                    "selected_exact_marks": [],
                    "accounting_input_rows": [],
                    "accounting_input_sha256": "d" * 64,
                    "accounting": "validated-by-upstream-accounting",
                    "metrics": metrics,
                    "gate": gate,
                    "false_locks": false_locks,
                    "promotion_claims": promotion_claims,
                    "no_claims": [
                        "NO_LIVE_TRADING",
                        "NO_BROKER_INTEGRATION",
                        "NO_PAPER_TRADING",
                        "NO_PROFIT_CLAIM",
                    ],
                },
                digest_field="result_sha256",
            )
        )
    payload: dict[str, object] = {
        "schema_version": EVALUATOR_SCHEMA_VERSION,
        "generated_at": "2026-07-18T00:00:00Z",
        "run_id": "run-1",
        "run_revision": 7,
        "run_artifact_id": "run-artifact-1",
        "panel_schema_version": "kronos_daily_v51_causal_panel.v1",
        "price_basis": "15:20_bar_close_proxy",
        "source_db_sha256": source_db_sha256,
        "panel_sha256": "e" * 64,
        "source_hashes": {
            "source_db_path": "D:/Kronos/_database/Stock_Database_ohlcv_5min.db",
            "source_db_sha256": source_db_sha256,
            "source_identity_sha256": "f" * 64,
            "source_tables": ["A000250"],
            "panel_sha256": "e" * 64,
        },
        "freeze_manifest_sha256": "a" * 64,
        "split_identity_sha256": "8" * 64,
        "primary_variant_id": PRIMARY_VARIANT_ID,
        "validation_variant_ids": list(VALIDATION_VARIANT_IDS),
        "variant_order": list(VARIANT_ORDER),
        "cost_scenario_bp": 23,
        "horizons_fixed_before_untouched_test": True,
        "test_oos_driven_horizon_choice_rejected": True,
        "post_hoc_retuning_rejected": True,
        "false_locks": false_locks,
        "promotion_claims": promotion_claims,
        "no_claims": [
            "NO_LIVE_TRADING",
            "NO_BROKER_INTEGRATION",
            "NO_PAPER_TRADING",
            "NO_PROFIT_CLAIM",
        ],
        "horizon_result_sha256_by_variant": {
            str(item["variant_id"]): str(item["result_sha256"]) for item in horizon_results
        },
        "metrics_by_variant": {str(item["variant_id"]): item["metrics"] for item in horizon_results},
        "gates_by_variant": {str(item["variant_id"]): item["gate"] for item in horizon_results},
        "horizon_results": horizon_results,
    }
    return _attach_evaluator_digest(payload)


def _ready_overlay_payload() -> dict[str, object]:
    from stom_rl import korean_index_overlay as overlay
    from stom_rl.korean_index_source import build_normalized_index_artifact, build_raw_index_artifact

    common_dates = ["2026-07-17", "2026-07-18"]

    def index_artifact(market: str, closes: list[object]) -> dict[str, object]:
        raw = build_raw_index_artifact(
            market=market,
            start_date=common_dates[0],
            end_date=common_dates[-1],
            raw_rows=[
                {"date": date, "종가": close}
                for date, close in zip(common_dates, closes, strict=True)
            ],
            collected_at="2026-07-18T00:00:00Z",
        )
        return build_normalized_index_artifact(raw)

    rl_nav = {
        "source_id": "run-1",
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
        "source_metadata": {
            "source_kind": "v51_accounting",
            "price_basis": "15:20_bar_close_proxy",
            "official_close": False,
        },
        "series": [
            {
                "date": common_dates[0],
                "account_nav_krw": 60_000_000,
                "price_basis": "15:20_bar_close_proxy",
                "official_close": False,
            },
            {
                "date": common_dates[1],
                "account_nav_krw": 63_000_000,
                "price_basis": "15:20_bar_close_proxy",
                "official_close": False,
            },
        ],
    }
    payload = overlay.build_korean_index_overlay(
        index_artifact("KOSPI", [2500, 2525]),
        index_artifact("KOSDAQ", [800, 820]),
        rl_nav,
        min_common_dates=2,
    )
    payload.pop("overlay_sha256")
    payload.update(
        {
            "generated_at": "2026-07-18T00:00:00Z",
            "run_id": "run-1",
            "run_revision": 7,
            "run_artifact_id": "run-artifact-1",
            "source_db_sha256": "b" * 64,
        }
    )
    payload["overlay_sha256"] = overlay.sha256_hex(payload)
    return payload


def test_report_list_and_read_match_v51_contract_with_safe_content() -> None:
    catalog = FakeReportCatalog()
    client = _client(report_catalog=catalog)

    listing_response = client.get("/api/daily-close-v51/reports")
    listing = _json(listing_response)

    assert set(listing) == {"route_id", "status", "status_reason", "protocol", "source", "locks", "claims", "reports"}
    assert listing["route_id"] == "REPORTS"
    assert listing["status"] == "READY"
    assert listing["status_reason"] == "READY"
    assert listing["protocol"]["route_path"] == "/api/daily-close-v51/reports"
    assert listing_response.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in listing_response.headers["Content-Security-Policy"]
    assert listing["locks"] == V51_API_FALSE_LOCKS
    assert listing["claims"] == V51_RESEARCH_CLAIMS
    assert set(listing["source"]) == {"source_protocol", "catalog_artifact_id", "catalog_sha256", "generated_at", "price_basis", "official_close"}
    assert listing["source"]["source_protocol"] == "kronos_v51_report_catalog.v1"
    assert listing["source"]["catalog_artifact_id"] == "report-catalog"
    assert listing["source"]["price_basis"] == "15:20_bar_close_proxy"
    assert listing["source"]["official_close"] is False
    assert len(listing["reports"]) == 1
    public_report_id = listing["reports"][0]["report_id"]
    assert "/" not in public_report_id

    read_response = client.get(f"/api/daily-close-v51/reports/{public_report_id}")
    read = _json(read_response)

    assert set(read) == {"route_id", "status", "status_reason", "protocol", "source", "locks", "claims", "report", "content"}
    assert read["route_id"] == "REPORT_READ"
    assert read["status"] == "READY"
    assert read["protocol"]["route_path"] == "/api/daily-close-v51/reports/{report_id}"
    assert read_response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in read_response.headers["Content-Security-Policy"]
    assert read["report"]["report_id"] == public_report_id
    assert "<script" in read["content"]["raw_text"]
    assert "<script" not in read["content"]["safe_html"].lower()
    assert "&lt;script&gt;" in read["content"]["safe_html"]
    assert catalog.read_ids == [catalog.service_report_id]

def test_report_read_reescapes_unsafe_injected_safe_html() -> None:
    catalog = UnsafeHtmlReportCatalog()
    client = _client(report_catalog=catalog)
    listing = _json(client.get("/api/daily-close-v51/reports"))
    public_report_id = listing["reports"][0]["report_id"]

    read = _json(client.get(f"/api/daily-close-v51/reports/{public_report_id}"))

    safe_html = read["content"]["safe_html"].lower()
    assert "<script" not in safe_html
    assert "onerror" not in safe_html
    assert "&lt;script&gt;" in safe_html


def test_report_read_ignores_malicious_candidate_html_and_escapes_raw_text() -> None:
    catalog = CandidateHtmlReportCatalog()
    client = _client(report_catalog=catalog)
    listing = _json(client.get("/api/daily-close-v51/reports"))
    public_report_id = listing["reports"][0]["report_id"]

    read = _json(client.get(f"/api/daily-close-v51/reports/{public_report_id}"))

    safe_html = read["content"]["safe_html"]
    assert safe_html.startswith('<article data-kronos-report-html="escaped-pre"><pre>')
    assert "&lt;em&gt;raw text only&lt;/em&gt;" in safe_html
    assert "<em>" not in safe_html.lower()
    assert "candidate html must not pass through" not in safe_html


def test_oversized_report_read_returns_typed_error_without_path_leakage() -> None:
    catalog = OversizedReportCatalog()
    client = _client(report_catalog=catalog)
    listing = _json(client.get("/api/daily-close-v51/reports"))
    public_report_id = listing["reports"][0]["report_id"]

    response = client.get(f"/api/daily-close-v51/reports/{public_report_id}")
    payload = _json(response)
    body = response.get_data(as_text=True)

    assert response.status_code == 413
    assert payload["route_id"] == "REPORT_READ"
    assert payload["status"] == "ERROR"
    assert payload["error"]["status_code"] == 413
    assert "D:/" not in body and "\\" not in body


def test_oversized_report_response_envelope_returns_typed_error() -> None:
    client = _client(report_catalog=LargeEnvelopeReportCatalog(), max_json_bytes=5000)
    listing = _json(client.get("/api/daily-close-v51/reports"))
    public_report_id = listing["reports"][0]["report_id"]

    response = client.get(f"/api/daily-close-v51/reports/{public_report_id}")
    payload = _json(response)

    assert response.status_code == 413
    assert payload["route_id"] == "REPORT_READ"
    assert payload["status"] == "ERROR"
    assert payload["error"]["status_code"] == 413


def test_report_internal_v51_error_returns_typed_503_not_blocked(monkeypatch: Any) -> None:
    def broken_report_list(_reports: object) -> dict[str, object]:
        raise v51_api_module.V51ResearchApiError(503, "internal server error", code="INTERNAL_ERROR")

    monkeypatch.setattr(v51_api_module, "_report_list_payload", broken_report_list)
    client = _client(report_catalog=FakeReportCatalog())

    response = client.get("/api/daily-close-v51/reports")
    payload = _json(response)

    assert response.status_code == 503
    assert payload["route_id"] == "REPORTS"
    assert payload["status"] == "ERROR"
    assert payload["error"]["status_code"] == 503


def test_report_list_runtime_error_returns_typed_503_without_path_leakage() -> None:
    client = _client(report_catalog=RuntimeErrorListReportCatalog())

    response = client.get("/api/daily-close-v51/reports")
    payload = _json(response)
    body = response.get_data(as_text=True)

    assert response.status_code == 503
    assert response.mimetype == "application/json"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"
    assert "<html" not in body.lower()
    assert "D:/" not in body and "\\" not in body
    assert payload["route_id"] == "REPORTS"
    assert payload["status"] == "ERROR"
    assert payload["locks"] == V51_API_FALSE_LOCKS
    assert payload["claims"] == V51_RESEARCH_CLAIMS
    assert payload["error"] == {"code": "INTERNAL_ERROR", "message": "internal server error", "status_code": 503}


def test_report_read_runtime_error_returns_typed_503_without_path_leakage() -> None:
    catalog = RuntimeErrorReadReportCatalog()
    client = _client(report_catalog=catalog)
    public_report_id = _json(client.get("/api/daily-close-v51/reports"))["reports"][0]["report_id"]

    response = client.get(f"/api/daily-close-v51/reports/{public_report_id}")
    payload = _json(response)
    body = response.get_data(as_text=True)

    assert response.status_code == 503
    assert response.mimetype == "application/json"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"
    assert "<html" not in body.lower()
    assert "C:/" not in body and "\\" not in body
    assert payload["route_id"] == "REPORT_READ"
    assert payload["status"] == "ERROR"
    assert payload["locks"] == V51_API_FALSE_LOCKS
    assert payload["claims"] == V51_RESEARCH_CLAIMS
    assert payload["error"] == {"code": "INTERNAL_ERROR", "message": "internal server error", "status_code": 503}
    assert catalog.read_ids == [catalog.service_report_id]


def test_uppercase_report_extension_is_rejected_without_fabricated_report_path() -> None:
    client = _client(report_catalog=UppercaseExtensionReportCatalog())

    response = client.get("/api/daily-close-v51/reports")
    payload = _json(response)

    assert response.status_code == 200
    assert payload["route_id"] == "REPORTS"
    assert payload["status"] == "BLOCKED"
    assert payload["status_reason"] == "BLOCKED_SCHEMA_INVALID"
    assert payload["reports"] == []


def test_report_traversal_and_missing_ids_are_blocked_without_path_leakage() -> None:
    client = _client(report_catalog=FakeReportCatalog())

    for report_id in ("%2e%2e", "%2e%2e%5Csecret", "C:%5Csecret", "not-present"):
        response = client.get(f"/api/daily-close-v51/reports/{report_id}")
        payload = _json(response)
        body = response.get_data(as_text=True)

        assert response.status_code == 200
        assert payload["route_id"] == "REPORT_READ"
        assert payload["status"] == "BLOCKED"
        assert payload["status_reason"] == "BLOCKED_REPORT_NOT_FOUND"
        assert all(token not in body for token in ("D:/", "C:/", "D:\\\\", "C:\\\\"))

def test_default_report_catalog_error_blocks_without_path_leakage(monkeypatch: Any) -> None:
    class BrokenReportCatalog:
        def __init__(self) -> None:
            raise v51_api_module.ResearchReportCatalogError(503, "ROOT_UNAVAILABLE", "D:/secret\\reports unavailable")

    monkeypatch.setattr(v51_api_module, "ResearchReportCatalog", BrokenReportCatalog)
    client = _client()

    response = client.get("/api/daily-close-v51/reports")
    payload = _json(response)
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert payload["route_id"] == "REPORTS"
    assert payload["status"] == "BLOCKED"
    assert payload["status_reason"] == "BLOCKED_ARTIFACT_UNAVAILABLE"
    assert "D:/" not in body and "\\" not in body



def test_research_query_bindings_reject_unknown_duplicate_unsafe_and_mismatched_values() -> None:
    provider = CountingArtifactProvider()
    client = _client(artifact_provider=provider, report_catalog=FakeReportCatalog())
    wrong_artifact_id = V51_RESEARCH_ARTIFACT_IDS["CAUSAL_PANEL"]

    cases = (
        ("/api/daily-close-v51/source-coverage?extra=1", 400, "SOURCE_COVERAGE"),
        ("/api/daily-close-v51/source-coverage?run_id=run-1&run_id=run-2", 400, "SOURCE_COVERAGE"),
        ("/api/daily-close-v51/source-coverage?run_id=%2e%2e%2fsecret", 400, "SOURCE_COVERAGE"),
        ("/api/daily-close-v51/source-coverage?artifact_id=daily-close-v51-source-coverage%2F..", 400, "SOURCE_COVERAGE"),
        (f"/api/daily-close-v51/source-coverage?artifact_id={wrong_artifact_id}", 409, "SOURCE_COVERAGE"),
        ("/api/daily-close-v51/source-coverage?revision=0", 400, "SOURCE_COVERAGE"),
        ("/api/daily-close-v51/reports?run_id=run-1", 400, "REPORTS"),
    )

    for path, status_code, route_id in cases:
        response = client.get(path)
        payload = _json(response)

        assert response.status_code == status_code, path
        assert payload["route_id"] == route_id
        assert payload["status"] == "ERROR"
        assert payload["error"]["status_code"] == status_code
        _assert_v51_schema(payload)
        if route_id in V51_RESEARCH_ARTIFACT_IDS:
            assert payload["source"]["source_artifact_id"] == V51_RESEARCH_ARTIFACT_IDS[route_id]

    assert provider.calls == []


def test_research_query_run_and_revision_mismatch_are_conflicts() -> None:
    provider = SourceArtifactProvider()
    client = _client(artifact_provider=provider, report_catalog=FakeReportCatalog())
    source_artifact_id = V51_RESEARCH_ARTIFACT_IDS["SOURCE_COVERAGE"]

    matched_response = client.get(
        f"/api/daily-close-v51/source-coverage?artifact_id={source_artifact_id}&run_id=run-1&revision=7"
    )
    matched = _json(matched_response)

    assert matched_response.status_code == 200
    assert matched["status"] == "READY"
    assert matched["artifact"]["artifact_id"] == source_artifact_id
    assert matched["run"]["run_id"] == "run-1"
    assert matched["run"]["run_revision"] == 7
    assert matched["run"]["run_artifact_id"] == "run-artifact-1"

    for path in (
        f"/api/daily-close-v51/source-coverage?artifact_id={source_artifact_id}&run_id=run-2",
        f"/api/daily-close-v51/source-coverage?artifact_id={source_artifact_id}&revision=8",
    ):
        response = client.get(path)
        payload = _json(response)

        assert response.status_code == 409, path
        assert payload["route_id"] == "SOURCE_COVERAGE"
        assert payload["status"] == "ERROR"
        assert payload["error"]["status_code"] == 409
        _assert_v51_schema(payload)
        assert payload["source"]["source_artifact_id"] == source_artifact_id


def test_ready_evaluator_uses_gates_and_horizon_metrics_without_evaluation_status() -> None:
    artifact_id = V51_RESEARCH_ARTIFACT_IDS["EVALUATOR"]
    artifact_payload = _ready_evaluator_payload()
    assert "evaluation_status" not in artifact_payload
    provider = StaticArtifactProvider({artifact_id: _artifact_envelope(artifact_id, artifact_payload)})
    client = _client(artifact_provider=provider, report_catalog=FakeReportCatalog())

    response = client.get("/api/daily-close-v51/evaluator")
    payload = _json(response)

    assert response.status_code == 200
    assert payload["status"] == "READY"
    assert payload["status_reason"] == "READY"
    assert payload["run"]["run_id"] == "run-1"
    assert payload["run"]["run_revision"] == 7
    assert payload["run"]["run_artifact_id"] == "run-artifact-1"
    assert payload["source"]["source_db_sha256"] == "b" * 64
    assert payload["source"]["generated_at"] == "2026-07-18T00:00:00Z"
    evaluator = payload["evaluator"]
    assert evaluator["evaluation_status"] == "READY"
    assert evaluator["split_statuses"] == {"train": "READY", "validation": "READY", "test": "BLOCKED"}
    assert [metric["horizon"] for metric in evaluator["metrics"]] == ["H1", "H3", "H5"]
    assert evaluator["metrics"][0]["metric_id"] == "cumulative_return"
    assert evaluator["metrics"][0]["display_percent"] == "0.50%"
    assert provider.calls == [artifact_id]


def test_ready_benchmark_overlay_series_order_and_latest_index_value() -> None:
    artifact_id = V51_RESEARCH_ARTIFACT_IDS["BENCHMARK_OVERLAY"]
    provider = StaticArtifactProvider({artifact_id: _artifact_envelope(artifact_id, _ready_overlay_payload())})
    client = _client(artifact_provider=provider, report_catalog=FakeReportCatalog())

    response = client.get("/api/daily-close-v51/benchmark-overlay")
    payload = _json(response)

    assert response.status_code == 200
    assert payload["status"] == "READY"
    _assert_v51_schema(payload)
    series = payload["benchmark_overlay"]["series"]
    assert [item["series_id"] for item in series] == ["KOSPI", "KOSDAQ", "RL_PORTFOLIO"]
    assert [item["index_100"] for item in series] == [101, 102.5, 105]
    assert [item["provider"] for item in series] == ["PYKRX", "PYKRX", None]
    assert provider.calls == [artifact_id]


def test_ready_research_artifacts_missing_identity_block_schema_invalid() -> None:
    artifact_id = V51_RESEARCH_ARTIFACT_IDS["SOURCE_COVERAGE"]
    cases: list[tuple[str, dict[str, object]]] = []
    for missing_key in ("run_id", "run_revision", "run_artifact_id", "generated_at"):
        envelope = _artifact_envelope(artifact_id, _source_artifact_payload())
        envelope.pop(missing_key)
        cases.append((missing_key, envelope))

    uppercase_source_payload = _source_artifact_payload()
    uppercase_source_payload["source_db_sha256"] = "B" * 64
    source_snapshot = uppercase_source_payload["source_snapshot"]
    assert isinstance(source_snapshot, dict)
    source_snapshot["sha256"] = "B" * 64
    cases.append(("source_db_sha256", _artifact_envelope(artifact_id, uppercase_source_payload)))

    for case_id, envelope in cases:
        provider = StaticArtifactProvider({artifact_id: envelope})
        client = _client(artifact_provider=provider, report_catalog=FakeReportCatalog())

        response = client.get("/api/daily-close-v51/source-coverage")
        payload = _json(response)

        assert response.status_code == 200, case_id
        assert payload["status"] == "BLOCKED", case_id
        assert payload["status_reason"] == "BLOCKED_SCHEMA_INVALID", case_id
        assert payload["source_coverage"]["coverage_status"] == "BLOCKED", case_id
        assert provider.calls == [artifact_id]

def test_missing_artifact_store_returns_exact_blocked_roots_and_creates_nothing(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing-v51-artifacts"
    client = _client(artifact_dir=missing_dir, report_catalog=FakeReportCatalog())

    for spec in ROUTE_SPECS:
        response = client.get(f"/api/daily-close-v51{spec.rule}")
        payload = _json(response)

        assert response.status_code == 200
        assert payload["route_id"] == spec.route_id
        assert payload["status"] == "BLOCKED"
        assert payload["status_reason"] in {
            "BLOCKED_ARTIFACT_UNAVAILABLE",
            "BLOCKED_SOURCE_CONTRACT",
            "BLOCKED_INDEX_SERIES_SOURCE",
            "BLOCKED_PYKRX_ARTIFACT_MISSING",
        }
        assert payload["protocol"]["route_path"] == f"/api/daily-close-v51{spec.rule}"
        assert payload["locks"] == V51_API_FALSE_LOCKS
        assert payload["claims"] == V51_RESEARCH_CLAIMS
        assert set(payload) == {"route_id", "status", "status_reason", "protocol", "source", "run", "artifact", "locks", "claims", spec.artifact_key}

    assert not missing_dir.exists()


def test_non_get_methods_are_405_without_reading_artifacts_or_reports() -> None:
    provider = CountingArtifactProvider()
    catalog = FakeReportCatalog()
    client = _client(artifact_provider=provider, report_catalog=catalog)

    for path, expected_route in (
        ("/api/daily-close-v51/source-coverage", "SOURCE_COVERAGE"),
        ("/api/daily-close-v51/reports", "REPORTS"),
        ("/api/daily-close-v51/reports/not-present", "REPORT_READ"),
    ):
        for method in ("HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            response = client.open(path, method=method)
            assert response.status_code == 405, (path, method)
            assert response.headers["Allow"] == "GET"
            if method != "HEAD":
                payload = _json(response)
                assert payload["error"]["code"] == "METHOD_NOT_ALLOWED"
                assert payload["error"]["status_code"] == 405
                _assert_v51_schema(payload)
                assert payload["route_id"] == expected_route
                assert payload["protocol"]["route_id"] == expected_route
                assert payload["locks"] == V51_API_FALSE_LOCKS
                if expected_route in V51_RESEARCH_ARTIFACT_IDS:
                    assert payload["source"]["source_artifact_id"] == V51_RESEARCH_ARTIFACT_IDS[expected_route]
                if expected_route in {"REPORTS", "REPORT_READ"}:
                    assert payload["source"]["source_protocol"] == "kronos_v51_report_catalog.v1"

    assert provider.calls == []
    assert catalog.read_ids == []
    assert catalog.list_calls == 0
