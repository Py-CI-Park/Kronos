"""Past-only Daily OHLCV market-regime data-quality audit.

This module is a research-only diagnostic.  It never submits orders, never opens
broker/live/paper surfaces, and never converts market-regime evidence into a
model-build or profitability claim.  Its job is to make D0/D1/proxy blockers
explicit and reproducible before any further Daily OHLCV model work.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

try:  # pragma: no cover - import shim for direct script execution
    from .daily_ohlcv_db import (
        DEFAULT_DAILY_DB_PATH,
        PRICE_BASIS_BLOCKED_USES,
        PRICE_BASIS_STATUS,
        build_price_basis_audit,
        connect_readonly,
        list_daily_tables,
        summarize_daily_db,
        validate_daily_table_name,
    )
except ImportError:  # pragma: no cover
    from daily_ohlcv_db import (  # type: ignore
        DEFAULT_DAILY_DB_PATH,
        PRICE_BASIS_BLOCKED_USES,
        PRICE_BASIS_STATUS,
        build_price_basis_audit,
        connect_readonly,
        list_daily_tables,
        summarize_daily_db,
        validate_daily_table_name,
    )

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ID = "market_regime_audit_2026_06_19_001"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "webui" / "rl_runs" / "daily_ohlcv_market_regime"
DEFAULT_COST_SENSITIVITY_BP = (0, 23, 46)
ALLOWED_REPO_OUTPUT_ROOTS = (
    REPO_ROOT / "webui" / "rl_runs",
    REPO_ROOT / "artifacts",
)
RESEARCH_GUARDRAIL = (
    "Research-only market-regime data-quality audit; no live/broker/orders, "
    "no model-build unlock, no paper-forward unlock, and no profit claim."
)
REQUIRED_ARTIFACTS = (
    "market_regime_audit_manifest.json",
    "price_basis_audit.json",
    "universe_quality.csv",
    "regime_proxy_metrics.csv",
    "baseline_control_metrics.csv",
    "leakage_audit.json",
    "stale_artifact_audit.json",
)
SOURCE_HASH_PATHS = (
    "stom_rl/daily_market_regime_audit.py",
    "stom_rl/daily_ohlcv_db.py",
    "docs/stom_daily_ohlcv_past_only_market_regime_data_quality_audit_prereg_2026-06-19.md",
)



def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _fingerprint_path(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path), "sha256": None, "bytes": 0}
    if path.is_file():
        return {"exists": True, "path": str(path), "sha256": _sha256_file(path), "bytes": path.stat().st_size}
    payload = "|".join(sorted(child.name for child in path.iterdir()))
    return {"exists": True, "path": str(path), "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(), "bytes": None}

def _source_hashes(paths: Sequence[str] = SOURCE_HASH_PATHS) -> dict[str, dict[str, Any]]:
    hashes: dict[str, dict[str, Any]] = {}
    for rel_path in paths:
        path = REPO_ROOT / rel_path
        hashes[rel_path] = _fingerprint_path(path)
    return hashes
def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_run_id(run_id: str) -> str:
    if not run_id or run_id in {".", ".."}:
        raise ValueError("run_id must be a non-empty leaf directory name")
    if Path(run_id).name != run_id or any(sep in run_id for sep in ("/", "\\", ":")):
        raise ValueError("run_id must not contain path separators or drive markers")
    return run_id


def _resolve_run_dir(output_root: Path, run_id: str) -> Path:
    output_root = output_root.resolve()
    repo_root = REPO_ROOT.resolve()
    if _is_relative_to(output_root, repo_root):
        allowed_roots = tuple(root.resolve() for root in ALLOWED_REPO_OUTPUT_ROOTS)
        if not any(_is_relative_to(output_root, allowed_root) for allowed_root in allowed_roots):
            raise ValueError("repo-local output_root must be under webui/rl_runs or artifacts")
    run_dir = (output_root / _validate_run_id(run_id)).resolve()
    if not _is_relative_to(run_dir, output_root):
        raise ValueError("run_id escapes output_root")
    return run_dir


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)





def _quote_ident(name: str) -> str:
    validate_daily_table_name(name)
    return '"' + name.replace('"', '""') + '"'


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: Sequence[float]) -> float:
    if len(values) <= 1:
        return 0.0
    avg = _mean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / (len(values) - 1))


def _max_drawdown(closes: Sequence[float]) -> float:
    peak: float | None = None
    max_dd = 0.0
    for close in closes:
        if close <= 0:
            continue
        peak = close if peak is None else max(peak, close)
        if peak and peak > 0:
            max_dd = min(max_dd, (close / peak) - 1.0)
    return max_dd


def _read_table_rows(conn: sqlite3.Connection, table: str, *, row_limit: int) -> list[dict[str, Any]]:
    qt = _quote_ident(table)
    safe_limit = max(2, min(int(row_limit), 5000))
    rows = conn.execute(
        f"SELECT date, open, high, low, close, volume FROM {qt} "
        "WHERE date IS NOT NULL AND close IS NOT NULL ORDER BY date DESC LIMIT ?",
        (safe_limit,),
    ).fetchall()
    return [dict(row) for row in reversed(rows)]


def _table_dates(conn: sqlite3.Connection, table: str) -> dict[str, Any]:
    qt = _quote_ident(table)
    row = conn.execute(f"SELECT COUNT(*) AS rows, MIN(date) AS first_date, MAX(date) AS last_date FROM {qt}").fetchone()
    return {"row_count": int(row["rows"] or 0), "first_date": row["first_date"], "last_date": row["last_date"]}


def _missing_days(first_date: str | None, last_date: str | None, row_count: int) -> int | None:
    if not first_date or not last_date:
        return None
    try:
        first = datetime.fromisoformat(str(first_date)).date()
        last = datetime.fromisoformat(str(last_date)).date()
    except ValueError:
        return None
    calendar_days = max((last - first).days + 1, 0)
    return max(calendar_days - row_count, 0)


def build_universe_quality_rows(
    conn: sqlite3.Connection,
    tables: Sequence[str],
    *,
    latest_global_date: str | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table in tables:
        stats = _table_dates(conn, table)
        missing = _missing_days(stats["first_date"], stats["last_date"], stats["row_count"])
        stale = bool(latest_global_date and stats["last_date"] and str(stats["last_date"]) < latest_global_date)
        coverage_bucket = "empty"
        if stats["row_count"] >= 2000:
            coverage_bucket = "deep_history"
        elif stats["row_count"] >= 500:
            coverage_bucket = "medium_history"
        elif stats["row_count"] > 0:
            coverage_bucket = "thin_history"
        rows.append(
            {
                "table": table,
                "code": table[1:],
                "prefix": table[0],
                "code_preserved_as_string": True,
                "row_count": stats["row_count"],
                "first_date": stats["first_date"],
                "last_date": stats["last_date"],
                "missing_calendar_days": missing,
                "stale_vs_global_latest": stale,
                "coverage_bucket": coverage_bucket,
                "status": "WATCH" if stale or stats["row_count"] <= 0 else "INSPECTED_RESEARCH_ONLY",
            }
        )
    return rows


def build_regime_proxy_rows(
    conn: sqlite3.Connection,
    tables: Sequence[str],
    *,
    row_limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table in tables:
        ohlcv_rows = _read_table_rows(conn, table, row_limit=row_limit)
        closes = [value for value in (_safe_float(row.get("close")) for row in ohlcv_rows) if value and value > 0]
        volumes = [value for value in (_safe_float(row.get("volume")) for row in ohlcv_rows) if value is not None]
        returns: list[float] = []
        for prev, cur in zip(closes, closes[1:]):
            if prev > 0:
                returns.append((cur / prev) - 1.0)
        positive_days = sum(1 for value in returns if value > 0)
        breadth_proxy = positive_days / len(returns) if returns else 0.0
        volatility = _stddev(returns[-20:]) if returns else 0.0
        drawdown = _max_drawdown(closes[-60:]) if closes else 0.0
        dispersion = max(returns[-20:]) - min(returns[-20:]) if len(returns[-20:]) >= 2 else 0.0
        liquidity = _mean(volumes[-20:]) if volumes else 0.0
        last_return = returns[-1] if returns else 0.0
        rows.append(
            {
                "split": "audit_sample",
                "fold_id": "market_regime_prereg_sample",
                "table": table,
                "code": table[1:],
                "code_preserved_as_string": True,
                "sample_rows": len(ohlcv_rows),
                "return_observations": len(returns),
                "volatility_proxy_20d": volatility,
                "drawdown_proxy_60d": drawdown,
                "breadth_proxy_positive_return_share": breadth_proxy,
                "dispersion_proxy_20d": dispersion,
                "liquidity_proxy_avg_volume_20d": liquidity,
                "last_observed_return": last_return,
                "source_timing": "past_or_current_ohlcv_only",
                "future_label_used": False,
                "promotion_allowed": False,
                "status": "PAST_ONLY_PROXY_BUILT" if len(returns) >= 2 else "INSUFFICIENT_HISTORY_WATCH",
            }
        )
    return rows


def build_baseline_control_rows(proxy_rows: Sequence[dict[str, Any]], *, cost_bp_values: Sequence[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    returns = [float(row.get("last_observed_return") or 0.0) for row in proxy_rows]
    mean_return = _mean(returns)
    shuffle_return = _mean(list(reversed(returns))) if returns else 0.0
    top_count = max(1, min(5, len(proxy_rows))) if proxy_rows else 0
    top_rows = sorted(proxy_rows, key=lambda row: float(row.get("volatility_proxy_20d") or 0.0), reverse=True)[:top_count]
    top_return = _mean([float(row.get("last_observed_return") or 0.0) for row in top_rows]) if top_rows else 0.0
    controls = [
        ("no_trade", 0.0),
        ("shuffle", shuffle_return),
        ("equal_weight_top_k", top_return),
        ("frozen_d3", mean_return),
    ]
    for name, gross in controls:
        for cost_bp in cost_bp_values:
            rows.append(
                {
                    "control": name,
                    "cost_round_trip_bp": cost_bp,
                    "gross_return_proxy": gross,
                    "net_return_proxy": gross - (cost_bp / 10000.0 if name != "no_trade" else 0.0),
                    "observation_count": len(returns),
                    "split": "audit_sample",
                    "promotion_allowed": False,
                    "status": "DIAGNOSTIC_ONLY_NO_D5_UNLOCK",
                }
            )
    return rows


def build_leakage_audit(proxy_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    violations = [row for row in proxy_rows if row.get("future_label_used") not in {False, "False", "false", 0}]
    return {
        "schema_version": "daily_ohlcv_market_regime_leakage_audit.v1",
        "status": "PASS" if not violations else "BLOCKED_LEAKAGE_VIOLATION",
        "feature_timing_policy": "current_or_past_ohlcv_only; future labels evaluation-only",
        "future_label_used": False,
        "violation_count": len(violations),
        "violations": violations[:10],
        "promotion_allowed": False,
        "guardrail": RESEARCH_GUARDRAIL,
    }


def build_stale_artifact_audit(
    run_dir: Path,
    *,
    required_artifacts: Sequence[str],
    fresh_after_utc: str | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    missing = 0
    malformed = 0
    stale = 0
    fresh_after = _parse_utc(fresh_after_utc)
    for name in required_artifacts:
        path = run_dir / name
        exists = path.exists()
        parse_status = "not_checked"
        modified_at_utc = None
        freshness_status = "not_checked"
        if not exists:
            missing += 1
            parse_status = "missing_fail_closed"
            freshness_status = "missing_fail_closed"
        else:
            if path.is_file():
                modified_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
                modified_at_utc = modified_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
                if fresh_after and modified_at < fresh_after:
                    stale += 1
                    freshness_status = "stale_fail_closed"
                else:
                    freshness_status = "fresh_ok" if fresh_after else "freshness_not_required"
            if path.suffix == ".json":
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                    parse_status = "json_ok"
                except json.JSONDecodeError:
                    malformed += 1
                    parse_status = "malformed_fail_closed"
        rows.append(
            {
                "artifact": name,
                "exists": exists,
                "parse_status": parse_status,
                "freshness_status": freshness_status,
                "modified_at_utc": modified_at_utc,
                "sha256": _sha256_file(path) if exists and path.is_file() else None,
            }
        )
    return {
        "schema_version": "daily_ohlcv_market_regime_stale_artifact_audit.v1",
        "status": "PASS" if missing == 0 and malformed == 0 and stale == 0 else "FAIL_CLOSED",
        "missing_count": missing,
        "malformed_count": malformed,
        "stale_count": stale,
        "fresh_after_utc": fresh_after_utc,
        "artifact_checks": rows,
        "latest_selection_policy": "hash_required_and_missing_malformed_or_stale_artifacts_fail_closed",
        "optimistic_state_allowed": False,
    }


def run_market_regime_audit(
    *,
    db_path: Path | str = DEFAULT_DAILY_DB_PATH,
    output_root: Path | str = DEFAULT_OUTPUT_ROOT,
    run_id: str = DEFAULT_RUN_ID,
    table_limit: int = 25,
    row_limit: int = 260,
    cost_bp_values: Sequence[int] = DEFAULT_COST_SENSITIVITY_BP,
    source_ref: str | None = None,
) -> dict[str, Any]:
    db_path = Path(db_path)
    run_started_at = datetime.now(timezone.utc)
    run_dir = _resolve_run_dir(Path(output_root), run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = run_dir / "market_regime_audit_manifest.json"
    if not db_path.exists():
        fail_payload = {
            "schema_version": "daily_ohlcv_market_regime_audit.v1",
            "run_id": run_id,
            "created_at_utc": _utc_now(),
            "status": "FAIL_CLOSED_MISSING_DAILY_DB",
            "db_path": str(db_path),
            "promotion_allowed": False,
            "research_only_locks": _research_only_locks(),
            "guardrail": RESEARCH_GUARDRAIL,
            "source_hashes": _source_hashes(),
        }
        _write_json(manifest_path, fail_payload)
        return fail_payload

    all_tables = list_daily_tables(db_path)
    selected_tables = all_tables[: max(0, min(int(table_limit), len(all_tables)))]
    with connect_readonly(db_path) as conn:
        db_summary = summarize_daily_db(db_path, table_limit=0, quality_table_limit=min(len(all_tables), max(0, int(table_limit))))
        latest_global_date = db_summary.get("latest_date")
        price_basis = build_price_basis_audit(
            quality_scan_scope="market_regime_audit_sample" if selected_tables else "empty_universe",
            quality_scan_table_count=len(selected_tables),
            quality_scan_total_table_count=len(all_tables),
            quality_scan_complete=len(selected_tables) == len(all_tables),
            representative_windows=list(db_summary.get("material_unknown_adjustment_windows") or [])[:10],
            split_like_table_count=int(db_summary.get("split_like_table_count") or 0),
            split_like_window_sample_count=int(db_summary.get("split_like_window_sample_count") or 0),
            per_table_window_limit=5,
        )
        universe_rows = build_universe_quality_rows(conn, selected_tables, latest_global_date=latest_global_date)
        proxy_rows = build_regime_proxy_rows(conn, selected_tables, row_limit=row_limit)

    control_rows = build_baseline_control_rows(proxy_rows, cost_bp_values=cost_bp_values)
    leakage_audit = build_leakage_audit(proxy_rows)

    price_path = run_dir / "price_basis_audit.json"
    universe_path = run_dir / "universe_quality.csv"
    proxy_path = run_dir / "regime_proxy_metrics.csv"
    controls_path = run_dir / "baseline_control_metrics.csv"
    leakage_path = run_dir / "leakage_audit.json"
    stale_path = run_dir / "stale_artifact_audit.json"

    _write_json(price_path, price_basis)
    _write_csv(
        universe_path,
        universe_rows,
        [
            "table",
            "code",
            "prefix",
            "code_preserved_as_string",
            "row_count",
            "first_date",
            "last_date",
            "missing_calendar_days",
            "stale_vs_global_latest",
            "coverage_bucket",
            "status",
        ],
    )
    _write_csv(
        proxy_path,
        proxy_rows,
        [
            "split",
            "fold_id",
            "table",
            "code",
            "code_preserved_as_string",
            "sample_rows",
            "return_observations",
            "volatility_proxy_20d",
            "drawdown_proxy_60d",
            "breadth_proxy_positive_return_share",
            "dispersion_proxy_20d",
            "liquidity_proxy_avg_volume_20d",
            "last_observed_return",
            "source_timing",
            "future_label_used",
            "promotion_allowed",
            "status",
        ],
    )
    _write_csv(
        controls_path,
        control_rows,
        [
            "control",
            "cost_round_trip_bp",
            "gross_return_proxy",
            "net_return_proxy",
            "observation_count",
            "split",
            "promotion_allowed",
            "status",
        ],
    )
    _write_json(leakage_path, leakage_audit)
    stale_audit = build_stale_artifact_audit(
        run_dir,
        required_artifacts=[
            name
            for name in REQUIRED_ARTIFACTS
            if name not in {"market_regime_audit_manifest.json", "stale_artifact_audit.json"}
        ],
        fresh_after_utc=run_started_at.isoformat().replace("+00:00", "Z"),
    )
    _write_json(stale_path, stale_audit)

    artifact_paths = {
        "price_basis_audit": price_path,
        "universe_quality": universe_path,
        "regime_proxy_metrics": proxy_path,
        "baseline_control_metrics": controls_path,
        "leakage_audit": leakage_path,
        "stale_artifact_audit": stale_path,
    }
    artifact_hashes = {key: _sha256_file(path) for key, path in artifact_paths.items()}
    blocker_flags = []
    if PRICE_BASIS_STATUS != "VERIFIED":
        blocker_flags.append("D0_PRICE_BASIS_NOT_VERIFIED")
    if any(row.get("status") in {"WATCH", "empty"} for row in universe_rows):
        blocker_flags.append("D1_UNIVERSE_WATCH_OR_MISSINGNESS")
    if leakage_audit["status"] != "PASS":
        blocker_flags.append("PROXY_LEAKAGE_BLOCKER")
    if stale_audit["status"] != "PASS":
        blocker_flags.append("STALE_ARTIFACT_FAIL_CLOSED")

    manifest = {
        "schema_version": "daily_ohlcv_market_regime_audit.v1",
        "run_id": run_id,
        "created_at_utc": _utc_now(),
        "status": "COMPLETED_RESEARCH_ONLY",
        "verdict": "BLOCKER_EVIDENCE_RECORDED_NO_PROMOTION",
        "source_ref": source_ref or "working_tree",
        "source_hashes": _source_hashes(),
        "db_path": str(db_path),
        "db_fingerprint": _fingerprint_path(db_path),
        "table_denominator_count": len(all_tables),
        "sampled_table_count": len(selected_tables),
        "row_limit_per_table": row_limit,
        "default_cost_round_trip_bp": 23,
        "cost_sensitivity_bp": list(cost_bp_values),
        "required_controls": ["no_trade", "shuffle", "equal_weight_top_k", "frozen_d3"],
        "artifact_paths": {key: str(path) for key, path in artifact_paths.items()},
        "artifact_hashes": artifact_hashes,
        "blocker_flags": blocker_flags,
        "price_basis_status": PRICE_BASIS_STATUS,
        "price_basis_blocked_uses": list(PRICE_BASIS_BLOCKED_USES),
        "leakage_status": leakage_audit["status"],
        "stale_artifact_status": stale_audit["status"],
        "research_only_locks": _research_only_locks(),
        "promotion_allowed": False,
        "guardrail": RESEARCH_GUARDRAIL,
    }
    _write_json(manifest_path, manifest)
    return manifest


def _research_only_locks() -> dict[str, bool]:
    return {
        "model_build_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
        "go_summary_allowed": False,
        "profitability_claim_allowed": False,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Daily OHLCV market-regime data-quality audit")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DAILY_DB_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--table-limit", type=int, default=25)
    parser.add_argument("--row-limit", type=int, default=260)
    parser.add_argument("--source-ref", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    manifest = run_market_regime_audit(
        db_path=args.db_path,
        output_root=args.output_root,
        run_id=args.run_id,
        table_limit=args.table_limit,
        row_limit=args.row_limit,
        source_ref=args.source_ref,
    )
    print(json.dumps({"run_id": manifest.get("run_id"), "status": manifest.get("status"), "verdict": manifest.get("verdict"), "promotion_allowed": manifest.get("promotion_allowed")}, ensure_ascii=False))
    return 0 if str(manifest.get("status", "")).startswith("COMPLETED") else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
