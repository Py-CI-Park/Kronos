"""Custody-safe readers used by the daily-market authority audit."""

from __future__ import annotations

import csv
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Literal

from pydantic import ValidationError

from .daily_market_authority_contract import (
    AuthorityFileIdentity,
    DailyMarketAuthorityError,
    PitMembershipRecord,
    PriceProvenanceRecord,
)
from .daily_market_path_custody import has_reparse_component
from .daily_ohlcv_db import connect_readonly

EvidenceState = Literal["PRESENT", "MISSING", "INVALID"]
CURRENT_METADATA_COLUMNS: Final = frozenset(
    {"code", "name", "market", "instrument_type"}
)
PIT_COLUMNS: Final = frozenset(
    {
        "code",
        "name",
        "market",
        "instrument_type",
        "effective_from",
        "effective_to",
        "available_at",
        "source_hash",
    }
)


def ensure_required_file(path: Path, code: str) -> Path:
    resolved = path.resolve()
    if has_reparse_component(path) or not resolved.is_file():
        raise DailyMarketAuthorityError(code, str(path))
    return resolved


def file_identity(path: Path) -> AuthorityFileIdentity:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return AuthorityFileIdentity(
        path_suffix=path.name,
        size_bytes=stat.st_size,
        modified_at_utc=datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
        sha256=digest.hexdigest(),
    )


def local_columns(path: Path, tables: tuple[str, ...]) -> tuple[str, ...]:
    if not tables:
        return ()
    with connect_readonly(path) as connection:
        cursor = connection.execute(f'SELECT * FROM "{tables[0]}" LIMIT 0')
        description = cursor.description
    if description is None:
        return ()
    return tuple(column[0] for column in description)


def price_provenance(path: Path) -> tuple[EvidenceState, PriceProvenanceRecord | None]:
    if not path.exists():
        return "MISSING", None
    if has_reparse_component(path) or not path.is_file():
        return "INVALID", None
    try:
        return "PRESENT", PriceProvenanceRecord.model_validate_json(path.read_bytes())
    except (OSError, ValidationError):
        return "INVALID", None


def candidate_pairs(path: Path) -> frozenset[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = frozenset(reader.fieldnames or ())
        if not {"date", "code", "eligible_for_selection"}.issubset(fields):
            raise DailyMarketAuthorityError("CANDIDATE_SCORE_SCHEMA_INVALID")
        for row in reader:
            if str(row.get("eligible_for_selection", "")).casefold() != "true":
                continue
            date_text = str(row.get("date", "")).replace("-", "")
            code = str(row.get("code", "")).zfill(6)
            if (
                len(date_text) != 8
                or len(code) != 6
                or not date_text.isdigit()
                or not code.isdigit()
            ):
                raise DailyMarketAuthorityError("CANDIDATE_MEMBERSHIP_KEY_INVALID")
            pairs.add((date_text, code))
    if not pairs:
        raise DailyMarketAuthorityError("CANDIDATE_MEMBERSHIP_KEYS_MISSING")
    return frozenset(pairs)


def current_metadata_state(path: Path) -> EvidenceState:
    if not path.exists():
        return "MISSING"
    if has_reparse_component(path) or not path.is_file():
        return "INVALID"
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not CURRENT_METADATA_COLUMNS.issubset(
                frozenset(reader.fieldnames or ())
            ):
                return "INVALID"
            first = next(reader, None)
        return "PRESENT" if first is not None else "INVALID"
    except (OSError, csv.Error):
        return "INVALID"


def pit_records(path: Path) -> tuple[EvidenceState, tuple[PitMembershipRecord, ...]]:
    if not path.exists():
        return "MISSING", ()
    if has_reparse_component(path) or not path.is_file():
        return "INVALID", ()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not PIT_COLUMNS.issubset(frozenset(reader.fieldnames or ())):
                return "INVALID", ()
            records = tuple(PitMembershipRecord.model_validate(row) for row in reader)
    except (OSError, csv.Error, ValidationError):
        return "INVALID", ()
    return ("PRESENT", records) if records else ("INVALID", ())


def covered_pairs(
    required: frozenset[tuple[str, str]],
    records: tuple[PitMembershipRecord, ...],
) -> int:
    by_code: dict[str, list[PitMembershipRecord]] = {}
    for record in records:
        by_code.setdefault(record.code, []).append(record)
    return sum(
        any(
            record.available_at <= decision_date <= record.effective_to
            and record.effective_from <= decision_date
            for record in by_code.get(code, ())
        )
        for decision_date, code in required
    )


def stockinfo_count(path: Path) -> int:
    uri = f"file:{path.as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            _ = connection.execute("PRAGMA query_only = ON")
            cursor = connection.execute("SELECT 1 FROM stockinfo LIMIT 1")
            rows = 1 if cursor.fetchone() is not None else 0
    except sqlite3.Error as exc:
        raise DailyMarketAuthorityError(
            "STOCKINFO_DATABASE_INVALID", str(path)
        ) from exc
    return rows


__all__ = [
    "EvidenceState",
    "candidate_pairs",
    "covered_pairs",
    "current_metadata_state",
    "ensure_required_file",
    "file_identity",
    "local_columns",
    "pit_records",
    "price_provenance",
    "stockinfo_count",
]
