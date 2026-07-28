import builtins
from pathlib import Path

import pytest

import scripts.type1_krx_public_authority as collector
from scripts.type1_krx_public_authority import CollectionError, build_authority, classify_candidate, collect_from_krx, main, _typed_delisted_bounds


def _typed(symbol, name, *, isin=True, listed="2010-01-01", delisted="", group="주권", certificate="보통주", domestic="국내"):
    return {"ISU_SRT_CD": symbol, "ISU_CD": f"KR7{symbol}003" if isin else "", "ISU_ABBRV": name, "MKT_NM": "KOSPI", "SECUGRP_NM": group, "KIND_STKCERT_TP_NM": certificate, "DOMESTIC_FOREIGN_NM": domestic, "LIST_DD": listed, "DELIST_DD": delisted}


def _inputs():
    dates = [f"2017-10-{day:02d}" for day in range(1, 31)] + [f"2017-11-{day:02d}" for day in range(1, 30)] + ["2017-12-29", "2018-01-02", "2025-06-30"]
    historical = [_typed(f"{number:06d}", f"종목{number}") for number in range(1000, 1506)]
    values = {date: {"KOSPI": [{"ISU_SRT_CD": f"{number:06d}", "MKT_NM": "KOSPI", "거래대금": number} for number in range(1000, 1506)], "KOSDAQ": []} for date in dates[:60]}
    return list(historical), [[]], {"KOSPI": historical, "KOSDAQ": []}, [{"TRD_DD": date} for date in dates], values, [{"from": "1973-01-01", "to": "2017-12-31"}]


@pytest.mark.parametrize(("typed", "reason"), [
    (_typed("123450", "blank", isin=False), "typed_isin_missing"),
    (_typed("123450", "foreign", domestic="외국"), "typed_group_not_domestic"),
    (_typed("123450", "fund", group="집합투자증권"), "typed_security_group"),
])
def test_typed_filter_rejects_blank_foreign_and_non_stock_evidence(typed, reason):
    assert reason in classify_candidate("123450", typed, typed)


def test_typed_filter_retains_named_delisted_domestic_cases():
    for name in ("메리츠화재", "메리츠증권", "메리츠금융지주", "HD현대인프라코어", "연우"):
        typed = _typed("001234", name, delisted="2018-01-01")
        assert classify_candidate("001234", typed, typed) is None


def test_frozen_ranking_is_exactly_500_and_per_market_captured():
    current, chunks, historical, calendar, values, bounds = _inputs()
    for date in values:
        values[date]["KOSPI"].extend([{"ISU_SRT_CD": "001504", "MKT_NM": "KOSPI", "거래대금": 9999}, {"ISU_SRT_CD": "001505", "MKT_NM": "KOSPI", "거래대금": 9999}])
    authority = build_authority(typed_current=current, typed_delisted_chunks=chunks, historical_anchor=historical, calendar=calendar, values=values, delisted_chunk_bounds=bounds, provider_retrieval_utc="2025-07-01T00:00:00Z")
    assert authority["authority_id"] == "type1-krx-authority-20260724-004"
    assert len(authority["stable_symbols"]) == 500
    assert authority["stable_symbols"].index("001504") < authority["stable_symbols"].index("001505")
    assert authority["raw_responses"]["historical_anchor_by_market"]["KOSDAQ"]["query"]["mktId"] == "KSQ"
    assert authority["fresh_oos"] == {"status": "NOT_RUN", "no_read": True}


def test_exact_isu_cd_conflict_and_reused_ticker_are_rejected():
    current, chunks, historical, calendar, values, bounds = _inputs()
    duplicate = dict(current[0])
    duplicate["KIND_STKCERT_TP_NM"] = "우선주"
    chunks[0].append(duplicate)
    authority = build_authority(typed_current=current, typed_delisted_chunks=chunks, historical_anchor=historical, calendar=calendar, values=values, delisted_chunk_bounds=bounds, provider_retrieval_utc="2025-07-01T00:00:00Z")
    assert "001000" not in {row["symbol"] for row in authority["ranking"]["rows"]}
    current, chunks, historical, calendar, values, bounds = _inputs()
    current = current[1:]
    reused = _typed("001000", "pre-anchor", delisted="2018-01-01")
    chunks[0].extend([_typed("001000", "post-anchor", listed="2018-01-01"), reused])
    historical["KOSPI"][0].pop("ISU_CD")
    authority = build_authority(typed_current=current, typed_delisted_chunks=chunks, historical_anchor=historical, calendar=calendar, values=values, delisted_chunk_bounds=bounds, provider_retrieval_utc="2025-07-01T00:00:00Z")
    assert "001000" in {row["symbol"] for row in authority["ranking"]["rows"]}


def test_mdcstat23801_six_digit_identity_recovers_delisted_member():
    current, _, historical, calendar, values, bounds = _inputs()
    current = current[1:]
    delisted = dict(historical["KOSPI"][0])
    delisted.pop("ISU_SRT_CD")
    delisted["ISU_CD"] = historical["KOSPI"][0]["ISU_CD"] = "001000"
    delisted["DELIST_DD"] = "2018-01-02"
    authority = build_authority(typed_current=current, typed_delisted_chunks=[[delisted]], historical_anchor=historical, calendar=calendar, values=values, delisted_chunk_bounds=bounds, provider_retrieval_utc="2025-07-01T00:00:00Z")
    assert "001000" in {row["symbol"] for row in authority["ranking"]["rows"]}


def test_typed_delisted_metadata_bounds_extend_only_to_metadata_cutoff():
    assert _typed_delisted_bounds()[-1] == {"from": "2023-01-01", "to": "2026-07-24"}


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
    assert capsys.readouterr().out == ""


def test_collector_refuses_existing_output_without_loading_environment(tmp_path: Path):
    output = tmp_path / "authority.json"
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(CollectionError, match="overwrite"):
        main(["--quant-insight-root", str(tmp_path), "--output", str(output)])
