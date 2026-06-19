import csv
import json
import sqlite3
from pathlib import Path

from stom_rl.daily_market_regime_audit import build_stale_artifact_audit, run_market_regime_audit


def _make_daily_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute('CREATE TABLE "A000250" (date TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL)')
        conn.execute('CREATE TABLE "QABC123" (date TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL)')
        rows = [
            ("2024-01-01", 100, 105, 95, 100, 1000),
            ("2024-01-02", 101, 106, 96, 104, 1200),
            ("2024-01-03", 103, 108, 99, 102, 900),
            ("2024-01-04", 102, 109, 101, 108, 1500),
            ("2024-01-05", 108, 110, 104, 106, 1100),
        ]
        conn.executemany('INSERT INTO "A000250" VALUES (?, ?, ?, ?, ?, ?)', rows)
        conn.executemany('INSERT INTO "QABC123" VALUES (?, ?, ?, ?, ?, ?)', rows[:3])
        conn.commit()
    finally:
        conn.close()


def test_market_regime_audit_writes_research_only_artifacts(tmp_path):
    db_path = tmp_path / "daily.db"
    _make_daily_db(db_path)
    output_root = tmp_path / "runs"

    manifest = run_market_regime_audit(
        db_path=db_path,
        output_root=output_root,
        run_id="market_regime_audit_test",
        table_limit=2,
        row_limit=5,
        source_ref="test-ref",
    )

    run_dir = output_root / "market_regime_audit_test"
    assert manifest["status"] == "COMPLETED_RESEARCH_ONLY"
    assert manifest["promotion_allowed"] is False
    assert manifest["research_only_locks"] == {
        "model_build_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
        "go_summary_allowed": False,
        "profitability_claim_allowed": False,
    }
    assert manifest["default_cost_round_trip_bp"] == 23
    assert manifest["cost_sensitivity_bp"] == [0, 23, 46]
    assert "D0_PRICE_BASIS_NOT_VERIFIED" in manifest["blocker_flags"]
    assert manifest["stale_artifact_status"] == "PASS"
    assert manifest["source_hashes"]["stom_rl/daily_market_regime_audit.py"]["exists"] is True
    assert manifest["source_hashes"]["stom_rl/daily_market_regime_audit.py"]["sha256"]

    required = [
        "market_regime_audit_manifest.json",
        "price_basis_audit.json",
        "universe_quality.csv",
        "regime_proxy_metrics.csv",
        "baseline_control_metrics.csv",
        "leakage_audit.json",
        "stale_artifact_audit.json",
    ]
    for name in required:
        assert (run_dir / name).exists(), name

    price_basis = json.loads((run_dir / "price_basis_audit.json").read_text(encoding="utf-8"))
    assert price_basis["status"] == "UNKNOWN_CONFIRMED"
    assert "model_build_or_candidate_promotion" in price_basis["blocked_uses"]

    universe_rows = list(csv.DictReader((run_dir / "universe_quality.csv").open(encoding="utf-8")))
    assert {row["code"] for row in universe_rows} == {"000250", "ABC123"}
    assert all(row["code_preserved_as_string"] == "True" for row in universe_rows)

    proxy_rows = list(csv.DictReader((run_dir / "regime_proxy_metrics.csv").open(encoding="utf-8")))
    assert proxy_rows
    assert {row["future_label_used"] for row in proxy_rows} == {"False"}
    assert {row["promotion_allowed"] for row in proxy_rows} == {"False"}
    assert {row["source_timing"] for row in proxy_rows} == {"past_or_current_ohlcv_only"}

    controls = list(csv.DictReader((run_dir / "baseline_control_metrics.csv").open(encoding="utf-8")))
    assert {int(row["cost_round_trip_bp"]) for row in controls} == {0, 23, 46}
    assert {row["control"] for row in controls} == {"no_trade", "shuffle", "equal_weight_top_k", "frozen_d3"}

    leakage = json.loads((run_dir / "leakage_audit.json").read_text(encoding="utf-8"))
    assert leakage["status"] == "PASS"
    assert leakage["future_label_used"] is False


def test_market_regime_audit_missing_db_fails_closed(tmp_path):
    manifest = run_market_regime_audit(
        db_path=tmp_path / "missing.db",
        output_root=tmp_path / "runs",
        run_id="missing_db",
    )

    assert manifest["status"] == "FAIL_CLOSED_MISSING_DAILY_DB"
    assert manifest["promotion_allowed"] is False
    assert manifest["research_only_locks"]["model_build_allowed"] is False
    manifest_path = tmp_path / "runs" / "missing_db" / "market_regime_audit_manifest.json"
    assert manifest_path.exists()

def test_stale_artifact_audit_fails_closed_on_missing_or_malformed_json(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "malformed.json").write_text("{not-json", encoding="utf-8")

    audit = build_stale_artifact_audit(run_dir, required_artifacts=["malformed.json", "missing.json"])

    assert audit["status"] == "FAIL_CLOSED"
    assert audit["malformed_count"] == 1
    assert audit["missing_count"] == 1
    checks = {row["artifact"]: row for row in audit["artifact_checks"]}
    assert checks["malformed.json"]["parse_status"] == "malformed_fail_closed"
    assert checks["missing.json"]["parse_status"] == "missing_fail_closed"
