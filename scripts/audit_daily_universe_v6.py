#!/usr/bin/env python3
"""V6 Track D-1/D-2: read-only full audit of the daily OHLCV DB and frozen universe manifest.

Honesty boundaries:
- Read-only against `_database/Stock_Database_ohlcv_1day.db`.
- The daily DB price basis remains UNKNOWN_CONFIRMED (see stom_rl.daily_ohlcv_db);
  liquidity uses close*volume strictly as a *filter heuristic*, never as verified
  traded amount and never as return evidence.
- Flow columns (foreign/institution) are audited for fill only; point-in-time
  publication-lag verification is a separate gate before any state feature use.
- Output is an audit artifact + a frozen universe manifest. No training happens here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_DB = REPO_ROOT / "_database" / "Stock_Database_ohlcv_1day.db"
DEFAULT_OUT = REPO_ROOT / "webui" / "rl_runs" / "daily_ohlcv_db_summary"
COMMON_STOCK_RE = re.compile(r"^A\d{6}$")

SCHEMA_VERSION = "kronos_v6_daily_universe_audit.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_of(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit daily OHLCV DB and emit a frozen V6 research universe manifest.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--manifest-out", type=Path, default=REPO_ROOT / "docs" / "kronos_v6_universe_manifest_2026-07-19.json")
    parser.add_argument("--active-min-last-date", type=int, default=20260601)
    parser.add_argument("--min-rows", type=int, default=750)
    parser.add_argument("--liquidity-window", type=int, default=60)
    parser.add_argument("--min-median-liquidity-proxy-krw", type=float, default=1_000_000_000.0)
    parser.add_argument("--top-n", type=int, default=500)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    conn = connect_readonly(args.db)
    tables = [
        str(r[0])
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    ]
    total_tables = len(tables)
    common = [t for t in tables if COMMON_STOCK_RE.match(t) and t.endswith("0")]
    non_common = total_tables - len(common)

    audited: list[dict[str, object]] = []
    skipped = {"inactive": 0, "short_history": 0, "illiquid": 0, "no_rows": 0}
    for table in common:
        qt = '"' + table + '"'
        row = conn.execute(f"SELECT COUNT(*), MIN(date), MAX(date) FROM {qt}").fetchone()
        rows, dmin, dmax = int(row[0] or 0), row[1], row[2]
        if rows == 0:
            skipped["no_rows"] += 1
            continue
        if dmax is None or int(dmax) < args.active_min_last_date:
            skipped["inactive"] += 1
            continue
        if rows < args.min_rows:
            skipped["short_history"] += 1
            continue
        tail = conn.execute(
            f"SELECT close, volume, 외국인현보유비율, 기관순매수 FROM {qt} ORDER BY date DESC LIMIT ?",
            (args.liquidity_window,),
        ).fetchall()
        proxies = [float(c) * float(v) for c, v, _, _ in tail if c is not None and v is not None]
        median_proxy = statistics.median(proxies) if proxies else 0.0
        if median_proxy < args.min_median_liquidity_proxy_krw:
            skipped["illiquid"] += 1
            continue
        foreign_fill = sum(1 for _, _, f, _ in tail if f not in (None, 0)) / max(1, len(tail))
        inst_fill = sum(1 for _, _, _, i in tail if i not in (None, 0)) / max(1, len(tail))
        audited.append(
            {
                "table": table,
                "code": table[1:],
                "rows": rows,
                "first_date": int(dmin),
                "last_date": int(dmax),
                "median_liquidity_proxy_krw_60d": round(median_proxy),
                "foreign_ratio_fill_rate_60d": round(foreign_fill, 4),
                "institution_netbuy_fill_rate_60d": round(inst_fill, 4),
            }
        )
    conn.close()

    audited.sort(key=lambda r: r["median_liquidity_proxy_krw_60d"], reverse=True)  # type: ignore[arg-type]
    selected = audited[: args.top_n]

    stat = args.db.stat()
    common_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": utc_now(),
        "db": {
            "path_suffix": "_database/Stock_Database_ohlcv_1day.db",
            "size_bytes": stat.st_size,
            "mtime_epoch": int(stat.st_mtime),
        },
        "price_basis": {
            "status": "UNKNOWN_CONFIRMED",
            "decision_grade_returns": "BLOCKED_UNTIL_PRICE_BASIS_VERIFIED",
            "allowed_use_here": "universe_filtering_and_feature_candidates_only",
        },
        "instrument_type": {
            "status": "UNVERIFIED_CODE_HEURISTIC_ONLY",
            "note": "code-ending-0 heuristic includes ETF/ETN/index products (e.g. A069500, A122630); a D1 instrument-type gate must verify and quarantine non-common-stock instruments before this universe is training-final",
        },
        "liquidity_proxy_disclaimer": "close*volume heuristic only; not verified traded amount; not return evidence",
        "flow_columns_disclaimer": "fill-rate audit only; point-in-time publication-lag gate pending before feature use",
        "filters": {
            "table_pattern": "^A\\d{6}$ and endswith '0' (common-stock heuristic)",
            "active_min_last_date": args.active_min_last_date,
            "min_rows": args.min_rows,
            "liquidity_window_sessions": args.liquidity_window,
            "min_median_liquidity_proxy_krw": args.min_median_liquidity_proxy_krw,
            "top_n": args.top_n,
        },
        "population": {
            "total_tables": total_tables,
            "common_stock_candidate_tables": len(common),
            "non_common_tables": non_common,
            "passed_all_filters": len(audited),
            "skipped": skipped,
        },
    }

    audit_payload = dict(common_payload)
    audit_payload["candidates_ranked"] = audited

    manifest_payload = dict(common_payload)
    manifest_payload["universe"] = [
        {"table": r["table"], "code": r["code"], "rows": r["rows"], "first_date": r["first_date"], "last_date": r["last_date"]}
        for r in selected
    ]
    manifest_payload["universe_size"] = len(selected)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    audit_path = args.out_dir / "v6_universe_audit.json"
    audit_text = json.dumps(audit_payload, ensure_ascii=False, indent=1, sort_keys=True)
    audit_path.write_text(audit_text, encoding="utf-8")

    manifest_text = json.dumps(manifest_payload, ensure_ascii=False, indent=1, sort_keys=True)
    args.manifest_out.write_text(manifest_text, encoding="utf-8")

    receipt = {
        "audit_artifact": str(audit_path.relative_to(REPO_ROOT)),
        "audit_sha256": sha256_of(audit_text),
        "manifest": str(args.manifest_out.relative_to(REPO_ROOT)),
        "manifest_sha256": sha256_of(manifest_text),
        "universe_size": len(selected),
        "population": common_payload["population"],
    }
    sys.stdout.write(json.dumps(receipt, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
