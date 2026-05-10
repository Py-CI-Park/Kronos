"""STOM tick DB -> Qlib/Kronos research pipeline helpers.

This module intentionally keeps the first implementation pilot-first:

* it reads the source SQLite database in read-only mode;
* it writes Qlib dump-ready CSV files for optional ``pyqlib`` conversion;
* it writes the pickle split format consumed by ``finetune/dataset.py``;
* it provides a lightweight Qlib-style Top-K score backtest for Kronos
  prediction CSVs.

The produced data artifacts can be large and are not meant to be committed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import pickle
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
FINETUNE_CSV_DIR = PROJECT_ROOT / "finetune_csv"
if str(FINETUNE_CSV_DIR) not in sys.path:
    sys.path.insert(0, str(FINETUNE_CSV_DIR))

from stom_tick_dataset import (  # noqa: E402
    DEFAULT_GROUP_COLUMNS,
    connect_readonly,
    list_stock_tables,
    read_stom_table_as_kline,
)


KRONOS_PICKLE_COLUMNS = ["open", "high", "low", "close", "vol", "amt"]
QLIB_CSV_FIELDS = ["open", "high", "low", "close", "volume", "amount", "money", "factor"]
SUPPORTED_FREQS = {"1s", "1min"}
SUPPORTED_SPLIT_STRATEGIES = {"session", "group"}
PYQLIB_PROVIDER_UNSUPPORTED_FREQS = {"1s"}
ExportItem = Tuple[str, str, pd.Timestamp, pd.Timestamp, pd.DataFrame]


@dataclass
class StomQlibExportConfig:
    db_path: str
    output_dir: str
    max_tables: int = 0
    tables: Optional[List[str]] = None
    lookback_window: int = 300
    predict_window: int = 60
    price_mode: str = "close_only"
    time_start: str = "090000"
    time_end: str = "093000"
    max_rows_per_group: int = 0
    max_groups: int = 0
    freq: str = "1s"
    regularize_1s: bool = False
    split_by: str = "session"
    horizon_seconds: Optional[int] = None
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15


def _clean_symbol(value: Any) -> str:
    text = str(value).strip()
    return text.zfill(6) if text.isdigit() and len(text) <= 6 else text


def _instrument_key(symbol: Any, session: Any) -> str:
    """Use symbol+session as an instrument key to prevent cross-session windows."""

    return f"KR{_clean_symbol(symbol)}_{str(session)}"


def _validate_ratios(train_ratio: float, val_ratio: float, test_ratio: float) -> None:
    total = train_ratio + val_ratio + test_ratio
    if total <= 0:
        raise ValueError("At least one split ratio must be positive.")
    if any(r < 0 for r in [train_ratio, val_ratio, test_ratio]):
        raise ValueError("Split ratios must be non-negative.")
    if not math.isclose(total, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError(f"Split ratios must sum to 1.0; got {total:.6f}")


def _resample_group(group: pd.DataFrame, freq: str) -> pd.DataFrame:
    if freq not in SUPPORTED_FREQS:
        raise ValueError(f"freq must be one of {sorted(SUPPORTED_FREQS)}")
    group = group.sort_values("timestamps").copy()
    if freq == "1s":
        return group

    # 1min aggregation keeps standard OHLCV semantics and sums flow fields.
    group["bucket"] = group["timestamps"].dt.floor("min")
    out = (
        group.groupby(["symbol", "session", "bucket"], sort=True)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
            amount=("amount", "sum"),
        )
        .reset_index()
        .rename(columns={"bucket": "timestamps"})
    )
    return out


def _split_count(total: int, train_ratio: float, val_ratio: float, test_ratio: float) -> Tuple[int, int]:
    train_end = int(total * train_ratio)
    val_end = int(total * (train_ratio + val_ratio))

    if train_ratio > 0 and train_end == 0 and total > 0:
        train_end = 1
    if val_ratio > 0 and val_end <= train_end and total > train_end:
        val_end = train_end + 1
    if test_ratio > 0 and val_end >= total and total > train_end:
        val_end = max(train_end, total - 1)
    return train_end, val_end


def _split_items(
    items: Sequence[ExportItem],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    split_by: str = "session",
) -> Dict[str, List[ExportItem]]:
    _validate_ratios(train_ratio, val_ratio, test_ratio)
    if split_by not in SUPPORTED_SPLIT_STRATEGIES:
        raise ValueError(f"split_by must be one of {sorted(SUPPORTED_SPLIT_STRATEGIES)}")

    ordered = sorted(items, key=lambda item: (item[2], item[0]))
    if split_by == "group":
        train_end, val_end = _split_count(len(ordered), train_ratio, val_ratio, test_ratio)
        return {
            "train": ordered[:train_end],
            "val": ordered[train_end:val_end],
            "test": ordered[val_end:],
        }

    sessions = sorted({session for _, session, _, _, _ in ordered})
    train_end, val_end = _split_count(len(sessions), train_ratio, val_ratio, test_ratio)
    split_sessions = {
        "train": set(sessions[:train_end]),
        "val": set(sessions[train_end:val_end]),
        "test": set(sessions[val_end:]),
    }

    return {
        split_name: [item for item in ordered if item[1] in session_set]
        for split_name, session_set in split_sessions.items()
    }


def _split_session_summary(split_items: Dict[str, List[ExportItem]]) -> Dict[str, List[str]]:
    return {
        split_name: sorted({session for _, session, _, _, _ in split_rows})
        for split_name, split_rows in split_items.items()
    }


def _session_time(session: Any, hhmmss: Optional[str]) -> Optional[pd.Timestamp]:
    if not hhmmss:
        return None
    text = str(hhmmss)
    if len(text) != 6 or not text.isdigit():
        raise ValueError(f"Expected HHMMSS time, got: {hhmmss}")
    return pd.to_datetime(f"{session}{text}", format="%Y%m%d%H%M%S", errors="raise")


def _regularize_group_to_1s(
    group: pd.DataFrame,
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Reindex a symbol/session group to a true one-second grid without leading look-ahead fill."""

    if group.empty:
        return group.copy(), {"input_rows": 0, "output_rows": 0, "inserted_rows": 0}

    ordered = group.sort_values("timestamps").drop_duplicates("timestamps", keep="last").copy()
    session = str(ordered["session"].iloc[0])
    start_ts = _session_time(session, time_start) or ordered["timestamps"].min()
    end_ts = _session_time(session, time_end) or ordered["timestamps"].max()
    start_ts = max(pd.Timestamp(start_ts), pd.Timestamp(ordered["timestamps"].min()))
    end_ts = min(pd.Timestamp(end_ts), pd.Timestamp(ordered["timestamps"].max()) if not time_end else pd.Timestamp(end_ts))
    if end_ts < start_ts:
        return ordered, {
            "input_rows": int(len(group)),
            "output_rows": int(len(ordered)),
            "inserted_rows": 0,
            "warning": "regularize_1s skipped because computed end is before start",
        }

    full_index = pd.date_range(start=start_ts, end=end_ts, freq="1s")
    indexed = ordered.set_index("timestamps").reindex(full_index)
    indexed.index.name = "timestamps"
    indexed["symbol"] = indexed["symbol"].ffill()
    indexed["session"] = indexed["session"].ffill()
    price_columns = ["open", "high", "low", "close"]
    indexed[price_columns] = indexed[price_columns].ffill()
    indexed[["volume", "amount"]] = indexed[["volume", "amount"]].fillna(0.0)
    indexed = indexed.dropna(subset=["symbol", "session", *price_columns])
    out = indexed.reset_index()
    return out[DEFAULT_GROUP_COLUMNS + ["timestamps"] + ["open", "high", "low", "close", "volume", "amount"]], {
        "input_rows": int(len(ordered)),
        "output_rows": int(len(out)),
        "inserted_rows": int(max(len(out) - len(ordered), 0)),
        "start_timestamp": None if out.empty else str(out["timestamps"].iloc[0]),
        "end_timestamp": None if out.empty else str(out["timestamps"].iloc[-1]),
    }


def _to_kronos_pickle_frame(group: pd.DataFrame) -> pd.DataFrame:
    out = group[["timestamps", "open", "high", "low", "close", "volume", "amount"]].copy()
    out = out.rename(columns={"timestamps": "datetime", "volume": "vol", "amount": "amt"})
    out["datetime"] = pd.to_datetime(out["datetime"])
    for column in KRONOS_PICKLE_COLUMNS:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna(subset=["datetime", *KRONOS_PICKLE_COLUMNS]).sort_values("datetime")
    return out.set_index("datetime")[KRONOS_PICKLE_COLUMNS]


def _to_qlib_dump_csv_frame(instrument: str, group: pd.DataFrame) -> pd.DataFrame:
    out = group[["timestamps", "open", "high", "low", "close", "volume", "amount"]].copy()
    out = out.rename(columns={"timestamps": "date"})
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    out["symbol"] = instrument
    out["money"] = pd.to_numeric(out["amount"], errors="coerce").fillna(0.0)
    out["factor"] = 1.0
    return out[["symbol", "date", *QLIB_CSV_FIELDS]]


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _format_command(command: Sequence[str]) -> str:
    return " ".join(f'"{part}"' if " " in str(part) else str(part) for part in command)


def check_qlib_environment(dump_bin_script: Optional[Path] = None) -> Dict[str, Any]:
    """Return pyqlib/dump_bin readiness without requiring pyqlib to be installed."""

    qlib_spec = importlib.util.find_spec("qlib")
    qlib_version = None
    qlib_error = None
    if qlib_spec is not None:
        try:
            import qlib  # type: ignore

            qlib_version = getattr(qlib, "__version__", "unknown")
        except Exception as exc:  # pragma: no cover - depends on local pyqlib install
            qlib_error = repr(exc)

    candidates: List[Path] = []
    if dump_bin_script is not None:
        candidates.append(Path(dump_bin_script))
    env_dump_bin = os.environ.get("QLIB_DUMP_BIN_SCRIPT")
    if env_dump_bin:
        candidates.append(Path(env_dump_bin))
    if qlib_spec is not None and qlib_spec.origin:
        qlib_origin = Path(qlib_spec.origin).resolve()
        candidates.extend(
            [
                qlib_origin.parent / "scripts" / "dump_bin.py",
                qlib_origin.parent.parent / "scripts" / "dump_bin.py",
            ]
        )
    candidates.extend(
        [
            PROJECT_ROOT / "scripts" / "dump_bin.py",
            PROJECT_ROOT / "qlib" / "scripts" / "dump_bin.py",
            PROJECT_ROOT / ".omx" / "external" / "qlib" / "scripts" / "dump_bin.py",
        ]
    )
    existing_script = next((path.resolve() for path in candidates if path.exists()), None)

    return {
        "qlib_installed": qlib_spec is not None and qlib_error is None,
        "qlib_origin": None if qlib_spec is None else qlib_spec.origin,
        "qlib_version": qlib_version,
        "qlib_error": qlib_error,
        "dump_bin_script_found": existing_script is not None,
        "dump_bin_script": None if existing_script is None else str(existing_script),
        "recommended_install_command": "python -m pip install pyqlib",
        "recommended_dump_bin_source": "Clone microsoft/qlib or point --dump-bin-script to qlib/scripts/dump_bin.py",
    }


def build_dump_bin_command(
    csv_path: Path,
    qlib_dir: Path,
    dump_bin_script: Optional[Path] = None,
    include_fields: Optional[Sequence[str]] = None,
    date_field_name: str = "date",
    symbol_field_name: str = "symbol",
    freq: Optional[str] = None,
) -> List[str]:
    script = Path(dump_bin_script) if dump_bin_script else Path("scripts") / "dump_bin.py"
    command = [
        sys.executable,
        str(script),
        "dump_all",
        "--data_path",
        str(csv_path),
        "--qlib_dir",
        str(qlib_dir),
        "--date_field_name",
        date_field_name,
        "--symbol_field_name",
        symbol_field_name,
        "--include_fields",
        ",".join(include_fields or QLIB_CSV_FIELDS),
    ]
    if freq:
        command.extend(["--freq", freq])
    return command


def run_dump_bin_from_report(
    export_report_path: Path,
    qlib_dir: Optional[Path] = None,
    dump_bin_script: Optional[Path] = None,
    execute: bool = False,
    freq: Optional[str] = None,
) -> Dict[str, Any]:
    report = json.loads(Path(export_report_path).read_text(encoding="utf-8"))
    csv_path = Path(report["qlib_csv_dir"])
    target_dir = Path(qlib_dir) if qlib_dir else Path(report["output_dir"]) / "qlib_bin"
    effective_freq = freq or report.get("config", {}).get("freq")
    command = build_dump_bin_command(
        csv_path=csv_path,
        qlib_dir=target_dir,
        dump_bin_script=dump_bin_script,
        include_fields=QLIB_CSV_FIELDS,
        freq=effective_freq,
    )
    result: Dict[str, Any] = {
        "mode": "qlib_dump_bin",
        "export_report_path": str(export_report_path),
        "csv_path": str(csv_path),
        "qlib_dir": str(target_dir),
        "command": command,
        "command_text": _format_command(command),
        "executed": execute,
    }
    if not execute:
        result["status"] = "dry_run"
        return result

    script = Path(command[1])
    if not script.is_absolute():
        script = PROJECT_ROOT / script
        command[1] = str(script)
        result["command"] = command
        result["command_text"] = _format_command(command)
    if not script.exists():
        raise FileNotFoundError(
            f"dump_bin.py not found: {script}. "
            "Install/clone microsoft/qlib and pass --dump-bin-script, or run qlib-env-check first."
        )
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    result.update(
        {
            "returncode": completed.returncode,
            "stdout": stdout[-4000:],
            "stderr": stderr[-4000:],
            "status": "ok" if completed.returncode == 0 else "failed",
        }
    )
    if completed.returncode != 0:
        raise RuntimeError(f"dump_bin failed with exit code {completed.returncode}: {stderr[-1000:]}")
    return result


def smoke_qlib_provider(provider_uri: Path, region: str = "cn", freq: str = "day") -> Dict[str, Any]:
    """Initialize pyqlib provider and load a small calendar sample."""

    if freq.lower() in PYQLIB_PROVIDER_UNSUPPORTED_FREQS:
        raise ValueError(
            "pyqlib provider does not support second-level freq such as '1s'. "
            "Use --freq 1min for Qlib provider smoke, or use the generated "
            "processed_datasets pickles for Kronos 1-second fine-tuning."
        )

    try:
        import qlib  # type: ignore
        from qlib.config import REG_CN, REG_US  # type: ignore
        from qlib.data import D  # type: ignore
    except Exception as exc:
        raise RuntimeError("pyqlib is not installed or cannot be imported. Run: python -m pip install pyqlib") from exc

    region_map = {"cn": REG_CN, "us": REG_US}
    qlib.init(provider_uri=str(provider_uri), region=region_map.get(region.lower(), REG_CN))
    calendar = D.calendar(freq=freq)
    sample = [str(item) for item in calendar[: min(len(calendar), 5)]]
    return {
        "mode": "qlib_provider_smoke",
        "provider_uri": str(provider_uri),
        "region": region,
        "freq": freq,
        "calendar_count": int(len(calendar)),
        "calendar_sample": sample,
    }


def export_stom_to_qlib(config: StomQlibExportConfig) -> Dict[str, Any]:
    """Export STOM DB rows to Qlib dump-ready CSV and Kronos QlibDataset pickles."""

    predict_window = config.horizon_seconds if config.horizon_seconds is not None else config.predict_window
    if config.horizon_seconds is not None and config.freq != "1s":
        raise ValueError("--horizon-seconds is only valid for --freq 1s exports.")
    if config.regularize_1s and config.freq != "1s":
        raise ValueError("--regularize-1s is only valid with --freq 1s.")
    min_rows = config.lookback_window + predict_window + 1
    output_dir = Path(config.output_dir)
    qlib_csv_dir = output_dir / "qlib_csv"
    processed_dir = output_dir / "processed_datasets"
    meta_dir = output_dir / "meta"
    for directory in [qlib_csv_dir, processed_dir, meta_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    conn = connect_readonly(config.db_path)
    items: List[ExportItem] = []
    table_reports: List[Dict[str, Any]] = []
    warnings: List[str] = []
    grid_summary = {"regularized_groups": 0, "inserted_rows": 0}
    try:
        selected_tables = list(config.tables) if config.tables else list_stock_tables(conn, max_tables=None)
        if config.max_tables and config.max_tables > 0:
            selected_tables = selected_tables[: config.max_tables]

        for table in selected_tables:
            if config.max_groups and len(items) >= config.max_groups:
                break
            try:
                frame, mapping = read_stom_table_as_kline(
                    conn,
                    table,
                    price_mode=config.price_mode,
                    time_start=config.time_start,
                    time_end=config.time_end,
                )
                mapping_warnings = mapping.get("warnings", [])
                warnings.extend(str(w) for w in mapping_warnings)
                written_groups = 0
                written_rows = 0
                skipped_groups = 0
                table_grid_inserted_rows = 0
                for (symbol, session), group in frame.groupby(DEFAULT_GROUP_COLUMNS, sort=True):
                    if config.max_groups and len(items) >= config.max_groups:
                        break
                    group = _resample_group(group, config.freq)
                    if config.regularize_1s:
                        group, group_grid = _regularize_group_to_1s(
                            group,
                            time_start=config.time_start,
                            time_end=config.time_end,
                        )
                        grid_summary["regularized_groups"] += 1
                        grid_summary["inserted_rows"] += int(group_grid.get("inserted_rows", 0))
                        table_grid_inserted_rows += int(group_grid.get("inserted_rows", 0))
                    if config.max_rows_per_group and config.max_rows_per_group > 0:
                        group = group.head(config.max_rows_per_group)
                    if len(group) < min_rows:
                        skipped_groups += 1
                        continue

                    instrument = _instrument_key(symbol, session)
                    group = group.sort_values("timestamps").reset_index(drop=True)
                    qlib_frame = _to_qlib_dump_csv_frame(instrument, group)
                    qlib_frame.to_csv(qlib_csv_dir / f"{instrument}.csv", index=False, encoding="utf-8")

                    pickle_frame = _to_kronos_pickle_frame(group)
                    if len(pickle_frame) < min_rows:
                        skipped_groups += 1
                        continue

                    items.append(
                        (
                            instrument,
                            str(session),
                            pickle_frame.index.min(),
                            pickle_frame.index.max(),
                            pickle_frame,
                        )
                    )
                    written_groups += 1
                    written_rows += len(pickle_frame)

                table_reports.append(
                    {
                        "table": table,
                        "written_groups": written_groups,
                        "written_rows": written_rows,
                        "skipped_groups": skipped_groups,
                        "regularized_inserted_rows": table_grid_inserted_rows,
                        "mapping": {k: v for k, v in mapping.items() if k != "warnings"},
                    }
                )
            except Exception as exc:  # pragma: no cover - real DB diagnostics
                table_reports.append({"table": table, "error": str(exc)})
    finally:
        conn.close()

    if not items:
        raise ValueError(
            f"No STOM groups were exportable for min_rows={min_rows}. "
            "Lower lookback/predict windows or export more rows."
        )

    split_items = _split_items(items, config.train_ratio, config.val_ratio, config.test_ratio, split_by=config.split_by)
    split_sessions = _split_session_summary(split_items)
    split_counts: Dict[str, Dict[str, int]] = {}
    for split_name, split_rows in split_items.items():
        split_payload = {instrument: frame for instrument, _, _, _, frame in split_rows}
        with (processed_dir / f"{split_name}_data.pkl").open("wb") as f:
            pickle.dump(split_payload, f)
        split_counts[split_name] = {
            "groups": len(split_rows),
            "rows": int(sum(len(frame) for _, _, _, _, frame in split_rows)),
            "sessions": len(split_sessions.get(split_name, [])),
        }

    calendar = sorted({ts for _, _, _, _, frame in items for ts in frame.index})
    calendar_path = meta_dir / f"calendar_{config.freq}.txt"
    calendar_path.write_text("\n".join(ts.strftime("%Y-%m-%d %H:%M:%S") for ts in calendar) + "\n", encoding="utf-8")

    instruments_path = meta_dir / "instruments_all.txt"
    instruments_path.write_text(
        "\n".join(
            f"{instrument}\t{start.strftime('%Y-%m-%d %H:%M:%S')}\t{end.strftime('%Y-%m-%d %H:%M:%S')}"
            for instrument, _, start, end, _ in sorted(items, key=lambda item: item[0])
        )
        + "\n",
        encoding="utf-8",
    )

    dump_command = (
        "python scripts/dump_bin.py dump_all "
        f"--data_path {qlib_csv_dir.as_posix()} "
        f"--qlib_dir {(output_dir / 'qlib_bin').as_posix()} "
        "--date_field_name date --symbol_field_name symbol "
        f"--include_fields {','.join(QLIB_CSV_FIELDS)} "
        f"--freq {config.freq}"
    )
    (meta_dir / "qlib_dump_bin_command.txt").write_text(dump_command + "\n", encoding="utf-8")

    report = {
        "mode": "stom_to_qlib_export",
        "config": {**asdict(config), "effective_predict_window": predict_window},
        "min_rows_per_group": min_rows,
        "split_strategy": config.split_by,
        "output_dir": str(output_dir),
        "qlib_csv_dir": str(qlib_csv_dir),
        "processed_dataset_dir": str(processed_dir),
        "calendar_path": str(calendar_path),
        "instruments_path": str(instruments_path),
        "qlib_dump_bin_command": dump_command,
        "selected_table_count": len(config.tables) if config.tables else (config.max_tables or "all"),
        "exported_group_count": len(items),
        "exported_row_count": int(sum(len(frame) for _, _, _, _, frame in items)),
        "split_counts": split_counts,
        "split_sessions": split_sessions,
        "grid_summary": grid_summary,
        "warnings": sorted(set(warnings)),
        "tables": table_reports,
    }
    _write_json(output_dir / "stom_qlib_export_report.json", report)
    return report


def _pct_max_drawdown(equity: Sequence[float]) -> float:
    peak = -float("inf")
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, value / peak - 1.0)
    return float(max_dd * 100.0)


def _load_prediction_latest(prediction_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(prediction_csv, dtype={"symbol": str, "session": str}, encoding="utf-8-sig")
    required = {"window_id", "symbol", "session", "asof_timestamp", "pred_return_window", "actual_return_window"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Prediction CSV missing required columns: {missing}")
    df["asof_timestamp"] = pd.to_datetime(df["asof_timestamp"], errors="coerce")
    sort_columns = ["window_id"]
    if "horizon_step" in df.columns:
        sort_columns.append("horizon_step")
    latest = df.sort_values(sort_columns).groupby("window_id").tail(1).copy()
    for column in ["pred_return_window", "actual_return_window", "direction_hit_window"]:
        if column in latest.columns:
            latest[column] = pd.to_numeric(latest[column], errors="coerce")
    latest = latest.dropna(subset=["asof_timestamp", "pred_return_window", "actual_return_window"])
    return latest


def run_score_backtest(
    prediction_csv: Path,
    output_dir: Path,
    top_k: int = 10,
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
    score_column: str = "pred_return_window",
) -> Dict[str, Any]:
    """Run a deterministic Qlib-style Top-K backtest from prediction CSV scores."""

    if top_k <= 0:
        raise ValueError("top_k must be positive")
    latest = _load_prediction_latest(prediction_csv)
    if score_column not in latest.columns:
        raise ValueError(f"score_column not found: {score_column}")

    output_dir.mkdir(parents=True, exist_ok=True)
    cost_pct = (cost_bps + slippage_bps) * 0.01
    rows: List[Dict[str, Any]] = []
    curve_rows: List[Dict[str, Any]] = []
    previous_symbols: set[str] = set()
    equity = 1.0
    equity_values = [equity]

    for timestamp, group in latest.groupby("asof_timestamp", sort=True):
        selected = group.sort_values(score_column, ascending=False).head(top_k).copy()
        if selected.empty:
            continue
        symbols = set(selected["symbol"].astype(str))
        gross = float(selected["actual_return_window"].mean())
        net = gross - cost_pct
        hit_rate = float((selected["actual_return_window"] > 0).mean())
        direction_hit = (
            float(selected["direction_hit_window"].mean())
            if "direction_hit_window" in selected.columns
            else float("nan")
        )
        turnover = 1.0
        if previous_symbols:
            turnover = 1.0 - len(symbols & previous_symbols) / max(len(symbols), 1)
        previous_symbols = symbols
        equity *= 1.0 + net / 100.0
        equity_values.append(equity)
        curve_rows.append(
            {
                "asof_timestamp": pd.Timestamp(timestamp).isoformat(),
                "gross_return_pct": gross,
                "net_return_pct": net,
                "hit_rate": hit_rate,
                "direction_hit": direction_hit,
                "turnover": turnover,
                "equity": equity,
            }
        )
        for rank, (_, row) in enumerate(selected.iterrows(), start=1):
            hit_value = row.get("direction_hit_window") if "direction_hit_window" in row else None
            direction_hit = None if pd.isna(hit_value) else int(hit_value)
            rows.append(
                {
                    "asof_timestamp": pd.Timestamp(timestamp).isoformat(),
                    "rank": rank,
                    "symbol": row.get("symbol"),
                    "session": row.get("session"),
                    "window_id": int(row.get("window_id")),
                    "score": float(row[score_column]),
                    "actual_return_pct": float(row["actual_return_window"]),
                    "net_return_pct": float(row["actual_return_window"] - cost_pct),
                    "direction_hit": direction_hit,
                }
            )

    if not curve_rows:
        raise ValueError("No backtest periods were generated.")

    curve = pd.DataFrame(curve_rows)
    trades = pd.DataFrame(rows)
    returns = curve["net_return_pct"].astype(float)
    sharpe = 0.0
    if len(returns) > 1 and returns.std(ddof=1) > 0:
        sharpe = float((returns.mean() / returns.std(ddof=1)) * math.sqrt(len(returns)))

    metrics = {
        "mode": "qlib_style_topk",
        "source_prediction_csv": str(prediction_csv),
        "top_k": top_k,
        "score_column": score_column,
        "cost_bps": cost_bps,
        "slippage_bps": slippage_bps,
        "period_count": int(len(curve)),
        "trade_count": int(len(trades)),
        "avg_trades_per_period": float(len(trades) / len(curve)),
        "avg_gross_return_pct": float(curve["gross_return_pct"].mean()),
        "avg_net_return_pct": float(curve["net_return_pct"].mean()),
        "hit_rate": float((trades["actual_return_pct"] > 0).mean()),
        "direction_hit_rate": float(pd.to_numeric(trades["direction_hit"], errors="coerce").mean()),
        "avg_turnover": float(curve["turnover"].mean()),
        "cumulative_return_pct": float((equity - 1.0) * 100.0),
        "max_drawdown_pct": _pct_max_drawdown(equity_values),
        "sharpe_per_period": sharpe,
    }
    warnings: List[str] = []
    if metrics["avg_trades_per_period"] < top_k:
        warnings.append(
            "Average selected trades per period is below top_k. "
            "For true Qlib cross-sectional Top-K, generate predictions for multiple symbols at the same asof_timestamp."
        )
    payload = {
        "metrics": metrics,
        "warnings": warnings,
        "curve": curve_rows,
        "top_trades": rows[: min(len(rows), 500)],
    }
    stem = prediction_csv.stem
    json_path = output_dir / f"{stem}.qlib_topk{top_k}.json"
    curve_path = output_dir / f"{stem}.qlib_topk{top_k}.curve.csv"
    trades_path = output_dir / f"{stem}.qlib_topk{top_k}.trades.csv"
    _write_json(json_path, payload)
    curve.to_csv(curve_path, index=False, encoding="utf-8")
    trades.to_csv(trades_path, index=False, encoding="utf-8")
    return {
        **payload,
        "artifact_paths": {
            "json": str(json_path),
            "curve_csv": str(curve_path),
            "trades_csv": str(trades_path),
        },
    }


def _parse_tables(raw: Optional[str]) -> Optional[List[str]]:
    if not raw:
        return None
    return [part.strip() for part in raw.split(",") if part.strip()]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="STOM -> Qlib/Kronos pilot pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export", help="Export STOM DB to Qlib dump-ready CSV and QlibDataset pickles")
    export.add_argument("--db", required=True)
    export.add_argument("--output-dir", required=True)
    export.add_argument("--max-tables", type=int, default=0)
    export.add_argument("--tables", default=None, help="Comma-separated table list")
    export.add_argument("--lookback-window", type=int, default=300)
    export.add_argument("--predict-window", type=int, default=60)
    export.add_argument("--price-mode", choices=["db_ohlc", "close_only"], default="close_only")
    export.add_argument("--time-start", default="090000")
    export.add_argument("--time-end", default="093000")
    export.add_argument("--max-rows-per-group", type=int, default=0)
    export.add_argument("--max-groups", type=int, default=0)
    export.add_argument("--freq", choices=sorted(SUPPORTED_FREQS), default="1s")
    export.add_argument(
        "--regularize-1s",
        action="store_true",
        help="Reindex 1-second exports to a strict 1-second grid. Prices forward-fill; missing volume/amount become 0.",
    )
    export.add_argument(
        "--split-by",
        choices=sorted(SUPPORTED_SPLIT_STRATEGIES),
        default="session",
        help="Split train/val/test by chronological session dates by default to reduce time-series leakage.",
    )
    export.add_argument(
        "--horizon-seconds",
        type=int,
        default=None,
        help="For 1-second exports, use this exact second horizon as the effective predict window.",
    )
    export.add_argument("--train-ratio", type=float, default=0.70)
    export.add_argument("--val-ratio", type=float, default=0.15)
    export.add_argument("--test-ratio", type=float, default=0.15)

    backtest = sub.add_parser("score-backtest", help="Run Qlib-style Top-K backtest from Kronos prediction CSV")
    backtest.add_argument("--prediction-csv", required=True)
    backtest.add_argument("--output-dir", default="webui/qlib_backtests")
    backtest.add_argument("--top-k", type=int, default=10)
    backtest.add_argument("--cost-bps", type=float, default=0.0)
    backtest.add_argument("--slippage-bps", type=float, default=0.0)
    backtest.add_argument("--score-column", default="pred_return_window")

    env_check = sub.add_parser("qlib-env-check", help="Check optional pyqlib/dump_bin readiness")
    env_check.add_argument("--dump-bin-script", default=None)

    dump_bin = sub.add_parser("dump-bin", help="Build or execute Qlib dump_bin command from an export report")
    dump_bin.add_argument("--export-report", required=True)
    dump_bin.add_argument("--qlib-dir", default=None)
    dump_bin.add_argument("--dump-bin-script", default=None)
    dump_bin.add_argument("--freq", default=None)
    dump_bin.add_argument("--execute", action="store_true")

    provider = sub.add_parser("provider-smoke", help="Initialize pyqlib provider and read a calendar sample")
    provider.add_argument("--provider-uri", required=True)
    provider.add_argument("--region", choices=["cn", "us"], default="cn")
    provider.add_argument("--freq", default="day")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.command == "export":
        report = export_stom_to_qlib(
            StomQlibExportConfig(
                db_path=args.db,
                output_dir=args.output_dir,
                max_tables=args.max_tables,
                tables=_parse_tables(args.tables),
                lookback_window=args.lookback_window,
                predict_window=args.predict_window,
                price_mode=args.price_mode,
                time_start=args.time_start,
                time_end=args.time_end,
                max_rows_per_group=args.max_rows_per_group,
                max_groups=args.max_groups,
                freq=args.freq,
                regularize_1s=args.regularize_1s,
                split_by=args.split_by,
                horizon_seconds=args.horizon_seconds,
                train_ratio=args.train_ratio,
                val_ratio=args.val_ratio,
                test_ratio=args.test_ratio,
            )
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "score-backtest":
        result = run_score_backtest(
            prediction_csv=Path(args.prediction_csv),
            output_dir=Path(args.output_dir),
            top_k=args.top_k,
            cost_bps=args.cost_bps,
            slippage_bps=args.slippage_bps,
            score_column=args.score_column,
        )
        print(
            json.dumps(
                result["metrics"]
                | {"warnings": result.get("warnings", []), "artifact_paths": result["artifact_paths"]},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "qlib-env-check":
        result = check_qlib_environment(Path(args.dump_bin_script) if args.dump_bin_script else None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "dump-bin":
        result = run_dump_bin_from_report(
            export_report_path=Path(args.export_report),
            qlib_dir=Path(args.qlib_dir) if args.qlib_dir else None,
            dump_bin_script=Path(args.dump_bin_script) if args.dump_bin_script else None,
            execute=args.execute,
            freq=args.freq,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "provider-smoke":
        result = smoke_qlib_provider(Path(args.provider_uri), region=args.region, freq=args.freq)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
