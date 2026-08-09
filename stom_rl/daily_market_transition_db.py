"""Read-only daily OHLCV adapter for causal market-transition rewards."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import ClassVar, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from .daily_market_transition_contract import (
    DailyMarketCandidate,
    DailyMarketScore,
    market_score_hash,
    rank_market_scores,
)
from .daily_ohlcv_db import (
    DECISION_GRADE_RETURN_STATUS,
    DEFAULT_DAILY_DB_PATH,
    PRICE_BASIS,
    connect_readonly,
    validate_daily_table_name,
)

PRICE_BASIS_BLOCKER = "D0_PRICE_BASIS_NOT_VERIFIED"
SQLITE_ROW_ADAPTER = TypeAdapter(tuple[JsonValue, ...])
SQLITE_ROWS_ADAPTER = TypeAdapter(list[tuple[JsonValue, ...]])


class _ObjectCursor(Protocol):
    """Typed view over sqlite3's dynamically typed fetch boundary."""

    def fetchone(self) -> object: ...

    def fetchall(self) -> object: ...


class DailyMarketCandidateBatch(BaseModel):
    """Reward labels loaded after the causal top-10 selection is frozen."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_candidate_batch.v1"]
    candidates: tuple[DailyMarketCandidate, ...]
    source_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_identity_kind: Literal["path_size_mtime_lineage"]
    split_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    price_basis: Literal["unknown"]
    decision_grade_status: Literal["BLOCKED_UNTIL_PRICE_BASIS_VERIFIED"]
    blockers: tuple[str, ...]
    read_only: Literal[True]
    query_only: Literal[True]
    fresh_oos_read: Literal[False]


def _source_identity(path: Path) -> str:
    stat = path.stat()
    payload = f"{path}|{stat.st_size}|{stat.st_mtime_ns}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_db_date(value: object, *, code: str) -> date:
    if isinstance(value, bool):
        raise ValueError(f"{code}:INVALID_TRADING_DATE")
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip().replace("-", "")
    else:
        raise ValueError(f"{code}:INVALID_TRADING_DATE")
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError(f"{code}:INVALID_TRADING_DATE") from exc


def _parse_open(value: object, *, code: str, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{code}:INVALID_{label}_OPEN")
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{code}:INVALID_{label}_OPEN") from exc
    if not price.is_finite() or price <= 0:
        raise ValueError(f"{code}:INVALID_{label}_OPEN")
    return price


def _query_only_enabled(row: tuple[object, ...] | None) -> bool:
    if row is None or not row:
        return False
    value = row[0]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip() == "1"
    return False


def _fetch_optional_row(
    cursor: _ObjectCursor,
) -> tuple[JsonValue, ...] | None:
    raw: object = cursor.fetchone()
    if raw is None:
        return None
    try:
        return SQLITE_ROW_ADAPTER.validate_python(raw)
    except ValueError as exc:
        raise ValueError("SQLITE_ROW_SHAPE_INVALID") from exc


def _fetch_rows(cursor: _ObjectCursor) -> list[tuple[JsonValue, ...]]:
    raw: object = cursor.fetchall()
    try:
        return SQLITE_ROWS_ADAPTER.validate_python(raw)
    except ValueError as exc:
        raise ValueError("SQLITE_ROWS_SHAPE_INVALID") from exc


def _load_candidate(
    connection: sqlite3.Connection,
    score: DailyMarketScore,
) -> DailyMarketCandidate:
    table = validate_daily_table_name(score.table)
    decision_key = int(score.decision_date.strftime("%Y%m%d"))
    decision_row = _fetch_optional_row(
        connection.execute(
            f'SELECT 1 FROM "{table}" WHERE date = ? LIMIT 1',
            (decision_key,),
        )
    )
    if decision_row is None:
        raise ValueError(f"{score.code}:MISSING_DECISION_ROW")
    rows = _fetch_rows(
        connection.execute(
            f'SELECT date, open FROM "{table}" WHERE date > ? ORDER BY date ASC LIMIT 2',
            (decision_key,),
        )
    )
    if not rows:
        raise ValueError(f"{score.code}:MISSING_ENTRY_OPEN")
    if len(rows) < 2:
        raise ValueError(f"{score.code}:MISSING_EXIT_OPEN")
    return DailyMarketCandidate(
        decision_date=score.decision_date,
        code=score.code,
        score=score.score,
        split=score.split,
        market_prefix=score.market_prefix,
        entry_date=_parse_db_date(rows[0][0], code=score.code),
        exit_date=_parse_db_date(rows[1][0], code=score.code),
        entry_open_krw=_parse_open(rows[0][1], code=score.code, label="ENTRY"),
        exit_open_krw=_parse_open(rows[1][1], code=score.code, label="EXIT"),
    )


def load_daily_market_candidates(
    scores: Sequence[DailyMarketScore],
    *,
    db_path: Path | str = DEFAULT_DAILY_DB_PATH,
) -> DailyMarketCandidateBatch:
    """Freeze a causal top-10, then attach the exact next two valid opens."""
    ranked = rank_market_scores(scores)
    raw_path = Path(db_path)
    if raw_path.is_symlink():
        raise ValueError("daily market transition DB must not be a symbolic link")
    resolved_path = raw_path.resolve()
    if not resolved_path.is_file():
        raise FileNotFoundError(resolved_path)
    with connect_readonly(resolved_path) as connection:
        query_only = _fetch_optional_row(connection.execute("PRAGMA query_only"))
        if not _query_only_enabled(query_only):
            raise RuntimeError("daily market transition DB is not query-only")
        candidates = tuple(_load_candidate(connection, score) for score in ranked)
    if PRICE_BASIS != "unknown" or DECISION_GRADE_RETURN_STATUS != "BLOCKED_UNTIL_PRICE_BASIS_VERIFIED":
        raise RuntimeError("market transition authority contract changed; explicit review required")
    return DailyMarketCandidateBatch(
        schema_version="kronos_daily_market_candidate_batch.v1",
        candidates=candidates,
        source_identity=_source_identity(resolved_path),
        source_identity_kind="path_size_mtime_lineage",
        split_hash=market_score_hash(ranked),
        price_basis="unknown",
        decision_grade_status="BLOCKED_UNTIL_PRICE_BASIS_VERIFIED",
        blockers=(PRICE_BASIS_BLOCKER,),
        read_only=True,
        query_only=True,
        fresh_oos_read=False,
    )


__all__ = ["DailyMarketCandidateBatch", "load_daily_market_candidates"]
