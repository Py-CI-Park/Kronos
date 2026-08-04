"""Read-only source snapshot custody for daily-close research."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

from .contracts import ExecutionEvidence, validate_stock_code

_CORE_COLUMNS: Final = ("date", "open", "high", "low", "close", "volume")
_HASH_CHUNK_BYTES: Final = 1024 * 1024
_EXTERNAL_EVIDENCE_BLOCKERS: Final = (
    "POINT_IN_TIME_UNIVERSE",
    "AVAILABLE_AT_PROVEN",
    "OFFICIAL_PRICE_IDENTITY",
    "CORPORATE_ACTION_CONTRACT",
)


@dataclass(frozen=True, slots=True)
class SourceTableProfile:
    code: str
    table: str
    row_count: int
    first_date: int | None
    last_date: int | None
    core_columns_present: bool


@dataclass(frozen=True, slots=True)
class SourceCustodyReceipt:
    database_path: str
    database_sha256: str
    database_size_bytes: int
    hash_basis: str
    read_only: bool
    query_only: bool
    requested_table_count: int
    available_table_count: int
    tables: tuple[SourceTableProfile, ...]
    price_basis_status: str
    external_evidence_blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceChangedDuringRunError(Exception):
    database_path: str
    expected_sha256: str
    observed_sha256: str

    def __str__(self) -> str:
        return f"source database changed during research run: {self.database_path}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_source_custody(database: Path, codes: tuple[str, ...]) -> SourceCustodyReceipt:
    """Bind the exact SQLite bytes and profile requested tables without mutation."""
    path = database.resolve(strict=True)
    profiles: list[SourceTableProfile] = []
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only = ON")
        available_tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        for raw_code in codes:
            code = validate_stock_code(raw_code)
            table = f"A{code}"
            if table not in available_tables:
                continue
            columns = tuple(str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall())
            first_date, last_date, row_count = connection.execute(
                f'SELECT MIN(date), MAX(date), COUNT(*) FROM "{table}"'
            ).fetchone()
            profiles.append(
                SourceTableProfile(
                    code=code,
                    table=table,
                    row_count=int(row_count),
                    first_date=int(first_date) if first_date is not None else None,
                    last_date=int(last_date) if last_date is not None else None,
                    core_columns_present=all(column in columns for column in _CORE_COLUMNS),
                )
            )
    return SourceCustodyReceipt(
        database_path=str(path),
        database_sha256=_sha256(path),
        database_size_bytes=path.stat().st_size,
        hash_basis="SHA256_FULL_SQLITE_FILE",
        read_only=True,
        query_only=True,
        requested_table_count=len(codes),
        available_table_count=len(profiles),
        tables=tuple(profiles),
        price_basis_status="UNKNOWN_CONFIRMED",
        external_evidence_blockers=_EXTERNAL_EVIDENCE_BLOCKERS,
    )


def bind_source_hash(evidence: ExecutionEvidence, custody: SourceCustodyReceipt) -> ExecutionEvidence:
    """Promote only the local full-file hash gate; external authority stays unchanged."""
    return replace(evidence, immutable_source_hash=len(custody.database_sha256) == 64)


def assert_source_unchanged(custody: SourceCustodyReceipt) -> None:
    """Fail closed when the source bytes no longer match the bound snapshot."""
    observed = _sha256(Path(custody.database_path))
    if observed != custody.database_sha256:
        raise SourceChangedDuringRunError(custody.database_path, custody.database_sha256, observed)
