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
