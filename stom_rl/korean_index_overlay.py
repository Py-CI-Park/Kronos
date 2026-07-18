"""Read-only normalized KOSPI/KOSDAQ/RL overlay from offline PyKRX artifacts.

This module performs no collection and has no live-data fallback.  It consumes
already-custodied Korean index artifacts plus an explicitly 15:20-based RL NAV
series, intersects dates exactly, and emits a deterministic normalized-100
research overlay with false locks and no trading/profit claims.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date as Date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
import hashlib
import inspect
import json
from pathlib import Path
import re
from typing import Any, Final

try:  # pragma: no cover - the source module is supplied by the sibling custody task.
    from .korean_index_source import (
        OVERLAY_CLAIMS as _SOURCE_OVERLAY_CLAIMS,
        OVERLAY_FALSE_LOCKS as _SOURCE_OVERLAY_FALSE_LOCKS,
        validate_korean_index_artifact as _source_index_validator,
    )
except Exception:  # pragma: no cover - fail closed at runtime when only overlay code is present.
    _source_index_validator = None
    _SOURCE_OVERLAY_FALSE_LOCKS = None
    _SOURCE_OVERLAY_CLAIMS = None

validate_korean_index_artifact = _source_index_validator

SCHEMA_VERSION: Final = "kronos_v51_korean_index_overlay.v1"
PRICE_BASIS: Final = "15:20_bar_close_proxy"
CAUSAL_CUTOFF_KST: Final = "15:20:00"
NORMALIZATION_BASE: Final = Decimal("100")
NORMALIZED_QUANT: Final = Decimal("0.000000000001")
NORMALIZED_ARITHMETIC: Final = "Decimal ROUND_HALF_UP quantized to 0.000000000001"
MIN_COMMON_DATES: Final = 2

KOSPI: Final = "KOSPI"
KOSDAQ: Final = "KOSDAQ"
RL_MARKET: Final = "RL"

INDEX_ARTIFACT_MISSING: Final = "INDEX_ARTIFACT_MISSING"
INDEX_ARTIFACT_INVALID: Final = "INDEX_ARTIFACT_INVALID"
INDEX_ARTIFACT_VALIDATOR_UNAVAILABLE: Final = "INDEX_ARTIFACT_VALIDATOR_UNAVAILABLE"
INDEX_ARTIFACT_HASH_MISMATCH: Final = "INDEX_ARTIFACT_HASH_MISMATCH"
INDEX_ARTIFACT_MARKET_MISMATCH: Final = "INDEX_ARTIFACT_MARKET_MISMATCH"
INDEX_ARTIFACT_DUPLICATE_DATES: Final = "INDEX_ARTIFACT_DUPLICATE_DATES"
INDEX_ARTIFACT_FORBIDDEN_SOURCE: Final = "INDEX_ARTIFACT_FORBIDDEN_SOURCE"
POINT_IN_TIME_CONSTITUENT_CLAIM: Final = "POINT_IN_TIME_CONSTITUENT_CLAIM"
RL_NAV_MISSING: Final = "RL_NAV_MISSING"
RL_NAV_INVALID: Final = "RL_NAV_INVALID"
RL_NAV_DUPLICATE_DATES: Final = "RL_NAV_DUPLICATE_DATES"
RL_NAV_DAILY_OR_OFFICIAL_CLOSE_SOURCE: Final = "RL_NAV_DAILY_OR_OFFICIAL_CLOSE_SOURCE"
NONPOSITIVE_SERIES_VALUE: Final = "NONPOSITIVE_SERIES_VALUE"
NO_COMMON_DATES: Final = "NO_COMMON_DATES"
TOO_SHORT_INTERSECTION: Final = "TOO_SHORT_INTERSECTION"
OVERLAY_HASH_MISMATCH: Final = "OVERLAY_HASH_MISMATCH"

_FALSE_LOCKS: Final = (
    dict(_SOURCE_OVERLAY_FALSE_LOCKS)
    if isinstance(_SOURCE_OVERLAY_FALSE_LOCKS, Mapping)
    else {
        "official_close": False,
        "full_day_daily_ohlcv": False,
        "live_trading": False,
        "profit_claim": False,
        "paper_trading": False,
        "broker_integration": False,
        "model_build_allowed": False,
        "promotion_allowed": False,
        "go_summary_allowed": False,
        "live_broker_order_allowed": False,
    }
)
_CLAIMS: Final = (
    dict(_SOURCE_OVERLAY_CLAIMS)
    if isinstance(_SOURCE_OVERLAY_CLAIMS, Mapping)
    else {
        "official_close": False,
        "point_in_time_constituents": False,
        "live_trading": False,
        "profit": False,
        "paper_trading": False,
        "broker_integration": False,
    }
)
_HASH_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_DATE_RE: Final = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RL_VALUE_KEYS: Final = (
    "close",
    "nav",
    "policy_nav",
    "economic_nav",
    "account_nav",
    "account_nav_krw",
    "account_nav_krw_decimal",
    "nav_krw",
    "equity",
)
_FORBIDDEN_RL_SOURCE_TOKENS: Final = (
    "official_close",
    "official close",
    "official-close",
    "15:30",
    "full_day",
    "full day",
    "full-day",
    "daily_ohlcv",
    "daily ohlcv",
    "daily-ohlcv",
    "stock_database_ohlcv_1day.db",
    "ohlcv_1day",
    "ohlcv 1day",
    "ohlcv-1day",
    "1day",
    "naver",
)
_RL_SOURCE_IDENTIFIER_KEYS: Final = (
    "source",
    "source_id",
    "source_kind",
    "source_name",
    "source_path",
    "source_db_path",
    "price_source",
    "basis",
    "run_id",
    "run_name",
    "run_path",
    "artifact_id",
    "artifact_path",
)

getcontext().prec = 40


class KoreanIndexOverlayError(ValueError):
    """Raised when the overlay contract fails closed."""

    def __init__(self, reason_codes: Sequence[str], message: str | None = None, payload: Mapping[str, Any] | None = None):
        self.reason_codes = tuple(dict.fromkeys(str(code) for code in reason_codes))
        self.payload = payload
        text = message or ",".join(self.reason_codes) or "Korean index overlay contract failed"
        super().__init__(text)


class _ReasonError(ValueError):
    def __init__(self, reason_code: str, message: str):
        self.reason_code = reason_code
        super().__init__(message)


def canonical_bytes(value: Any) -> bytes:
    """Return deterministic JSON bytes for overlay custody hashes."""

    return json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(value: Any) -> str:
    """Hash deterministic JSON bytes, or raw bytes when bytes are supplied."""

    raw = value if isinstance(value, bytes) else canonical_bytes(value)
    return hashlib.sha256(raw).hexdigest()


def build_korean_index_overlay(
    kospi_artifact: Any,
    kosdaq_artifact: Any,
    rl_nav_series: Any,
    *,
    min_common_dates: int = MIN_COMMON_DATES,
) -> dict[str, Any]:
    """Build a PASS overlay or raise ``KoreanIndexOverlayError`` with reason codes."""

    result = build_korean_index_overlay_result(
        kospi_artifact,
        kosdaq_artifact,
        rl_nav_series,
        min_common_dates=min_common_dates,
    )
    if result["status"] != "PASS":
        raise KoreanIndexOverlayError(result["reason_codes"], payload=result)
    return result


def build_korean_index_overlay_result(
    kospi_artifact: Any,
    kosdaq_artifact: Any,
    rl_nav_series: Any,
    *,
    min_common_dates: int = MIN_COMMON_DATES,
) -> dict[str, Any]:
    """Build an overlay result, returning BLOCKED with exact reason codes on failure."""

    errors: list[dict[str, str]] = []
    try:
        min_common_dates_value = int(min_common_dates)
    except (TypeError, ValueError):
        min_common_dates_value = MIN_COMMON_DATES
        _append_error(errors, TOO_SHORT_INTERSECTION, "min_common_dates must be a positive integer")
    if isinstance(min_common_dates, bool) or min_common_dates_value < 1:
        _append_error(errors, TOO_SHORT_INTERSECTION, "min_common_dates must be a positive integer")
        min_common_dates_value = MIN_COMMON_DATES

    kospi = _safe_load_index_artifact(kospi_artifact, KOSPI, errors)
    kosdaq = _safe_load_index_artifact(kosdaq_artifact, KOSDAQ, errors)
    rl = _safe_load_rl_nav_series(rl_nav_series, errors)

    if errors:
        return _blocked_payload(errors)

    assert kospi is not None and kosdaq is not None and rl is not None
    common_dates = sorted(set(kospi["by_date"]) & set(kosdaq["by_date"]) & set(rl["by_date"]))
    if not common_dates:
        _append_error(errors, NO_COMMON_DATES, "KOSPI, KOSDAQ, and RL NAV have no exact common trading dates")
    elif len(common_dates) < min_common_dates_value:
        _append_error(
            errors,
            TOO_SHORT_INTERSECTION,
            f"Common trading-date intersection has {len(common_dates)} dates, below {min_common_dates_value}",
        )

    if errors:
        return _blocked_payload(errors)

    try:
        payload = _pass_payload(kospi, kosdaq, rl, common_dates, min_common_dates=min_common_dates_value)
    except _ReasonError as exc:
        _append_error(errors, exc.reason_code, str(exc))
        return _blocked_payload(errors)
    return _attach_overlay_hash(payload)


def validate_korean_index_overlay(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate overlay hash and core fail-closed invariants."""

    if not isinstance(payload, Mapping):
        raise KoreanIndexOverlayError([INDEX_ARTIFACT_INVALID], "overlay payload must be a mapping")
    digest = payload.get("overlay_sha256")
    if not isinstance(digest, str) or not _HASH_RE.fullmatch(digest):
        raise KoreanIndexOverlayError([OVERLAY_HASH_MISMATCH], "overlay_sha256 is missing or invalid")
    body = dict(payload)
    body.pop("overlay_sha256", None)
    if sha256_hex(body) != digest:
        raise KoreanIndexOverlayError([OVERLAY_HASH_MISMATCH], "overlay_sha256 does not match canonical overlay bytes")
    try:
        _require_exact_false_map(payload.get("false_locks"), _FALSE_LOCKS, "overlay false_locks", INDEX_ARTIFACT_INVALID)
        _require_exact_false_map(payload.get("claims"), _CLAIMS, "overlay claims", INDEX_ARTIFACT_INVALID)
        _require_persisted_overlay_provenance(payload)
    except _ReasonError as exc:
        raise KoreanIndexOverlayError([exc.reason_code], str(exc)) from exc
    if payload.get("official_close") is not False or payload.get("price_basis") != PRICE_BASIS:
        raise KoreanIndexOverlayError([RL_NAV_DAILY_OR_OFFICIAL_CLOSE_SOURCE], "overlay must remain exact 15:20 and official_close=false")
    if payload.get("status") == "BLOCKED":
        return payload
    if payload.get("status") != "PASS" or payload.get("reason_codes") != []:
        raise KoreanIndexOverlayError([INDEX_ARTIFACT_INVALID], "PASS overlay must have empty reason_codes")
    common_dates = list((payload.get("coverage") or {}).get("common_dates") or [])
    if not common_dates or common_dates != sorted(set(common_dates)):
        raise KoreanIndexOverlayError([INDEX_ARTIFACT_INVALID], "overlay common_dates must be sorted and unique")
    series = payload.get("series")
    if not isinstance(series, list) or len(series) != 3:
        raise KoreanIndexOverlayError([INDEX_ARTIFACT_INVALID], "overlay must contain KOSPI, KOSDAQ, and RL series")
    for item in series:
        if not isinstance(item, Mapping):
            raise KoreanIndexOverlayError([INDEX_ARTIFACT_INVALID], "overlay series entries must be mappings")
        rows = item.get("series")
        if not isinstance(rows, list) or [row.get("date") for row in rows if isinstance(row, Mapping)] != common_dates:
            raise KoreanIndexOverlayError([INDEX_ARTIFACT_INVALID], "overlay series must use the exact common date list")
        if rows[0].get("close") != "100.000000000000":
            raise KoreanIndexOverlayError([INDEX_ARTIFACT_INVALID], "each overlay series must start at normalized 100")
    return payload


def _require_persisted_overlay_provenance(payload: Mapping[str, Any]) -> None:
    if payload.get("read_only") is not True:
        raise _ReasonError(INDEX_ARTIFACT_FORBIDDEN_SOURCE, "overlay read_only must remain true")
    if payload.get("network_used") is not False:
        raise _ReasonError(INDEX_ARTIFACT_FORBIDDEN_SOURCE, "overlay network_used must remain false")
    if payload.get("point_in_time_constituents") is not False:
        raise _ReasonError(
            POINT_IN_TIME_CONSTITUENT_CLAIM,
            "overlay must not claim point-in-time constituents",
        )
    if payload.get("source_policy") != _source_policy():
        raise _ReasonError(
            INDEX_ARTIFACT_FORBIDDEN_SOURCE,
            "overlay source_policy must remain pykrx-only offline/Naver-disabled/no-network",
        )
    if payload.get("status") == "PASS":
        _require_pass_source_artifacts(payload.get("source_artifacts"))


def _require_pass_source_artifacts(value: Any) -> None:
    if not isinstance(value, Mapping) or {str(key) for key in value} != {KOSPI, KOSDAQ, RL_MARKET}:
        raise _ReasonError(
            INDEX_ARTIFACT_INVALID,
            "PASS overlay source_artifacts must exactly enumerate KOSPI, KOSDAQ, and RL",
        )
    for market in (KOSPI, KOSDAQ):
        artifact = value.get(market)
        if not isinstance(artifact, Mapping) or artifact.get("market") != market:
            raise _ReasonError(
                INDEX_ARTIFACT_INVALID,
                f"{market} source_artifact must be a mapping for that market",
            )
        _require_index_source_artifact_provenance(artifact, market)
    rl_artifact = value.get(RL_MARKET)
    if not isinstance(rl_artifact, Mapping) or rl_artifact.get("market") != RL_MARKET:
        raise _ReasonError(INDEX_ARTIFACT_INVALID, "RL source_artifact must be a mapping")
    if rl_artifact.get("price_basis") != PRICE_BASIS or rl_artifact.get("official_close") is not False:
        raise _ReasonError(
            RL_NAV_DAILY_OR_OFFICIAL_CLOSE_SOURCE,
            "RL source_artifact must remain exact 15:20 and official_close=false",
        )


def _require_index_source_artifact_provenance(artifact: Mapping[str, Any], market: str) -> None:
    metadata = artifact.get("source_metadata")
    if not isinstance(metadata, Mapping):
        raise _ReasonError(
            INDEX_ARTIFACT_FORBIDDEN_SOURCE,
            f"{market} source_artifact.source_metadata must be a mapping",
        )
    provider_package = artifact.get("provider_package")
    source_package = metadata.get("source_package")
    if (
        str(metadata.get("provider") or "").lower() != "pykrx"
        or not isinstance(provider_package, Mapping)
        or provider_package.get("name") != "pykrx"
        or not isinstance(source_package, Mapping)
        or source_package.get("name") != "pykrx"
    ):
        raise _ReasonError(
            INDEX_ARTIFACT_FORBIDDEN_SOURCE,
            f"{market} source_artifact provider must remain pykrx",
        )
    required_flags = {
        "runtime_read_only": True,
        "naver_disabled": True,
        "naver_source_used": False,
        "no_live_fetch": True,
        "no_fallback": True,
        "fallback_enabled": False,
        "no_interpolation": True,
        "no_fill": True,
        "official_close": False,
        "point_in_time_constituents": False,
        "index_levels_only": True,
    }
    for key, expected in required_flags.items():
        if metadata.get(key) is not expected:
            reason = (
                POINT_IN_TIME_CONSTITUENT_CLAIM
                if key == "point_in_time_constituents"
                else INDEX_ARTIFACT_FORBIDDEN_SOURCE
            )
            raise _ReasonError(
                reason,
                f"{market} source_artifact.source_metadata.{key} must be {expected}",
            )
    if metadata.get("fallback_sources") != []:
        raise _ReasonError(
            INDEX_ARTIFACT_FORBIDDEN_SOURCE,
            f"{market} source_artifact fallback_sources must be empty",
        )
    if metadata.get("point_in_time_limitation") != "index_levels_only_not_constituents":
        raise _ReasonError(
            POINT_IN_TIME_CONSTITUENT_CLAIM,
            f"{market} source_artifact point-in-time limitation drifted",
        )
    point_in_time = artifact.get("point_in_time")
    if (
        not isinstance(point_in_time, Mapping)
        or point_in_time.get("constituents") is not False
        or point_in_time.get("index_levels_only") is not True
    ):
        raise _ReasonError(
            POINT_IN_TIME_CONSTITUENT_CLAIM,
            f"{market} source_artifact point-in-time custody drifted",
        )


def _safe_load_index_artifact(source: Any, expected_market: str, errors: list[dict[str, str]]) -> dict[str, Any] | None:
    try:
        return _load_index_artifact(source, expected_market)
    except _ReasonError as exc:
        _append_error(errors, exc.reason_code, f"{expected_market}: {exc}")
    except Exception as exc:  # defensive fail-closed boundary around sibling validator.
        _append_error(errors, _classify_validation_exception(exc), f"{expected_market}: {exc}")
    return None


def _load_index_artifact(source: Any, expected_market: str) -> dict[str, Any]:
    if source is None:
        raise _ReasonError(INDEX_ARTIFACT_MISSING, "index artifact source is missing")
    artifact_path: str | None = None
    artifact_file_sha256: str | None = None
    validator = validate_korean_index_artifact
    if validator is None:
        raise _ReasonError(
            INDEX_ARTIFACT_VALIDATOR_UNAVAILABLE,
            "stom_rl.korean_index_source.validate_korean_index_artifact is unavailable",
        )
    try:
        payload = _call_index_validator(validator, source, expected_market)
    except FileNotFoundError as exc:
        raise _ReasonError(INDEX_ARTIFACT_MISSING, str(exc)) from exc
    except Exception as exc:
        raise _ReasonError(_classify_validation_exception(exc), str(exc)) from exc
    if not isinstance(source, Mapping):
        artifact_path = str(source)
        artifact_file_sha256 = _optional_file_sha256(source)
    validated = _validate_index_payload_shape(payload, expected_market)
    if artifact_path is not None:
        validated["artifact_path"] = artifact_path
    if artifact_file_sha256 is not None:
        validated["artifact_file_sha256"] = artifact_file_sha256
    return validated


def _call_index_validator(validator: Any, source: Any, expected_market: str) -> Any:
    try:
        signature = inspect.signature(validator)
    except (TypeError, ValueError):
        signature = None
    if signature is not None and "expected_market" in signature.parameters:
        return validator(source, expected_market=expected_market)
    try:
        return validator(source, expected_market=expected_market)
    except TypeError as exc:
        text = str(exc)
        if "expected_market" in text or "unexpected keyword" in text:
            return validator(source)
        raise


def _validate_index_payload_shape(payload: Any, expected_market: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise _ReasonError(INDEX_ARTIFACT_INVALID, "validated index artifact must be a mapping")
    market = _required_text(payload.get("market"), "index artifact market", INDEX_ARTIFACT_INVALID)
    if market != expected_market:
        raise _ReasonError(INDEX_ARTIFACT_MARKET_MISMATCH, f"expected {expected_market}, got {market}")
    series = _parse_series(
        payload.get("series"),
        value_keys=("close",),
        duplicate_reason=INDEX_ARTIFACT_DUPLICATE_DATES,
        invalid_reason=INDEX_ARTIFACT_INVALID,
        label=f"{expected_market} series",
        require_ordered=True,
    )
    hashes = {
        key: _required_sha(payload.get(key), f"{expected_market} {key}")
        for key in ("raw_sha256", "normalized_sha256", "artifact_sha256")
    }
    metadata = payload.get("source_metadata")
    if not isinstance(metadata, Mapping):
        raise _ReasonError(INDEX_ARTIFACT_INVALID, f"{expected_market} source_metadata must be a mapping")
    provider = str(metadata.get("provider") or "")
    if provider.lower() != "pykrx":
        raise _ReasonError(INDEX_ARTIFACT_FORBIDDEN_SOURCE, f"{expected_market} provider must be pykrx")
    for key in ("naver_disabled", "no_live_fetch", "no_fallback", "no_interpolation"):
        if metadata.get(key) is not True:
            raise _ReasonError(INDEX_ARTIFACT_FORBIDDEN_SOURCE, f"{expected_market} source_metadata.{key} must be true")
    if metadata.get("official_close") is not False:
        raise _ReasonError(INDEX_ARTIFACT_FORBIDDEN_SOURCE, f"{expected_market} source must not claim official close")
    if metadata.get("point_in_time_constituents") is not False:
        raise _ReasonError(POINT_IN_TIME_CONSTITUENT_CLAIM, f"{expected_market} must not claim point-in-time constituents")
    _require_exact_false_map(payload.get("false_locks"), _FALSE_LOCKS, f"{expected_market} false_locks", INDEX_ARTIFACT_INVALID)
    _require_exact_false_map(payload.get("claims"), _CLAIMS, f"{expected_market} claims", INDEX_ARTIFACT_INVALID)
    by_date = {row["date"]: row["close"] for row in series}
    return {
        "market": market,
        "index_code": payload.get("index_code"),
        "index_name": payload.get("index_name"),
        "requested_start_date": payload.get("requested_start_date"),
        "requested_end_date": payload.get("requested_end_date"),
        "actual_start_date": payload.get("actual_start_date"),
        "actual_end_date": payload.get("actual_end_date"),
        "series": series,
        "by_date": by_date,
        "hashes": hashes,
        "source_metadata": _jsonable(dict(metadata)),
        "series_count": len(series),
        "provider_package": _jsonable(payload.get("provider_package")),
        "package": _jsonable(payload.get("package")),
        "parser": _jsonable(payload.get("parser")),
        "license_review": _jsonable(payload.get("license_review")),
        "point_in_time": _jsonable(payload.get("point_in_time")),
        "source_lineage": _jsonable(payload.get("source_lineage")),
        "artifact_filename": payload.get("artifact_filename"),
        "source_artifact_filename": payload.get("source_artifact_filename"),
    }


def _safe_load_rl_nav_series(source: Any, errors: list[dict[str, str]]) -> dict[str, Any] | None:
    try:
        return _validate_rl_nav_series(source)
    except _ReasonError as exc:
        _append_error(errors, exc.reason_code, str(exc))
    except Exception as exc:
        _append_error(errors, RL_NAV_INVALID, str(exc))
    return None


def _validate_rl_nav_series(source: Any) -> dict[str, Any]:
    if source is None:
        raise _ReasonError(RL_NAV_MISSING, "RL NAV series is missing")
    metadata: Mapping[str, Any] = {}
    top_price_basis: Any = None
    top_official_close: Any = None
    rows_value: Any = source
    source_label = "rl_nav_series"
    if isinstance(source, Mapping):
        metadata_value = source.get("source_metadata", source.get("metadata", {}))
        metadata = metadata_value if isinstance(metadata_value, Mapping) else {}
        for key in ("series", "rows", "nav_series", "policy_nav"):
            if key in source:
                rows_value = source[key]
                break
        else:
            raise _ReasonError(RL_NAV_MISSING, "RL NAV payload missing series rows")
        top_price_basis = source.get("price_basis", metadata.get("price_basis"))
        top_official_close = source.get("official_close", metadata.get("official_close"))
        source_label = str(source.get("source_id") or source.get("run_id") or source_label)
        if _has_forbidden_rl_source(source, metadata):
            raise _ReasonError(
                RL_NAV_DAILY_OR_OFFICIAL_CLOSE_SOURCE,
                "RL NAV top-level source/run identifiers must not reference full-day, daily-OHLCV, 1day, Naver, or official-close provenance",
            )
    rows = _parse_rl_rows(rows_value, top_price_basis=top_price_basis, top_official_close=top_official_close, metadata=metadata)
    if not rows:
        raise _ReasonError(RL_NAV_MISSING, "RL NAV series is empty")
    by_date = {row["date"]: row["close"] for row in rows}
    source_sha256 = sha256_hex(
        {
            "price_basis": PRICE_BASIS,
            "official_close": False,
            "metadata": _jsonable(dict(metadata)),
            "series": [{"date": row["date"], "close": _decimal_text(row["close"])} for row in rows],
        }
    )
    return {
        "market": RL_MARKET,
        "series": rows,
        "by_date": by_date,
        "series_count": len(rows),
        "source_sha256": source_sha256,
        "source_label": source_label,
        "source_metadata": _jsonable(dict(metadata)),
    }


def _parse_rl_rows(
    rows_value: Any,
    *,
    top_price_basis: Any,
    top_official_close: Any,
    metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if isinstance(rows_value, (str, bytes)) or not isinstance(rows_value, Sequence):
        raise _ReasonError(RL_NAV_MISSING, "RL NAV rows must be a sequence")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(rows_value):
        if not isinstance(raw, Mapping):
            raise _ReasonError(RL_NAV_INVALID, f"RL NAV row {index} must be a mapping")
        price_basis = raw["price_basis"] if "price_basis" in raw else top_price_basis
        official_close = raw["official_close"] if "official_close" in raw else top_official_close
        if price_basis != PRICE_BASIS or official_close is not False or _has_forbidden_rl_source(raw, metadata):
            raise _ReasonError(
                RL_NAV_DAILY_OR_OFFICIAL_CLOSE_SOURCE,
                "RL NAV rows must explicitly use exact 15:20 proxy and official_close=false",
            )
        row_date = _session_date(raw.get("date"), f"RL NAV row {index} date", RL_NAV_INVALID)
        if row_date in seen:
            raise _ReasonError(RL_NAV_DUPLICATE_DATES, f"duplicate RL NAV date: {row_date}")
        seen.add(row_date)
        value = _first_present(raw, _RL_VALUE_KEYS)
        rows.append({"date": row_date, "close": _positive_decimal(value, f"RL NAV row {index} value", RL_NAV_INVALID)})
    return sorted(rows, key=lambda row: row["date"])


def _parse_series(
    rows_value: Any,
    *,
    value_keys: Sequence[str],
    duplicate_reason: str,
    invalid_reason: str,
    label: str,
    require_ordered: bool,
) -> list[dict[str, Any]]:
    if isinstance(rows_value, (str, bytes)) or not isinstance(rows_value, Sequence):
        raise _ReasonError(invalid_reason, f"{label} must be a sequence")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(rows_value):
        if not isinstance(raw, Mapping):
            raise _ReasonError(invalid_reason, f"{label} row {index} must be a mapping")
        row_date = _session_date(raw.get("date"), f"{label} row {index} date", invalid_reason)
        if row_date in seen:
            raise _ReasonError(duplicate_reason, f"duplicate date in {label}: {row_date}")
        seen.add(row_date)
        value = _first_present(raw, value_keys)
        rows.append({"date": row_date, "close": _positive_decimal(value, f"{label} row {index} close", invalid_reason)})
    if require_ordered and [row["date"] for row in rows] != sorted(row["date"] for row in rows):
        raise _ReasonError(invalid_reason, f"{label} must be ordered by date")
    return rows if require_ordered else sorted(rows, key=lambda row: row["date"])


def _pass_payload(
    kospi: Mapping[str, Any],
    kosdaq: Mapping[str, Any],
    rl: Mapping[str, Any],
    common_dates: Sequence[str],
    *,
    min_common_dates: int,
) -> dict[str, Any]:
    series_entries = [
        _overlay_series_entry(kospi, common_dates, kind="pykrx_index"),
        _overlay_series_entry(kosdaq, common_dates, kind="pykrx_index"),
        _overlay_series_entry(rl, common_dates, kind="rl_economic_nav"),
    ]
    coverage = _coverage(kospi, kosdaq, rl, common_dates, min_common_dates=min_common_dates)
    source_artifacts = {
        KOSPI: _index_source_ref(kospi),
        KOSDAQ: _index_source_ref(kosdaq),
        RL_MARKET: {
            "market": RL_MARKET,
            "series_count": rl["series_count"],
            "source_sha256": rl["source_sha256"],
            "source_label": rl["source_label"],
            "source_metadata": rl["source_metadata"],
            "price_basis": PRICE_BASIS,
            "official_close": False,
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "reason_codes": [],
        "read_only": True,
        "network_used": False,
        "market": "KOREA",
        "price_basis": PRICE_BASIS,
        "causal_cutoff_kst": CAUSAL_CUTOFF_KST,
        "official_close": False,
        "normalization": {
            "base": "100",
            "first_common_date": common_dates[0],
            "arithmetic": NORMALIZED_ARITHMETIC,
            "no_fill": True,
            "no_interpolation": True,
            "no_nearest_date": True,
        },
        "source_policy": _source_policy(),
        "point_in_time_constituents": False,
        "point_in_time_limitation": "No point-in-time constituent membership is claimed; overlay uses only official index level artifacts and RL NAV dates.",
        "false_locks": dict(_FALSE_LOCKS),
        "claims": dict(_CLAIMS),
        "coverage": coverage,
        "series": series_entries,
        "source_artifacts": source_artifacts,
        "source_artifact_hashes": {
            KOSPI: dict(kospi["hashes"]),
            KOSDAQ: dict(kosdaq["hashes"]),
            RL_MARKET: {"source_sha256": rl["source_sha256"]},
        },
        "hash_algorithm": "SHA256_CANONICAL_JSON_SORT_KEYS_NO_SELF_FIELD",
    }


def _overlay_series_entry(contract: Mapping[str, Any], common_dates: Sequence[str], *, kind: str) -> dict[str, Any]:
    market = str(contract["market"])
    by_date: Mapping[str, Decimal] = contract["by_date"]
    start = by_date[common_dates[0]]
    if start <= 0 or not start.is_finite():
        raise _ReasonError(NONPOSITIVE_SERIES_VALUE, f"{market} first common date value must be finite and positive")
    rows = []
    for row_date in common_dates:
        value = by_date[row_date]
        if value <= 0 or not value.is_finite():
            raise _ReasonError(NONPOSITIVE_SERIES_VALUE, f"{market} value on {row_date} must be finite and positive")
        rows.append({"date": row_date, "close": _normalized_text(value, start)})
    source = {"price_basis": PRICE_BASIS, "official_close": False}
    if market in {KOSPI, KOSDAQ}:
        source.update(_index_source_ref(contract))
    else:
        source.update({"source_sha256": contract["source_sha256"], "source_label": contract["source_label"]})
    return {
        "id": market,
        "market": market,
        "kind": kind,
        "normalization_base": "100",
        "normalization_start_date": common_dates[0],
        "normalization_start_close": _decimal_text(start),
        "series": rows,
        "source": source,
    }


def _coverage(
    kospi: Mapping[str, Any],
    kosdaq: Mapping[str, Any],
    rl: Mapping[str, Any],
    common_dates: Sequence[str],
    *,
    min_common_dates: int,
) -> dict[str, Any]:
    contracts = {KOSPI: kospi, KOSDAQ: kosdaq, RL_MARKET: rl}
    dropped_dates = {
        market: sorted(set(contract["by_date"]) - set(common_dates))
        for market, contract in contracts.items()
    }
    return {
        "intersection_policy": "exact_three_way_trading_date_intersection_only_no_fill_interpolation_or_nearest_date",
        "min_common_dates": min_common_dates,
        "common_date_count": len(common_dates),
        "common_dates": list(common_dates),
        "common_start_date": common_dates[0],
        "common_end_date": common_dates[-1],
        "input_counts": {market: int(contract["series_count"]) for market, contract in contracts.items()},
        "dropped_date_count": {market: len(dates) for market, dates in dropped_dates.items()},
        "dropped_dates": dropped_dates,
        "filled_dates": [],
        "interpolated_dates": [],
        "nearest_date_matches": [],
    }


def _index_source_ref(contract: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "market": contract["market"],
        "index_code": contract.get("index_code"),
        "index_name": contract.get("index_name"),
        "requested_start_date": contract.get("requested_start_date"),
        "requested_end_date": contract.get("requested_end_date"),
        "actual_start_date": contract.get("actual_start_date"),
        "actual_end_date": contract.get("actual_end_date"),
        "series_count": contract["series_count"],
        "raw_sha256": contract["hashes"]["raw_sha256"],
        "normalized_sha256": contract["hashes"]["normalized_sha256"],
        "artifact_sha256": contract["hashes"]["artifact_sha256"],
        "source_metadata": contract["source_metadata"],
    }
    for key in (
        "provider_package",
        "package",
        "parser",
        "license_review",
        "point_in_time",
        "source_lineage",
        "artifact_filename",
        "source_artifact_filename",
    ):
        if contract.get(key) is not None:
            payload[key] = contract[key]
    if contract.get("artifact_path") is not None:
        payload["artifact_path"] = contract["artifact_path"]
    if contract.get("artifact_file_sha256") is not None:
        payload["artifact_file_sha256"] = contract["artifact_file_sha256"]
    return payload


def _blocked_payload(errors: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "BLOCKED",
        "reason_codes": _unique_reason_codes(errors),
        "read_only": True,
        "network_used": False,
        "price_basis": PRICE_BASIS,
        "causal_cutoff_kst": CAUSAL_CUTOFF_KST,
        "official_close": False,
        "source_policy": _source_policy(),
        "point_in_time_constituents": False,
        "point_in_time_limitation": "No point-in-time constituent membership is claimed while blocked.",
        "false_locks": dict(_FALSE_LOCKS),
        "claims": dict(_CLAIMS),
        "coverage": {
            "intersection_policy": "exact_three_way_trading_date_intersection_only_no_fill_interpolation_or_nearest_date",
            "common_date_count": 0,
            "common_dates": [],
            "input_counts": {},
            "dropped_date_count": {},
            "dropped_dates": {},
            "filled_dates": [],
            "interpolated_dates": [],
            "nearest_date_matches": [],
        },
        "audit": {"error_count": len(errors), "errors": [dict(error) for error in errors]},
        "hash_algorithm": "SHA256_CANONICAL_JSON_SORT_KEYS_NO_SELF_FIELD",
    }
    return _attach_overlay_hash(payload)


def _source_policy() -> dict[str, Any]:
    return {
        "index_provider": "pykrx",
        "index_validator": "stom_rl.korean_index_source.validate_korean_index_artifact",
        "offline_artifacts_only": True,
        "naver_disabled": True,
        "no_live_fetch": True,
        "no_network": True,
        "no_fallback": True,
        "no_interpolation": True,
        "no_nearest_date": True,
        "official_close": False,
        "point_in_time_constituents": False,
    }


def _attach_overlay_hash(payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    body.pop("overlay_sha256", None)
    payload["overlay_sha256"] = sha256_hex(body)
    return payload


def _append_error(errors: list[dict[str, str]], reason_code: str, message: str) -> None:
    errors.append({"reason_code": reason_code, "message": message})


def _unique_reason_codes(errors: Sequence[Mapping[str, str]]) -> list[str]:
    return list(dict.fromkeys(str(error.get("reason_code")) for error in errors if error.get("reason_code")))


def _classify_validation_exception(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return INDEX_ARTIFACT_MISSING
    text = str(exc).lower()
    if "hash" in text or "sha" in text or "tamper" in text or "digest" in text:
        return INDEX_ARTIFACT_HASH_MISMATCH
    if "market" in text and ("mismatch" in text or "expected" in text):
        return INDEX_ARTIFACT_MARKET_MISMATCH
    if ("duplicate" in text and "date" in text) or ("strictly ascending" in text and "date" in text) or ("unique" in text and "date" in text):
        return INDEX_ARTIFACT_DUPLICATE_DATES
    if "positive" in text or "nonpositive" in text or "finite" in text:
        return NONPOSITIVE_SERIES_VALUE
    if "naver" in text or "fallback" in text or "live fetch" in text or "provider" in text:
        return INDEX_ARTIFACT_FORBIDDEN_SOURCE
    if "point-in-time" in text or "point in time" in text or "point_in_time" in text:
        return POINT_IN_TIME_CONSTITUENT_CLAIM
    return INDEX_ARTIFACT_INVALID


def _required_text(value: Any, label: str, reason: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _ReasonError(reason, f"{label} must be a non-empty string")
    return value


def _required_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise _ReasonError(INDEX_ARTIFACT_INVALID, f"{label} is missing")
    if _HASH_RE.fullmatch(value) is None:
        raise _ReasonError(INDEX_ARTIFACT_HASH_MISMATCH, f"{label} must be a lowercase SHA-256 hex digest")
    return value


def _session_date(value: Any, label: str, reason: str) -> str:
    if not isinstance(value, str) or _DATE_RE.fullmatch(value) is None:
        raise _ReasonError(reason, f"{label} must be YYYY-MM-DD")
    try:
        parsed = Date.fromisoformat(value)
    except ValueError as exc:
        raise _ReasonError(reason, f"{label} is not a valid calendar date") from exc
    return parsed.isoformat()


def _positive_decimal(value: Any, label: str, invalid_reason: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise _ReasonError(invalid_reason, f"{label} is missing")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise _ReasonError(invalid_reason, f"{label} must be a finite positive decimal") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise _ReasonError(NONPOSITIVE_SERIES_VALUE, f"{label} must be finite and positive")
    return parsed


def _first_present(row: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _normalized_text(value: Decimal, start: Decimal) -> str:
    normalized = (value * NORMALIZATION_BASE / start).quantize(NORMALIZED_QUANT, rounding=ROUND_HALF_UP)
    if normalized.is_zero():
        normalized = normalized.copy_abs()
    return format(normalized, "f")


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _require_exact_false_map(value: Any, expected: Mapping[str, bool], label: str, reason: str) -> dict[str, bool]:
    if not isinstance(value, Mapping) or not value:
        raise _ReasonError(reason, f"{label} must be a non-empty mapping of false booleans")
    observed = {str(key): item for key, item in value.items()}
    if set(observed) != set(expected):
        raise _ReasonError(reason, f"{label} keys must exactly match the canonical custody set")
    if any(item is not False for item in observed.values()):
        raise _ReasonError(reason, f"{label} values must all be false")
    if observed != dict(expected):
        raise _ReasonError(reason, f"{label} must exactly match the canonical custody set")
    return dict(expected)


def _has_forbidden_rl_source(*mappings: Mapping[str, Any]) -> bool:
    for mapping in mappings:
        if not isinstance(mapping, Mapping):
            continue
        for key in _RL_SOURCE_IDENTIFIER_KEYS:
            value = mapping.get(key)
            if value is None:
                continue
            text = str(value).replace("\\", "/").lower()
            if any(token in text for token in _FORBIDDEN_RL_SOURCE_TOKENS):
                return True
    return False


def _optional_file_sha256(source: Any) -> str | None:
    try:
        path = Path(source)
    except TypeError:
        return None
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, Path):
        return str(value)
    return value


__all__ = [
    "CAUSAL_CUTOFF_KST",
    "KOSDAQ",
    "KOSPI",
    "KoreanIndexOverlayError",
    "MIN_COMMON_DATES",
    "NORMALIZED_ARITHMETIC",
    "PRICE_BASIS",
    "RL_MARKET",
    "SCHEMA_VERSION",
    "build_korean_index_overlay",
    "build_korean_index_overlay_result",
    "canonical_bytes",
    "sha256_hex",
    "validate_korean_index_overlay",
    "validate_korean_index_artifact",
]
