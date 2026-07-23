"""Collect and seal the point-in-time Type1 KRX public authority.

This collector intentionally has no product-code dependency on Quant-Insight.  It
uses that checkout only as the credentialed runtime from which pykrx is imported.
"""
from __future__ import annotations

import argparse
import base64
import importlib.metadata
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from stom_rl.daily_type1_authority import (  # noqa: E402
    AUTHORITY_ID,
    EXCLUSION_PATTERNS,
    ANCHOR,
    INTEGRITY_LABEL,
    PUBLIC_END,
    SCHEMA,
    SIGNING_DOMAIN,
    canonical_json,
    sha256_canonical,
    validate_authority,
)

CALENDAR_START = "2018-01-02"


class CollectionError(RuntimeError):
    """A public source could not be collected completely and safely."""


def _date_string(value: Any) -> str:
    return str(value)[:10]


def _plain(value: Any) -> Any:
    """Convert pandas/numpy scalars and frames to deterministic JSON primitives."""
    if hasattr(value, "to_dict") and hasattr(value, "index") and hasattr(value, "columns"):
        return {
            _date_string(index): {str(key): _plain(item) for key, item in row.items()}
            for index, row in value.to_dict(orient="index").items()
        }
    if hasattr(value, "item"):
        try:
            return _plain(value.item())
        except ValueError:
            pass
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, float) and value != value:
        return 0
    return value


def classify_candidate(symbol: str, name: str) -> str | None:
    """Return an explicit exclusion reason, or None for an ordinary common candidate."""
    if not re.fullmatch(r"\d{6}", symbol):
        return "not_six_digit_symbol"
    if not isinstance(name, str) or not name.strip():
        return "blank_historical_name"
    for pattern in EXCLUSION_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return "identity_pattern:" + pattern
    return None


def _median(values: list[int | float]) -> int | float:
    ordered = sorted(values)
    result = (ordered[29] + ordered[30]) / 2
    return int(result) if result.is_integer() else result


def _traded_value(row: Any) -> int | float:
    if not row:
        return 0
    for key in ("거래대금", "traded_value", "거래금액", "value"):
        if key in row:
            value = row[key]
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
    return 0


def build_authority(*, ticker_master: dict[str, dict[str, str]], calendar: dict[str, Any], values: dict[str, dict[str, dict[str, Any]]], provider_version: str, retrieval_utc: str) -> dict[str, Any]:
    """Build the authority from captured public responses (also used by offline tests)."""
    sessions = sorted(date for date in calendar if CALENDAR_START <= date <= PUBLIC_END)
    if not sessions or sessions[0] != CALENDAR_START or sessions[-1] != PUBLIC_END:
        raise CollectionError("KOSPI index authority did not provide the approved session bounds")
    # The published calendar begins after the anchor, so ranking dates must come
    # from the separately captured pre-anchor index sessions supplied by collector.
    ranking_sessions = calendar.get("_ranking_sessions") if isinstance(calendar, dict) else None
    if ranking_sessions is None:
        # Offline callers may provide an already complete calendar including 2017.
        ranking_sessions = sorted(date for date in calendar if date <= ANCHOR)
    if len(ranking_sessions) < 60:
        raise CollectionError("fewer than 60 authoritative sessions through anchor")
    ranking_sessions = list(ranking_sessions[-60:])
    exclusions: list[dict[str, str]] = []
    eligible: list[str] = []
    for market in ("KOSPI", "KOSDAQ"):
        for symbol, name in sorted(ticker_master.get(market, {}).items()):
            reason = classify_candidate(symbol, name)
            if reason:
                exclusions.append({"market": market, "symbol": symbol, "name": name, "reason": reason})
            else:
                eligible.append(symbol)
    rows = []
    for symbol in sorted(set(eligible)):
        traded_values = [_traded_value(values.get(date, {}).get(symbol)) for date in ranking_sessions]
        rows.append({"symbol": symbol, "traded_values": traded_values, "median_traded_value": _median(traded_values)})
    rows.sort(key=lambda row: (-row["median_traded_value"], row["symbol"]))
    if len(rows) < 500:
        raise CollectionError("fewer than 500 eligible ordinary common stocks at anchor")
    public_sessions = sorted(date for date in calendar if CALENDAR_START <= date <= PUBLIC_END)
    raw_responses = {
        "calendar": {date: calendar[date] for date in sorted(calendar) if date != "_ranking_sessions"},
        "ticker_master": ticker_master,
        "traded_value_by_session": {date: values.get(date, {}) for date in ranking_sessions},
    }
    authority = {
        "authority_id": AUTHORITY_ID,
        "anchor_date": ANCHOR,
        "approved_dates": {"calendar_start": CALENDAR_START, "public_end": PUBLIC_END},
        "provider": {"name": "pykrx/KRX public", "package": "pykrx", "version": provider_version, "retrieval_utc": retrieval_utc},
        "query_profile": {"calendar_market": "KOSPI", "calendar_index_code": "1001", "calendar_start": CALENDAR_START, "end_date": PUBLIC_END, "anchor_date": ANCHOR, "ticker_markets": ["KOSPI", "KOSDAQ"], "ranking_sessions": ranking_sessions},
        "classification_profile": {"historical_master_date": ANCHOR, "source_universe_excludes": ["ETF", "ETN", "ELW"], "ordinary_common": {"six_digits": True, "nonblank_name": True, "identity_exclusion_patterns": list(EXCLUSION_PATTERNS)}, "no_survival_filter": True},
        "candidate_exclusions": exclusions,
        "raw_responses": raw_responses,
        "raw_sha256": sha256_canonical(raw_responses),
        "sessions": {"count": len(public_sessions), "first": public_sessions[0], "last": public_sessions[-1], "ordered": public_sessions, "pairs": [[index, index + 1] for index in range(0, len(public_sessions) - 1, 2)], "parity": len(public_sessions) % 2, "trailing_embargo": [len(public_sessions) - 1] if len(public_sessions) % 2 else []},
        "ranking": {"window_sessions": 60, "missing_traded_value": 0, "tie_break": "symbol_ascending", "rows": rows},
        "stable_symbols": [row["symbol"] for row in rows[:500]],
        "fresh_oos": {"status": "NOT_RUN", "no_read": True},
    }
    return authority


def seal_authority(authority: dict[str, Any]) -> dict[str, Any]:
    private_key = Ed25519PrivateKey.generate()
    signature = private_key.sign(SIGNING_DOMAIN + canonical_json(authority))
    public_key = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    envelope = {"schema": SCHEMA, "authority": authority, "integrity": {"algorithm": "Ed25519", "domain": SIGNING_DOMAIN.decode("ascii").rstrip("\x00"), "label": INTEGRITY_LABEL, "public_key_b64": base64.b64encode(public_key).decode("ascii"), "signature_b64": base64.b64encode(signature).decode("ascii")}}
    validate_authority(envelope)
    return envelope


def _load_quant_insight_env(root: Path) -> None:
    env_path = root / ".env"
    if not env_path.is_file():
        raise CollectionError("Quant-Insight .env is required")
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise CollectionError("python-dotenv is required in the Quant-Insight runtime") from exc
    load_dotenv(env_path, override=False)


def collect_from_pykrx(quant_insight_root: Path) -> dict[str, Any]:
    _load_quant_insight_env(quant_insight_root)
    try:
        from pykrx import stock
    except ImportError as exc:
        raise CollectionError("pykrx is unavailable in the Quant-Insight runtime") from exc
    try:
        # No query is allowed later than PUBLIC_END.  The earlier query supplies
        # only the 60 sessions ending at the approved effective-date anchor.
        pre_anchor = _plain(stock.get_index_ohlcv_by_date("2017-01-01", ANCHOR, "1001"))
        public_calendar = _plain(stock.get_index_ohlcv_by_date(CALENDAR_START, PUBLIC_END, "1001"))
        calendar = {**pre_anchor, **public_calendar}
        calendar["_ranking_sessions"] = sorted(pre_anchor)[-60:]
        master = {market: {symbol: stock.get_market_ticker_name(symbol) or "" for symbol in stock.get_market_ticker_list(ANCHOR, market=market)} for market in ("KOSPI", "KOSDAQ")}
        values: dict[str, dict[str, dict[str, Any]]] = {}
        for date in calendar["_ranking_sessions"]:
            merged: dict[str, dict[str, Any]] = {}
            for market in ("KOSPI", "KOSDAQ"):
                merged.update(_plain(stock.get_market_ohlcv_by_ticker(date, market=market)))
            values[date] = merged
    except Exception as exc:
        raise CollectionError("KRX public collection failed; no artifact was written") from exc
    try:
        version = importlib.metadata.version("pykrx")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"
    return build_authority(ticker_master=master, calendar=calendar, values=values, provider_version=version, retrieval_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quant-insight-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise CollectionError("refusing to overwrite an existing authority artifact")
    authority = collect_from_pykrx(args.quant_insight_root)
    envelope = seal_authority(authority)
    try:
        with args.output.open("xb") as handle:
            handle.write(canonical_json(envelope))
    except FileExistsError as exc:
        raise CollectionError("refusing to overwrite an existing authority artifact") from exc
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CollectionError as exc:
        # Do not include exception chains or environment state: they can contain secrets.
        raise SystemExit("type1 KRX authority collection failed: " + str(exc))
