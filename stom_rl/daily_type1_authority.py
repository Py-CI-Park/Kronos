"""Strict reader for the effective-dated typed Type1 KRX authority artifact."""
from __future__ import annotations

import base64
import hashlib
import re
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "kronos.type1.krx-public-authority.v2"
SIGNING_DOMAIN = b"KRONOS.TYPE1.KRX.PUBLIC.AUTHORITY.V2\x00"
INTEGRITY_LABEL = "local artifact integrity; not KRX/external attestation"
PUBLIC_END = "2025-06-30"
ANCHOR = "2017-12-29"
AUTHORITY_ID = "type1-krx-authority-20260723-002"
MARKETS = ("KOSPI", "KOSDAQ")
MARKET_QUERY_IDS = {"KOSPI": "STK", "KOSDAQ": "KSQ"}


class AuthorityError(ValueError):
    """An authority artifact failed a fail-closed validation rule."""


def canonical_json(value: Any) -> bytes:
    try:
        import rfc8785
    except ImportError as exc:  # pragma: no cover
        raise AuthorityError("rfc8785 is required to verify an authority artifact") from exc
    return rfc8785.dumps(value)


def sha256_canonical(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(freeze(item) for item in value)
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuthorityError(message)


def _median(values: list[int | float]) -> int | float:
    ordered = sorted(values)
    value = (ordered[29] + ordered[30]) / 2
    return int(value) if value.is_integer() else value


def _value(row: Any) -> int:
    if not isinstance(row, Mapping):
        return 0
    for key in ("거래대금", "ACC_TRDVOL", "traded_value", "거래금액", "value"):
        if key in row:
            try:
                return int(row[key])
            except (TypeError, ValueError):
                return 0
    return 0


def _response_rows(capture: Any) -> list[Mapping[str, Any]]:
    if not isinstance(capture, Mapping) or set(capture) != {"query", "response"}:
        raise AuthorityError("raw KRX capture must retain exact query and response")
    response = capture["response"]
    if not isinstance(response, list) or not all(isinstance(row, Mapping) for row in response):
        raise AuthorityError("raw KRX response rows malformed")
    if not isinstance(capture["query"], Mapping):
        raise AuthorityError("raw KRX query malformed")
    return response


def _field(row: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None:
            return str(value).strip()
    return ""


def _symbol(row: Mapping[str, Any]) -> str:
    short = _field(row, "ISU_SRT_CD", "symbol", "단축코드")
    if short:
        return short
    isin = _field(row, "ISU_CD")
    match = re.fullmatch(r"KR7(\d{6})\d{3}", isin)
    return match.group(1) if match else ""
def _typed_row_for_historical(
    historical: Mapping[str, Any],
    typed_by_isin: Mapping[str, Mapping[str, Any]],
    typed_by_symbol: Mapping[str, list[Mapping[str, Any]]],
) -> Mapping[str, Any]:
    """Join KRX instruments by ISIN; only use an unambiguous short-code fallback."""
    isin = _field(historical, "ISU_CD")
    if isin:
        return typed_by_isin.get(isin, {})
    candidates = typed_by_symbol.get(_symbol(historical), [])
    return candidates[0] if len(candidates) == 1 else {}


def _date_key(value: str) -> str:
    return "".join(character for character in value if character.isdigit())



def _typed_exclusion(symbol: str, historical: Mapping[str, Any], typed: Mapping[str, Any]) -> str | None:
    if len(symbol) != 6 or not symbol.isdigit():
        return "not_six_digit_symbol"
    if not _field(historical, "ISU_ABBRV", "ISU_NM", "name", "종목명"):
        return "blank_historical_name"
    if _field(typed, "MKT_NM", "MKT_TP_NM", "market") not in MARKETS:
        return "typed_market_not_kospi_or_kosdaq"
    if _field(typed, "SECUGRP_NM") != "주권":
        return "typed_security_group_not_ordinary_stock"
    if _field(typed, "KIND_STKCERT_TP_NM") != "보통주":
        return "typed_stock_certificate_not_common"
    domestic = _field(typed, "DOMESTIC_FOREIGN_NM", "DOMESTIC_FOREIGN_TP_NM", "NATN_NM", "국내외구분")
    if domestic and domestic not in ("국내", "DOMESTIC"):
        return "typed_group_not_domestic"
    listed = _date_key(_field(typed, "LIST_DD", "listing_date"))
    delisted = _date_key(_field(typed, "DELIST_DD", "delisting_date"))
    anchor = _date_key(ANCHOR)
    if not listed or listed > anchor or (delisted and anchor >= delisted):
        return "not_effective_at_anchor"
    spac = _field(typed, "SPAC_YN", "SPAC_TP_NM")
    if spac and spac not in ("N", "NO", "비해당"):
        return "typed_spac"
    # KRX has no SPAC type on these required surfaces. This narrow historical-name
    # control is permitted only when the typed field is absent.
    name = _field(historical, "ISU_ABBRV", "ISU_NM", "name", "종목명")
    if not spac and ("스팩" in name.upper() or "SPAC" in name.upper()):
        return "historical_name_spac_without_typed_field"
    return None


def validate_authority(envelope: Mapping[str, Any]) -> None:
    _require(set(envelope) == {"authority", "integrity", "schema"}, "unexpected envelope fields")
    _require(envelope["schema"] == SCHEMA, "wrong authority schema")
    authority, integrity = envelope["authority"], envelope["integrity"]
    _require(isinstance(authority, dict) and isinstance(integrity, dict), "malformed envelope")
    required = {"authority_id", "anchor_date", "approved_dates", "provider", "query_profile", "classification_profile", "candidate_exclusions", "raw_responses", "raw_sha256", "sessions", "ranking", "stable_symbols", "fresh_oos"}
    _require(set(authority) == required, "unexpected or missing authority fields")
    _require(authority["authority_id"] == AUTHORITY_ID and authority["anchor_date"] == ANCHOR, "wrong frozen authority identity")
    _require(authority["approved_dates"] == {"calendar_start": "2018-01-02", "public_end": PUBLIC_END}, "wrong approved dates")
    _require(authority["fresh_oos"] == {"status": "NOT_RUN", "no_read": True}, "fresh OOS must remain NOT_RUN/no-read")
    provider = authority["provider"]
    _require(isinstance(provider, Mapping) and provider.get("name") == "KRX public data portal" and set(provider) == {"name", "retrieval_utc"}, "wrong public KRX source identity")
    raw = authority["raw_responses"]
    _require(isinstance(raw, Mapping) and set(raw) == {"calendar", "historical_anchor", "traded_value_by_session", "typed_current", "typed_delisted_chunks"}, "malformed typed raw responses")
    _require(authority["raw_sha256"] == sha256_canonical(raw), "raw response SHA mismatch")
    _validate_signature(authority, integrity)
    _validate_reconstruction(authority)


def _validate_signature(authority: Mapping[str, Any], integrity: Mapping[str, Any]) -> None:
    expected = {"algorithm", "domain", "label", "public_key_b64", "signature_b64"}
    _require(isinstance(integrity, Mapping) and set(integrity) == expected, "malformed integrity envelope")
    _require(integrity["algorithm"] == "Ed25519" and integrity["label"] == INTEGRITY_LABEL and integrity["domain"] == SIGNING_DOMAIN.decode().rstrip("\x00"), "wrong local integrity")
    try:
        public = base64.b64decode(integrity["public_key_b64"], validate=True)
        signature = base64.b64decode(integrity["signature_b64"], validate=True)
        _require(base64.b64encode(public).decode() == integrity["public_key_b64"] and base64.b64encode(signature).decode() == integrity["signature_b64"], "signature encoding is not canonical")
        Ed25519PublicKey.from_public_bytes(public).verify(signature, SIGNING_DOMAIN + canonical_json(authority))
    except (KeyError, TypeError, ValueError, InvalidSignature) as exc:
        raise AuthorityError("invalid local artifact signature") from exc


def _validate_reconstruction(authority: Mapping[str, Any]) -> None:
    raw = authority["raw_responses"]
    calendar = raw["calendar"]
    historical = _response_rows(raw["historical_anchor"])
    current = _response_rows(raw["typed_current"])
    chunks = raw["typed_delisted_chunks"]
    _require(isinstance(chunks, list) and chunks, "missing chunked delisted typed history")
    delisted = [row for chunk in chunks for row in _response_rows(chunk)]
    profile = authority["query_profile"]
    _require(isinstance(profile, Mapping) and profile.get("historical_anchor_surface") == "MDCSTAT01501" and profile.get("typed_current_surface") == "MDCSTAT01901" and profile.get("typed_delisted_surface") == "MDCSTAT23801", "wrong KRX typed query profile")
    _require(profile.get("typed_join") == "ISU_CD exact; unique ISU_SRT_CD fallback", "wrong typed instrument join")
    bounds = profile.get("delisted_chunk_bounds")
    _require(isinstance(bounds, list) and len(bounds) == len(chunks) and all(set(bound) == {"from", "to"} and bound["from"] <= bound["to"] <= PUBLIC_END for bound in bounds), "invalid delisted chunk bounds")
    current_query = raw["typed_current"]["query"]
    historical_query = raw["historical_anchor"]["query"]
    _require(
        current_query == {
            "class": "전종목기본정보",
            "fetch_args": ["ALL"],
            "bld": "dbms/MDC/STAT/standard/MDCSTAT01901",
        },
        "current typed master query is not exact",
    )
    _require(
        historical_query == {
            "calls": [
                {"bld": "dbms/MDC/STAT/standard/MDCSTAT01501", "trdDd": "20171228", "mktId": MARKET_QUERY_IDS[market]}
                for market in MARKETS
            ]
        },
        "historical anchor query is not exact",
    )
    for bound, chunk in zip(bounds, chunks):
        _require(
            chunk["query"] == {
                "bld": "dbms/MDC/STAT/issue/MDCSTAT23801",
                "strtDd": bound["from"].replace("-", ""),
                "endDd": bound["to"].replace("-", ""),
                "mktId": "ALL",
                "isuCd": "ALL",
                "isuCd2": "ALL",
                "share": "1",
                "csvxls_isNo": "true",
            },
            "delisted typed chunk query is not exact",
        )
    _require(isinstance(calendar, Mapping), "malformed calendar capture")
    calendar_rows = _response_rows(calendar)
    dates = sorted(_field(row, "TRD_DD", "date") for row in calendar_rows)
    public = [date for date in dates if "2018-01-02" <= date <= PUBLIC_END]
    _require(public and public[0] == "2018-01-02" and public[-1] == PUBLIC_END and all(date <= PUBLIC_END for date in dates), "invalid public calendar")
    sessions = authority["sessions"]
    _require(sessions.get("ordered") == public and sessions.get("count") == len(public), "sessions do not match public calendar raw authority")
    expected_pairs = [[i, i + 1] for i in range(0, len(public) - 1, 2)]
    _require(sessions.get("pairs") == expected_pairs and sessions.get("parity") == len(public) % 2 and sessions.get("trailing_embargo") == ([len(public)-1] if len(public) % 2 else []), "session pairing invalid")
    typed_by_isin = {
        _field(row, "ISU_CD"): row
        for row in current + delisted
        if _field(row, "ISU_CD")
    }
    typed_by_symbol: dict[str, list[Mapping[str, Any]]] = {}
    for row in current + delisted:
        symbol = _symbol(row)
        if symbol:
            typed_by_symbol.setdefault(symbol, []).append(row)
    historical_by_symbol = {_symbol(row): row for row in historical if _symbol(row)}
    expected_exclusions, eligible = [], set()
    for symbol, row in sorted(historical_by_symbol.items()):
        reason = _typed_exclusion(symbol, row, _typed_row_for_historical(row, typed_by_isin, typed_by_symbol))
        name = _field(row, "ISU_ABBRV", "ISU_NM", "name", "종목명")
        if reason:
            expected_exclusions.append({"symbol": symbol, "name": name, "reason": reason})
        else:
            eligible.add(symbol)
    _require(authority["candidate_exclusions"] == expected_exclusions, "typed candidate exclusions do not reconstruct")
    ranking_sessions = profile.get("ranking_sessions")
    _require(isinstance(ranking_sessions, list) and len(ranking_sessions) == 60 and ranking_sessions == sorted(ranking_sessions) and ranking_sessions[-1] <= ANCHOR, "invalid 60-session ranking window")
    values = raw["traded_value_by_session"]
    _require(isinstance(values, Mapping) and set(values) == set(ranking_sessions), "missing ranking source captures")
    rows = authority["ranking"].get("rows")
    _require(isinstance(rows, list) and len(rows) >= 500, "incomplete ranking")
    expected_rows = []
    for symbol in eligible:
        series = [_value({ _symbol(item): item for item in _response_rows(values[date]) }.get(symbol)) for date in ranking_sessions]
        expected_rows.append({"symbol": symbol, "traded_values": series, "median_traded_value": _median(series)})
    expected_rows.sort(key=lambda row: (-row["median_traded_value"], row["symbol"]))
    _require(rows == expected_rows, "ranking does not reconstruct from typed raw sources")
    _require(authority["ranking"].get("window_sessions") == 60 and authority["ranking"].get("missing_traded_value") == 0 and authority["ranking"].get("tie_break") == "symbol_ascending", "wrong ranking profile")
    _require(authority["stable_symbols"] == [row["symbol"] for row in rows[:500]], "stable symbols do not match typed ranking")


def load_type1_authority(path: str | Path) -> Mapping[str, Any]:
    raw = Path(path).read_bytes()
    try:
        envelope = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorityError("authority artifact is not JSON") from exc
    _require(raw == canonical_json(envelope), "authority artifact is not canonical JSON")
    validate_authority(envelope)
    return freeze(envelope["authority"])


load_authority = load_type1_authority
