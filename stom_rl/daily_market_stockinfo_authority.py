"""Small canonical stockinfo extract from the registered multi-gigabyte DB."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .daily_market_authority_contract import (
    AuthorityFileIdentity,
    DailyMarketAuthorityError,
)
from .daily_market_path_custody import has_reparse_component

MAX_STOCKINFO_ROWS = 100_000


@dataclass(frozen=True, slots=True)
class StockinfoAuthorityEvidence:
    identity: AuthorityFileIdentity
    row_count: int


def _stat_key(path: Path) -> tuple[int, int, int, int, int]:
    value = path.stat()
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _json_value(value: object) -> object:
    if value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DailyMarketAuthorityError("STOCKINFO_NONFINITE_VALUE")
        return value
    if isinstance(value, bytes):
        return {"blob_hex": value.hex()}
    raise DailyMarketAuthorityError("STOCKINFO_VALUE_TYPE_INVALID")


def observe_stockinfo_authority(path: Path) -> StockinfoAuthorityEvidence:
    """Bind only the stockinfo table semantics actually consumed by D1."""
    if has_reparse_component(path) or not path.is_file():
        raise DailyMarketAuthorityError("STOCKINFO_DATABASE_UNTRUSTED", str(path))
    before = _stat_key(path)
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            _ = connection.execute("PRAGMA query_only = ON")
            _ = connection.execute("BEGIN")
            schema = connection.execute("PRAGMA table_info(stockinfo)").fetchall()
            if not schema:
                raise DailyMarketAuthorityError("STOCKINFO_TABLE_MISSING")
            columns = tuple(str(row[1]) for row in schema)
            quoted = ", ".join(f'"{column.replace(chr(34), chr(34) * 2)}"' for column in columns)
            rows = connection.execute(
                f"SELECT {quoted} FROM stockinfo LIMIT ?",
                (MAX_STOCKINFO_ROWS + 1,),
            ).fetchall()
            _ = connection.execute("ROLLBACK")
    except sqlite3.Error as exc:
        raise DailyMarketAuthorityError("STOCKINFO_DATABASE_INVALID", str(path)) from exc
    if not rows or len(rows) > MAX_STOCKINFO_ROWS:
        raise DailyMarketAuthorityError("STOCKINFO_ROW_COUNT_INVALID", str(len(rows)))
    after = _stat_key(path)
    if before != after:
        raise DailyMarketAuthorityError("STOCKINFO_CHANGED_DURING_AUDIT")
    normalized_rows = sorted(
        ([*(_json_value(value) for value in row)] for row in rows),
        key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True),
    )
    payload = json.dumps(
        {
            "schema_version": "kronos_stockinfo_authority_extract.v1",
            "table": "stockinfo",
            "schema": [[_json_value(value) for value in row] for row in schema],
            "rows": normalized_rows,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    stat_result = path.stat()
    identity = AuthorityFileIdentity(
        identity_kind="CANONICAL_SQLITE_QUERY_SHA256",
        path_suffix="stockinfo-authority-extract.json",
        size_bytes=len(payload),
        modified_at_utc=datetime.fromtimestamp(
            stat_result.st_mtime,
            tz=timezone.utc,
        ).isoformat(),
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    return StockinfoAuthorityEvidence(identity, len(rows))


__all__ = ["StockinfoAuthorityEvidence", "observe_stockinfo_authority"]
