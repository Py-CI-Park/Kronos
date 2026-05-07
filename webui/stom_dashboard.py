import csv
import io
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.utils


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREDICTION_DIRS = [
    PROJECT_ROOT / "webui" / "stom_predictions",
    PROJECT_ROOT / "finetune_csv" / "predictions",
]
EVIDENCE_DIR = PROJECT_ROOT / ".omx" / "specs" / "stom-ohlcv-finetune-research"
SCORE_FILTER_NAMES = [
    "all_scored",
    "buy_candidate_score60",
    "score65_consistency80",
    "score70_pred_return_0_5",
    "stable_positive_filter",
    "early_session_score60",
]
ADAPTER_EXPORT_FIELDS = [
    "rank",
    "source_file",
    "window_id",
    "symbol",
    "session",
    "asof_timestamp",
    "adapter_action",
    "signal",
    "kronos_score",
    "score_band",
    "pred_return_pct",
    "prediction_consistency",
    "pred_range_pct",
    "asof_minute_bucket",
    "filter_labels",
    "diagnostic_actual_return_pct",
    "diagnostic_direction_hit",
    "diagnostic_realized_mape",
]


def _safe_path_in_dirs(file_name: str, directories: Optional[List[Path]] = None) -> Path:
    directories = directories or PREDICTION_DIRS
    requested = Path(file_name)
    if requested.is_absolute() or ".." in requested.parts:
        raise ValueError("Invalid file path")

    for directory in directories:
        candidate = (directory / requested).resolve()
        if candidate.exists() and directory.resolve() in candidate.parents:
            return candidate
    raise FileNotFoundError(f"Prediction file not found: {file_name}")


def load_training_summary() -> Dict[str, Any]:
    inspect_path = EVIDENCE_DIR / "all_tables_inspect_close_only.json"
    scale_path = EVIDENCE_DIR / "all_tables_sample_scale_lookback300_predict60.json"
    summary: Dict[str, Any] = {
        "inspect_available": inspect_path.exists(),
        "scale_available": scale_path.exists(),
        "table_count": None,
        "compatible_stock_table_count": None,
        "eligible_group_count": None,
        "estimated_samples": None,
        "excluded_tables": ["moneytop", "stockinfo"],
    }

    if inspect_path.exists():
        data = json.loads(inspect_path.read_text(encoding="utf-8"))
        summary.update(
            {
                "table_count": data.get("table_count"),
                "compatible_stock_table_count": data.get("compatible_table_count"),
                "eligible_group_count": data.get("eligible_group_count"),
                "db_size_bytes": data.get("db_size_bytes"),
                "warnings": data.get("warnings", []),
            }
        )
    if scale_path.exists():
        scale = json.loads(scale_path.read_text(encoding="utf-8"))
        summary.update(
            {
                "estimated_samples": scale.get("estimated_samples_lookback300_predict60"),
                "total_rows_stock_groups": scale.get("total_rows_stock_groups"),
                "compatible_stock_table_count": scale.get("compatible_stock_table_count"),
            }
        )
    return summary


def list_prediction_files() -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    for directory in PREDICTION_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.csv")):
            stat = path.stat()
            files.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "directory": str(directory),
                    "size_bytes": stat.st_size,
                    "modified_at": stat.st_mtime,
                }
            )
    return files


def load_prediction_frame(file_name: str) -> pd.DataFrame:
    path = _safe_path_in_dirs(file_name)
    df = pd.read_csv(path, dtype={"symbol": str, "session": str})
    required = {"window_id", "symbol", "session", "target_timestamp", "pred_close", "actual_close"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Prediction file missing required columns: {missing}")
    for column in ["pred_close", "actual_close", "error", "abs_error", "pred_return_window", "actual_return_window"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df["target_timestamp"] = pd.to_datetime(df["target_timestamp"])
    if "asof_timestamp" in df.columns:
        df["asof_timestamp"] = pd.to_datetime(df["asof_timestamp"])
    return df


def prediction_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    error = pd.to_numeric(df.get("error", df["pred_close"] - df["actual_close"]), errors="coerce")
    abs_error = error.abs()
    actual = pd.to_numeric(df["actual_close"], errors="coerce").replace(0, np.nan)
    latest = df.sort_values(["window_id", "target_timestamp"]).groupby("window_id").tail(1)
    direction = pd.to_numeric(latest.get("direction_hit_window", pd.Series(dtype=float)), errors="coerce")
    mape = (abs_error / actual).replace([np.inf, -np.inf], np.nan).mean() * 100.0
    return {
        "rows": int(len(df)),
        "windows": int(df["window_id"].nunique()),
        "symbols": int(df["symbol"].nunique()),
        "mae": float(abs_error.mean()),
        "rmse": float(np.sqrt((error**2).mean())),
        "mape": float(0.0 if np.isnan(mape) else mape),
        "direction_accuracy": float(0.0 if direction.empty else direction.mean()),
        "avg_pred_return": float(pd.to_numeric(latest.get("pred_return_window", pd.Series(dtype=float)), errors="coerce").mean()),
        "avg_actual_return": float(pd.to_numeric(latest.get("actual_return_window", pd.Series(dtype=float)), errors="coerce").mean()),
    }


def prediction_chart_json(df: pd.DataFrame, window_id: Optional[int] = None) -> str:
    if window_id is None:
        window_id = int(df["window_id"].iloc[0])
    chart_df = df[df["window_id"] == window_id].sort_values("target_timestamp")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=chart_df["target_timestamp"],
            y=chart_df["actual_close"],
            mode="lines+markers",
            name="실제 close",
            line={"color": "#111827", "width": 2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=chart_df["target_timestamp"],
            y=chart_df["pred_close"],
            mode="lines+markers",
            name="예측 close",
            line={"color": "#dc2626", "width": 2, "dash": "dash"},
        )
    )
    title = f"STOM 실제값 vs 예측값 - window {window_id}"
    if len(chart_df):
        first = chart_df.iloc[0]
        title += f" ({first['symbol']} / {first['session']})"
    fig.update_layout(
        title=title,
        xaxis_title="시각",
        yaxis_title="가격",
        template="plotly_white",
        height=520,
        legend={"orientation": "h"},
    )
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


def topk_rows(df: pd.DataFrame, k: int = 20) -> List[Dict[str, Any]]:
    latest = df.sort_values(["window_id", "target_timestamp"]).groupby("window_id").tail(1)
    latest = latest.sort_values("pred_return_window", ascending=False).head(k)
    columns = [
        "window_id",
        "symbol",
        "session",
        "asof_timestamp",
        "pred_return_window",
        "actual_return_window",
        "direction_hit_window",
    ]
    return latest[[col for col in columns if col in latest.columns]].to_dict(orient="records")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(result) or np.isinf(result):
        return default
    return result


def _pct(numerator: float, denominator: float) -> float:
    if denominator == 0 or np.isnan(denominator):
        return 0.0
    return numerator / denominator * 100.0


def ranked_recommendations(
    df: pd.DataFrame,
    k: int = 20,
    long_only: bool = True,
    min_score: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Rank prediction windows by a live-usable Kronos score.

    The score intentionally uses predicted fields only:
    predicted window return, path consistency, and predicted path volatility.
    Actual return / hit fields are included only as backtest diagnostics.
    """

    rows: List[Dict[str, Any]] = []
    for window_id, group in df.sort_values(["window_id", "target_timestamp"]).groupby("window_id", sort=True):
        latest = group.iloc[-1]
        t0_close = _safe_float(latest.get("actual_close_t0"), _safe_float(group["actual_close"].iloc[0]))
        pred_return = _safe_float(latest.get("pred_return_window"))
        actual_return = _safe_float(latest.get("actual_return_window"))
        pred_close = pd.to_numeric(group["pred_close"], errors="coerce").dropna()
        actual_close = pd.to_numeric(group["actual_close"], errors="coerce").replace(0, np.nan)
        abs_error = pd.to_numeric(group.get("abs_error", pd.Series(dtype=float)), errors="coerce")

        if pred_close.empty:
            continue

        if pred_return >= 0:
            consistency = float((pred_close >= t0_close).mean())
        else:
            consistency = float((pred_close <= t0_close).mean())

        pred_range_pct = _pct(float(pred_close.max() - pred_close.min()), t0_close)
        realized_mape = float((abs_error / actual_close).replace([np.inf, -np.inf], np.nan).mean() * 100.0)
        if np.isnan(realized_mape):
            realized_mape = 0.0

        raw_score = 50.0 + pred_return * 5.0 + (consistency - 0.5) * 30.0 - min(pred_range_pct, 20.0) * 0.5
        if long_only and pred_return <= 0:
            raw_score -= 20.0 + min(abs(pred_return) * 3.0, 20.0)
        score = float(np.clip(raw_score, 0.0, 100.0))

        if score >= 60.0 and pred_return > 0:
            signal = "BUY_CANDIDATE"
        elif score >= 45.0:
            signal = "WATCH"
        else:
            signal = "AVOID"

        rows.append(
            {
                "window_id": int(window_id),
                "symbol": str(latest.get("symbol", "")),
                "session": str(latest.get("session", "")),
                "asof_timestamp": str(latest.get("asof_timestamp", "")),
                "kronos_score": score,
                "signal": signal,
                "pred_return_window": pred_return,
                "actual_return_window": actual_return,
                "direction_hit_window": int(_safe_float(latest.get("direction_hit_window"))),
                "prediction_consistency": consistency,
                "pred_range_pct": pred_range_pct,
                "realized_mape": realized_mape,
            }
        )

    if min_score is not None:
        rows = [row for row in rows if row["kronos_score"] >= min_score]
    rows = sorted(rows, key=lambda row: (row["kronos_score"], row["pred_return_window"]), reverse=True)
    return rows[: max(0, int(k))]


def recommendation_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "count": 0,
            "avg_score": 0.0,
            "top_score": 0.0,
            "avg_pred_return": 0.0,
            "avg_actual_return": 0.0,
            "hit_rate": 0.0,
            "buy_candidates": 0,
        }

    return {
        "count": len(rows),
        "avg_score": float(np.mean([row["kronos_score"] for row in rows])),
        "top_score": float(max(row["kronos_score"] for row in rows)),
        "avg_pred_return": float(np.mean([row["pred_return_window"] for row in rows])),
        "avg_actual_return": float(np.mean([row["actual_return_window"] for row in rows])),
        "hit_rate": float(np.mean([row["direction_hit_window"] for row in rows])),
        "buy_candidates": int(sum(row["signal"] == "BUY_CANDIDATE" for row in rows)),
    }


def _backtest_metrics(rows: List[Dict[str, Any]], label: str) -> Dict[str, Any]:
    if not rows:
        return {
            "label": label,
            "count": 0,
            "avg_score": 0.0,
            "avg_pred_return": 0.0,
            "avg_actual_return": 0.0,
            "hit_rate": 0.0,
            "win_rate": 0.0,
            "avg_realized_mape": 0.0,
            "profit_factor": 0.0,
        }

    actual_returns = [_safe_float(row.get("actual_return_window")) for row in rows]
    gross_gain = sum(value for value in actual_returns if value > 0)
    gross_loss = abs(sum(value for value in actual_returns if value < 0))
    return {
        "label": label,
        "count": len(rows),
        "avg_score": float(np.mean([row["kronos_score"] for row in rows])),
        "avg_pred_return": float(np.mean([row["pred_return_window"] for row in rows])),
        "avg_actual_return": float(np.mean(actual_returns)),
        "hit_rate": float(np.mean([row["direction_hit_window"] for row in rows])),
        "win_rate": float(np.mean([1 if value > 0 else 0 for value in actual_returns])),
        "avg_realized_mape": float(np.mean([row["realized_mape"] for row in rows])),
        "profit_factor": float(gross_gain / gross_loss) if gross_loss > 0 else float(gross_gain),
    }


def _asof_minute_bucket(asof_timestamp: str, minutes: int = 5) -> str:
    ts = pd.to_datetime(asof_timestamp, errors="coerce")
    if pd.isna(ts):
        return "unknown"
    bucket_minute = int(ts.minute // minutes * minutes)
    end_minute = bucket_minute + minutes - 1
    return f"{ts.hour:02d}:{bucket_minute:02d}-{ts.hour:02d}:{end_minute:02d}"


def _is_early_session(asof_timestamp: str, max_minute: int = 10) -> bool:
    ts = pd.to_datetime(asof_timestamp, errors="coerce")
    if pd.isna(ts):
        return False
    return int(ts.minute) <= max_minute


def _score_band(score: float) -> str:
    if score >= 70:
        return "70+"
    if score >= 60:
        return "60-70"
    if score >= 45:
        return "45-60"
    return "<45"


def _filter_label_matches(row: Dict[str, Any], filter_name: str) -> bool:
    if filter_name == "all_scored":
        return True
    if filter_name == "buy_candidate_score60":
        return row["kronos_score"] >= 60 and row["pred_return_window"] > 0
    if filter_name == "score65_consistency80":
        return row["kronos_score"] >= 65 and row["prediction_consistency"] >= 0.80
    if filter_name == "score70_pred_return_0_5":
        return row["kronos_score"] >= 70 and row["pred_return_window"] >= 0.5
    if filter_name == "stable_positive_filter":
        return (
            row["kronos_score"] >= 60
            and row["pred_return_window"] >= 0.3
            and row["prediction_consistency"] >= 0.80
            and row["pred_range_pct"] <= 2.5
        )
    if filter_name == "early_session_score60":
        return row["kronos_score"] >= 60 and _is_early_session(row["asof_timestamp"])
    raise ValueError(f"Unknown score filter: {filter_name}")


def _filter_labels(row: Dict[str, Any]) -> List[str]:
    labels = ["all_scored"]
    for filter_name in SCORE_FILTER_NAMES[1:]:
        if _filter_label_matches(row, filter_name):
            labels.append(filter_name)
    return labels


def _top_group_metrics(
    rows: List[Dict[str, Any]],
    key: str,
    label: str,
    limit: int = 10,
    min_count: int = 1,
) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(key, "")), []).append(row)

    result = []
    for group_key, group_rows in grouped.items():
        if len(group_rows) < min_count:
            continue
        metrics = _backtest_metrics(group_rows, group_key)
        metrics["segment"] = label
        result.append(metrics)
    return sorted(result, key=lambda item: (item["avg_actual_return"], item["count"]), reverse=True)[:limit]


def score_backtest_report(df: pd.DataFrame, top_k: Optional[int] = None) -> Dict[str, Any]:
    """Build score-filter and segment backtest diagnostics for prediction windows."""

    max_rows = int(df["window_id"].nunique()) if top_k is None else int(top_k)
    rows = ranked_recommendations(df, k=max_rows, long_only=False)
    for row in rows:
        row["score_band"] = _score_band(row["kronos_score"])
        row["asof_minute_bucket"] = _asof_minute_bucket(row["asof_timestamp"])

    conditions = [
        (filter_name, [row for row in rows if _filter_label_matches(row, filter_name)])
        for filter_name in SCORE_FILTER_NAMES
    ]

    return {
        "window_count": int(df["window_id"].nunique()),
        "scored_count": len(rows),
        "filters": [_backtest_metrics(condition_rows, label) for label, condition_rows in conditions],
        "segments": {
            "score_band": _top_group_metrics(rows, "score_band", "score_band", limit=10),
            "symbol": _top_group_metrics(rows, "symbol", "symbol", limit=10),
            "asof_minute_bucket": _top_group_metrics(rows, "asof_minute_bucket", "asof_minute_bucket", limit=10),
        },
    }


def recommendation_export_payload(
    df: pd.DataFrame,
    source_file: str = "",
    limit: Optional[int] = 20,
    min_score: Optional[float] = None,
    selected_filter: str = "buy_candidate_score60",
    long_only: bool = True,
) -> Dict[str, Any]:
    """Build a stable CSV/JSON adapter payload for external recommendation tools.

    Selection filters use prediction-time fields only. Diagnostic actual-return
    fields are exported for review/backtest display and must not be used as live
    filter inputs.
    """

    if selected_filter not in SCORE_FILTER_NAMES:
        raise ValueError(f"Unknown score filter: {selected_filter}")

    normalized_limit = None if limit is None else max(0, int(limit))
    all_rows = ranked_recommendations(df, k=int(df["window_id"].nunique()), long_only=long_only)
    exported_rows: List[Dict[str, Any]] = []
    for row in all_rows:
        row["score_band"] = _score_band(row["kronos_score"])
        row["asof_minute_bucket"] = _asof_minute_bucket(row["asof_timestamp"])
        labels = _filter_labels(row)
        if selected_filter and selected_filter not in labels:
            continue
        if min_score is not None and row["kronos_score"] < min_score:
            continue
        exported_rows.append(row)

    if normalized_limit is not None:
        exported_rows = exported_rows[:normalized_limit]

    records = []
    for rank, row in enumerate(exported_rows, start=1):
        labels = _filter_labels(row)
        adapter_action = "BUY" if "buy_candidate_score60" in labels else ("WATCH" if row["signal"] == "WATCH" else "AVOID")
        records.append(
            {
                "rank": rank,
                "source_file": source_file,
                "window_id": row["window_id"],
                "symbol": row["symbol"],
                "session": row["session"],
                "asof_timestamp": row["asof_timestamp"],
                "adapter_action": adapter_action,
                "signal": row["signal"],
                "kronos_score": row["kronos_score"],
                "score_band": row["score_band"],
                "pred_return_pct": row["pred_return_window"],
                "prediction_consistency": row["prediction_consistency"],
                "pred_range_pct": row["pred_range_pct"],
                "asof_minute_bucket": row["asof_minute_bucket"],
                "filter_labels": labels,
                "diagnostic_actual_return_pct": row["actual_return_window"],
                "diagnostic_direction_hit": row["direction_hit_window"],
                "diagnostic_realized_mape": row["realized_mape"],
            }
        )

    return {
        "metadata": {
            "adapter_version": "stom-kronos-score-v1",
            "source_file": source_file,
            "created_at": pd.Timestamp.utcnow().isoformat(),
            "window_count": int(df["window_id"].nunique()),
            "selected_filter": selected_filter,
            "min_score": min_score,
            "limit": normalized_limit,
            "long_only": long_only,
            "record_count": len(records),
            "fields": ADAPTER_EXPORT_FIELDS,
            "live_selection_note": "Selection fields use Kronos prediction outputs only; diagnostic_* fields are for backtest review.",
        },
        "records": records,
    }


def recommendation_export_csv(records: List[Dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ADAPTER_EXPORT_FIELDS, lineterminator="\n")
    writer.writeheader()
    for record in records:
        row = {field: record.get(field, "") for field in ADAPTER_EXPORT_FIELDS}
        row["filter_labels"] = ";".join(record.get("filter_labels", []))
        writer.writerow(row)
    return output.getvalue()
