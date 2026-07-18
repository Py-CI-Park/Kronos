"""Deterministic V5.1 horizon evaluator for exact 15:20 proxy panels.

The evaluator is intentionally narrow: callers must freeze H1/H3/H5 selections
before untouched test/OOS evaluation, then replay that immutable manifest against a
validated causal panel.  Monetary NAV is delegated to the V5.1 accounting helper.
"""
from __future__ import annotations

import hashlib

import json
import math
import re
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import is_dataclass, asdict
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import Any, Final

from stom_rl.daily_v51_causal_panel import (
    PRICE_BASIS,
    SCHEMA_VERSION as CAUSAL_PANEL_SCHEMA_VERSION,
    validate_causal_panel,
)

EVALUATOR_SCHEMA_VERSION: Final = "kronos_daily_v51_evaluator.v1"
FREEZE_SCHEMA_VERSION: Final = "kronos_daily_v51_horizon_freeze.v1"
HORIZON_MANIFEST_SCHEMA_VERSION: Final = "kronos_daily_v51_horizon_manifest.v1"
HORIZON_RESULT_SCHEMA_VERSION: Final = "kronos_daily_v51_horizon_result.v1"
HORIZON_GATE_SCHEMA_VERSION: Final = "kronos_daily_v51_horizon_gate.v1"

PRIMARY_VARIANT_ID: Final = "v51-h1-primary"
VALIDATION_VARIANT_IDS: Final = ("v51-h3-validation", "v51-h5-validation")
VARIANT_ORDER: Final = (PRIMARY_VARIANT_ID, *VALIDATION_VARIANT_IDS)

MISSING_1520_ENTRY_BAR: Final = "MISSING_1520_ENTRY_BAR"
MISSING_1520_EXIT_BAR: Final = "MISSING_1520_EXIT_BAR"

HORIZON_VARIANTS: Final = (
    {
        "variant_id": PRIMARY_VARIANT_ID,
        "role": "primary",
        "horizon_id": "H1",
        "horizon_days": 1,
        "label_column": "future_return_h1_1520_proxy",
    },
    {
        "variant_id": "v51-h3-validation",
        "role": "validation",
        "horizon_id": "H3",
        "horizon_days": 3,
        "label_column": "future_return_h3_1520_proxy",
    },
    {
        "variant_id": "v51-h5-validation",
        "role": "validation",
        "horizon_id": "H5",
        "horizon_days": 5,
        "label_column": "future_return_h5_1520_proxy",
    },
)

FALSE_PROMOTION_CLAIMS: Final = {
    "broker_integration": False,
    "live_trading": False,
    "paper_trading": False,
    "profit": False,
}
NO_CLAIM_LABELS: Final = (
    "NO_LIVE_TRADING",
    "NO_BROKER_INTEGRATION",
    "NO_PAPER_TRADING",
    "NO_PROFIT_CLAIM",
)
_V51_COST_SCENARIO_ID_BY_BP: Final = {
    0: "zero_control_0bp",
    23: "base_23bp",
    46: "stress_46bp",
}
_V51_COST_SCENARIO_IDS: Final = tuple(_V51_COST_SCENARIO_ID_BY_BP.values())
_V51_ROUND_TRIP_BP_BY_SCENARIO_ID: Final = {
    scenario_id: cost_bp for cost_bp, scenario_id in _V51_COST_SCENARIO_ID_BY_BP.items()
}
_ACCOUNTING_SCHEMA_VERSION: Final = "kronos_v51_slot_accounting.v1"
_ACCOUNTING_DIGEST_FIELD: Final = "accounting_manifest_sha256"
_V51_SLOT_BUY_BUDGET_KRW: Final = Decimal("5000000")
_V51_STRESS_BUY_SIDE_COST_BP: Final = Decimal("13")
_BP_DENOMINATOR: Final = Decimal("10000")

_REQUIRED_SPLIT_KEYS: Final = frozenset(
    {
        "split_id",
        "train_split_id",
        "validation_split_id",
        "untouched_test_split_id",
        "oos_split_id",
        "horizon_choice_source",
        "used_untouched_test_for_horizon_choice",
        "used_oos_for_horizon_choice",
        "post_hoc_retune",
    }
)
_ALLOWED_HORIZON_CHOICE_SOURCES: Final = frozenset(
    {"train_validation_only", "pre_registered_protocol", "ex_ante"}
)
_FORBIDDEN_TRUE_SPLIT_FLAGS: Final = (
    "used_untouched_test_for_horizon_choice",
    "used_test_for_horizon_choice",
    "used_oos_for_horizon_choice",
    "post_hoc_retune",
    "post_hoc_retuning",
    "retuned_after_test",
    "retuned_after_oos",
)
_SELECTION_ALLOWED_KEYS: Final = frozenset(
    {
        "symbol",
        "session",
        "rank",
        "score",
        "score_column",
        "selection_reason",
        "selection_source",
        "variant_id",
        "horizon_id",
        "label_column",
        "fixed_at",
        "selection_sequence",
        "split_id",
        "quantity",
    }
)
_FORBIDDEN_LEGACY_VALUE_KEYS: Final = frozenset(
    {
        "horizon_id",
        "label_column",
        "target_column",
        "return_column",
        "horizon_label",
        "label_alias",
        "prediction_target",
    }
)
_SYMBOL_RE: Final = re.compile(r"[0-9]{6}\Z")
_DATE_RE: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_UTC_SECONDS_RE: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_SHA256_RE: Final = re.compile(r"[0-9a-f]{64}\Z")


class V51EvaluationError(ValueError):
    """Raised when V5.1 horizon evaluation must fail closed."""


AccountHelper = Callable[..., Mapping[str, Any]]


def canonical_manifest_sha256(value: Any, *, digest_field: str = "manifest_sha256") -> str:
    """Return the deterministic SHA-256 used by V5.1 evaluator manifests."""

    payload = value
    if isinstance(value, Mapping) and digest_field in value:
        payload = {str(key): item for key, item in value.items() if str(key) != digest_field}
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def freeze_v51_horizon_variants(
    panel: Mapping[str, Any],
    selections_by_variant: Mapping[str, Sequence[Any]],
    *,
    split_identity: Mapping[str, Any],
    fixed_at: str | None = None,
    selection_sequence: int | None = None,
    cost_scenario_bp: int = 23,
) -> dict[str, Any]:
    """Freeze immutable H1/H3/H5 selections before untouched test/OOS evaluation."""

    _reject_future_return_1d(panel, "causal panel")
    validated_panel = validate_causal_panel(panel)
    split = _validate_split_identity(split_identity)
    fixed_at_value, sequence_value = _normalize_selection_marker(fixed_at, selection_sequence)
    cost_bp = _cost_scenario_bp(cost_scenario_bp, "cost_scenario_bp")
    _require_exact_variant_keys(selections_by_variant)

    lookup, by_symbol = _panel_row_lookup(validated_panel)
    source_hashes = _source_hashes(validated_panel)
    split_identity_sha256 = canonical_manifest_sha256(split)
    horizon_manifests: list[dict[str, Any]] = []

    for variant in HORIZON_VARIANTS:
        variant_id = str(variant["variant_id"])
        selected_rows = _normalize_variant_selections(
            selections_by_variant[variant_id],
            variant=variant,
            lookup=lookup,
            by_symbol=by_symbol,
            split_identity=split,
        )
        horizon_manifest = {
            "schema_version": HORIZON_MANIFEST_SCHEMA_VERSION,
            "variant_id": variant_id,
            "role": variant["role"],
            "horizon_id": variant["horizon_id"],
            "horizon_days": variant["horizon_days"],
            "label_column": variant["label_column"],
            "price_basis": PRICE_BASIS,
            "panel_schema_version": CAUSAL_PANEL_SCHEMA_VERSION,
            "panel_sha256": validated_panel["panel_sha256"],
            "source_hashes": source_hashes,
            "split_identity_sha256": split_identity_sha256,
            "split_identity": split,
            "selection_fixed_at": fixed_at_value,
            "selection_sequence": sequence_value,
            "selection_lock": "FROZEN_BEFORE_UNTOUCHED_TEST_AND_OOS",
            "horizon_choice_source": split["horizon_choice_source"],
            "cost_scenario_bp": cost_bp,
            "selected_count": len(selected_rows),
            "selected_rows": selected_rows,
        }
        horizon_manifests.append(_attach_digest(horizon_manifest))

    freeze_manifest = {
        "schema_version": FREEZE_SCHEMA_VERSION,
        "evaluator_schema_version": EVALUATOR_SCHEMA_VERSION,
        "panel_schema_version": CAUSAL_PANEL_SCHEMA_VERSION,
        "panel_sha256": validated_panel["panel_sha256"],
        "price_basis": PRICE_BASIS,
        "source_hashes": source_hashes,
        "primary_variant_id": PRIMARY_VARIANT_ID,
        "validation_variant_ids": list(VALIDATION_VARIANT_IDS),
        "variant_order": list(VARIANT_ORDER),
        "split_identity_sha256": split_identity_sha256,
        "split_identity": split,
        "selection_fixed_at": fixed_at_value,
        "selection_sequence": sequence_value,
        "horizons_fixed_before_untouched_test": True,
        "test_oos_driven_horizon_choice_rejected": True,
        "post_hoc_retuning_rejected": True,
        "cost_scenario_bp": cost_bp,
        "horizon_manifest_sha256_by_variant": {
            str(item["variant_id"]): str(item["manifest_sha256"]) for item in horizon_manifests
        },
        "horizon_manifests": horizon_manifests,
    }
    return validate_v51_freeze_manifest(_attach_digest(freeze_manifest), panel=validated_panel)


def validate_v51_freeze_manifest(
    freeze_manifest: Mapping[str, Any],
    *,
    panel: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a frozen H1/H3/H5 manifest and its deterministic hash."""

    manifest = _require_mapping(freeze_manifest, "freeze manifest")
    _reject_future_return_1d(manifest, "freeze manifest")
    declared_digest = manifest.get("manifest_sha256")
    if not _is_sha256(declared_digest):
        raise V51EvaluationError("freeze manifest_sha256 is missing or invalid")
    expected_digest = canonical_manifest_sha256(manifest)
    if declared_digest != expected_digest:
        raise V51EvaluationError("freeze manifest_sha256 does not match deterministic contents")
    if manifest.get("schema_version") != FREEZE_SCHEMA_VERSION:
        raise V51EvaluationError("freeze manifest schema_version mismatch")
    if manifest.get("evaluator_schema_version") != EVALUATOR_SCHEMA_VERSION:
        raise V51EvaluationError("freeze manifest evaluator schema_version mismatch")
    if manifest.get("panel_schema_version") != CAUSAL_PANEL_SCHEMA_VERSION:
        raise V51EvaluationError("freeze manifest panel schema_version mismatch")
    if manifest.get("price_basis") != PRICE_BASIS:
        raise V51EvaluationError("freeze manifest price_basis must be exact 15:20 proxy")
    if manifest.get("primary_variant_id") != PRIMARY_VARIANT_ID:
        raise V51EvaluationError("freeze manifest primary variant drifted")
    if tuple(manifest.get("validation_variant_ids", ())) != VALIDATION_VARIANT_IDS:
        raise V51EvaluationError("freeze manifest validation variants drifted")
    if tuple(manifest.get("variant_order", ())) != VARIANT_ORDER:
        raise V51EvaluationError("freeze manifest variant order drifted")
    if manifest.get("horizons_fixed_before_untouched_test") is not True:
        raise V51EvaluationError("horizons must be fixed before untouched test/OOS")
    if manifest.get("test_oos_driven_horizon_choice_rejected") is not True:
        raise V51EvaluationError("test/OOS-driven horizon choice must be rejected")
    if manifest.get("post_hoc_retuning_rejected") is not True:
        raise V51EvaluationError("post-hoc retuning must be rejected")

    if panel is not None:
        _reject_future_return_1d(panel, "causal panel")
        validated_panel = validate_causal_panel(panel)
        if manifest.get("panel_sha256") != validated_panel.get("panel_sha256"):
            raise V51EvaluationError("freeze manifest panel_sha256 does not match supplied panel")
        if manifest.get("source_hashes") != _source_hashes(validated_panel):
            raise V51EvaluationError("freeze manifest source hashes do not match supplied panel")
    elif not _is_sha256(manifest.get("panel_sha256")):
        raise V51EvaluationError("freeze manifest panel_sha256 is invalid")

    split = _validate_split_identity(_require_mapping(manifest.get("split_identity"), "freeze split_identity"))
    split_digest = canonical_manifest_sha256(split)
    if manifest.get("split_identity_sha256") != split_digest:
        raise V51EvaluationError("freeze manifest split_identity_sha256 mismatch")

    fixed_at, sequence = _normalize_selection_marker(
        manifest.get("selection_fixed_at"),
        manifest.get("selection_sequence"),
    )
    cost_bp = _cost_scenario_bp(manifest.get("cost_scenario_bp"), "freeze cost_scenario_bp")
    manifest_hashes = _require_mapping(
        manifest.get("horizon_manifest_sha256_by_variant"),
        "freeze horizon_manifest_sha256_by_variant",
    )
    horizon_manifests = manifest.get("horizon_manifests")
    if not isinstance(horizon_manifests, list) or len(horizon_manifests) != len(HORIZON_VARIANTS):
        raise V51EvaluationError("freeze manifest must carry exactly H1/H3/H5 horizon manifests")

    seen_variants: set[str] = set()
    normalized_horizon_manifests: list[dict[str, Any]] = []
    variant_by_id = _variant_by_id()
    for expected_variant_id, horizon_manifest in zip(VARIANT_ORDER, horizon_manifests):
        item = _require_mapping(horizon_manifest, f"horizon manifest {expected_variant_id}")
        item_digest = item.get("manifest_sha256")
        if not _is_sha256(item_digest):
            raise V51EvaluationError(f"horizon manifest {expected_variant_id} manifest_sha256 is invalid")
        if item_digest != canonical_manifest_sha256(item):
            raise V51EvaluationError(f"horizon manifest {expected_variant_id} manifest_sha256 mismatch")
        variant_id = str(item.get("variant_id"))
        if variant_id != expected_variant_id:
            raise V51EvaluationError("horizon manifest variant order or ID drifted")
        if variant_id in seen_variants:
            raise V51EvaluationError(f"duplicate horizon variant: {variant_id}")
        seen_variants.add(variant_id)
        if manifest_hashes.get(variant_id) != item_digest:
            raise V51EvaluationError(f"freeze manifest hash table drifted for {variant_id}")
        variant = variant_by_id[variant_id]
        _validate_horizon_manifest_shape(
            item,
            variant=variant,
            panel_sha256=str(manifest["panel_sha256"]),
            source_hashes=_require_mapping(manifest.get("source_hashes"), "freeze source_hashes"),
            split=split,
            split_digest=split_digest,
            fixed_at=fixed_at,
            sequence=sequence,
            cost_scenario_bp=cost_bp,
        )
        normalized_horizon_manifests.append(dict(item))

    return dict(manifest, split_identity=split, horizon_manifests=normalized_horizon_manifests)


def evaluate_v51_horizon_variants(
    panel: Mapping[str, Any],
    freeze_manifest: Mapping[str, Any],
    *,
    cost_scenario_bp: int = 23,
    accounting_helper: AccountHelper | None = None,
) -> dict[str, Any]:
    """Evaluate frozen H1/H3/H5 variants and delegate economic NAV to accounting."""

    _reject_future_return_1d(panel, "causal panel")
    validated_panel = validate_causal_panel(panel)
    freeze = validate_v51_freeze_manifest(freeze_manifest, panel=validated_panel)
    cost_bp = _cost_scenario_bp(cost_scenario_bp, "cost_scenario_bp")
    if cost_bp != _cost_scenario_bp(freeze.get("cost_scenario_bp"), "freeze cost_scenario_bp"):
        raise V51EvaluationError("cost_scenario_bp must match the frozen manifest")
    helper = accounting_helper or _load_accounting_helper()
    lookup, _ = _panel_row_lookup(validated_panel)
    source_hashes = _source_hashes(validated_panel)
    false_locks = _false_map(_require_mapping(validated_panel.get("locks"), "panel locks"), "panel locks")
    promotion_claims = _false_map(
        _require_mapping(validated_panel.get("promotion_claims"), "panel promotion_claims"),
        "panel promotion_claims",
    )

    horizon_results: list[dict[str, Any]] = []
    for horizon_manifest in freeze["horizon_manifests"]:
        variant = _variant_by_id()[str(horizon_manifest["variant_id"])]
        accounting_rows, selected_exact_marks = _accounting_rows_for_horizon(
            lookup,
            horizon_manifest=horizon_manifest,
            variant=variant,
        )
        accounting_result = _invoke_accounting_helper(
            helper,
            accounting_rows=accounting_rows,
            horizon_id=variant["horizon_id"],
        )
        accounting_payload = _validate_accounting_result(
            accounting_result,
            variant=variant,
            cost_scenario_bp=cost_bp,
        )
        accounting_manifest_sha256 = str(accounting_payload["accounting_manifest_sha256"])
        accounting_input_sha256 = canonical_manifest_sha256(accounting_rows)
        metrics = {
            "schema_version": "kronos_daily_v51_horizon_metrics.v1",
            "variant_id": variant["variant_id"],
            "horizon_id": variant["horizon_id"],
            "horizon_days": variant["horizon_days"],
            "cost_scenario_id": accounting_payload["cost_scenario_id"],
            "round_trip_cost_bp": accounting_payload["round_trip_cost_bp"],
            "selected_count": len(accounting_rows),
            "slot_count": len(accounting_payload["slots"]),
            "account_nav": accounting_payload["account_nav"],
            "reserve_krw": accounting_payload["reserve_krw"],
            "deployed_principal_krw": accounting_payload["deployed_principal_krw"],
            "accounting_blocker_count": len(accounting_payload["blockers"]),
            "accounting_manifest_sha256": accounting_manifest_sha256,
            "accounting_input_sha256": accounting_input_sha256,
        }
        gate = _horizon_gate(variant, accounting_payload["blockers"])
        result = {
            "schema_version": HORIZON_RESULT_SCHEMA_VERSION,
            "variant_id": variant["variant_id"],
            "role": variant["role"],
            "horizon_id": variant["horizon_id"],
            "horizon_days": variant["horizon_days"],
            "label_column": variant["label_column"],
            "price_basis": PRICE_BASIS,
            "panel_sha256": validated_panel["panel_sha256"],
            "source_hashes": source_hashes,
            "freeze_manifest_sha256": freeze["manifest_sha256"],
            "horizon_manifest_sha256": horizon_manifest["manifest_sha256"],
            "split_identity_sha256": freeze["split_identity_sha256"],
            "selection_fixed_at": horizon_manifest["selection_fixed_at"],
            "selection_sequence": horizon_manifest["selection_sequence"],
            "selected_exact_marks": selected_exact_marks,
            "accounting_input_rows": accounting_rows,
            "accounting_input_sha256": accounting_input_sha256,
            "accounting": accounting_payload,
            "metrics": metrics,
            "gate": gate,
            "false_locks": false_locks,
            "promotion_claims": promotion_claims,
            "no_claims": list(NO_CLAIM_LABELS),
        }
        horizon_results.append(_attach_digest(result, digest_field="result_sha256"))

    evaluation_manifest = {
        "schema_version": EVALUATOR_SCHEMA_VERSION,
        "panel_schema_version": CAUSAL_PANEL_SCHEMA_VERSION,
        "price_basis": PRICE_BASIS,
        "panel_sha256": validated_panel["panel_sha256"],
        "source_hashes": source_hashes,
        "freeze_manifest_sha256": freeze["manifest_sha256"],
        "split_identity_sha256": freeze["split_identity_sha256"],
        "primary_variant_id": PRIMARY_VARIANT_ID,
        "validation_variant_ids": list(VALIDATION_VARIANT_IDS),
        "variant_order": list(VARIANT_ORDER),
        "cost_scenario_bp": cost_bp,
        "horizons_fixed_before_untouched_test": True,
        "test_oos_driven_horizon_choice_rejected": True,
        "post_hoc_retuning_rejected": True,
        "false_locks": false_locks,
        "promotion_claims": promotion_claims,
        "no_claims": list(NO_CLAIM_LABELS),
        "horizon_result_sha256_by_variant": {
            str(item["variant_id"]): str(item["result_sha256"]) for item in horizon_results
        },
        "metrics_by_variant": {str(item["variant_id"]): item["metrics"] for item in horizon_results},
        "gates_by_variant": {str(item["variant_id"]): item["gate"] for item in horizon_results},
        "horizon_results": horizon_results,
    }
    return _attach_digest(evaluation_manifest)


def _load_accounting_helper() -> AccountHelper:
    from stom_rl.v5_accounting import build_v51_slot_accounting_manifest

    return build_v51_slot_accounting_manifest


def _invoke_accounting_helper(
    helper: AccountHelper,
    *,
    accounting_rows: Sequence[Mapping[str, Any]],
    horizon_id: str,
) -> Mapping[str, Any]:
    return helper(accounting_rows, horizon_id)


def _require_exact_variant_keys(selections_by_variant: Mapping[str, Sequence[Any]]) -> None:
    if not isinstance(selections_by_variant, Mapping):
        raise V51EvaluationError("selections_by_variant must be a mapping keyed by immutable variant IDs")
    observed = tuple(selections_by_variant.keys())
    if observed != VARIANT_ORDER:
        raise V51EvaluationError("selections must be keyed exactly by immutable H1/H3/H5 variant IDs")


def _normalize_variant_selections(
    selections: Sequence[Any],
    *,
    variant: Mapping[str, Any],
    lookup: Mapping[tuple[str, str], tuple[int, Mapping[str, Any]]],
    by_symbol: Mapping[str, Sequence[tuple[str, int, Mapping[str, Any]]]],
    split_identity: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if isinstance(selections, (str, bytes)) or isinstance(selections, Mapping) or not isinstance(selections, Sequence):
        raise V51EvaluationError(f"selections for {variant['variant_id']} must be a sequence")
    rows: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()
    for ordinal, item in enumerate(selections, start=1):
        normalized = _normalize_selection_item(item, variant=variant, ordinal=ordinal, split_identity=split_identity)
        symbol = normalized["symbol"]
        if symbol in seen_symbols:
            raise V51EvaluationError(f"duplicate selected symbol for {variant['variant_id']}: {symbol}")
        seen_symbols.add(symbol)
        session = normalized.get("session")
        if session is None:
            candidates = list(by_symbol.get(symbol, ()))
            if len(candidates) != 1:
                raise V51EvaluationError(f"selected symbol {symbol} must include an unambiguous session")
            session = candidates[0][0]
            normalized["session"] = session
        key = (symbol, str(session))
        if key not in lookup:
            raise V51EvaluationError(f"selected row is outside the validated panel: {symbol} {session}")
        panel_index, row = lookup[key]
        label_column = str(variant["label_column"])
        statuses = _require_mapping(row.get("label_statuses"), "panel row label_statuses")
        status = _require_mapping(statuses.get(label_column), f"label status {label_column}")
        normalized.update(
            {
                "panel_row_index": panel_index,
                "label_status": status.get("status"),
                "entry_1520_status": row.get("entry_1520_status"),
                "entry_timestamp": status.get("entry_timestamp"),
                "exit_timestamp": status.get("exit_timestamp"),
            }
        )
        rows.append(normalized)
    return rows


def _normalize_selection_item(
    item: Any,
    *,
    variant: Mapping[str, Any],
    ordinal: int,
    split_identity: Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(item, str):
        payload: dict[str, Any] = {"symbol": item}
    elif isinstance(item, Mapping):
        payload = {str(key): value for key, value in item.items()}
    else:
        raise V51EvaluationError(f"selection item {ordinal} for {variant['variant_id']} must be a symbol or mapping")
    _reject_future_return_1d(payload, f"selection item {ordinal}")
    unexpected = sorted(set(payload) - _SELECTION_ALLOWED_KEYS)
    if unexpected:
        raise V51EvaluationError(f"selection item {ordinal} contains unexpected key: {unexpected[0]}")
    if str(payload.get("variant_id", variant["variant_id"])) != variant["variant_id"]:
        raise V51EvaluationError("selection variant_id mixes immutable horizon variants")
    if str(payload.get("horizon_id", variant["horizon_id"])) != variant["horizon_id"]:
        raise V51EvaluationError("selection horizon_id mixes immutable horizon variants")
    label_column = str(payload.get("label_column", variant["label_column"]))
    if label_column == "future_return_1d":
        raise V51EvaluationError("future_return_1d is not a V5.1 horizon alias")
    if label_column != variant["label_column"]:
        raise V51EvaluationError("selection label_column mixes immutable horizon variants")
    split_id = str(payload.get("split_id", split_identity["split_id"]))
    if split_id != split_identity["split_id"]:
        raise V51EvaluationError("selection split_id does not match frozen split identity")
    symbol = _symbol(payload.get("symbol"), "selection symbol")
    normalized: dict[str, Any] = {
        "symbol": symbol,
        "variant_id": variant["variant_id"],
        "horizon_id": variant["horizon_id"],
        "label_column": variant["label_column"],
        "role": variant["role"],
        "selection_ordinal": ordinal,
        "split_id": split_id,
    }
    if payload.get("session") is not None:
        normalized["session"] = _date(payload["session"], "selection session")
    if payload.get("rank") is not None:
        normalized["rank"] = _positive_int(payload["rank"], "selection rank")
    if payload.get("score") is not None:
        normalized["score"] = _finite_json_number(payload["score"], "selection score")
    for text_key in ("score_column", "selection_reason", "selection_source", "fixed_at"):
        if payload.get(text_key) is not None:
            normalized[text_key] = _text(payload[text_key], f"selection {text_key}")
    if payload.get("selection_sequence") is not None:
        normalized["selection_sequence"] = _positive_int(payload["selection_sequence"], "selection sequence")
    if "quantity" in payload:
        normalized["quantity"] = _explicit_quantity(payload.get("quantity"))
    else:
        normalized["quantity"] = None
    return normalized


def _accounting_rows_for_horizon(
    lookup: Mapping[tuple[str, str], tuple[int, Mapping[str, Any]]],
    *,
    horizon_manifest: Mapping[str, Any],
    variant: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accounting_rows: list[dict[str, Any]] = []
    selected_exact_marks: list[dict[str, Any]] = []
    label_column = str(variant["label_column"])
    for selection in horizon_manifest["selected_rows"]:
        symbol = str(selection["symbol"])
        session = str(selection["session"])
        _, row = lookup[(symbol, session)]
        entry, exit_mark, status = _require_available_marks(row, label_column=label_column, symbol=symbol, session=session)
        entry_price = _exact_price(entry, f"{symbol} {session} entry")
        exit_price = _exact_price(exit_mark, f"{symbol} {session} {label_column} exit")
        quantity = selection.get("quantity") or _floor_v51_quantity_for_accounting(entry_price)
        accounting_rows.append(
            {
                "symbol": symbol,
                "side": "long",
                "quantity": quantity,
                "entry_mark": entry,
                "exit_mark": exit_mark,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "horizon_id": variant["horizon_id"],
                "horizon_days": variant["horizon_days"],
                "label_column": label_column,
                "session": session,
                "entry_session": session,
                "exit_session": status["exit_session"],
                "source_db_sha256": horizon_manifest["source_hashes"]["source_db_sha256"],
                "source_identity_sha256": horizon_manifest["source_hashes"]["source_identity_sha256"],
                "panel_sha256": horizon_manifest["panel_sha256"],
            }
        )
        selected_exact_marks.append(
            {
                "symbol": symbol,
                "entry_session": session,
                "exit_session": status["exit_session"],
                "entry_timestamp": status["entry_timestamp"],
                "exit_timestamp": status["exit_timestamp"],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "price_basis": PRICE_BASIS,
                "official_close": False,
                "label_column": label_column,
                "horizon_id": variant["horizon_id"],
            }
        )
    return accounting_rows, selected_exact_marks


def _require_available_marks(
    row: Mapping[str, Any],
    *,
    label_column: str,
    symbol: str,
    session: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    entry = row.get("entry_1520")
    if row.get("entry_1520_status") != "available" or not isinstance(entry, Mapping):
        raise V51EvaluationError(f"{MISSING_1520_ENTRY_BAR}: {symbol} {session}")
    statuses = _require_mapping(row.get("label_statuses"), "panel row label_statuses")
    status = _require_mapping(statuses.get(label_column), f"label status {label_column}")
    if status.get("status") == "missing_entry":
        raise V51EvaluationError(f"{MISSING_1520_ENTRY_BAR}: {symbol} {session}")
    exits = _require_mapping(row.get("exit_1520_by_label"), "panel row exit_1520_by_label")
    exit_mark = exits.get(label_column)
    if status.get("status") != "available" or not isinstance(exit_mark, Mapping):
        raise V51EvaluationError(f"{MISSING_1520_EXIT_BAR}: {symbol} {session} {label_column}")
    return entry, exit_mark, status


def _validate_accounting_result(
    accounting_result: Mapping[str, Any],
    *,
    variant: Mapping[str, Any],
    cost_scenario_bp: int,
) -> dict[str, Any]:
    result = dict(_require_mapping(accounting_result, "accounting result"))
    manifest = _require_mapping(result.get("manifest", result), "accounting manifest")

    declared_digest = manifest.get(_ACCOUNTING_DIGEST_FIELD)
    if not _is_sha256(declared_digest):
        raise V51EvaluationError("accounting_manifest_sha256 is missing or invalid")
    expected_digest = canonical_manifest_sha256(manifest, digest_field=_ACCOUNTING_DIGEST_FIELD)
    if declared_digest != expected_digest:
        raise V51EvaluationError("accounting_manifest_sha256 does not match deterministic accounting manifest")

    _require_accounting_manifest_header(manifest, variant=variant)
    if "cost_scenario_bp" in manifest and _cost_scenario_bp(
        manifest["cost_scenario_bp"],
        "accounting cost_scenario_bp",
    ) != cost_scenario_bp:
        raise V51EvaluationError("accounting manifest cost_scenario_bp does not match frozen cost")

    false_locks = _false_map(
        _require_mapping(manifest.get("false_locks"), "accounting false_locks"),
        "accounting false_locks",
    )
    promotion_claims = _exact_false_map(
        _require_mapping(manifest.get("promotion_claims"), "accounting promotion_claims"),
        FALSE_PROMOTION_CLAIMS,
        "accounting promotion_claims",
    )
    no_claims = _required_no_claim_labels(manifest.get("no_claims"), "accounting no_claims")

    scenario_ids = manifest.get("cost_scenario_ids")
    if isinstance(scenario_ids, (str, bytes)) or not isinstance(scenario_ids, Sequence):
        raise V51EvaluationError("accounting manifest must enumerate exact 0/23/46bp scenarios")
    if tuple(scenario_ids) != _V51_COST_SCENARIO_IDS:
        raise V51EvaluationError("accounting manifest must enumerate exact 0/23/46bp scenarios")
    scenario_manifests_raw = _require_mapping(manifest.get("scenario_manifests"), "accounting scenario_manifests")
    if {str(key) for key in scenario_manifests_raw} != set(_V51_COST_SCENARIO_IDS):
        raise V51EvaluationError("accounting scenario_manifests must contain exact 0/23/46bp scenarios")

    scenario_manifests: dict[str, dict[str, Any]] = {}
    for scenario_id in _V51_COST_SCENARIO_IDS:
        scenario = dict(
            _require_mapping(
                scenario_manifests_raw.get(scenario_id),
                f"accounting scenario manifest {scenario_id}",
            )
        )
        _validate_accounting_scenario_manifest(
            scenario,
            scenario_id=scenario_id,
            round_trip_cost_bp=_V51_ROUND_TRIP_BP_BY_SCENARIO_ID[scenario_id],
            variant=variant,
        )
        scenario_manifests[scenario_id] = scenario

    primary_scenario_id = _scenario_id_for_cost_bp(23)
    if manifest.get("primary_cost_scenario_id") != primary_scenario_id:
        raise V51EvaluationError("accounting manifest primary_cost_scenario_id drifted")
    if _require_mapping(manifest.get("primary_accounting"), "accounting primary_accounting") != scenario_manifests[primary_scenario_id]:
        raise V51EvaluationError("accounting primary_accounting does not match base_23bp scenario")

    selected_scenario_id = _scenario_id_for_cost_bp(cost_scenario_bp)
    selected_scenario = scenario_manifests[selected_scenario_id]
    slots = selected_scenario["ledger"]
    blockers = selected_scenario["blockers"]
    account_nav = _accounting_required_value(
        selected_scenario,
        ("account_nav_krw_decimal", "account_nav_krw"),
        "account_nav",
    )
    reserve_krw = _accounting_required_value(
        selected_scenario,
        ("reserve_cash_krw_decimal", "reserve_cash_krw"),
        "reserve_krw",
    )
    deployed_principal = _accounting_required_value(
        selected_scenario,
        ("deployed_principal_krw_decimal", "deployed_principal_krw"),
        "deployed_principal_krw",
    )

    return dict(
        selected_scenario,
        manifest=dict(manifest, scenario_manifests=scenario_manifests),
        scenario_manifest=dict(selected_scenario),
        scenario_manifests=scenario_manifests,
        slots=list(slots),
        account_nav=account_nav,
        reserve_krw=reserve_krw,
        deployed_principal_krw=deployed_principal,
        blockers=list(blockers),
        false_locks=false_locks,
        promotion_claims=promotion_claims,
        no_claims=no_claims,
        cost_scenario_id=selected_scenario_id,
        round_trip_cost_bp=cost_scenario_bp,
        accounting_manifest_sha256=declared_digest,
    )


def _require_accounting_manifest_header(manifest: Mapping[str, Any], *, variant: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != _ACCOUNTING_SCHEMA_VERSION:
        raise V51EvaluationError("accounting manifest schema_version mismatch")
    if manifest.get("horizon_id") != variant["horizon_id"]:
        raise V51EvaluationError("accounting manifest horizon_id does not match evaluated horizon")
    if manifest.get("horizon_days") != variant["horizon_days"]:
        raise V51EvaluationError("accounting manifest horizon_days does not match evaluated horizon")
    if manifest.get("label_column") != variant["label_column"]:
        raise V51EvaluationError("accounting manifest label_column does not match evaluated horizon")
    _require_accounting_price_contract(manifest, "accounting manifest")


def _validate_accounting_scenario_manifest(
    scenario: Mapping[str, Any],
    *,
    scenario_id: str,
    round_trip_cost_bp: int,
    variant: Mapping[str, Any],
) -> None:
    if scenario.get("schema_version") != _ACCOUNTING_SCHEMA_VERSION:
        raise V51EvaluationError(f"accounting scenario {scenario_id} schema_version mismatch")
    if scenario.get("horizon_id") != variant["horizon_id"]:
        raise V51EvaluationError(f"accounting scenario {scenario_id} horizon_id mismatch")
    if scenario.get("horizon_days") != variant["horizon_days"]:
        raise V51EvaluationError(f"accounting scenario {scenario_id} horizon_days mismatch")
    if scenario.get("label_column") != variant["label_column"]:
        raise V51EvaluationError(f"accounting scenario {scenario_id} label_column mismatch")
    if scenario.get("cost_scenario_id") != scenario_id:
        raise V51EvaluationError(f"accounting scenario {scenario_id} cost_scenario_id mismatch")
    if _cost_scenario_bp(
        scenario.get("round_trip_cost_bp"),
        f"accounting scenario {scenario_id} round_trip_cost_bp",
    ) != round_trip_cost_bp:
        raise V51EvaluationError(f"accounting scenario {scenario_id} round_trip_cost_bp mismatch")
    cost_scenario = _require_mapping(scenario.get("cost_scenario"), f"accounting scenario {scenario_id} cost_scenario")
    if cost_scenario.get("scenario_id") != scenario_id:
        raise V51EvaluationError(f"accounting scenario {scenario_id} cost_scenario payload mismatch")
    if _cost_scenario_bp(
        cost_scenario.get("total_bp"),
        f"accounting scenario {scenario_id} total_bp",
    ) != round_trip_cost_bp:
        raise V51EvaluationError(f"accounting scenario {scenario_id} total_bp mismatch")
    if _positive_int(scenario.get("cost_application_count"), f"accounting scenario {scenario_id} cost_application_count") != 1:
        raise V51EvaluationError(f"accounting scenario {scenario_id} cost_application_count mismatch")
    slots = scenario.get("ledger")
    if not isinstance(slots, list):
        raise V51EvaluationError(f"accounting scenario {scenario_id} ledger must be a list")
    if _positive_int(scenario.get("slot_count"), f"accounting scenario {scenario_id} slot_count") != len(slots):
        raise V51EvaluationError(f"accounting scenario {scenario_id} slot_count mismatch")
    blockers = scenario.get("blockers")
    if not isinstance(blockers, list):
        raise V51EvaluationError(f"accounting scenario {scenario_id} blockers must be a list")
    for index, slot in enumerate(slots):
        _validate_accounting_slot(slot, scenario_id=scenario_id, variant=variant, index=index)


def _validate_accounting_slot(
    slot: Any,
    *,
    scenario_id: str,
    variant: Mapping[str, Any],
    index: int,
) -> None:
    item = _require_mapping(slot, f"accounting slot {index}")
    if item.get("horizon_id") != variant["horizon_id"]:
        raise V51EvaluationError(f"accounting slot {index} horizon_id mismatch")
    if item.get("horizon_days") != variant["horizon_days"]:
        raise V51EvaluationError(f"accounting slot {index} horizon_days mismatch")
    if item.get("label_column") != variant["label_column"]:
        raise V51EvaluationError(f"accounting slot {index} label_column mismatch")
    if item.get("cost_scenario_id") != scenario_id:
        raise V51EvaluationError(f"accounting slot {index} cost_scenario_id mismatch")
    _require_accounting_price_contract(item, f"accounting slot {index}")


def _require_accounting_price_contract(payload: Mapping[str, Any], label: str) -> None:
    if payload.get("price_basis") != PRICE_BASIS:
        raise V51EvaluationError(f"{label} price_basis must be exact 15:20 proxy")
    if payload.get("official_close") is not False:
        raise V51EvaluationError(f"{label} official_close must be false")


def _accounting_required_value(payload: Mapping[str, Any], keys: Sequence[str], label: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    raise V51EvaluationError(f"accounting result missing required key: {label}")


def _exact_false_map(value: Mapping[str, Any], expected: Mapping[str, bool], label: str) -> dict[str, bool]:
    observed = {str(key): item for key, item in value.items()}
    if observed != dict(expected):
        raise V51EvaluationError(f"{label} must exactly match false claim locks")
    return dict(expected)


def _required_no_claim_labels(value: Any, label: str) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise V51EvaluationError(f"{label} must be a sequence")
    labels = [_text(item, f"{label} label") for item in value]
    if tuple(labels) != NO_CLAIM_LABELS:
        raise V51EvaluationError(f"{label} must exactly match required no-claim labels")
    return labels


def _horizon_gate(variant: Mapping[str, Any], blockers: Sequence[Any]) -> dict[str, Any]:
    reason_codes = ["ACCOUNTING_BLOCKERS"] if blockers else []
    return {
        "schema_version": HORIZON_GATE_SCHEMA_VERSION,
        "variant_id": variant["variant_id"],
        "horizon_id": variant["horizon_id"],
        "role": variant["role"],
        "primary": variant["variant_id"] == PRIMARY_VARIANT_ID,
        "status": "PASS" if not blockers else "FAIL",
        "reason_codes": reason_codes,
        "blockers": list(blockers),
        "requires_exact_1520_entry_exit": True,
        "requires_pre_test_oos_freeze": True,
        "economic_nav_from_accounting": True,
        "live_trading_claim": False,
        "paper_trading_claim": False,
        "broker_integration_claim": False,
        "profit_claim": False,
    }


def _validate_horizon_manifest_shape(
    item: Mapping[str, Any],
    *,
    variant: Mapping[str, Any],
    panel_sha256: str,
    source_hashes: Mapping[str, Any],
    split: Mapping[str, Any],
    split_digest: str,
    fixed_at: str | None,
    sequence: int | None,
    cost_scenario_bp: int,
) -> None:
    expected = {
        "schema_version": HORIZON_MANIFEST_SCHEMA_VERSION,
        "variant_id": variant["variant_id"],
        "role": variant["role"],
        "horizon_id": variant["horizon_id"],
        "horizon_days": variant["horizon_days"],
        "label_column": variant["label_column"],
        "price_basis": PRICE_BASIS,
        "panel_schema_version": CAUSAL_PANEL_SCHEMA_VERSION,
        "panel_sha256": panel_sha256,
        "source_hashes": source_hashes,
        "split_identity_sha256": split_digest,
        "split_identity": split,
        "selection_fixed_at": fixed_at,
        "selection_sequence": sequence,
        "selection_lock": "FROZEN_BEFORE_UNTOUCHED_TEST_AND_OOS",
        "horizon_choice_source": split["horizon_choice_source"],
        "cost_scenario_bp": cost_scenario_bp,
    }
    for key, value in expected.items():
        if item.get(key) != value:
            raise V51EvaluationError(f"horizon manifest {variant['variant_id']} {key} drifted")
    selected_rows = item.get("selected_rows")
    if not isinstance(selected_rows, list):
        raise V51EvaluationError(f"horizon manifest {variant['variant_id']} selected_rows must be a list")
    if item.get("selected_count") != len(selected_rows):
        raise V51EvaluationError(f"horizon manifest {variant['variant_id']} selected_count mismatch")
    seen_symbols: set[str] = set()
    for ordinal, row in enumerate(selected_rows, start=1):
        selection = _require_mapping(row, f"horizon manifest {variant['variant_id']} selected row")
        symbol = _symbol(selection.get("symbol"), "selected row symbol")
        if symbol in seen_symbols:
            raise V51EvaluationError(f"duplicate selected symbol for {variant['variant_id']}: {symbol}")
        seen_symbols.add(symbol)
        if selection.get("variant_id") != variant["variant_id"]:
            raise V51EvaluationError("selected row variant_id drifted")
        if selection.get("horizon_id") != variant["horizon_id"]:
            raise V51EvaluationError("selected row horizon_id drifted")
        if selection.get("label_column") != variant["label_column"]:
            raise V51EvaluationError("selected row label_column drifted")
        if selection.get("selection_ordinal") != ordinal:
            raise V51EvaluationError("selected row selection_ordinal drifted")
        _date(selection.get("session"), "selected row session")


def _validate_split_identity(split_identity: Mapping[str, Any]) -> dict[str, Any]:
    split = _require_mapping(split_identity, "split_identity")
    _reject_future_return_1d(split, "split_identity")
    missing = sorted(_REQUIRED_SPLIT_KEYS - set(split))
    if missing:
        raise V51EvaluationError(f"split_identity missing required key: {missing[0]}")
    normalized = dict(split)
    for key in ("split_id", "train_split_id", "validation_split_id", "untouched_test_split_id", "oos_split_id"):
        normalized[key] = _text(normalized[key], f"split_identity {key}")
    source = _text(normalized["horizon_choice_source"], "split_identity horizon_choice_source")
    if source not in _ALLOWED_HORIZON_CHOICE_SOURCES:
        raise V51EvaluationError("horizon choice source must be train/validation only and fixed before untouched test/OOS")
    normalized["horizon_choice_source"] = source
    for flag in _FORBIDDEN_TRUE_SPLIT_FLAGS:
        if bool(normalized.get(flag, False)) is True:
            raise V51EvaluationError("test/OOS-driven horizon choice or post-hoc retuning is forbidden")
        if flag in normalized:
            normalized[flag] = False
    return normalized


def _normalize_selection_marker(fixed_at: Any, sequence: Any) -> tuple[str | None, int | None]:
    fixed_at_value: str | None = None
    sequence_value: int | None = None
    if fixed_at is not None:
        fixed_at_value = _text(fixed_at, "selection_fixed_at")
        if _UTC_SECONDS_RE.fullmatch(fixed_at_value) is None:
            raise V51EvaluationError("selection_fixed_at must be canonical UTC seconds ending in Z")
    if sequence is not None:
        sequence_value = _positive_int(sequence, "selection_sequence")
    if fixed_at_value is None and sequence_value is None:
        raise V51EvaluationError("a selection_fixed_at timestamp or selection_sequence marker is required")
    return fixed_at_value, sequence_value


def _panel_row_lookup(
    panel: Mapping[str, Any],
) -> tuple[dict[tuple[str, str], tuple[int, Mapping[str, Any]]], dict[str, list[tuple[str, int, Mapping[str, Any]]]]]:
    lookup: dict[tuple[str, str], tuple[int, Mapping[str, Any]]] = {}
    by_symbol: dict[str, list[tuple[str, int, Mapping[str, Any]]]] = defaultdict(list)
    rows = panel.get("rows")
    if not isinstance(rows, list):
        raise V51EvaluationError("validated panel rows must be a list")
    for index, row in enumerate(rows):
        item = _require_mapping(row, f"panel row {index}")
        symbol = _symbol(item.get("symbol"), "panel row symbol")
        session = _date(item.get("session"), "panel row session")
        key = (symbol, session)
        if key in lookup:
            raise V51EvaluationError(f"duplicate panel row for {symbol} {session}")
        lookup[key] = (index, item)
        by_symbol[symbol].append((session, index, item))
    return lookup, by_symbol


def _source_hashes(panel: Mapping[str, Any]) -> dict[str, Any]:
    source_identity = _require_mapping(panel.get("source_identity"), "panel source_identity")
    return {
        "source_db_path": str(source_identity["source_db_path"]),
        "source_db_sha256": str(source_identity["source_db_sha256"]),
        "source_identity_sha256": str(source_identity["source_identity_sha256"]),
        "source_tables": list(source_identity["source_tables"]),
        "panel_sha256": str(panel["panel_sha256"]),
    }


def _exact_price(payload: Mapping[str, Any], label: str) -> str:
    if payload.get("price_basis") != PRICE_BASIS or payload.get("official_close") is not False:
        raise V51EvaluationError(f"{label} must be exact 15:20 proxy, not official close")
    value = payload.get("price_1520_close_proxy", payload.get("close"))
    return _positive_decimal_string(value, f"{label} price")


def _positive_decimal_string(value: Any, label: str) -> str:
    if value is None or isinstance(value, bool):
        raise V51EvaluationError(f"{label} must be a positive decimal")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise V51EvaluationError(f"{label} must be a positive decimal") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise V51EvaluationError(f"{label} must be a positive decimal")
    return str(value)


def _floor_v51_quantity_for_accounting(entry_price: Any) -> int:
    entry = Decimal(str(entry_price))
    effective_unit_cost = entry * (Decimal("1") + (_V51_STRESS_BUY_SIDE_COST_BP / _BP_DENOMINATOR))
    quantity = int((_V51_SLOT_BUY_BUDGET_KRW / effective_unit_cost).to_integral_value(rounding=ROUND_FLOOR))
    if quantity <= 0:
        raise V51EvaluationError("V51_SLOT_BUDGET_NO_WHOLE_SHARE")
    return quantity


def _explicit_quantity(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        raise V51EvaluationError("explicit quantity must be positive when supplied")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise V51EvaluationError("explicit quantity must be positive when supplied") from exc
    if not parsed.is_finite() or parsed <= 0 or parsed != parsed.to_integral_value():
        raise V51EvaluationError("explicit quantity must be a positive whole-share integer when supplied")
    return int(parsed)


def _false_map(value: Mapping[str, Any], label: str) -> dict[str, bool]:
    result = {str(key): item for key, item in value.items()}
    if any(item is not False for item in result.values()):
        raise V51EvaluationError(f"{label} must contain false labels only")
    return {key: False for key in sorted(result)}


def _variant_by_id() -> dict[str, Mapping[str, Any]]:
    return {str(variant["variant_id"]): variant for variant in HORIZON_VARIANTS}


def _attach_digest(payload: Mapping[str, Any], *, digest_field: str = "manifest_sha256") -> dict[str, Any]:
    result = dict(payload)
    result[digest_field] = canonical_manifest_sha256(result, digest_field=digest_field)
    return result


def _canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(_jsonable(item) for item in value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise V51EvaluationError("non-finite float is not manifest-canonical")
        return value
    return value


def _reject_future_return_1d(value: Any, label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) == "future_return_1d":
                raise V51EvaluationError(f"{label} must not contain or alias future_return_1d")
            if str(key) in _FORBIDDEN_LEGACY_VALUE_KEYS and isinstance(item, str) and item == "future_return_1d":
                raise V51EvaluationError(f"{label} must not contain or alias future_return_1d")
            _reject_future_return_1d(item, label)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _reject_future_return_1d(item, label)


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise V51EvaluationError(f"{label} must be a mapping")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise V51EvaluationError(f"{label} must be a non-empty string")
    return value


def _symbol(value: Any, label: str) -> str:
    text = _text(value, label)
    if _SYMBOL_RE.fullmatch(text) is None:
        raise V51EvaluationError(f"{label} must be a six-digit code")
    return text


def _date(value: Any, label: str) -> str:
    text = _text(value, label)
    if _DATE_RE.fullmatch(text) is None:
        raise V51EvaluationError(f"{label} must be YYYY-MM-DD")
    return text


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise V51EvaluationError(f"{label} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise V51EvaluationError(f"{label} must be a positive integer") from exc
    if str(value).strip() not in {str(parsed), f"+{parsed}"} and not isinstance(value, int):
        raise V51EvaluationError(f"{label} must be a positive integer")
    if parsed <= 0:
        raise V51EvaluationError(f"{label} must be a positive integer")
    return parsed


def _cost_scenario_bp(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise V51EvaluationError(f"{label} must be one of 0, 23, or 46")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise V51EvaluationError(f"{label} must be one of 0, 23, or 46") from exc
    if str(value).strip() not in {str(parsed), f"+{parsed}"} and not isinstance(value, int):
        raise V51EvaluationError(f"{label} must be one of 0, 23, or 46")
    if parsed not in _V51_COST_SCENARIO_ID_BY_BP:
        raise V51EvaluationError(f"{label} must be one of 0, 23, or 46")
    return parsed


def _scenario_id_for_cost_bp(cost_scenario_bp: int) -> str:
    return _V51_COST_SCENARIO_ID_BY_BP[_cost_scenario_bp(cost_scenario_bp, "cost_scenario_bp")]


def _finite_json_number(value: Any, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise V51EvaluationError(f"{label} must be a finite JSON number")
    return value


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


__all__ = [
    "EVALUATOR_SCHEMA_VERSION",
    "FREEZE_SCHEMA_VERSION",
    "HORIZON_MANIFEST_SCHEMA_VERSION",
    "HORIZON_RESULT_SCHEMA_VERSION",
    "HORIZON_GATE_SCHEMA_VERSION",
    "HORIZON_VARIANTS",
    "MISSING_1520_ENTRY_BAR",
    "MISSING_1520_EXIT_BAR",
    "NO_CLAIM_LABELS",
    "PRIMARY_VARIANT_ID",
    "VALIDATION_VARIANT_IDS",
    "VARIANT_ORDER",
    "V51EvaluationError",
    "canonical_manifest_sha256",
    "evaluate_v51_horizon_variants",
    "freeze_v51_horizon_variants",
    "validate_v51_freeze_manifest",
]
