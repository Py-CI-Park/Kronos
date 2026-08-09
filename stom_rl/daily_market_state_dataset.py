"""Train-only preprocessing for causal Top-10 daily market state vectors."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from .daily_market_artifact_guard import (
    MAX_PANEL_CSV_BYTES,
    MAX_PANEL_ROWS,
    resolve_trusted_artifact,
)
from .daily_market_score_dataset import DailyMarketScoreDataset
from .daily_market_transition_contract import SplitName
from .daily_ohlcv_db import validate_daily_table_name

CAUSAL_FEATURE_COLUMNS = (
    "return_1d",
    "return_5d",
    "volatility_5d",
    "volume_ratio_5d",
    "hl_range",
    "gap_from_prev_close",
    "foreign_holding_ratio",
    "institutional_net_buy",
)
SLOTS = 10
VALUES_PER_FEATURE = 2
STATE_VECTOR_SIZE = SLOTS * len(CAUSAL_FEATURE_COLUMNS) * VALUES_PER_FEATURE
STATE_BLOCKERS = (
    "D0_PRICE_BASIS_NOT_VERIFIED",
    "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED",
    "RIGHT_CENSORED_REWARD_DAY_REMAINS",
    "MODEL_TRAINING_NOT_RUN",
)


class FeatureStatistic(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    feature: str
    mean: float
    standard_deviation: float = Field(ge=0)
    scaling_denominator: float = Field(gt=0)
    observed_count: int = Field(gt=0)
    fitted_split: Literal["TRAIN"]


class CausalMarketStateDay(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    decision_date: str
    split: SplitName
    score_day_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    feature_vector: tuple[float, ...]
    missing_feature_count: int = Field(ge=0)
    feature_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class DailyMarketStateDataset(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: Literal["kronos_daily_market_state_dataset.v1"]
    score_dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_panel_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    state_dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    feature_columns: tuple[str, ...]
    preprocessing: Literal["TRAIN_MEAN_IMPUTE_TRAIN_ZSCORE_WITH_MISSING_MASK"]
    statistics: tuple[FeatureStatistic, ...]
    days: tuple[CausalMarketStateDay, ...]
    day_count: int = Field(gt=0)
    training_selected_rows: int = Field(gt=0)
    feature_vector_size: Literal[160]
    blockers: tuple[str, ...]
    promotion_allowed: Literal[False]
    fresh_oos_read: Literal[False]


@dataclass(frozen=True, slots=True)
class _RawPanelRow:
    split: SplitName
    values: tuple[float | None, ...]


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha_payload(value: JsonValue) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _split_matches(value: str, expected: SplitName) -> bool:
    normalized = value.strip().upper()
    if normalized == "VAL":
        normalized = "VALIDATION"
    return normalized == expected


def _feature_value(row: Mapping[str, str | None], feature: str) -> float | None:
    raw = (row.get(feature) or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"INVALID_CAUSAL_FEATURE:{feature}") from exc
    if not math.isfinite(value):
        raise ValueError(f"NONFINITE_CAUSAL_FEATURE:{feature}")
    return value


def _selected_keys(dataset: DailyMarketScoreDataset) -> dict[tuple[str, str], SplitName]:
    selected: dict[tuple[str, str], SplitName] = {}
    for day in dataset.days:
        if day.split == "FRESH_OOS" or any(score.split == "FRESH_OOS" for score in day.scores):
            raise ValueError("FRESH_OOS remains sealed")
        if len(day.scores) != SLOTS:
            raise ValueError("STATE_DATASET_REQUIRES_EXACTLY_10_SCORES_PER_DAY")
        date_key = day.decision_date.strftime("%Y%m%d")
        for score in day.scores:
            key = (date_key, score.table)
            if key in selected:
                raise ValueError("DUPLICATE_SELECTED_SCORE_KEY")
            selected[key] = day.split
    return selected


def _read_selected_panel(
    panel_path: Path,
    selected: Mapping[tuple[str, str], SplitName],
) -> dict[tuple[str, str], _RawPanelRow]:
    rows: dict[tuple[str, str], _RawPanelRow] = {}
    with panel_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"date", "table", "code", "split", *CAUSAL_FEATURE_COLUMNS}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("CAUSAL_PANEL_COLUMNS_MISSING")
        for row_number, row in enumerate(reader, start=1):
            if row_number > MAX_PANEL_ROWS:
                raise ValueError("CAUSAL_PANEL_ROW_LIMIT_EXCEEDED")
            table = validate_daily_table_name(row.get("table") or "")
            key = ((row.get("date") or "").strip().replace("-", ""), table)
            expected_split = selected.get(key)
            if expected_split is None:
                continue
            if table[1:] != (row.get("code") or "").strip():
                raise ValueError("PANEL_TABLE_CODE_IDENTITY_MISMATCH")
            if not _split_matches(row.get("split") or "", expected_split):
                raise ValueError("PANEL_SCORE_SPLIT_MISMATCH")
            if key in rows:
                raise ValueError("DUPLICATE_SELECTED_PANEL_ROW")
            rows[key] = _RawPanelRow(
                split=expected_split,
                values=tuple(_feature_value(row, feature) for feature in CAUSAL_FEATURE_COLUMNS),
            )
    missing = sorted(set(selected) - set(rows))
    if missing:
        raise ValueError(f"SELECTED_PANEL_ROW_MISSING:{missing[0][0]}:{missing[0][1]}")
    return rows


def _fit_statistics(rows: Mapping[tuple[str, str], _RawPanelRow]) -> tuple[FeatureStatistic, ...]:
    statistics: list[FeatureStatistic] = []
    for feature_index, feature in enumerate(CAUSAL_FEATURE_COLUMNS):
        observed = [
            row.values[feature_index]
            for row in rows.values()
            if row.split == "TRAIN" and row.values[feature_index] is not None
        ]
        values = [value for value in observed if value is not None]
        if not values:
            raise ValueError(f"TRAIN_FEATURE_HAS_NO_OBSERVATIONS:{feature}")
        mean = sum(values) / len(values)
        deviation = math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))
        statistics.append(
            FeatureStatistic(
                feature=feature,
                mean=mean,
                standard_deviation=deviation,
                scaling_denominator=deviation if deviation > 0 else 1.0,
                observed_count=len(values),
                fitted_split="TRAIN",
            )
        )
    return tuple(statistics)


def _day_vector(
    dataset: DailyMarketScoreDataset,
    rows: Mapping[tuple[str, str], _RawPanelRow],
    statistics: tuple[FeatureStatistic, ...],
) -> tuple[CausalMarketStateDay, ...]:
    output: list[CausalMarketStateDay] = []
    for day in dataset.days:
        values: list[float] = []
        missing_count = 0
        date_key = day.decision_date.strftime("%Y%m%d")
        for score in day.scores:
            raw = rows[(date_key, score.table)]
            for feature_index, statistic in enumerate(statistics):
                raw_value = raw.values[feature_index]
                is_missing = raw_value is None
                value = statistic.mean if is_missing else raw_value
                values.extend(((value - statistic.mean) / statistic.scaling_denominator, float(is_missing)))
                missing_count += int(is_missing)
        vector = tuple(values)
        if len(vector) != STATE_VECTOR_SIZE:
            raise RuntimeError("STATE_FEATURE_VECTOR_SIZE_MISMATCH")
        feature_hash = _sha_payload([repr(value) for value in vector])
        output.append(
            CausalMarketStateDay(
                decision_date=day.decision_date.isoformat(),
                split=day.split,
                score_day_hash=day.day_hash,
                feature_vector=vector,
                missing_feature_count=missing_count,
                feature_hash=feature_hash,
            )
        )
    return tuple(output)


def build_market_state_dataset(
    score_dataset: DailyMarketScoreDataset,
    *,
    panel_csv_path: Path | str,
    artifact_root: Path | str,
) -> DailyMarketStateDataset:
    """Build fixed 160-value states without reading any future-label column."""
    panel_path = resolve_trusted_artifact(
        panel_csv_path,
        artifact_root=artifact_root,
        max_bytes=MAX_PANEL_CSV_BYTES,
        label="CAUSAL_PANEL_CSV",
    )
    selected = _selected_keys(score_dataset)
    raw_rows = _read_selected_panel(panel_path, selected)
    statistics = _fit_statistics(raw_rows)
    days = _day_vector(score_dataset, raw_rows, statistics)
    state_hash = _sha_payload(
        {
            "score_dataset_hash": score_dataset.dataset_hash,
            "statistics": [row.model_dump() for row in statistics],
            "days": [{"date": day.decision_date, "split": day.split, "hash": day.feature_hash} for day in days],
        }
    )
    return DailyMarketStateDataset(
        schema_version="kronos_daily_market_state_dataset.v1",
        score_dataset_hash=score_dataset.dataset_hash,
        source_panel_sha256=_sha_file(panel_path),
        state_dataset_hash=state_hash,
        feature_columns=CAUSAL_FEATURE_COLUMNS,
        preprocessing="TRAIN_MEAN_IMPUTE_TRAIN_ZSCORE_WITH_MISSING_MASK",
        statistics=statistics,
        days=days,
        day_count=len(days),
        training_selected_rows=sum(day.split == "TRAIN" for day in score_dataset.days) * SLOTS,
        feature_vector_size=160,
        blockers=STATE_BLOCKERS,
        promotion_allowed=False,
        fresh_oos_read=False,
    )


__all__ = [
    "CAUSAL_FEATURE_COLUMNS",
    "CausalMarketStateDay",
    "DailyMarketStateDataset",
    "FeatureStatistic",
    "build_market_state_dataset",
]
