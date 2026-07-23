from pathlib import Path

import pytest

from scripts.type1_krx_public_authority import CollectionError, build_authority, classify_candidate, main


def _inputs():
    sessions = [f"2017-10-{day:02d}" for day in range(1, 31)] + [f"2017-11-{day:02d}" for day in range(1, 30)] + ["2017-12-29"]
    calendar = {date: {"종가": 1} for date in sessions}
    calendar.update({"2018-01-02": {"종가": 1}, "2025-06-30": {"종가": 1}})
    calendar["_ranking_sessions"] = sessions
    master = {"KOSPI": {f"{number:06d}": f"종목{number}" for number in range(1000, 1506)}, "KOSDAQ": {}}
    values = {date: {symbol: {"거래대금": number} for symbol, number in ((f"{n:06d}", n) for n in range(1000, 1506))} for date in sessions}
    return master, calendar, values


@pytest.mark.parametrize(("symbol", "name", "reason"), [
    ("005935", "삼성전자우", "identity_pattern"),
    ("005935", "삼성전자1우B", "identity_pattern"),
    ("123456", "테스트 SPAC", "identity_pattern"),
    ("123450", "한국리츠", "identity_pattern"),
    ("123450", "인프라펀드", "identity_pattern"),
    ("950000", "Foreign common", "identity_pattern"),
    ("123450", "", "blank_historical_name"),
])
def test_ordinary_common_filter_rejects_explicitly_ambiguous_identities(symbol, name, reason):
    assert reason in classify_candidate(symbol, name)


def test_frozen_ranking_uses_all_60_zeroes_and_symbol_tie():
    master, calendar, values = _inputs()
    # A symbol in later market data but absent from the historical anchor master
    # cannot enter the frozen authority.
    values[calendar["_ranking_sessions"][0]]["777777"] = {"거래대금": 999999}
    master["KOSPI"].update({"001504": "A", "001505": "B"})
    for date in calendar["_ranking_sessions"]:
        values[date]["001504"] = {"거래대금": 9999}
        values[date]["001505"] = {"거래대금": 9999}
    authority = build_authority(ticker_master=master, calendar=calendar, values=values, provider_version="test", retrieval_utc="2025-07-01T00:00:00Z")
    rows = {row["symbol"]: row for row in authority["ranking"]["rows"]}
    assert rows["001504"]["median_traded_value"] == 9999
    assert rows["001505"]["median_traded_value"] == 9999
    assert authority["stable_symbols"].index("001504") < authority["stable_symbols"].index("001505")
    assert "777777" not in rows
    assert len(authority["stable_symbols"]) == 500
    assert authority["sessions"]["pairs"] == [[0, 1]]
    assert authority["sessions"]["trailing_embargo"] == []


def test_leading_zero_and_any_six_digit_ordinary_symbol_are_eligible():
    assert classify_candidate("001234", "보통주") is None
    assert classify_candidate("950001", "보통주") is None


def test_collector_refuses_fewer_than_500_anchor_members():
    master, calendar, values = _inputs()
    master["KOSPI"] = dict(list(master["KOSPI"].items())[:499])
    with pytest.raises(CollectionError, match="fewer than 500"):
        build_authority(ticker_master=master, calendar=calendar, values=values, provider_version="test", retrieval_utc="2025-07-01T00:00:00Z")

def test_collector_refuses_existing_output_without_loading_environment(tmp_path: Path):
    output = tmp_path / "authority.json"
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(CollectionError, match="overwrite"):
        main(["--quant-insight-root", str(tmp_path), "--output", str(output)])
