"""Read-only custody and quality audit for the existing local market databases."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from .daily_market_authority_contract import AuthorityFileIdentity
from .daily_market_authority_file_custody import file_identity
from .daily_market_path_custody import has_reparse_component
from .daily_market_stockinfo_authority import observe_stockinfo_authority
from .daily_ohlcv_db import connect_readonly, list_daily_tables
from .daily_market_rl_contract import DailyMarketRlContractError

_REQUIRED_DAILY_COLUMNS = frozenset({"date", "open", "high", "low", "close", "volume"})
_SQL_ROWS = TypeAdapter(list[tuple[str | int | float | None, ...]])
_AGGREGATE_ROW = TypeAdapter(tuple[int, int | str | None, int | str | None, int])


@dataclass(frozen=True, slots=True)
class LocalDbCustodyPaths:
    repository_root: Path
    daily_database: Path
    stockinfo_database: Path
    output_directory: Path

    @classmethod
    def registered(cls, repository_root: Path) -> "LocalDbCustodyPaths":
        root = repository_root.resolve()
        return cls(
            repository_root=root,
            daily_database=root / "_database" / "Stock_Database_ohlcv_1day.db",
            stockinfo_database=root / "_database" / "stock_tick_back.db",
            output_directory=(
                root
                / "webui"
                / "rl_runs"
                / "daily_market_local_db"
                / "DAILY_MARKET_LOCAL_DB_CUSTODY_2026_08_14_001"
            ),
        )


class LocalDbQuality(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    table_count: int = Field(gt=0)
    nonempty_table_count: int = Field(ge=0)
    required_schema_table_count: int = Field(ge=0)
    explicit_price_basis_table_count: int = Field(ge=0)
    duplicate_date_table_count: int = Field(ge=0)
    total_row_count: int = Field(gt=0)
    first_date: str = Field(pattern=r"^[0-9]{8}$")
    last_date: str = Field(pattern=r"^[0-9]{8}$")
    stockinfo_row_count: int = Field(gt=0)
    leading_zero_codes_preserved: Literal[True]
    quality_passed: bool


class LocalDbCustodyReceipt(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_local_db_custody.v1"]
    research_id: Literal["DAILY_MARKET_LOCAL_DB_CUSTODY_2026_08_14_001"]
    status: Literal["COMPLETE_LOCAL_RESEARCH_ONLY"]
    daily_database: AuthorityFileIdentity
    stockinfo_database: AuthorityFileIdentity
    quality: LocalDbQuality
    price_basis: Literal["UNKNOWN_LOCAL_DB_BASIS"]
    universe_basis: Literal["CURRENT_SNAPSHOT_NOT_PIT"]
    historical_test_state: Literal["CONTAMINATED_LOCAL_RESEARCH_ONLY"]
    blockers: tuple[str, ...]
    local_research_allowed: bool
    independent_oos_claim_allowed: Literal[False]
    profitability_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    paper_live_allowed: Literal[False]
    fresh_holdout_read: Literal[False]
    read_only: Literal[True]
    query_only: Literal[True]


def _stat_key(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _scan_daily_database(path: Path) -> tuple[int, int, int, int, int, int, str, str]:
    tables = tuple(list_daily_tables(path))
    if not tables:
        raise DailyMarketRlContractError("LOCAL_DB_DAILY_TABLES_MISSING")
    nonempty = 0
    schema_complete = 0
    explicit_basis = 0
    duplicate_tables = 0
    total_rows = 0
    first_date = "99999999"
    last_date = "00000000"
    with closing(connect_readonly(path)) as connection:
        for table in tables:
            schema_rows = _SQL_ROWS.validate_python(
                connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            )
            columns = {str(row[1]) for row in schema_rows if len(row) > 1}
            schema_complete += int(_REQUIRED_DAILY_COLUMNS.issubset(columns))
            explicit_basis += int("수정주가구분" in columns)
            raw_row = cast(
                object,
                connection.execute(
                    f'SELECT COUNT(*), MIN(date), MAX(date), COUNT(date) - COUNT(DISTINCT date) FROM "{table}"'
                ).fetchone(),
            )
            if raw_row is None:
                raise DailyMarketRlContractError("LOCAL_DB_DAILY_SCAN_INVALID", table)
            row = _AGGREGATE_ROW.validate_python(raw_row)
            count = int(row[0])
            total_rows += count
            nonempty += int(count > 0)
            duplicate_tables += int(int(row[3]) > 0)
            if count > 0:
                minimum, maximum = str(row[1]), str(row[2])
                if len(minimum) != 8 or len(maximum) != 8:
                    raise DailyMarketRlContractError("LOCAL_DB_DATE_INVALID", table)
                first_date = min(first_date, minimum)
                last_date = max(last_date, maximum)
    if total_rows <= 0:
        raise DailyMarketRlContractError("LOCAL_DB_DAILY_ROWS_MISSING")
    return (
        len(tables),
        nonempty,
        schema_complete,
        explicit_basis,
        duplicate_tables,
        total_rows,
        first_date,
        last_date,
    )


def audit_local_databases(paths: LocalDbCustodyPaths) -> LocalDbCustodyReceipt:
    """Hash and scan the existing databases without mutating or copying them."""
    for path in (paths.daily_database, paths.stockinfo_database):
        if has_reparse_component(path) or not path.is_file():
            raise DailyMarketRlContractError("LOCAL_DB_INPUT_UNTRUSTED", str(path))
    daily_stat = _stat_key(paths.daily_database)
    daily_identity = file_identity(paths.daily_database)
    scan = _scan_daily_database(paths.daily_database)
    if _stat_key(paths.daily_database) != daily_stat:
        raise DailyMarketRlContractError("LOCAL_DB_CHANGED_DURING_AUDIT")
    stockinfo = observe_stockinfo_authority(paths.stockinfo_database)
    (
        table_count,
        nonempty,
        schema_complete,
        explicit_basis,
        duplicates,
        rows,
        first,
        last,
    ) = scan
    quality_passed = (
        nonempty == table_count
        and schema_complete == table_count
        and duplicates == 0
        and stockinfo.row_count > 0
    )
    quality = LocalDbQuality(
        table_count=table_count,
        nonempty_table_count=nonempty,
        required_schema_table_count=schema_complete,
        explicit_price_basis_table_count=explicit_basis,
        duplicate_date_table_count=duplicates,
        total_row_count=rows,
        first_date=first,
        last_date=last,
        stockinfo_row_count=stockinfo.row_count,
        leading_zero_codes_preserved=True,
        quality_passed=quality_passed,
    )
    blockers = ["D0_PRICE_BASIS_UNKNOWN_LOCAL_DB", "D1_CURRENT_SNAPSHOT_NOT_PIT"]
    if not quality_passed:
        blockers.append("LOCAL_DB_SCHEMA_OR_DUPLICATE_QUALITY_FAILED")
    return LocalDbCustodyReceipt(
        schema_version="kronos_daily_market_local_db_custody.v1",
        research_id="DAILY_MARKET_LOCAL_DB_CUSTODY_2026_08_14_001",
        status="COMPLETE_LOCAL_RESEARCH_ONLY",
        daily_database=daily_identity,
        stockinfo_database=stockinfo.identity,
        quality=quality,
        price_basis="UNKNOWN_LOCAL_DB_BASIS",
        universe_basis="CURRENT_SNAPSHOT_NOT_PIT",
        historical_test_state="CONTAMINATED_LOCAL_RESEARCH_ONLY",
        blockers=tuple(blockers),
        local_research_allowed=quality_passed,
        independent_oos_claim_allowed=False,
        profitability_claim_allowed=False,
        promotion_allowed=False,
        paper_live_allowed=False,
        fresh_holdout_read=False,
        read_only=True,
        query_only=True,
    )


def write_local_db_custody(receipt: LocalDbCustodyReceipt, output: Path) -> Path:
    if has_reparse_component(output) or output.exists():
        raise DailyMarketRlContractError("LOCAL_DB_OUTPUT_UNTRUSTED")
    output.mkdir(parents=True, exist_ok=False)
    path = output / "local_db_custody_receipt.json"
    payload = f"{receipt.model_dump_json(indent=2)}\n"
    with path.open("x", encoding="utf-8", newline="") as handle:
        _ = handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return path


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        raise DailyMarketRlContractError("LOCAL_DB_RUNNER_REQUIRES_REPOSITORY_ROOT")
    paths = LocalDbCustodyPaths.registered(Path(arguments[0]))
    receipt = audit_local_databases(paths)
    _ = write_local_db_custody(receipt, paths.output_directory)
    print(json.dumps(receipt.model_dump(mode="json"), ensure_ascii=False))
    return 0


__all__ = [
    "LocalDbCustodyPaths",
    "LocalDbCustodyReceipt",
    "LocalDbQuality",
    "audit_local_databases",
    "write_local_db_custody",
]


if __name__ == "__main__":
    raise SystemExit(main())
