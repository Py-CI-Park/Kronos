import builtins
from pathlib import Path

import pytest

import scripts.type1_krx_public_authority as collector
from scripts.type1_krx_public_authority import CollectionError, build_authority, classify_candidate, collect_from_krx, main, _typed_delisted_bounds


def _typed(symbol, name, *, listed="2010-01-01", delisted="", group="주권", certificate="보통주", domestic="국내"):
    return {"ISU_SRT_CD": symbol, "ISU_ABBRV": name, "MKT_NM": "KOSPI", "SECUGRP_NM": group, "KIND_STKCERT_TP_NM": certificate, "DOMESTIC_FOREIGN_NM": domestic, "LIST_DD": listed, "DELIST_DD": delisted}


def _inputs():
    dates = [f"2017-10-{day:02d}" for day in range(1, 31)] + [f"2017-11-{day:02d}" for day in range(1, 30)] + ["2017-12-29", "2018-01-02", "2025-06-30"]
    historical = [_typed(f"{number:06d}", f"종목{number}") for number in range(1000, 1506)]
    current = list(historical)
    values = {date: [{"ISU_SRT_CD": f"{number:06d}", "거래대금": number} for number in range(1000, 1506)] for date in dates[:60]}
    return current, [[]], historical, [{"TRD_DD": date} for date in dates], values, [{"from": "1973-01-01", "to": "2017-12-31"}]


@pytest.mark.parametrize(("symbol", "typed", "reason"), [
    ("005935", _typed("005935", "삼성전자우", certificate="우선주"), "typed_stock_certificate"),
    ("123456", _typed("123456", "테스트 SPAC"), "historical_name_spac"),
    ("123450", _typed("123450", "한국리츠", group="집합투자증권"), "typed_security_group"),
    ("123451", _typed("123451", "펀드", group="집합투자증권"), "typed_security_group"),
    ("950000", _typed("950000", "Foreign", domestic="외국"), "typed_group_not_domestic"),
    ("123452", _typed("123452", "later", listed="2018-01-01"), "not_effective_at_anchor"),
])
def test_typed_filter_rejects_ineligible_members(symbol, typed, reason):
    assert reason in classify_candidate(symbol, typed, typed)


def test_typed_filter_retains_ordinary_and_delisted_anchor_members():
    for name in ("메리츠화재", "메리츠증권", "메리츠금융지주", "HD현대인프라코어", "연우"):
        typed = _typed("001234", name, delisted="2018-01-01")
        assert classify_candidate("001234", typed, typed) is None


def test_frozen_ranking_reconstructs_from_typed_anchor_only():
    current, chunks, historical, calendar, values, bounds = _inputs()
    for date in values:
        values[date].extend([{"ISU_SRT_CD": "001504", "거래대금": 9999}, {"ISU_SRT_CD": "001505", "거래대금": 9999}, {"ISU_SRT_CD": "777777", "거래대금": 999999}])
    authority = build_authority(typed_current=current, typed_delisted_chunks=chunks, historical_anchor=historical, calendar=calendar, values=values, delisted_chunk_bounds=bounds, provider_retrieval_utc="2025-07-01T00:00:00Z")
    rows = {row["symbol"]: row for row in authority["ranking"]["rows"]}
    assert rows["001504"]["median_traded_value"] == 9999
    assert authority["stable_symbols"].index("001504") < authority["stable_symbols"].index("001505")
    assert "777777" not in rows
    assert authority["raw_responses"]["typed_current"]["query"]["bld"].endswith("MDCSTAT01901")

def test_isin_join_prevents_reused_short_code_from_overwriting_anchor_type():
    current, chunks, historical, calendar, values, bounds = _inputs()
    historical[0]["ISU_CD"] = "KR7001000003"
    current[0]["ISU_CD"] = "KR7001000003"
    reused = _typed("001000", "reused code", certificate="우선주", delisted="2018-01-02")
    reused["ISU_CD"] = "KR7999999003"
    chunks[0].append(reused)

    authority = build_authority(typed_current=current, typed_delisted_chunks=chunks, historical_anchor=historical, calendar=calendar, values=values, delisted_chunk_bounds=bounds, provider_retrieval_utc="2025-07-01T00:00:00Z")

    assert "001000" in {row["symbol"] for row in authority["ranking"]["rows"]}


def test_post_anchor_delisted_typed_member_remains_eligible():
    current, _, historical, calendar, values, bounds = _inputs()
    current = current[1:]
    delisted = dict(historical[0])
    delisted["DELIST_DD"] = "2018-01-02"

    authority = build_authority(typed_current=current, typed_delisted_chunks=[[delisted]], historical_anchor=historical, calendar=calendar, values=values, delisted_chunk_bounds=bounds, provider_retrieval_utc="2025-07-01T00:00:00Z")

    assert "001000" in {row["symbol"] for row in authority["ranking"]["rows"]}


def test_typed_delisted_metadata_bounds_stop_at_public_end():
    bounds = _typed_delisted_bounds()

    assert bounds[0] == {"from": "1973-01-01", "to": "1977-12-31"}
    assert bounds[-1] == {"from": "2023-01-01", "to": "2025-06-30"}


def test_dependency_import_banner_is_suppressed_before_krx_login(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(collector, "_load_quant_insight_env", lambda root: None)
    original_import = builtins.__import__

    def noisy_missing_import(name, *args, **kwargs):
        if name == "pykrx":
            print("KRX login banner")
            raise ImportError("dependency unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", noisy_missing_import)
    with pytest.raises(CollectionError, match="dependencies unavailable"):
        collect_from_krx(tmp_path)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

def test_collector_refuses_fewer_than_500_typed_anchor_members():
    current, chunks, historical, calendar, values, bounds = _inputs()
    with pytest.raises(CollectionError, match="fewer than 500"):
        build_authority(typed_current=current[:499], typed_delisted_chunks=chunks, historical_anchor=historical[:499], calendar=calendar, values=values, delisted_chunk_bounds=bounds, provider_retrieval_utc="2025-07-01T00:00:00Z")


def test_collector_refuses_existing_output_without_loading_environment(tmp_path: Path):
    output = tmp_path / "authority.json"
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(CollectionError, match="overwrite"):
        main(["--quant-insight-root", str(tmp_path), "--output", str(output)])
