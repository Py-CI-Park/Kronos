from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pytest

from stom_rl.daily_v51_causal_panel import (
    FORBIDDEN_DAILY_FIELDS,
    SCHEMA_VERSION,
    CausalPanelContractError,
    build_causal_panel as _build_causal_panel,
    validate_causal_panel,
    _panel_digest,
)

_SOURCE_DB_PATH = "D:/Kronos/_database/Stock_Database_ohlcv_5min.db"
_SOURCE_COLUMNS = ("date", "open", "high", "low", "close", "volume")
_BAR_VOLUME_STATUS = "SINGLE_5MIN_BAR_VOLUME_AT_15_20_ONLY"
_UNAVAILABLE_CUMULATIVE_VOLUME_STATUS = "NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY"
_UNAVAILABLE_AMOUNT_STATUS = "NOT_AVAILABLE_5MIN_DB_HAS_NO_AMOUNT_COLUMN_DO_NOT_APPROXIMATE_PRICE_X_VOLUME"
_VALID_SOURCE_DB_SHA256 = "0123456789abcdef" * 4
_VALID_SOURCE_IDENTITY: Mapping[str, object] = {
    "schema_version": "kronos_daily_1520_source.v1",
    "source_db_path": _SOURCE_DB_PATH,
    "source_db_sha256": _VALID_SOURCE_DB_SHA256,
}


def build_causal_panel(
    observation_rows: Sequence[object],
    exact_1520_rows: Sequence[object],
    *,
    source_calendar: Sequence[str],
    horizon_days: Sequence[int] = (1, 3, 5),
    source_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return _build_causal_panel(
        observation_rows,
        exact_1520_rows,
        source_calendar=source_calendar,
        horizon_days=horizon_days,
        source_identity=_VALID_SOURCE_IDENTITY if source_identity is None else source_identity,
    )


@dataclass(frozen=True)
class Exact1520Fixture:
    schema_version: str
    session_date: str
    date: str
    timestamp_kst: str
    timestamp_yyyymmddhhmm: str
    symbol: str
    table: str
    open: float
    high: float
    low: float
    close: float
    price_1520_close_proxy: float
    bar_volume_1520: int
    bar_volume_status: str
    volume_to_1520: None
    volume_to_1520_status: str
    cumulative_volume_to_1520: None
    cumulative_volume_to_1520_status: str
    amount_to_1520: None
    amount_to_1520_status: str
    tradable: bool
    exclusion_reason: str | None
    official_close: bool
    price_basis: str
    causal_cutoff_kst: str
    source_db_path: str
    source_table: str
    source_columns: tuple[str, ...]
    source_timestamp_column: str
    source_price_column: str
    source_volume_column: str


def _observation(symbol: str = "005930", session: str = "2024-01-05", timestamp: str | None = None, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "symbol": symbol,
        "session": session,
        "timestamp": timestamp or f"{session}T15:19:00+09:00",
        "feature_score": 1.25,
        "source_db_path": _SOURCE_DB_PATH,
    }
    row.update(extra)
    return row


def _exact(symbol: str, session: str, close: float, **extra: object) -> Exact1520Fixture:
    table = str(extra.pop("table", f"A{symbol}"))
    source_table = str(extra.pop("source_table", table))
    return Exact1520Fixture(
        schema_version=str(extra.pop("schema_version", "kronos_daily_1520_source.v1")),
        session_date=str(extra.pop("session_date", session)),
        date=str(extra.pop("date", session)),
        timestamp_kst=str(extra.pop("timestamp_kst", f"{session}T15:20:00+09:00")),
        timestamp_yyyymmddhhmm=str(extra.pop("timestamp_yyyymmddhhmm", session.replace("-", "") + "1520")),
        symbol=symbol,
        table=table,
        open=float(extra.pop("open", close - 1.0)),
        high=float(extra.pop("high", close + 2.0)),
        low=float(extra.pop("low", close - 2.0)),
        close=close,
        price_1520_close_proxy=float(extra.pop("price_1520_close_proxy", close)),
        bar_volume_1520=int(extra.pop("bar_volume_1520", 1234)),
        bar_volume_status=str(extra.pop("bar_volume_status", _BAR_VOLUME_STATUS)),
        volume_to_1520=extra.pop("volume_to_1520", None),
        volume_to_1520_status=str(extra.pop("volume_to_1520_status", _UNAVAILABLE_CUMULATIVE_VOLUME_STATUS)),
        cumulative_volume_to_1520=extra.pop("cumulative_volume_to_1520", None),
        cumulative_volume_to_1520_status=str(
            extra.pop("cumulative_volume_to_1520_status", _UNAVAILABLE_CUMULATIVE_VOLUME_STATUS)
        ),
        amount_to_1520=extra.pop("amount_to_1520", None),
        amount_to_1520_status=str(extra.pop("amount_to_1520_status", _UNAVAILABLE_AMOUNT_STATUS)),
        tradable=bool(extra.pop("tradable", True)),
        exclusion_reason=extra.pop("exclusion_reason", None),
        official_close=bool(extra.pop("official_close", False)),
        price_basis=str(extra.pop("price_basis", "15:20_bar_close_proxy")),
        causal_cutoff_kst=str(extra.pop("causal_cutoff_kst", "15:20:00")),
        source_db_path=str(extra.pop("source_db_path", _SOURCE_DB_PATH)),
        source_table=source_table,
        source_columns=tuple(extra.pop("source_columns", _SOURCE_COLUMNS)),
        source_timestamp_column=str(extra.pop("source_timestamp_column", "date")),
        source_price_column=str(extra.pop("source_price_column", "close")),
        source_volume_column=str(extra.pop("source_volume_column", "volume")),
    )


def _six_sessions() -> list[str]:
    return ["2024-01-05", "2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11", "2024-01-12"]


def test_trading_session_h1_h3_h5_labels_use_exact_1520_marks_and_not_calendar_days() -> None:
    sessions = _six_sessions()
    closes = [100.0, 110.0, 90.0, 120.0, 150.0, 200.0]
    panel = build_causal_panel(
        [_observation("005930", sessions[0], timestamp=f"{sessions[0]}T15:20:00+09:00")],
        [_exact("005930", session, close) for session, close in zip(sessions, closes)],
        source_calendar=sessions,
    )

    assert panel["schema_version"] == SCHEMA_VERSION
    row = panel["rows"][0]
    assert row["symbol"] == "005930"
    assert row["future_return_h1_1520_proxy"] == pytest.approx(0.10)
    assert row["future_return_h3_1520_proxy"] == pytest.approx(0.20)
    assert row["future_return_h5_1520_proxy"] == pytest.approx(1.00)
    assert row["label_statuses"]["future_return_h1_1520_proxy"]["exit_session"] == "2024-01-08"
    assert row["label_statuses"]["future_return_h3_1520_proxy"]["exit_session"] == "2024-01-10"
    assert row["label_statuses"]["future_return_h5_1520_proxy"]["exit_session"] == "2024-01-12"
    assert all(status["fallback_used"] is False for status in row["label_statuses"].values())
    assert validate_causal_panel(panel) is panel


def test_source_calendar_session_without_exact_1520_does_not_compress_h1() -> None:
    h1 = "future_return_h1_1520_proxy"
    panel = build_causal_panel(
        [_observation("005930", "2024-01-05")],
        [
            _exact("005930", "2024-01-05", 100.0),
            _exact("005930", "2024-01-09", 120.0),
        ],
        source_calendar=["2024-01-05", "2024-01-08", "2024-01-09"],
    )

    assert panel["coverage"]["trading_sessions"] == [
        "2024-01-05",
        "2024-01-08",
        "2024-01-09",
    ]
    row = panel["rows"][0]
    assert row["label_statuses"][h1]["status"] == "missing_exit"
    assert row["label_statuses"][h1]["exit_session"] == "2024-01-08"
    assert row["label_statuses"][h1]["fallback_used"] is False
    assert row["exit_1520_by_label"][h1] is None
    assert row[h1] is None
    assert validate_causal_panel(panel) is panel


def test_validate_rejects_h1_compressed_to_next_available_exact_mark() -> None:
    h1 = "future_return_h1_1520_proxy"
    source_calendar = [
        "2024-01-05",
        "2024-01-08",
        "2024-01-09",
        "2024-01-10",
        "2024-01-11",
        "2024-01-12",
    ]
    exact_rows = [
        _exact("005930", "2024-01-05", 100.0),
        _exact("005930", "2024-01-09", 120.0),
        _exact("005930", "2024-01-10", 130.0),
        _exact("005930", "2024-01-11", 140.0),
        _exact("005930", "2024-01-12", 150.0),
    ]
    panel = build_causal_panel(
        [_observation("005930", "2024-01-05")],
        exact_rows,
        source_calendar=source_calendar,
    )
    compressed_panel = build_causal_panel(
        [_observation("005930", "2024-01-05")],
        [*exact_rows, _exact("005930", "2024-01-15", 160.0)],
        source_calendar=[
            "2024-01-05",
            "2024-01-09",
            "2024-01-10",
            "2024-01-11",
            "2024-01-12",
            "2024-01-15",
        ],
    )

    assert panel["rows"][0]["label_statuses"][h1]["exit_session"] == "2024-01-08"
    assert panel["rows"][0][h1] is None

    mutated = copy.deepcopy(panel)
    compressed_row = compressed_panel["rows"][0]
    row = mutated["rows"][0]
    row[h1] = compressed_row[h1]
    row["labels"][h1] = compressed_row["labels"][h1]
    row["label_statuses"][h1] = copy.deepcopy(compressed_row["label_statuses"][h1])
    row["exit_1520_by_label"][h1] = copy.deepcopy(compressed_row["exit_1520_by_label"][h1])
    mutated["coverage"]["labels"][h1] = {"available": 1, "missing_entry": 0, "missing_exit": 0}
    mutated["panel_sha256"] = _panel_digest(mutated)

    with pytest.raises(
        CausalPanelContractError,
        match="exit_session does not match source calendar horizon",
    ):
        validate_causal_panel(mutated)


@pytest.mark.parametrize(
    ("source_calendar", "match"),
    (
        (["20240105", "2024-01-08"], "canonical YYYY-MM-DD"),
        (["2024-01-08", "2024-01-05"], "strictly increasing"),
        (["2024-01-05", "2024-01-05"], "unique"),
        ({"2024-01-05", "2024-01-08"}, "sequence"),
    ),
)
def test_source_calendar_rejects_noncanonical_duplicate_or_unsorted_sessions(
    source_calendar: object,
    match: str,
) -> None:
    with pytest.raises(CausalPanelContractError, match=match):
        build_causal_panel(
            [_observation("005930", "2024-01-05")],
            [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 101.0)],
            source_calendar=source_calendar,
        )


def test_observation_and_exact_sessions_must_belong_to_source_calendar() -> None:
    with pytest.raises(CausalPanelContractError, match="observation_rows session 2024-01-09"):
        build_causal_panel(
            [_observation("005930", "2024-01-09")],
            [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 101.0)],
            source_calendar=["2024-01-05", "2024-01-08"],
        )

    with pytest.raises(CausalPanelContractError, match="exact_1520_rows session 2024-01-09"):
        build_causal_panel(
            [_observation("005930", "2024-01-05")],
            [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-09", 101.0)],
            source_calendar=["2024-01-05", "2024-01-08"],
        )


def test_non_contract_horizons_are_rejected_in_build_and_validation() -> None:
    exact_rows = [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 101.0)]
    with pytest.raises(CausalPanelContractError, match="horizon_days must be exactly"):
        build_causal_panel(
            [_observation("005930", "2024-01-05")],
            exact_rows,
            source_calendar=["2024-01-05", "2024-01-08"],
            horizon_days=(1, 2, 5),
        )

    panel = build_causal_panel(
        [_observation("005930", "2024-01-05")],
        exact_rows,
        source_calendar=["2024-01-05", "2024-01-08"],
    )
    mutated = copy.deepcopy(panel)
    mutated["horizon_days"] = [1, 2, 5]
    mutated["panel_sha256"] = _panel_digest(mutated)
    with pytest.raises(CausalPanelContractError, match="horizon_days must be exactly"):
        validate_causal_panel(mutated)


def test_post_cutoff_observation_timestamp_is_rejected() -> None:
    with pytest.raises(CausalPanelContractError, match="post-cutoff"):
        build_causal_panel(
            [_observation(timestamp="2024-01-05T15:20:01+09:00")],
            [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 101.0)],
            source_calendar=["2024-01-05", "2024-01-08"],
        )


def test_date_only_observation_timestamps_are_rejected() -> None:
    exact_rows = [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 101.0)]

    with pytest.raises(CausalPanelContractError, match="intraday time"):
        build_causal_panel([_observation(timestamp="2024-01-05")], exact_rows, source_calendar=["2024-01-05", "2024-01-08"])

    panel = build_causal_panel([_observation()], exact_rows, source_calendar=["2024-01-05", "2024-01-08"])
    mutated = copy.deepcopy(panel)
    mutated["rows"][0]["observations"][0]["timestamp"] = "2024-01-05"
    mutated["panel_sha256"] = _panel_digest(mutated)
    with pytest.raises(CausalPanelContractError, match="intraday time"):
        validate_causal_panel(mutated)


def test_alphabetic_symbols_are_rejected_for_observations_and_exact_rows() -> None:
    exact_rows = [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 101.0)]

    with pytest.raises(CausalPanelContractError, match="six-digit numeric"):
        build_causal_panel([_observation("00AB12")], exact_rows, source_calendar=["2024-01-05", "2024-01-08"])

    with pytest.raises(CausalPanelContractError, match="six-digit numeric"):
        build_causal_panel(
            [_observation("005930")],
            [_exact("00AB12", "2024-01-05", 100.0), _exact("00AB12", "2024-01-08", 101.0)],
            source_calendar=["2024-01-05", "2024-01-08"],
        )

    with pytest.raises(CausalPanelContractError, match="source_table must match symbol"):
        build_causal_panel(
            [_observation("005930")],
            [
                _exact("005930", "2024-01-05", 100.0, source_table="A000001"),
                _exact("005930", "2024-01-08", 101.0, source_table="A000001"),
            ],
            source_calendar=["2024-01-05", "2024-01-08"],
        )


def test_exact_rows_require_explicit_proxy_provenance() -> None:
    for missing_field in ("official_close", "price_basis"):
        entry = vars(_exact("005930", "2024-01-05", 100.0)).copy()
        entry.pop(missing_field)
        with pytest.raises(CausalPanelContractError, match="official_close=false|price_basis"):
            build_causal_panel(
                [_observation("005930")],
                [entry, _exact("005930", "2024-01-08", 101.0)],
                source_calendar=["2024-01-05", "2024-01-08"],
            )


def test_source_identity_requires_explicit_non_null_lowercase_sha256() -> None:
    exact_rows = [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 101.0)]
    base_identity = {
        "schema_version": "kronos_daily_1520_source.v1",
        "source_db_path": _SOURCE_DB_PATH,
    }

    with pytest.raises(CausalPanelContractError, match="source_identity.*source_db_sha256"):
        _build_causal_panel([_observation("005930")], exact_rows, source_calendar=["2024-01-05", "2024-01-08"], source_identity=None)

    with pytest.raises(CausalPanelContractError, match="source_db_sha256"):
        _build_causal_panel([_observation("005930")], exact_rows, source_calendar=["2024-01-05", "2024-01-08"], source_identity=base_identity)

    for bad_sha in (None, "A" * 64):
        bad_identity = {**base_identity, "source_db_sha256": bad_sha}
        with pytest.raises(CausalPanelContractError, match="source_db_sha256"):
            _build_causal_panel([_observation("005930")], exact_rows, source_calendar=["2024-01-05", "2024-01-08"], source_identity=bad_identity)

    panel = build_causal_panel([_observation("005930")], exact_rows, source_calendar=["2024-01-05", "2024-01-08"])
    mutated = copy.deepcopy(panel)
    mutated["source_identity"]["source_db_sha256"] = None
    mutated["panel_sha256"] = _panel_digest(mutated)
    with pytest.raises(CausalPanelContractError, match="source_db_sha256"):
        validate_causal_panel(mutated)


def test_forbidden_daily_fields_daily_source_and_legacy_label_are_rejected() -> None:
    assert "future_return_1d" in FORBIDDEN_DAILY_FIELDS
    exact_rows = [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 101.0)]

    with pytest.raises(CausalPanelContractError, match="daily OHLCV field"):
        build_causal_panel([_observation(daily_close=100.0)], exact_rows, source_calendar=["2024-01-05", "2024-01-08"])

    with pytest.raises(CausalPanelContractError, match="future_return_1d"):
        build_causal_panel([_observation(future_return_1d=0.01)], exact_rows, source_calendar=["2024-01-05", "2024-01-08"])

    with pytest.raises(CausalPanelContractError, match="forbidden or unapproved causal source"):
        build_causal_panel(
            [_observation(source_db_path="D:/Kronos/_database/Stock_Database_ohlcv_1day.db")],
            exact_rows,
            source_calendar=["2024-01-05", "2024-01-08"],
        )


def test_missing_entry_and_exit_statuses_are_explicit_without_nearest_fallback() -> None:
    panel = build_causal_panel(
        [
            _observation("000660", "2024-01-05"),
            _observation("005930", "2024-01-08"),
        ],
        [
            _exact("005930", "2024-01-05", 100.0),
            _exact("005930", "2024-01-08", 105.0),
        ],
        source_calendar=["2024-01-05", "2024-01-08"],
    )

    by_symbol = {row["symbol"]: row for row in panel["rows"]}
    missing_entry = by_symbol["000660"]["label_statuses"]["future_return_h1_1520_proxy"]
    missing_exit = by_symbol["005930"]["label_statuses"]["future_return_h1_1520_proxy"]
    assert missing_entry["status"] == "missing_entry"
    assert by_symbol["000660"]["future_return_h1_1520_proxy"] is None
    assert missing_exit["status"] == "missing_exit"
    assert by_symbol["005930"]["future_return_h1_1520_proxy"] is None
    assert panel["coverage"]["labels"]["future_return_h1_1520_proxy"] == {
        "available": 0,
        "missing_entry": 1,
        "missing_exit": 1,
    }


def test_unavailable_exact_entry_row_is_rejected() -> None:
    with pytest.raises(CausalPanelContractError, match="tradable=true"):
        build_causal_panel(
            [_observation("005930", "2024-01-05")],
            [_exact("005930", "2024-01-05", 100.0, tradable=False), _exact("005930", "2024-01-08", 101.0)],
            source_calendar=["2024-01-05", "2024-01-08"],
        )


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        ({"tradable": False}, "tradable=true"),
        ({"exclusion_reason": "HALTED_OR_NOT_TRADABLE"}, "exclusion_reason"),
        ({"drop_tradable": True}, "missing source-row contract field: tradable"),
        ({"drop_bar_volume_status": True}, "missing source-row contract field: bar_volume_status"),
        ({"amount_to_1520": 1.0}, "amount_to_1520 must be null"),
        ({"volume_to_1520": 100.0}, "cumulative volume fields must be null"),
        ({"timestamp_yyyymmddhhmm": 202401081520}, "compact timestamp must be a JSON string"),
        ({"unexpected_field": True}, "unexpected source-row field: unexpected_field"),
    ),
)
def test_malformed_unavailable_or_partial_exact_exit_rows_are_rejected(mutation: dict[str, object], match: str) -> None:
    mutation = dict(mutation)
    exit_mark = vars(_exact("005930", "2024-01-08", 110.0)).copy()
    if mutation.pop("drop_tradable", False):
        exit_mark.pop("tradable")
    if mutation.pop("drop_bar_volume_status", False):
        exit_mark.pop("bar_volume_status")
    exit_mark.update(mutation)

    with pytest.raises(CausalPanelContractError, match=match):
        build_causal_panel(
            [_observation("005930", "2024-01-05")],
            [
                _exact("005930", "2024-01-05", 100.0),
                exit_mark,
            ],
            source_calendar=["2024-01-05", "2024-01-08"],
        )


def test_manifest_audit_emits_proxy_contract_source_identity_six_false_locks_and_no_amount_approximation() -> None:
    panel = build_causal_panel(
        [_observation("000001", "2024-01-05", source_timestamp="2024-01-05T15:18:00+09:00")],
        [_exact("000001", "2024-01-05", 100.0), _exact("000001", "2024-01-08", 101.0)],
        source_calendar=["2024-01-05", "2024-01-08"],
    )

    assert panel["source_identity"]["schema_version"] == "kronos_daily_1520_source.v1"
    assert panel["source_identity"]["identity_basis"] == "explicit"
    assert panel["source_identity"]["source_db_sha256"] == _VALID_SOURCE_DB_SHA256
    assert panel["source_identity"]["source_tables"] == ["A000001"]
    assert panel["source_identity"]["source_identity_sha256"]
    assert panel["official_close"] is False
    assert panel["contract"]["proxy_1520_not_official_close"] is True
    assert panel["contract"]["no_price_volume_amount_approximation"] is True
    assert len(panel["locks"]) == 6
    assert all(value is False for value in panel["locks"].values())
    assert all(value is False for value in panel["promotion_claims"].values())
    assert panel["audit"]["observation_sources"]["forbidden"] == []
    assert panel["audit"]["source_audit"]["forbidden_sources"] == []
    assert panel["audit"]["observation_sources"]["allowed"] == [_SOURCE_DB_PATH]
    assert panel["audit"]["exact_1520_source"]["official_close"] is False
    assert panel["audit"]["exact_1520_source"]["price_basis"] == "15:20_bar_close_proxy"
    entry = panel["rows"][0]["entry_1520"]
    assert entry["bar_volume_1520"] == 1234.0
    assert "cumulative_volume_1520" not in entry
    assert "amount_1520" not in entry
    assert "cumulative_amount_1520" not in entry


def test_leading_zero_symbols_are_preserved_for_observations_exact_rows_and_labels() -> None:
    panel = build_causal_panel(
        [_observation("000001", "2024-01-05")],
        [_exact("000001", "2024-01-05", 100.0), _exact("000001", "2024-01-08", 103.0)],
        source_calendar=["2024-01-05", "2024-01-08"],
    )

    row = panel["rows"][0]
    assert row["symbol"] == "000001"
    assert row["observations"][0]["symbol"] == "000001"
    assert row["entry_1520"]["symbol"] == "000001"
    assert row["future_return_h1_1520_proxy"] == pytest.approx(0.03)


def test_validation_is_deterministic_and_rejects_mutated_panel_digest() -> None:
    sessions = _six_sessions()
    exact_rows = [_exact("005930", session, 100.0 + index) for index, session in enumerate(reversed(sessions))]
    panel_a = build_causal_panel([_observation("005930", sessions[0])], exact_rows, source_calendar=sessions)
    panel_b = build_causal_panel([_observation("005930", sessions[0])], list(reversed(exact_rows)), source_calendar=sessions)

    assert panel_a["panel_sha256"] == panel_b["panel_sha256"]
    validate_causal_panel(panel_a)

    mutated = copy.deepcopy(panel_a)
    mutated["rows"][0]["labels"]["future_return_h1_1520_proxy"] = 999.0
    with pytest.raises(CausalPanelContractError, match="differs from labels map|panel_sha256"):
        validate_causal_panel(mutated)


def test_validate_causal_panel_requires_available_entry_and_exit_payloads_after_digest_refresh() -> None:
    panel = build_causal_panel(
        [_observation("005930", "2024-01-05")],
        [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 110.0)],
        source_calendar=["2024-01-05", "2024-01-08"],
    )
    label = "future_return_h1_1520_proxy"

    missing_entry = copy.deepcopy(panel)
    missing_entry["rows"][0]["entry_1520"] = None
    missing_entry["panel_sha256"] = _panel_digest(missing_entry)
    with pytest.raises(CausalPanelContractError, match="entry_1520 must be a mapping"):
        validate_causal_panel(missing_entry)

    missing_exit = copy.deepcopy(panel)
    missing_exit["rows"][0]["exit_1520_by_label"][label] = None
    missing_exit["panel_sha256"] = _panel_digest(missing_exit)
    with pytest.raises(CausalPanelContractError, match="exit .* must be a mapping"):
        validate_causal_panel(missing_exit)



def test_validate_causal_panel_requires_exact_payload_source_table_matches_row_symbol_after_digest_refresh() -> None:
    panel = build_causal_panel(
        [_observation("005930", "2024-01-05")],
        [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 110.0)],
        source_calendar=["2024-01-05", "2024-01-08"],
    )
    label = "future_return_h1_1520_proxy"

    mutated_entry = copy.deepcopy(panel)
    mutated_entry["rows"][0]["entry_1520"]["source_table"] = "A000001"
    mutated_entry["panel_sha256"] = _panel_digest(mutated_entry)
    with pytest.raises(CausalPanelContractError, match="source_table must match symbol A005930"):
        validate_causal_panel(mutated_entry)

    mutated_exit = copy.deepcopy(panel)
    mutated_exit["rows"][0]["exit_1520_by_label"][label]["source_table"] = "A000001"
    mutated_exit["panel_sha256"] = _panel_digest(mutated_exit)
    with pytest.raises(CausalPanelContractError, match="source_table must match symbol A005930"):
        validate_causal_panel(mutated_exit)

    mutated_path = copy.deepcopy(panel)
    mutated_path["rows"][0]["entry_1520"]["source_db_path"] = (
        "D:/other/_database/Stock_Database_ohlcv_5min.db"
    )
    mutated_path["panel_sha256"] = _panel_digest(mutated_path)
    with pytest.raises(CausalPanelContractError, match="source_db_path must match panel source_identity"):
        validate_causal_panel(mutated_path)

def test_validate_causal_panel_recomputes_available_returns_after_digest_refresh() -> None:
    panel = build_causal_panel(
        [_observation("005930", "2024-01-05")],
        [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 110.0)],
        source_calendar=["2024-01-05", "2024-01-08"],
    )
    label = "future_return_h1_1520_proxy"

    mutated = copy.deepcopy(panel)
    mutated["rows"][0]["labels"][label] = 0.25
    mutated["rows"][0][label] = 0.25
    mutated["panel_sha256"] = _panel_digest(mutated)

    with pytest.raises(CausalPanelContractError, match="does not match exact 15:20 closes"):
        validate_causal_panel(mutated)

def _closed_contract_panel() -> dict[str, object]:
    return build_causal_panel(
        [_observation("005930", "2024-01-05")],
        [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 110.0)],
        source_calendar=["2024-01-05", "2024-01-08"],
    )


def _set_path(payload: dict[str, object], path: tuple[object, ...], value: object) -> None:
    target: object = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]


def _delete_path(payload: dict[str, object], path: tuple[object, ...]) -> None:
    target: object = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    del target[path[-1]]  # type: ignore[index]


@pytest.mark.parametrize(
    ("path", "value", "match"),
    (
        (("unexpected_top_level",), True, "top-level.*unexpected key"),
        (("fallback_policy",), "nearest_fallback_allowed", "fallback_policy"),
        (("amount_policy",), "price_times_volume_allowed", "amount_policy"),
        (("forbidden_daily_fields",), ["future_return_1d"], "forbidden_daily_fields"),
        (("forbidden_observation_source_suffix",), "_database/Stock_Database_ohlcv_5min.db", "suffix"),
        (("cutoff",), "15:19:00", "cutoff"),
        (("locks", "extra_lock"), False, "locks.*unexpected key"),
        (("locks", "official_close"), True, "locks must all be false"),
        (("promotion_claims", "profit"), True, "live/profit/paper/broker"),
        (("promotion_claims", "extra_claim"), False, "promotion_claims.*unexpected key"),
        (("contract", "no_nearest_fallback"), False, "guardrail flags"),
        (("contract", "unexpected"), True, "contract.*unexpected key"),
        (("audit", "unexpected"), True, "audit.*unexpected key"),
        (("audit", "observation_field_policy", "legacy_future_return_1d_allowed"), True, "observation_field_policy"),
        (("audit", "observation_field_policy", "forbidden_daily_fields"), ["future_return_1d"], "observation_field_policy"),
        (("audit", "observation_field_policy", "unexpected"), False, "observation_field_policy.*unexpected key"),
        (("audit", "observation_sources", "allowed"), ["A005930"], "allowed list must match observed sources"),
        (("audit", "exact_1520_source", "unexpected"), True, "exact source audit.*unexpected key"),
        (("audit", "source_audit", "unexpected"), True, "source_audit.*unexpected key"),
        (("coverage", "unexpected"), True, "coverage.*unexpected key"),
        (("coverage", "labels", "future_return_h1_1520_proxy", "unexpected"), 0, "coverage label.*unexpected key"),
    ),
)
def test_validate_causal_panel_rejects_closed_policy_and_audit_drift_after_digest_refresh(
    path: tuple[object, ...],
    value: object,
    match: str,
) -> None:
    mutated = copy.deepcopy(_closed_contract_panel())
    _set_path(mutated, path, value)
    mutated["panel_sha256"] = _panel_digest(mutated)

    with pytest.raises(CausalPanelContractError, match=match):
        validate_causal_panel(mutated)


@pytest.mark.parametrize(
    ("path", "value", "match"),
    (
        (("rows", 0, "unexpected"), True, "unexpected row key"),
        (("rows", 0, "daily_close"), 1.0, "forbidden daily OHLCV"),
        (("rows", 0, "cutoff"), "15:19:00", "row 0 cutoff"),
        (("rows", 0, "cutoff_timestamp"), "2024-01-05T15:19:00+09:00", "cutoff_timestamp"),
        (("rows", 0, "observation_count"), 2, "observation_count"),
        (("rows", 0, "labels", "future_return_h2_1520_proxy"), None, "labels.*unexpected key"),
        (
            ("rows", 0, "label_statuses", "future_return_h1_1520_proxy", "unexpected"),
            False,
            "label status.*unexpected key",
        ),
        (("rows", 0, "exit_1520_by_label", "future_return_h2_1520_proxy"), None, "exit_1520_by_label.*unexpected key"),
    ),
)
def test_validate_causal_panel_rejects_closed_row_shape_drift_after_digest_refresh(
    path: tuple[object, ...],
    value: object,
    match: str,
) -> None:
    mutated = copy.deepcopy(_closed_contract_panel())
    _set_path(mutated, path, value)
    mutated["panel_sha256"] = _panel_digest(mutated)

    with pytest.raises(CausalPanelContractError, match=match):
        validate_causal_panel(mutated)


@pytest.mark.parametrize(
    ("path", "match"),
    (
        (("rows", 0, "future_return_h5_1520_proxy"), "missing required row key"),
        (("rows", 0, "labels", "future_return_h5_1520_proxy"), "labels.*missing required key"),
        (("rows", 0, "label_statuses", "future_return_h5_1520_proxy"), "label_statuses.*missing required key"),
        (("rows", 0, "exit_1520_by_label", "future_return_h5_1520_proxy"), "exit_1520_by_label.*missing required key"),
    ),
)
def test_validate_causal_panel_rejects_missing_required_row_shape_after_digest_refresh(
    path: tuple[object, ...],
    match: str,
) -> None:
    mutated = copy.deepcopy(_closed_contract_panel())
    _delete_path(mutated, path)
    mutated["panel_sha256"] = _panel_digest(mutated)

    with pytest.raises(CausalPanelContractError, match=match):
        validate_causal_panel(mutated)
