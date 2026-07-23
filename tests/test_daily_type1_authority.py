import json
from pathlib import Path

import pytest

from stom_rl.daily_type1_authority import AuthorityError, canonical_json, load_type1_authority, sha256_canonical
from scripts.type1_krx_public_authority import build_authority, seal_authority


def _envelope():
    pre = [f"2017-10-{day:02d}" for day in range(1, 31)] + [f"2017-11-{day:02d}" for day in range(1, 30)] + ["2017-12-29"]
    calendar = {date: {"종가": 1} for date in pre}
    calendar.update({"2018-01-02": {"종가": 1}, "2025-06-30": {"종가": 1}})
    calendar["_ranking_sessions"] = pre
    master = {"KOSPI": {f"{number:06d}": f"보통주{number}" for number in range(1000, 1506)}, "KOSDAQ": {}}
    values = {date: {symbol: {"거래대금": number} for symbol, number in ((f"{n:06d}", n) for n in range(1000, 1506))} for date in pre}
    return seal_authority(build_authority(ticker_master=master, calendar=calendar, values=values, provider_version="test", retrieval_utc="2025-07-01T00:00:00Z"))


def _write(tmp_path: Path, envelope: dict) -> Path:
    path = tmp_path / "authority.json"
    path.write_bytes(canonical_json(envelope))
    return path


def test_loads_only_canonical_signed_immutable_authority(tmp_path):
    authority = load_type1_authority(_write(tmp_path, _envelope()))
    assert authority["authority_id"] == "type1-krx-authority-20260723-001"
    assert authority["stable_symbols"][0] == "001505"
    assert authority["fresh_oos"]["status"] == "NOT_RUN"
    with pytest.raises(TypeError):
        authority["stable_symbols"] += ("000001",)


@pytest.mark.parametrize("mutator", [
    lambda artifact: artifact["authority"]["raw_responses"]["calendar"].update({"2025-07-01": {}}),
    lambda artifact: artifact["authority"]["ranking"]["rows"].__setitem__(0, {"symbol": "000000", "traded_values": [0] * 60, "median_traded_value": 0}),
    lambda artifact: artifact["authority"]["sessions"].update({"pairs": [[1, 0]]}),
    lambda artifact: artifact["integrity"].update({"signature_b64": "AAAA"}),
])
def test_rejects_raw_rank_calendar_and_signature_tampering(tmp_path, mutator):
    envelope = _envelope()
    mutator(envelope)
    with pytest.raises(AuthorityError):
        load_type1_authority(_write(tmp_path, envelope))
def test_recomputes_classification_and_ranking_from_signed_raw_responses():
    envelope = _envelope()
    envelope["authority"]["raw_responses"]["ticker_master"]["KOSPI"]["001000"] = "테스트 SPAC"
    envelope["authority"]["raw_sha256"] = sha256_canonical(envelope["authority"]["raw_responses"])
    with pytest.raises(AuthorityError, match="candidate exclusions"):
        seal_authority(envelope["authority"])

    envelope = _envelope()
    envelope["authority"]["raw_responses"]["traded_value_by_session"]["2017-12-29"]["001500"] = {"거래대금": 0}
    envelope["authority"]["raw_sha256"] = sha256_canonical(envelope["authority"]["raw_responses"])
    with pytest.raises(AuthorityError, match="rank traded values"):
        seal_authority(envelope["authority"])
    envelope = _envelope()
    envelope["authority"]["raw_responses"]["calendar"]["2024-01-03"] = {"종가": 1}
    envelope["authority"]["raw_sha256"] = sha256_canonical(envelope["authority"]["raw_responses"])
    with pytest.raises(AuthorityError, match="sessions do not match"):
        seal_authority(envelope["authority"])



def test_rejects_noncanonical_signature_base64_spelling(tmp_path):
    envelope = _envelope()
    envelope["integrity"]["signature_b64"] += "\n"
    with pytest.raises(AuthorityError, match="signature"):
        load_type1_authority(_write(tmp_path, envelope))



def test_rejects_noncanonical_json(tmp_path):
    path = tmp_path / "authority.json"
    path.write_text(json.dumps(_envelope(), indent=2), encoding="utf-8")
    with pytest.raises(AuthorityError, match="canonical"):
        load_type1_authority(path)
