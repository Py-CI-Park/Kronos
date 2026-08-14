"""Custody-safe readers used by the daily-market authority audit."""

from __future__ import annotations

import csv
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Final, Literal, cast

from pydantic import ValidationError

from .daily_market_authority_contract import (
    DailyMarketAuthorityError,
    PitMembershipRecord,
    PriceProvenanceRecord,
)
from .daily_market_authority_file_custody import (
    authority_input_binding,
    ensure_required_file,
    file_identity,
    resolve_source_artifacts,
)
from .daily_market_candidate_eligibility import parse_candidate_eligibility
from .daily_market_path_custody import has_reparse_component
from .daily_ohlcv_db import connect_readonly

EvidenceState = Literal["PRESENT", "MISSING", "INVALID"]
CURRENT_METADATA_COLUMNS: Final = frozenset(
    {
        "code",
        "name",
        "market",
        "instrument_type",
        "available_at",
        "source_hash",
    }
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


def local_columns(path: Path, tables: tuple[str, ...]) -> tuple[str, ...]:
    if not tables:
        return ()
    with closing(connect_readonly(path)) as connection:
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
            try:
                eligible = parse_candidate_eligibility(
                    row.get("eligible_for_selection", "")
                )
            except ValueError as exc:
                raise DailyMarketAuthorityError(
                    "CANDIDATE_ELIGIBILITY_INVALID"
                ) from exc
            if not eligible:
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


def current_metadata_evidence(
    path: Path,
) -> tuple[EvidenceState, tuple[str, ...]]:
    if not path.exists():
        return "MISSING", ()
    if has_reparse_component(path) or not path.is_file():
        return "INVALID", ()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not CURRENT_METADATA_COLUMNS.issubset(
                frozenset(reader.fieldnames or ())
            ):
                return "INVALID", ()
            hashes: set[str] = set()
            observed = 0
            for row in reader:
                code = str(row.get("code", ""))
                market = str(row.get("market", ""))
                instrument_type = str(row.get("instrument_type", ""))
                available_at = str(row.get("available_at", ""))
                source_hash = str(row.get("source_hash", ""))
                if (
                    len(code) != 6
                    or not code.isdigit()
                    or market not in {"KOSPI", "KOSDAQ", "KONEX"}
                    or instrument_type != "common_equity"
                    or len(available_at) != 8
                    or not available_at.isdigit()
                    or len(source_hash) != 64
                    or any(
                        character not in "0123456789abcdef" for character in source_hash
                    )
                ):
                    return "INVALID", ()
                hashes.add(source_hash)
                observed += 1
        return ("PRESENT", tuple(sorted(hashes))) if observed else ("INVALID", ())
    except (OSError, csv.Error):
        return "INVALID", ()


def daily_column_presence_count(
    path: Path,
    tables: tuple[str, ...],
    column: str,
) -> int:
    with closing(connect_readonly(path)) as connection:
        covered = 0
        for table in tables:
            rows = cast(
                list[tuple[object, ...]],
                connection.execute(f'PRAGMA table_info("{table}")').fetchall(),
            )
            if any(len(row) > 1 and row[1] == column for row in rows):
                covered += 1
        return covered


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
        with closing(sqlite3.connect(uri, uri=True)) as connection:
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
    "authority_input_binding",
    "candidate_pairs",
    "covered_pairs",
    "current_metadata_evidence",
    "daily_column_presence_count",
    "ensure_required_file",
    "file_identity",
    "local_columns",
    "pit_records",
    "price_provenance",
    "resolve_source_artifacts",
    "stockinfo_count",
]
