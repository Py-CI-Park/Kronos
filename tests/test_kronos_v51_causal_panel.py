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

_VALID_SOURCE_DB_SHA256 = "0123456789abcdef" * 4
_VALID_SOURCE_IDENTITY: Mapping[str, object] = {
    "schema_version": "kronos_daily_1520_source.v1",
    "source_db_path": "D:/Kronos/_database/Stock_Database_ohlcv_5min.db",
    "source_db_sha256": _VALID_SOURCE_DB_SHA256,
}


def build_causal_panel(
    observation_rows: Sequence[object],
    exact_1520_rows: Sequence[object],
    *,
    horizon_days: Sequence[int] = (1, 3, 5),
    source_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return _build_causal_panel(
        observation_rows,
        exact_1520_rows,
        horizon_days=horizon_days,
        source_identity=_VALID_SOURCE_IDENTITY if source_identity is None else source_identity,
    )


@dataclass(frozen=True)
class Exact1520Fixture:
    symbol: str
    session: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    bar_volume_1520: int
    cumulative_volume_status: str
    amount_status: str
    tradable: bool
    exclusion_reason: str | None
    source_db_path: str
    source_table: str
    source_columns: tuple[str, ...]
    schema_version: str
    causal_cutoff_kst: str
    price_basis: str
    official_close: bool


def _observation(symbol: str = "005930", session: str = "2024-01-05", timestamp: str | None = None, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "symbol": symbol,
        "session": session,
        "timestamp": timestamp or f"{session}T15:19:00+09:00",
        "feature_score": 1.25,
        "source_db_path": "D:/Kronos/_database/Stock_Database_ohlcv_5min.db",
    }
    row.update(extra)
    return row


def _exact(symbol: str, session: str, close: float, **extra: object) -> Exact1520Fixture:
    return Exact1520Fixture(
        symbol=symbol,
        session=session,
        timestamp=f"{session}T15:20:00+09:00",
        open=close - 1.0,
        high=close + 2.0,
        low=close - 2.0,
        close=close,
        bar_volume_1520=1234,
        cumulative_volume_status=str(extra.pop("cumulative_volume_status", "not_verified")),
        amount_status=str(extra.pop("amount_status", "not_verified")),
        tradable=bool(extra.pop("tradable", True)),
        exclusion_reason=extra.pop("exclusion_reason", None),
        source_db_path=str(extra.pop("source_db_path", "D:/Kronos/_database/Stock_Database_ohlcv_5min.db")),
        source_table=str(extra.pop("source_table", f"A{symbol}")),
        source_columns=tuple(extra.pop("source_columns", ("date", "open", "high", "low", "close", "volume"))),
        schema_version=str(extra.pop("schema_version", "kronos_daily_1520_source.v1")),
        causal_cutoff_kst=str(extra.pop("causal_cutoff_kst", "15:20:00")),
        price_basis=str(extra.pop("price_basis", "15:20_bar_close_proxy")),
        official_close=bool(extra.pop("official_close", False)),
    )


def _six_sessions() -> list[str]:
    return ["2024-01-05", "2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11", "2024-01-12"]


def test_trading_session_h1_h3_h5_labels_use_exact_1520_marks_and_not_calendar_days() -> None:
    sessions = _six_sessions()
    closes = [100.0, 110.0, 90.0, 120.0, 150.0, 200.0]
    panel = build_causal_panel(
        [_observation("005930", sessions[0], timestamp=f"{sessions[0]}T15:20:00+09:00")],
        [_exact("005930", session, close) for session, close in zip(sessions, closes)],
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


def test_post_cutoff_observation_timestamp_is_rejected() -> None:
    with pytest.raises(CausalPanelContractError, match="post-cutoff"):
        build_causal_panel(
            [_observation(timestamp="2024-01-05T15:20:01+09:00")],
            [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 101.0)],
        )


def test_date_only_observation_timestamps_are_rejected() -> None:
    exact_rows = [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 101.0)]

    with pytest.raises(CausalPanelContractError, match="intraday time"):
        build_causal_panel([_observation(timestamp="2024-01-05")], exact_rows)

    panel = build_causal_panel([_observation()], exact_rows, horizon_days=(1,))
    mutated = copy.deepcopy(panel)
    mutated["rows"][0]["observations"][0]["timestamp"] = "2024-01-05"
    mutated["panel_sha256"] = _panel_digest(mutated)
    with pytest.raises(CausalPanelContractError, match="intraday time"):
        validate_causal_panel(mutated)


def test_alphabetic_symbols_are_rejected_for_observations_and_exact_rows() -> None:
    exact_rows = [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 101.0)]

    with pytest.raises(CausalPanelContractError, match="six-digit numeric"):
        build_causal_panel([_observation("00AB12")], exact_rows, horizon_days=(1,))

    with pytest.raises(CausalPanelContractError, match="six-digit numeric"):
        build_causal_panel(
            [_observation("005930")],
            [_exact("00AB12", "2024-01-05", 100.0), _exact("00AB12", "2024-01-08", 101.0)],
            horizon_days=(1,),
        )

    with pytest.raises(CausalPanelContractError, match="source_table must match symbol"):
        build_causal_panel(
            [_observation("005930")],
            [
                _exact("005930", "2024-01-05", 100.0, source_table="A000001"),
                _exact("005930", "2024-01-08", 101.0, source_table="A000001"),
            ],
            horizon_days=(1,),
        )


def test_exact_rows_require_explicit_proxy_provenance() -> None:
    for missing_field in ("official_close", "price_basis"):
        entry = vars(_exact("005930", "2024-01-05", 100.0)).copy()
        entry.pop(missing_field)
        with pytest.raises(CausalPanelContractError, match="official_close=false|price_basis"):
            build_causal_panel(
                [_observation("005930")],
                [entry, _exact("005930", "2024-01-08", 101.0)],
                horizon_days=(1,),
            )


def test_source_identity_requires_explicit_non_null_lowercase_sha256() -> None:
    exact_rows = [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 101.0)]
    base_identity = {
        "schema_version": "kronos_daily_1520_source.v1",
        "source_db_path": "D:/Kronos/_database/Stock_Database_ohlcv_5min.db",
    }

    with pytest.raises(CausalPanelContractError, match="source_identity.*source_db_sha256"):
        _build_causal_panel([_observation("005930")], exact_rows, horizon_days=(1,), source_identity=None)

    with pytest.raises(CausalPanelContractError, match="source_db_sha256"):
        _build_causal_panel([_observation("005930")], exact_rows, horizon_days=(1,), source_identity=base_identity)

    for bad_sha in (None, "A" * 64):
        bad_identity = {**base_identity, "source_db_sha256": bad_sha}
        with pytest.raises(CausalPanelContractError, match="source_db_sha256"):
            _build_causal_panel([_observation("005930")], exact_rows, horizon_days=(1,), source_identity=bad_identity)

    panel = build_causal_panel([_observation("005930")], exact_rows, horizon_days=(1,))
    mutated = copy.deepcopy(panel)
    mutated["source_identity"]["source_db_sha256"] = None
    mutated["panel_sha256"] = _panel_digest(mutated)
    with pytest.raises(CausalPanelContractError, match="source_db_sha256"):
        validate_causal_panel(mutated)


def test_forbidden_daily_fields_daily_source_and_legacy_label_are_rejected() -> None:
    assert "future_return_1d" in FORBIDDEN_DAILY_FIELDS
    exact_rows = [_exact("005930", "2024-01-05", 100.0), _exact("005930", "2024-01-08", 101.0)]

    with pytest.raises(CausalPanelContractError, match="daily OHLCV field"):
        build_causal_panel([_observation(daily_close=100.0)], exact_rows)

    with pytest.raises(CausalPanelContractError, match="future_return_1d"):
        build_causal_panel([_observation(future_return_1d=0.01)], exact_rows)

    with pytest.raises(CausalPanelContractError, match="forbidden or unapproved causal source"):
        build_causal_panel(
            [_observation(source_db_path="D:/Kronos/_database/Stock_Database_ohlcv_1day.db")],
            exact_rows,
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
        horizon_days=(1,),
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


def test_unavailable_entry_mark_does_not_become_available_entry_label() -> None:
    panel = build_causal_panel(
        [_observation("005930", "2024-01-05")],
        [_exact("005930", "2024-01-05", 100.0, tradable=False), _exact("005930", "2024-01-08", 101.0)],
        horizon_days=(1,),
    )

    row = panel["rows"][0]
    assert row["entry_1520_status"] == "missing_entry"
    assert row["entry_1520"] is None
    assert row["label_statuses"]["future_return_h1_1520_proxy"]["status"] == "missing_entry"
    assert row["future_return_h1_1520_proxy"] is None


@pytest.mark.parametrize(
    "mutation",
    (
        {"tradable": False},
        {"exclusion_reason": "HALTED_OR_NOT_TRADABLE"},
        {"drop_tradable": True},
    ),
)
def test_unavailable_exit_marks_do_not_become_available_labels(mutation: dict[str, object]) -> None:
    mutation = dict(mutation)
    exit_mark = vars(_exact("005930", "2024-01-08", 110.0)).copy()
    if mutation.pop("drop_tradable", False):
        exit_mark.pop("tradable")
    exit_mark.update(mutation)

    panel = build_causal_panel(
        [_observation("005930", "2024-01-05")],
        [
            _exact("005930", "2024-01-05", 100.0),
            exit_mark,
            _exact("005930", "2024-01-09", 120.0),
        ],
        horizon_days=(1, 2),
    )

    row = panel["rows"][0]
    h1 = "future_return_h1_1520_proxy"
    h2 = "future_return_h2_1520_proxy"
    assert row["label_statuses"][h1]["status"] == "missing_exit"
    assert row["label_statuses"][h1]["exit_session"] == "2024-01-08"
    assert row["exit_1520_by_label"][h1] is None
    assert row[h1] is None
    assert row["label_statuses"][h2]["status"] == "available"
    assert row[h2] == pytest.approx(0.20)


def test_manifest_audit_emits_proxy_contract_source_identity_six_false_locks_and_no_amount_approximation() -> None:
    panel = build_causal_panel(
        [_observation("000001", "2024-01-05", source_timestamp="2024-01-05T15:18:00+09:00")],
        [_exact("000001", "2024-01-05", 100.0), _exact("000001", "2024-01-08", 101.0)],
        horizon_days=(1,),
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
    assert panel["audit"]["observation_sources"]["allowed"] == ["D:/Kronos/_database/Stock_Database_ohlcv_5min.db"]
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
        horizon_days=(1,),
    )

    row = panel["rows"][0]
    assert row["symbol"] == "000001"
    assert row["observations"][0]["symbol"] == "000001"
    assert row["entry_1520"]["symbol"] == "000001"
    assert row["future_return_h1_1520_proxy"] == pytest.approx(0.03)


def test_validation_is_deterministic_and_rejects_mutated_panel_digest() -> None:
    sessions = _six_sessions()
    exact_rows = [_exact("005930", session, 100.0 + index) for index, session in enumerate(reversed(sessions))]
    panel_a = build_causal_panel([_observation("005930", sessions[0])], exact_rows, horizon_days=(1, 3, 5))
    panel_b = build_causal_panel([_observation("005930", sessions[0])], list(reversed(exact_rows)), horizon_days=(1, 3, 5))

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
        horizon_days=(1,),
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
        horizon_days=(1,),
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
        horizon_days=(1,),
    )
    label = "future_return_h1_1520_proxy"

    mutated = copy.deepcopy(panel)
    mutated["rows"][0]["labels"][label] = 0.25
    mutated["rows"][0][label] = 0.25
    mutated["panel_sha256"] = _panel_digest(mutated)

    with pytest.raises(CausalPanelContractError, match="does not match exact 15:20 closes"):
        validate_causal_panel(mutated)
