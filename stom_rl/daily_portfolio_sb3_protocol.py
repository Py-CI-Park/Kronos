"""Immutable Kronos V5 daily Portfolio SB3 protocol foundation.

This module builds and verifies a closed, research-only protocol description.  It
never opens OOS data, trains a model, imports SB3, or writes artifacts; dependent
runner/state/evaluator slices must consume the protocol bytes and fail closed on
any drift.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Final, Mapping, Sequence

import rfc8785


PROTOCOL_SCHEMA: Final = "kronos_daily_sb3_protocol.v1"
PROTOCOL_SCHEMA_ID: Final = "https://kronos.local/schemas/kronos_daily_sb3_protocol.v1.schema.json"
COMMAND_MANIFEST_SCHEMA: Final = "kronos_dashboard_v5_runner_command_manifest.v1"
PROTOCOL_VERSION: Final = "2026-07-15.g008.immutable.v1"
IDENTITY_ALGORITHM: Final = "SHA256_RFC8785_STATEMENT_V1"
CELL_IDENTITY_ALGORITHM: Final = "SHA256_RFC8785_CELL_BASIS_V1"
SYNTHETIC_COMPUTE_MODE: Final = "synthetic_verification_only"
NO_HEAVY_COMPUTE_MARKER: Final = "NO_TRAINING_NO_SB3_LEARN_NO_FRESH_OOS_READ"

SEEDS: Final = (
    {"seed_id": "seed-01", "value": 7},
    {"seed_id": "seed-02", "value": 17},
    {"seed_id": "seed-03", "value": 29},
    {"seed_id": "seed-04", "value": 41},
    {"seed_id": "seed-05", "value": 53},
)
FOLD_IDS: Final = ("fold-01", "fold-02")
VARIANT_IDS: Final = ("baseline", "cost-00bp", "cost-23bp", "cost-46bp", "no-trade")
ALIAS_VARIANT_IDS: Final = frozenset(
    {
        "0bp",
        "00bp",
        "23bp",
        "46bp",
        "base",
        "base_23bp",
        "cost23",
        "no_trade",
        "notrade",
        "stress_46bp",
        "zero_control_0bp",
    }
)
EVALUATION_COSTS_BPS: Final = (0, 23, 46)
PRIMARY_COST_BPS: Final = 23

_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_DATE_RE: Final = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_CODE_RE: Final = re.compile(r"\d{6}\Z")
_REPO_ROOT: Final = Path(__file__).resolve().parents[1]
_CLOSED_METADATA: Final = {
    "schema": "kronos_daily_sb3_protocol_closed_metadata.v1",
    "semantic_runtime_validator_required": True,
    "semantic_runtime_validator": "stom_rl.daily_portfolio_sb3_protocol.validate_protocol",
    "validates_exact_train_counts_and_date_arrays": True,
    "validates_dependency_paths_sha256_byte_length": True,
    "validates_available_sessions_exact": True,
}
_APPROVED_EXECUTABLE_COMMANDS: Final = (
    (
        "emit-canonical-protocol-json",
        [
            "py",
            "-3.11",
            "-m",
            "stom_rl.daily_portfolio_sb3_protocol",
            "--emit-protocol",
            "--synthetic-verification-only",
            "--no-heavy-compute",
        ],
    ),
    (
        "emit-protocol-fixture-summary",
        [
            "py",
            "-3.11",
            "-m",
            "stom_rl.daily_portfolio_sb3_protocol",
            "--emit-fixture-summary",
            "--synthetic-verification-only",
            "--no-heavy-compute",
        ],
    ),
)
_APPROVED_PASS_RECEIPT_COMMANDS: Final = (
    ("protocol", "not-run-protocol-synthetic-receipt", ["NOT_RUN_SYNTHETIC_RECEIPT", "protocol"]),
    ("runner", "not-run-runner-synthetic-receipt", ["NOT_RUN_SYNTHETIC_RECEIPT", "runner"]),
    ("evaluator", "not-run-evaluator-synthetic-receipt", ["NOT_RUN_SYNTHETIC_RECEIPT", "evaluator"]),
)


TRAIN_HOLIDAYS: Final = frozenset(
    {
        "2025-06-03",
        "2025-06-06",
        "2025-08-15",
        "2025-10-03",
        "2025-10-06",
        "2025-10-07",
        "2025-10-08",
        "2025-10-09",
        "2025-10-10",
        "2025-12-25",
        "2025-12-31",
    }
)
VALIDATION_HOLIDAYS: Final = frozenset({"2026-02-16", "2026-02-17", "2026-02-18", "2026-03-02"})
HISTORICAL_HOLIDAYS: Final = frozenset({"2026-05-01", "2026-05-05", "2026-05-25", "2026-06-03"})

FOLD1_TRAIN_COUNT: Final = 104
BOUNDARY_BLOCKED_COUNT: Final = 5
FOLD_EVAL_COUNT: Final = 47

DEFAULT_DEPENDENCIES: Final = (
    {
        "name": "kronos_v5_daily_accounting_adr",
        "uri": "docs/kronos_v5_daily_accounting_adr_2026-07-14.md",
        "sha256": "75f3f8b3fa8262e778b45fcf4c7794aa7cc335fc3153727dd555570516f31d93",
        "byte_length": 3029,
        "role": "accounting_cost_horizon_authority",
    },
    {
        "name": "stom_daily_sb3_prior_stop_result",
        "uri": "docs/stom_daily_sb3_ppo_result_2026-07-12.md",
        "sha256": "6311e97a3561a7b55ff09925999cd75babfcacbbba08011c3b9474bf34191045",
        "byte_length": 5840,
        "role": "prior_protocol_gap_and_stop_authority",
    },
    {
        "name": "kronos_research_runbook",
        "uri": "docs/kronos_research_runbook_2026-07-10.md",
        "sha256": "155e85c0ecec209b2c3ba61f7964f040991942a55bf5e7e00cdcc997a942e6ff",
        "byte_length": 8243,
        "role": "research_boundary_and_seed_source",
    },
)

COST_SCENARIOS: Final = (
    {
        "scenario_id": "zero_control_0bp",
        "total_bp": 0,
        "buy_commission_bp": 0,
        "buy_slippage_bp": 0,
        "sell_commission_bp": 0,
        "sell_tax_bp": 0,
        "sell_slippage_bp": 0,
    },
    {
        "scenario_id": "base_23bp",
        "total_bp": 23,
        "buy_commission_bp": 1.5,
        "buy_slippage_bp": 0,
        "sell_commission_bp": 1.5,
        "sell_tax_bp": 20,
        "sell_slippage_bp": 0,
    },
    {
        "scenario_id": "stress_46bp",
        "total_bp": 46,
        "buy_commission_bp": 1.5,
        "buy_slippage_bp": 11.5,
        "sell_commission_bp": 1.5,
        "sell_tax_bp": 20,
        "sell_slippage_bp": 11.5,
    },
)

DEFAULT_PPO_CONFIG: Final = {
    "algorithm": "ppo",
    "stable_baselines_family": "PPO",
    "total_timesteps_per_seed_fold": 200_000,
    "device_requested": "auto",
    "n_steps": 256,
    "batch_size": 64,
    "n_epochs": 4,
    "top_k_candidates": 3,
    "max_positions": 2,
    "initial_cash_krw": 1_000_000,
    "buy_fraction": 0.25,
    "invalid_action_penalty": 0.001,
    "turnover_penalty_lambda": 0.001,
    "max_eval_steps": 512,
    "eval_callback_frequency_steps": 10_000,
    "fold_seed_semantics": "same_base_seed_in_every_fold_no_plus_fold_index",
}

DEFAULT_FEATURE_NORMALIZATION: Final = {
    "schema": "kronos_daily_sb3_feature_normalization.v1",
    "method": "TRAIN_FOLD_ONLY_ZSCORE",
    "fit_scope": "fold_train_sessions_only",
    "apply_scope": "validation_and_historical_secondary_without_refit",
    "missing_value_policy": "impute_train_mean_then_z0",
    "std_zero_policy": "std_zero_or_missing_maps_to_z0",
    "clip_z_min": -8,
    "clip_z_max": 8,
    "causal_feature_columns": [
        "rank_score",
        "feature_score_supervised_linear_ranker",
        "feature_score_equal_weight_topk_momentum",
        "feature_return_1d",
        "feature_return_5d",
        "feature_volatility_5d",
        "feature_volume_ratio_5d",
    ],
    "forbidden_feature_prefixes": ["future_", "label_", "target_"],
    "label_columns": ["future_return_1d"],
}

COMPARATOR_ORDER: Final = (
    "no_trade_cash",
    "shuffle_control",
    "equal_weight_topk_momentum",
    "ts_imb_rule_baseline",
    "buy_and_hold_cash",
    "ppo_policy",
)

STOP_RULES: Final = (
    {"code": "MISSING_SESSION", "phase": "protocol_builder", "severity": "BLOCK", "convenience_stop": False},
    {"code": "LABEL_LEAKAGE_PAST_FIT", "phase": "protocol_builder", "severity": "BLOCK", "convenience_stop": False},
    {"code": "ALIAS_VARIANT", "phase": "protocol_builder", "severity": "BLOCK", "convenience_stop": False},
    {"code": "PROTOCOL_DRIFT", "phase": "protocol_builder", "severity": "BLOCK", "convenience_stop": False},
    {"code": "NONCANONICAL_CODE_OR_HASH", "phase": "protocol_builder", "severity": "BLOCK", "convenience_stop": False},
    {"code": "FRESH_OOS_ACCESS_REQUESTED", "phase": "protocol_builder", "severity": "BLOCK", "convenience_stop": False},
    {"code": "UNSUPPORTED_COMPUTE", "phase": "protocol_builder", "severity": "BLOCK", "convenience_stop": False},
    {"code": "D0_PRICE_BASIS_NOT_VERIFIED", "phase": "prerequisite", "severity": "BLOCK", "convenience_stop": False},
    {"code": "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED", "phase": "prerequisite", "severity": "BLOCK", "convenience_stop": False},
    {"code": "FRESH_OOS_NOT_RUN", "phase": "custody", "severity": "BLOCK", "convenience_stop": False},
    {"code": "NAN_OR_INF_METRIC", "phase": "future_runner", "severity": "STOP", "convenience_stop": False},
    {"code": "INVALID_ACTION_RATE_ABOVE_0_05", "phase": "future_runner", "severity": "STOP", "threshold": 0.05, "convenience_stop": False},
)

DEFAULT_CODES: Final = ("000250", "005930", "035420")


class DailySb3ProtocolError(ValueError):
    """Raised when the immutable protocol cannot be built or verified."""


def canonical_bytes(value: Any) -> bytes:
    """Return RFC 8785/JCS bytes without applying input normalization."""
    try:
        return rfc8785.dumps(value)
    except Exception as exc:  # pragma: no cover - exact exception type is library-specific.
        raise DailySb3ProtocolError("value is not RFC 8785 canonicalizable") from exc


def sha256_hex(value: bytes | Any) -> str:
    raw = value if isinstance(value, bytes) else canonical_bytes(value)
    return hashlib.sha256(raw).hexdigest()


def _business_sessions(start: str, end: str, holidays: set[str] | frozenset[str]) -> tuple[str, ...]:
    current = date.fromisoformat(start)
    final = date.fromisoformat(end)
    sessions: list[str] = []
    while current <= final:
        iso = current.isoformat()
        if current.weekday() < 5 and iso not in holidays:
            sessions.append(iso)
        current += timedelta(days=1)
    return tuple(sessions)


TRAIN_SESSIONS: Final = _business_sessions("2025-05-20", "2026-01-07", TRAIN_HOLIDAYS)
FOLD2_PURGE_EMBARGO_SESSIONS: Final = _business_sessions("2026-01-08", "2026-01-14", frozenset())
VALIDATION_SESSIONS: Final = _business_sessions("2026-01-15", "2026-03-26", VALIDATION_HOLIDAYS)
HISTORICAL_PURGE_EMBARGO_SESSIONS: Final = _business_sessions("2026-03-27", "2026-04-02", frozenset())
HISTORICAL_SECONDARY_ONLY_SESSIONS: Final = _business_sessions("2026-04-03", "2026-06-12", HISTORICAL_HOLIDAYS)
FOLD1_TRAIN_SESSIONS: Final = TRAIN_SESSIONS[:FOLD1_TRAIN_COUNT]
FOLD1_PURGE_EMBARGO_SESSIONS: Final = TRAIN_SESSIONS[FOLD1_TRAIN_COUNT : FOLD1_TRAIN_COUNT + BOUNDARY_BLOCKED_COUNT]
FOLD1_VALIDATION_SESSIONS: Final = TRAIN_SESSIONS[FOLD1_TRAIN_COUNT + BOUNDARY_BLOCKED_COUNT :]
ALL_REQUIRED_SESSIONS: Final = tuple(
    dict.fromkeys(
        (
            *TRAIN_SESSIONS,
            *FOLD2_PURGE_EMBARGO_SESSIONS,
            *VALIDATION_SESSIONS,
            *HISTORICAL_PURGE_EMBARGO_SESSIONS,
            *HISTORICAL_SECONDARY_ONLY_SESSIONS,
        )
    )
)


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise DailySb3ProtocolError(f"{label} is not a canonical lower-case SHA-256 digest")
    return value


def _require_date(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        raise DailySb3ProtocolError(f"{label} is not an ISO date")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise DailySb3ProtocolError(f"{label} is not a real date") from exc
    return value


def _require_code(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _CODE_RE.fullmatch(value):
        raise DailySb3ProtocolError(f"{label} is not a canonical zero-padded six-digit code string")
    return value

def _repo_local_dependency_path(uri: Any, label: str) -> Path:
    if not isinstance(uri, str) or not uri:
        raise DailySb3ProtocolError(f"{label} uri is not a repository-local path")
    if "://" in uri or "\\" in uri or uri.startswith("/") or re.match(r"^[A-Za-z]:", uri):
        raise DailySb3ProtocolError(f"{label} uri is not a repository-local path")
    relative = Path(uri)
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise DailySb3ProtocolError(f"{label} uri contains non-canonical path segments")
    path = (_REPO_ROOT / relative).resolve()
    try:
        path.relative_to(_REPO_ROOT)
    except ValueError as exc:
        raise DailySb3ProtocolError(f"{label} uri escapes the repository root") from exc
    if not path.is_file():
        raise DailySb3ProtocolError(f"{label} dependency path does not exist")
    return path


def _validate_dependency_bytes(ref: Mapping[str, Any], label: str) -> None:
    path = _repo_local_dependency_path(ref["uri"], label)
    raw = path.read_bytes()
    actual_sha256 = sha256_hex(raw)
    actual_byte_length = len(raw)
    if ref["sha256"] != actual_sha256 or ref["byte_length"] != actual_byte_length:
        raise DailySb3ProtocolError(f"{label} dependency bytes drifted from the frozen sha256/byte_length")



def _folds() -> tuple[dict[str, Any], ...]:
    return (
        {
            "fold_id": "fold-01",
            "train_sessions": list(FOLD1_TRAIN_SESSIONS),
            "fit_start_session": FOLD1_TRAIN_SESSIONS[0],
            "fit_end_session": FOLD1_TRAIN_SESSIONS[-1],
            "purge_embargo_sessions": list(FOLD1_PURGE_EMBARGO_SESSIONS),
            "validation_sessions": list(FOLD1_VALIDATION_SESSIONS),
            "validation_start_session": FOLD1_VALIDATION_SESSIONS[0],
            "validation_end_session": FOLD1_VALIDATION_SESSIONS[-1],
            "train_session_count": len(FOLD1_TRAIN_SESSIONS),
            "purge_embargo_session_count": len(FOLD1_PURGE_EMBARGO_SESSIONS),
            "validation_session_count": len(FOLD1_VALIDATION_SESSIONS),
            "fit_label_max_session": FOLD1_TRAIN_SESSIONS[-1],
        },
        {
            "fold_id": "fold-02",
            "train_sessions": list(TRAIN_SESSIONS),
            "fit_start_session": TRAIN_SESSIONS[0],
            "fit_end_session": TRAIN_SESSIONS[-1],
            "purge_embargo_sessions": list(FOLD2_PURGE_EMBARGO_SESSIONS),
            "validation_sessions": list(VALIDATION_SESSIONS),
            "validation_start_session": VALIDATION_SESSIONS[0],
            "validation_end_session": VALIDATION_SESSIONS[-1],
            "train_session_count": len(TRAIN_SESSIONS),
            "purge_embargo_session_count": len(FOLD2_PURGE_EMBARGO_SESSIONS),
            "validation_session_count": len(VALIDATION_SESSIONS),
            "fit_label_max_session": TRAIN_SESSIONS[-1],
        },
    )


def _variant_defs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "variant_id": "baseline",
            "role": "ppo_primary_baseline",
            "trains_policy": False,
            "evaluation_cost_bps": 23,
            "cost_scenario_id": "base_23bp",
            "notes": "Synthetic protocol card for the primary PPO baseline; future runner must train only after prerequisites are verified.",
        },
        {
            "variant_id": "cost-00bp",
            "role": "evaluation_cost_control",
            "trains_policy": False,
            "evaluation_cost_bps": 0,
            "cost_scenario_id": "zero_control_0bp",
            "notes": "Evaluation-only 0bp control; no retuning against this control.",
        },
        {
            "variant_id": "cost-23bp",
            "role": "primary_cost_evaluation",
            "trains_policy": False,
            "evaluation_cost_bps": 23,
            "cost_scenario_id": "base_23bp",
            "notes": "Primary 23bp accounting card.",
        },
        {
            "variant_id": "cost-46bp",
            "role": "stress_cost_evaluation",
            "trains_policy": False,
            "evaluation_cost_bps": 46,
            "cost_scenario_id": "stress_46bp",
            "notes": "Stress 46bp accounting card; no retuning against this control.",
        },
        {
            "variant_id": "no-trade",
            "role": "comparator_no_trade_cash",
            "trains_policy": False,
            "evaluation_cost_bps": 23,
            "cost_scenario_id": "base_23bp",
            "notes": "No-trade comparator projected into every seed/fold slot for exact 50-cell matrix accounting.",
        },
    )


def _default_label_fit_max_by_fold() -> dict[str, str]:
    return {fold["fold_id"]: fold["fit_end_session"] for fold in _folds()}


def _default_historical_window() -> dict[str, Any]:
    return {
        "window_id": "historical-secondary-only-2026-04-03-2026-06-12",
        "label": "historical_test_oos_secondary_only",
        "usage": "SECONDARY_DIAGNOSTIC_ONLY_NOT_MODEL_SELECTION_NOT_PROMOTION",
        "sessions": list(HISTORICAL_SECONDARY_ONLY_SESSIONS),
        "start_session": HISTORICAL_SECONDARY_ONLY_SESSIONS[0],
        "end_session": HISTORICAL_SECONDARY_ONLY_SESSIONS[-1],
        "session_count": len(HISTORICAL_SECONDARY_ONLY_SESSIONS),
        "pre_access_purge_embargo_sessions": list(HISTORICAL_PURGE_EMBARGO_SESSIONS),
        "fresh_oos_access_allowed": False,
        "fresh_oos_consumed": False,
        "model_go_source": False,
    }


def _assert_default_lengths() -> None:
    expected = {
        "train": (TRAIN_SESSIONS, 156),
        "fold1_train": (FOLD1_TRAIN_SESSIONS, 104),
        "fold1_purge_embargo": (FOLD1_PURGE_EMBARGO_SESSIONS, 5),
        "fold1_validation": (FOLD1_VALIDATION_SESSIONS, 47),
        "fold2_purge_embargo": (FOLD2_PURGE_EMBARGO_SESSIONS, 5),
        "validation": (VALIDATION_SESSIONS, 47),
        "historical_purge_embargo": (HISTORICAL_PURGE_EMBARGO_SESSIONS, 5),
        "historical_secondary": (HISTORICAL_SECONDARY_ONLY_SESSIONS, 47),
        "all_required": (ALL_REQUIRED_SESSIONS, 260),
    }
    for label, (values, count) in expected.items():
        if len(values) != count:
            raise DailySb3ProtocolError(f"{label} session count drifted from {count} to {len(values)}")


def _validate_variants(variants: Sequence[str] | None) -> tuple[str, ...]:
    if variants is None:
        return VARIANT_IDS
    observed = tuple(str(value) for value in variants)
    aliases = [value for value in observed if value in ALIAS_VARIANT_IDS]
    if aliases:
        raise DailySb3ProtocolError(f"Alias variants are forbidden: {aliases}")
    if len(set(observed)) != len(observed):
        raise DailySb3ProtocolError("Variant list contains duplicates")
    if observed != VARIANT_IDS:
        raise DailySb3ProtocolError("Variant order or cardinality drifted from the immutable protocol")
    return observed


def _validate_dependencies(dependency_refs: Sequence[Mapping[str, Any]] | None) -> tuple[dict[str, Any], ...]:
    refs = tuple(dict(item) for item in (DEFAULT_DEPENDENCIES if dependency_refs is None else dependency_refs))
    for index, ref in enumerate(refs):
        label = f"dependency {ref.get('name', index)}"
        if set(ref) != {"name", "uri", "sha256", "byte_length", "role"}:
            raise DailySb3ProtocolError(f"dependency {index} has an invalid shape")
        if not isinstance(ref["name"], str) or not ref["name"] or not isinstance(ref["role"], str) or not ref["role"]:
            raise DailySb3ProtocolError(f"{label} name/role is invalid")
        _require_sha(ref["sha256"], f"{label} sha256")
        if not isinstance(ref["byte_length"], int) or isinstance(ref["byte_length"], bool) or ref["byte_length"] <= 0:
            raise DailySb3ProtocolError(f"{label} byte_length is invalid")
        _validate_dependency_bytes(ref, label)
    if refs != DEFAULT_DEPENDENCIES:
        raise DailySb3ProtocolError("Dependency refs drifted from the immutable protocol")
    return refs



def _validate_codes(candidate_codes: Sequence[Any] | None) -> tuple[str, ...]:
    codes = tuple(DEFAULT_CODES if candidate_codes is None else candidate_codes)
    if not codes:
        raise DailySb3ProtocolError("At least one canonical code sample is required")
    return tuple(_require_code(value, f"candidate code {index}") for index, value in enumerate(codes))


def _validate_available_sessions(available_sessions: Sequence[str] | None) -> tuple[str, ...]:
    sessions = tuple(ALL_REQUIRED_SESSIONS if available_sessions is None else available_sessions)
    canonical = tuple(_require_date(value, f"available session {index}") for index, value in enumerate(sessions))
    if tuple(sorted(set(canonical))) != canonical:
        raise DailySb3ProtocolError("Available sessions must be unique and sorted ascending")
    if canonical != ALL_REQUIRED_SESSIONS:
        expected = set(ALL_REQUIRED_SESSIONS)
        observed = set(canonical)
        missing = [session for session in ALL_REQUIRED_SESSIONS if session not in observed]
        extra = [session for session in canonical if session not in expected]
        raise DailySb3ProtocolError(f"Available sessions drifted from the exact frozen KRX list; missing={missing[:3]} extra={extra[:3]}")
    return canonical



def _validate_label_fit_max(label_fit_max_by_fold: Mapping[str, str] | None) -> dict[str, str]:
    values = dict(_default_label_fit_max_by_fold() if label_fit_max_by_fold is None else label_fit_max_by_fold)
    fold_map = {fold["fold_id"]: fold for fold in _folds()}
    if set(values) != set(fold_map):
        raise DailySb3ProtocolError("Label fit maxima must be supplied for exactly fold-01 and fold-02")
    for fold_id, value in values.items():
        session = _require_date(value, f"{fold_id} fit label max session")
        if session > fold_map[fold_id]["fit_end_session"]:
            raise DailySb3ProtocolError(f"{fold_id} label leakage past fit end")
    return values


def _validate_ppo_config(ppo_config: Mapping[str, Any] | None) -> dict[str, Any]:
    config = dict(DEFAULT_PPO_CONFIG if ppo_config is None else ppo_config)
    if config != DEFAULT_PPO_CONFIG:
        raise DailySb3ProtocolError("PPO config drifted from the immutable protocol")
    return config


def _validate_feature_normalization(feature_normalization: Mapping[str, Any] | None) -> dict[str, Any]:
    config = dict(DEFAULT_FEATURE_NORMALIZATION if feature_normalization is None else feature_normalization)
    if config != DEFAULT_FEATURE_NORMALIZATION:
        raise DailySb3ProtocolError("Feature normalization drifted from the immutable protocol")
    return config


def _validate_compute_mode(compute_mode: str, *, fresh_oos_access_requested: bool, historical_window_usage: str) -> None:
    if compute_mode != SYNTHETIC_COMPUTE_MODE:
        raise DailySb3ProtocolError("Unsupported compute mode; only synthetic verification is allowed")
    if fresh_oos_access_requested:
        raise DailySb3ProtocolError("Fresh OOS access is forbidden by this protocol foundation")
    if historical_window_usage != "SECONDARY_DIAGNOSTIC_ONLY_NOT_MODEL_SELECTION_NOT_PROMOTION":
        raise DailySb3ProtocolError("Historical OOS window usage drifted from secondary-only")


def _statement(
    *,
    available_sessions: Sequence[str] | None = None,
    variants: Sequence[str] | None = None,
    dependency_refs: Sequence[Mapping[str, Any]] | None = None,
    candidate_codes: Sequence[Any] | None = None,
    label_fit_max_by_fold: Mapping[str, str] | None = None,
    ppo_config: Mapping[str, Any] | None = None,
    feature_normalization: Mapping[str, Any] | None = None,
    compute_mode: str = SYNTHETIC_COMPUTE_MODE,
    fresh_oos_access_requested: bool = False,
    historical_window_usage: str = "SECONDARY_DIAGNOSTIC_ONLY_NOT_MODEL_SELECTION_NOT_PROMOTION",
) -> dict[str, Any]:
    _assert_default_lengths()
    variant_ids = _validate_variants(variants)
    dependencies = _validate_dependencies(dependency_refs)
    codes = _validate_codes(candidate_codes)
    sessions = _validate_available_sessions(available_sessions)
    label_max = _validate_label_fit_max(label_fit_max_by_fold)
    frozen_ppo = _validate_ppo_config(ppo_config)
    frozen_normalization = _validate_feature_normalization(feature_normalization)
    _validate_compute_mode(compute_mode, fresh_oos_access_requested=fresh_oos_access_requested, historical_window_usage=historical_window_usage)

    folds = []
    for fold in _folds():
        frozen = dict(fold)
        frozen["fit_label_max_session"] = label_max[frozen["fold_id"]]
        folds.append(frozen)

    return {
        "schema": f"{PROTOCOL_SCHEMA}.statement",
        "protocol_version": PROTOCOL_VERSION,
        "created_at": "2026-07-15T00:00:00Z",
        "market": "KRX",
        "timezone": "Asia/Seoul",
        "research_boundary": {
            "label": "portfolio RL research protocol foundation",
            "research_only": True,
            "synthetic_verification_only": True,
            "compute_mode": compute_mode,
            "no_heavy_compute_marker": NO_HEAVY_COMPUTE_MARKER,
            "training_allowed": False,
            "sb3_learn_allowed": False,
            "fresh_oos_access_allowed": False,
            "fresh_oos_consumed": False,
            "promotion_allowed": False,
            "model_build_allowed": False,
            "paper_forward_allowed": False,
            "live_broker_order_allowed": False,
            "profitability_claim_allowed": False,
            "go_summary_allowed": False,
        },
        "closed_metadata": dict(_CLOSED_METADATA),
        "dependencies": list(dependencies),
        "calendar": {
            "calendar_id": "krx-daily-sb3-v1-2025-05-20-2026-06-12",
            "session_source": "frozen_research_calendar_v1",
            "holiday_exclusions": {
                "train": sorted(TRAIN_HOLIDAYS),
                "validation": sorted(VALIDATION_HOLIDAYS),
                "historical_secondary_only": sorted(HISTORICAL_HOLIDAYS),
            },
            "available_sessions": list(sessions),
            "available_session_count": len(sessions),
            "purge_days": 5,
            "embargo_days": 5,
            "folds": folds,
            "historical_secondary_only_window": _default_historical_window(),
        },
        "candidate_source_contract": {
            "required_columns": [
                "timestamp",
                "symbol",
                "rank_score",
                "price",
                "fill_price",
                "fillable",
                "split",
                "future_return_1d",
                "table",
                "code",
                "source_prediction_run_id",
            ],
            "canonical_code_pattern": "^[0-9]{6}$",
            "canonical_code_samples": list(codes),
            "hash_pattern": "^[0-9a-f]{64}$",
            "noncanonical_code_or_hash_policy": "FAIL_CLOSED",
            "official_test_oos_fit_rows_allowed": 0,
        },
        "cost_model": {
            "primary_cost_bps": PRIMARY_COST_BPS,
            "evaluation_costs_bps": list(EVALUATION_COSTS_BPS),
            "cost_scenarios": list(COST_SCENARIOS),
            "accounting_horizon": "SB3_T_DECIDE_T1_FILL_STATEFUL_V1",
            "duplicate_scalar_haircut_allowed": False,
        },
        "portfolio_config": {
            "initial_cash_krw": 1_000_000,
            "max_positions": 2,
            "buy_fraction": 0.25,
            "cash_reserve_fraction": 0.5,
            "rounding": "Decimal ROUND_HALF_UP",
            "money_quantum_krw": "0.000001",
            "ratio_quantum": "0.000000000001",
        },
        "feature_normalization": frozen_normalization,
        "ppo_config": frozen_ppo,
        "seeds": list(SEEDS),
        "fold_order": list(FOLD_IDS),
        "variant_order": list(variant_ids),
        "variants": list(_variant_defs()),
        "matrix_dimensions": {
            "seed_count": 5,
            "fold_count": 2,
            "variant_count": 5,
            "cell_count": 50,
            "order": "seed-major/fold/variant",
        },
        "comparator_order": list(COMPARATOR_ORDER),
        "prerequisites": {
            "d0": {"required_status_before_promotion": "VERIFIED", "blocking_code": "D0_PRICE_BASIS_NOT_VERIFIED"},
            "d1": {"required_status_before_promotion": "VERIFIED", "blocking_code": "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED"},
            "custody": {"fresh_oos_required_before_any_claim": True, "status_in_protocol": "FRESH_OOS_NOT_RUN", "fresh_oos_access_allowed_here": False},
        },
        "stops": list(STOP_RULES),
    }


def _protocol_uid(protocol_sha256: str) -> str:
    return f"kdp1-{protocol_sha256[:32]}"


def _cell_uid(protocol_sha256: str, seed_id: str, fold_id: str, variant_id: str) -> str:
    basis = {
        "schema": "kronos_daily_sb3_cell_identity_basis.v1",
        "protocol_sha256": protocol_sha256,
        "seed_id": seed_id,
        "fold_id": fold_id,
        "variant_id": variant_id,
    }
    return f"kdp1-cell-{sha256_hex(basis)[:32]}"


def _attempt_uid(protocol_sha256: str, cell_uid: str) -> str:
    basis = {
        "schema": "kronos_daily_sb3_attempt_identity_basis.v1",
        "protocol_sha256": protocol_sha256,
        "cell_uid": cell_uid,
        "attempt_number": 1,
        "compute_mode": SYNTHETIC_COMPUTE_MODE,
    }
    return f"kdp1-attempt-{sha256_hex(basis)[:32]}"


def _variant_by_id(statement: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(variant["variant_id"]): variant for variant in statement["variants"]}


def _fold_by_id(statement: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(fold["fold_id"]): fold for fold in statement["calendar"]["folds"]}


def _cells(statement: Mapping[str, Any], protocol_sha256: str) -> list[dict[str, Any]]:
    variant_by_id = _variant_by_id(statement)
    fold_by_id = _fold_by_id(statement)
    cells: list[dict[str, Any]] = []
    ordinal = 0
    for seed in statement["seeds"]:
        for fold_id in statement["fold_order"]:
            fold = fold_by_id[fold_id]
            for variant_id in statement["variant_order"]:
                variant = variant_by_id[variant_id]
                ordinal += 1
                cell_uid = _cell_uid(protocol_sha256, seed["seed_id"], fold_id, variant_id)
                cells.append(
                    {
                        "schema": "kronos_daily_sb3_protocol_cell.v1",
                        "ordinal": ordinal,
                        "cell_uid": cell_uid,
                        "attempt_uid": _attempt_uid(protocol_sha256, cell_uid),
                        "seed_id": seed["seed_id"],
                        "seed": seed["value"],
                        "fold_id": fold_id,
                        "variant_id": variant_id,
                        "evaluation_cost_bps": variant["evaluation_cost_bps"],
                        "cost_scenario_id": variant["cost_scenario_id"],
                        "train_start_session": fold["fit_start_session"],
                        "train_end_session": fold["fit_end_session"],
                        "validation_start_session": fold["validation_start_session"],
                        "validation_end_session": fold["validation_end_session"],
                        "historical_secondary_only_window_id": statement["calendar"]["historical_secondary_only_window"]["window_id"],
                        "compute_mode": SYNTHETIC_COMPUTE_MODE,
                        "heavy_compute_allowed": False,
                        "fresh_oos_access_allowed": False,
                        "synthetic_verification_only": True,
                    }
                )
    return cells


def build_protocol(
    *,
    available_sessions: Sequence[str] | None = None,
    variants: Sequence[str] | None = None,
    dependency_refs: Sequence[Mapping[str, Any]] | None = None,
    candidate_codes: Sequence[Any] | None = None,
    label_fit_max_by_fold: Mapping[str, str] | None = None,
    ppo_config: Mapping[str, Any] | None = None,
    feature_normalization: Mapping[str, Any] | None = None,
    compute_mode: str = SYNTHETIC_COMPUTE_MODE,
    fresh_oos_access_requested: bool = False,
    historical_window_usage: str = "SECONDARY_DIAGNOSTIC_ONLY_NOT_MODEL_SELECTION_NOT_PROMOTION",
) -> dict[str, Any]:
    """Build the single canonical protocol object and fail closed on drift."""
    statement = _statement(
        available_sessions=available_sessions,
        variants=variants,
        dependency_refs=dependency_refs,
        candidate_codes=candidate_codes,
        label_fit_max_by_fold=label_fit_max_by_fold,
        ppo_config=ppo_config,
        feature_normalization=feature_normalization,
        compute_mode=compute_mode,
        fresh_oos_access_requested=fresh_oos_access_requested,
        historical_window_usage=historical_window_usage,
    )
    protocol_sha256 = sha256_hex(statement)
    cells = _cells(statement, protocol_sha256)
    if len(cells) != 50:
        raise DailySb3ProtocolError(f"Protocol matrix must contain exactly 50 cells, got {len(cells)}")
    return {
        "schema": PROTOCOL_SCHEMA,
        "identity": {
            "protocol_uid": _protocol_uid(protocol_sha256),
            "protocol_sha256": protocol_sha256,
            "identity_algorithm": IDENTITY_ALGORITHM,
            "cell_identity_algorithm": CELL_IDENTITY_ALGORITHM,
        },
        "statement": statement,
        "matrix": {
            "cell_count": len(cells),
            "order": "seed-major/fold/variant",
            "cells": cells,
        },
    }


def validate_protocol(protocol: Mapping[str, Any]) -> None:
    """Verify the canonical protocol bytes, identities, matrix order, and drift."""
    if not isinstance(protocol, Mapping) or set(protocol) != {"schema", "identity", "statement", "matrix"}:
        raise DailySb3ProtocolError("Protocol has an invalid top-level shape")
    if protocol["schema"] != PROTOCOL_SCHEMA:
        raise DailySb3ProtocolError("Protocol schema mismatch")
    identity = protocol["identity"]
    if not isinstance(identity, Mapping) or set(identity) != {"protocol_uid", "protocol_sha256", "identity_algorithm", "cell_identity_algorithm"}:
        raise DailySb3ProtocolError("Protocol identity has an invalid shape")
    protocol_sha256 = _require_sha(identity["protocol_sha256"], "protocol_sha256")
    if identity["protocol_uid"] != _protocol_uid(protocol_sha256):
        raise DailySb3ProtocolError("protocol_uid does not derive from protocol_sha256")
    if identity["identity_algorithm"] != IDENTITY_ALGORITHM or identity["cell_identity_algorithm"] != CELL_IDENTITY_ALGORITHM:
        raise DailySb3ProtocolError("Protocol identity algorithm drifted")
    if sha256_hex(protocol["statement"]) != protocol_sha256:
        raise DailySb3ProtocolError("protocol_sha256 does not match statement bytes")

    expected = build_protocol()
    if protocol != expected:
        raise DailySb3ProtocolError("Protocol drifted from the immutable G008 definition")


def protocol_canonical_bytes() -> bytes:
    protocol = build_protocol()
    validate_protocol(protocol)
    return canonical_bytes(protocol)


def fixture_summary(protocol: Mapping[str, Any] | None = None) -> dict[str, Any]:
    value = build_protocol() if protocol is None else dict(protocol)
    validate_protocol(value)
    raw = canonical_bytes(value)
    cells = value["matrix"]["cells"]
    folds = value["statement"]["calendar"]["folds"]
    return {
        "schema": "kronos_daily_sb3_protocol_fixture.v1",
        "protocol_sha256": value["identity"]["protocol_sha256"],
        "canonical_protocol_sha256": sha256_hex(raw),
        "canonical_protocol_byte_length": len(raw),
        "cell_count": len(cells),
        "first_cell_uid": cells[0]["cell_uid"],
        "first_attempt_uid": cells[0]["attempt_uid"],
        "last_cell_uid": cells[-1]["cell_uid"],
        "last_attempt_uid": cells[-1]["attempt_uid"],
        "fold_session_counts": {
            fold["fold_id"]: {
                "train": fold["train_session_count"],
                "purge_embargo": fold["purge_embargo_session_count"],
                "validation": fold["validation_session_count"],
            }
            for fold in folds
        },
        "historical_secondary_only_session_count": value["statement"]["calendar"]["historical_secondary_only_window"]["session_count"],
        "available_session_count": value["statement"]["calendar"]["available_session_count"],
    }


def validate_command_manifest(manifest: Mapping[str, Any], *, protocol: Mapping[str, Any] | None = None) -> None:
    """Validate the frozen dashboard command manifest without running commands."""
    protocol_value = build_protocol() if protocol is None else dict(protocol)
    validate_protocol(protocol_value)
    required = {
        "schema",
        "protocol_schema",
        "protocol_sha256",
        "purpose",
        "synthetic_verification_only",
        "no_heavy_compute",
        "fresh_oos_access_allowed",
        "command_id_policy",
        "forbidden_token_policy",
        "commands",
        "pass_receipt_commands",
        "forbidden_argv_tokens",
    }
    if not isinstance(manifest, Mapping) or set(manifest) != required:
        raise DailySb3ProtocolError("Command manifest has an invalid shape")
    if manifest["schema"] != COMMAND_MANIFEST_SCHEMA:
        raise DailySb3ProtocolError("Command manifest schema mismatch")
    if manifest["protocol_schema"] != PROTOCOL_SCHEMA or manifest["protocol_sha256"] != protocol_value["identity"]["protocol_sha256"]:
        raise DailySb3ProtocolError("Command manifest is not bound to the canonical protocol")
    if manifest["purpose"] != SYNTHETIC_COMPUTE_MODE or manifest["synthetic_verification_only"] is not True:
        raise DailySb3ProtocolError("Command manifest must be synthetic-verification-only")
    if manifest["no_heavy_compute"] is not True or manifest["fresh_oos_access_allowed"] is not False:
        raise DailySb3ProtocolError("Command manifest compute/OOS guardrails drifted")
    if manifest["command_id_policy"] != "EXACT_APPROVED_COMMAND_ID_AND_ARGV_ONLY":
        raise DailySb3ProtocolError("Command manifest command-id policy drifted")
    if manifest["forbidden_token_policy"] != "CASE_INSENSITIVE_SUBSTRING_REJECT":
        raise DailySb3ProtocolError("Command manifest forbidden-token policy drifted")

    forbidden = tuple(str(token) for token in manifest["forbidden_argv_tokens"])
    if not forbidden or len(set(forbidden)) != len(forbidden):
        raise DailySb3ProtocolError("Command manifest must list unique forbidden argv tokens")

    commands = manifest["commands"]
    if not isinstance(commands, list) or len(commands) != len(_APPROVED_EXECUTABLE_COMMANDS):
        raise DailySb3ProtocolError("Command manifest executable command set drifted")
    for command, (expected_id, expected_argv) in zip(commands, _APPROVED_EXECUTABLE_COMMANDS, strict=True):
        if not isinstance(command, Mapping) or set(command) != {"command_id", "argv", "may_train", "may_read_fresh_oos", "expected_exit", "max_cells_executable"}:
            raise DailySb3ProtocolError("Command entry has an invalid shape")
        argv = command["argv"]
        if command["command_id"] != expected_id or argv != expected_argv:
            raise DailySb3ProtocolError("Command entry is not the exact approved command id/argv")
        flattened = " ".join(argv).lower()
        if command["may_train"] is not False or command["may_read_fresh_oos"] is not False or command["max_cells_executable"] != 0:
            raise DailySb3ProtocolError("Command entry is not synthetic-only")
        if command["expected_exit"] != 0:
            raise DailySb3ProtocolError("Command entry expected_exit must be zero for synthetic verification")
        if "--synthetic-verification-only" not in argv or "--no-heavy-compute" not in argv:
            raise DailySb3ProtocolError("Command argv must carry synthetic/no-heavy-compute flags")
        for token in forbidden:
            if token.lower() in flattened:
                raise DailySb3ProtocolError(f"Command argv contains forbidden token {token}")

    receipt_commands = manifest["pass_receipt_commands"]
    if not isinstance(receipt_commands, list) or len(receipt_commands) != len(_APPROVED_PASS_RECEIPT_COMMANDS):
        raise DailySb3ProtocolError("Command manifest PASS receipt command set drifted")
    for command, (expected_component, expected_id, expected_argv) in zip(receipt_commands, _APPROVED_PASS_RECEIPT_COMMANDS, strict=True):
        expected_keys = {
            "component",
            "command_id",
            "argv",
            "not_run_synthetic_receipt",
            "synthetic_only",
            "heavy_compute_run",
            "fresh_oos_accessed",
            "full_ppo_status",
            "fresh_oos_status",
        }
        if not isinstance(command, Mapping) or set(command) != expected_keys:
            raise DailySb3ProtocolError("PASS receipt command entry has an invalid shape")
        argv = command["argv"]
        if command["component"] != expected_component or command["command_id"] != expected_id or argv != expected_argv:
            raise DailySb3ProtocolError("PASS receipt command is not the exact approved command id/argv")
        if command["not_run_synthetic_receipt"] is not True or command["synthetic_only"] is not True:
            raise DailySb3ProtocolError("PASS receipt command must be an explicit synthetic NOT_RUN receipt")
        if command["heavy_compute_run"] is not False or command["fresh_oos_accessed"] is not False:
            raise DailySb3ProtocolError("PASS receipt command attempted compute or fresh OOS access")
        if command["full_ppo_status"] != "NOT_RUN" or command["fresh_oos_status"] != "NOT_RUN":
            raise DailySb3ProtocolError("PASS receipt command reports a forbidden run")
        flattened = " ".join(argv).lower()
        for token in forbidden:
            if token.lower() in flattened:
                raise DailySb3ProtocolError(f"PASS receipt command argv contains forbidden token {token}")


def _parse_canonical_protocol(path: Path) -> Mapping[str, Any]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DailySb3ProtocolError("Protocol file is not JSON") from exc
    if canonical_bytes(value) != raw:
        raise DailySb3ProtocolError("Protocol file is not RFC 8785 canonical JSON")
    if not isinstance(value, Mapping):
        raise DailySb3ProtocolError("Protocol file root is not an object")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit or validate the immutable Kronos daily SB3 protocol without training.")
    parser.add_argument("--emit-protocol", action="store_true")
    parser.add_argument("--emit-fixture-summary", action="store_true")
    parser.add_argument("--validate-protocol", type=Path)
    parser.add_argument("--synthetic-verification-only", action="store_true")
    parser.add_argument("--no-heavy-compute", action="store_true")
    args = parser.parse_args(argv)
    if not args.synthetic_verification_only or not args.no_heavy_compute:
        raise DailySb3ProtocolError("CLI requires --synthetic-verification-only and --no-heavy-compute")
    selected = sum(bool(value) for value in (args.emit_protocol, args.emit_fixture_summary, args.validate_protocol is not None))
    if selected != 1:
        raise DailySb3ProtocolError("Select exactly one protocol action")
    if args.validate_protocol is not None:
        validate_protocol(_parse_canonical_protocol(args.validate_protocol))
        return 0
    payload: Mapping[str, Any] = fixture_summary() if args.emit_fixture_summary else build_protocol()
    print(canonical_bytes(payload).decode("utf-8"))
    return 0


__all__ = [
    "ALL_REQUIRED_SESSIONS",
    "COMMAND_MANIFEST_SCHEMA",
    "DailySb3ProtocolError",
    "EVALUATION_COSTS_BPS",
    "FOLD_IDS",
    "HISTORICAL_SECONDARY_ONLY_SESSIONS",
    "NO_HEAVY_COMPUTE_MARKER",
    "PROTOCOL_SCHEMA",
    "PROTOCOL_SCHEMA_ID",
    "SEEDS",
    "SYNTHETIC_COMPUTE_MODE",
    "VARIANT_IDS",
    "build_protocol",
    "canonical_bytes",
    "fixture_summary",
    "protocol_canonical_bytes",
    "sha256_hex",
    "validate_command_manifest",
    "validate_protocol",
]


if __name__ == "__main__":
    raise SystemExit(main())
