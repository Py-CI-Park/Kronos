from __future__ import annotations

from pathlib import Path

import pytest

from stom_rl.daily_market_authority_contract import DailyMarketAuthorityError
from stom_rl.daily_market_authority_runner import DailyMarketAuthorityPaths, main


def test_registered_authority_paths_are_fixed_under_repository(tmp_path: Path) -> None:
    # Given/When: the registered audit resolves one explicit repository root.
    paths = DailyMarketAuthorityPaths.registered(tmp_path)

    # Then: inputs and output stay in their declared custody locations.
    assert (
        paths.daily_database == tmp_path / "_database" / "Stock_Database_ohlcv_1day.db"
    )
    assert paths.stockinfo_database == tmp_path / "_database" / "stock_tick_back.db"
    assert (
        paths.price_provenance == tmp_path / "_database" / "daily_price_provenance.json"
    )
    assert (
        paths.current_official_metadata
        == tmp_path / "_database" / "krx_listed_products.csv"
    )
    assert paths.pit_membership == tmp_path / "_database" / "krx_pit_membership.csv"
    assert (
        paths.source_artifact_root
        == tmp_path / "_database" / "market_authority_sources"
    )
    assert paths.output_directory.name == "DAILY_MARKET_AUTHORITY_2026_08_10_002"


def test_authority_cli_rejects_more_than_one_repository_root() -> None:
    # Given/When/Then: the bounded CLI refuses ambiguous roots before any I/O.
    with pytest.raises(
        DailyMarketAuthorityError, match="RUNNER_ACCEPTS_AT_MOST_ONE_REPOSITORY_ROOT"
    ):
        _ = main(("first", "second"))
