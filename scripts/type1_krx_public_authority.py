"""Collect and locally seal the effective-dated typed Type1 KRX authority."""
from __future__ import annotations

import contextlib
import io
import argparse
import base64
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from stom_rl.daily_type1_authority import (  # noqa: E402
    ANCHOR, AUTHORITY_ID, INTEGRITY_LABEL, MARKETS, PUBLIC_END, SCHEMA,
    SIGNING_DOMAIN, _field, _median, _symbol, _typed_exclusion, _typed_row_for_historical, _value,
    canonical_json, sha256_canonical, validate_authority,
)

CALENDAR_START = "2018-01-02"
SURFACES = {
    "typed_current": "dbms/MDC/STAT/standard/MDCSTAT01901",
    "typed_delisted": "dbms/MDC/STAT/issue/MDCSTAT23801",
    "historical_anchor": "dbms/MDC/STAT/standard/MDCSTAT01501",
}
DOMESTIC_TYPED_FIELDS = ("DOMESTIC_FOREIGN_NM", "DOMESTIC_FOREIGN_TP_NM", "NATN_NM", "국내외구분")


class CollectionError(RuntimeError):
    """A public source could not be collected completely and safely."""


def _plain(value: Any) -> Any:
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
def _records(value: Any) -> list[Mapping[str, Any]]:
    if hasattr(value, "to_dict"):
        value = value.to_dict(orient="records")
    if not isinstance(value, list) or not all(isinstance(row, Mapping) for row in value):
        raise CollectionError("KRX surface did not return tabular rows")
    return [_plain(dict(row)) for row in value]



def _capture(query: Mapping[str, Any], response: Any) -> dict[str, Any]:
    return {"query": dict(query), "response": _records(response)}


def classify_candidate(symbol: str, historical: Mapping[str, Any], typed: Mapping[str, Any]) -> str | None:
    """Classify solely from KRX typed fields, except the narrow SPAC control."""
    return _typed_exclusion(symbol, historical, typed)


def _build_typed_master(current: list[Mapping[str, Any]], chunks: list[list[Mapping[str, Any]]], historical: list[Mapping[str, Any]]) -> tuple[list[dict[str, str]], set[str]]:
    typed_rows = current + [item for chunk in chunks for item in chunk]
    typed_by_isin = {
        _field(row, "ISU_CD"): row
        for row in typed_rows
        if _field(row, "ISU_CD")
    }
    typed_by_symbol: dict[str, list[Mapping[str, Any]]] = {}
    for row in typed_rows:
        symbol = _symbol(row)
        if symbol:
            typed_by_symbol.setdefault(symbol, []).append(row)
    anchor = {_symbol(row): row for row in historical if _symbol(row)}
    exclusions: list[dict[str, str]] = []
    eligible: set[str] = set()
    for symbol, historical_row in sorted(anchor.items()):
        typed = _typed_row_for_historical(historical_row, typed_by_isin, typed_by_symbol)
        reason = classify_candidate(symbol, historical_row, typed)
        name = _field(historical_row, "ISU_ABBRV", "ISU_NM", "name", "종목명")
        if reason:
            exclusions.append({"symbol": symbol, "name": name, "reason": reason})
        else:
            eligible.add(symbol)
    return exclusions, eligible


def build_authority(*, typed_current: list[Mapping[str, Any]], typed_delisted_chunks: list[list[Mapping[str, Any]]], historical_anchor: list[Mapping[str, Any]], calendar: list[Mapping[str, Any]], values: dict[str, list[Mapping[str, Any]]], delisted_chunk_bounds: list[dict[str, str]], provider_retrieval_utc: str) -> dict[str, Any]:
    """Build from verbatim official responses; used by the offline regression tests."""
    dates = sorted(_field(row, "TRD_DD", "date") for row in calendar)
    public = [date for date in dates if CALENDAR_START <= date <= PUBLIC_END]
    if not public or public[0] != CALENDAR_START or public[-1] != PUBLIC_END:
        raise CollectionError("KRX calendar did not provide approved public session bounds")
    ranking_sessions = [date for date in dates if date <= ANCHOR][-60:]
    if len(ranking_sessions) != 60:
        raise CollectionError("fewer than 60 KRX sessions through anchor")
    if len(typed_delisted_chunks) != len(delisted_chunk_bounds) or not typed_delisted_chunks:
        raise CollectionError("typed delisted history must be captured in bounded chunks")
    exclusions, eligible = _build_typed_master(typed_current, typed_delisted_chunks, historical_anchor)
    if len(eligible) < 500:
        raise CollectionError("fewer than 500 typed ordinary common anchor members")
    if set(values) != set(ranking_sessions):
        raise CollectionError("missing typed ranking session responses")
    rows = []
    for symbol in sorted(eligible):
        series = [_value({_symbol(row): row for row in values[date]}.get(symbol)) for date in ranking_sessions]
        rows.append({"symbol": symbol, "traded_values": series, "median_traded_value": _median(series)})
    rows.sort(key=lambda row: (-row["median_traded_value"], row["symbol"]))
    raw = {
        "calendar": _capture({"bld": "index-calendar", "market": "KOSPI", "index_code": "1001", "from": "2017-01-01", "to": PUBLIC_END}, calendar),
        "historical_anchor": _capture({"calls": [{"bld": SURFACES["historical_anchor"], "trdDd": "20171228", "mktId": market} for market in MARKETS]}, historical_anchor),
        "typed_current": _capture({"class": "전종목기본정보", "fetch_args": ["ALL"], "bld": SURFACES["typed_current"]}, typed_current),
        "typed_delisted_chunks": [_capture({"bld": SURFACES["typed_delisted"], "strtDd": bound["from"].replace("-", ""), "endDd": bound["to"].replace("-", ""), "mktId": "ALL", "isuCd": "ALL", "isuCd2": "ALL", "share": "1", "csvxls_isNo": "true"}, chunk) for bound, chunk in zip(delisted_chunk_bounds, typed_delisted_chunks)],
        "traded_value_by_session": {date: _capture({"bld": "market-ohlcv", "trdDd": date, "mktId": "ALL"}, values[date]) for date in ranking_sessions},
    }
    return {
        "authority_id": AUTHORITY_ID, "anchor_date": ANCHOR,
        "approved_dates": {"calendar_start": CALENDAR_START, "public_end": PUBLIC_END},
        "provider": {"name": "KRX public data portal", "retrieval_utc": provider_retrieval_utc},
        "query_profile": {"historical_anchor_surface": "MDCSTAT01501", "typed_current_surface": "MDCSTAT01901", "typed_delisted_surface": "MDCSTAT23801", "typed_join": "ISU_CD exact; unique ISU_SRT_CD fallback", "anchor_date": ANCHOR, "markets": list(MARKETS), "ranking_sessions": ranking_sessions, "delisted_chunk_bounds": delisted_chunk_bounds},
        "classification_profile": {"effective_dated": "LIST_DD<=anchor<DELIST_DD_or_active", "markets": list(MARKETS), "security_group": "SECUGRP_NM==주권", "certificate_type": "KIND_STKCERT_TP_NM==보통주", "domestic_group_fields": list(DOMESTIC_TYPED_FIELDS), "domestic_values": ["국내", "DOMESTIC"], "name_rule": "historical SPAC only when typed SPAC field absent"},
        "candidate_exclusions": exclusions, "raw_responses": raw, "raw_sha256": sha256_canonical(raw),
        "sessions": {"count": len(public), "first": public[0], "last": public[-1], "ordered": public, "pairs": [[i, i + 1] for i in range(0, len(public) - 1, 2)], "parity": len(public) % 2, "trailing_embargo": [len(public)-1] if len(public) % 2 else []},
        "ranking": {"window_sessions": 60, "missing_traded_value": 0, "tie_break": "symbol_ascending", "rows": rows}, "stable_symbols": [row["symbol"] for row in rows[:500]], "fresh_oos": {"status": "NOT_RUN", "no_read": True},
    }


def seal_authority(authority: dict[str, Any]) -> dict[str, Any]:
    key = Ed25519PrivateKey.generate()
    signature = key.sign(SIGNING_DOMAIN + canonical_json(authority))
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    envelope = {"schema": SCHEMA, "authority": authority, "integrity": {"algorithm": "Ed25519", "domain": SIGNING_DOMAIN.decode().rstrip("\x00"), "label": INTEGRITY_LABEL, "public_key_b64": base64.b64encode(public).decode(), "signature_b64": base64.b64encode(signature).decode()}}
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


@contextlib.contextmanager
def _silence_krx_runtime_output() -> Iterable[None]:
    """Contain dependency-import and authenticated-client login banners."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        yield
def _typed_delisted_bounds() -> list[dict[str, str]]:
    return [
        {
            "from": f"{year}-01-01",
            "to": min(f"{year + 4}-12-31", PUBLIC_END),
        }
        for year in range(1973, int(PUBLIC_END[:4]) + 1, 5)
    ]




def collect_from_krx(quant_insight_root: Path) -> dict[str, Any]:
    """Use authenticated pykrx KRX surfaces without exposing runtime output."""
    with _silence_krx_runtime_output():
        _load_quant_insight_env(quant_insight_root)
        try:
            from pykrx import stock
            from pykrx.website.krx.market.core import KrxWebIo, 전종목기본정보, 전종목시세
        except ImportError as exc:
            raise CollectionError("KRX collection dependencies unavailable") from exc

        class 상장폐지종목기본정보(KrxWebIo):
            bld = "dbms/MDC/STAT/issue/MDCSTAT23801"

        bounds = _typed_delisted_bounds()
        try:
            current = _records(전종목기본정보().fetch("ALL"))
            delisted = [
                _records(
                    상장폐지종목기본정보().read(
                        mktId="ALL", isuCd="ALL", isuCd2="ALL",
                        strtDd=bound["from"].replace("-", ""), endDd=bound["to"].replace("-", ""),
                        share="1", csvxls_isNo="true",
                    )["output"]
                )
                for bound in bounds
            ]
            historical = []
            for market in MARKETS:
                historical.extend(_records(전종목시세().fetch("20171228", market)))
            index = stock.get_index_ohlcv_by_date("20170101", PUBLIC_END.replace("-", ""), "1001")
            calendar = [{"TRD_DD": str(day)[:10]} for day in index.index]
            ranking = sorted(row["TRD_DD"] for row in calendar if row["TRD_DD"] <= ANCHOR)[-60:]
            per_date: dict[str, list[Mapping[str, Any]]] = {}
            for date in ranking:
                combined = []
                for market in MARKETS:
                    frame = stock.get_market_ohlcv_by_ticker(date.replace("-", ""), market=market)
                    combined.extend([{"ISU_SRT_CD": str(symbol), **dict(row)} for symbol, row in frame.to_dict(orient="index").items()])
                per_date[date] = combined
        except Exception as exc:
            raise CollectionError("KRX public collection failed; no artifact was written") from exc
        return build_authority(typed_current=current, typed_delisted_chunks=delisted, historical_anchor=historical, calendar=calendar, values=per_date, delisted_chunk_bounds=bounds, provider_retrieval_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quant-insight-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise CollectionError("refusing to overwrite an existing authority artifact")
    envelope = seal_authority(collect_from_krx(args.quant_insight_root))
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
        raise SystemExit("type1 KRX authority collection failed: " + str(exc))
