"""Immutable pykrx-only offline KOSPI/KOSDAQ index artifact custody.

This module intentionally has no pykrx import and no network access.  Runtime and
Dashboard code may import the validation helpers safely; collection is performed
only by the explicit collector CLI in ``scripts/collect_korean_index_artifact.py``.
"""
from __future__ import annotations

import json
import hashlib
import math
import os
import re
import secrets
from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

RAW_SCHEMA_VERSION = "kronos_korean_index_raw.v1"
NORMALIZED_SCHEMA_VERSION = "kronos_korean_index_normalized.v1"
PROTOCOL_VERSION = "kronos_korean_index_levels_protocol.v1"
PARSER_VERSION = "kronos_korean_index_parser.v1"
COLLECTOR_VERSION = "kronos_korean_index_collector.v1"
PYKRX_PACKAGE_NAME = "pykrx"
PYKRX_PACKAGE_VERSION = "1.2.8"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_COMPACT_DATE_RE = re.compile(r"^\d{8}$")
_UTC_SECONDS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

FALSE_RESEARCH_LOCKS: dict[str, bool] = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}

NO_CLAIM_FLAGS: dict[str, bool] = {
    "official_close_claim": False,
    "point_in_time_constituent_claim": False,
    "naver_source_claim": False,
    "fallback_claim": False,
    "interpolation_claim": False,
    "unsupported_redistribution_claim": False,
    "paper_forward_claim": False,
    "live_broker_order_claim": False,
    "profitability_claim": False,
}
OVERLAY_FALSE_LOCKS: dict[str, bool] = {
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

OVERLAY_CLAIMS: dict[str, bool] = {
    "official_close": False,
    "point_in_time_constituents": False,
    "live_trading": False,
    "profit": False,
    "paper_trading": False,
    "broker_integration": False,
}

_LICENSE_REVIEW_STATUS = "not_reviewed_for_redistribution"
_LICENSE_REVIEW_NOTES = (
    "Local research custody of pykrx-derived KRX index levels only; no "
    "redistribution-rights or unsupported licensing claim is made."
)
_POINT_IN_TIME_LIMITATION = "index_levels_only_not_constituents"
_PROVIDER_METHOD = "pykrx.stock.get_index_ohlcv_by_date"
_COLLECTION_MODE = "explicit_cli_only_optional_offline_artifact"
_NORMALIZATION_METHOD = "extract_close_levels_without_interpolation_fill_or_fallback"

RAW_ARTIFACT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "protocol_version",
    "artifact_kind",
    "parser_version",
    "collector_version",
    "market",
    "index_code",
    "index_name",
    "requested_start_date",
    "requested_end_date",
    "actual_start_date",
    "actual_end_date",
    "trading_dates",
    "row_count",
    "collected_at",
    "provider_package",
    "source_metadata",
    "source_lineage",
    "false_research_locks",
    "six_locks_false",
    "no_claim_flags",
    "raw_rows",
    "raw_sha256",
    "artifact_sha256",
)

NORMALIZED_ARTIFACT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "protocol_version",
    "artifact_kind",
    "parser_version",
    "collector_version",
    "market",
    "index_code",
    "index_name",
    "requested_start_date",
    "requested_end_date",
    "actual_start_date",
    "actual_end_date",
    "trading_dates",
    "row_count",
    "collected_at",
    "provider_package",
    "source_metadata",
    "source_lineage",
    "false_research_locks",
    "six_locks_false",
    "no_claim_flags",
    "series",
    "raw_sha256",
    "normalized_sha256",
    "artifact_sha256",
)

_SOURCE_METADATA_FIELDS: tuple[str, ...] = (
    "provider",
    "provider_method",
    "source_package",
    "collection_mode",
    "collection_requires_explicit_cli",
    "runtime_read_only",
    "naver_disabled",
    "naver_source_used",
    "no_live_fetch",
    "no_fallback",
    "fallback_enabled",
    "fallback_sources",
    "no_interpolation",
    "no_fill",
    "official_close",
    "point_in_time_limitation",
    "point_in_time_constituents",
    "index_levels_only",
    "license_review",
    "source_lineage",
)

_LICENSE_REVIEW_FIELDS: tuple[str, ...] = (
    "status",
    "review_date",
    "notes",
    "unsupported_redistribution_claim",
)
_SOURCE_METADATA_LINEAGE_FIELDS: tuple[str, ...] = (
    "market",
    "index_code",
    "index_name",
    "requested_start_date",
    "requested_end_date",
    "actual_start_date",
    "actual_end_date",
    "lineage",
)
_RAW_SOURCE_LINEAGE_FIELDS: tuple[str, ...] = (
    "provider",
    "provider_method",
    "provider_index_code",
    "provider_index_name",
    "requested_start_date",
    "requested_end_date",
    "actual_start_date",
    "actual_end_date",
    "raw_row_count",
    "date_source",
    "close_column_candidates",
    "naver_disabled",
    "fallback_used",
    "interpolation_used",
    "fill_used",
)
_NORMALIZED_SOURCE_LINEAGE_FIELDS: tuple[str, ...] = (
    "normalization_method",
    "source_schema_version",
    "source_market",
    "source_index_code",
    "source_index_name",
    "source_raw_sha256",
    "source_artifact_sha256",
    "source_artifact_filename",
    "source_row_count",
    "source_trading_dates_sha256",
    "naver_disabled",
    "fallback_used",
    "interpolation_used",
    "fill_used",
)

_PROVIDER_PACKAGE_FIELDS: tuple[str, ...] = ("name", "version", "required_version")
_RAW_ROW_FIELDS: tuple[str, ...] = ("date", "close", "source_row")
_SERIES_ROW_FIELDS: tuple[str, ...] = ("date", "close")


@dataclass(frozen=True)
class KoreanIndexSpec:
    market: str
    index_code: str
    index_name: str


SUPPORTED_INDEXES: dict[str, KoreanIndexSpec] = {
    "KOSPI": KoreanIndexSpec(market="KOSPI", index_code="1001", index_name="KOSPI"),
    "KOSDAQ": KoreanIndexSpec(market="KOSDAQ", index_code="2001", index_name="KOSDAQ"),
}

Provider = Callable[..., Any]


class KoreanIndexArtifactError(ValueError):
    """Raised when an index artifact violates the immutable custody contract."""


def supported_markets() -> tuple[str, ...]:
    """Return the exact market identifiers accepted by this boundary."""

    return tuple(SUPPORTED_INDEXES)


def collect_index_artifacts(
    *,
    market: str,
    start_date: str | int | Date,
    end_date: str | int | Date,
    provider: Provider,
    provider_package_version: str = PYKRX_PACKAGE_VERSION,
    collected_at: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Collect raw provider rows through an explicit provider and build artifacts.

    The provider is injected so tests can be fully offline.  The production CLI
    supplies the lazy pykrx provider; validation paths never call this function.
    """

    spec = _require_market_spec(market)
    requested_start = _coerce_date(start_date, "start_date")
    requested_end = _coerce_date(end_date, "end_date")
    _require_ordered_range(requested_start, requested_end)
    if provider_package_version != PYKRX_PACKAGE_VERSION:
        raise KoreanIndexArtifactError(
            f"pykrx package version must be exactly {PYKRX_PACKAGE_VERSION}, got {provider_package_version!r}"
        )
    rows = provider(
        market=spec.market,
        index_code=spec.index_code,
        index_name=spec.index_name,
        start_date=requested_start,
        end_date=requested_end,
    )
    raw = build_raw_index_artifact(
        market=spec.market,
        start_date=requested_start,
        end_date=requested_end,
        raw_rows=rows,
        provider_package_version=provider_package_version,
        collected_at=collected_at,
    )
    normalized = build_normalized_index_artifact(raw)
    return {"raw": raw, "normalized": normalized}


def collect_and_write_index_artifacts(
    *,
    market: str,
    start_date: str | int | Date,
    end_date: str | int | Date,
    output_dir: str | Path,
    provider: Provider,
    provider_package_version: str = PYKRX_PACKAGE_VERSION,
    collected_at: str | None = None,
) -> dict[str, Any]:
    """Collect, validate, and write content-addressed raw/normalized artifacts."""

    artifacts = collect_index_artifacts(
        market=market,
        start_date=start_date,
        end_date=end_date,
        provider=provider,
        provider_package_version=provider_package_version,
        collected_at=collected_at,
    )
    raw_artifact = artifacts["raw"]
    normalized_artifact = artifacts["normalized"]
    raw_path = write_raw_index_artifact(output_dir, raw_artifact)
    normalized_path = write_normalized_index_artifact(output_dir, normalized_artifact)
    return {
        "schema_version": "kronos_korean_index_collection_receipt.v1",
        "market": normalized_artifact["market"],
        "index_code": normalized_artifact["index_code"],
        "index_name": normalized_artifact["index_name"],
        "requested_start_date": normalized_artifact["requested_start_date"],
        "requested_end_date": normalized_artifact["requested_end_date"],
        "actual_start_date": normalized_artifact["actual_start_date"],
        "actual_end_date": normalized_artifact["actual_end_date"],
        "row_count": normalized_artifact["row_count"],
        "raw_path": str(raw_path),
        "normalized_path": str(normalized_path),
        "raw_sha256": normalized_artifact["raw_sha256"],
        "normalized_sha256": normalized_artifact["normalized_sha256"],
        "raw_artifact_sha256": raw_artifact["artifact_sha256"],
        "normalized_artifact_sha256": normalized_artifact["artifact_sha256"],
        "naver_disabled": True,
        "no_fallback": True,
        "no_interpolation": True,
    }


def build_raw_index_artifact(
    *,
    market: str,
    start_date: str | int | Date,
    end_date: str | int | Date,
    raw_rows: Any,
    provider_package_version: str = PYKRX_PACKAGE_VERSION,
    collected_at: str | None = None,
) -> dict[str, Any]:
    """Build an immutable raw pykrx index artifact from provider output."""

    spec = _require_market_spec(market)
    requested_start = _coerce_date(start_date, "start_date")
    requested_end = _coerce_date(end_date, "end_date")
    _require_ordered_range(requested_start, requested_end)
    timestamp = _coerce_utc_seconds(collected_at or _utc_now_seconds(), "collected_at")
    if provider_package_version != PYKRX_PACKAGE_VERSION:
        raise KoreanIndexArtifactError(
            f"pykrx package version must be exactly {PYKRX_PACKAGE_VERSION}, got {provider_package_version!r}"
        )

    records = _provider_rows_to_raw_records(raw_rows)
    if not records:
        raise KoreanIndexArtifactError("provider returned no index level rows")
    _validate_ordered_records(records, requested_start=requested_start, requested_end=requested_end)
    trading_dates = [row["date"] for row in records]
    actual_start = trading_dates[0]
    actual_end = trading_dates[-1]
    source_lineage = _raw_source_lineage(spec, requested_start, requested_end, actual_start, actual_end, len(records))
    metadata = _source_metadata(
        spec=spec,
        requested_start=requested_start,
        requested_end=requested_end,
        actual_start=actual_start,
        actual_end=actual_end,
        collected_at=timestamp,
        source_lineage=source_lineage,
    )
    package = _provider_package(provider_package_version)
    artifact: dict[str, Any] = {
        "schema_version": RAW_SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "artifact_kind": "raw_pykrx_index_levels",
        "parser_version": PARSER_VERSION,
        "collector_version": COLLECTOR_VERSION,
        "market": spec.market,
        "index_code": spec.index_code,
        "index_name": spec.index_name,
        "requested_start_date": requested_start,
        "requested_end_date": requested_end,
        "actual_start_date": actual_start,
        "actual_end_date": actual_end,
        "trading_dates": trading_dates,
        "row_count": len(records),
        "collected_at": timestamp,
        "provider_package": package,
        "source_metadata": metadata,
        "source_lineage": source_lineage,
        "false_research_locks": dict(FALSE_RESEARCH_LOCKS),
        "six_locks_false": dict(FALSE_RESEARCH_LOCKS),
        "no_claim_flags": dict(NO_CLAIM_FLAGS),
        "raw_rows": records,
    }
    artifact["raw_sha256"] = _sha256_json(_raw_hash_basis(artifact))
    artifact["artifact_sha256"] = _sha256_json(_raw_artifact_hash_basis(artifact))
    validate_raw_index_artifact(artifact)
    return artifact


def build_normalized_index_artifact(raw_artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Build the dashboard/runtime normalized close-series artifact."""

    raw_summary = validate_raw_index_artifact(raw_artifact)
    spec = _require_market_spec(str(raw_artifact["market"]))
    series = [
        {"date": str(row["date"]), "close": _coerce_positive_float(row["close"], "raw row close")}
        for row in raw_artifact["raw_rows"]
    ]
    source_lineage = {
        "normalization_method": _NORMALIZATION_METHOD,
        "source_schema_version": RAW_SCHEMA_VERSION,
        "source_market": spec.market,
        "source_index_code": spec.index_code,
        "source_index_name": spec.index_name,
        "source_raw_sha256": raw_artifact["raw_sha256"],
        "source_artifact_sha256": raw_artifact["artifact_sha256"],
        "source_artifact_filename": raw_index_artifact_filename(raw_artifact),
        "source_row_count": raw_artifact["row_count"],
        "source_trading_dates_sha256": _sha256_json(raw_artifact["trading_dates"]),
        "naver_disabled": True,
        "fallback_used": False,
        "interpolation_used": False,
        "fill_used": False,
    }
    metadata = _source_metadata(
        spec=spec,
        requested_start=str(raw_artifact["requested_start_date"]),
        requested_end=str(raw_artifact["requested_end_date"]),
        actual_start=str(raw_artifact["actual_start_date"]),
        actual_end=str(raw_artifact["actual_end_date"]),
        collected_at=str(raw_artifact["collected_at"]),
        source_lineage=source_lineage,
    )
    artifact: dict[str, Any] = {
        "schema_version": NORMALIZED_SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "artifact_kind": "normalized_korean_index_levels",
        "parser_version": PARSER_VERSION,
        "collector_version": COLLECTOR_VERSION,
        "market": spec.market,
        "index_code": spec.index_code,
        "index_name": spec.index_name,
        "requested_start_date": raw_artifact["requested_start_date"],
        "requested_end_date": raw_artifact["requested_end_date"],
        "actual_start_date": raw_artifact["actual_start_date"],
        "actual_end_date": raw_artifact["actual_end_date"],
        "trading_dates": list(raw_artifact["trading_dates"]),
        "row_count": raw_artifact["row_count"],
        "collected_at": raw_artifact["collected_at"],
        "provider_package": dict(raw_artifact["provider_package"]),
        "source_metadata": metadata,
        "source_lineage": source_lineage,
        "false_research_locks": dict(FALSE_RESEARCH_LOCKS),
        "six_locks_false": dict(FALSE_RESEARCH_LOCKS),
        "no_claim_flags": dict(NO_CLAIM_FLAGS),
        "series": series,
        "raw_sha256": raw_summary["raw_sha256"],
    }
    artifact["normalized_sha256"] = _sha256_json(_normalized_hash_basis(artifact))
    artifact["artifact_sha256"] = _sha256_json(_normalized_artifact_hash_basis(artifact))
    validate_normalized_index_artifact(artifact, raw_artifact=raw_artifact)
    return artifact


def validate_raw_index_artifact(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a raw artifact without importing pykrx or touching the network."""

    if not isinstance(artifact, Mapping):
        raise KoreanIndexArtifactError("raw artifact must be a JSON object")
    _require_exact_fields(artifact, RAW_ARTIFACT_FIELDS, "raw artifact")
    _require_literal(artifact["schema_version"], RAW_SCHEMA_VERSION, "schema_version")
    _require_literal(artifact["protocol_version"], PROTOCOL_VERSION, "protocol_version")
    _require_literal(artifact["artifact_kind"], "raw_pykrx_index_levels", "artifact_kind")
    _require_literal(artifact["parser_version"], PARSER_VERSION, "parser_version")
    _require_literal(artifact["collector_version"], COLLECTOR_VERSION, "collector_version")
    spec = _require_index_identity(artifact)
    requested_start, requested_end, actual_start, actual_end = _validate_coverage_fields(artifact)
    package = _validate_provider_package(artifact["provider_package"], "provider_package")
    _validate_policy_lineage(
        artifact["source_lineage"],
        spec=spec,
        requested_start=requested_start,
        requested_end=requested_end,
        actual_start=actual_start,
        actual_end=actual_end,
    )
    metadata = _validate_source_metadata(
        artifact["source_metadata"],
        spec=spec,
        requested_start=requested_start,
        requested_end=requested_end,
        actual_start=actual_start,
        actual_end=actual_end,
        collected_at=str(artifact["collected_at"]),
        package=package,
        source_lineage=artifact["source_lineage"],
    )
    _validate_false_locks(artifact["false_research_locks"], "false_research_locks")
    _validate_false_locks(artifact["six_locks_false"], "six_locks_false")
    _validate_no_claims(artifact["no_claim_flags"])

    rows = artifact["raw_rows"]
    if not isinstance(rows, list) or not rows:
        raise KoreanIndexArtifactError("raw_rows must be a non-empty array")
    trading_dates = _validate_row_collection(
        rows,
        row_fields=_RAW_ROW_FIELDS,
        requested_start=requested_start,
        requested_end=requested_end,
        expect_source_row=True,
    )
    _validate_trading_dates(artifact, trading_dates=trading_dates, actual_start=actual_start, actual_end=actual_end)
    _require_sha(artifact["raw_sha256"], "raw_sha256")
    _require_sha(artifact["artifact_sha256"], "artifact_sha256")
    if artifact["raw_sha256"] != _sha256_json(_raw_hash_basis(artifact)):
        raise KoreanIndexArtifactError("raw_sha256 mismatch")
    if artifact["artifact_sha256"] != _sha256_json(_raw_artifact_hash_basis(artifact)):
        raise KoreanIndexArtifactError("raw artifact_sha256 mismatch")
    return {
        "schema_version": artifact["schema_version"],
        "market": spec.market,
        "index_code": spec.index_code,
        "index_name": spec.index_name,
        "requested_start_date": requested_start,
        "requested_end_date": requested_end,
        "actual_start_date": actual_start,
        "actual_end_date": actual_end,
        "trading_dates": trading_dates,
        "row_count": len(rows),
        "series": [{"date": row["date"], "close": row["close"]} for row in rows],
        "raw_sha256": artifact["raw_sha256"],
        "artifact_sha256": artifact["artifact_sha256"],
        "source_metadata": metadata,
    }


def validate_normalized_index_artifact(
    artifact: Mapping[str, Any],
    *,
    raw_artifact: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a normalized artifact and return the overlay-safe payload."""

    if not isinstance(artifact, Mapping):
        raise KoreanIndexArtifactError("normalized artifact must be a JSON object")
    _require_exact_fields(artifact, NORMALIZED_ARTIFACT_FIELDS, "normalized artifact")
    _require_literal(artifact["schema_version"], NORMALIZED_SCHEMA_VERSION, "schema_version")
    _require_literal(artifact["protocol_version"], PROTOCOL_VERSION, "protocol_version")
    _require_literal(artifact["artifact_kind"], "normalized_korean_index_levels", "artifact_kind")
    _require_literal(artifact["parser_version"], PARSER_VERSION, "parser_version")
    _require_literal(artifact["collector_version"], COLLECTOR_VERSION, "collector_version")
    spec = _require_index_identity(artifact)
    requested_start, requested_end, actual_start, actual_end = _validate_coverage_fields(artifact)
    package = _validate_provider_package(artifact["provider_package"], "provider_package")
    _validate_normalized_lineage(artifact["source_lineage"], spec=spec)
    metadata = _validate_source_metadata(
        artifact["source_metadata"],
        spec=spec,
        requested_start=requested_start,
        requested_end=requested_end,
        actual_start=actual_start,
        actual_end=actual_end,
        collected_at=str(artifact["collected_at"]),
        package=package,
        source_lineage=artifact["source_lineage"],
    )
    _validate_false_locks(artifact["false_research_locks"], "false_research_locks")
    _validate_false_locks(artifact["six_locks_false"], "six_locks_false")
    _validate_no_claims(artifact["no_claim_flags"])

    rows = artifact["series"]
    if not isinstance(rows, list) or not rows:
        raise KoreanIndexArtifactError("series must be a non-empty array")
    trading_dates = _validate_row_collection(
        rows,
        row_fields=_SERIES_ROW_FIELDS,
        requested_start=requested_start,
        requested_end=requested_end,
        expect_source_row=False,
    )
    _validate_trading_dates(artifact, trading_dates=trading_dates, actual_start=actual_start, actual_end=actual_end)
    if artifact["source_lineage"]["source_row_count"] != len(rows):
        raise KoreanIndexArtifactError("normalized source_row_count must equal row count")
    if artifact["source_lineage"]["source_trading_dates_sha256"] != _sha256_json(trading_dates):
        raise KoreanIndexArtifactError("normalized source trading-date hash mismatch")
    expected_source_filename = (
        f"korean-index-{spec.market.lower()}-raw-{artifact['source_lineage']['source_artifact_sha256']}.json"
    )
    if artifact["source_lineage"]["source_artifact_filename"] != expected_source_filename:
        raise KoreanIndexArtifactError("normalized source artifact filename mismatch")
    _require_sha(artifact["raw_sha256"], "raw_sha256")
    _require_sha(artifact["normalized_sha256"], "normalized_sha256")
    _require_sha(artifact["artifact_sha256"], "artifact_sha256")
    if artifact["normalized_sha256"] != _sha256_json(_normalized_hash_basis(artifact)):
        raise KoreanIndexArtifactError("normalized_sha256 mismatch")
    if artifact["artifact_sha256"] != _sha256_json(_normalized_artifact_hash_basis(artifact)):
        raise KoreanIndexArtifactError("normalized artifact_sha256 mismatch")
    if artifact["source_lineage"]["source_raw_sha256"] != artifact["raw_sha256"]:
        raise KoreanIndexArtifactError("normalized lineage raw hash mismatch")
    if raw_artifact is not None:
        raw_summary = validate_raw_index_artifact(raw_artifact)
        if artifact["raw_sha256"] != raw_summary["raw_sha256"]:
            raise KoreanIndexArtifactError("normalized raw_sha256 does not match raw artifact")
        if artifact["source_lineage"]["source_artifact_sha256"] != raw_summary["artifact_sha256"]:
            raise KoreanIndexArtifactError("normalized source artifact hash mismatch")
        if artifact["series"] != raw_summary["series"]:
            raise KoreanIndexArtifactError("normalized series does not exactly match raw closes")
    return {
        "schema_version": artifact["schema_version"],
        "market": spec.market,
        "index_code": spec.index_code,
        "index_name": spec.index_name,
        "requested_start_date": requested_start,
        "requested_end_date": requested_end,
        "actual_start_date": actual_start,
        "actual_end_date": actual_end,
        "trading_dates": trading_dates,
        "row_count": len(rows),
        "series": [{"date": row["date"], "close": row["close"]} for row in rows],
        "raw_sha256": artifact["raw_sha256"],
        "normalized_sha256": artifact["normalized_sha256"],
        "artifact_sha256": artifact["artifact_sha256"],
        "source_metadata": metadata,
    }


def validate_korean_index_artifact(
    path_or_mapping: str | Path | Mapping[str, Any],
    expected_market: str | None = None,
) -> dict[str, Any]:
    """Validate an offline normalized artifact path or mapping for overlay use.

    Paths are loaded only through the canonical content-addressed normalized
    artifact loader.  Mappings are validated against the full normalized
    schema, lineage, policy, and hash contract before any overlay-compatible
    view is returned.
    """

    if isinstance(path_or_mapping, Mapping):
        artifact = path_or_mapping
    else:
        try:
            path = Path(path_or_mapping)
        except TypeError as exc:
            raise KoreanIndexArtifactError("artifact source must be a mapping or filesystem path") from exc
        artifact = load_normalized_index_artifact(path)

    summary = validate_normalized_index_artifact(artifact)
    if expected_market is not None:
        if not isinstance(expected_market, str):
            raise KoreanIndexArtifactError("expected_market must be a string")
        expected_spec = _require_market_spec(expected_market)
        if expected_market != expected_spec.market:
            raise KoreanIndexArtifactError("expected_market must be canonical uppercase KOSPI or KOSDAQ")
        if summary["market"] != expected_spec.market:
            raise KoreanIndexArtifactError(f"market mismatch: expected {expected_spec.market}, got {summary['market']}")
    return _overlay_safe_index_view(artifact, summary)



def raw_index_artifact_filename(artifact: Mapping[str, Any]) -> str:
    """Return the content-addressed raw artifact filename."""

    spec = _require_index_identity(artifact)
    digest = _require_sha(artifact.get("artifact_sha256"), "artifact_sha256")
    return f"korean-index-{spec.market.lower()}-raw-{digest}.json"


def normalized_index_artifact_filename(artifact: Mapping[str, Any]) -> str:
    """Return the content-addressed normalized artifact filename."""

    spec = _require_index_identity(artifact)
    digest = _require_sha(artifact.get("artifact_sha256"), "artifact_sha256")
    return f"korean-index-{spec.market.lower()}-normalized-{digest}.json"


def write_raw_index_artifact(output_dir: str | Path, artifact: Mapping[str, Any]) -> Path:
    """Write a raw artifact with atomic no-overwrite semantics."""

    validate_raw_index_artifact(artifact)
    path = Path(output_dir) / raw_index_artifact_filename(artifact)
    _write_immutable_json(path, artifact)
    return path


def write_normalized_index_artifact(output_dir: str | Path, artifact: Mapping[str, Any]) -> Path:
    """Write a normalized artifact with atomic no-overwrite semantics."""

    validate_normalized_index_artifact(artifact)
    path = Path(output_dir) / normalized_index_artifact_filename(artifact)
    _write_immutable_json(path, artifact)
    return path


def load_raw_index_artifact(path: str | Path) -> dict[str, Any]:
    """Load and validate a canonical raw artifact file."""

    artifact = _read_canonical_json(Path(path))
    validate_raw_index_artifact(artifact)
    _require_content_addressed_name(Path(path), raw_index_artifact_filename(artifact))
    return artifact


def load_normalized_index_artifact(path: str | Path) -> dict[str, Any]:
    """Load and validate a canonical normalized artifact file."""

    artifact = _read_canonical_json(Path(path))
    validate_normalized_index_artifact(artifact)
    _require_content_addressed_name(Path(path), normalized_index_artifact_filename(artifact))
    return artifact


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical JSON bytes used for all artifact hashes and files."""

    return _canonical_bytes(value)


def sha256_json(value: Any) -> str:
    """Return SHA-256 over canonical JSON bytes."""

    return _sha256_json(value)


def _overlay_safe_index_view(artifact: Mapping[str, Any], summary: Mapping[str, Any]) -> dict[str, Any]:
    provider_package = dict(_jsonable(artifact["provider_package"]))
    metadata = _jsonable(summary["source_metadata"])
    source_lineage = _jsonable(artifact["source_lineage"])
    hashes = {
        "raw_sha256": summary["raw_sha256"],
        "normalized_sha256": summary["normalized_sha256"],
        "artifact_sha256": summary["artifact_sha256"],
    }
    return {
        "schema_version": summary["schema_version"],
        "protocol_version": artifact["protocol_version"],
        "artifact_kind": artifact["artifact_kind"],
        "artifact_filename": normalized_index_artifact_filename(artifact),
        "source_artifact_filename": source_lineage["source_artifact_filename"],
        "parser_version": artifact["parser_version"],
        "collector_version": artifact["collector_version"],
        "market": summary["market"],
        "index_code": summary["index_code"],
        "index_name": summary["index_name"],
        "requested_start_date": summary["requested_start_date"],
        "requested_end_date": summary["requested_end_date"],
        "actual_start_date": summary["actual_start_date"],
        "actual_end_date": summary["actual_end_date"],
        "trading_dates": list(summary["trading_dates"]),
        "row_count": summary["row_count"],
        "series": [{"date": row["date"], "close": row["close"]} for row in summary["series"]],
        "provider_package": dict(provider_package),
        "package": dict(provider_package),
        "parser": {
            "protocol_version": artifact["protocol_version"],
            "parser_version": artifact["parser_version"],
            "collector_version": artifact["collector_version"],
            "normalization_method": source_lineage["normalization_method"],
        },
        "license_review": _jsonable(metadata["license_review"]),
        "point_in_time": {
            "constituents": metadata["point_in_time_constituents"],
            "limitation": metadata["point_in_time_limitation"],
            "index_levels_only": metadata["index_levels_only"],
        },
        "source_metadata": metadata,
        "source_lineage": source_lineage,
        "false_locks": _canonical_overlay_false_locks(artifact),
        "claims": _canonical_overlay_claims(artifact),
        "raw_sha256": summary["raw_sha256"],
        "normalized_sha256": summary["normalized_sha256"],
        "artifact_sha256": summary["artifact_sha256"],
        "hashes": hashes,
    }


def _canonical_overlay_false_locks(artifact: Mapping[str, Any]) -> dict[str, bool]:
    locks = artifact["false_research_locks"]
    claims = artifact["no_claim_flags"]
    _validate_false_locks(locks, "false_research_locks")
    _validate_no_claims(claims)
    mapped = {
        "official_close": claims["official_close_claim"],
        "full_day_daily_ohlcv": False,
        "live_trading": claims["live_broker_order_claim"],
        "profit_claim": claims["profitability_claim"],
        "paper_trading": claims["paper_forward_claim"],
        "broker_integration": claims["live_broker_order_claim"],
        "model_build_allowed": locks["model_build_allowed"],
        "promotion_allowed": locks["promotion_allowed"],
        "go_summary_allowed": locks["go_summary_allowed"],
        "live_broker_order_allowed": locks["live_broker_order_allowed"],
    }
    if mapped != OVERLAY_FALSE_LOCKS:
        raise KoreanIndexArtifactError("overlay false_locks mapping is not canonical")
    return dict(mapped)


def _canonical_overlay_claims(artifact: Mapping[str, Any]) -> dict[str, bool]:
    claims = artifact["no_claim_flags"]
    _validate_no_claims(claims)
    mapped = {
        "official_close": claims["official_close_claim"],
        "point_in_time_constituents": claims["point_in_time_constituent_claim"],
        "live_trading": claims["live_broker_order_claim"],
        "profit": claims["profitability_claim"],
        "paper_trading": claims["paper_forward_claim"],
        "broker_integration": claims["live_broker_order_claim"],
    }
    if mapped != OVERLAY_CLAIMS:
        raise KoreanIndexArtifactError("overlay claims mapping is not canonical")
    return dict(mapped)



def _require_market_spec(market: str) -> KoreanIndexSpec:
    if not isinstance(market, str):
        raise KoreanIndexArtifactError("market must be a string")
    key = market.strip().upper()
    try:
        return SUPPORTED_INDEXES[key]
    except KeyError as exc:
        raise KoreanIndexArtifactError("market must be exactly KOSPI or KOSDAQ") from exc


def _require_index_identity(artifact: Mapping[str, Any]) -> KoreanIndexSpec:
    spec = _require_market_spec(str(artifact.get("market")))
    if artifact.get("market") != spec.market:
        raise KoreanIndexArtifactError("market must be canonical uppercase KOSPI or KOSDAQ")
    if artifact.get("index_code") != spec.index_code:
        raise KoreanIndexArtifactError(f"{spec.market} index_code must be exactly {spec.index_code}")
    if artifact.get("index_name") != spec.index_name:
        raise KoreanIndexArtifactError(f"{spec.market} index_name must be exactly {spec.index_name}")
    return spec


def _provider_package(version: str) -> dict[str, str]:
    return {"name": PYKRX_PACKAGE_NAME, "version": version, "required_version": PYKRX_PACKAGE_VERSION}


def _source_metadata(
    *,
    spec: KoreanIndexSpec,
    requested_start: str,
    requested_end: str,
    actual_start: str,
    actual_end: str,
    collected_at: str,
    source_lineage: Mapping[str, Any],
) -> dict[str, Any]:
    review_date = _coerce_utc_seconds(collected_at, "collected_at")[:10]
    return {
        "provider": PYKRX_PACKAGE_NAME,
        "provider_method": _PROVIDER_METHOD,
        "source_package": _provider_package(PYKRX_PACKAGE_VERSION),
        "collection_mode": _COLLECTION_MODE,
        "collection_requires_explicit_cli": True,
        "runtime_read_only": True,
        "naver_disabled": True,
        "naver_source_used": False,
        "no_live_fetch": True,
        "no_fallback": True,
        "fallback_enabled": False,
        "fallback_sources": [],
        "no_interpolation": True,
        "no_fill": True,
        "official_close": False,
        "point_in_time_limitation": _POINT_IN_TIME_LIMITATION,
        "point_in_time_constituents": False,
        "index_levels_only": True,
        "license_review": {
            "status": _LICENSE_REVIEW_STATUS,
            "review_date": review_date,
            "notes": _LICENSE_REVIEW_NOTES,
            "unsupported_redistribution_claim": False,
        },
        "source_lineage": {
            "market": spec.market,
            "index_code": spec.index_code,
            "index_name": spec.index_name,
            "requested_start_date": requested_start,
            "requested_end_date": requested_end,
            "actual_start_date": actual_start,
            "actual_end_date": actual_end,
            "lineage": _jsonable(source_lineage),
        },
    }


def _raw_source_lineage(
    spec: KoreanIndexSpec,
    requested_start: str,
    requested_end: str,
    actual_start: str,
    actual_end: str,
    row_count: int,
) -> dict[str, Any]:
    return {
        "provider": PYKRX_PACKAGE_NAME,
        "provider_method": _PROVIDER_METHOD,
        "provider_index_code": spec.index_code,
        "provider_index_name": spec.index_name,
        "requested_start_date": requested_start,
        "requested_end_date": requested_end,
        "actual_start_date": actual_start,
        "actual_end_date": actual_end,
        "raw_row_count": row_count,
        "date_source": "provider_index_or_explicit_date_column",
        "close_column_candidates": ["종가", "close", "Close", "close_level", "index_close"],
        "naver_disabled": True,
        "fallback_used": False,
        "interpolation_used": False,
        "fill_used": False,
    }


def _provider_rows_to_raw_records(raw_rows: Any) -> list[dict[str, Any]]:
    candidates: list[tuple[Any | None, Any]] = []
    if raw_rows is None:
        raise KoreanIndexArtifactError("provider returned None")
    if isinstance(raw_rows, Mapping):
        if _row_mapping_has_date_and_close(raw_rows):
            candidates = [(None, raw_rows)]
        else:
            candidates = list(raw_rows.items())
    elif hasattr(raw_rows, "to_dict"):
        try:
            as_index = raw_rows.to_dict(orient="index")
        except TypeError:
            as_index = raw_rows.to_dict()
        if isinstance(as_index, Mapping):
            candidates = list(as_index.items())
        else:
            candidates = [(None, row) for row in as_index]
    else:
        try:
            candidates = [(None, row) for row in raw_rows]
        except TypeError as exc:
            raise KoreanIndexArtifactError("provider output must be iterable rows or a pandas-like frame") from exc

    records: list[dict[str, Any]] = []
    for index_key, row in candidates:
        row_mapping = _row_to_mapping(row)
        date_value = _extract_date(row_mapping, index_key)
        close_value = _extract_close(row_mapping)
        records.append(
            {
                "date": _coerce_date(date_value, "row date"),
                "close": _coerce_positive_float(close_value, "row close"),
                "source_row": _jsonable(row_mapping),
            }
        )
    return records


def _row_mapping_has_date_and_close(value: Mapping[Any, Any]) -> bool:
    keys = {str(key) for key in value}
    return bool(keys & {"date", "Date", "날짜", "일자", "trading_date"}) and bool(
        keys & {"close", "Close", "종가", "close_level", "index_close"}
    )


def _row_to_mapping(row: Any) -> Mapping[Any, Any]:
    if isinstance(row, Mapping):
        return row
    if hasattr(row, "_asdict"):
        return row._asdict()
    if hasattr(row, "to_dict"):
        value = row.to_dict()
        if isinstance(value, Mapping):
            return value
    raise KoreanIndexArtifactError("provider row must be a mapping")


def _extract_date(row: Mapping[Any, Any], index_key: Any | None) -> Any:
    for key in ("date", "Date", "날짜", "일자", "trading_date"):
        if key in row:
            return row[key]
    if index_key is not None:
        return index_key
    raise KoreanIndexArtifactError("provider row is missing a trading date")


def _extract_close(row: Mapping[Any, Any]) -> Any:
    for key in ("종가", "close", "Close", "close_level", "index_close"):
        if key in row:
            return row[key]
    raise KoreanIndexArtifactError("provider row is missing close/종가")


def _validate_ordered_records(records: list[dict[str, Any]], *, requested_start: str, requested_end: str) -> None:
    dates = [str(record["date"]) for record in records]
    if dates != sorted(dates):
        raise KoreanIndexArtifactError("provider trading dates must be strictly ascending; raw custody does not reorder rows")
    if len(set(dates)) != len(dates):
        raise KoreanIndexArtifactError("provider trading dates must be unique")
    for record in records:
        _require_exact_fields(record, _RAW_ROW_FIELDS, "raw row")
        date = _coerce_date(record["date"], "row date")
        if date < requested_start or date > requested_end:
            raise KoreanIndexArtifactError("provider row date lies outside requested coverage")
        _coerce_positive_float(record["close"], "row close")
        if not isinstance(record["source_row"], Mapping):
            raise KoreanIndexArtifactError("raw source_row must be an object")


def _validate_coverage_fields(artifact: Mapping[str, Any]) -> tuple[str, str, str, str]:
    requested_start = _coerce_date(artifact["requested_start_date"], "requested_start_date")
    requested_end = _coerce_date(artifact["requested_end_date"], "requested_end_date")
    actual_start = _coerce_date(artifact["actual_start_date"], "actual_start_date")
    actual_end = _coerce_date(artifact["actual_end_date"], "actual_end_date")
    if artifact["requested_start_date"] != requested_start or artifact["requested_end_date"] != requested_end:
        raise KoreanIndexArtifactError("requested coverage dates must be canonical YYYY-MM-DD")
    if artifact["actual_start_date"] != actual_start or artifact["actual_end_date"] != actual_end:
        raise KoreanIndexArtifactError("actual coverage dates must be canonical YYYY-MM-DD")
    _require_ordered_range(requested_start, requested_end)
    _require_ordered_range(actual_start, actual_end)
    if actual_start < requested_start or actual_end > requested_end:
        raise KoreanIndexArtifactError("actual coverage must be within requested coverage")
    _coerce_utc_seconds(artifact["collected_at"], "collected_at")
    return requested_start, requested_end, actual_start, actual_end


def _validate_provider_package(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise KoreanIndexArtifactError(f"{label} must be an object")
    _require_exact_fields(value, _PROVIDER_PACKAGE_FIELDS, label)
    if value["name"] != PYKRX_PACKAGE_NAME or value["version"] != PYKRX_PACKAGE_VERSION or value["required_version"] != PYKRX_PACKAGE_VERSION:
        raise KoreanIndexArtifactError(f"{label} must pin pykrx=={PYKRX_PACKAGE_VERSION}")
    return {"name": value["name"], "version": value["version"], "required_version": value["required_version"]}


def _validate_source_metadata(
    value: Any,
    *,
    spec: KoreanIndexSpec,
    requested_start: str,
    requested_end: str,
    actual_start: str,
    actual_end: str,
    collected_at: str,
    package: Mapping[str, str],
    source_lineage: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise KoreanIndexArtifactError("source_metadata must be an object")
    _require_exact_fields(value, _SOURCE_METADATA_FIELDS, "source_metadata")
    if value["provider"] != PYKRX_PACKAGE_NAME or value["provider_method"] != _PROVIDER_METHOD:
        raise KoreanIndexArtifactError("source_metadata provider must be pykrx get_index_ohlcv_by_date")
    if value["source_package"] != dict(package):
        raise KoreanIndexArtifactError("source_metadata source_package mismatch")
    expected_booleans = {
        "collection_requires_explicit_cli": True,
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
    for key, expected in expected_booleans.items():
        if value[key] is not expected:
            raise KoreanIndexArtifactError(f"source_metadata.{key} must be {expected}")
    if value["collection_mode"] != _COLLECTION_MODE:
        raise KoreanIndexArtifactError("source_metadata.collection_mode is unsupported")
    if value["fallback_sources"] != []:
        raise KoreanIndexArtifactError("fallback_sources must be empty")
    if value["point_in_time_limitation"] != _POINT_IN_TIME_LIMITATION:
        raise KoreanIndexArtifactError("point-in-time limitation must be index_levels_only_not_constituents")
    license_review = value["license_review"]
    if not isinstance(license_review, Mapping):
        raise KoreanIndexArtifactError("license_review must be an object")
    _require_exact_fields(license_review, _LICENSE_REVIEW_FIELDS, "license_review")
    if license_review["status"] != _LICENSE_REVIEW_STATUS:
        raise KoreanIndexArtifactError("license_review.status must not claim redistribution approval")
    review_date = _coerce_date(license_review["review_date"], "license_review.review_date")
    if license_review["review_date"] != review_date:
        raise KoreanIndexArtifactError("license review date must be canonical YYYY-MM-DD")
    if review_date != _coerce_utc_seconds(collected_at, "collected_at")[:10]:
        raise KoreanIndexArtifactError("license review date must match collection date")
    if license_review["notes"] != _LICENSE_REVIEW_NOTES:
        raise KoreanIndexArtifactError("license_review.notes must be canonical")
    if license_review["unsupported_redistribution_claim"] is not False:
        raise KoreanIndexArtifactError("unsupported redistribution claim must be false")
    lineage = value["source_lineage"]
    if not isinstance(lineage, Mapping):
        raise KoreanIndexArtifactError("source_metadata.source_lineage must be an object")
    _require_exact_fields(lineage, _SOURCE_METADATA_LINEAGE_FIELDS, "source_metadata.source_lineage")
    for key, expected in {
        "market": spec.market,
        "index_code": spec.index_code,
        "index_name": spec.index_name,
        "requested_start_date": requested_start,
        "requested_end_date": requested_end,
        "actual_start_date": actual_start,
        "actual_end_date": actual_end,
    }.items():
        if lineage.get(key) != expected:
            raise KoreanIndexArtifactError(f"source_metadata.source_lineage.{key} mismatch")
    embedded_lineage = lineage["lineage"]
    if not isinstance(embedded_lineage, Mapping):
        raise KoreanIndexArtifactError("source_metadata.source_lineage.lineage is required")
    if embedded_lineage != _jsonable(source_lineage):
        raise KoreanIndexArtifactError("source_metadata.source_lineage.lineage must exactly match top-level source_lineage")
    return _jsonable(value)


def _validate_policy_lineage(
    value: Any,
    *,
    spec: KoreanIndexSpec,
    requested_start: str,
    requested_end: str,
    actual_start: str,
    actual_end: str,
) -> None:
    if not isinstance(value, Mapping):
        raise KoreanIndexArtifactError("source_lineage must be an object")
    _require_exact_fields(value, _RAW_SOURCE_LINEAGE_FIELDS, "source_lineage")
    expected = {
        "provider": PYKRX_PACKAGE_NAME,
        "provider_method": _PROVIDER_METHOD,
        "provider_index_code": spec.index_code,
        "provider_index_name": spec.index_name,
        "requested_start_date": requested_start,
        "requested_end_date": requested_end,
        "actual_start_date": actual_start,
        "actual_end_date": actual_end,
        "naver_disabled": True,
        "fallback_used": False,
        "interpolation_used": False,
        "fill_used": False,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise KoreanIndexArtifactError(f"source_lineage.{key} mismatch")
    if not isinstance(value.get("raw_row_count"), int) or value["raw_row_count"] <= 0:
        raise KoreanIndexArtifactError("source_lineage.raw_row_count must be positive")
    if value.get("close_column_candidates") != ["종가", "close", "Close", "close_level", "index_close"]:
        raise KoreanIndexArtifactError("source_lineage close candidates are not canonical")


def _validate_normalized_lineage(value: Any, *, spec: KoreanIndexSpec) -> None:
    if not isinstance(value, Mapping):
        raise KoreanIndexArtifactError("source_lineage must be an object")
    _require_exact_fields(value, _NORMALIZED_SOURCE_LINEAGE_FIELDS, "source_lineage")
    required = {
        "normalization_method": _NORMALIZATION_METHOD,
        "source_schema_version": RAW_SCHEMA_VERSION,
        "source_market": spec.market,
        "source_index_code": spec.index_code,
        "source_index_name": spec.index_name,
        "naver_disabled": True,
        "fallback_used": False,
        "interpolation_used": False,
        "fill_used": False,
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise KoreanIndexArtifactError(f"normalized source_lineage.{key} mismatch")
    for key in ("source_raw_sha256", "source_artifact_sha256", "source_trading_dates_sha256"):
        _require_sha(value.get(key), f"source_lineage.{key}")
    if not isinstance(value.get("source_artifact_filename"), str) or not value["source_artifact_filename"]:
        raise KoreanIndexArtifactError("source_artifact_filename is required")
    if not isinstance(value.get("source_row_count"), int) or value["source_row_count"] <= 0:
        raise KoreanIndexArtifactError("source_row_count must be positive")


def _validate_false_locks(value: Any, label: str) -> None:
    if value != FALSE_RESEARCH_LOCKS:
        raise KoreanIndexArtifactError(f"{label} must preserve all research locks as false")


def _validate_no_claims(value: Any) -> None:
    if value != NO_CLAIM_FLAGS:
        raise KoreanIndexArtifactError("no_claim_flags must preserve every claim as false")


def _validate_row_collection(
    rows: list[Any],
    *,
    row_fields: Iterable[str],
    requested_start: str,
    requested_end: str,
    expect_source_row: bool,
) -> list[str]:
    dates: list[str] = []
    last: str | None = None
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise KoreanIndexArtifactError(f"row {index} must be an object")
        _require_exact_fields(row, tuple(row_fields), f"row {index}")
        date = _coerce_date(row["date"], f"row {index} date")
        if row["date"] != date:
            raise KoreanIndexArtifactError(f"row {index} date must be canonical YYYY-MM-DD")
        if date < requested_start or date > requested_end:
            raise KoreanIndexArtifactError(f"row {index} date is outside requested coverage")
        if last is not None and date <= last:
            raise KoreanIndexArtifactError("trading dates must be strictly ascending and unique")
        last = date
        dates.append(date)
        _coerce_positive_float(row["close"], f"row {index} close")
        if expect_source_row and not isinstance(row["source_row"], Mapping):
            raise KoreanIndexArtifactError(f"row {index} source_row must be an object")
    return dates


def _validate_trading_dates(
    artifact: Mapping[str, Any],
    *,
    trading_dates: list[str],
    actual_start: str,
    actual_end: str,
) -> None:
    if artifact["trading_dates"] != trading_dates:
        raise KoreanIndexArtifactError("trading_dates must exactly match row dates")
    if artifact["row_count"] != len(trading_dates):
        raise KoreanIndexArtifactError("row_count must equal row count")
    if artifact["actual_start_date"] != trading_dates[0] or artifact["actual_end_date"] != trading_dates[-1]:
        raise KoreanIndexArtifactError("actual coverage must match leading/trailing trading dates")
    if actual_start != trading_dates[0] or actual_end != trading_dates[-1]:
        raise KoreanIndexArtifactError("parsed actual coverage must match leading/trailing trading dates")


def _raw_hash_basis(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return _select_fields(artifact, RAW_ARTIFACT_FIELDS[:-2])


def _raw_artifact_hash_basis(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return _select_fields(artifact, RAW_ARTIFACT_FIELDS[:-1])


def _normalized_hash_basis(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return _select_fields(artifact, NORMALIZED_ARTIFACT_FIELDS[:-3])


def _normalized_artifact_hash_basis(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return _select_fields(artifact, NORMALIZED_ARTIFACT_FIELDS[:-1])


def _select_fields(artifact: Mapping[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    return {field: artifact[field] for field in fields}


def _require_exact_fields(value: Mapping[Any, Any], fields: Iterable[str], label: str) -> None:
    expected = tuple(fields)
    actual = tuple(value.keys())
    if set(actual) != set(expected):
        raise KoreanIndexArtifactError(f"{label} fields are not canonical")


def _require_literal(value: Any, expected: str, label: str) -> None:
    if value != expected:
        raise KoreanIndexArtifactError(f"{label} must be {expected}")


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise KoreanIndexArtifactError(f"{label} must be a lowercase SHA-256")
    return value


def _require_ordered_range(start: str, end: str) -> None:
    if start > end:
        raise KoreanIndexArtifactError("start_date must be on or before end_date")


def _coerce_date(value: Any, label: str) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, Date):
        return value.isoformat()
    if hasattr(value, "strftime") and not isinstance(value, str):
        try:
            return str(value.strftime("%Y-%m-%d"))
        except Exception as exc:  # pragma: no cover - defensive for pandas-like dates.
            raise KoreanIndexArtifactError(f"{label} is not a valid date") from exc
    if isinstance(value, int) and not isinstance(value, bool):
        text = f"{value:08d}"
    elif isinstance(value, str):
        text = value.strip()
    else:
        raise KoreanIndexArtifactError(f"{label} must be YYYY-MM-DD")
    if _COMPACT_DATE_RE.fullmatch(text):
        text = f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    elif len(text) >= 10 and _DATE_RE.fullmatch(text[:10]):
        text = text[:10]
    if _DATE_RE.fullmatch(text) is None:
        raise KoreanIndexArtifactError(f"{label} must be YYYY-MM-DD")
    try:
        return Date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise KoreanIndexArtifactError(f"{label} is not a valid calendar date") from exc


def _coerce_utc_seconds(value: Any, label: str) -> str:
    if not isinstance(value, str) or _UTC_SECONDS_RE.fullmatch(value) is None:
        raise KoreanIndexArtifactError(f"{label} must be UTC seconds like 2026-07-18T00:00:00Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise KoreanIndexArtifactError(f"{label} is not a valid timestamp") from exc
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc_now_seconds() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coerce_positive_float(value: Any, label: str) -> float:
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, bool) or value is None:
        raise KoreanIndexArtifactError(f"{label} must be a positive finite number")
    if isinstance(value, str):
        try:
            number = float(value.replace(",", ""))
        except ValueError as exc:
            raise KoreanIndexArtifactError(f"{label} must be a positive finite number") from exc
    elif isinstance(value, (int, float)):
        number = float(value)
    else:
        raise KoreanIndexArtifactError(f"{label} must be a positive finite number")
    if not math.isfinite(number) or number <= 0:
        raise KoreanIndexArtifactError(f"{label} must be a positive finite number")
    return number


def _jsonable(value: Any) -> Any:
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(inner) for inner in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Date):
        return value.isoformat()
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise KoreanIndexArtifactError("non-finite raw provider value is forbidden")
        return value
    return str(value)


def _canonical_bytes(value: Any) -> bytes:
    try:
        import rfc8785  # type: ignore

        return rfc8785.dumps(value)
    except ImportError:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except Exception as exc:
        raise KoreanIndexArtifactError("value is not canonical JSON serializable") from exc


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _write_immutable_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical_bytes(value) + b"\n"
    if path.exists():
        raise FileExistsError(f"artifact already exists: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp")
    fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(str(temporary), str(path))
        except FileExistsError:
            raise FileExistsError(f"artifact already exists: {path}")
        except OSError:
            fd2 = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            try:
                with os.fdopen(fd2, "wb") as handle2:
                    fd2 = -1
                    handle2.write(raw)
                    handle2.flush()
                    os.fsync(handle2.fileno())
            finally:
                if fd2 != -1:
                    os.close(fd2)
    finally:
        if fd != -1:
            os.close(fd)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _read_canonical_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise KoreanIndexArtifactError("artifact file must end with exactly one LF")
    try:
        value = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise KoreanIndexArtifactError("artifact file is not valid JSON") from exc
    if not isinstance(value, dict):
        raise KoreanIndexArtifactError("artifact file must contain a JSON object")
    if _canonical_bytes(value) + b"\n" != raw:
        raise KoreanIndexArtifactError("artifact file is not canonical JSON")
    return value


def _require_content_addressed_name(path: Path, expected_name: str) -> None:
    if path.name != expected_name:
        raise KoreanIndexArtifactError("artifact filename does not match content-addressed SHA-256")
