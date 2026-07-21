#!/usr/bin/env python3
"""V7 P6: audit whether Quant-Insight-style flow collection would duplicate
columns that already exist in the local daily OHLCV database.

Read-only and fully offline. Produces a JSON coverage report used to decide
whether new custody collectors (investor flow / foreign ratio) are needed or
would duplicate `_database/Stock_Database_ohlcv_1day.db` columns.
Short-selling data is reported as ABSENT (a genuinely new candidate) and is
deliberately NOT collected here; collection requires a preregistration that
actually consumes it.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_DB = REPO_ROOT / "_database" / "Stock_Database_ohlcv_1day.db"
UNIVERSE_MANIFEST = REPO_ROOT / "docs" / "kronos_v6_universe_manifest_2026-07-19.json"

FLOW_COLUMNS = ("기관순매수", "기관누적순매수", "외국인현보유비율", "외국인현보유수량", "외국인주문한도수량", "상장주식수")
SHORTSELLING_COLUMN_HINTS = ("공매도", "대차", "잔고")
RECENT_START = 20240101


def audit(sample_size: int) -> dict:
    manifest = json.loads(UNIVERSE_MANIFEST.read_text(encoding="utf-8"))
    tables = [str(row["table"]) for row in manifest["universe"]][:sample_size]
    connection = sqlite3.connect(f"file:{DAILY_DB.as_posix()}?mode=ro", uri=True)
    per_column = {name: {"tables_with_column": 0, "recent_rows": 0, "recent_nonnull": 0} for name in FLOW_COLUMNS}
    shortselling_columns_found: set[str] = set()
    tables_checked = 0
    try:
        for table in tables:
            if not table.startswith("A") or not table[1:].isdigit():
                continue
            columns = [str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')]
            if not columns:
                continue
            tables_checked += 1
            for column in columns:
                if any(hint in column for hint in SHORTSELLING_COLUMN_HINTS):
                    shortselling_columns_found.add(column)
            present = [name for name in FLOW_COLUMNS if name in columns]
            if not present:
                continue
            select = ", ".join(f'"{name}"' for name in present)
            rows = connection.execute(f'SELECT {select} FROM "{table}" WHERE date >= ?', (RECENT_START,)).fetchall()
            for name in present:
                per_column[name]["tables_with_column"] += 1
            index_by_name = {name: i for i, name in enumerate(present)}
            for row in rows:
                for name, i in index_by_name.items():
                    per_column[name]["recent_rows"] += 1
                    if row[i] is not None:
                        per_column[name]["recent_nonnull"] += 1
    finally:
        connection.close()

    summary = {}
    for name, stats in per_column.items():
        nonnull_pct = (stats["recent_nonnull"] / stats["recent_rows"] * 100.0) if stats["recent_rows"] else 0.0
        summary[name] = {
            **stats,
            "table_coverage_pct": stats["tables_with_column"] / tables_checked * 100.0 if tables_checked else 0.0,
            "recent_nonnull_pct": nonnull_pct,
        }
    flow_duplicated = all(
        summary[name]["table_coverage_pct"] >= 99.0 and summary[name]["recent_nonnull_pct"] >= 95.0
        for name in ("기관순매수", "외국인현보유비율")
    )
    return {
        "schema_version": "kronos_v7_p6_flow_coverage.v1",
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "daily_db": DAILY_DB.name,
        "universe_manifest": UNIVERSE_MANIFEST.name,
        "sample_tables_requested": sample_size,
        "tables_checked": tables_checked,
        "recent_window_start": RECENT_START,
        "columns": summary,
        "shortselling_columns_found": sorted(shortselling_columns_found),
        "decision": {
            "investor_flow_collection": "DUPLICATE_SKIP" if flow_duplicated else "GAP_FOUND_REVIEW_REQUIRED",
            "shortselling_collection": "ABSENT_DEFERRED_UNTIL_PREREG_CONSUMES_IT" if not shortselling_columns_found else "PRESENT_REVIEW_REQUIRED",
        },
        "policy": {
            "network_used": False,
            "price_basis_caveat": "daily DB price basis UNKNOWN_CONFIRMED; feature inputs only",
            "point_in_time_caveat": "flow publication lag unverified; D-1-or-earlier usage only",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit daily DB flow-column coverage vs collector candidates.")
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--output", default=str(REPO_ROOT / "docs" / "kronos_v7_p6_flow_coverage_2026-07-20.json"))
    args = parser.parse_args(argv)
    report = audit(args.sample_size)
    output = Path(args.output)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": output.as_posix(),
        "tables_checked": report["tables_checked"],
        "decision": report["decision"],
        "inst_netbuy_nonnull_pct": round(report["columns"]["기관순매수"]["recent_nonnull_pct"], 2),
        "foreign_ratio_nonnull_pct": round(report["columns"]["외국인현보유비율"]["recent_nonnull_pct"], 2),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
