"""Additive read-only Flask Blueprint for Kronos Daily Close V5.1 research artifacts.

The blueprint intentionally has no app registration side effect.  App integration can
later import :func:`create_v51_research_api_blueprint` and register it beside the
existing V5 API without changing the V5 v2 routes.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Final

from flask import Blueprint, Response, current_app, request

try:  # jsonschema is already used by the V5 contract layer; keep import fail-closed.
    from jsonschema import Draft202012Validator
except Exception:  # pragma: no cover - runtime environments without jsonschema block source artifacts.
    Draft202012Validator = None  # type: ignore[assignment]

try:
    from .research_reports import ResearchReportCatalog, ResearchReportCatalogError, escaped_pre_report_html
except ImportError:  # pragma: no cover - supports direct module execution in legacy tests.
    from research_reports import ResearchReportCatalog, ResearchReportCatalogError, escaped_pre_report_html  # type: ignore[no-redef]


WEBUI_ROOT: Final = Path(__file__).resolve().parent
REPO_ROOT: Final = WEBUI_ROOT.parent
SCHEMA_ROOT: Final = REPO_ROOT / "docs" / "schemas"
SOURCE_SCHEMA_PATH: Final = SCHEMA_ROOT / "kronos_daily_1520_source.v1.schema.json"

API_PROTOCOL_ID: Final = "kronos_v51_research_api.v1"
API_SCHEMA_VERSION: Final = "kronos_v51_research_api.v1"
DEFAULT_ARTIFACT_DIR_CONFIG_KEY: Final = "KRONOS_V51_ARTIFACT_DIR"
LEGACY_ARTIFACT_DIR_CONFIG_KEY: Final = "KRONOS_V51_RESEARCH_ARTIFACT_DIR"
MAX_JSON_BYTES: Final = 1_000_000
ZERO_SHA256: Final = "0" * 64
UNAVAILABLE: Final = "UNAVAILABLE"

ALL_ROUTE_METHODS: Final = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}\Z")
SYMBOL_RE: Final = re.compile(r"^[0-9]{6}\Z")
SOURCE_TABLE_RE: Final = re.compile(r"^A[0-9]{6}\Z")
RFC3339_UTC_RE: Final = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")
REPORT_PATH_RE: Final = re.compile(r"^(?![A-Za-z]:)(?!/)(?!.*[\\])(?!.*(?:^|/)\.\.(?:/|$))[a-z0-9._/-]+\.(?:md|html)\Z")
ARTIFACT_QUERY_KEYS: Final[frozenset[str]] = frozenset({"run_id", "artifact_id", "revision"})
REVISION_QUERY_RE: Final = re.compile(r"^[1-9][0-9]{0,15}\Z")
PUBLIC_ID_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
PUBLIC_ROOT_ID_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")

V51_API_FALSE_LOCKS: Final[dict[str, bool]] = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}
V51_RESEARCH_CLAIMS: Final[dict[str, bool]] = {
    "official_close_claim": False,
    "paper_forward_claim": False,
    "live_trading_claim": False,
    "broker_integration_claim": False,
    "profitability_claim": False,
    "go_readiness_claim": False,
}
NO_CLAIM_LABELS: Final[tuple[str, ...]] = (
    "NO_OFFICIAL_CLOSE_CLAIM",
    "NO_PAPER_FORWARD",
    "NO_LIVE_TRADING",
    "NO_BROKER_INTEGRATION",
    "NO_PROFIT_CLAIM",
    "NO_GO_READINESS_CLAIM",
)
RESEARCH_TRUTH: Final[dict[str, Any]] = {
    "research_only": True,
    "read_only": True,
    "network_used": False,
    "causal_cutoff_kst": "15:20:00",
    "price_basis": "15:20_bar_close_proxy",
    "official_close": False,
    "official_close_claim": False,
    "daily_ohlcv_fallback_claim": False,
    "nearest_bar_fallback_claim": False,
    "live_broker_order_claim": False,
    "paper_forward_claim": False,
    "profitability_claim": False,
}

ACCOUNTING_CONTRACT: Final[dict[str, Any]] = {
    "initial_capital_krw": 60_000_000,
    "slot_count": 10,
    "slot_budget_krw": 5_000_000,
    "max_invested_krw": 50_000_000,
    "reserve_cash_krw": 10_000_000,
    "reserve_cash_display_percent": "16.6667%",
    "max_target_investment_display_percent": "83.3333%",
    "shorting_allowed": False,
    "leverage_allowed": False,
    "duplicate_symbol_slots_allowed": False,
}
COST_SCHEDULE: Final[dict[str, Any]] = {
    "primary": {"internal_id": "base_23bp", "round_trip_cost_bp": 23, "display_percent": "0.23%"},
    "zero_cost_control": {"internal_id": "zero_control_0bp", "round_trip_cost_bp": 0, "display_percent": "0.00%"},
    "stress_control": {"internal_id": "stress_46bp", "round_trip_cost_bp": 46, "display_percent": "0.46%"},
}
HORIZON_CONTRACT: Final[dict[str, Any]] = {
    "primary_horizon": "H1",
    "validation_horizons": ["H3", "H5"],
    "label_columns": [
        "future_return_h1_1520_proxy",
        "future_return_h3_1520_proxy",
        "future_return_h5_1520_proxy",
    ],
}
SOURCE_POLICY: Final[dict[str, Any]] = {
    "daily_1520_source_schema": "kronos_daily_1520_source.v1",
    "causal_panel_schema": "kronos_daily_v51_causal_panel.v1",
    "causal_cutoff_kst": "15:20:00",
    "price_basis": "15:20_bar_close_proxy",
    "official_close": False,
    "nearest_fallback_allowed": False,
    "full_day_daily_ohlcv_allowed": False,
    "price_volume_amount_approximation_allowed": False,
    "pykrx_offline_only": True,
    "naver_fallback_allowed": False,
    "network_required": False,
}
OVERLAY_POLICY: Final[dict[str, Any]] = {
    "allowed_index_provider": "PYKRX",
    "offline_artifact_required": True,
    "naver_fallback_allowed": False,
    "forbidden_provider": "NAVER",
    "missing_index_state": "BLOCKED_INDEX_SERIES_SOURCE",
}
EPOCH_UTC: Final = "1970-01-01T00:00:00Z"
REPORT_SOURCE_PROTOCOL: Final = "kronos_v51_report_catalog.v1"
REPORT_CATALOG_ARTIFACT_ID: Final = "report-catalog"

SOURCE_COVERAGE_ARTIFACT_ID: Final = "daily-close-v51-source-coverage"
CAUSAL_PANEL_ARTIFACT_ID: Final = "daily-close-v51-causal-panel"
ACCOUNTING_ARTIFACT_ID: Final = "daily-close-v51-accounting"
EVALUATOR_ARTIFACT_ID: Final = "daily-close-v51-evaluator"
BENCHMARK_OVERLAY_ARTIFACT_ID: Final = "daily-close-v51-benchmark-overlay"

V51_RESEARCH_ARTIFACT_IDS: Final[dict[str, str]] = {
    "SOURCE_COVERAGE": SOURCE_COVERAGE_ARTIFACT_ID,
    "CAUSAL_PANEL": CAUSAL_PANEL_ARTIFACT_ID,
    "ACCOUNTING": ACCOUNTING_ARTIFACT_ID,
    "EVALUATOR": EVALUATOR_ARTIFACT_ID,
    "BENCHMARK_OVERLAY": BENCHMARK_OVERLAY_ARTIFACT_ID,
}
ALLOWED_ARTIFACT_IDS: Final[frozenset[str]] = frozenset(V51_RESEARCH_ARTIFACT_IDS.values())


class V51ResearchApiError(Exception):
    """HTTP error with a bounded public message."""

    def __init__(self, status_code: int, message: str, *, code: str = "INTERNAL_ERROR") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = _safe_message(message)


class V51ArtifactUnavailable(Exception):
    """Provider-level fail-closed condition that returns a BLOCKED payload."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = str(reason_code or "ARTIFACT_UNAVAILABLE")
        self.message = _safe_message(message)


class V51ArtifactValidationError(ValueError):
    """Artifact content violated a V5.1 research contract."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = str(reason_code or "ARTIFACT_INVALID")
        self.message = _safe_message(message)


@dataclass(frozen=True)
class V51RouteSpec:
    route_id: str
    rule: str
    endpoint: str
    artifact_id: str
    artifact_key: str
    payload_schema_version: str
    schema_id: str
    validator: Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class ArtifactRead:
    artifact_id: str
    payload: Mapping[str, Any]
    canonical_bytes: bytes
    source_sha256: str
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class V51QueryBindings:
    run_id: str | None = None
    artifact_id: str | None = None
    revision: int | None = None


class ReadOnlyArtifactProvider:
    """Fail-closed file-backed provider for explicit V5.1 artifact directories.

    Files are resolved only from an exact allowlist as ``<artifact_id>.json``.  The
    provider never creates directories and does not consult the network.
    """

    read_only = True

    def __init__(
        self,
        artifact_dir: Path | str | None = None,
        *,
        allowed_artifact_ids: set[str] | frozenset[str] | None = None,
        max_bytes: int = MAX_JSON_BYTES,
        config_key: str = DEFAULT_ARTIFACT_DIR_CONFIG_KEY,
    ) -> None:
        self._explicit_root = _resolve_path(artifact_dir) if artifact_dir is not None else None
        self._allowed_artifact_ids = frozenset(allowed_artifact_ids or ALLOWED_ARTIFACT_IDS)
        self._max_bytes = _positive_max_bytes(max_bytes)
        self._config_key = str(config_key or DEFAULT_ARTIFACT_DIR_CONFIG_KEY)

    def read_json(self, artifact_id: str) -> Mapping[str, Any]:
        artifact_id = _require_allowed_artifact_id(artifact_id, self._allowed_artifact_ids)
        root = self._root()
        if not root.is_dir():
            raise V51ArtifactUnavailable("ARTIFACT_DIR_UNAVAILABLE", "configured artifact directory is unavailable")
        path = (root / f"{artifact_id}.json").resolve(strict=False)
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise V51ArtifactUnavailable("ARTIFACT_ID_NOT_ALLOWED", "artifact id is not allowlisted") from exc
        if not path.is_file():
            raise V51ArtifactUnavailable("ARTIFACT_MISSING", "allowlisted artifact is unavailable")
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise V51ArtifactUnavailable("ARTIFACT_UNREADABLE", "allowlisted artifact is unreadable") from exc
        if size > self._max_bytes:
            raise V51ArtifactUnavailable("ARTIFACT_TOO_LARGE", "allowlisted artifact exceeds the JSON byte limit")
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise V51ArtifactUnavailable("ARTIFACT_UNREADABLE", "allowlisted artifact is unreadable") from exc
        return _json_payload_from_bytes(raw, max_bytes=self._max_bytes)

    def _root(self) -> Path:
        if self._explicit_root is not None:
            return self._explicit_root
        try:
            configured = current_app.config.get(self._config_key)
            if configured in (None, "") and self._config_key != LEGACY_ARTIFACT_DIR_CONFIG_KEY:
                configured = current_app.config.get(LEGACY_ARTIFACT_DIR_CONFIG_KEY)
        except RuntimeError as exc:
            raise V51ArtifactUnavailable(
                "ARTIFACT_DIR_UNCONFIGURED",
                "explicit artifact directory is not configured",
            ) from exc
        if configured in (None, ""):
            raise V51ArtifactUnavailable(
                "ARTIFACT_DIR_UNCONFIGURED",
                "explicit artifact directory is not configured",
            )
        return _resolve_path(configured)


_SOURCE_SCHEMA_VALIDATOR: Any | None = None


def _resolve_path(path: Path | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _positive_max_bytes(value: int) -> int:
    if isinstance(value, bool):
        raise ValueError("max_json_bytes must be a positive integer")
    amount = int(value)
    if amount <= 0:
        raise ValueError("max_json_bytes must be a positive integer")
    return amount


def _require_allowed_artifact_id(artifact_id: Any, allowed: set[str] | frozenset[str] = ALLOWED_ARTIFACT_IDS) -> str:
    if not isinstance(artifact_id, str) or artifact_id not in allowed:
        raise V51ArtifactUnavailable("ARTIFACT_ID_NOT_ALLOWED", "artifact id is not allowlisted")
    return artifact_id


def _safe_message(message: Any) -> str:
    text = str(message or "request failed")
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"[A-Za-z]:[\\/][^\s,;]+", "[path]", text)
    text = re.sub(r"(?:^|\s)(?:\.\.?[\\/]|/)[^\s,;]+", " [path]", text)
    return text[:240]


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical UTF-8 JSON bytes used for response bodies and hashes."""

    return json.dumps(
        _jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical_json_bytes(value)
    return hashlib.sha256(raw).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _clone_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(canonical_json_bytes(value).decode("utf-8"))


def _json_payload_from_bytes(raw: bytes | bytearray, *, max_bytes: int) -> Mapping[str, Any]:
    if len(raw) > max_bytes:
        raise V51ArtifactUnavailable("ARTIFACT_TOO_LARGE", "allowlisted artifact exceeds the JSON byte limit")
    try:
        text = bytes(raw).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise V51ArtifactUnavailable("ARTIFACT_NOT_UTF8", "allowlisted artifact is not UTF-8 JSON") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise V51ArtifactUnavailable("ARTIFACT_JSON_INVALID", "allowlisted artifact is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise V51ArtifactUnavailable("ARTIFACT_JSON_INVALID", "allowlisted artifact JSON root must be an object")
    return value


def _coerce_provider_result(result: Any, *, artifact_id: str, max_bytes: int) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    metadata: dict[str, Any] = {}
    value = result
    if isinstance(result, Mapping) and isinstance(result.get("payload"), Mapping) and (
        "artifact_id" in result or "source_sha256" in result or "sha256" in result or "artifact_sha256" in result
    ):
        declared_artifact_id = result.get("artifact_id")
        if declared_artifact_id is not None and declared_artifact_id != artifact_id:
            raise V51ArtifactUnavailable("ARTIFACT_ID_MISMATCH", "provider returned a different artifact id")
        metadata = {str(key): item for key, item in result.items() if key != "payload"}
        value = result["payload"]
    elif hasattr(result, "payload"):
        declared_artifact_id = getattr(result, "artifact_id", artifact_id)
        if declared_artifact_id != artifact_id:
            raise V51ArtifactUnavailable("ARTIFACT_ID_MISMATCH", "provider returned a different artifact id")
        metadata = {
            key: getattr(result, key)
            for key in (
                "artifact_id",
                "source_sha256",
                "sha256",
                "artifact_sha256",
                "source_db_sha256",
                "generated_at",
                "created_at",
                "updated_at",
                "run_id",
                "run_revision",
                "revision",
                "run_artifact_id",
            )
            if hasattr(result, key)
        }
        value = getattr(result, "payload")

    if isinstance(value, (bytes, bytearray)):
        return _json_payload_from_bytes(value, max_bytes=max_bytes), metadata
    if isinstance(value, str):
        return _json_payload_from_bytes(value.encode("utf-8"), max_bytes=max_bytes), metadata
    if isinstance(value, Mapping):
        return value, metadata
    raise V51ArtifactUnavailable("ARTIFACT_JSON_INVALID", "provider returned an invalid artifact payload")


def _call_provider(provider: Any, artifact_id: str) -> Any:
    if callable(provider):
        return provider(artifact_id)
    for method_name in ("read_json", "read_artifact", "read", "get"):
        method = getattr(provider, method_name, None)
        if callable(method):
            return method(artifact_id)
    raise V51ArtifactUnavailable("ARTIFACT_PROVIDER_INVALID", "artifact provider does not expose a read method")


def _read_artifact(provider: Any, spec: V51RouteSpec, *, max_bytes: int) -> ArtifactRead:
    artifact_id = _require_allowed_artifact_id(spec.artifact_id)
    try:
        result = _call_provider(provider, artifact_id)
    except V51ArtifactUnavailable:
        raise
    except (FileNotFoundError, KeyError, LookupError) as exc:
        raise V51ArtifactUnavailable("ARTIFACT_MISSING", "allowlisted artifact is unavailable") from exc
    except Exception as exc:
        raise V51ArtifactUnavailable("ARTIFACT_UNREADABLE", "artifact provider could not read allowlisted artifact") from exc
    payload, metadata = _coerce_provider_result(result, artifact_id=artifact_id, max_bytes=max_bytes)
    try:
        canonical = canonical_json_bytes(payload)
    except (TypeError, ValueError) as exc:
        raise V51ArtifactUnavailable("ARTIFACT_JSON_INVALID", "artifact is outside the canonical JSON profile") from exc
    if len(canonical) > max_bytes:
        raise V51ArtifactUnavailable("ARTIFACT_TOO_LARGE", "allowlisted artifact exceeds the JSON byte limit")
    source_sha256 = hashlib.sha256(canonical).hexdigest()
    metadata_artifact_sha = metadata.get("artifact_sha256") or metadata.get("sha256")
    if metadata_artifact_sha is not None and metadata_artifact_sha != source_sha256:
        raise V51ArtifactUnavailable("SOURCE_HASH_MISMATCH", "provider artifact hash metadata does not match canonical payload")
    return ArtifactRead(
        artifact_id=artifact_id,
        payload=_clone_mapping(payload),
        canonical_bytes=canonical,
        source_sha256=source_sha256,
        metadata=metadata,
    )


def _load_source_schema_validator() -> Any:
    global _SOURCE_SCHEMA_VALIDATOR
    if Draft202012Validator is None:
        raise V51ArtifactValidationError("VALIDATOR_UNAVAILABLE", "jsonschema validator is unavailable")
    if _SOURCE_SCHEMA_VALIDATOR is None:
        try:
            schema = json.loads(SOURCE_SCHEMA_PATH.read_text(encoding="utf-8"))
        except OSError as exc:
            raise V51ArtifactValidationError("VALIDATOR_UNAVAILABLE", "source schema is unavailable") from exc
        Draft202012Validator.check_schema(schema)
        _SOURCE_SCHEMA_VALIDATOR = Draft202012Validator(schema)
    return _SOURCE_SCHEMA_VALIDATOR


def _validate_source_coverage(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    normalized = dict(payload)
    normalized.setdefault("rows", [])
    try:
        _load_source_schema_validator().validate(normalized)
    except V51ArtifactValidationError:
        raise
    except Exception as exc:
        raise V51ArtifactValidationError("ARTIFACT_INVALID", f"source coverage contract failed: {exc}") from exc
    if normalized.get("false_research_locks") != V51_API_FALSE_LOCKS:
        raise V51ArtifactValidationError("FALSE_LOCKS_DRIFT", "source false_research_locks must be the exact six false locks")
    if normalized.get("six_locks_false") != V51_API_FALSE_LOCKS:
        raise V51ArtifactValidationError("FALSE_LOCKS_DRIFT", "source six_locks_false must be the exact six false locks")
    snapshot = normalized.get("source_snapshot")
    if not isinstance(snapshot, Mapping) or snapshot.get("sha256") != normalized.get("source_db_sha256"):
        raise V51ArtifactValidationError("SOURCE_HASH_MISMATCH", "source_db_sha256 must match source_snapshot.sha256")
    _validate_common_research_contract(normalized)
    return normalized


def _validate_causal_panel_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        from stom_rl.daily_v51_causal_panel import SCHEMA_VERSION, validate_causal_panel

        if payload.get("schema_version") != SCHEMA_VERSION:
            raise V51ArtifactValidationError("SCHEMA_MISMATCH", "causal panel schema_version mismatch")
        validated = validate_causal_panel(payload)
    except V51ArtifactValidationError:
        raise
    except Exception as exc:
        raise V51ArtifactValidationError("ARTIFACT_INVALID", f"causal panel contract failed: {exc}") from exc
    _validate_common_research_contract(validated)
    return validated


def _accounting_manifest_sha256(manifest: Mapping[str, Any]) -> str:
    payload = {str(key): value for key, value in manifest.items() if str(key) != "accounting_manifest_sha256"}
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _validate_accounting_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        from stom_rl.v5_accounting import (  # noqa: PLC0415 - lazy import keeps blueprint import fail-closed.
            V51_ACCOUNTING_SCHEMA_VERSION,
            V51_FALSE_LOCKS,
            V51_PRICE_BASIS,
            V51_PROMOTION_CLAIMS,
        )
    except Exception as exc:
        raise V51ArtifactValidationError("VALIDATOR_UNAVAILABLE", "accounting constants are unavailable") from exc

    if payload.get("schema_version") != V51_ACCOUNTING_SCHEMA_VERSION:
        raise V51ArtifactValidationError("SCHEMA_MISMATCH", "accounting schema_version mismatch")
    declared = payload.get("accounting_manifest_sha256")
    if not _is_sha256(declared):
        raise V51ArtifactValidationError("SOURCE_HASH_MISMATCH", "accounting_manifest_sha256 is missing or invalid")
    if declared != _accounting_manifest_sha256(payload):
        raise V51ArtifactValidationError("SOURCE_HASH_MISMATCH", "accounting_manifest_sha256 does not match canonical contents")
    if payload.get("price_basis") != V51_PRICE_BASIS or payload.get("causal_cutoff_kst") != "15:20:00":
        raise V51ArtifactValidationError("RESEARCH_TRUTH_DRIFT", "accounting must use exact 15:20 price basis")
    if payload.get("official_close") is not False:
        raise V51ArtifactValidationError("RESEARCH_TRUTH_DRIFT", "accounting official_close must be false")
    if payload.get("false_locks") != V51_FALSE_LOCKS:
        raise V51ArtifactValidationError("FALSE_LOCKS_DRIFT", "accounting false_locks drifted")
    if payload.get("promotion_claims") != V51_PROMOTION_CLAIMS:
        raise V51ArtifactValidationError("CLAIM_DRIFT", "accounting promotion_claims drifted")
    _validate_common_research_contract(payload)
    return payload


def _validate_evaluator_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        from stom_rl.daily_v51_evaluator import (
            EVALUATOR_SCHEMA_VERSION,
            PRIMARY_VARIANT_ID,
            VALIDATION_VARIANT_IDS,
            VARIANT_ORDER,
            canonical_manifest_sha256,
        )
    except Exception as exc:
        raise V51ArtifactValidationError("VALIDATOR_UNAVAILABLE", "evaluator constants are unavailable") from exc

    if payload.get("schema_version") != EVALUATOR_SCHEMA_VERSION:
        raise V51ArtifactValidationError("SCHEMA_MISMATCH", "evaluator schema_version mismatch")
    declared = payload.get("manifest_sha256")
    if not _is_sha256(declared):
        raise V51ArtifactValidationError("SOURCE_HASH_MISMATCH", "evaluator manifest_sha256 is missing or invalid")
    if declared != canonical_manifest_sha256(payload):
        raise V51ArtifactValidationError("SOURCE_HASH_MISMATCH", "evaluator manifest_sha256 does not match canonical contents")
    if payload.get("price_basis") != "15:20_bar_close_proxy":
        raise V51ArtifactValidationError("RESEARCH_TRUTH_DRIFT", "evaluator must use exact 15:20 price basis")
    if payload.get("primary_variant_id") != PRIMARY_VARIANT_ID:
        raise V51ArtifactValidationError("SCHEMA_MISMATCH", "evaluator primary variant drifted")
    if tuple(payload.get("validation_variant_ids", ())) != VALIDATION_VARIANT_IDS:
        raise V51ArtifactValidationError("SCHEMA_MISMATCH", "evaluator validation variants drifted")
    if tuple(payload.get("variant_order", ())) != VARIANT_ORDER:
        raise V51ArtifactValidationError("SCHEMA_MISMATCH", "evaluator variant order drifted")
    _require_false_mapping(payload.get("false_locks"), "evaluator false_locks")
    _require_false_mapping(payload.get("promotion_claims"), "evaluator promotion_claims")
    gates_by_variant = payload.get("gates_by_variant")
    metrics_by_variant = payload.get("metrics_by_variant")
    if not isinstance(gates_by_variant, Mapping):
        raise V51ArtifactValidationError("ARTIFACT_INVALID", "evaluator gates_by_variant must be a variant mapping")
    if not isinstance(metrics_by_variant, Mapping):
        raise V51ArtifactValidationError("ARTIFACT_INVALID", "evaluator metrics_by_variant must be a variant mapping")
    horizon_results = payload.get("horizon_results")
    if (
        not isinstance(horizon_results, Sequence)
        or isinstance(horizon_results, (str, bytes, bytearray))
        or len(horizon_results) != len(VARIANT_ORDER)
    ):
        raise V51ArtifactValidationError("ARTIFACT_INVALID", "evaluator horizon_results must be exact H1/H3/H5 results")
    for index, result in enumerate(horizon_results):
        if not isinstance(result, Mapping):
            raise V51ArtifactValidationError("ARTIFACT_INVALID", f"evaluator horizon_result {index} must be an object")
        expected_variant_id = VARIANT_ORDER[index]
        if result.get("variant_id") != expected_variant_id:
            raise V51ArtifactValidationError("SCHEMA_MISMATCH", "evaluator horizon result variant order drifted")
        result_hash = result.get("result_sha256")
        if not _is_sha256(result_hash) or result_hash != canonical_manifest_sha256(result, digest_field="result_sha256"):
            raise V51ArtifactValidationError("SOURCE_HASH_MISMATCH", f"evaluator horizon_result {index} hash mismatch")
        gate = gates_by_variant.get(expected_variant_id)
        if not isinstance(gate, Mapping) or result.get("gate") != gate:
            raise V51ArtifactValidationError("SCHEMA_MISMATCH", "evaluator gates_by_variant must match horizon_results")
        if str(gate.get("status") or "").upper() not in {"PASS", "FAIL"}:
            raise V51ArtifactValidationError("ARTIFACT_INVALID", "evaluator gate status must be PASS or FAIL")
        metrics = metrics_by_variant.get(expected_variant_id)
        if not isinstance(metrics, Mapping) or result.get("metrics") != metrics:
            raise V51ArtifactValidationError("SCHEMA_MISMATCH", "evaluator metrics_by_variant must match horizon_results")
        accounting = result.get("accounting")
        if isinstance(accounting, Mapping):
            accounting_manifest = accounting.get("manifest") if isinstance(accounting.get("manifest"), Mapping) else accounting
            _validate_accounting_payload(accounting_manifest)
    _validate_common_research_contract(payload)
    return payload


def _validate_benchmark_overlay_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        from stom_rl.korean_index_overlay import SCHEMA_VERSION, validate_korean_index_overlay

        if payload.get("schema_version") != SCHEMA_VERSION:
            raise V51ArtifactValidationError("SCHEMA_MISMATCH", "benchmark overlay schema_version mismatch")
        validated = validate_korean_index_overlay(payload)
    except V51ArtifactValidationError:
        raise
    except Exception as exc:
        raise V51ArtifactValidationError("ARTIFACT_INVALID", f"benchmark overlay contract failed: {exc}") from exc
    _validate_common_research_contract(validated)
    return validated


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _require_false_mapping(value: Any, label: str) -> None:
    if not isinstance(value, Mapping) or not value or any(item is not False for item in value.values()):
        raise V51ArtifactValidationError("FALSE_LOCKS_DRIFT", f"{label} must be an explicit all-false mapping")


def _validate_common_research_contract(payload: Mapping[str, Any]) -> None:
    _reject_true_claims(payload)
    _validate_symbol_fields(payload)


def _reject_true_claims(value: Any, path: str = "$") -> None:
    forbidden_true_keys = {
        "official_close",
        "official_close_claim",
        "full_day_daily_ohlcv",
        "daily_ohlcv_fallback_claim",
        "nearest_bar_fallback_claim",
        "live_trading",
        "live_trading_claim",
        "live_broker_order_claim",
        "live_broker_order_allowed",
        "broker_integration",
        "broker_integration_claim",
        "paper_trading",
        "paper_forward_claim",
        "paper_forward_allowed",
        "profit",
        "profit_claim",
        "profitability_claim",
        "profitability_claim_allowed",
        "go_readiness_claim",
    }
    if isinstance(value, Mapping):
        for key, item in value.items():
            text_key = str(key)
            if text_key in forbidden_true_keys and item is True:
                raise V51ArtifactValidationError("CLAIM_DRIFT", f"{path}.{text_key} must be false")
            _reject_true_claims(item, f"{path}.{text_key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _reject_true_claims(item, f"{path}[{index}]")


def _validate_symbol_fields(value: Any, path: str = "$") -> None:
    symbol_keys = {"symbol", "ticker", "code"}
    symbol_list_keys = {"symbols", "tickers"}
    table_keys = {"table", "source_table"}
    table_list_keys = {"tables", "source_tables"}
    if isinstance(value, Mapping):
        for key, item in value.items():
            text_key = str(key)
            if text_key in symbol_keys and item is not None and not (isinstance(item, str) and SYMBOL_RE.fullmatch(item)):
                raise V51ArtifactValidationError("SYMBOL_INVALID", f"{path}.{text_key} must be a six-digit symbol")
            if text_key in symbol_list_keys:
                _require_string_list(item, SYMBOL_RE, f"{path}.{text_key}", "six-digit symbols")
            if text_key in table_keys and item is not None and not (isinstance(item, str) and SOURCE_TABLE_RE.fullmatch(item)):
                raise V51ArtifactValidationError("SYMBOL_INVALID", f"{path}.{text_key} must be an A-prefixed six-digit source table")
            if text_key in table_list_keys and _looks_like_string_list(item):
                _require_string_list(item, SOURCE_TABLE_RE, f"{path}.{text_key}", "A-prefixed six-digit source tables")
            _validate_symbol_fields(item, f"{path}.{text_key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _validate_symbol_fields(item, f"{path}[{index}]")


def _looks_like_string_list(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) and all(
        item is None or isinstance(item, str) for item in value
    )


def _require_string_list(value: Any, pattern: re.Pattern[str], label: str, description: str) -> None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise V51ArtifactValidationError("SYMBOL_INVALID", f"{label} must be a list of {description}")
    for index, item in enumerate(value):
        if not isinstance(item, str) or pattern.fullmatch(item) is None:
            raise V51ArtifactValidationError("SYMBOL_INVALID", f"{label}[{index}] must be {description}")



def _extract_source_db_sha256(payload: Mapping[str, Any]) -> str:
    direct = payload.get("source_db_sha256")
    if _is_sha256(direct):
        return str(direct)
    source_identity = payload.get("source_identity")
    if isinstance(source_identity, Mapping) and _is_sha256(source_identity.get("source_db_sha256")):
        return str(source_identity["source_db_sha256"])
    source_hashes = payload.get("source_hashes")
    if isinstance(source_hashes, Mapping) and _is_sha256(source_hashes.get("source_db_sha256")):
        return str(source_hashes["source_db_sha256"])
    return UNAVAILABLE


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _public_id(value: Any, default: str = "unavailable", *, max_length: int = 128) -> str:
    raw = str(value or default)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")
    if not slug or not slug[0].isalnum():
        slug = default
    if len(slug) > max_length:
        digest = hashlib.sha256(raw.encode("utf-8", "surrogateescape")).hexdigest()[:16]
        slug = f"{slug[: max_length - 17].rstrip('-._')}-{digest}"
    if PUBLIC_ID_RE.fullmatch(slug) is None:
        digest = hashlib.sha256(raw.encode("utf-8", "surrogateescape")).hexdigest()[:16]
        slug = f"{default}-{digest}"
    return slug[:max_length]


def _public_root_id(value: Any) -> str:
    text = str(value or "")
    return text if PUBLIC_ROOT_ID_RE.fullmatch(text) is not None else _public_id(text, "report-root", max_length=64)


def _external_report_id(record: Mapping[str, Any]) -> str:
    service_id = str(record.get("report_id") or record.get("relative_path") or "report")
    filename = str(record.get("relative_path") or service_id).replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    slug = _public_id(filename, "report", max_length=96)
    digest = hashlib.sha256(service_id.encode("utf-8", "surrogateescape")).hexdigest()[:16]
    return _public_id(f"{slug}-{digest}", "report", max_length=128)


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if 0 <= parsed <= 9_007_199_254_740_991:
        return parsed
    return default


def _positive_int(value: Any, default: int = 1) -> int:
    parsed = _safe_int(value, default)
    return parsed if parsed >= 1 else default

def _require_public_identity(value: Any, label: str) -> str:
    if not isinstance(value, str) or PUBLIC_ID_RE.fullmatch(value) is None:
        raise V51ArtifactValidationError("IDENTITY_SCHEMA_INVALID", f"{label} must be an explicit portable id")
    return value


def _require_positive_safe_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or value in (None, ""):
        raise V51ArtifactValidationError("IDENTITY_SCHEMA_INVALID", f"{label} must be an explicit positive safe integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and REVISION_QUERY_RE.fullmatch(value) is not None:
        parsed = int(value)
    else:
        raise V51ArtifactValidationError("IDENTITY_SCHEMA_INVALID", f"{label} must be an explicit positive safe integer")
    if not 1 <= parsed <= 9_007_199_254_740_991:
        raise V51ArtifactValidationError("IDENTITY_SCHEMA_INVALID", f"{label} must be an explicit positive safe integer")
    return parsed


def _require_sha256_identity(value: Any, label: str) -> str:
    if not _is_sha256(value) or str(value) == ZERO_SHA256:
        raise V51ArtifactValidationError("IDENTITY_SCHEMA_INVALID", f"{label} must be an explicit lowercase sha256")
    return str(value)


def _require_utc_identity(value: Any, label: str) -> str:
    if not isinstance(value, str) or value == EPOCH_UTC or RFC3339_UTC_RE.fullmatch(value) is None:
        raise V51ArtifactValidationError("IDENTITY_SCHEMA_INVALID", f"{label} must be an explicit UTC generated_at")
    return value



def _non_negative_number(value: Any, default: float | int = 0) -> float | int:
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed >= 0 and parsed <= 9_007_199_254_740_991 and parsed == parsed and parsed not in (float("inf"), float("-inf")):
        return int(parsed) if parsed.is_integer() else parsed
    return default


def _status(value: Any, default: str = "BLOCKED") -> str:
    text = str(value or "").upper()
    if text in {"READY", "PASS"}:
        return "READY"
    if text == "BLOCKED":
        return "BLOCKED"
    return default


def _availability_status(value: Any) -> str:
    text = str(value or "").lower()
    return "READY" if text in {"ready", "pass", "available", "ok", "true"} else "BLOCKED"


def _sha_or_zero(value: Any) -> str:
    return str(value) if _is_sha256(value) else ZERO_SHA256


def _utc_or_epoch(value: Any) -> str:
    return str(value) if isinstance(value, str) and RFC3339_UTC_RE.fullmatch(value) is not None else EPOCH_UTC


def _date_or_epoch(value: Any) -> str:
    text = str(value or "")
    return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else "1970-01-01"


def _timestamp_kst_or_epoch(value: Any) -> str:
    text = str(value or "")
    return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}T15:20:00\+09:00", text) else "1970-01-01T15:20:00+09:00"


def _compact_1520(value: Any) -> str:
    text = str(value or "")
    return text if re.fullmatch(r"\d{8}1520", text) else "197001011520"


def _cost_schedule() -> dict[str, Any]:
    return _clone_mapping(COST_SCHEDULE)


def _route_path(route_id: str, spec: V51RouteSpec | None = None) -> str:
    if route_id == "REPORTS":
        return "/api/daily-close-v51/reports"
    if route_id == "REPORT_READ":
        return "/api/daily-close-v51/reports/{report_id}"
    if spec is None:
        spec = ROUTE_SPECS_BY_ID[route_id]
    return f"/api/daily-close-v51{spec.rule}"


def _protocol_identity(route_id_or_spec: str | V51RouteSpec, *, max_bytes: int | None = None) -> dict[str, Any]:
    route_id = route_id_or_spec.route_id if isinstance(route_id_or_spec, V51RouteSpec) else str(route_id_or_spec)
    spec = route_id_or_spec if isinstance(route_id_or_spec, V51RouteSpec) else ROUTE_SPECS_BY_ID.get(route_id)
    return {
        "schema_version": API_PROTOCOL_ID,
        "api_version": "v5.1",
        "method": "GET",
        "read_only": True,
        "route_id": route_id,
        "route_path": _route_path(route_id, spec),
        "causal_cutoff_kst": "15:20:00",
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
        "accounting": _clone_mapping(ACCOUNTING_CONTRACT),
        "cost_schedule": _cost_schedule(),
        "horizon": _clone_mapping(HORIZON_CONTRACT),
        "source_policy": _clone_mapping(SOURCE_POLICY),
        "overlay_policy": _clone_mapping(OVERLAY_POLICY),
    }


def _run_identity(
    payload: Mapping[str, Any] | None,
    metadata: Mapping[str, Any] | None = None,
    *,
    source_sha256: str = ZERO_SHA256,
    protocol_sha256: str = ZERO_SHA256,
) -> dict[str, Any]:
    if payload is None and not metadata:
        return {
            "run_id": "unavailable-run",
            "run_revision": 1,
            "run_artifact_id": "unavailable-run-artifact",
            "source_sha256": _sha_or_zero(source_sha256),
            "protocol_sha256": _sha_or_zero(protocol_sha256),
            "stable_artifact_ids": {
                "source_coverage": SOURCE_COVERAGE_ARTIFACT_ID,
                "causal_panel": CAUSAL_PANEL_ARTIFACT_ID,
                "accounting": ACCOUNTING_ARTIFACT_ID,
                "evaluator": EVALUATOR_ARTIFACT_ID,
                "benchmark_overlay": BENCHMARK_OVERLAY_ARTIFACT_ID,
            },
        }
    payload = payload or {}
    metadata = metadata or {}
    nested_run = payload.get("run") if isinstance(payload.get("run"), Mapping) else {}
    nested_identity = payload.get("run_identity") if isinstance(payload.get("run_identity"), Mapping) else {}
    run_id = _first_present(
        metadata.get("run_id"),
        payload.get("run_id"),
        nested_identity.get("run_id"),
        nested_run.get("run_id"),
    )
    revision = _first_present(
        metadata.get("run_revision"),
        metadata.get("revision"),
        payload.get("run_revision"),
        payload.get("revision"),
        nested_identity.get("run_revision"),
        nested_identity.get("revision"),
        nested_run.get("run_revision"),
        nested_run.get("revision"),
    )
    run_artifact_id = _first_present(
        metadata.get("run_artifact_id"),
        payload.get("run_artifact_id"),
        nested_identity.get("run_artifact_id"),
        nested_run.get("run_artifact_id"),
    )
    return {
        "run_id": _require_public_identity(run_id, "run.run_id"),
        "run_revision": _require_positive_safe_int(revision, "run.run_revision"),
        "run_artifact_id": _require_public_identity(run_artifact_id, "run.run_artifact_id"),
        "source_sha256": _require_sha256_identity(source_sha256, "run.source_sha256"),
        "protocol_sha256": _require_sha256_identity(protocol_sha256, "run.protocol_sha256"),
        "stable_artifact_ids": {
            "source_coverage": SOURCE_COVERAGE_ARTIFACT_ID,
            "causal_panel": CAUSAL_PANEL_ARTIFACT_ID,
            "accounting": ACCOUNTING_ARTIFACT_ID,
            "evaluator": EVALUATOR_ARTIFACT_ID,
            "benchmark_overlay": BENCHMARK_OVERLAY_ARTIFACT_ID,
        },
    }


def _source_identity(read: ArtifactRead | None, spec: V51RouteSpec, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or (read.payload if read is not None else {})
    if read is None:
        return {
            "source_protocol": "kronos_daily_1520_source.v1",
            "source_artifact_id": spec.artifact_id,
            "source_sha256": ZERO_SHA256,
            "source_db_sha256": ZERO_SHA256,
            "generated_at": EPOCH_UTC,
            "causal_cutoff_kst": "15:20:00",
            "price_basis": "15:20_bar_close_proxy",
            "official_close": False,
        }
    metadata = read.metadata
    generated = _first_present(
        metadata.get("generated_at"),
        metadata.get("created_at"),
        metadata.get("updated_at"),
        payload.get("generated_at"),
        payload.get("created_at"),
        payload.get("updated_at"),
        (payload.get("source_identity") or {}).get("generated_at") if isinstance(payload.get("source_identity"), Mapping) else None,
    )
    source_db_sha256 = _first_present(metadata.get("source_db_sha256"), _extract_source_db_sha256(payload))
    return {
        "source_protocol": "kronos_daily_1520_source.v1",
        "source_artifact_id": spec.artifact_id,
        "source_sha256": _require_sha256_identity(read.source_sha256, "source.source_sha256"),
        "source_db_sha256": _require_sha256_identity(source_db_sha256, "source.source_db_sha256"),
        "generated_at": _require_utc_identity(generated, "source.generated_at"),
        "causal_cutoff_kst": "15:20:00",
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
    }


def _artifact_identity(read: ArtifactRead, spec: V51RouteSpec) -> dict[str, Any]:
    return {
        "artifact_id": spec.artifact_id,
        "artifact_kind": {
            "SOURCE_COVERAGE": "source_coverage",
            "CAUSAL_PANEL": "causal_panel",
            "ACCOUNTING": "accounting",
            "EVALUATOR": "evaluator",
            "BENCHMARK_OVERLAY": "benchmark_overlay",
        }[spec.route_id],
        "media_type": "application/json; charset=utf-8",
        "byte_length": len(read.canonical_bytes),
        "sha256": read.source_sha256,
        "stable_id": True,
    }


def _source_coverage_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    tables = [item for item in payload.get("tables", []) if isinstance(item, Mapping)]
    rows = [item for item in payload.get("rows", []) if isinstance(item, Mapping)]
    sample_table = tables[0] if tables else {}
    sample_row = rows[0] if rows else {}
    sample_symbol = str(_first_present(sample_row.get("symbol"), sample_table.get("symbol"), "000000"))
    if SYMBOL_RE.fullmatch(sample_symbol) is None:
        sample_symbol = "000000"
    timestamp = _first_present(sample_row.get("timestamp_yyyymmddhhmm"), sample_row.get("date"))
    return {
        "coverage_status": "READY" if _safe_int(payload.get("exact_1520_row_count")) > 0 else "BLOCKED",
        "exact_1520_row_count": _safe_int(payload.get("exact_1520_row_count")),
        "symbol_count": _safe_int(payload.get("symbol_count"), len({str(item.get("symbol")) for item in tables})),
        "session_count": _safe_int(payload.get("session_count"), len(payload.get("source_calendar", []) or [])),
        "first_valid_date": payload.get("first_valid_date") if isinstance(payload.get("first_valid_date"), str) else None,
        "last_valid_date": payload.get("last_valid_date") if isinstance(payload.get("last_valid_date"), str) else None,
        "sample_symbol": sample_symbol,
        "sample_timestamp_yyyymmddhhmm": _compact_1520(timestamp),
        "volume_to_1520_status": "NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY",
        "amount_to_1520_status": "NOT_AVAILABLE_5MIN_DB_HAS_NO_AMOUNT_COLUMN_DO_NOT_APPROXIMATE_PRICE_X_VOLUME",
        "missing_policy": "MISSING_1520_BAR_BLOCKS_ROW_NO_NEAREST_FALLBACK",
    }


def _causal_panel_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = [item for item in payload.get("rows", []) if isinstance(item, Mapping)]
    preview: list[dict[str, Any]] = []
    for row in rows[:20]:
        label_statuses = row.get("label_statuses") if isinstance(row.get("label_statuses"), Mapping) else {}

        def label_state(name: str) -> str:
            value = label_statuses.get(name)
            if isinstance(value, Mapping):
                return _availability_status(value.get("status"))
            return _availability_status(value)

        symbol = str(row.get("symbol") or "000000")
        if SYMBOL_RE.fullmatch(symbol) is None:
            symbol = "000000"
        preview.append(
            {
                "symbol": symbol,
                "session_date": _date_or_epoch(row.get("session")),
                "timestamp_kst": _timestamp_kst_or_epoch(row.get("cutoff_timestamp")),
                "price_basis": "15:20_bar_close_proxy",
                "official_close": False,
                "entry_status": _availability_status(row.get("entry_1520_status")),
                "h1_status": label_state("future_return_h1_1520_proxy"),
                "h3_status": label_state("future_return_h3_1520_proxy"),
                "h5_status": label_state("future_return_h5_1520_proxy"),
            }
        )
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), Mapping) else {}
    return {
        "panel_schema": "kronos_daily_v51_causal_panel.v1",
        "row_count": _safe_int(coverage.get("panel_row_count"), len(rows)),
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
        "primary_horizon": "H1",
        "validation_horizons": ["H3", "H5"],
        "label_columns": list(HORIZON_CONTRACT["label_columns"]),
        "rows_preview": preview,
    }


def _accounting_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    blockers = payload.get("blockers")
    blocked = isinstance(blockers, Sequence) and not isinstance(blockers, (str, bytes, bytearray)) and len(blockers) > 0
    nav = _first_present(payload.get("economic_nav_krw"), payload.get("account_nav_krw"), payload.get("total_capital_krw"), 60_000_000)
    reserve = _first_present(payload.get("cash_reserve_krw"), payload.get("reserve_cash_krw"), 10_000_000)
    return {
        "accounting_status": "BLOCKED" if blocked else "READY",
        "contract": _clone_mapping(ACCOUNTING_CONTRACT),
        "cost_schedule": _cost_schedule(),
        "economic_nav_krw": _non_negative_number(nav, 60_000_000),
        "cash_reserve_krw": _non_negative_number(reserve, 10_000_000),
        "slots_used": min(_safe_int(payload.get("selected_count")), 10),
        "max_slots": 10,
        "internal_cost_id": "base_23bp",
        "display_cost_percent": "0.23%",
    }


def _cost_pair_from_metrics(metrics: Mapping[str, Any]) -> tuple[str, str]:
    scenario_id = str(metrics.get("cost_scenario_id") or "")
    cost_bp = _safe_int(metrics.get("round_trip_cost_bp"), -1)
    for item in _cost_schedule().values():
        if item["internal_id"] == scenario_id or item["round_trip_cost_bp"] == cost_bp:
            return str(item["internal_id"]), str(item["display_percent"])
    return "base_23bp", "0.23%"


def _return_ratio_from_nav(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        nav = float(value)
    except (TypeError, ValueError):
        return None
    if nav < 0 or nav != nav or nav in (float("inf"), float("-inf")):
        return None
    return (nav / float(ACCOUNTING_CONTRACT["initial_capital_krw"])) - 1.0


def _display_ratio_percent(value: float) -> str:
    return f"{value * 100.0:.2f}%"


def _evaluator_metric_from_result(result: Mapping[str, Any]) -> dict[str, Any] | None:
    metrics = result.get("metrics")
    if not isinstance(metrics, Mapping):
        return None
    horizon = str(result.get("horizon_id") or "")
    if horizon not in {"H1", "H3", "H5"}:
        return None
    ratio = _return_ratio_from_nav(metrics.get("account_nav"))
    if ratio is None:
        return None
    internal_cost_id, display_cost_percent = _cost_pair_from_metrics(metrics)
    split = "train" if result.get("role") == "primary" else "validation"
    return {
        "metric_id": "cumulative_return",
        "split": split,
        "horizon": horizon,
        "internal_cost_id": internal_cost_id,
        "display_cost_percent": display_cost_percent,
        "value": ratio,
        "display_percent": _display_ratio_percent(ratio),
    }


def _gate_passed(gates_by_variant: Mapping[str, Any], result: Mapping[str, Any]) -> bool:
    variant_id = str(result.get("variant_id") or "")
    gate = gates_by_variant.get(variant_id)
    if not isinstance(gate, Mapping):
        gate = result.get("gate") if isinstance(result.get("gate"), Mapping) else {}
    return str(gate.get("status") or "").upper() == "PASS"


def _evaluator_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_results = payload.get("horizon_results")
    horizon_results = (
        [item for item in raw_results if isinstance(item, Mapping)]
        if isinstance(raw_results, Sequence) and not isinstance(raw_results, (str, bytes, bytearray))
        else []
    )
    gates_by_variant = payload.get("gates_by_variant") if isinstance(payload.get("gates_by_variant"), Mapping) else {}
    ready_by_variant = {str(result.get("variant_id") or ""): _gate_passed(gates_by_variant, result) for result in horizon_results}
    primary_ready = ready_by_variant.get("v51-h1-primary") is True
    validation_ready = all(
        ready_by_variant.get(variant_id) is True
        for variant_id in ("v51-h3-validation", "v51-h5-validation")
    )
    evaluation_ready = len(horizon_results) == 3 and primary_ready and validation_ready
    metrics = [metric for result in horizon_results if (metric := _evaluator_metric_from_result(result)) is not None]
    return {
        "evaluation_status": "READY" if evaluation_ready else "BLOCKED",
        "primary_horizon": "H1",
        "validation_horizons": ["H3", "H5"],
        "cost_schedule": _cost_schedule(),
        "split_statuses": {
            "train": "READY" if primary_ready else "BLOCKED",
            "validation": "READY" if validation_ready else "BLOCKED",
            "test": "BLOCKED",
        },
        "metrics": metrics,
    }


def _display_percent(first: Any, last: Any) -> str | None:
    try:
        start = float(first)
        end = float(last)
    except (TypeError, ValueError):
        return None
    if start <= 0 or start != start or end != end:
        return None
    return f"{((end / start) - 1.0) * 100.0:.2f}%"


def _overlay_source_state(payload: Mapping[str, Any]) -> str:
    reason_codes = {str(code) for code in payload.get("reason_codes", [])} if isinstance(payload.get("reason_codes"), Sequence) else set()
    if any("PYKRX" in code or "INDEX_ARTIFACT_MISSING" in code for code in reason_codes):
        return "BLOCKED_PYKRX_ARTIFACT_MISSING"
    return "BLOCKED_INDEX_SERIES_SOURCE"


def _benchmark_overlay_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_series = [item for item in payload.get("series", []) if isinstance(item, Mapping)]
    by_id = {str(_first_present(item.get("id"), item.get("market"), item.get("series_id"))).upper(): item for item in raw_series}
    source_state = "READY" if str(payload.get("status")).upper() == "PASS" else _overlay_source_state(payload)
    series: list[dict[str, Any]] = []
    for public_id, raw_id in (("KOSPI", "KOSPI"), ("KOSDAQ", "KOSDAQ"), ("RL_PORTFOLIO", "RL")):
        item = by_id.get(raw_id)
        rows = [row for row in (item or {}).get("series", []) if isinstance(row, Mapping)] if isinstance(item, Mapping) else []
        first = rows[0].get("close") if rows else None
        last = rows[-1].get("close") if rows else None
        ready = item is not None and source_state == "READY"
        series.append(
            {
                "series_id": public_id,
                "status": "READY" if ready else "BLOCKED",
                "source_state": "READY" if ready else source_state,
                "provider": "PYKRX" if public_id in {"KOSPI", "KOSDAQ"} and ready else None,
                "naver_used": False,
                "index_100": _non_negative_number(last, 100) if ready else None,
                "cumulative_return_display_percent": _display_percent(first, last) if ready else None,
            }
        )
    return {
        "overlay_status": "READY" if source_state == "READY" else "BLOCKED",
        "provider_policy": _clone_mapping(OVERLAY_POLICY),
        "common_start_index": 100,
        "series": series,
    }


def _research_body_for_spec(spec: V51RouteSpec, payload: Mapping[str, Any]) -> dict[str, Any]:
    if spec.route_id == "SOURCE_COVERAGE":
        return _source_coverage_summary(payload)
    if spec.route_id == "CAUSAL_PANEL":
        return _causal_panel_summary(payload)
    if spec.route_id == "ACCOUNTING":
        return _accounting_summary(payload)
    if spec.route_id == "EVALUATOR":
        return _evaluator_summary(payload)
    if spec.route_id == "BENCHMARK_OVERLAY":
        return _benchmark_overlay_summary(payload)
    raise V51ResearchApiError(503, "unknown V5.1 route", code="INTERNAL_ERROR")


def _status_reason_for_body(spec: V51RouteSpec, body: Mapping[str, Any]) -> tuple[str, str]:
    if spec.route_id == "BENCHMARK_OVERLAY":
        blocked_states = [
            str(item.get("source_state"))
            for item in body.get("series", [])
            if isinstance(item, Mapping) and str(item.get("source_state")) != "READY"
        ]
        if str(body.get("overlay_status")) == "READY" and not blocked_states:
            return "READY", "READY"
        reason = "BLOCKED_PYKRX_ARTIFACT_MISSING" if "BLOCKED_PYKRX_ARTIFACT_MISSING" in blocked_states else "BLOCKED_INDEX_SERIES_SOURCE"
        return "BLOCKED", reason
    status_field = {
        "SOURCE_COVERAGE": "coverage_status",
        "ACCOUNTING": "accounting_status",
        "EVALUATOR": "evaluation_status",
    }.get(spec.route_id)
    if status_field is not None and body.get(status_field) == "READY":
        return "READY", "READY"
    if spec.route_id == "CAUSAL_PANEL" and body.get("row_count", 0) and all(
        item.get("entry_status") == "READY"
        for item in body.get("rows_preview", [])
        if isinstance(item, Mapping)
    ):
        return "READY", "READY"
    if spec.route_id == "EVALUATOR":
        return "BLOCKED", "BLOCKED_SOURCE_CONTRACT"
    return "BLOCKED", "BLOCKED_SOURCE_CONTRACT"


def _blocked_status_reason(reason_code: str) -> str:
    code = str(reason_code or "")
    if "REPORT" in code:
        return "BLOCKED_REPORT_NOT_FOUND"
    if "INDEX" in code or "PYKRX" in code:
        return "BLOCKED_INDEX_SERIES_SOURCE"
    if "SCHEMA" in code or "VALID" in code or "LOCK" in code or "CLAIM" in code or "SYMBOL" in code or "HASH" in code:
        return "BLOCKED_SCHEMA_INVALID"
    return "BLOCKED_ARTIFACT_UNAVAILABLE"


def _blocked_body_for_spec(spec: V51RouteSpec, reason_code: str) -> dict[str, Any]:
    if spec.route_id == "SOURCE_COVERAGE":
        return {
            "coverage_status": "BLOCKED",
            "exact_1520_row_count": 0,
            "symbol_count": 0,
            "session_count": 0,
            "first_valid_date": None,
            "last_valid_date": None,
            "sample_symbol": "000000",
            "sample_timestamp_yyyymmddhhmm": "197001011520",
            "volume_to_1520_status": "NOT_AVAILABLE_SOURCE_HAS_SINGLE_5MIN_BAR_VOLUME_ONLY",
            "amount_to_1520_status": "NOT_AVAILABLE_5MIN_DB_HAS_NO_AMOUNT_COLUMN_DO_NOT_APPROXIMATE_PRICE_X_VOLUME",
            "missing_policy": "MISSING_1520_BAR_BLOCKS_ROW_NO_NEAREST_FALLBACK",
        }
    if spec.route_id == "CAUSAL_PANEL":
        return {
            "panel_schema": "kronos_daily_v51_causal_panel.v1",
            "row_count": 0,
            "price_basis": "15:20_bar_close_proxy",
            "official_close": False,
            "primary_horizon": "H1",
            "validation_horizons": ["H3", "H5"],
            "label_columns": list(HORIZON_CONTRACT["label_columns"]),
            "rows_preview": [],
        }
    if spec.route_id == "ACCOUNTING":
        return dict(_accounting_summary({"blockers": [reason_code]}), accounting_status="BLOCKED")
    if spec.route_id == "EVALUATOR":
        return _evaluator_summary({})
    return _benchmark_overlay_summary({"status": "BLOCKED", "reason_codes": [reason_code]})


def _success_payload(read: ArtifactRead, spec: V51RouteSpec, *, max_bytes: int) -> dict[str, Any]:
    validated = spec.validator(read.payload)
    source_payload = _clone_mapping(validated)
    body = _research_body_for_spec(spec, source_payload)
    body_canonical = canonical_json_bytes(body)
    if len(body_canonical) > max_bytes:
        raise V51ResearchApiError(413, "validated artifact exceeds byte limit", code="VALIDATION_ERROR")
    response_read = ArtifactRead(
        artifact_id=read.artifact_id,
        payload=body,
        canonical_bytes=body_canonical,
        source_sha256=hashlib.sha256(body_canonical).hexdigest(),
        metadata=read.metadata,
    )
    status, reason = _status_reason_for_body(spec, body)
    protocol = _protocol_identity(spec)
    source = _source_identity(read, spec, source_payload)
    payload = {
        "route_id": spec.route_id,
        "status": status,
        "status_reason": reason,
        "protocol": protocol,
        "source": source,
        "run": _run_identity(
            source_payload,
            read.metadata,
            source_sha256=source["source_sha256"],
            protocol_sha256=sha256_hex(protocol),
        ),
        "artifact": _artifact_identity(response_read, spec),
        "locks": dict(V51_API_FALSE_LOCKS),
        "claims": dict(V51_RESEARCH_CLAIMS),
        spec.artifact_key: body,
    }
    _validate_envelope(payload)
    return payload


def _blocked_payload(spec: V51RouteSpec, *, reason_code: str, message: str, max_bytes: int) -> dict[str, Any]:
    body = _blocked_body_for_spec(spec, reason_code)
    body_canonical = canonical_json_bytes(body)
    read = ArtifactRead(
        artifact_id=spec.artifact_id,
        payload=body,
        canonical_bytes=body_canonical,
        source_sha256=hashlib.sha256(body_canonical).hexdigest(),
        metadata={},
    )
    protocol = _protocol_identity(spec)
    payload = {
        "route_id": spec.route_id,
        "status": "BLOCKED",
        "status_reason": _blocked_status_reason(reason_code),
        "protocol": protocol,
        "source": _source_identity(None, spec),
        "run": _run_identity(None, source_sha256=ZERO_SHA256, protocol_sha256=sha256_hex(protocol)),
        "artifact": _artifact_identity(read, spec),
        "locks": dict(V51_API_FALSE_LOCKS),
        "claims": dict(V51_RESEARCH_CLAIMS),
        spec.artifact_key: body,
    }
    _validate_envelope(payload)
    return payload


def _error_payload(spec: V51RouteSpec, status_code: int, message: str, *, code: str = "INTERNAL_ERROR", max_bytes: int) -> dict[str, Any]:
    return {
        "route_id": spec.route_id,
        "status": "ERROR",
        "protocol": _protocol_identity(spec),
        "locks": dict(V51_API_FALSE_LOCKS),
        "claims": dict(V51_RESEARCH_CLAIMS),
        "error": {"code": code, "message": _safe_message(message), "status_code": status_code},
    }


def _validate_envelope(payload: Mapping[str, Any]) -> None:
    if payload.get("locks") != V51_API_FALSE_LOCKS:
        raise V51ResearchApiError(503, "response locks drifted", code="INTERNAL_ERROR")
    if payload.get("claims") != V51_RESEARCH_CLAIMS:
        raise V51ResearchApiError(503, "response claims drifted", code="INTERNAL_ERROR")
    _reject_true_claims(payload)


def _json_response(payload: Mapping[str, Any], status_code: int = 200, *, max_bytes: int = MAX_JSON_BYTES) -> Response:
    try:
        raw = canonical_json_bytes(payload)
    except (TypeError, ValueError) as exc:
        raise V51ResearchApiError(503, "response is outside the canonical JSON profile", code="INTERNAL_ERROR") from exc
    if len(raw) > max_bytes:
        raise V51ResearchApiError(413, "JSON response exceeds byte limit", code="VALIDATION_ERROR")
    response = current_app.response_class(raw, status=status_code, mimetype="application/json")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


def _method_not_allowed_response(payload: Mapping[str, Any], *, max_bytes: int) -> Response:
    response = _json_response(payload, 405, max_bytes=max_bytes)
    response.headers["Allow"] = "GET"
    return response


def _validate_query_keys(allowed: frozenset[str]) -> None:
    for key in request.args.keys():
        if key not in allowed:
            raise V51ResearchApiError(400, "unknown query argument", code="BAD_REQUEST")
        if len(request.args.getlist(key)) != 1:
            raise V51ResearchApiError(400, "duplicate query argument", code="BAD_REQUEST")


def _validate_public_query_id(value: str, label: str) -> str:
    if PUBLIC_ID_RE.fullmatch(value) is None:
        raise V51ResearchApiError(400, f"{label} query value is not portable", code="BAD_REQUEST")
    return value


def _validate_revision_query(value: str) -> int:
    if REVISION_QUERY_RE.fullmatch(value) is None:
        raise V51ResearchApiError(400, "revision query value is not a positive safe integer", code="BAD_REQUEST")
    revision = int(value)
    if revision > 9_007_199_254_740_991:
        raise V51ResearchApiError(400, "revision query value is not a positive safe integer", code="BAD_REQUEST")
    return revision


def _validate_artifact_query_bindings(spec: V51RouteSpec) -> V51QueryBindings:
    _validate_query_keys(ARTIFACT_QUERY_KEYS)
    artifact_id = request.args.get("artifact_id")
    if artifact_id is not None:
        artifact_id = _validate_public_query_id(artifact_id, "artifact_id")
        if artifact_id != spec.artifact_id:
            raise V51ResearchApiError(409, "artifact_id query does not match route artifact", code="CONFLICT")
    run_id = request.args.get("run_id")
    if run_id is not None:
        run_id = _validate_public_query_id(run_id, "run_id")
    revision_value = request.args.get("revision")
    revision = _validate_revision_query(revision_value) if revision_value is not None else None
    return V51QueryBindings(run_id=run_id, artifact_id=artifact_id, revision=revision)


def _validate_empty_query_bindings() -> None:
    _validate_query_keys(frozenset())


def _enforce_artifact_query_bindings(bindings: V51QueryBindings, payload: Mapping[str, Any]) -> None:
    if bindings.run_id is None and bindings.artifact_id is None and bindings.revision is None:
        return
    run_identity = payload.get("run")
    artifact_identity = payload.get("artifact")
    if not isinstance(run_identity, Mapping) or not isinstance(artifact_identity, Mapping):
        raise V51ResearchApiError(503, "response identity is unavailable", code="INTERNAL_ERROR")
    if payload.get("status") != "READY" and (bindings.run_id is not None or bindings.revision is not None):
        raise V51ResearchApiError(409, "run identity query cannot be matched without a validated artifact", code="CONFLICT")
    if bindings.artifact_id is not None and artifact_identity.get("artifact_id") != bindings.artifact_id:
        raise V51ResearchApiError(409, "artifact_id query does not match response identity", code="CONFLICT")
    if bindings.run_id is not None and run_identity.get("run_id") != bindings.run_id:
        raise V51ResearchApiError(409, "run_id query does not match response identity", code="CONFLICT")
    if bindings.revision is not None and run_identity.get("run_revision") != bindings.revision:
        raise V51ResearchApiError(409, "revision query does not match response identity", code="CONFLICT")


def _report_status_reason_from_error(exc: ResearchReportCatalogError) -> str:
    code = str(getattr(exc, "code", ""))
    if code in {"INVALID_REPORT_ID", "REPORT_NOT_FOUND"}:
        return "BLOCKED_REPORT_NOT_FOUND"
    if code in {"BINARY_CONTENT", "DENIED_EXTENSION", "INVALID_CATALOG", "INVALID_ENCODING", "REPORT_TOO_LARGE", "SPECIAL_FILE", "UNSAFE_LINK", "DUPLICATE_REPORT_ID"}:
        return "BLOCKED_SCHEMA_INVALID"
    return "BLOCKED_ARTIFACT_UNAVAILABLE"


def _raise_typed_report_catalog_error(exc: ResearchReportCatalogError) -> None:
    if int(getattr(exc, "status_code", 0) or 0) == 413:
        raise V51ResearchApiError(413, "report exceeds byte limit", code="VALIDATION_ERROR") from exc


class _UnavailableReportCatalog:
    def list_reports(self) -> list[dict[str, object]]:
        raise ResearchReportCatalogError(503, "REPORT_CATALOG_UNAVAILABLE", "report catalog is unavailable")

    def read_report(self, report_id: str) -> dict[str, object]:
        raise ResearchReportCatalogError(404, "REPORT_NOT_FOUND", "report_id is not in the allowlisted catalog")

def _default_report_catalog() -> Any:
    try:
        return ResearchReportCatalog()
    except Exception:  # noqa: BLE001 - fail closed without leaking approved root details.
        return _UnavailableReportCatalog()


def _report_summary_from_record(record: Mapping[str, Any], *, report_id: str | None = None) -> dict[str, Any]:
    relative_path_value = record.get("relative_path")
    if not isinstance(relative_path_value, str) or REPORT_PATH_RE.fullmatch(relative_path_value) is None:
        raise ResearchReportCatalogError(503, "INVALID_CATALOG", "report catalog returned invalid relative_path")
    relative_path = relative_path_value
    title = str(record.get("title") or "Untitled report")[:200] or "Untitled report"
    media_type = record.get("media_type") or record.get("mime_type")
    expected_media_type = "text/html; charset=utf-8" if relative_path.endswith(".html") else "text/markdown; charset=utf-8"
    if media_type != expected_media_type:
        raise ResearchReportCatalogError(503, "INVALID_CATALOG", "report catalog returned media_type inconsistent with relative_path")
    return {
        "report_id": report_id or _external_report_id(record),
        "title": title,
        "relative_path": relative_path,
        "root_id": _public_root_id(record.get("root_id")),
        "media_type": media_type,
        "byte_length": _safe_int(record.get("byte_length")),
        "sha256": _sha_or_zero(_first_present(record.get("sha256"), record.get("content_sha256"))),
        "updated_at": _utc_or_epoch(record.get("updated_at")),
        "source_protocol": REPORT_SOURCE_PROTOCOL,
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
    }


def _placeholder_report(report_id: Any = "report-not-found") -> dict[str, Any]:
    return {
        "report_id": _public_id(report_id, "report-not-found"),
        "title": "Report not found",
        "relative_path": "report-not-found.md",
        "root_id": "report-catalog",
        "media_type": "text/markdown; charset=utf-8",
        "byte_length": 0,
        "sha256": ZERO_SHA256,
        "updated_at": EPOCH_UTC,
        "source_protocol": REPORT_SOURCE_PROTOCOL,
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
    }


def _report_source_from_summaries(summaries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    updated = sorted(
        str(item.get("updated_at"))
        for item in summaries
        if isinstance(item.get("updated_at"), str) and RFC3339_UTC_RE.fullmatch(str(item.get("updated_at"))) is not None
    )
    return {
        "source_protocol": REPORT_SOURCE_PROTOCOL,
        "catalog_artifact_id": REPORT_CATALOG_ARTIFACT_ID,
        "catalog_sha256": sha256_hex(list(summaries)),
        "generated_at": updated[-1] if updated else EPOCH_UTC,
        "price_basis": "15:20_bar_close_proxy",
        "official_close": False,
    }


def _report_entries(report_catalog: Any) -> tuple[list[tuple[str, dict[str, Any]]], dict[str, Any]]:
    records = report_catalog.list_reports()
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)):
        raise ResearchReportCatalogError(503, "INVALID_CATALOG", "report catalog returned an invalid list")
    entries: list[tuple[str, dict[str, Any]]] = []
    public_ids: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            raise ResearchReportCatalogError(503, "INVALID_CATALOG", "report catalog returned an invalid item")
        service_id = str(record.get("report_id") or "")
        if not service_id:
            raise ResearchReportCatalogError(503, "INVALID_CATALOG", "report catalog item is missing report_id")
        summary = _report_summary_from_record(record)
        public_id = str(summary.get("report_id") or "")
        if public_id in public_ids:
            raise ResearchReportCatalogError(503, "INVALID_CATALOG", "report catalog returned duplicate public ids")
        public_ids.add(public_id)
        entries.append((service_id, summary))
    summaries = [summary for _, summary in entries]
    return entries, _report_source_from_summaries(summaries)


def _report_list_payload(report_catalog: Any) -> dict[str, Any]:
    try:
        entries, source = _report_entries(report_catalog)
        status = "READY"
        reason = "READY"
        reports = [summary for _, summary in entries]
    except ResearchReportCatalogError as exc:
        _raise_typed_report_catalog_error(exc)
        source = _report_source_from_summaries([])
        status = "BLOCKED"
        reason = _report_status_reason_from_error(exc)
        reports = []
    payload = {
        "route_id": "REPORTS",
        "status": status,
        "status_reason": reason,
        "protocol": _protocol_identity("REPORTS"),
        "source": source,
        "locks": dict(V51_API_FALSE_LOCKS),
        "claims": dict(V51_RESEARCH_CLAIMS),
        "reports": reports,
    }
    _validate_envelope(payload)
    return payload


def _report_blocked_read_payload(report_id: Any, reason: str = "BLOCKED_REPORT_NOT_FOUND") -> dict[str, Any]:
    payload = {
        "route_id": "REPORT_READ",
        "status": "BLOCKED",
        "status_reason": reason,
        "protocol": _protocol_identity("REPORT_READ"),
        "source": _report_source_from_summaries([]),
        "locks": dict(V51_API_FALSE_LOCKS),
        "claims": dict(V51_RESEARCH_CLAIMS),
        "report": _placeholder_report(report_id),
        "content": {"raw_text": "", "safe_html": escaped_pre_report_html("")},
    }
    _validate_envelope(payload)
    return payload

def _report_error_payload(route_id: str, status_code: int, message: str, *, code: str = "INTERNAL_ERROR") -> dict[str, Any]:
    safe_route_id = route_id if route_id in {"REPORTS", "REPORT_READ"} else "REPORTS"
    payload = {
        "route_id": safe_route_id,
        "status": "ERROR",
        "protocol": _protocol_identity(safe_route_id),
        "source": _report_source_from_summaries([]),
        "locks": dict(V51_API_FALSE_LOCKS),
        "claims": dict(V51_RESEARCH_CLAIMS),
        "error": {"code": code, "message": _safe_message(message), "status_code": status_code},
    }
    _validate_envelope(payload)
    return payload


def _report_read_payload(report_catalog: Any, report_id: str) -> dict[str, Any]:
    if PUBLIC_ID_RE.fullmatch(str(report_id or "")) is None:
        return _report_blocked_read_payload("report-not-found")
    try:
        entries, _ = _report_entries(report_catalog)
        by_public_id: dict[str, tuple[str, dict[str, Any]]] = {}
        for service_id, summary in entries:
            public_id = str(summary.get("report_id") or "")
            if public_id in by_public_id:
                raise ResearchReportCatalogError(503, "INVALID_CATALOG", "report catalog returned duplicate public ids")
            by_public_id[public_id] = (service_id, summary)
        match = by_public_id.get(report_id)
        if match is None:
            return _report_blocked_read_payload(report_id)
        service_id, listed_summary = match
        public_report_id = str(listed_summary["report_id"])
        record = report_catalog.read_report(service_id)
        if not isinstance(record, Mapping):
            raise ResearchReportCatalogError(503, "INVALID_CATALOG", "report catalog returned invalid content")
        summary = _report_summary_from_record(record, report_id=public_report_id)
        source = _report_source_from_summaries(
            [summary if str(item.get("report_id") or "") == public_report_id else item for _, item in entries]
        )
        raw_text = str(_first_present(record.get("raw_text"), record.get("content"), record.get("text"), ""))
        content = {
            "raw_text": raw_text,
            "safe_html": escaped_pre_report_html(raw_text),
        }
    except ResearchReportCatalogError as exc:
        _raise_typed_report_catalog_error(exc)
        return _report_blocked_read_payload(report_id, _report_status_reason_from_error(exc))
    payload = {
        "route_id": "REPORT_READ",
        "status": "READY",
        "status_reason": "READY",
        "protocol": _protocol_identity("REPORT_READ"),
        "source": source,
        "locks": dict(V51_API_FALSE_LOCKS),
        "claims": dict(V51_RESEARCH_CLAIMS),
        "report": summary,
        "content": content,
    }
    _validate_envelope(payload)
    return payload


ROUTE_SPECS: Final[tuple[V51RouteSpec, ...]] = (
    V51RouteSpec(
        route_id="SOURCE_COVERAGE",
        rule="/source-coverage",
        endpoint="source_coverage",
        artifact_id=SOURCE_COVERAGE_ARTIFACT_ID,
        artifact_key="source_coverage",
        payload_schema_version="kronos_daily_1520_source.v1",
        schema_id="https://kronos.local/schemas/kronos_daily_1520_source.v1.schema.json",
        validator=_validate_source_coverage,
    ),
    V51RouteSpec(
        route_id="CAUSAL_PANEL",
        rule="/causal-panel",
        endpoint="causal_panel",
        artifact_id=CAUSAL_PANEL_ARTIFACT_ID,
        artifact_key="causal_panel",
        payload_schema_version="kronos_daily_v51_causal_panel.v1",
        schema_id="https://kronos.local/schemas/kronos_daily_v51_causal_panel.v1.schema.json",
        validator=_validate_causal_panel_payload,
    ),
    V51RouteSpec(
        route_id="ACCOUNTING",
        rule="/accounting",
        endpoint="accounting",
        artifact_id=ACCOUNTING_ARTIFACT_ID,
        artifact_key="accounting",
        payload_schema_version="kronos_v51_slot_accounting.v1",
        schema_id="internal://stom_rl.v5_accounting/kronos_v51_slot_accounting.v1",
        validator=_validate_accounting_payload,
    ),
    V51RouteSpec(
        route_id="EVALUATOR",
        rule="/evaluator",
        endpoint="evaluator",
        artifact_id=EVALUATOR_ARTIFACT_ID,
        artifact_key="evaluator",
        payload_schema_version="kronos_daily_v51_evaluator.v1",
        schema_id="internal://stom_rl.daily_v51_evaluator/kronos_daily_v51_evaluator.v1",
        validator=_validate_evaluator_payload,
    ),
    V51RouteSpec(
        route_id="BENCHMARK_OVERLAY",
        rule="/benchmark-overlay",
        endpoint="benchmark_overlay",
        artifact_id=BENCHMARK_OVERLAY_ARTIFACT_ID,
        artifact_key="benchmark_overlay",
        payload_schema_version="kronos_v51_korean_index_overlay.v1",
        schema_id="internal://stom_rl.korean_index_overlay/kronos_v51_korean_index_overlay.v1",
        validator=_validate_benchmark_overlay_payload,
    ),
)
ROUTE_SPECS_BY_ID: Final = {spec.route_id: spec for spec in ROUTE_SPECS}


def create_v51_research_api_blueprint(
    *,
    artifact_provider: Any | None = None,
    artifact_dir: Path | str | None = None,
    report_catalog: Any | None = None,
    max_json_bytes: int = MAX_JSON_BYTES,
    name: str = "kronos_v51_research_api",
    url_prefix: str = "/api/daily-close-v51",
) -> Blueprint:
    """Create the additive read-only Daily Close V5.1 research API Blueprint.

    Tests may inject ``artifact_provider`` as a callable or object with
    ``read_json/read_artifact/read/get`` and may inject ``report_catalog`` as a
    ``ResearchReportCatalog``-compatible object.  Without injections, the default
    provider reads only exact allowlisted ``<artifact_id>.json`` files from
    ``artifact_dir`` or ``current_app.config[KRONOS_V51_ARTIFACT_DIR]``, and the
    report catalog indexes only pre-existing approved roots without creating
    directories.
    """

    max_bytes = _positive_max_bytes(max_json_bytes)
    provider = artifact_provider if artifact_provider is not None else ReadOnlyArtifactProvider(artifact_dir, max_bytes=max_bytes)
    reports = report_catalog if report_catalog is not None else _default_report_catalog()
    bp = Blueprint(name, __name__, url_prefix=url_prefix)

    def install(spec: V51RouteSpec) -> None:
        endpoint = spec.endpoint

        def handler() -> Response:
            if request.method != "GET":
                return _method_not_allowed_response(
                    _error_payload(spec, 405, "method not allowed", code="BAD_REQUEST", max_bytes=max_bytes),
                    max_bytes=max_bytes,
                )
            try:
                bindings = _validate_artifact_query_bindings(spec)
                try:
                    read = _read_artifact(provider, spec, max_bytes=max_bytes)
                    payload = _success_payload(read, spec, max_bytes=max_bytes)
                except (V51ArtifactUnavailable, V51ArtifactValidationError) as exc:
                    reason_code = getattr(exc, "reason_code", "ARTIFACT_INVALID")
                    payload = _blocked_payload(spec, reason_code=reason_code, message=str(exc), max_bytes=max_bytes)
                _enforce_artifact_query_bindings(bindings, payload)
                return _json_response(payload, max_bytes=max_bytes)
            except V51ResearchApiError as exc:
                return _json_response(
                    _error_payload(spec, exc.status_code, exc.message, code=exc.code, max_bytes=max_bytes),
                    exc.status_code,
                    max_bytes=max_bytes,
                )
            except Exception:  # noqa: BLE001 - fail closed without leaking filesystem/provider details.
                return _json_response(
                    _error_payload(spec, 503, "internal server error", code="INTERNAL_ERROR", max_bytes=max_bytes),
                    503,
                    max_bytes=max_bytes,
                )

        handler.__name__ = endpoint
        bp.add_url_rule(
            spec.rule,
            endpoint=endpoint,
            view_func=handler,
            methods=list(ALL_ROUTE_METHODS),
            provide_automatic_options=False,
        )


    def report_list_handler() -> Response:
        if request.method != "GET":
            return _method_not_allowed_response(
                _report_error_payload("REPORTS", 405, "method not allowed", code="BAD_REQUEST"),
                max_bytes=max_bytes,
            )
        try:
            _validate_empty_query_bindings()
            return _json_response(_report_list_payload(reports), max_bytes=max_bytes)
        except V51ResearchApiError as exc:
            return _json_response(
                _report_error_payload("REPORTS", exc.status_code, exc.message, code=exc.code),
                exc.status_code,
                max_bytes=max_bytes,
            )
        except Exception:  # noqa: BLE001 - fail closed without leaking report catalog details.
            return _json_response(
                _report_error_payload("REPORTS", 503, "internal server error", code="INTERNAL_ERROR"),
                503,
                max_bytes=max_bytes,
            )

    def report_read_handler(report_id: str) -> Response:
        if request.method != "GET":
            return _method_not_allowed_response(
                _report_error_payload("REPORT_READ", 405, "method not allowed", code="BAD_REQUEST"),
                max_bytes=max_bytes,
            )
        try:
            _validate_empty_query_bindings()
            return _json_response(_report_read_payload(reports, report_id), max_bytes=max_bytes)
        except V51ResearchApiError as exc:
            return _json_response(
                _report_error_payload("REPORT_READ", exc.status_code, exc.message, code=exc.code),
                exc.status_code,
                max_bytes=max_bytes,
            )
        except Exception:  # noqa: BLE001 - fail closed without leaking report catalog details.
            return _json_response(
                _report_error_payload("REPORT_READ", 503, "internal server error", code="INTERNAL_ERROR"),
                503,
                max_bytes=max_bytes,
            )

    bp.add_url_rule(
        "/reports",
        endpoint="reports",
        view_func=report_list_handler,
        methods=list(ALL_ROUTE_METHODS),
        provide_automatic_options=False,
    )
    bp.add_url_rule(
        "/reports/<report_id>",
        endpoint="report_read",
        view_func=report_read_handler,
        methods=list(ALL_ROUTE_METHODS),
        provide_automatic_options=False,
    )
    for route_spec in ROUTE_SPECS:
        install(route_spec)

    return bp


create_blueprint = create_v51_research_api_blueprint

__all__ = [
    "ALLOWED_ARTIFACT_IDS",
    "API_PROTOCOL_ID",
    "API_SCHEMA_VERSION",
    "MAX_JSON_BYTES",
    "ReadOnlyArtifactProvider",
    "ROUTE_SPECS",
    "ROUTE_SPECS_BY_ID",
    "V51_API_FALSE_LOCKS",
    "V51_RESEARCH_ARTIFACT_IDS",
    "V51_RESEARCH_CLAIMS",
    "canonical_json_bytes",
    "create_blueprint",
    "create_v51_research_api_blueprint",
]
