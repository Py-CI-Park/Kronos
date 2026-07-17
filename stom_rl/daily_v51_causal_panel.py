"""Pure V5.1 causal panel boundary built on exact 15:20 proxy marks.

The module is intentionally additive and side-effect free: callers provide already
loaded observation rows and exact 15:20 source rows, and receive a deterministic
JSON-compatible panel manifest.  It does not open databases, infer official
closes, use nearest-price fallbacks, or approximate amount as price times volume.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

SCHEMA_VERSION = "kronos_daily_v51_causal_panel.v1"
PRICE_BASIS = "15:20_bar_close_proxy"
CAUSAL_CUTOFF_KST = "15:20:00"
KST = timezone(timedelta(hours=9), "KST")
_FORBIDDEN_DAILY_SOURCE_SUFFIX = "_database/Stock_Database_ohlcv_1day.db"
_SOURCE_SCHEMA_VERSION = "kronos_daily_1520_source.v1"
_APPROVED_5MIN_SOURCE_SUFFIX = "_database/Stock_Database_ohlcv_5min.db"
_APPROVED_SOURCE_COLUMNS = ("date", "open", "high", "low", "close", "volume")
_COMPACT_1520_RE = re.compile(r"^\d{8}1520$")
_BARE_DAILY_OHLCV_FIELDS = frozenset({"open", "high", "low", "close", "volume", "amount"})

FORBIDDEN_DAILY_FIELDS = frozenset(
    {
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "future_return_1d",
        "future_direction_1d",
        "future_rank_pct_1d",
        "entry_close",
        "next_close",
        "daily_open",
        "daily_high",
        "daily_low",
        "daily_close",
        "daily_volume",
        "daily_amount",
        "final_open",
        "final_high",
        "final_low",
        "final_close",
        "final_volume",
        "final_amount",
        "full_day_open",
        "full_day_high",
        "full_day_low",
        "full_day_close",
        "full_day_volume",
        "full_day_amount",
        "one_day_open",
        "one_day_high",
        "one_day_low",
        "one_day_close",
        "one_day_volume",
        "one_day_amount",
        "ohlcv_1day_open",
        "ohlcv_1day_high",
        "ohlcv_1day_low",
        "ohlcv_1day_close",
        "ohlcv_1day_volume",
        "ohlcv_1day_amount",
    }
)

_FALSE_LOCK_NAMES = (
    "official_close",
    "full_day_daily_ohlcv",
    "live_trading",
    "profit_claim",
    "paper_trading",
    "broker_integration",
)
_OBSERVATION_TIMESTAMP_FIELDS = (
    "timestamp",
    "source_timestamp",
    "feature_timestamp",
    "event_timestamp",
    "bar_timestamp",
    "asof_timestamp",
)
_SOURCE_PATH_FIELDS = (
    "source_db_path",
    "db_path",
    "database_path",
    "database",
    "db",
    "source_database",
    "source_db",
    "source_path",
    "source_file",
    "source_uri",
)
_SOURCE_IDENTIFIER_FIELDS = ("source_table", "source_name", "lineage_source")
_SYMBOL_FIELDS = ("symbol", "code", "ticker")
_SESSION_FIELDS = ("session", "trading_session", "date")
_TIMESTAMP_FIELDS = ("timestamp", "timestamp_kst", "timestamp_yyyymmddhhmm", "source_timestamp", "bar_timestamp")
_CLOSE_FIELDS = ("close", "price", "close_1520", "price_1520", "price_1520_close_proxy")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_COMPACT_DATE_RE = re.compile(r"^\d{8}$")
_SYMBOL_RE = re.compile(r"^[0-9]{6}$")


class CausalPanelContractError(ValueError):
    """Raised when an input or panel violates the V5.1 causal-panel contract."""


@dataclass(frozen=True)
class _Observation:
    symbol: str
    session: str
    timestamp: datetime
    row: dict[str, Any]
    source_paths: tuple[str, ...]


@dataclass(frozen=True)
class _ExactMark:
    symbol: str
    session: str
    timestamp: datetime
    close: float
    row: dict[str, Any]
    source_paths: tuple[str, ...]
    source_table: str | None
    schema_version: str | None


@dataclass(frozen=True)
class _ExactIndex:
    marks: dict[tuple[str, str], _ExactMark]
    trading_sessions: tuple[str, ...]
    row_count: int
    source_paths: tuple[str, ...]
    source_tables: tuple[str, ...]
    schema_versions: tuple[str, ...]
    source_columns: tuple[str, ...]


def build_causal_panel(
    observation_rows: Sequence[Any],
    exact_1520_rows: Sequence[Any],
    *,
    horizon_days: Sequence[int] = (1, 3, 5),
    source_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic research-only causal panel.

    Observations must be same-session intraday rows whose source timestamps are
    at or before 15:20 KST.  Labels are derived only from exact 15:20 proxy rows:
    D and D+H must both have exact 15:20 marks in trading-session order.

    ``source_identity`` must be an explicit source-artifact identity with a
    non-null lowercase SHA-256 of the source DB; the builder does not derive or
    open the DB to fill missing identity.
    """

    horizons = _normalize_horizons(horizon_days)
    observations, observation_source_paths = _normalize_observations(observation_rows)
    exact_index = _normalize_exact_rows(exact_1520_rows)
    source_identity_payload = _normalize_source_identity(source_identity, exact_index)
    source_audit = _source_audit(exact_index)
    groups: dict[tuple[str, str], list[_Observation]] = defaultdict(list)
    for observation in observations:
        groups[(observation.symbol, observation.session)].append(observation)

    rows: list[dict[str, Any]] = []
    label_names = [_label_name(horizon) for horizon in horizons]
    label_coverage = {
        name: {"available": 0, "missing_entry": 0, "missing_exit": 0}
        for name in label_names
    }
    session_index = {session: index for index, session in enumerate(exact_index.trading_sessions)}

    for symbol, session in sorted(groups, key=lambda item: (item[0][1], item[0][0])):
        group = sorted(groups[(symbol, session)], key=lambda item: (item.timestamp, _canonical_json(item.row)))
        max_timestamp = max(item.timestamp for item in group)
        entry = exact_index.marks.get((symbol, session))
        labels: dict[str, float | None] = {}
        label_statuses: dict[str, dict[str, Any]] = {}
        exact_exit_rows: dict[str, dict[str, Any] | None] = {}

        for horizon in horizons:
            name = _label_name(horizon)
            value: float | None = None
            status = "missing_entry"
            exit_session: str | None = None
            exit_mark: _ExactMark | None = None
            if entry is not None:
                start_index = session_index.get(session)
                if start_index is None or start_index + horizon >= len(exact_index.trading_sessions):
                    status = "missing_exit"
                else:
                    exit_session = exact_index.trading_sessions[start_index + horizon]
                    exit_mark = exact_index.marks.get((symbol, exit_session))
                    if exit_mark is None:
                        status = "missing_exit"
                    else:
                        status = "available"
                        value = (exit_mark.close / entry.close) - 1.0
            labels[name] = value
            label_statuses[name] = {
                "status": status,
                "horizon_trading_sessions": horizon,
                "entry_session": session,
                "exit_session": exit_session,
                "entry_timestamp": _iso_kst(entry.timestamp) if entry is not None else None,
                "exit_timestamp": _iso_kst(exit_mark.timestamp) if exit_mark is not None else None,
                "official_close": False,
                "fallback_used": False,
            }
            exact_exit_rows[name] = exit_mark.row if exit_mark is not None else None
            label_coverage[name][status] += 1

        panel_row: dict[str, Any] = {
            "symbol": symbol,
            "session": session,
            "causal_cutoff_kst": CAUSAL_CUTOFF_KST,
            "cutoff": CAUSAL_CUTOFF_KST,
            "cutoff_timestamp": _iso_kst(_session_cutoff(session)),
            "max_observation_timestamp": _iso_kst(max_timestamp),
            "official_close": False,
            "observation_count": len(group),
            "observations": [item.row for item in group],
            "entry_1520_status": "available" if entry is not None else "missing_entry",
            "entry_1520": entry.row if entry is not None else None,
            "exit_1520_by_label": exact_exit_rows,
            "labels": labels,
            "label_statuses": label_statuses,
        }
        for name, value in labels.items():
            panel_row[name] = value
        rows.append(panel_row)

    panel: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "official_close": False,
        "price_basis": PRICE_BASIS,
        "causal_cutoff_kst": CAUSAL_CUTOFF_KST,
        "cutoff": CAUSAL_CUTOFF_KST,
        "horizon_days": list(horizons),
        "label_columns": label_names,
        "fallback_policy": "none_exact_1520_only_nearest_forbidden",
        "amount_policy": "no_price_times_volume_approximation_only_verified_source_fields",
        "source_identity": source_identity_payload,
        "forbidden_daily_fields": sorted(FORBIDDEN_DAILY_FIELDS),
        "forbidden_observation_source_suffix": _FORBIDDEN_DAILY_SOURCE_SUFFIX,
        "locks": {name: False for name in _FALSE_LOCK_NAMES},
        "promotion_claims": {
            "live_trading": False,
            "profit": False,
            "paper_trading": False,
            "broker_integration": False,
        },
        "contract": {
            "proxy_1520_not_official_close": True,
            "official_close": False,
            "no_nearest_fallback": True,
            "no_full_day_daily_ohlcv": True,
            "no_legacy_future_return_1d": True,
            "no_price_volume_amount_approximation": True,
            "trading_session_order_labels": True,
        },
        "audit": {
            "observation_sources": {
                "allowed": sorted(observation_source_paths),
                "forbidden": [],
                "rejected": [],
            },
            "observation_field_policy": {
                "forbidden_daily_fields": sorted(FORBIDDEN_DAILY_FIELDS),
                "legacy_future_return_1d_allowed": False,
            },
            "exact_1520_source": {
                "row_count": exact_index.row_count,
                "source_db_paths": list(exact_index.source_paths),
                "source_tables": list(exact_index.source_tables),
                "schema_versions": list(exact_index.schema_versions),
                "source_columns": list(exact_index.source_columns),
                "price_basis": PRICE_BASIS,
                "official_close": False,
            },
            "source_audit": source_audit,
            "source_identity_present": True,
        },
        "coverage": {
            "observation_row_count": len(observations),
            "panel_row_count": len(rows),
            "exact_1520_row_count": exact_index.row_count,
            "symbol_count": len({row[0] for row in groups}),
            "session_count": len(exact_index.trading_sessions),
            "trading_sessions": list(exact_index.trading_sessions),
            "labels": label_coverage,
        },
        "rows": rows,
    }
    panel["panel_sha256"] = _panel_digest(panel)
    validate_causal_panel(panel)
    return panel


def validate_causal_panel(panel: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate a panel produced by :func:`build_causal_panel`.

    The validator is deterministic: it recomputes the canonical panel SHA-256 and
    fails closed when rows, audits, or contract flags are mutated.
    """

    if not isinstance(panel, Mapping):
        raise CausalPanelContractError("causal panel must be a mapping")
    if panel.get("schema_version") != SCHEMA_VERSION:
        raise CausalPanelContractError("causal panel schema_version mismatch")
    if panel.get("official_close") is not False:
        raise CausalPanelContractError("causal panel must declare official_close=false")
    if panel.get("price_basis") != PRICE_BASIS:
        raise CausalPanelContractError("causal panel price_basis must be 15:20 proxy")
    if panel.get("causal_cutoff_kst") != CAUSAL_CUTOFF_KST:
        raise CausalPanelContractError("causal panel cutoff must be 15:20 KST")

    horizons = _normalize_horizons(panel.get("horizon_days", ()))
    expected_labels = [_label_name(horizon) for horizon in horizons]
    if panel.get("label_columns") != expected_labels:
        raise CausalPanelContractError("causal panel label_columns are not deterministic horizon labels")

    locks = panel.get("locks")
    if not isinstance(locks, Mapping) or set(locks) != set(_FALSE_LOCK_NAMES):
        raise CausalPanelContractError("causal panel must expose exactly six false locks")
    if any(value is not False for value in locks.values()):
        raise CausalPanelContractError("causal panel locks must all be false")
    claims = panel.get("promotion_claims")
    if not isinstance(claims, Mapping) or any(value is not False for value in claims.values()):
        raise CausalPanelContractError("causal panel must not make live/profit/paper/broker claims")
    contract = panel.get("contract")
    required_true_contracts = (
        "proxy_1520_not_official_close",
        "no_nearest_fallback",
        "no_full_day_daily_ohlcv",
        "no_legacy_future_return_1d",
        "no_price_volume_amount_approximation",
        "trading_session_order_labels",
    )
    if not isinstance(contract, Mapping) or contract.get("official_close") is not False:
        raise CausalPanelContractError("causal panel contract must declare official_close=false")
    if any(contract.get(name) is not True for name in required_true_contracts):
        raise CausalPanelContractError("causal panel contract guardrail flags must all be true")

    source_identity_payload = panel.get("source_identity")
    if not isinstance(source_identity_payload, Mapping):
        raise CausalPanelContractError("causal panel source_identity must be a non-null mapping")
    expected_source_identity_keys = {
        "schema_version",
        "identity_basis",
        "source_db_path",
        "source_db_paths",
        "source_db_sha256",
        "source_tables",
        "schema_versions",
        "source_columns",
        "exact_1520_row_count",
        "source_identity_sha256",
    }
    if set(source_identity_payload) != expected_source_identity_keys:
        raise CausalPanelContractError("causal panel source_identity keys mismatch")
    if source_identity_payload.get("schema_version") != _SOURCE_SCHEMA_VERSION:
        raise CausalPanelContractError("causal panel source_identity schema_version mismatch")
    if source_identity_payload.get("identity_basis") != "explicit":
        raise CausalPanelContractError("causal panel source_identity basis must be explicit")
    _require_approved_source_path(source_identity_payload.get("source_db_path"), "source_identity source_db_path")
    if source_identity_payload.get("source_db_paths") != [source_identity_payload.get("source_db_path")]:
        raise CausalPanelContractError("source_identity source_db_paths must match source_db_path")
    source_db_sha256 = source_identity_payload.get("source_db_sha256")
    if not isinstance(source_db_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", source_db_sha256) is None:
        raise CausalPanelContractError("source_identity source_db_sha256 must be explicit lowercase sha256")
    for table in _coerce_string_sequence(source_identity_payload.get("source_tables")):
        _require_approved_source_table(table, "source_identity source_table")
    if source_identity_payload.get("schema_versions") != [_SOURCE_SCHEMA_VERSION]:
        raise CausalPanelContractError("source_identity schema_versions mismatch")
    if tuple(_coerce_string_sequence(source_identity_payload.get("source_columns"))) != _APPROVED_SOURCE_COLUMNS:
        raise CausalPanelContractError("source_identity source_columns mismatch")
    identity_payload_without_digest = {
        str(key): source_identity_payload[key]
        for key in source_identity_payload
        if key != "source_identity_sha256"
    }
    expected_identity_digest = hashlib.sha256(_canonical_json(identity_payload_without_digest).encode("utf-8")).hexdigest()
    if source_identity_payload.get("source_identity_sha256") != expected_identity_digest:
        raise CausalPanelContractError("source_identity digest mismatch")

    audit = panel.get("audit")
    if not isinstance(audit, Mapping):
        raise CausalPanelContractError("causal panel audit must be present")
    observation_audit = audit.get("observation_sources")
    if not isinstance(observation_audit, Mapping):
        raise CausalPanelContractError("causal panel observation source audit must be present")
    if observation_audit.get("forbidden") != [] or observation_audit.get("rejected") != []:
        raise CausalPanelContractError("causal panel contains forbidden or rejected observation sources")
    allowed_sources = observation_audit.get("allowed")
    if not isinstance(allowed_sources, list) or allowed_sources != sorted(allowed_sources):
        raise CausalPanelContractError("allowed observation sources must be sorted deterministically")
    for source in allowed_sources:
        _require_approved_causal_source_identifier(source, "allowed observation source")
    exact_source_audit = audit.get("exact_1520_source")
    if not isinstance(exact_source_audit, Mapping):
        raise CausalPanelContractError("causal panel exact source audit must be present")
    if exact_source_audit.get("row_count") != source_identity_payload.get("exact_1520_row_count"):
        raise CausalPanelContractError("exact source audit row_count must match source_identity")
    if exact_source_audit.get("source_db_paths") != source_identity_payload.get("source_db_paths"):
        raise CausalPanelContractError("exact source audit paths must match source_identity")
    if exact_source_audit.get("source_tables") != source_identity_payload.get("source_tables"):
        raise CausalPanelContractError("exact source audit tables must match source_identity")
    if exact_source_audit.get("schema_versions") != [_SOURCE_SCHEMA_VERSION]:
        raise CausalPanelContractError("exact source audit schema_versions mismatch")
    if tuple(_coerce_string_sequence(exact_source_audit.get("source_columns"))) != tuple(sorted(_APPROVED_SOURCE_COLUMNS)):
        raise CausalPanelContractError("exact source audit source_columns mismatch")
    if exact_source_audit.get("price_basis") != PRICE_BASIS or exact_source_audit.get("official_close") is not False:
        raise CausalPanelContractError("exact source audit must remain 15:20 proxy only")
    declared_source_audit = audit.get("source_audit")
    if not isinstance(declared_source_audit, Mapping):
        raise CausalPanelContractError("causal panel source_audit must be present")
    if declared_source_audit.get("approved_source_db_paths") != exact_source_audit.get("source_db_paths"):
        raise CausalPanelContractError("source_audit approved paths mismatch")
    if declared_source_audit.get("approved_source_tables") != exact_source_audit.get("source_tables"):
        raise CausalPanelContractError("source_audit approved tables mismatch")
    if declared_source_audit.get("approved_schema_versions") != [_SOURCE_SCHEMA_VERSION]:
        raise CausalPanelContractError("source_audit approved schema versions mismatch")
    if tuple(_coerce_string_sequence(declared_source_audit.get("approved_source_columns"))) != tuple(sorted(_APPROVED_SOURCE_COLUMNS)):
        raise CausalPanelContractError("source_audit approved source columns mismatch")
    if (
        declared_source_audit.get("rejected_source_db_paths") != []
        or declared_source_audit.get("rejected_source_tables") != []
        or declared_source_audit.get("forbidden_sources") != []
    ):
        raise CausalPanelContractError("source_audit rejected and forbidden encounters must be empty")
    if audit.get("source_identity_present") is not True:
        raise CausalPanelContractError("source_identity_present must be true")

    rows = panel.get("rows")
    if not isinstance(rows, list):
        raise CausalPanelContractError("causal panel rows must be a list")
    expected_order = sorted(
        ((_require_panel_symbol(row), _require_panel_session(row)) for row in rows),
        key=lambda item: (item[1], item[0]),
    )
    actual_order = [(_require_panel_symbol(row), _require_panel_session(row)) for row in rows]
    if actual_order != expected_order:
        raise CausalPanelContractError("causal panel rows must be sorted by session then symbol")

    coverage_counts = {
        name: {"available": 0, "missing_entry": 0, "missing_exit": 0}
        for name in expected_labels
    }
    observation_count = 0
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise CausalPanelContractError(f"causal panel row {index} must be a mapping")
        if row.get("official_close") is not False:
            raise CausalPanelContractError(f"causal panel row {index} must declare official_close=false")
        symbol = _require_panel_symbol(row)
        session = _require_panel_session(row)
        cutoff = _session_cutoff(session)
        max_timestamp = _parse_timestamp(row.get("max_observation_timestamp"), f"row {index} max_observation_timestamp")
        if max_timestamp.date() != cutoff.date() or max_timestamp > cutoff:
            raise CausalPanelContractError(f"row {index} max observation timestamp violates 15:20 cutoff")
        if row.get("causal_cutoff_kst") != CAUSAL_CUTOFF_KST:
            raise CausalPanelContractError(f"row {index} cutoff must be 15:20 KST")
        observations = row.get("observations")
        if not isinstance(observations, list) or not observations:
            raise CausalPanelContractError(f"row {index} observations must be a non-empty list")
        observation_count += len(observations)
        observed_max_timestamp: datetime | None = None
        for observation in observations:
            if not isinstance(observation, Mapping):
                raise CausalPanelContractError(f"row {index} observation must be a mapping")
            _reject_forbidden_fields(observation, f"row {index} observation", allow_exact_ohlcv=False)
            _reject_nested_observation_values(observation, f"row {index} observation")
            observation_sources = tuple(sorted(set(_source_paths(observation)) | set(_source_identifiers(observation))))
            if not observation_sources:
                raise CausalPanelContractError(f"row {index} observation must declare approved exact 15:20 source")
            for source in observation_sources:
                _require_approved_causal_source_identifier(source, f"row {index} observation source")
            if _require_symbol(_first_present(observation, _SYMBOL_FIELDS), f"row {index} observation symbol") != symbol:
                raise CausalPanelContractError(f"row {index} observation symbol mismatch")
            if _normalize_session(
                _first_present(observation, _SESSION_FIELDS),
                fallback_timestamp=max_timestamp,
                label=f"row {index} observation session",
            ) != session:
                raise CausalPanelContractError(f"row {index} observation session mismatch")
            observation_timestamp = _parse_timestamp(observation.get("timestamp"), f"row {index} observation timestamp")
            _enforce_same_session_cutoff(observation_timestamp, session, label=f"row {index} observation timestamp")
            max_source_timestamp = _parse_timestamp(
                observation.get("max_source_timestamp"),
                f"row {index} observation max_source_timestamp",
            )
            _enforce_same_session_cutoff(
                max_source_timestamp,
                session,
                label=f"row {index} observation max_source_timestamp",
            )
            if max_source_timestamp < observation_timestamp:
                raise CausalPanelContractError(f"row {index} observation max_source_timestamp precedes timestamp")
            if observed_max_timestamp is None or max_source_timestamp > observed_max_timestamp:
                observed_max_timestamp = max_source_timestamp
        if observed_max_timestamp != max_timestamp:
            raise CausalPanelContractError(f"row {index} max observation timestamp is not the observation maximum")

        labels = row.get("labels")
        statuses = row.get("label_statuses")
        if not isinstance(labels, Mapping) or not isinstance(statuses, Mapping):
            raise CausalPanelContractError(f"row {index} labels and statuses must be mappings")
        if set(labels) != set(expected_labels) or set(statuses) != set(expected_labels):
            raise CausalPanelContractError(f"row {index} label keys mismatch")

        entry_status = row.get("entry_1520_status")
        entry_payload = row.get("entry_1520")
        if entry_status not in {"available", "missing_entry"}:
            raise CausalPanelContractError(f"row {index} entry_1520_status is invalid")
        entry_close: float | None = None
        entry_timestamp: datetime | None = None
        if entry_status == "available":
            entry_close = _validate_exact_payload(
                entry_payload,
                allow_none=False,
                label=f"row {index} entry_1520",
                expected_symbol=symbol,
                expected_source_db_path=str(source_identity_payload["source_db_path"]),
            )
            if _require_symbol(entry_payload.get("symbol"), f"row {index} entry_1520 symbol") != symbol:
                raise CausalPanelContractError(f"row {index} entry_1520 symbol mismatch")
            entry_session = _normalize_session(
                entry_payload.get("session"),
                fallback_timestamp=None,
                label=f"row {index} entry_1520 session",
            )
            if entry_session != session:
                raise CausalPanelContractError(f"row {index} entry_1520 session mismatch")
            entry_timestamp = _parse_timestamp(entry_payload.get("timestamp"), f"row {index} entry_1520 timestamp")
        elif entry_payload is not None:
            raise CausalPanelContractError(f"row {index} missing entry status cannot carry entry_1520 payload")

        exits = row.get("exit_1520_by_label")
        if not isinstance(exits, Mapping) or set(exits) != set(expected_labels):
            raise CausalPanelContractError(f"row {index} exit_1520_by_label keys mismatch")

        for name in expected_labels:
            if name not in row:
                raise CausalPanelContractError(f"row {index} missing top-level {name}")
            if row[name] != labels[name]:
                raise CausalPanelContractError(f"row {index} top-level {name} differs from labels map")
            status_payload = statuses[name]
            if not isinstance(status_payload, Mapping):
                raise CausalPanelContractError(f"row {index} label status for {name} must be a mapping")
            status = status_payload.get("status")
            if status not in coverage_counts[name]:
                raise CausalPanelContractError(f"row {index} label {name} has invalid status")
            if status == "available" and labels[name] is None:
                raise CausalPanelContractError(f"row {index} label {name} is available but missing")
            if status != "available" and labels[name] is not None:
                raise CausalPanelContractError(f"row {index} label {name} has value despite missing exact mark")
            if status_payload.get("official_close") is not False or status_payload.get("fallback_used") is not False:
                raise CausalPanelContractError(f"row {index} label {name} must be proxy-only with no fallback")
            if status_payload.get("entry_session") != session:
                raise CausalPanelContractError(f"row {index} label {name} entry_session mismatch")

            exit_payload = exits[name]
            if status == "available":
                if entry_status != "available" or entry_close is None or entry_timestamp is None:
                    raise CausalPanelContractError(f"row {index} label {name} is available without entry_1520 payload")
                exit_close = _validate_exact_payload(
                    exit_payload,
                    allow_none=False,
                    label=f"row {index} exit {name}",
                    expected_symbol=symbol,
                    expected_source_db_path=str(source_identity_payload["source_db_path"]),
                )
                if _require_symbol(exit_payload.get("symbol"), f"row {index} exit {name} symbol") != symbol:
                    raise CausalPanelContractError(f"row {index} exit {name} symbol mismatch")
                exit_session = _normalize_session(
                    exit_payload.get("session"),
                    fallback_timestamp=None,
                    label=f"row {index} exit {name} session",
                )
                if status_payload.get("exit_session") != exit_session:
                    raise CausalPanelContractError(f"row {index} label {name} exit_session mismatch")
                exit_timestamp = _parse_timestamp(exit_payload.get("timestamp"), f"row {index} exit {name} timestamp")
                if status_payload.get("entry_timestamp") != _iso_kst(entry_timestamp):
                    raise CausalPanelContractError(f"row {index} label {name} entry_timestamp mismatch")
                if status_payload.get("exit_timestamp") != _iso_kst(exit_timestamp):
                    raise CausalPanelContractError(f"row {index} label {name} exit_timestamp mismatch")
                expected_return = (exit_close / entry_close) - 1.0
                label_value = _finite_float(labels[name], f"row {index} label {name}")
                if label_value != expected_return:
                    raise CausalPanelContractError(f"row {index} label {name} does not match exact 15:20 closes")
            else:
                if exit_payload is not None:
                    raise CausalPanelContractError(f"row {index} label {name} is missing but carries exit_1520 payload")
                if status == "missing_entry":
                    if entry_status != "missing_entry":
                        raise CausalPanelContractError(f"row {index} label {name} missing_entry disagrees with entry status")
                    if status_payload.get("entry_timestamp") is not None or status_payload.get("exit_timestamp") is not None:
                        raise CausalPanelContractError(f"row {index} label {name} missing_entry timestamps must be null")
                    if status_payload.get("exit_session") is not None:
                        raise CausalPanelContractError(f"row {index} label {name} missing_entry exit_session must be null")
                elif status == "missing_exit":
                    if entry_status != "available" or entry_timestamp is None:
                        raise CausalPanelContractError(f"row {index} label {name} missing_exit requires entry_1520 payload")
                    if status_payload.get("entry_timestamp") != _iso_kst(entry_timestamp):
                        raise CausalPanelContractError(f"row {index} label {name} entry_timestamp mismatch")
                    if status_payload.get("exit_timestamp") is not None:
                        raise CausalPanelContractError(f"row {index} label {name} missing_exit exit_timestamp must be null")
            coverage_counts[name][status] += 1
        if "future_return_1d" in row:
            raise CausalPanelContractError("legacy future_return_1d is forbidden in causal panel rows")

    coverage = panel.get("coverage")
    if not isinstance(coverage, Mapping):
        raise CausalPanelContractError("causal panel coverage must be present")
    if coverage.get("observation_row_count") != observation_count:
        raise CausalPanelContractError("causal panel observation coverage mismatch")
    if coverage.get("panel_row_count") != len(rows):
        raise CausalPanelContractError("causal panel row coverage mismatch")
    if coverage.get("labels") != coverage_counts:
        raise CausalPanelContractError("causal panel label coverage mismatch")

    expected_sha = _panel_digest(panel)
    if panel.get("panel_sha256") != expected_sha:
        raise CausalPanelContractError("causal panel panel_sha256 does not match deterministic contents")
    return panel


def _normalize_horizons(horizon_days: Sequence[int] | Any) -> tuple[int, ...]:
    if isinstance(horizon_days, (str, bytes)) or not isinstance(horizon_days, Iterable):
        raise CausalPanelContractError("horizon_days must be a sequence of positive integers")
    result: list[int] = []
    for value in horizon_days:
        if isinstance(value, bool):
            raise CausalPanelContractError("horizon_days values must be positive integers")
        try:
            horizon = int(value)
        except (TypeError, ValueError) as exc:
            raise CausalPanelContractError("horizon_days values must be positive integers") from exc
        if horizon <= 0 or horizon != value and not (isinstance(value, str) and value.isdigit()):
            raise CausalPanelContractError("horizon_days values must be positive integers")
        if horizon in result:
            raise CausalPanelContractError("horizon_days values must be unique")
        result.append(horizon)
    if not result:
        raise CausalPanelContractError("horizon_days must not be empty")
    return tuple(result)


def _normalize_observations(rows: Sequence[Any]) -> tuple[list[_Observation], set[str]]:
    observations: list[_Observation] = []
    allowed_sources: set[str] = set()
    for index, raw_row in enumerate(_as_sequence(rows, "observation_rows")):
        label = f"observation row {index}"
        row = _row_mapping(raw_row, label)
        _reject_forbidden_fields(row, label, allow_exact_ohlcv=False)
        _reject_nested_observation_values(row, label)
        if _present(row.get("official_close")) and _coerce_bool(row.get("official_close"), f"{label} official_close"):
            raise CausalPanelContractError(f"{label} cannot be an official close source")
        source_identifiers = tuple(sorted(set(_source_paths(row)) | set(_source_identifiers(row))))
        if not source_identifiers:
            raise CausalPanelContractError(f"{label} must declare an approved exact 15:20 source")
        for source in source_identifiers:
            _require_approved_causal_source_identifier(source, f"{label} source")
        allowed_sources.update(source_identifiers)
        timestamp_fields = [field for field in _OBSERVATION_TIMESTAMP_FIELDS if _present(row.get(field))]
        if not timestamp_fields:
            raise CausalPanelContractError(f"{label} missing observation source timestamp")
        primary_timestamp = _parse_timestamp(row[timestamp_fields[0]], f"{label} {timestamp_fields[0]}")
        symbol = _require_symbol(_first_present(row, _SYMBOL_FIELDS), f"{label} symbol")
        session = _normalize_session(
            _first_present(row, _SESSION_FIELDS),
            fallback_timestamp=primary_timestamp,
            label=f"{label} session",
        )
        max_timestamp = primary_timestamp
        for field in timestamp_fields:
            timestamp = _parse_timestamp(row[field], f"{label} {field}")
            _enforce_same_session_cutoff(timestamp, session, label=f"{label} {field}")
            if timestamp > max_timestamp:
                max_timestamp = timestamp
        cleaned = _jsonable(row)
        cleaned["symbol"] = symbol
        cleaned["session"] = session
        cleaned["timestamp"] = _iso_kst(primary_timestamp)
        cleaned["max_source_timestamp"] = _iso_kst(max_timestamp)
        observations.append(
            _Observation(
                symbol=symbol,
                session=session,
                timestamp=max_timestamp,
                row=cleaned,
                source_paths=source_identifiers,
            )
        )
    return observations, allowed_sources


def _normalize_exact_rows(rows: Sequence[Any]) -> _ExactIndex:
    marks: dict[tuple[str, str], _ExactMark] = {}
    source_paths: set[str] = set()
    source_tables: set[str] = set()
    schema_versions: set[str] = set()
    source_columns: set[str] = set()
    trading_sessions_seen: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    row_count = 0
    for index, raw_row in enumerate(_as_sequence(rows, "exact_1520_rows")):
        row_count += 1
        label = f"exact_1520 row {index}"
        row = _row_mapping(raw_row, label)
        _reject_forbidden_fields(row, label, allow_exact_ohlcv=True)
        symbol = _require_symbol(_first_present(row, _SYMBOL_FIELDS), f"{label} symbol")
        timestamp_value = _first_present(row, _TIMESTAMP_FIELDS)
        timestamp = _parse_timestamp(timestamp_value, f"{label} timestamp")
        session = _normalize_session(
            _first_present(row, _SESSION_FIELDS),
            fallback_timestamp=timestamp,
            label=f"{label} session",
        )
        _enforce_exact_1520(timestamp, session, label=label)
        if row.get("official_close") is not False:
            raise CausalPanelContractError(f"{label} must explicitly declare official_close=false")
        if row.get("price_basis") != PRICE_BASIS:
            raise CausalPanelContractError(f"{label} price_basis must be {PRICE_BASIS}")
        close = _finite_float(_first_present(row, _CLOSE_FIELDS), f"{label} close")
        if close <= 0:
            raise CausalPanelContractError(f"{label} close must be positive")
        paths = _source_paths(row)
        if not paths:
            raise CausalPanelContractError(f"{label} must declare approved exact 15:20 source_db_path")
        for path in paths:
            _require_approved_source_path(path, f"{label} source_db_path")
        source_paths.update(paths)
        source_table = _optional_string(row.get("source_table") or row.get("table"))
        if source_table is None:
            raise CausalPanelContractError(f"{label} must declare approved exact 15:20 source_table")
        _require_approved_source_table(source_table, f"{label} source_table")
        if source_table != f"A{symbol}":
            raise CausalPanelContractError(f"{label} source_table must match symbol A{symbol}")
        source_tables.add(source_table)
        schema_version = _optional_string(row.get("schema_version"))
        if schema_version != _SOURCE_SCHEMA_VERSION:
            raise CausalPanelContractError(f"{label} schema_version must be {_SOURCE_SCHEMA_VERSION}")
        schema_versions.add(schema_version)
        source_columns_tuple = tuple(_coerce_string_sequence(row.get("source_columns")))
        if source_columns_tuple != _APPROVED_SOURCE_COLUMNS:
            raise CausalPanelContractError(f"{label} source_columns must be {list(_APPROVED_SOURCE_COLUMNS)}")
        source_columns.update(source_columns_tuple)
        key = (symbol, session)
        if key in seen_keys:
            raise CausalPanelContractError(f"duplicate exact 15:20 mark for {symbol} {session}")
        seen_keys.add(key)
        trading_sessions_seen.add(session)
        if not _exact_mark_available(row):
            continue
        cleaned = _sanitize_exact_mark(row, symbol=symbol, session=session, timestamp=timestamp, close=close)
        marks[key] = _ExactMark(
            symbol=symbol,
            session=session,
            timestamp=timestamp,
            close=close,
            row=cleaned,
            source_paths=tuple(sorted(paths)),
            source_table=source_table,
            schema_version=schema_version,
        )
    trading_sessions = tuple(sorted(trading_sessions_seen))
    return _ExactIndex(
        marks=marks,
        trading_sessions=trading_sessions,
        row_count=row_count,
        source_paths=tuple(sorted(source_paths)),
        source_tables=tuple(sorted(source_tables)),
        schema_versions=tuple(sorted(schema_versions)),
        source_columns=tuple(sorted(source_columns)),
    )


def _source_audit(exact_index: _ExactIndex) -> dict[str, Any]:
    return {
        "approved_source_db_paths": list(exact_index.source_paths),
        "approved_source_tables": list(exact_index.source_tables),
        "approved_schema_versions": list(exact_index.schema_versions),
        "approved_source_columns": list(exact_index.source_columns),
        "rejected_source_db_paths": [],
        "rejected_source_tables": [],
        "forbidden_sources": [],
    }


def _normalize_source_identity(source_identity: Mapping[str, Any] | None, exact_index: _ExactIndex) -> dict[str, Any]:
    if len(exact_index.source_paths) != 1:
        raise CausalPanelContractError("source_identity requires exactly one approved exact 15:20 source_db_path")
    source_db_path = exact_index.source_paths[0]
    _require_approved_source_path(source_db_path, "source_identity source_db_path")
    if not exact_index.source_tables:
        raise CausalPanelContractError("source_identity requires at least one approved source_table")
    for table in exact_index.source_tables:
        _require_approved_source_table(table, "source_identity source_table")
    if exact_index.schema_versions != (_SOURCE_SCHEMA_VERSION,):
        raise CausalPanelContractError("source_identity requires kronos_daily_1520_source.v1 exact rows")
    if exact_index.source_columns != tuple(sorted(_APPROVED_SOURCE_COLUMNS)):
        raise CausalPanelContractError("source_identity requires approved 5-minute source columns")

    if source_identity is None or not isinstance(source_identity, Mapping):
        raise CausalPanelContractError("source_identity with explicit source_db_sha256 is required")
    provided = {str(key): value for key, value in source_identity.items()}
    allowed_keys = {
        "schema_version",
        "identity_basis",
        "source_db_path",
        "source_db_paths",
        "source_db_sha256",
        "source_table",
        "source_tables",
        "source_columns",
    }
    unexpected = sorted(set(provided) - allowed_keys)
    if unexpected:
        raise CausalPanelContractError(f"source_identity contains unexpected key: {unexpected[0]}")
    if provided.get("identity_basis", "explicit") != "explicit":
        raise CausalPanelContractError("source_identity identity_basis must be explicit")
    if provided.get("schema_version") != _SOURCE_SCHEMA_VERSION:
        raise CausalPanelContractError(f"source_identity schema_version must be {_SOURCE_SCHEMA_VERSION}")
    provided_paths = _coerce_string_sequence(provided.get("source_db_paths") or provided.get("source_db_path"))
    if tuple(sorted(provided_paths)) != exact_index.source_paths:
        raise CausalPanelContractError("source_identity source_db_path must match exact 15:20 rows")
    provided_tables = _coerce_string_sequence(provided.get("source_tables") or provided.get("source_table"))
    if provided_tables and tuple(sorted(provided_tables)) != exact_index.source_tables:
        raise CausalPanelContractError("source_identity source_tables must match exact 15:20 rows")
    provided_columns = _coerce_string_sequence(provided.get("source_columns"))
    if provided_columns and tuple(provided_columns) != _APPROVED_SOURCE_COLUMNS:
        raise CausalPanelContractError("source_identity source_columns must match approved 5-minute source columns")
    source_db_sha256 = provided.get("source_db_sha256")
    if not isinstance(source_db_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", source_db_sha256) is None:
        raise CausalPanelContractError("source_identity source_db_sha256 must be explicit lowercase sha256")
    identity_basis = "explicit"

    payload: dict[str, Any] = {
        "schema_version": _SOURCE_SCHEMA_VERSION,
        "identity_basis": identity_basis,
        "source_db_path": source_db_path,
        "source_db_paths": list(exact_index.source_paths),
        "source_db_sha256": source_db_sha256,
        "source_tables": list(exact_index.source_tables),
        "schema_versions": list(exact_index.schema_versions),
        "source_columns": list(_APPROVED_SOURCE_COLUMNS),
        "exact_1520_row_count": exact_index.row_count,
    }
    payload["source_identity_sha256"] = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return payload


def _exact_mark_available(row: Mapping[str, Any]) -> bool:
    return row.get("tradable") is True and not _has_exclusion_reason(row.get("exclusion_reason"))


def _has_exclusion_reason(value: Any) -> bool:
    return _present(value) and str(value).strip() != ""


def _sanitize_exact_mark(
    row: Mapping[str, Any],
    *,
    symbol: str,
    session: str,
    timestamp: datetime,
    close: float,
) -> dict[str, Any]:
    cleaned: dict[str, Any] = {
        "symbol": symbol,
        "session": session,
        "timestamp": _iso_kst(timestamp),
        "date": session,
        "session_date": session,
        "timestamp_kst": _iso_kst(timestamp),
        "timestamp_yyyymmddhhmm": _compact_1520_timestamp_string(timestamp),
        "close": close,
        "price": close,
        "price_basis": PRICE_BASIS,
        "official_close": False,
    }
    for name in ("open", "high", "low", "price_1520_close_proxy"):
        if _present(row.get(name)):
            cleaned[name] = _finite_float(row.get(name), f"exact 1520 {symbol} {session} {name}")
    if _present(row.get("bar_volume_1520")):
        cleaned["bar_volume_1520"] = _finite_float(row.get("bar_volume_1520"), f"exact 1520 {symbol} {session} bar_volume_1520")
    for name in (
        "date",
        "session_date",
        "timestamp_kst",
        "timestamp_yyyymmddhhmm",
        "table",
        "bar_volume_status",
        "volume_to_1520",
        "volume_to_1520_status",
        "cumulative_volume_status",
        "cumulative_volume_to_1520",
        "cumulative_volume_to_1520_status",
        "amount_status",
        "amount_to_1520",
        "amount_to_1520_status",
        "tradable",
        "exclusion_reason",
        "source_db_path",
        "source_table",
        "schema_version",
        "causal_cutoff_kst",
        "source_timestamp_column",
        "source_price_column",
        "source_volume_column",
    ):
        if name in row:
            cleaned[name] = _jsonable(row.get(name))
    if "source_columns" in row:
        cleaned["source_columns"] = _coerce_string_sequence(row.get("source_columns"))
    if "source_table" in cleaned and "table" not in cleaned:
        cleaned["table"] = cleaned["source_table"]
    if "table" in cleaned and "source_table" not in cleaned:
        cleaned["source_table"] = cleaned["table"]
    cleaned["timestamp_yyyymmddhhmm"] = _compact_1520_timestamp_string(row.get("timestamp_yyyymmddhhmm", timestamp))

    cumulative_status = str(row.get("cumulative_volume_status") or "").lower()
    if cumulative_status == "verified" and _present(row.get("cumulative_volume_1520")):
        cleaned["cumulative_volume_1520"] = _finite_float(
            row.get("cumulative_volume_1520"), f"exact 1520 {symbol} {session} cumulative_volume_1520"
        )
    amount_status = str(row.get("amount_status") or "").lower()
    for amount_field in ("amount_1520", "cumulative_amount_1520"):
        if amount_status == "verified" and _present(row.get(amount_field)):
            cleaned[amount_field] = _finite_float(row.get(amount_field), f"exact 1520 {symbol} {session} {amount_field}")
    return cleaned


def _as_sequence(rows: Iterable[Any], label: str) -> list[Any]:
    if isinstance(rows, (str, bytes, Mapping)) or not isinstance(rows, Iterable):
        raise CausalPanelContractError(f"{label} must be an iterable of rows")
    return list(rows)


def _row_mapping(row: Any, label: str) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    if is_dataclass(row):
        return asdict(row)
    if hasattr(row, "_asdict"):
        value = row._asdict()
        if isinstance(value, Mapping):
            return dict(value)
    if hasattr(row, "__dict__"):
        return {key: value for key, value in vars(row).items() if not key.startswith("_")}
    slots = getattr(type(row), "__slots__", ())
    if isinstance(slots, str):
        slots = (slots,)
    if slots:
        return {key: getattr(row, key) for key in slots if not key.startswith("_") and hasattr(row, key)}
    raise CausalPanelContractError(f"{label} must be a mapping, dataclass, namedtuple, or simple object")


def _reject_forbidden_fields(row: Mapping[str, Any], label: str, *, allow_exact_ohlcv: bool) -> None:
    forbidden = sorted(key for key in row if _is_forbidden_field_name(str(key), allow_exact_ohlcv=allow_exact_ohlcv))
    if forbidden:
        if "future_return_1d" in forbidden:
            raise CausalPanelContractError(f"{label} includes forbidden legacy future_return_1d label")
        raise CausalPanelContractError(f"{label} includes forbidden daily OHLCV field: {forbidden[0]}")


def _is_forbidden_field_name(name: str, *, allow_exact_ohlcv: bool = False) -> bool:
    lower = name.lower()
    if lower in _BARE_DAILY_OHLCV_FIELDS:
        return lower == "amount" or not allow_exact_ohlcv
    if lower in FORBIDDEN_DAILY_FIELDS:
        return True
    if lower == "future_return_1d":
        return True
    if lower.startswith("future_return_"):
        return True
    if "ohlcv_1day" in lower or "ohlcv_1d" in lower or "one_day" in lower:
        return True
    if lower.startswith(("daily_", "final_", "final_daily_", "full_day_", "one_day_")) and any(
        token in lower for token in ("open", "high", "low", "close", "volume", "amount")
    ):
        return True
    if lower.endswith(("_daily_open", "_daily_high", "_daily_low", "_daily_close", "_daily_volume", "_daily_amount")):
        return True
    return False


def _source_paths(row: Mapping[str, Any]) -> tuple[str, ...]:
    paths: set[str] = set()
    for field in _SOURCE_PATH_FIELDS:
        value = row.get(field)
        if not _present(value):
            continue
        if isinstance(value, (list, tuple, set)):
            for item in value:
                if _present(item):
                    paths.add(str(item))
        else:
            paths.add(str(value))
    return tuple(sorted(paths))

def _source_identifiers(row: Mapping[str, Any]) -> tuple[str, ...]:
    identifiers: set[str] = set()
    for field in _SOURCE_IDENTIFIER_FIELDS:
        value = row.get(field)
        if _present(value):
            identifiers.add(str(value))
    return tuple(sorted(identifiers))



def _is_forbidden_source_path(value: Any) -> bool:
    normalized = str(value).strip().replace("\\", "/").lower()
    return (
        normalized.endswith(_FORBIDDEN_DAILY_SOURCE_SUFFIX.lower())
        or "ohlcv_1day" in normalized
        or "ohlcv_1d" in normalized
        or "naver" in normalized
        or "unknown" in normalized
        or normalized.startswith(("http://", "https://"))
        or normalized == "stock_database_ohlcv_1day"
    )


def _is_approved_source_path(value: Any) -> bool:
    normalized = str(value).strip().replace("\\", "/")
    return normalized.endswith(_APPROVED_5MIN_SOURCE_SUFFIX) and not _is_forbidden_source_path(value)


def _require_approved_source_path(value: Any, label: str) -> str:
    if not _present(value) or not _is_approved_source_path(value):
        raise CausalPanelContractError(f"{label} must be an approved exact 15:20 5-minute source path")
    return str(value)


def _require_approved_source_table(value: Any, label: str) -> str:
    table = str(value).strip()
    if re.fullmatch(r"A[0-9]{6}", table) is None:
        raise CausalPanelContractError(f"{label} must be an approved A-prefixed 5-minute source table")
    return table


def _require_approved_causal_source_identifier(value: Any, label: str) -> str:
    text = str(value).strip()
    if _is_forbidden_source_path(text):
        raise CausalPanelContractError(f"{label} uses forbidden or unapproved causal source: {text}")
    if _is_approved_source_path(text):
        return text
    if re.fullmatch(r"A[0-9]{6}", text):
        return text
    raise CausalPanelContractError(f"{label} must be an approved exact 15:20 5-minute source path/table")


def _reject_nested_observation_values(row: Mapping[str, Any], label: str) -> None:
    for key, value in row.items():
        if isinstance(value, Mapping) or isinstance(value, (list, tuple, set)):
            raise CausalPanelContractError(f"{label} field {key} must be a scalar causal feature")


def _first_present(row: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        value = row.get(name)
        if _present(value):
            return value
    return None


def _present(value: Any) -> bool:
    return value is not None and value != ""


def _require_symbol(value: Any, label: str) -> str:
    if not _present(value):
        raise CausalPanelContractError(f"{label} is required")
    if not isinstance(value, str):
        raise CausalPanelContractError(f"{label} must be a six-digit numeric KRX stock symbol")
    symbol = value.strip()
    if not _SYMBOL_RE.fullmatch(symbol):
        raise CausalPanelContractError(f"{label} must be a six-digit numeric KRX stock symbol")
    return symbol


def _normalize_session(value: Any, *, fallback_timestamp: datetime | None, label: str) -> str:
    if not _present(value):
        if fallback_timestamp is None:
            raise CausalPanelContractError(f"{label} is required")
        return fallback_timestamp.date().isoformat()
    if isinstance(value, datetime):
        return _to_kst(value).date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if _DATE_RE.fullmatch(text):
        return text
    if _COMPACT_DATE_RE.fullmatch(text):
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    try:
        return _parse_timestamp(text, label).date().isoformat()
    except CausalPanelContractError as exc:
        raise CausalPanelContractError(f"{label} must be an ISO trading session date") from exc


def _parse_timestamp(value: Any, label: str) -> datetime:
    if isinstance(value, datetime):
        return _to_kst(value)
    if isinstance(value, date):
        raise CausalPanelContractError(f"{label} must include intraday time")
    if not _present(value):
        raise CausalPanelContractError(f"{label} is required")
    text = str(value).strip()
    if _DATE_RE.fullmatch(text) or _COMPACT_DATE_RE.fullmatch(text):
        raise CausalPanelContractError(f"{label} must include intraday time")
    text = text.replace(" KST", "").replace("KST", "")
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    compact = text.replace("-", "").replace(":", "").replace("T", "").replace(" ", "")
    if _COMPACT_DATE_RE.fullmatch(compact):
        raise CausalPanelContractError(f"{label} must include intraday time")
    if re.fullmatch(r"\d{14}", compact):
        return datetime.strptime(compact, "%Y%m%d%H%M%S").replace(tzinfo=KST)
    if re.fullmatch(r"\d{12}", compact):
        return datetime.strptime(compact, "%Y%m%d%H%M").replace(tzinfo=KST)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0 and parsed.microsecond == 0 and "T" not in text and " " not in text:
            raise CausalPanelContractError(f"{label} must include intraday time")
        return _to_kst(parsed)
    for pattern in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=KST)
        except ValueError:
            continue
    raise CausalPanelContractError(f"{label} must be an ISO timestamp")


def _to_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)


def _session_cutoff(session: str) -> datetime:
    return datetime.combine(date.fromisoformat(session), time(15, 20), tzinfo=KST)


def _enforce_same_session_cutoff(timestamp: datetime, session: str, *, label: str) -> None:
    cutoff = _session_cutoff(session)
    if timestamp.date() != cutoff.date():
        raise CausalPanelContractError(f"{label} is not from the same trading session")
    if timestamp > cutoff:
        raise CausalPanelContractError(f"{label} is post-cutoff; observation timestamps must be <= 15:20 KST")


def _enforce_exact_1520(timestamp: datetime, session: str, *, label: str) -> None:
    cutoff = _session_cutoff(session)
    if timestamp != cutoff:
        raise CausalPanelContractError(f"{label} is not an exact same-session 15:20 mark")


def _coerce_bool(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"false", "0", "no", "n"}:
            return False
        if lowered in {"true", "1", "yes", "y"}:
            return True
    raise CausalPanelContractError(f"{label} must be boolean")


def _finite_float(value: Any, label: str) -> float:
    if isinstance(value, bool) or not _present(value):
        raise CausalPanelContractError(f"{label} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise CausalPanelContractError(f"{label} must be numeric") from exc
    if not math.isfinite(number):
        raise CausalPanelContractError(f"{label} must be finite")
    return number


def _optional_string(value: Any) -> str | None:
    if not _present(value):
        return None
    return str(value)


def _coerce_string_sequence(value: Any) -> list[str]:
    if not _present(value):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return [str(value)]


def _label_name(horizon: int) -> str:
    return f"future_return_h{horizon}_1520_proxy"


def _iso_kst(value: datetime) -> str:
    return _to_kst(value).replace(microsecond=0).isoformat()


def _compact_1520_timestamp_string(value: Any) -> str:
    if isinstance(value, datetime):
        timestamp = _to_kst(value)
    else:
        timestamp = _parse_timestamp(value, "compact timestamp")
    text = timestamp.strftime("%Y%m%d%H%M")
    if _COMPACT_1520_RE.fullmatch(text) is None:
        raise CausalPanelContractError(f"compact timestamp must match YYYYMMDD1520, got {value!r}")
    return text


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(value[key]) for key in sorted(value, key=lambda item: str(item))}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return [_jsonable(item) for item in sorted(value, key=lambda item: str(item))]
    if isinstance(value, datetime):
        return _iso_kst(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _panel_digest(panel: Mapping[str, Any]) -> str:
    payload = {str(key): value for key, value in panel.items() if key != "panel_sha256"}
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _require_panel_symbol(row: Mapping[str, Any]) -> str:
    return _require_symbol(row.get("symbol"), "panel row symbol")


def _require_panel_session(row: Mapping[str, Any]) -> str:
    return _normalize_session(row.get("session"), fallback_timestamp=None, label="panel row session")


def _validate_exact_payload(
    payload: Any,
    *,
    allow_none: bool,
    label: str,
    expected_symbol: str | None = None,
    expected_source_db_path: str | None = None,
) -> float | None:
    if payload is None and allow_none:
        return None
    if not isinstance(payload, Mapping):
        raise CausalPanelContractError(f"{label} must be a mapping")
    _reject_forbidden_fields(payload, label, allow_exact_ohlcv=True)
    symbol = _require_symbol(payload.get("symbol"), f"{label} symbol")
    if expected_symbol is not None and symbol != expected_symbol:
        raise CausalPanelContractError(f"{label} symbol mismatch")
    session = _normalize_session(payload.get("session"), fallback_timestamp=None, label=f"{label} session")
    timestamp = _parse_timestamp(payload.get("timestamp"), f"{label} timestamp")
    _enforce_exact_1520(timestamp, session, label=label)
    if not _present(payload.get("timestamp_yyyymmddhhmm")):
        raise CausalPanelContractError(f"{label} compact timestamp is required")
    if not isinstance(payload.get("timestamp_yyyymmddhhmm"), str):
        raise CausalPanelContractError(f"{label} compact timestamp must be a JSON string")
    if _compact_1520_timestamp_string(payload.get("timestamp_yyyymmddhhmm")) != timestamp.strftime("%Y%m%d%H%M"):
        raise CausalPanelContractError(f"{label} compact timestamp must match exact 15:20 timestamp")
    _require_approved_source_path(payload.get("source_db_path"), f"{label} source_db_path")
    if expected_source_db_path is not None and payload.get("source_db_path") != expected_source_db_path:
        raise CausalPanelContractError(f"{label} source_db_path must match panel source_identity")
    source_table = _require_approved_source_table(payload.get("source_table"), f"{label} source_table")
    expected_table = f"A{expected_symbol or symbol}"
    if source_table != expected_table:
        raise CausalPanelContractError(f"{label} source_table must match symbol {expected_table}")
    table = _require_approved_source_table(payload.get("table"), f"{label} table")
    if table != source_table:
        raise CausalPanelContractError(f"{label} table must match source_table")
    if payload.get("schema_version") != _SOURCE_SCHEMA_VERSION:
        raise CausalPanelContractError(f"{label} schema_version must be {_SOURCE_SCHEMA_VERSION}")
    if payload.get("causal_cutoff_kst") != CAUSAL_CUTOFF_KST:
        raise CausalPanelContractError(f"{label} causal_cutoff_kst must be 15:20:00")
    if tuple(_coerce_string_sequence(payload.get("source_columns"))) != _APPROVED_SOURCE_COLUMNS:
        raise CausalPanelContractError(f"{label} source_columns must be approved 5-minute columns")
    if payload.get("official_close") is not False:
        raise CausalPanelContractError(f"{label} must declare official_close=false")
    if payload.get("price_basis") != PRICE_BASIS:
        raise CausalPanelContractError(f"{label} must keep 15:20 proxy price_basis")
    if payload.get("tradable") is not True:
        raise CausalPanelContractError(f"{label} must declare tradable=true")
    if _has_exclusion_reason(payload.get("exclusion_reason")):
        raise CausalPanelContractError(f"{label} must not carry an exclusion_reason")
    close = _finite_float(payload.get("close"), f"{label} close")
    if close <= 0:
        raise CausalPanelContractError(f"{label} close must be positive")
    if _present(payload.get("price")) and _finite_float(payload.get("price"), f"{label} price") != close:
        raise CausalPanelContractError(f"{label} price must match close")
    if _present(payload.get("price_1520_close_proxy")) and _finite_float(
        payload.get("price_1520_close_proxy"),
        f"{label} price_1520_close_proxy",
    ) != close:
        raise CausalPanelContractError(f"{label} price_1520_close_proxy must match close")
    return close
