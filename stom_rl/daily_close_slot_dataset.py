"""Close-to-next-close 10-slot dataset builder for research-only experiments.

This module materializes the Mode A daily close-slot panel used by the
specialized close-to-next-close contextual-bandit/RL lane. It deliberately keeps
D0 price-basis and D1 universe blockers visible while still allowing research
artifact generation, and it never implies live, broker, order, paper-forward, or
profitability readiness.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sqlite3
from copy import deepcopy
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .daily_ohlcv_dataset import (
    DEFAULT_FEATURE_COLUMNS,
    FEATURE_DEFINITIONS,
    assign_chronological_splits,
    load_universe_manifest,
    validate_no_feature_leakage,
)
from .daily_ohlcv_db import (
    ADJUSTMENT_POLICY,
    DECISION_GRADE_RETURN_STATUS,
    DEFAULT_DAILY_DB_PATH,
    PRICE_BASIS,
    PRICE_BASIS_EVIDENCE,
    PRICE_BASIS_STATUS,
    REPO_ROOT,
    connect_readonly,
    validate_daily_table_name,
)

DEFAULT_CLOSE_SLOT_DATASET_ROOT = REPO_ROOT / "webui" / "rl_runs" / "daily_close_slot_dataset"
CLOSE_SLOT_DATASET_SCHEMA_VERSION = 2
CLOSE_SLOT_LINEAGE_SCHEMA_VERSION = 1
RUN_ID_RE = re.compile(r"^(?=.*[0-9A-Za-z])[0-9A-Za-z_.-]+$")
ROUND_TRIP_COST_BP = 23
COST_SENSITIVITY_BP = [0, 23, 46]
COST_MODEL_SCHEMA_VERSION = 2
MAX_SLOT_COUNT = 10
SELECTION_CARDINALITY = "threshold_selected_0_to_10"
HOLD_CASH_ACTION = True
FALSE_LOCK_FIELDS = [
    "promotion_allowed",
    "model_build_allowed",
    "paper_forward_allowed",
    "live_broker_order_allowed",
    "profitability_claim_allowed",
    "go_summary_allowed",
]
COST_SCENARIOS = {
    "zero_control_0bp": {
        "scenario_id": "zero_control_0bp",
        "sell_tax_bp": 0.0,
        "buy_commission_bp": 0.0,
        "sell_commission_bp": 0.0,
        "buy_slippage_bp": 0.0,
        "sell_slippage_bp": 0.0,
        "total_bp": 0.0,
    },
    "base_23bp": {
        "scenario_id": "base_23bp",
        "sell_tax_bp": 20.0,
        "buy_commission_bp": 1.5,
        "sell_commission_bp": 1.5,
        "buy_slippage_bp": 0.0,
        "sell_slippage_bp": 0.0,
        "total_bp": 23.0,
    },
    "stress_46bp": {
        "scenario_id": "stress_46bp",
        "sell_tax_bp": 20.0,
        "buy_commission_bp": 1.5,
        "sell_commission_bp": 1.5,
        "buy_slippage_bp": 11.5,
        "sell_slippage_bp": 11.5,
        "total_bp": 46.0,
    },
}
POLICY_THRESHOLD_CONTRACT = {
    "selection_rule": "select rows with score >= inclusive_threshold after deterministic sort",
    "threshold_inclusive": True,
    "max_selected_count": MAX_SLOT_COUNT,
    "selection_cardinality": SELECTION_CARDINALITY,
    "hold_cash_action": HOLD_CASH_ACTION,
    "cash_hold_reason": "fewer_than_max_slot_count_rows_meet_threshold",
    "deterministic_tie_breaks": [
        {"column": "score", "direction": "desc"},
        {"column": "tie_score", "direction": "desc", "missing": "last"},
        {"column": "code", "direction": "asc", "format": "zero_padded_6_digit_string"},
        {"column": "table", "direction": "asc"},
        {"column": "candidate_index", "direction": "asc", "missing": "last"},
    ],
    "replay_adapter": "must_preserve_threshold_selected_flags_hold_cash_and_zero_padded_codes",
}
DEFAULT_TOTAL_CAPITAL_KRW = 10_000_000
DEFAULT_SLOT_COUNT = 10
FILL_MODE = "close_to_next_close_research_label"
DECISION_TIME_LABEL = "after_current_daily_close_research_only"
EXECUTION_REALISM = "non_executable_upper_bound_without_preclose_features"
RESEARCH_STATUS = "NO-GO_RESEARCH_ONLY"
WATCH_STATUS = "WATCH_RESEARCH_ONLY"

LABEL_COLUMNS = ["future_return_1d", "future_direction_1d", "future_rank_pct_1d"]
STABLE_LINEAGE_ERRORS = {
    "LINEAGE_MISSING_SCHEMA_VERSION",
    "LINEAGE_MISSING_UPSTREAM_RUN_ID",
    "LINEAGE_HASH_MISMATCH",
    "LINEAGE_FILE_MISSING",
    "LINEAGE_ROW_COUNT_MISMATCH",
    "LINEAGE_UNSAFE_PATH",
    "LINEAGE_STALE_OPTIMISTIC_FLAGS",
    "LINEAGE_MISSING_ARTIFACT_HASH",
    "COST_LADDER_MISSING_23BP",
    "BASELINE_NO_TRADE_OR_SHUFFLE_MISSING",
    "DATASET_V2_COST_MODEL_SCHEMA_MISSING",
    "DATASET_V2_COST_SCENARIOS_INVALID",
    "DATASET_V2_POLICY_CONTRACT_INVALID",
    "DATASET_V2_SLOT_CONTRACT_INVALID",
    "DATASET_V2_DB_ACCESS_NOT_READ_ONLY",
}

DB_READ_ONLY_ACCESS_CONTRACT = {
    "access_mode": "read_only",
    "sqlite_uri_mode": "ro",
    "pragma_query_only": True,
    "mutation_allowed": False,
    "connection_helper": "stom_rl.daily_ohlcv_db.connect_readonly",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha_json(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _db_fingerprint(path: Path | str) -> str:
    resolved = Path(path).resolve()
    stat = resolved.stat()
    payload = f"{resolved}|{stat.st_size}|{int(stat.st_mtime)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
        if math.isnan(parsed) or math.isinf(parsed):
            return None
        return parsed
    except (TypeError, ValueError):
        return None


def _safe_ratio(numerator: Any, denominator: Any) -> float | None:
    num = _safe_float(numerator)
    den = _safe_float(denominator)
    if num is None or den in {None, 0}:
        return None
    return num / den


def _pct_change(current: Any, previous: Any) -> float | None:
    ratio = _safe_ratio(current, previous)
    if ratio is None:
        return None
    return ratio - 1.0


def _mean(values: Iterable[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None and not math.isnan(float(value))]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _std(values: Iterable[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None and not math.isnan(float(value))]
    if not clean:
        return None
    avg = sum(clean) / len(clean)
    return math.sqrt(sum((value - avg) ** 2 for value in clean) / len(clean))


def _quote_ident(table: str) -> str:
    table = validate_daily_table_name(table)
    return '"' + table.replace('"', '""') + '"'


def _validate_run_id(run_id: str) -> str:
    rid = str(run_id or "").strip()
    if not rid or rid in {".", ".."} or not RUN_ID_RE.match(rid) or ".." in rid:
        raise ValueError(f"Invalid close-slot run_id: {run_id!r}")
    return rid


def _included_universe_symbols(manifest: dict[str, Any], *, max_symbols: int | None = None) -> list[dict[str, Any]]:
    symbols = [dict(row) for row in manifest.get("symbols") or [] if row.get("include") is True]
    if max_symbols is not None:
        return symbols[: max(0, int(max_symbols))]
    return symbols


def _upstream_gate_blockers(universe: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if str(DECISION_GRADE_RETURN_STATUS).startswith("BLOCKED") or PRICE_BASIS_STATUS != "VERIFIED":
        blockers.append("D0_PRICE_BASIS_NOT_VERIFIED")
    review = str(universe.get("universe_review_status") or universe.get("review_status") or universe.get("verdict") or "")
    if review != "OFFICIAL_OR_MANUAL_REVIEWED":
        blockers.append("D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED")
    return blockers


def _read_table_rows(
    conn: sqlite3.Connection,
    table: str,
    *,
    max_rows_per_symbol: int | None = None,
) -> list[dict[str, Any]]:
    qt = _quote_ident(table)
    if max_rows_per_symbol is None:
        rows = conn.execute(f"SELECT * FROM {qt} ORDER BY date ASC").fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM (SELECT * FROM {qt} ORDER BY date DESC LIMIT ?) ORDER BY date ASC",
            (max(0, int(max_rows_per_symbol)),),
        ).fetchall()
    return [dict(row) for row in rows]


def _build_symbol_rows(rows: list[dict[str, Any]], *, table: str, code: str) -> list[dict[str, Any]]:
    panel_rows: list[dict[str, Any]] = []
    returns: list[float | None] = []
    volumes: list[float | None] = []
    for index, row in enumerate(rows):
        previous = rows[index - 1] if index > 0 else None
        future = rows[index + 1] if index + 1 < len(rows) else None
        close = _safe_float(row.get("close"))
        prev_close = _safe_float(previous.get("close")) if previous is not None else None
        next_close = _safe_float(future.get("close")) if future is not None else None
        ret_1d = _pct_change(close, prev_close)
        returns.append(ret_1d)
        volume = _safe_float(row.get("volume"))
        volumes.append(volume)
        window_returns = [value for value in returns[max(0, index - 4) : index + 1] if value is not None]
        window_volumes = [value for value in volumes[max(0, index - 4) : index + 1] if value is not None]
        close_5 = _safe_float(rows[index - 5].get("close")) if index >= 5 else None
        return_5d = _pct_change(close, close_5)
        vol_5d = _std(window_returns)
        mean_volume_5d = _mean(window_volumes)
        volume_ratio_5d = (volume / mean_volume_5d) if volume is not None and mean_volume_5d not in {None, 0} else None
        hl_range = None
        high = _safe_float(row.get("high"))
        low = _safe_float(row.get("low"))
        if high is not None and low is not None and close not in {None, 0}:
            hl_range = (high - low) / close
        future_return = _pct_change(next_close, close)
        candidate_score = None if return_5d is None else return_5d / max(abs(vol_5d or 0.0), 1e-9)
        panel_rows.append(
            {
                "date": str(row.get("date")),
                "exit_date": None if future is None else str(future.get("date")),
                "table": table,
                "code": str(code).zfill(6),
                "entry_close": close,
                "next_close": next_close,
                "volume": volume,
                "return_1d": ret_1d,
                "return_5d": return_5d,
                "volatility_5d": vol_5d,
                "volume_ratio_5d": volume_ratio_5d,
                "hl_range": hl_range,
                "gap_from_prev_close": _pct_change(row.get("open"), prev_close),
                "foreign_holding_ratio": _safe_float(row.get("외국인현보유비율")),
                "institutional_net_buy": _safe_float(row.get("기관순매수")),
                "future_return_1d": future_return,
                "future_direction_1d": None if future_return is None else int(future_return > 0),
                "future_rank_pct_1d": None,
                "candidate_score_causal_momentum": candidate_score,
                "label_join_key": f'{row.get("date")}|{table}',
            }
        )
    return panel_rows


def _add_cross_sectional_ranks(rows: list[dict[str, Any]]) -> None:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    score_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("future_return_1d") is not None:
            by_date[str(row["date"])].append(row)
        if row.get("candidate_score_causal_momentum") is not None:
            score_by_date[str(row["date"])].append(row)
    for date_rows in by_date.values():
        ordered = sorted(date_rows, key=lambda row: float(row["future_return_1d"]))
        denom = max(1, len(ordered) - 1)
        for index, row in enumerate(ordered):
            row["future_rank_pct_1d"] = 1.0 if len(ordered) == 1 else index / denom
    for date_rows in score_by_date.values():
        ordered = sorted(date_rows, key=lambda row: (-float(row["candidate_score_causal_momentum"]), str(row["code"])))
        denom = max(1, len(ordered) - 1)
        for index, row in enumerate(ordered):
            row["candidate_rank_within_date"] = 1.0 if len(ordered) == 1 else 1.0 - (index / denom)


def _apply_splits(rows: list[dict[str, Any]], split_by_date: dict[str, str]) -> list[dict[str, Any]]:
    audits: list[dict[str, Any]] = []
    for row in rows:
        split = split_by_date.get(str(row["date"]), "blocked_out_of_range")
        block_reason = None
        if split not in {"train", "val", "test"}:
            block_reason = split.upper()
        if row.get("entry_close") is None or float(row.get("entry_close") or 0.0) <= 0:
            block_reason = "NONPOSITIVE_ENTRY_CLOSE"
        elif row.get("volume") is None or float(row.get("volume") or 0.0) <= 0:
            block_reason = "NONPOSITIVE_VOLUME"
        elif row.get("next_close") is None or row.get("future_return_1d") is None:
            block_reason = "MISSING_NEXT_CLOSE"
        eligible = split in {"train", "val", "test"} and block_reason is None
        row["split"] = split
        row["eligible_for_selection"] = eligible
        row["blocked_reason"] = block_reason
        audits.append(
            {
                "date": row["date"],
                "exit_date": row.get("exit_date"),
                "table": row["table"],
                "code": row["code"],
                "split": split,
                "label_available": row.get("future_return_1d") is not None,
                "eligible_for_selection": eligible,
                "blocked_reason": block_reason,
            }
        )
    return audits


def _split_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(row.get("split")) for row in rows)
    eligible_counts = Counter(str(row.get("split")) for row in rows if row.get("eligible_for_selection"))
    dates_by_split: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        dates_by_split[str(row.get("split"))].append(str(row.get("date")))
    return {
        "row_counts": dict(counts),
        "eligible_row_counts": dict(eligible_counts),
        "date_ranges": {
            split: {"start": min(dates), "end": max(dates), "unique_dates": len(set(dates))}
            for split, dates in dates_by_split.items()
            if dates
        },
    }


def _candidate_scores_input_schema() -> dict[str, Any]:
    return {
        "schema_version": CLOSE_SLOT_DATASET_SCHEMA_VERSION,
        "purpose": "canonical_score_and_pick_input_for_daily_close_slot_env",
        "required_columns": ["date", "table", "code", "score"],
        "optional_columns": ["tie_score", "candidate_index", "source", "candidate_rank_within_date"],
        "code_format": "zero_padded_6_digit_string_preserved",
        "canonical_sort": [
            {"column": "score", "direction": "desc"},
            {"column": "tie_score", "direction": "desc", "missing": "last"},
            {"column": "code", "direction": "asc", "format": "zero_padded_6_digit_string"},
            {"column": "table", "direction": "asc"},
            {"column": "candidate_index", "direction": "asc", "missing": "last"},
        ],
        "slot_count": DEFAULT_SLOT_COUNT,
        "max_slot_count": MAX_SLOT_COUNT,
        "selection_cardinality": SELECTION_CARDINALITY,
        "hold_cash_action": HOLD_CASH_ACTION,
        "selected_code_lists": "test_or_replay_adapter_only_not_policy_action",
        "replay_adapter_contract": "threshold_selected_flags_and_cash_hold_counts_only_no_policy_action",
    }


def _v2_cost_scenarios_match(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    component_keys = [
        "sell_tax_bp",
        "buy_commission_bp",
        "sell_commission_bp",
        "buy_slippage_bp",
        "sell_slippage_bp",
    ]
    for scenario_id, expected in COST_SCENARIOS.items():
        scenario = value.get(scenario_id)
        if not isinstance(scenario, dict):
            return False
        if scenario.get("scenario_id") != scenario_id:
            return False
        for component in component_keys:
            try:
                actual_bp = float(scenario[component])
            except (KeyError, TypeError, ValueError):
                return False
            if actual_bp != float(expected[component]):
                return False
        try:
            actual_total = float(scenario.get("total_bp"))
        except (TypeError, ValueError):
            return False
        if actual_total != float(expected["total_bp"]):
            return False
    return True


def _validate_dataset_v2_contract(manifest: dict[str, Any], errors: list[str]) -> None:
    if int(manifest.get("schema_version") or 1) != 2:
        return
    if manifest.get("cost_model_schema_version") != COST_MODEL_SCHEMA_VERSION:
        errors.append("DATASET_V2_COST_MODEL_SCHEMA_MISSING")
    if not _v2_cost_scenarios_match(manifest.get("cost_scenarios")):
        errors.append("DATASET_V2_COST_SCENARIOS_INVALID")
    if (
        manifest.get("max_slot_count") != MAX_SLOT_COUNT
        or manifest.get("selection_cardinality") != SELECTION_CARDINALITY
        or manifest.get("hold_cash_action") is not HOLD_CASH_ACTION
    ):
        errors.append("DATASET_V2_SLOT_CONTRACT_INVALID")
    contract = manifest.get("policy_threshold_contract")
    if contract != POLICY_THRESHOLD_CONTRACT:
        errors.append("DATASET_V2_POLICY_CONTRACT_INVALID")
    db_access = manifest.get("daily_db_access")
    if db_access != DB_READ_ONLY_ACCESS_CONTRACT:
        errors.append("DATASET_V2_DB_ACCESS_NOT_READ_ONLY")


def build_daily_close_slot_dataset(
    *,
    daily_db_path: Path | str = DEFAULT_DAILY_DB_PATH,
    universe_manifest_path: Path | str | None = None,
    max_symbols: int | None = None,
    max_rows_per_symbol: int | None = None,
    train_fraction: float = 0.6,
    val_fraction: float = 0.2,
    purge_days: int = 5,
    embargo_days: int = 5,
    total_capital_krw: int = DEFAULT_TOTAL_CAPITAL_KRW,
    slot_count: int = DEFAULT_SLOT_COUNT,
) -> dict[str, Any]:
    """Build the close-slot research panel without writing artifacts."""

    if int(slot_count) != DEFAULT_SLOT_COUNT:
        raise ValueError("daily close-slot dataset currently requires slot_count=10")
    if int(total_capital_krw) <= 0:
        raise ValueError("total_capital_krw must be positive")
    feature_columns = list(DEFAULT_FEATURE_COLUMNS)
    leakage_report = validate_no_feature_leakage(feature_columns, LABEL_COLUMNS)
    universe, universe_path, universe_file_sha = load_universe_manifest(universe_manifest_path)
    included_symbols = _included_universe_symbols(universe, max_symbols=max_symbols)
    table_rows: list[dict[str, Any]] = []
    missing_tables: list[str] = []
    with connect_readonly(daily_db_path) as conn:
        table_names = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        for symbol in included_symbols:
            table = validate_daily_table_name(str(symbol.get("table")))
            code = str(symbol.get("code") or table[1:]).zfill(6)
            if table not in table_names:
                missing_tables.append(table)
                continue
            rows = _read_table_rows(conn, table, max_rows_per_symbol=max_rows_per_symbol)
            table_rows.extend(_build_symbol_rows(rows, table=table, code=code))
    _add_cross_sectional_ranks(table_rows)
    split_by_date = assign_chronological_splits(
        [row["date"] for row in table_rows],
        train_fraction=train_fraction,
        val_fraction=val_fraction,
        purge_days=purge_days,
        embargo_days=embargo_days,
    )
    label_audit = _apply_splits(table_rows, split_by_date)
    candidate_rows = [
        {
            "date": row["date"],
            "table": row["table"],
            "code": row["code"],
            "score": row.get("candidate_score_causal_momentum"),
            "candidate_rank_within_date": row.get("candidate_rank_within_date"),
            "eligible_for_selection": row.get("eligible_for_selection"),
            "split": row.get("split"),
            "blocked_reason": row.get("blocked_reason"),
            "label_join_key": row.get("label_join_key"),
        }
        for row in table_rows
    ]
    upstream_blockers = _upstream_gate_blockers(universe)
    status = WATCH_STATUS if upstream_blockers else RESEARCH_STATUS
    split_summary = _split_summary(table_rows)
    row_counts = {
        "close_slot_panel_rows": len(table_rows),
        "candidate_score_rows": len(candidate_rows),
        "label_audit_rows": len(label_audit),
        "eligible_rows": sum(1 for row in table_rows if row.get("eligible_for_selection")),
        "missing_tables": len(missing_tables),
    }
    manifest = {
        "schema_version": CLOSE_SLOT_DATASET_SCHEMA_VERSION,
        "lineage_schema_version": CLOSE_SLOT_LINEAGE_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "artifact_kind": "daily_close_slot_dataset",
        "research_lane": "daily_close_slot",
        "strategy_label": "contextual_bandit_or_rl_research_dataset",
        "status": status,
        "readiness_status": status,
        "guardrail": "EXPERIMENTAL_ONLY RESEARCH_ONLY; no live/broker/account/order/paper-forward/profitability claim.",
        "artifact_generation_allowed": True,
        "promotion_allowed": False,
        "model_build_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
        "profitability_claim_allowed": False,
        "go_summary_allowed": False,
        "false_locks": {field: False for field in FALSE_LOCK_FIELDS},
        "price_basis": PRICE_BASIS,
        "price_basis_status": PRICE_BASIS_STATUS,
        "price_basis_evidence": PRICE_BASIS_EVIDENCE,
        "decision_grade_return_status": DECISION_GRADE_RETURN_STATUS,
        "adjustment_policy": ADJUSTMENT_POLICY,
        "universe_manifest_path": str(universe_path),
        "universe_manifest_sha": universe.get("manifest_sha") or universe_file_sha,
        "universe_file_sha256": universe_file_sha,
        "source_run_ids": {
            "daily_db_fingerprint": _db_fingerprint(daily_db_path),
            "universe_manifest_sha": universe.get("manifest_sha") or universe_file_sha,
        },
        "universe_verdict": universe.get("verdict"),
        "universe_review_status": universe.get("universe_review_status") or universe.get("review_status"),
        "upstream_gate_blockers": upstream_blockers,
        "d0_d1_blockers": {
            "d0_price_basis_blocked": "D0_PRICE_BASIS_NOT_VERIFIED" in upstream_blockers,
            "d1_universe_blocked": "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED" in upstream_blockers,
            "active_blockers": list(upstream_blockers),
        },
        "fill_mode": FILL_MODE,
        "decision_time_label": DECISION_TIME_LABEL,
        "execution_realism": EXECUTION_REALISM,
        "entry_fill_assumption": "official_daily_close_research_fill",
        "exit_fill_assumption": "next_official_daily_close_research_fill",
        "closing_auction_queue_model": "unavailable",
        "partial_fill_model": "unavailable",
        "closing_auction_volume": "unavailable",
        "liquidity_proxy": "daily_volume_only",
        "round_trip_cost_bp": ROUND_TRIP_COST_BP,
        "cost_sensitivity_bp": list(COST_SENSITIVITY_BP),
        "cost_model_schema_version": COST_MODEL_SCHEMA_VERSION,
        "max_slot_count": MAX_SLOT_COUNT,
        "selection_cardinality": SELECTION_CARDINALITY,
        "hold_cash_action": HOLD_CASH_ACTION,
        "cost_scenarios": deepcopy(COST_SCENARIOS),
        "policy_threshold_contract": deepcopy(POLICY_THRESHOLD_CONTRACT),
        "slot_count": int(slot_count),
        "total_capital_krw": int(total_capital_krw),
        "slot_capital_krw": int(total_capital_krw) / int(slot_count),
        "integer_shares_primary": True,
        "daily_db_path": str(Path(daily_db_path)),
        "daily_db_fingerprint": _db_fingerprint(daily_db_path),
        "daily_db_access": deepcopy(DB_READ_ONLY_ACCESS_CONTRACT),
        "feature_columns": feature_columns,
        "label_columns": LABEL_COLUMNS,
        "feature_definitions": {name: FEATURE_DEFINITIONS[name] for name in feature_columns},
        "leakage_status": leakage_report["status"],
        "split_policy": {
            "method": "chronological_train_val_test_with_purge_embargo",
            "train_fraction": train_fraction,
            "val_fraction": val_fraction,
            "test_fraction": 1.0 - train_fraction - val_fraction,
            "purge_days": int(purge_days),
            "embargo_days": int(embargo_days),
        },
        "split_summary": split_summary,
        "row_counts": row_counts,
        "source_counts": {
            "universe_symbols_total": len(universe.get("symbols") or []),
            "included_symbols_total": sum(1 for row in universe.get("symbols") or [] if row.get("include") is True),
            "included_symbols_used": len(included_symbols),
            "max_symbols": max_symbols,
            "max_rows_per_symbol": max_rows_per_symbol,
        },
        "missing_tables": missing_tables[:100],
        "lineage_validation_status": "PENDING_WRITE",
        "lineage_validation_errors": [],
    }
    manifest["manifest_sha"] = _sha_json(
        {
            "schema_version": manifest["schema_version"],
            "lineage_schema_version": manifest["lineage_schema_version"],
            "generated_at": manifest["generated_at"],
            "universe_manifest_sha": manifest["universe_manifest_sha"],
            "row_counts": row_counts,
            "feature_columns": feature_columns,
            "label_columns": LABEL_COLUMNS,
            "split_policy": manifest["split_policy"],
        }
    )
    return {
        "manifest": manifest,
        "close_slot_panel": table_rows,
        "candidate_scores_input_schema": _candidate_scores_input_schema(),
        "candidate_score_rows": candidate_rows,
        "feature_contract": {
            "schema_version": CLOSE_SLOT_DATASET_SCHEMA_VERSION,
            "feature_columns": feature_columns,
            "label_columns": LABEL_COLUMNS,
            "feature_definitions": {name: FEATURE_DEFINITIONS[name] for name in feature_columns},
            "leakage_report": leakage_report,
            "max_slot_count": MAX_SLOT_COUNT,
            "selection_cardinality": SELECTION_CARDINALITY,
            "hold_cash_action": HOLD_CASH_ACTION,
            "code_format": "zero_padded_6_digit_string_preserved",
            "policy_threshold_contract": POLICY_THRESHOLD_CONTRACT,
        },
        "label_audit": label_audit,
        "split_summary": split_summary,
        "source_hashes": {
            "daily_db_fingerprint": manifest["daily_db_fingerprint"],
            "universe_manifest_sha": manifest["universe_manifest_sha"],
            "universe_file_sha256": universe_file_sha,
            "dataset_manifest_contract_sha256": _sha_json(
                {
                    "schema_version": CLOSE_SLOT_DATASET_SCHEMA_VERSION,
                    "cost_model_schema_version": COST_MODEL_SCHEMA_VERSION,
                    "max_slot_count": MAX_SLOT_COUNT,
                    "selection_cardinality": SELECTION_CARDINALITY,
                    "hold_cash_action": HOLD_CASH_ACTION,
                    "cost_scenarios": COST_SCENARIOS,
                    "policy_threshold_contract": POLICY_THRESHOLD_CONTRACT,
                    "code_format": "zero_padded_6_digit_string_preserved",
                }
            ),
        },
    }


def _write_rows_csv(path: Path, rows: list[dict[str, Any]], *, fallback_fields: list[str]) -> None:
    if rows:
        fields = sorted({key for row in rows for key in row.keys()})
    else:
        fields = fallback_fields
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _csv_row_count(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _resolve_artifact_path(value: Any, *, manifest_dir: Path, artifact_dir: Path) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = manifest_dir / path
    resolved = path.resolve()
    try:
        resolved.relative_to(artifact_dir.resolve())
    except ValueError:
        return None
    return resolved


def validate_close_slot_dataset_lineage(manifest_or_path: dict[str, Any] | Path | str) -> dict[str, Any]:
    """Validate a written close-slot dataset manifest and artifact hashes."""

    if isinstance(manifest_or_path, (str, Path)):
        manifest_path = Path(manifest_or_path).resolve()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_dir = manifest_path.parent
    else:
        manifest = dict(manifest_or_path)
        manifest_dir = Path(str(manifest.get("artifact_dir") or ".")).resolve()
    artifact_dir = Path(str(manifest.get("artifact_dir") or manifest_dir)).resolve()
    errors: list[str] = []
    if "schema_version" not in manifest:
        errors.append("LINEAGE_MISSING_SCHEMA_VERSION")
    if manifest.get("lineage_schema_version") != CLOSE_SLOT_LINEAGE_SCHEMA_VERSION:
        errors.append("LINEAGE_MISSING_SCHEMA_VERSION")
    try:
        _validate_run_id(str(manifest.get("run_id") or ""))
    except ValueError:
        errors.append("LINEAGE_MISSING_UPSTREAM_RUN_ID")
    cost_ladder = [int(value) for value in manifest.get("cost_sensitivity_bp") or []]
    if ROUND_TRIP_COST_BP not in cost_ladder or int(manifest.get("round_trip_cost_bp") or -1) != ROUND_TRIP_COST_BP:
        errors.append("COST_LADDER_MISSING_23BP")
    _validate_dataset_v2_contract(manifest, errors)
    false_locks = manifest.get("false_locks")
    if int(manifest.get("schema_version") or 1) == 2 and (
        not isinstance(false_locks, dict)
        or any(false_locks.get(field) is not False for field in FALSE_LOCK_FIELDS)
    ):
        errors.append("LINEAGE_STALE_OPTIMISTIC_FLAGS")
    if not isinstance(false_locks, dict):
        false_locks = {}
    if (
        manifest.get("promotion_allowed") is not False
        or manifest.get("model_build_allowed") is not False
        or manifest.get("live_broker_order_allowed") is not False
        or manifest.get("profitability_claim_allowed") is not False
        or manifest.get("paper_forward_allowed") is not False
        or manifest.get("go_summary_allowed") is not False
        or any(value is not False for value in false_locks.values())
    ):
        errors.append("LINEAGE_STALE_OPTIMISTIC_FLAGS")
    artifacts = manifest.get("artifacts") or {}
    artifact_hashes = manifest.get("artifact_hashes") or {}
    expected_rows = manifest.get("row_counts") or {}
    csv_count_keys = {
        "close_slot_panel": "close_slot_panel_rows",
        "label_audit": "label_audit_rows",
        "candidate_score_rows": "candidate_score_rows",
    }
    for key in [
        "close_slot_panel",
        "candidate_scores_input_schema",
        "candidate_score_rows",
        "feature_contract",
        "label_audit",
        "split_summary",
        "source_hashes",
    ]:
        path = _resolve_artifact_path(artifacts.get(key), manifest_dir=manifest_dir, artifact_dir=artifact_dir)
        if path is None:
            errors.append("LINEAGE_UNSAFE_PATH")
            continue
        if not path.exists():
            errors.append("LINEAGE_FILE_MISSING")
            continue
        expected_hash = artifact_hashes.get(key)
        if not expected_hash:
            errors.append("LINEAGE_MISSING_ARTIFACT_HASH")
        elif _file_sha(path) != expected_hash:
            errors.append("LINEAGE_HASH_MISMATCH")
        if key in csv_count_keys and _csv_row_count(path) != int(expected_rows.get(csv_count_keys[key], -1)):
            errors.append("LINEAGE_ROW_COUNT_MISMATCH")
    stable_errors = sorted(set(error for error in errors if error in STABLE_LINEAGE_ERRORS))
    return {
        "schema_version": CLOSE_SLOT_DATASET_SCHEMA_VERSION,
        "lineage_schema_version": CLOSE_SLOT_LINEAGE_SCHEMA_VERSION,
        "checked_at": _utc_now(),
        "status": "PASS" if not stable_errors else "BLOCK",
        "errors": stable_errors,
        "run_id": manifest.get("run_id"),
        "artifact_dir": str(artifact_dir),
    }


def write_close_slot_dataset_artifacts(
    dataset: dict[str, Any],
    *,
    artifact_root: Path | str | None = None,
    run_id: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write close-slot dataset artifacts under the generated run root."""

    root = Path(artifact_root or DEFAULT_CLOSE_SLOT_DATASET_ROOT).resolve()
    default_root = DEFAULT_CLOSE_SLOT_DATASET_ROOT.resolve()
    try:
        root.relative_to(default_root)
    except ValueError:
        if root != default_root:
            raise ValueError("Close-slot dataset artifacts must stay under webui/rl_runs/daily_close_slot_dataset")
    rid = _validate_run_id(run_id or f"close_slot_dataset_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
    out_dir = (root / rid).resolve()
    try:
        out_dir.relative_to(root)
    except ValueError as exc:
        raise ValueError("run_id escapes close-slot dataset artifact root") from exc
    if out_dir.exists() and any(out_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"Close-slot dataset artifact run_id already exists: {rid}")
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "close_slot_panel": out_dir / "close_slot_panel.csv",
        "candidate_scores_input_schema": out_dir / "candidate_scores_input_schema.json",
        "candidate_score_rows": out_dir / "candidate_score_rows.csv",
        "feature_contract": out_dir / "feature_contract.json",
        "label_audit": out_dir / "label_audit.csv",
        "split_summary": out_dir / "split_summary.json",
        "source_hashes": out_dir / "source_hashes.json",
    }
    manifest_path = out_dir / "close_slot_dataset_manifest.json"
    lineage_path = out_dir / "lineage_report.json"

    _write_rows_csv(
        paths["close_slot_panel"],
        dataset["close_slot_panel"],
        fallback_fields=[
            "date",
            "exit_date",
            "table",
            "code",
            "entry_close",
            "next_close",
            "future_return_1d",
            "split",
            "eligible_for_selection",
            "blocked_reason",
        ],
    )
    _write_rows_csv(
        paths["candidate_score_rows"],
        dataset["candidate_score_rows"],
        fallback_fields=["date", "table", "code", "score", "eligible_for_selection", "split", "blocked_reason"],
    )
    _write_rows_csv(
        paths["label_audit"],
        dataset["label_audit"],
        fallback_fields=["date", "exit_date", "table", "code", "split", "label_available", "eligible_for_selection", "blocked_reason"],
    )
    for key in ["candidate_scores_input_schema", "feature_contract", "split_summary", "source_hashes"]:
        paths[key].write_text(json.dumps(dataset[key], ensure_ascii=False, indent=2), encoding="utf-8")

    artifact_hashes = {key: _file_sha(path) for key, path in paths.items()}
    manifest = dict(dataset["manifest"])
    manifest.update(
        {
            "run_id": rid,
            "artifact_dir": str(out_dir),
            "artifacts": {key: str(path) for key, path in paths.items()},
            "artifact_hashes": artifact_hashes,
            "source_hashes_path": str(paths["source_hashes"]),
            "lineage_validation_status": "PENDING_VALIDATION",
            "lineage_validation_errors": [],
        }
    )
    manifest["manifest_sha"] = _sha_json(
        {
            "run_id": rid,
            "row_counts": manifest.get("row_counts"),
            "artifact_hashes": artifact_hashes,
            "source_hashes": dataset.get("source_hashes"),
            "lineage_schema_version": manifest.get("lineage_schema_version"),
            "guardrail_flags": {
                "promotion_allowed": manifest.get("promotion_allowed"),
                "paper_forward_allowed": manifest.get("paper_forward_allowed"),
                "live_broker_order_allowed": manifest.get("live_broker_order_allowed"),
                "profitability_claim_allowed": manifest.get("profitability_claim_allowed"),
            },
        }
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    lineage_report = validate_close_slot_dataset_lineage(manifest_path)
    manifest["lineage_validation_status"] = lineage_report["status"]
    manifest["lineage_validation_errors"] = lineage_report["errors"]
    manifest["lineage_report_path"] = str(lineage_path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    lineage_report = validate_close_slot_dataset_lineage(manifest_path)
    lineage_path.write_text(json.dumps(lineage_report, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "run_id": rid,
        "artifact_dir": str(out_dir),
        "close_slot_dataset_manifest_path": str(manifest_path),
        "close_slot_panel_path": str(paths["close_slot_panel"]),
        "candidate_scores_input_schema_path": str(paths["candidate_scores_input_schema"]),
        "candidate_score_rows_path": str(paths["candidate_score_rows"]),
        "feature_contract_path": str(paths["feature_contract"]),
        "label_audit_path": str(paths["label_audit"]),
        "split_summary_path": str(paths["split_summary"]),
        "source_hashes_path": str(paths["source_hashes"]),
        "lineage_report_path": str(lineage_path),
        "manifest_sha": manifest["manifest_sha"],
        "lineage_validation_status": lineage_report["status"],
    }


def build_and_write_daily_close_slot_dataset(**kwargs: Any) -> dict[str, Any]:
    dataset_keys = {
        "daily_db_path",
        "universe_manifest_path",
        "max_symbols",
        "max_rows_per_symbol",
        "train_fraction",
        "val_fraction",
        "purge_days",
        "embargo_days",
        "total_capital_krw",
        "slot_count",
    }
    write_keys = {"artifact_root", "run_id", "overwrite"}
    dataset_kwargs = {key: value for key, value in kwargs.items() if key in dataset_keys}
    write_kwargs = {key: value for key, value in kwargs.items() if key in write_keys}
    dataset = build_daily_close_slot_dataset(**dataset_kwargs)
    written = write_close_slot_dataset_artifacts(dataset, **write_kwargs)
    return {"dataset": dataset, "written": written}


__all__ = [
    "CLOSE_SLOT_DATASET_SCHEMA_VERSION",
    "CLOSE_SLOT_LINEAGE_SCHEMA_VERSION",
    "DEFAULT_CLOSE_SLOT_DATASET_ROOT",
    "DEFAULT_TOTAL_CAPITAL_KRW",
    "DEFAULT_SLOT_COUNT",
    "ROUND_TRIP_COST_BP",
    "COST_SENSITIVITY_BP",
    "build_daily_close_slot_dataset",
    "write_close_slot_dataset_artifacts",
    "build_and_write_daily_close_slot_dataset",
    "validate_close_slot_dataset_lineage",
]
