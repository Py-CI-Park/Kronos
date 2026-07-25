import json
from pathlib import Path

import pytest

from stom_rl.daily_type1_authority import AuthorityError, canonical_json, load_type1_authority, sha256_canonical
from scripts.type1_krx_public_authority import build_authority, seal_authority


def _typed(number, *, isin=True, **changes):
    symbol = f"{number:06d}"
    row = {"ISU_SRT_CD": symbol, "ISU_CD": f"KR7{symbol}003" if isin else "", "ISU_ABBRV": f"보통주{number}", "MKT_NM": "KOSPI", "SECUGRP_NM": "주권", "KIND_STKCERT_TP_NM": "보통주", "DOMESTIC_FOREIGN_NM": "국내", "LIST_DD": "2010-01-01", "DELIST_DD": ""}
    row.update(changes)
    return row


def _envelope():
    pre = [f"2017-10-{day:02d}" for day in range(1, 31)] + [f"2017-11-{day:02d}" for day in range(1, 30)] + ["2017-12-29"]
    calendar = [{"TRD_DD": date} for date in pre + ["2018-01-02", "2025-06-30"]]
    master = [_typed(number) for number in range(1000, 1506)]
    historical = {"KOSPI": master, "KOSDAQ": []}
    values = {date: {"KOSPI": [{"ISU_SRT_CD": f"{number:06d}", "MKT_NM": "KOSPI", "거래대금": number} for number in range(1000, 1506)], "KOSDAQ": []} for date in pre}
    authority = build_authority(typed_current=master, typed_delisted_chunks=[[]], historical_anchor=historical, calendar=calendar, values=values, delisted_chunk_bounds=[{"from": "1973-01-01", "to": "2026-07-24"}], provider_retrieval_utc="2025-07-01T00:00:00Z")
    return seal_authority(authority)


def _write(tmp_path: Path, envelope: dict) -> Path:
    path = tmp_path / "authority.json"
    path.write_bytes(canonical_json(envelope))
    return path


def _reseal(envelope):
    envelope["authority"]["raw_sha256"] = sha256_canonical(envelope["authority"]["raw_responses"])
    return seal_authority(envelope["authority"])


def test_loads_only_canonical_signed_typed_authority(tmp_path):
    authority = load_type1_authority(_write(tmp_path, _envelope()))
    assert authority["authority_id"] == "type1-krx-authority-20260724-004"
    assert len(authority["stable_symbols"]) == 500
    assert authority["fresh_oos"] == {"status": "NOT_RUN", "no_read": True}
    assert authority["approved_dates"]["public_end"] == "2025-06-30"
    assert authority["raw_responses"]["historical_anchor_by_market"]["KOSPI"]["query"]["mktId"] == "STK"


def test_reader_rejects_blank_foreign_and_duplicate_exact_typed_evidence(tmp_path):
    for changes in ({"ISU_CD": ""}, {"DOMESTIC_FOREIGN_NM": "외국"}):
        envelope = _envelope()
        envelope["authority"]["raw_responses"]["typed_current"]["response"][0].update(changes)
        with pytest.raises(AuthorityError):
            load_type1_authority(_write(tmp_path, _reseal(envelope)))
    envelope = _envelope()
    duplicate = dict(envelope["authority"]["raw_responses"]["typed_current"]["response"][0])
    duplicate["KIND_STKCERT_TP_NM"] = "우선주"
    envelope["authority"]["raw_responses"]["typed_delisted_chunks"][0]["response"].append(duplicate)
    with pytest.raises(AuthorityError):
        load_type1_authority(_write(tmp_path, _reseal(envelope)))


def test_reader_accepts_effective_six_digit_delisted_identity(tmp_path):
    envelope = _envelope()
    current = envelope["authority"]["raw_responses"]["typed_current"]["response"]
    historical = envelope["authority"]["raw_responses"]["historical_anchor_by_market"]["KOSPI"]["response"]
    delisted = dict(current.pop(0))
    delisted.pop("ISU_SRT_CD")
    delisted["ISU_CD"] = historical[0]["ISU_CD"] = "001000"
    delisted["DELIST_DD"] = "2018-01-01"
    envelope["authority"]["raw_responses"]["typed_delisted_chunks"][0]["response"].append(delisted)
    authority = load_type1_authority(_write(tmp_path, _reseal(envelope)))
    assert "001000" in {row["symbol"] for row in authority["ranking"]["rows"]}


@pytest.mark.parametrize("mutator", [
    lambda artifact: artifact["authority"]["raw_responses"]["historical_anchor_by_market"].pop("KOSDAQ"),
    lambda artifact: artifact["authority"]["raw_responses"]["historical_anchor_by_market"]["KOSPI"].update({"query": {}}),
    lambda artifact: artifact["authority"]["raw_responses"]["traded_value_by_session"]["2017-12-29"].pop("KOSDAQ"),
    lambda artifact: artifact["authority"]["raw_responses"]["traded_value_by_session"]["2017-12-29"]["KOSPI"]["response"].__setitem__(0, {"ISU_SRT_CD": "001000", "MKT_NM": "KOSDAQ", "거래대금": 1}),
])
def test_rejects_per_market_capture_omission_swap_and_tampering(tmp_path, mutator):
    envelope = _envelope()
    mutator(envelope)
    with pytest.raises(AuthorityError):
        load_type1_authority(_write(tmp_path, _reseal(envelope)))


def test_rejects_noncanonical_json(tmp_path):
    path = tmp_path / "authority.json"
    path.write_text(json.dumps(_envelope(), indent=2), encoding="utf-8")
    with pytest.raises(AuthorityError, match="canonical"):
        load_type1_authority(path)
