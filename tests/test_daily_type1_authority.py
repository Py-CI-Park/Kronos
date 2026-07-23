import json
from pathlib import Path

import pytest

from stom_rl.daily_type1_authority import AuthorityError, canonical_json, load_type1_authority, sha256_canonical
from scripts.type1_krx_public_authority import build_authority, seal_authority


def _typed(number):
    return {"ISU_SRT_CD": f"{number:06d}", "ISU_ABBRV": f"보통주{number}", "MKT_NM": "KOSPI", "SECUGRP_NM": "주권", "KIND_STKCERT_TP_NM": "보통주", "DOMESTIC_FOREIGN_NM": "국내", "LIST_DD": "2010-01-01", "DELIST_DD": ""}


def _envelope():
    pre = [f"2017-10-{day:02d}" for day in range(1, 31)] + [f"2017-11-{day:02d}" for day in range(1, 30)] + ["2017-12-29"]
    calendar = [{"TRD_DD": date} for date in pre + ["2018-01-02", "2025-06-30"]]
    master = [_typed(number) for number in range(1000, 1506)]
    values = {date: [{"ISU_SRT_CD": f"{number:06d}", "거래대금": number} for number in range(1000, 1506)] for date in pre}
    authority = build_authority(typed_current=master, typed_delisted_chunks=[[]], historical_anchor=master, calendar=calendar, values=values, delisted_chunk_bounds=[{"from": "1973-01-01", "to": "2026-07-24"}], provider_retrieval_utc="2025-07-01T00:00:00Z")
    return seal_authority(authority)


def _write(tmp_path: Path, envelope: dict) -> Path:
    path = tmp_path / "authority.json"
    path.write_bytes(canonical_json(envelope))
    return path


def test_loads_only_canonical_signed_typed_authority(tmp_path):
    authority = load_type1_authority(_write(tmp_path, _envelope()))
    assert authority["authority_id"] == "type1-krx-authority-20260724-003"
    assert authority["stable_symbols"][0] == "001505"
    assert authority["fresh_oos"]["status"] == "NOT_RUN"
    assert authority["query_profile"]["authority_metadata_cutoff"] == "2026-07-24"
    assert authority["approved_dates"]["public_end"] == "2025-06-30"
    assert authority["sessions"]["ordered"][-1] == "2025-06-30"
    assert authority["raw_responses"]["calendar"]["query"]["to"] == "2025-06-30"
    assert authority["raw_responses"]["typed_delisted_chunks"][-1]["query"]["endDd"] == "20260724"
    with pytest.raises(TypeError):
        authority["stable_symbols"] += ("000001",)

def test_reader_reconstructs_isin_join_without_short_code_collision(tmp_path):
    envelope = _envelope()
    historical = envelope["authority"]["raw_responses"]["historical_anchor"]["response"][0]
    typed = envelope["authority"]["raw_responses"]["typed_current"]["response"][0]
    historical["ISU_CD"] = "KR7001000003"
    typed["ISU_CD"] = "KR7001000003"
    collision = dict(typed)
    collision["ISU_CD"] = "KR7999999003"
    collision["KIND_STKCERT_TP_NM"] = "우선주"
    envelope["authority"]["raw_responses"]["typed_delisted_chunks"][0]["response"].append(collision)
    envelope["authority"]["raw_sha256"] = sha256_canonical(envelope["authority"]["raw_responses"])

    authority = load_type1_authority(_write(tmp_path, seal_authority(envelope["authority"])))

    assert "001000" in {row["symbol"] for row in authority["ranking"]["rows"]}
def test_reader_recovers_mdcstat23801_six_digit_isu_cd_anchor_member(tmp_path):
    envelope = _envelope()
    current = envelope["authority"]["raw_responses"]["typed_current"]["response"]
    historical = envelope["authority"]["raw_responses"]["historical_anchor"]["response"]
    delisted = dict(current.pop(0))
    delisted.pop("ISU_SRT_CD")
    delisted["ISU_CD"] = historical[0]["ISU_CD"] = "001000"
    envelope["authority"]["raw_responses"]["typed_delisted_chunks"][0]["response"].append(delisted)
    envelope["authority"]["raw_sha256"] = sha256_canonical(envelope["authority"]["raw_responses"])

    authority = load_type1_authority(_write(tmp_path, seal_authority(envelope["authority"])))

    assert "001000" in {row["symbol"] for row in authority["ranking"]["rows"]}


@pytest.mark.parametrize("mutator", [
    lambda artifact: artifact["authority"]["raw_responses"]["calendar"]["response"].append({"TRD_DD": "2025-07-01"}),
    lambda artifact: artifact["authority"]["ranking"]["rows"].__setitem__(0, {"symbol": "000000", "traded_values": [0] * 60, "median_traded_value": 0}),
    lambda artifact: artifact["authority"]["sessions"].update({"pairs": [[1, 0]]}),
    lambda artifact: artifact["integrity"].update({"signature_b64": "AAAA"}),
])
def test_rejects_typed_raw_rank_calendar_and_signature_tampering(tmp_path, mutator):
    envelope = _envelope()
    mutator(envelope)
    with pytest.raises(AuthorityError):
        load_type1_authority(_write(tmp_path, envelope))


def test_reconstructs_typed_classification_and_ranking_from_signed_raw_responses():
    envelope = _envelope()
    envelope["authority"]["raw_responses"]["typed_current"]["response"][0]["KIND_STKCERT_TP_NM"] = "우선주"
    envelope["authority"]["raw_sha256"] = sha256_canonical(envelope["authority"]["raw_responses"])
    with pytest.raises(AuthorityError, match="typed candidate exclusions"):
        seal_authority(envelope["authority"])

    envelope = _envelope()
    envelope["authority"]["raw_responses"]["traded_value_by_session"]["2017-12-29"]["response"][500]["거래대금"] = 0
    envelope["authority"]["raw_sha256"] = sha256_canonical(envelope["authority"]["raw_responses"])
    with pytest.raises(AuthorityError, match="ranking does not reconstruct"):
        seal_authority(envelope["authority"])


def test_rejects_noncanonical_json(tmp_path):
    path = tmp_path / "authority.json"
    path.write_text(json.dumps(_envelope(), indent=2), encoding="utf-8")
    with pytest.raises(AuthorityError, match="canonical"):
        load_type1_authority(path)
