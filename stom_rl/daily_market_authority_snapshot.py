"""Exact-byte SQLite snapshots used by the daily-market authority audit."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from .daily_market_authority_contract import (
    AuthorityFileIdentity,
    DailyMarketAuthorityError,
)
from .daily_market_authority_file_custody import copy_stable_file, file_identity
from .daily_market_path_custody import has_reparse_component


@dataclass(frozen=True, slots=True)
class AuthorityDatabaseSnapshots:
    daily_path: Path
    daily_identity: AuthorityFileIdentity


@contextmanager
def immutable_authority_database_snapshots(
    daily_database: Path,
) -> Iterator[AuthorityDatabaseSnapshots]:
    """Copy the audited price DB from one verified descriptor read."""
    with TemporaryDirectory(prefix="kronos-market-authority-") as raw_directory:
        directory = Path(raw_directory)
        if has_reparse_component(directory):
            raise DailyMarketAuthorityError(
                "AUTHORITY_SNAPSHOT_DIRECTORY_UNTRUSTED",
                str(directory),
            )
        daily_path = directory / daily_database.name
        daily_identity = copy_stable_file(daily_database, daily_path)
        snapshots = AuthorityDatabaseSnapshots(
            daily_path,
            daily_identity,
        )
        yield snapshots
        final_daily = file_identity(daily_path)
        if (
            final_daily.sha256 != daily_identity.sha256
            or final_daily.size_bytes != daily_identity.size_bytes
        ):
            raise DailyMarketAuthorityError("AUTHORITY_SNAPSHOT_CHANGED_DURING_AUDIT")


__all__ = [
    "AuthorityDatabaseSnapshots",
    "immutable_authority_database_snapshots",
]
