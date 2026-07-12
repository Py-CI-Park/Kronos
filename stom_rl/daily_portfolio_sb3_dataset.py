"""Bridge official D3 daily predictions into generic PortfolioEnv candidates.

This module is intentionally narrow: it accepts only frozen/authoritative daily D3
prediction artifacts, re-derives the close-to-next-close label from the read-only
D2 daily OHLCV SQLite lineage, and emits a research-only candidate CSV accepted by
``PortfolioEnv`` without relying on its legacy fill-price fallback.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from .daily_ohlcv_db import connect_readonly, validate_daily_table_name

DATASET_SCHEMA_VERSION = "daily_portfolio_sb3_dataset.v1"
CANDIDATE_FILENAME = "daily_portfolio_sb3_candidates.csv"
MANIFEST_FILENAME = "daily_portfolio_sb3_dataset_manifest.json"
SAFE_RUN_RE = re.compile(r"^[0-9A-Za-z_.-]+$")
REQUIRED_CANDIDATE_COLUMNS = [
    "timestamp",
    "symbol",
    "rank_score",
    "price",
    "fill_price",
    "fillable",
    "split",
    "future_return_1d",
    "table",
    "code",
    "source_prediction_run_id",
]
_ALLOWED_SPLITS = {"train", "val", "test"}


class DailyPortfolioSb3DatasetError(ValueError):
    """Raised when official D3 lineage cannot be converted fail-closed."""


@dataclass(frozen=True)
class DailyPortfolioSb3DatasetConfig:
    prediction_run_dir: Path | str
    rank_score_column: str = "score_supervised_linear_ranker"
    expected_cost_bps: float = 23.0



@dataclass(frozen=True)
class DailyPortfolioSb3Dataset:
    candidates: pd.DataFrame
    manifest: Mapping[str, Any]
    prediction_run_dir: Path
    dataset_manifest_path: Path
    daily_db_path: Path
    daily_db_sha256: str


@dataclass(frozen=True)
class _Lineage:
    run_dir: Path
    manifest_path: Path
    predictions_path: Path
    baseline_metrics_path: Path
    verdict_path: Path
    preregistration_path: Path
    manifest: Mapping[str, Any]
    predictions: Sequence[Mapping[str, Any]]
    baseline_metrics: Sequence[Mapping[str, Any]]
    verdict: Mapping[str, Any]
    dataset_manifest_path: Path
    dataset_manifest: Mapping[str, Any]
    daily_db_path: Path
    daily_db_sha256: str
    hashes: Mapping[str, str]
    declared_hashes: Mapping[str, str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DailyPortfolioSb3DatasetError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise DailyPortfolioSb3DatasetError(f"{label} must be a JSON object: {path}")
    return value


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise DailyPortfolioSb3DatasetError(f"CSV has no header: {path}")
        return [dict(row) for row in reader]


def _safe_float(value: Any, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DailyPortfolioSb3DatasetError(f"{label} is not numeric") from exc
    if not math.isfinite(result):
        raise DailyPortfolioSb3DatasetError(f"{label} is not finite")
    return result


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _resolve_existing_child(run_dir: Path, filename: str) -> Path:
    path = (run_dir / filename).resolve()
    try:
        path.relative_to(run_dir)
    except ValueError as exc:
        raise DailyPortfolioSb3DatasetError(f"Artifact escapes prediction run dir: {filename}") from exc
    if not path.exists() or not path.is_file():
        raise DailyPortfolioSb3DatasetError(f"Missing required artifact: {path}")
    if path.is_symlink():
        raise DailyPortfolioSb3DatasetError(f"Symlink artifact is not allowed: {path}")
    return path


def _resolve_declared_path(value: Any, *, base_dir: Path, label: str, filename: str | None = None) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise DailyPortfolioSb3DatasetError(f"Missing {label}")
    raw = Path(value)
    candidates = [raw] if raw.is_absolute() else [base_dir / raw]
    for candidate in candidates:
        path = candidate.resolve()
        if filename and path.name != filename:
            continue
        if path.exists() and path.is_file():
            if path.is_symlink():
                raise DailyPortfolioSb3DatasetError(f"Symlink {label} is not allowed: {path}")
            return path
    raise DailyPortfolioSb3DatasetError(f"Missing declared {label}: {value}")


def _declared_hash(manifest: Mapping[str, Any], key: str) -> str | None:
    hashes = manifest.get("artifact_hashes")
    if isinstance(hashes, Mapping) and isinstance(hashes.get(key), str):
        return str(hashes[key])
    alternates = [f"{key}_sha256", f"{key}_sha", f"{key}_file_sha256"]
    for alt in alternates:
        if isinstance(manifest.get(alt), str):
            return str(manifest[alt])
    return None
def _preregistration_candidate(manifest: Mapping[str, Any], run_dir: Path) -> tuple[Path, str]:
    path_value = None
    for key in ("prereg_doc", "prereg_path", "preregistration_doc", "preregistration_path"):
        if isinstance(manifest.get(key), str) and str(manifest[key]).strip():
            path_value = manifest[key]
            break
    path = _resolve_declared_path(
        path_value,
        base_dir=run_dir,
        label="preregistration document",
    )
    declared_hash = None
    for key in ("prereg_doc_sha256", "prereg_sha256", "preregistration_sha256"):
        if isinstance(manifest.get(key), str) and str(manifest[key]).strip():
            declared_hash = str(manifest[key])
            break
    actual_hash = _sha256_file(path)
    _require_hash(actual_hash, declared_hash, "preregistration document")
    return path, actual_hash




def _require_hash(actual: str, declared: str | None, label: str) -> None:
    if not declared:
        raise DailyPortfolioSb3DatasetError(f"Missing declared SHA-256 for {label}")
    if str(declared).lower() != actual.lower():
        raise DailyPortfolioSb3DatasetError(f"SHA-256 mismatch for {label}")


def _truthy(value: Any) -> bool:
    return value is True or value in {1, "1", "true", "True", "TRUE", "yes", "YES"}


def _validate_manifest_authority(manifest: Mapping[str, Any], *, expected_cost_bps: float, require_authoritative: bool) -> None:
    if str(manifest.get("stage") or manifest.get("pipeline_stage") or "").upper() not in {"D3", "DAILY_D3", "DAILY_PREDICTION_D3"}:
        raise DailyPortfolioSb3DatasetError("Prediction manifest is not D3 stage")
    if str(manifest.get("status") or "").lower() not in {"completed", "complete", "completed_research_only"}:
        raise DailyPortfolioSb3DatasetError("Prediction manifest status is not completed")
    if require_authoritative and not _truthy(manifest.get("authoritative")):
        raise DailyPortfolioSb3DatasetError("Prediction manifest is not authoritative")
    if manifest.get("schema_version") in (None, ""):
        raise DailyPortfolioSb3DatasetError("Prediction manifest missing schema_version")
    run_id = str(manifest.get("run_id") or "").strip()
    if not run_id or not SAFE_RUN_RE.match(run_id) or run_id in {".", ".."}:
        raise DailyPortfolioSb3DatasetError("Prediction manifest run_id is missing or unsafe")
    primary = manifest.get("primary_cost_bps", manifest.get("cost_assumption_round_trip_bp"))
    if primary is None:
        primary = manifest.get("expected_cost_bps")
    if abs(_safe_float(primary, label="primary cost bps") - float(expected_cost_bps)) > 1e-9:
        raise DailyPortfolioSb3DatasetError("Prediction manifest primary cost is not 23bp")

    controls: set[float] = set()
    for key in ("cost_controls_bps", "cost_sensitivity_bp", "cost_sensitivity_bps"):
        value = manifest.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            controls.update(float(_safe_float(item, label=f"{key} item")) for item in value)
    scenarios = manifest.get("cost_scenarios")
    if isinstance(scenarios, Sequence) and not isinstance(scenarios, (str, bytes)):
        for item in scenarios:
            if isinstance(item, Mapping):
                cost = item.get("cost_bps", item.get("round_trip_bps"))
                if cost is not None:
                    controls.add(float(_safe_float(cost, label="cost_scenarios cost")))
            else:
                controls.add(float(_safe_float(item, label="cost_scenarios item")))
    required = {0.0, float(expected_cost_bps), float(expected_cost_bps) * 2.0}
    if not required.issubset(controls | {float(expected_cost_bps)}):
        raise DailyPortfolioSb3DatasetError("Prediction manifest missing 0/23/46bp cost controls")


def _validate_verdict(verdict: Mapping[str, Any]) -> None:
    if verdict.get("schema_version") in (None, ""):
        raise DailyPortfolioSb3DatasetError("Verdict missing schema_version")
    status = str(verdict.get("status") or "").lower()
    if status not in {"watch", "completed", "complete", "pass"}:
        raise DailyPortfolioSb3DatasetError("Verdict status is not official WATCH/completed")
    if verdict.get("model_build_allowed") is not False:
        raise DailyPortfolioSb3DatasetError("Verdict must keep model_build_allowed=false for research-only lock")


def _validate_baseline_metrics(metrics: Sequence[Mapping[str, Any]], *, expected_cost_bps: float) -> None:
    if not metrics:
        raise DailyPortfolioSb3DatasetError("baseline_metrics.json has no metrics")
    strategies = {str(row.get("strategy") or "") for row in metrics if isinstance(row, Mapping)}
    required = {"no_trade_cash", "shuffle_control", "equal_weight_topk_momentum"}
    if not required.issubset(strategies):
        raise DailyPortfolioSb3DatasetError("Baseline metrics missing no-trade/shuffle/momentum controls")
    primary_strategies: set[str] = set()
    primary_rule_present = False
    for row in metrics:
        if not isinstance(row, Mapping):
            raise DailyPortfolioSb3DatasetError("Baseline metric row is not an object")
        cost_value = None
        for key in ("cost_bps", "round_trip_cost_bps", "cost_round_trip_bp", "cost_assumption_round_trip_bp"):
            if row.get(key) not in (None, ""):
                cost_value = float(_safe_float(row[key], label="baseline metric cost"))
                break
        if cost_value is None or abs(cost_value - float(expected_cost_bps)) > 1e-9:
            continue
        strategy = str(row.get("strategy") or "")
        primary_strategies.add(strategy)
        if str(row.get("strategy_family") or "") == "rule_baseline" and strategy != "equal_weight_topk_momentum":
            primary_rule_present = True
    if not required.issubset(primary_strategies) or not primary_rule_present:
        raise DailyPortfolioSb3DatasetError("Baseline metrics missing 23bp no-trade/shuffle/momentum/RULE rows")


def _dataset_manifest_candidate(manifest: Mapping[str, Any], run_dir: Path) -> Path:
    candidates: list[Any] = [
        manifest.get("dataset_manifest_path"),
        manifest.get("source_dataset_manifest_path"),
        manifest.get("d2_dataset_manifest_path"),
    ]
    lineage = manifest.get("d2_dataset_lineage") or manifest.get("dataset_lineage")
    if isinstance(lineage, Mapping):
        candidates.extend([lineage.get("dataset_manifest_path"), lineage.get("manifest_path")])
    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, Mapping):
        candidates.extend([artifacts.get("dataset_manifest"), artifacts.get("d2_dataset_manifest")])
    for value in candidates:
        if value:
            return _resolve_declared_path(value, base_dir=run_dir, label="D2 dataset manifest", filename="dataset_manifest.json")
    raise DailyPortfolioSb3DatasetError("Prediction manifest missing D2 dataset manifest path")


def _declared_dataset_sha(manifest: Mapping[str, Any]) -> str | None:
    for key in ("dataset_manifest_sha256", "dataset_manifest_sha", "d2_dataset_manifest_sha256", "source_manifest_sha256"):
        if isinstance(manifest.get(key), str):
            return str(manifest[key])
    lineage = manifest.get("d2_dataset_lineage") or manifest.get("dataset_lineage")
    if isinstance(lineage, Mapping):
        for key in ("dataset_manifest_sha256", "manifest_sha256", "manifest_sha"):
            if isinstance(lineage.get(key), str):
                return str(lineage[key])
    return None


def _validate_dataset_manifest(dataset_manifest: Mapping[str, Any]) -> tuple[Path, str]:
    if dataset_manifest.get("split_chronology_status") != "PASS":
        raise DailyPortfolioSb3DatasetError("D2 split chronology is not PASS")
    split_policy = dataset_manifest.get("split_policy")
    if not isinstance(split_policy, Mapping) or "chronological" not in str(split_policy.get("method") or ""):
        raise DailyPortfolioSb3DatasetError("D2 split policy is not explicit chronological")
    if "test" not in str(dataset_manifest.get("split_summary") or dataset_manifest.get("row_counts") or ""):
        raise DailyPortfolioSb3DatasetError("D2 manifest does not declare a test split")
    db_value = dataset_manifest.get("daily_db_path")
    if not isinstance(db_value, str) or not db_value:
        raise DailyPortfolioSb3DatasetError("D2 manifest missing daily_db_path")
    db_path = Path(db_value).resolve()
    if not db_path.exists() or not db_path.is_file():
        raise DailyPortfolioSb3DatasetError(f"D2 daily DB path does not exist: {db_path}")
    if db_path.is_symlink():
        raise DailyPortfolioSb3DatasetError(f"D2 daily DB path is a symlink: {db_path}")
    declared_db_hash = dataset_manifest.get("daily_db_sha256") or dataset_manifest.get("daily_ohlcv_sqlite_sha256")
    if not isinstance(declared_db_hash, str) or not declared_db_hash.strip():
        raise DailyPortfolioSb3DatasetError("D2 manifest missing daily SQLite SHA-256")
    actual_db_hash = _sha256_file(db_path)
    _require_hash(actual_db_hash, declared_db_hash, "D2 daily SQLite DB")
    return db_path, actual_db_hash


def validate_daily_prediction_lineage(prediction_run_dir: Path | str, *, expected_cost_bps: float = 23.0) -> dict[str, Any]:
    """Validate official D3 artifact lineage and return loaded evidence metadata."""

    lineage = _load_lineage(prediction_run_dir, expected_cost_bps=expected_cost_bps, require_authoritative=True)
    return {
        "status": "PASS",
        "prediction_run_dir": str(lineage.run_dir),
        "prediction_manifest_sha256": lineage.hashes["prediction_manifest"],
        "prediction_artifact_hashes": dict(lineage.hashes),
        "prediction_declared_artifact_hashes": dict(lineage.declared_hashes),
        "dataset_manifest_path": str(lineage.dataset_manifest_path),
        "dataset_manifest_sha256": lineage.hashes["dataset_manifest"],
        "daily_db_path": str(lineage.daily_db_path),
        "daily_db_sha256": lineage.daily_db_sha256,
        "cost_primary_bps": float(expected_cost_bps),
        "cost_controls_bps": [0.0, float(expected_cost_bps), float(expected_cost_bps) * 2.0],
    }


def _load_lineage(prediction_run_dir: Path | str, *, expected_cost_bps: float, require_authoritative: bool) -> _Lineage:
    run_dir = Path(prediction_run_dir).resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        raise DailyPortfolioSb3DatasetError(f"Prediction run dir missing: {run_dir}")
    if run_dir.is_symlink():
        raise DailyPortfolioSb3DatasetError(f"Prediction run dir is a symlink: {run_dir}")
    manifest_path = _resolve_existing_child(run_dir, "prediction_manifest.json")
    predictions_path = _resolve_existing_child(run_dir, "predictions.csv")
    baseline_metrics_path = _resolve_existing_child(run_dir, "baseline_metrics.json")
    verdict_path = _resolve_existing_child(run_dir, "verdict.json")

    manifest = _read_json_object(manifest_path, "prediction_manifest.json")
    _validate_manifest_authority(manifest, expected_cost_bps=expected_cost_bps, require_authoritative=require_authoritative)
    predictions = _read_csv_rows(predictions_path)
    if not predictions:
        raise DailyPortfolioSb3DatasetError("predictions.csv has no rows")
    if "future_return_1d" not in predictions[0]:
        raise DailyPortfolioSb3DatasetError("predictions.csv missing future_return_1d header")
    baseline_payload = _read_json_object(baseline_metrics_path, "baseline_metrics.json")
    metrics = baseline_payload.get("metrics")
    if not isinstance(metrics, list):
        raise DailyPortfolioSb3DatasetError("baseline_metrics.json missing metrics list")
    _validate_baseline_metrics(metrics, expected_cost_bps=expected_cost_bps)
    verdict = _read_json_object(verdict_path, "verdict.json")
    _validate_verdict(verdict)
    preregistration_path, preregistration_hash = _preregistration_candidate(manifest, run_dir)

    hashes = {
        "prediction_manifest": _sha256_file(manifest_path),
        "predictions": _sha256_file(predictions_path),
        "baseline_metrics": _sha256_file(baseline_metrics_path),
        "verdict": _sha256_file(verdict_path),
        "preregistration": preregistration_hash,
    }
    declared = {
        **{key: _declared_hash(manifest, key) for key in hashes if key != "preregistration"},
        "preregistration": preregistration_hash,
    }
    for key in ("predictions", "baseline_metrics", "verdict"):
        _require_hash(hashes[key], declared.get(key), key)

    dataset_manifest_path = _dataset_manifest_candidate(manifest, run_dir)
    dataset_manifest = _read_json_object(dataset_manifest_path, "dataset_manifest.json")
    dataset_sha = _sha256_file(dataset_manifest_path)
    _require_hash(dataset_sha, _declared_dataset_sha(manifest), "D2 dataset manifest")
    daily_db_path, daily_db_sha256 = _validate_dataset_manifest(dataset_manifest)
    hashes = {**hashes, "dataset_manifest": dataset_sha, "daily_db": daily_db_sha256}
    declared = {**declared, "dataset_manifest": _declared_dataset_sha(manifest) or ""}

    return _Lineage(
        run_dir=run_dir,
        manifest_path=manifest_path,
        predictions_path=predictions_path,
        baseline_metrics_path=baseline_metrics_path,
        verdict_path=verdict_path,
        preregistration_path=preregistration_path,
        manifest=manifest,
        predictions=predictions,
        baseline_metrics=metrics,
        verdict=verdict,
        dataset_manifest_path=dataset_manifest_path,
        dataset_manifest=dataset_manifest,
        daily_db_path=daily_db_path,
        daily_db_sha256=daily_db_sha256,
        hashes=hashes,
        declared_hashes=declared,
    )


def _prediction_run_id(lineage: _Lineage) -> str:
    value = lineage.manifest.get("run_id")
    rid = str(value or "").strip()
    if not rid or not SAFE_RUN_RE.match(rid) or rid in {".", ".."}:
        raise DailyPortfolioSb3DatasetError("Prediction manifest run_id is missing or unsafe")
    return rid


def _score_columns(rows: Sequence[Mapping[str, Any]], rank_score_column: str) -> list[str]:
    first = rows[0]
    if rank_score_column not in first and "rank_score" not in first:
        raise DailyPortfolioSb3DatasetError(f"predictions.csv missing rank score column: {rank_score_column}")
    forbidden_score_cols = [
        key for key in first.keys()
        if key.startswith("score_") and any(token in key for token in ("future", "label", "target"))
    ]
    if forbidden_score_cols:
        raise DailyPortfolioSb3DatasetError(f"Forbidden non-causal score columns in predictions.csv: {forbidden_score_cols}")
    return [rank_score_column] if rank_score_column in first else ["rank_score"]


def _fetch_current_and_next_close(conn: sqlite3.Connection, *, table: str, date: str) -> tuple[float, str, float]:
    validate_daily_table_name(table)
    quoted = _quote_ident(table)
    row = conn.execute(f"SELECT date, close FROM {quoted} WHERE date >= ? ORDER BY date ASC LIMIT 2", (date,)).fetchall()
    if len(row) < 2 or str(row[0]["date"]) != date:
        raise DailyPortfolioSb3DatasetError(f"Missing current or next trading-day close for {table} {date}")
    current = _safe_float(row[0]["close"], label=f"{table} {date} close")
    next_close = _safe_float(row[1]["close"], label=f"{table} next close")
    if current <= 0 or next_close <= 0:
        raise DailyPortfolioSb3DatasetError(f"Nonpositive current or next close for {table} {date}")
    return current, str(row[1]["date"]), next_close
def _validate_candidate_split_chronology(candidates: pd.DataFrame) -> None:
    timestamps = pd.to_datetime(candidates["timestamp"], errors="coerce")
    if timestamps.isna().any():
        raise DailyPortfolioSb3DatasetError("Candidate timestamps must be parseable")
    splits = set(str(value) for value in candidates["split"])
    if splits != _ALLOWED_SPLITS:
        raise DailyPortfolioSb3DatasetError("Candidate rows must contain nonempty train, val, and test splits")
    by_split = {
        split: timestamps[candidates["split"] == split]
        for split in sorted(_ALLOWED_SPLITS)
    }
    if any(values.empty for values in by_split.values()):
        raise DailyPortfolioSb3DatasetError("Candidate rows must contain nonempty train, val, and test splits")
    if not (by_split["train"].max() < by_split["val"].min() and by_split["val"].max() < by_split["test"].min()):
        raise DailyPortfolioSb3DatasetError("Split chronology must satisfy max(train) < min(val) and max(val) < min(test)")



def build_daily_portfolio_sb3_dataset(config: DailyPortfolioSb3DatasetConfig) -> DailyPortfolioSb3Dataset:
    """Build deterministic PortfolioEnv candidate rows from official D3 predictions."""

    lineage = _load_lineage(
        config.prediction_run_dir,
        expected_cost_bps=config.expected_cost_bps,
        require_authoritative=True,
    )
    source_run_id = _prediction_run_id(lineage)
    score_columns = _score_columns(lineage.predictions, config.rank_score_column)
    output_rows: list[dict[str, Any]] = []

    with connect_readonly(lineage.daily_db_path) as conn:
        table_names = {
            str(row[0])
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
        }
        for index, row in enumerate(lineage.predictions, start=1):
            date = str(row.get("date") or row.get("timestamp") or "").strip()
            if not date:
                raise DailyPortfolioSb3DatasetError(f"Prediction row {index} missing date/timestamp")
            table = str(row.get("table") or "").strip()
            if not table:
                code = str(row.get("code") or row.get("symbol") or "").strip().zfill(6)
                table = f"A{code}"
            table = validate_daily_table_name(table)
            if table not in table_names:
                raise DailyPortfolioSb3DatasetError(f"Prediction row {index} table missing from D2 DB: {table}")
            table_suffix = table[1:]
            declared_code = str(row.get("code") or "").strip()
            declared_symbol = str(row.get("symbol") or "").strip()
            if declared_code and declared_code.zfill(6) != table_suffix:
                raise DailyPortfolioSb3DatasetError(f"Prediction row {index} code does not match table suffix")
            if declared_symbol and declared_symbol.zfill(6) != table_suffix:
                raise DailyPortfolioSb3DatasetError(f"Prediction row {index} symbol does not match table suffix")
            code = table_suffix
            if not re.fullmatch(r"\d{6}", code):
                raise DailyPortfolioSb3DatasetError(f"Prediction row {index} table suffix is not six digits")
            split = str(row.get("split") or "").strip()
            if split not in _ALLOWED_SPLITS:
                raise DailyPortfolioSb3DatasetError(f"Prediction row {index} has invalid split")
            rank_col = config.rank_score_column if config.rank_score_column in row else "rank_score"
            rank_score = _safe_float(row.get(rank_col), label=f"row {index} rank_score")
            current_close, _next_date, next_close = _fetch_current_and_next_close(conn, table=table, date=date)
            future_return = (next_close / current_close) - 1.0
            declared_return = row.get("future_return_1d")
            if declared_return in (None, ""):
                raise DailyPortfolioSb3DatasetError(f"Prediction row {index} missing future_return_1d value")
            declared = _safe_float(declared_return, label=f"row {index} future_return_1d")
            if abs(declared - future_return) > 1e-10:
                raise DailyPortfolioSb3DatasetError(f"Prediction row {index} future_return_1d inconsistent with D2 closes")
            output = {
                "timestamp": date,
                "symbol": code,
                "rank_score": rank_score,
                "price": current_close,
                "fill_price": next_close,
                "fillable": True,
                "split": split,
                "future_return_1d": future_return,
                "table": table,
                "code": code,
                "source_prediction_run_id": source_run_id,
            }
            for score_col in score_columns:
                if score_col in {rank_col, "future_return_1d", "future_direction_1d"}:
                    continue
                output[f"feature_{score_col}"] = _safe_float(row.get(score_col), label=f"row {index} {score_col}")
            output_rows.append(output)

    if not output_rows:
        raise DailyPortfolioSb3DatasetError("No candidate rows built")
    candidates = pd.DataFrame(output_rows)
    feature_cols = sorted(col for col in candidates.columns if col.startswith("feature_"))
    ordered_cols = [*REQUIRED_CANDIDATE_COLUMNS, *feature_cols]
    candidates = candidates[ordered_cols].sort_values(["timestamp", "rank_score", "symbol"], ascending=[True, False, True], kind="mergesort").reset_index(drop=True)
    _validate_candidate_split_chronology(candidates)
    if any(col.startswith("feature_future") or col == "feature_future_return_1d" for col in feature_cols):
        raise DailyPortfolioSb3DatasetError("Future return cannot be exposed as a feature")

    manifest = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "status": "COMPLETED_RESEARCH_ONLY",
        "authoritative_source_required": True,
        "research_only": True,
        "model_build_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
        "profit_claim_allowed": False,
        "primary_cost_bps": float(config.expected_cost_bps),
        "cost_controls_bps": [0.0, float(config.expected_cost_bps), float(config.expected_cost_bps) * 2.0],
        "source_prediction_run_id": source_run_id,
        "source_prediction_run_dir": str(lineage.run_dir),
        "source_prediction_manifest_sha256": lineage.hashes["prediction_manifest"],
        "source_baseline_metrics": list(lineage.baseline_metrics),
        "source_baseline_metrics_sha256": lineage.hashes["baseline_metrics"],
        "preregistration_path": str(lineage.preregistration_path),
        "preregistration_sha256": lineage.hashes["preregistration"],
        "source_artifact_hashes": dict(lineage.hashes),
        "source_declared_artifact_hashes": dict(lineage.declared_hashes),
        "d2_dataset_manifest_path": str(lineage.dataset_manifest_path),
        "d2_dataset_manifest_sha256": lineage.hashes["dataset_manifest"],
        "daily_db_path": str(lineage.daily_db_path),
        "daily_db_sha256": lineage.daily_db_sha256,
        "d2_daily_db_sha256": lineage.daily_db_sha256,
        "split_policy": lineage.dataset_manifest.get("split_policy"),
        "split_chronology_status": lineage.dataset_manifest.get("split_chronology_status"),
        "candidate_columns": ordered_cols,
        "feature_columns": feature_cols,
        "row_counts": {
            "candidates": int(len(candidates)),
            **{f"split_{split}": int((candidates["split"] == split).sum()) for split in sorted(_ALLOWED_SPLITS)},
        },
        "guardrail": "Research-only D3-to-PortfolioEnv bridge; no live/broker/orders/profit claim.",
    }
    return DailyPortfolioSb3Dataset(
        candidates=candidates,
        manifest=manifest,
        prediction_run_dir=lineage.run_dir,
        dataset_manifest_path=lineage.dataset_manifest_path,
        daily_db_path=lineage.daily_db_path,
        daily_db_sha256=lineage.daily_db_sha256,
    )


def _validate_run_id(run_id: str) -> str:
    rid = str(run_id or "").strip()
    if not SAFE_RUN_RE.match(rid) or rid in {".", ".."} or ".." in rid.split("."):
        raise DailyPortfolioSb3DatasetError("run_id contains unsafe characters")
    return rid


def _write_candidates_csv(path: Path, frame: pd.DataFrame) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(frame.columns), lineterminator="\n")
        writer.writeheader()
        for row in frame.to_dict(orient="records"):
            clean = dict(row)
            clean["symbol"] = str(clean["symbol"]).zfill(6)
            clean["code"] = str(clean["code"]).zfill(6)
            writer.writerow(clean)


def write_daily_portfolio_sb3_dataset(dataset: DailyPortfolioSb3Dataset, *, output_dir: Path | str, run_id: str) -> dict[str, Any]:
    """Write deterministic candidates and manifest under ``output_dir/run_id``."""

    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise DailyPortfolioSb3DatasetError(f"Output root is a symlink: {root}")
    rid = _validate_run_id(run_id)
    run_dir = (root / rid).resolve()
    try:
        run_dir.relative_to(root)
    except ValueError as exc:
        raise DailyPortfolioSb3DatasetError("run_id escapes output_dir") from exc
    run_dir.mkdir(parents=True, exist_ok=True)
    if run_dir.is_symlink():
        raise DailyPortfolioSb3DatasetError(f"Output run dir is a symlink: {run_dir}")

    candidate_path = run_dir / CANDIDATE_FILENAME
    manifest_path = run_dir / MANIFEST_FILENAME
    _write_candidates_csv(candidate_path, dataset.candidates)
    candidate_hash = _sha256_file(candidate_path)
    manifest = {
        **dict(dataset.manifest),
        "run_id": rid,
        "artifact_dir": str(run_dir),
        "artifacts": {
            "daily_portfolio_sb3_candidates": str(candidate_path),
            "daily_portfolio_sb3_dataset_manifest": str(manifest_path),
        },
        "output_hashes": {
            "daily_portfolio_sb3_candidates": candidate_hash,
        },
        "research_only_locks": {
            "model_build_allowed": False,
            "paper_forward_allowed": False,
            "live_broker_order_allowed": False,
            "profit_claim_allowed": False,
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_hash = _sha256_file(manifest_path)
    return {
        "run_id": rid,
        "artifact_dir": str(run_dir),
        "daily_portfolio_sb3_candidates_path": str(candidate_path),
        "daily_portfolio_sb3_dataset_manifest_path": str(manifest_path),
        "output_hashes": {
            "daily_portfolio_sb3_candidates": candidate_hash,
            "daily_portfolio_sb3_dataset_manifest": manifest_hash,
        },
    }


__all__ = [
    "DailyPortfolioSb3DatasetConfig",
    "DailyPortfolioSb3Dataset",
    "DailyPortfolioSb3DatasetError",
    "validate_daily_prediction_lineage",
    "build_daily_portfolio_sb3_dataset",
    "write_daily_portfolio_sb3_dataset",
]
