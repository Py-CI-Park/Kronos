"""Read-only daily ETF prices and fail-closed Q1 data gates."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_CODE_PATTERN = re.compile(r"^[0-9]{6}$")


@dataclass(frozen=True, slots=True)
class PriceSourceError(Exception):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"ETF price source {self.path}: {self.reason}"


@dataclass(frozen=True, slots=True)
class PriceBar:
    day: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class PriceSeries:
    code: str
    bars: tuple[PriceBar, ...]


@dataclass(frozen=True, slots=True)
class DataCustodyEvidence:
    point_in_time_universe: bool
    official_instrument_identity: bool
    available_at_cutoff: bool
    total_return_contract: bool
    no_backfill: bool
    fold_local_scaler: bool

    @classmethod
    def unverified(cls) -> DataCustodyEvidence:
        return cls(False, False, False, False, True, True)

    @classmethod
    def verified_for_tests(cls) -> DataCustodyEvidence:
        return cls(True, True, True, True, True, True)


@dataclass(frozen=True, slots=True)
class DataGate:
    name: str
    passed: bool
    evidence: str


@dataclass(frozen=True, slots=True)
class DataAuditReceipt:
    verdict: str
    codes: tuple[str, ...]
    gate_results: tuple[DataGate, ...]
    blockers: tuple[str, ...]
    q3_ppo_allowed: bool

    @property
    def gates(self) -> dict[str, bool]:
        return {gate.name: gate.passed for gate in self.gate_results}


def load_price_series(database: Path, codes: tuple[str, ...]) -> tuple[PriceSeries, ...]:
    """Load six-column OHLCV tables through a SQLite read-only URI."""
    invalid = tuple(code for code in codes if _CODE_PATTERN.fullmatch(code) is None)
    if invalid:
        raise PriceSourceError(database, f"invalid six-digit codes: {invalid}")
    if not database.is_file():
        raise PriceSourceError(database, "database file not found")
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            return tuple(_load_table(connection, database, code) for code in codes)
    except sqlite3.Error as error:
        raise PriceSourceError(database, str(error)) from error


def _load_table(connection: sqlite3.Connection, database: Path, code: str) -> PriceSeries:
    table = f"A{code}"
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if exists is None:
        raise PriceSourceError(database, f"missing table {table}")
    rows = connection.execute(
        f'SELECT date, open, high, low, close, volume FROM "{table}" ORDER BY rowid'
    ).fetchall()
    bars = tuple(
        PriceBar(
            day=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        )
        for row in rows
    )
    return PriceSeries(code=code, bars=bars)


def audit_data_readiness(
    series: tuple[PriceSeries, ...],
    custody: DataCustodyEvidence,
) -> DataAuditReceipt:
    """Evaluate structural and custody gates without softening missing evidence."""
    strict_dates = all(
        all(left.day < right.day for left, right in zip(item.bars, item.bars[1:], strict=False))
        for item in series
    )
    valid_ohlc = all(all(_valid_bar(bar) for bar in item.bars) for item in series)
    nonempty = bool(series) and all(item.bars for item in series)
    gates = (
        DataGate("READ_ONLY_SOURCE", True, "SQLite mode=ro adapter"),
        DataGate("LEADING_ZERO_PRESERVED", all(_CODE_PATTERN.fullmatch(item.code) for item in series), "six-digit strings"),
        DataGate("NONEMPTY_SERIES", nonempty, "at least one row per code"),
        DataGate("STRICT_DATE_ORDER", strict_dates, "no duplicates or reversals"),
        DataGate("VALID_OHLC", valid_ohlc, "positive price and low/high envelope"),
        DataGate("POINT_IN_TIME_UNIVERSE", custody.point_in_time_universe, "historical membership snapshot"),
        DataGate("OFFICIAL_INSTRUMENT_IDENTITY", custody.official_instrument_identity, "official ETF metadata"),
        DataGate("AVAILABLE_AT_CUTOFF", custody.available_at_cutoff, "available_at <= decision time"),
        DataGate("TOTAL_RETURN_CONTRACT", custody.total_return_contract, "distribution/adjustment contract"),
        DataGate("NO_BACKFILL", custody.no_backfill, "future backfill disabled"),
        DataGate("FOLD_LOCAL_SCALER", custody.fold_local_scaler, "train-only fit"),
    )
    integrity_names = {"LEADING_ZERO_PRESERVED", "NONEMPTY_SERIES", "STRICT_DATE_ORDER", "VALID_OHLC"}
    integrity_ok = all(gate.passed for gate in gates if gate.name in integrity_names)
    custody_ok = all(gate.passed for gate in gates if gate.name not in integrity_names)
    verdict = "PASS_DATA_READY" if integrity_ok and custody_ok else (
        "BLOCKED_DATA_INTEGRITY" if not integrity_ok else "BLOCKED_DATA_CUSTODY"
    )
    blockers = tuple(gate.name for gate in gates if not gate.passed)
    return DataAuditReceipt(verdict, tuple(item.code for item in series), gates, blockers, verdict == "PASS_DATA_READY")


def _valid_bar(bar: PriceBar) -> bool:
    prices = (bar.open, bar.high, bar.low, bar.close)
    return min(prices) > 0 and bar.volume >= 0 and bar.low <= min(bar.open, bar.close) and bar.high >= max(bar.open, bar.close)

