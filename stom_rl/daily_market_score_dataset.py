"""Causal score-dataset adapter for the next-open market-transition lane."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import ClassVar, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    model_validator,
)

from .daily_market_artifact_guard import (
    MAX_MANIFEST_BYTES,
    MAX_SCORE_CSV_BYTES,
    MAX_SCORE_ROWS,
    resolve_trusted_artifact,
)
from .daily_market_candidate_eligibility import parse_candidate_eligibility
from .daily_market_errors import DailyMarketScoreError
from .daily_market_transition_contract import (
    DailyMarketScore,
    SplitName,
    market_score_hash,
    rank_market_scores,
)
from .daily_ohlcv_db import validate_daily_table_name

SOURCE_FILL_MODE = "close_to_next_close_research_label"
TARGET_FILL_MODE = "D_CLOSE_DECISION_D1_OPEN_ENTRY_D2_OPEN_EXIT"
REQUIRED_BLOCKERS = (
    "D0_PRICE_BASIS_NOT_VERIFIED",
    "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED",
    "STATE_FEATURE_VECTOR_NOT_BUILT",
    "NEXT_OPEN_REWARD_NOT_MATERIALIZED",
)
MANIFEST_ADAPTER = TypeAdapter(dict[str, JsonValue])


class CausalMarketScoreDay(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    decision_date: date
    split: SplitName
    scores: tuple[DailyMarketScore, ...]
    day_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class DailyMarketScoreDataset(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_score_dataset.v1"]
    days: tuple[CausalMarketScoreDay, ...]
    dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_candidate_csv_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_fill_mode: Literal["close_to_next_close_research_label"]
    target_fill_mode: Literal["D_CLOSE_DECISION_D1_OPEN_ENTRY_D2_OPEN_EXIT"]
    day_count: int = Field(gt=0)
    scored_row_count: int = Field(gt=0)
    selected_score_count: int = Field(gt=0)
    excluded_missing_score_rows: int = Field(ge=0)
    excluded_ineligible_rows: int = Field(ge=0)
    split_day_counts: dict[str, int]
    blockers: tuple[str, ...]
    promotion_allowed: Literal[False]
    fresh_oos_read: Literal[False]

    @model_validator(mode="after")
    def reject_fresh_oos_days(self) -> Self:
        if any(day.split == "FRESH_OOS" for day in self.days):
            raise DailyMarketScoreError("FRESH_OOS remains sealed")
        return self


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_payload(value: JsonValue) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load_manifest(path: Path) -> dict[str, JsonValue]:
    try:
        return MANIFEST_ADAPTER.validate_json(path.read_bytes())
    except ValueError as exc:
        raise DailyMarketScoreError("SOURCE_MANIFEST_INVALID") from exc


def _validate_manifest(manifest: Mapping[str, JsonValue]) -> None:
    if manifest.get("fill_mode") != SOURCE_FILL_MODE:
        raise DailyMarketScoreError("SOURCE_FILL_MODE_UNEXPECTED")
    if manifest.get("price_basis") != "unknown":
        raise DailyMarketScoreError("SOURCE_PRICE_BASIS_REQUIRES_REVIEW")
    if (
        manifest.get("decision_grade_return_status")
        != "BLOCKED_UNTIL_PRICE_BASIS_VERIFIED"
    ):
        raise DailyMarketScoreError("SOURCE_DECISION_GRADE_STATUS_REQUIRES_REVIEW")
    if manifest.get("promotion_allowed") is not False:
        raise DailyMarketScoreError("SOURCE_PROMOTION_LOCK_MISSING")


def _parse_date(value: str) -> date:
    text = value.strip().replace("-", "")
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError as exc:
        raise DailyMarketScoreError("INVALID_DECISION_DATE") from exc


def _parse_split(value: str) -> SplitName:
    normalized = value.strip().upper()
    aliases: dict[str, SplitName] = {
        "TRAIN": "TRAIN",
        "VAL": "VALIDATION",
        "VALIDATION": "VALIDATION",
        "TEST": "TEST",
        "FRESH_OOS": "FRESH_OOS",
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise DailyMarketScoreError(f"UNSUPPORTED_SPLIT:{normalized}") from exc


def _market_prefix(table: str) -> Literal["A", "Q"]:
    if table.startswith("A"):
        return "A"
    if table.startswith("Q"):
        return "Q"
    raise DailyMarketScoreError("UNSUPPORTED_MARKET_PREFIX")


def _parse_score_row(row: Mapping[str, str | None]) -> DailyMarketScore:
    raw_table = row.get("table") or ""
    table = validate_daily_table_name(raw_table)
    code = (row.get("code") or "").strip()
    if table[1:] != code or len(code) != 6 or not code.isdigit():
        raise DailyMarketScoreError("TABLE_CODE_IDENTITY_MISMATCH")
    raw_score = row.get("score") or ""
    try:
        score = float(raw_score)
    except ValueError as exc:
        raise DailyMarketScoreError("INVALID_CAUSAL_SCORE") from exc
    if not math.isfinite(score):
        raise DailyMarketScoreError("INVALID_CAUSAL_SCORE")
    return DailyMarketScore(
        decision_date=_parse_date(row.get("date") or ""),
        code=code,
        score=score,
        split=_parse_split(row.get("split") or ""),
        market_prefix=_market_prefix(table),
    )


def load_market_score_dataset(
    candidate_csv_path: Path | str,
    *,
    source_manifest_path: Path | str,
    artifact_root: Path | str,
) -> DailyMarketScoreDataset:
    """Load causal scores only; source future-label columns are never consumed."""
    csv_path = resolve_trusted_artifact(
        candidate_csv_path,
        artifact_root=artifact_root,
        max_bytes=MAX_SCORE_CSV_BYTES,
        label="CANDIDATE_SCORE_CSV",
    )
    manifest_path = resolve_trusted_artifact(
        source_manifest_path,
        artifact_root=artifact_root,
        max_bytes=MAX_MANIFEST_BYTES,
        label="SOURCE_MANIFEST",
    )
    _validate_manifest(_load_manifest(manifest_path))
    grouped: dict[tuple[date, SplitName], list[DailyMarketScore]] = defaultdict(list)
    scored_rows = 0
    missing_scores = 0
    ineligible_rows = 0
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"date", "table", "code", "score", "split", "eligible_for_selection"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise DailyMarketScoreError("CANDIDATE_SCORE_COLUMNS_MISSING")
        for row_number, row in enumerate(reader, start=1):
            if row_number > MAX_SCORE_ROWS:
                raise DailyMarketScoreError("CANDIDATE_SCORE_ROW_LIMIT_EXCEEDED")
            try:
                eligible = parse_candidate_eligibility(
                    row.get("eligible_for_selection", "")
                )
            except ValueError as exc:
                raise DailyMarketScoreError("CANDIDATE_ELIGIBILITY_INVALID") from exc
            if not eligible:
                ineligible_rows += 1
                continue
            if not (row.get("score") or "").strip():
                missing_scores += 1
                continue
            score = _parse_score_row(row)
            if score.split == "FRESH_OOS":
                raise DailyMarketScoreError("FRESH_OOS remains sealed")
            grouped[(score.decision_date, score.split)].append(score)
            scored_rows += 1
    if not grouped:
        raise DailyMarketScoreError("NO_CAUSAL_SCORE_DAYS")
    splits_by_date: dict[date, SplitName] = {}
    days: list[CausalMarketScoreDay] = []
    for (decision_date, split), scores in sorted(grouped.items()):
        previous_split = splits_by_date.setdefault(decision_date, split)
        if previous_split != split:
            raise DailyMarketScoreError("DECISION_DATE_SPLIT_CONFLICT")
        ranked = rank_market_scores(scores)
        days.append(
            CausalMarketScoreDay(
                decision_date=decision_date,
                split=split,
                scores=ranked,
                day_hash=market_score_hash(ranked),
            )
        )
    split_counts: dict[str, int] = defaultdict(int)
    for day in days:
        split_counts[day.split] += 1
    dataset_hash = _sha256_payload(
        [
            {
                "date": day.decision_date.isoformat(),
                "split": day.split,
                "hash": day.day_hash,
            }
            for day in days
        ]
    )
    return DailyMarketScoreDataset(
        schema_version="kronos_daily_market_score_dataset.v1",
        days=tuple(days),
        dataset_hash=dataset_hash,
        source_candidate_csv_sha256=_sha256_file(csv_path),
        source_manifest_sha256=_sha256_file(manifest_path),
        source_fill_mode="close_to_next_close_research_label",
        target_fill_mode="D_CLOSE_DECISION_D1_OPEN_ENTRY_D2_OPEN_EXIT",
        day_count=len(days),
        scored_row_count=scored_rows,
        selected_score_count=sum(len(day.scores) for day in days),
        excluded_missing_score_rows=missing_scores,
        excluded_ineligible_rows=ineligible_rows,
        split_day_counts=dict(split_counts),
        blockers=REQUIRED_BLOCKERS,
        promotion_allowed=False,
        fresh_oos_read=False,
    )


__all__ = [
    "CausalMarketScoreDay",
    "DailyMarketScoreDataset",
    "load_market_score_dataset",
]
