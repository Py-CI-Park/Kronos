"""Strict reader for the frozen Type1 public KRX authority artifact."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "kronos.type1.krx-public-authority.v1"
SIGNING_DOMAIN = b"KRONOS.TYPE1.KRX.PUBLIC.AUTHORITY.V1\x00"
INTEGRITY_LABEL = "local artifact integrity; not KRX/external attestation"
PUBLIC_END = "2025-06-30"
ANCHOR = "2017-12-29"
AUTHORITY_ID = "type1-krx-authority-20260723-001"
EXCLUSION_PATTERNS = (
    r"스팩|SPAC", r"리츠|REIT", r"펀드|FUND", r"인프라|INFRA", r"선박|SHIP",
    r"ETF|ETN|ELW|INDEX|지수",
    r"(?:우|우선주)(?:[A-Z]|\d+)?$|(?:\d+)?우(?:[A-Z])?$|PREF(?:ERRED)?|PREFERRED",
    r"파생|DERIVATIVE|WARRANT|외국|FOREIGN|ADR|GDR",
)


class AuthorityError(ValueError):
    """An authority artifact failed a fail-closed validation rule."""


def canonical_json(value: Any) -> bytes:
    """RFC 8785 canonical JSON, used for both raw material and signatures."""
    try:
        import rfc8785
    except ImportError as exc:  # pragma: no cover - dependency is pinned
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


def _reject_fresh(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if "fresh" in lowered and key != "fresh_oos":
                raise AuthorityError("unexpected fresh/OOS field")
            _reject_fresh(item)
    elif isinstance(value, list):
        for item in value:
            _reject_fresh(item)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuthorityError(message)


def validate_authority(envelope: Mapping[str, Any]) -> None:
    """Validate every rule that makes the artifact safe to consume."""
    _require(set(envelope) == {"authority", "integrity", "schema"}, "unexpected envelope fields")
    _require(envelope["schema"] == SCHEMA, "wrong authority schema")
    authority = envelope["authority"]
    integrity = envelope["integrity"]
    _require(isinstance(authority, dict) and isinstance(integrity, dict), "malformed envelope")
    _reject_fresh(authority)
    required = {
        "anchor_date", "approved_dates", "authority_id", "candidate_exclusions",
        "classification_profile", "fresh_oos", "provider", "query_profile", "ranking",
        "raw_responses", "raw_sha256", "sessions", "stable_symbols",
    }
    _require(set(authority) == required, "unexpected or missing authority fields")
    _require(authority["authority_id"] == AUTHORITY_ID, "wrong frozen authority identity")
    _require(authority["anchor_date"] == ANCHOR, "wrong effective anchor")
    dates = authority["approved_dates"]
    _require(dates == {"calendar_start": "2018-01-02", "public_end": PUBLIC_END}, "wrong approved dates")
    _require(authority["fresh_oos"] == {"status": "NOT_RUN", "no_read": True}, "fresh OOS must remain NOT_RUN/no-read")
    provider = authority["provider"]
    _require(
        isinstance(provider, dict)
        and set(provider) == {"name", "package", "version", "retrieval_utc"}
        and provider["name"] == "pykrx/KRX public"
        and provider["package"] == "pykrx",
        "wrong public KRX source identity",
    )
    profile = authority["query_profile"]
    _require(isinstance(profile, dict), "malformed query authority")
    _require(
        profile == {
            "calendar_market": "KOSPI",
            "calendar_index_code": "1001",
            "calendar_start": "2018-01-02",
            "end_date": PUBLIC_END,
            "anchor_date": ANCHOR,
            "ticker_markets": ["KOSPI", "KOSDAQ"],
            "ranking_sessions": profile.get("ranking_sessions"),
        },
        "wrong query authority",
    )
    ranking_sessions = profile.get("ranking_sessions")
    _require(isinstance(ranking_sessions, list) and len(ranking_sessions) == 60 and ranking_sessions == sorted(ranking_sessions), "wrong authoritative ranking sessions")
    _require(all(isinstance(date, str) and date <= ANCHOR for date in ranking_sessions), "ranking reads past anchor")
    raw_responses = authority["raw_responses"]
    _require(isinstance(raw_responses, dict) and set(raw_responses) == {"calendar", "ticker_master", "traded_value_by_session"}, "malformed raw responses")
    _require(isinstance(raw_responses["calendar"], dict), "malformed raw calendar")
    _require(all(isinstance(date, str) and date <= PUBLIC_END for date in raw_responses["calendar"]), "raw calendar reads past public end")
    expected_ranking_sessions = sorted(date for date in raw_responses["calendar"] if date <= ANCHOR)[-60:]
    _require(ranking_sessions == expected_ranking_sessions, "ranking sessions do not match the last 60 KRX sessions through anchor")
    _require(authority["raw_sha256"] == sha256_canonical(raw_responses), "raw response SHA mismatch")
    _validate_signature(authority, integrity)
    _validate_sessions(authority)
    _validate_ranking(authority)


def _validate_signature(authority: Mapping[str, Any], integrity: Mapping[str, Any]) -> None:
    expected = {"algorithm", "domain", "label", "public_key_b64", "signature_b64"}
    _require(set(integrity) == expected, "malformed integrity envelope")
    _require(integrity["algorithm"] == "Ed25519", "wrong signature algorithm")
    _require(integrity["label"] == INTEGRITY_LABEL, "integrity label is not local")
    _require(integrity["domain"] == SIGNING_DOMAIN.decode("ascii").rstrip("\x00"), "wrong signature domain")
    try:
        public_key_b64 = integrity["public_key_b64"]
        signature_b64 = integrity["signature_b64"]
        _require(isinstance(public_key_b64, str) and isinstance(signature_b64, str), "signature encoding is not text")
        public_key = base64.b64decode(public_key_b64, validate=True)
        signature = base64.b64decode(signature_b64, validate=True)
        _require(base64.b64encode(public_key).decode("ascii") == public_key_b64, "public key encoding is not canonical")
        _require(base64.b64encode(signature).decode("ascii") == signature_b64, "signature encoding is not canonical")
        key = Ed25519PublicKey.from_public_bytes(public_key)
        key.verify(signature, SIGNING_DOMAIN + canonical_json(authority))
    except (ValueError, InvalidSignature) as exc:
        raise AuthorityError("invalid local artifact signature") from exc


def _validate_sessions(authority: Mapping[str, Any]) -> None:
    sessions = authority["sessions"]
    required = {"count", "first", "last", "ordered", "pairs", "parity", "trailing_embargo"}
    _require(isinstance(sessions, dict) and set(sessions) == required, "malformed session authority")
    ordered = sessions["ordered"]
    _require(isinstance(ordered, list) and ordered == sorted(ordered) and len(ordered) == len(set(ordered)), "sessions not strictly ordered")
    raw_calendar = authority["raw_responses"]["calendar"]
    expected_ordered = sorted(date for date in raw_calendar if "2018-01-02" <= date <= PUBLIC_END)
    _require(ordered == expected_ordered, "sessions do not match KOSPI index raw authority")
    _require(ordered and ordered[0] == "2018-01-02" and ordered[-1] == PUBLIC_END, "session date bounds invalid")
    _require(sessions["count"] == len(ordered) and sessions["first"] == ordered[0] and sessions["last"] == ordered[-1], "session counts invalid")
    expected_pairs = [[index, index + 1] for index in range(0, len(ordered) - 1, 2)]
    _require(sessions["pairs"] == expected_pairs, "sessions are not split locally")
    _require(sessions["parity"] == len(ordered) % 2, "session parity invalid")
    expected_tail = [len(ordered) - 1] if len(ordered) % 2 else []
    _require(sessions["trailing_embargo"] == expected_tail, "trailing embargo invalid")


def _validate_ranking(authority: Mapping[str, Any]) -> None:
    ranking = authority["ranking"]
    symbols = authority["stable_symbols"]
    _require(isinstance(ranking, dict), "malformed ranking")
    _require(ranking.get("window_sessions") == 60 and ranking.get("missing_traded_value") == 0, "wrong ranking window")
    _require(ranking.get("tie_break") == "symbol_ascending", "wrong tie rule")
    _require(isinstance(symbols, list) and len(symbols) == 500 and len(set(symbols)) == 500, "authority must have exactly 500 stable slots")
    _require(all(isinstance(symbol, str) and len(symbol) == 6 and symbol.isdigit() for symbol in symbols), "invalid stable symbol")
    rows = ranking.get("rows")
    _require(isinstance(rows, list) and len(rows) >= 500 and all(isinstance(row, dict) for row in rows), "incomplete rank rows")
    expected = sorted(rows, key=lambda row: (-row["median_traded_value"], row["symbol"]))
    _require(rows == expected, "rank rows do not follow median/tie rule")
    _require([row["symbol"] for row in rows[:500]] == symbols, "stable slots do not match ranks")
    for row in rows:
        values = row.get("traded_values")
        _require(isinstance(values, list) and len(values) == 60 and row["median_traded_value"] == _median(values), "invalid median row")
    _validate_classification(authority, rows)


def _validate_classification(authority: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> None:
    profile = authority["classification_profile"]
    _require(isinstance(profile, dict), "malformed classification profile")
    ordinary = profile.get("ordinary_common", {})
    patterns = ordinary.get("identity_exclusion_patterns") if isinstance(ordinary, dict) else None
    _require(profile.get("historical_master_date") == ANCHOR and profile.get("no_survival_filter") is True, "wrong classification profile")
    _require(profile.get("source_universe_excludes") == ["ETF", "ETN", "ELW"], "wrong source universe profile")
    _require(
        ordinary == {
            "six_digits": True,
            "nonblank_name": True,
            "identity_exclusion_patterns": list(EXCLUSION_PATTERNS),
        },
        "wrong ordinary-share filter",
    )
    master = authority["raw_responses"]["ticker_master"]
    _require(
        isinstance(master, dict)
        and set(master) == {"KOSPI", "KOSDAQ"}
        and all(isinstance(master[market], dict) for market in ("KOSPI", "KOSDAQ")),
        "wrong historical ticker master",
    )
    _require(all(isinstance(symbol, str) for market in ("KOSPI", "KOSDAQ") for symbol in master[market]), "historical ticker master has invalid symbols")
    expected_exclusions = []
    eligible = set()
    for market in ("KOSPI", "KOSDAQ"):
        for symbol, name in sorted(master[market].items()):
            reason = _candidate_exclusion(symbol, name, patterns)
            if reason is None:
                eligible.add(symbol)
            else:
                expected_exclusions.append({"market": market, "symbol": symbol, "name": name, "reason": reason})
    _require(authority["candidate_exclusions"] == expected_exclusions, "candidate exclusions do not match frozen profile")
    _require({row["symbol"] for row in rows} == eligible, "ranking includes a non-anchor candidate")
    sessions = authority["query_profile"]["ranking_sessions"]
    raw_values = authority["raw_responses"]["traded_value_by_session"]
    _require(
        isinstance(raw_values, dict)
        and set(raw_values) == set(sessions)
        and all(isinstance(raw_values[date], Mapping) for date in sessions),
        "missing authoritative traded-value session",
    )
    for row in rows:
        expected_values = [_raw_traded_value(raw_values[date].get(row["symbol"])) for date in sessions]
        _require(row["traded_values"] == expected_values, "rank traded values do not match raw response")


def _candidate_exclusion(symbol: Any, name: Any, patterns: list[str]) -> str | None:
    if not isinstance(symbol, str) or re.fullmatch(r"\d{6}", symbol) is None:
        return "not_six_digit_symbol"
    if not isinstance(name, str) or not name.strip():
        return "blank_historical_name"
    for pattern in patterns:
        if re.search(pattern, name, re.IGNORECASE):
            return "identity_pattern:" + pattern
    return None


def _raw_traded_value(row: Any) -> int | float:
    if not isinstance(row, Mapping):
        return 0
    for key in ("거래대금", "traded_value", "거래금액", "value"):
        if key in row:
            try:
                return int(row[key])
            except (TypeError, ValueError):
                return 0
    return 0


def _median(values: list[int | float]) -> float | int:
    ordered = sorted(values)
    result = (ordered[29] + ordered[30]) / 2
    return int(result) if result.is_integer() else result


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
