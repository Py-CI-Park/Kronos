"""Deterministic aggregate mechanics for the frozen daily Portfolio SB3 protocol.

This module is intentionally synthetic/reporting-only.  It consumes the immutable
``daily_portfolio_sb3_protocol`` matrix, conserves all 50 protocol cells, and
summarizes supplied cell records without training, reading fresh OOS data, or
promoting model quality claims.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any, Final

import numpy as np

from stom_rl import daily_portfolio_sb3_protocol as protocol


AGGREGATE_SCHEMA: Final = "kronos_daily_sb3_aggregate.v1"
PRIMARY_VARIANT_ID: Final = "cost-23bp"
PRIMARY_COST_BPS: Final = 23
BOOTSTRAP_REPLICATES: Final = 10_000
BOOTSTRAP_SEED: Final = 0
BOOTSTRAP_CI_LOWER_INDEX: Final = 249
BOOTSTRAP_CI_UPPER_INDEX: Final = 9749
INVALID_ACTION_STOP_THRESHOLD: Final = 0.05
MAX_DRAWDOWN_NO_GO_THRESHOLD_PCT: Final = -20.0
SB3_ACCOUNTING_HORIZON: Final = "SB3_T_DECIDE_T1_FILL_STATEFUL_V1"
ECONOMIC_NET_RETURN_FIELD: Final = "economic_net_return"
ECONOMIC_NET_RETURN_UNIT_FIELD: Final = "economic_net_return_unit"
ECONOMIC_NET_RETURN_COST_BPS_FIELD: Final = "economic_net_return_cost_bps"
ECONOMIC_NET_RETURN_HORIZON_FIELD: Final = "economic_net_return_horizon"
ECONOMIC_NET_RETURN_UNIT: Final = "fraction"
SHAPED_REWARD_ALIAS_FIELDS: Final = frozenset(
    {
        "avg_episode_net_return_pct",
        "avg_reward",
        "economic_return",
        "episode_reward",
        "net_return",
        "profit",
        "mean_daily_reward",
        "policy_reward",
        "return",
        "return_pct",
        "reward",
        "reward_mean",
        "reward_total",
        "train_reward",
        "training_reward",
        "shaped_reward",
        "total_net_return",
        "total_reward",
        "total_shaped_reward",
    }
)
FOLD_OFFSET_SEED_ALIAS_FIELDS: Final = frozenset(
    {
        "effective_seed",
        "base_seed_plus_fold",
        "fold_adjusted_seed",
        "fold_offset_seed",
        "fold_offset_rng_seed",
        "fold_plus_seed",
        "fold_seed_offset",
        "fold_seed",
        "rng_seed_fold_offset",
        "rng_seed_offset",
        "seed_offset",
        "seed_plus_fold",
        "seed_plus_fold_index",
        "seed_with_fold_offset",
    }
)

COMPLETED_STATUSES: Final = frozenset({"COMPLETED", "DONE", "SUCCEEDED", "SUCCESS", "PASS"})
STOPPED_STATUSES: Final = frozenset({"STOPPED", "STOP", "CANCELLED", "CANCELED"})
FAILED_STATUSES: Final = frozenset({"FAILED", "FAIL", "ERROR"})
RUNNING_STATUSES: Final = frozenset({"RUNNING", "PENDING", "QUEUED", "NOT_RUN"})

COMPARATOR_ALIASES: Final = {
    "no_trade": "no_trade_cash",
    "no-trade": "no_trade_cash",
    "notrade": "no_trade_cash",
    "cash": "no_trade_cash",
    "shuffle": "shuffle_control",
    "deterministic_shuffle": "shuffle_control",
    "shuffle_top10": "shuffle_control",
    "equal_weight": "equal_weight_topk_momentum",
    "momentum": "equal_weight_topk_momentum",
    "equal_weight_momentum": "equal_weight_topk_momentum",
    "ts_imb": "ts_imb_rule_baseline",
    "ts_imb_rule": "ts_imb_rule_baseline",
    "rule_baseline": "ts_imb_rule_baseline",
    "buy_hold": "buy_and_hold_cash",
    "buy-and-hold": "buy_and_hold_cash",
    "buy_and_hold": "buy_and_hold_cash",
    "ppo": "ppo_policy",
    "ppo_policy": "ppo_policy",
}


class DailyPortfolioSb3AggregateError(ValueError):
    """Raised when aggregate inputs cannot be bound to the frozen protocol."""


def canonical_bytes(value: Any) -> bytes:
    """Return RFC 8785 bytes using the protocol module's canonicalizer."""

    return protocol.canonical_bytes(value)


def aggregate_sha256(value: Any) -> str:
    """Return a SHA-256 digest over canonical aggregate bytes."""

    return protocol.sha256_hex(canonical_bytes(value))


def _protocol_value(value: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    frozen = protocol.build_protocol() if value is None else value
    protocol.validate_protocol(frozen)
    return frozen


def _cell_key(seed_id: str, fold_id: str, variant_id: str) -> tuple[str, str, str]:
    return (seed_id, fold_id, variant_id)


def _expected_cells(frozen: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cells = list(frozen["matrix"]["cells"])
    if len(cells) != 50:
        raise DailyPortfolioSb3AggregateError("protocol matrix does not contain exactly 50 cells")
    return cells


def _records_from_payload(payload: Any) -> Sequence[Any]:
    if isinstance(payload, Mapping):
        for key in ("cells", "records", "cell_records"):
            records = payload.get(key)
            if records is not None:
                if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)):
                    raise DailyPortfolioSb3AggregateError(f"{key} must be a sequence of cell records")
                return records
        raise DailyPortfolioSb3AggregateError("payload must contain cells, records, or cell_records")
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return payload
    raise DailyPortfolioSb3AggregateError("aggregate input must be a cell-record sequence or mapping payload")


def _as_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DailyPortfolioSb3AggregateError(f"{label} must be an object")
    return value


def _normalize_status(value: Any) -> str:
    status = str(value or "COMPLETED").strip().upper().replace("-", "_")
    if status in COMPLETED_STATUSES:
        return "COMPLETED"
    if status in STOPPED_STATUSES:
        return "STOPPED"
    if status in FAILED_STATUSES:
        return "FAILED"
    if status in RUNNING_STATUSES:
        return status
    return status or "COMPLETED"


def _observed_seed_int(value: Any, *, label: str) -> int:
    if value is None or isinstance(value, bool):
        raise DailyPortfolioSb3AggregateError(f"{label} must be the protocol integer seed")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise DailyPortfolioSb3AggregateError(f"{label} must be the protocol integer seed") from exc
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise DailyPortfolioSb3AggregateError(f"{label} must be the protocol integer seed")
    return int(numeric)


def _validate_observed_seed_identity(record: Mapping[str, Any], cell: Mapping[str, Any], *, label: str) -> None:
    sources: list[Mapping[str, Any]] = [record]
    nested_cell = record.get("cell")
    if isinstance(nested_cell, Mapping) and nested_cell is not record:
        sources.append(nested_cell)
    expected_seed = int(cell["seed"])
    observed_fields: set[str] = set()
    for source in sources:
        for alias in FOLD_OFFSET_SEED_ALIAS_FIELDS:
            if alias in source:
                raise DailyPortfolioSb3AggregateError(
                    f"{label}.{alias} is a forbidden fold-offset seed alias; base_seed/rng_seed must equal the protocol cell seed"
                )
        for field in ("base_seed", "rng_seed", "seed"):
            if field in source:
                observed = _observed_seed_int(source[field], label=f"{label}.{field}")
                if field in {"base_seed", "rng_seed"}:
                    observed_fields.add(field)
                if observed != expected_seed:
                    raise DailyPortfolioSb3AggregateError(
                        f"{label}.{field}={observed} does not match protocol seed {expected_seed}"
                    )
    for field in ("base_seed", "rng_seed"):
        if field not in observed_fields:
            raise DailyPortfolioSb3AggregateError(f"{label}.{field} is missing; explicit observed base_seed/rng_seed are required")


def _record_key(record: Mapping[str, Any], *, by_cell_uid: Mapping[str, Mapping[str, Any]], by_key: Mapping[tuple[str, str, str], Mapping[str, Any]]) -> tuple[str, str, str]:
    identity = record.get("cell") if isinstance(record.get("cell"), Mapping) else record
    cell_uid = identity.get("cell_uid")
    if isinstance(cell_uid, str) and cell_uid:
        cell = by_cell_uid.get(cell_uid)
        if cell is None:
            raise DailyPortfolioSb3AggregateError(f"record references non-protocol cell_uid: {cell_uid}")
        derived = _cell_key(str(cell["seed_id"]), str(cell["fold_id"]), str(cell["variant_id"]))
        for field, expected in (("seed_id", derived[0]), ("fold_id", derived[1]), ("variant_id", derived[2])):
            if field in identity and str(identity[field]) != expected:
                raise DailyPortfolioSb3AggregateError(f"record {cell_uid} {field} does not match protocol")
        _validate_observed_seed_identity(record, cell, label=f"record {cell_uid}")
        return derived

    try:
        key = _cell_key(str(identity["seed_id"]), str(identity["fold_id"]), str(identity["variant_id"]))
    except KeyError as exc:
        raise DailyPortfolioSb3AggregateError("record must carry cell_uid or seed_id/fold_id/variant_id") from exc
    cell = by_key.get(key)
    if cell is None:
        raise DailyPortfolioSb3AggregateError(f"record key is outside the frozen protocol matrix: {key}")
    _validate_observed_seed_identity(record, cell, label=f"record {key}")
    return key


def _finite_float(value: Any, *, label: str) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{label} is not finite")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not finite") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} is not finite")
    return result


def _metric_count(value: Any, *, label: str, positive: bool = False) -> int:
    numeric = _finite_float(value, label=label)
    if numeric < 0 or not float(numeric).is_integer():
        raise ValueError(f"{label} must be a non-negative integer")
    if positive and numeric <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return int(numeric)


def _reject_return_aliases(metrics: Mapping[str, Any], *, label: str) -> None:
    aliases = sorted(key for key in SHAPED_REWARD_ALIAS_FIELDS if key in metrics)
    if aliases:
        raise ValueError(
            f"{label} contains shaped reward or legacy return aliases {aliases}; use {ECONOMIC_NET_RETURN_FIELD} with unit/cost/horizon"
        )


def _metric_return(metrics: Mapping[str, Any], *, label: str, expected_cost_bps: int) -> float:
    _reject_return_aliases(metrics, label=label)
    if ECONOMIC_NET_RETURN_FIELD not in metrics:
        raise ValueError(f"{label}.{ECONOMIC_NET_RETURN_FIELD} is missing")
    unit = metrics.get(ECONOMIC_NET_RETURN_UNIT_FIELD)
    if unit != ECONOMIC_NET_RETURN_UNIT:
        raise ValueError(f"{label}.{ECONOMIC_NET_RETURN_UNIT_FIELD} must be {ECONOMIC_NET_RETURN_UNIT!r}")
    cost_bps = _finite_float(metrics.get(ECONOMIC_NET_RETURN_COST_BPS_FIELD), label=f"{label}.{ECONOMIC_NET_RETURN_COST_BPS_FIELD}")
    if cost_bps != float(expected_cost_bps):
        raise ValueError(
            f"{label}.{ECONOMIC_NET_RETURN_COST_BPS_FIELD}={cost_bps:g} does not match protocol cost {expected_cost_bps}"
        )
    horizon = metrics.get(ECONOMIC_NET_RETURN_HORIZON_FIELD)
    if horizon != SB3_ACCOUNTING_HORIZON:
        raise ValueError(f"{label}.{ECONOMIC_NET_RETURN_HORIZON_FIELD} must be {SB3_ACCOUNTING_HORIZON!r}")
    return _finite_float(metrics[ECONOMIC_NET_RETURN_FIELD], label=f"{label}.{ECONOMIC_NET_RETURN_FIELD}")


def _metric_mdd_pct(metrics: Mapping[str, Any], *, label: str) -> float:
    if "max_drawdown_pct" not in metrics:
        raise ValueError(f"{label}.max_drawdown_pct is missing")
    return _finite_float(metrics["max_drawdown_pct"], label=f"{label}.max_drawdown_pct")


def _metric_trade_count(metrics: Mapping[str, Any], *, label: str) -> int:
    if "trade_count" not in metrics:
        raise ValueError(f"{label}.trade_count is missing")
    return _metric_count(metrics["trade_count"], label=f"{label}.trade_count")


def _metric_invalid(metrics: Mapping[str, Any], *, label: str) -> tuple[int, int, float]:
    if "raw_invalid_action_count" not in metrics:
        raise ValueError(f"{label}.raw_invalid_action_count is missing")
    if "eval_step_count" not in metrics:
        raise ValueError(f"{label}.eval_step_count is missing")
    invalid_count = _metric_count(metrics["raw_invalid_action_count"], label=f"{label}.raw_invalid_action_count")
    step_count = _metric_count(metrics["eval_step_count"], label=f"{label}.eval_step_count", positive=True)
    if invalid_count > step_count:
        raise ValueError(f"{label}.raw_invalid_action_count exceeds eval_step_count")
    return invalid_count, step_count, float(invalid_count) / float(step_count)


def _extract_metrics(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("metrics")
    if isinstance(value, Mapping):
        return value
    forbidden_containers = (
        "primary_metrics",
        "result",
        "test_oos_primary",
        "untouched_test_oos_primary_metrics",
        "validation_primary_metrics",
    )
    for key in forbidden_containers:
        if key in record:
            raise ValueError(f"{key} is not an accepted synthetic aggregate metrics container; use metrics")
    metric_keys = {
        ECONOMIC_NET_RETURN_FIELD,
        ECONOMIC_NET_RETURN_UNIT_FIELD,
        ECONOMIC_NET_RETURN_COST_BPS_FIELD,
        ECONOMIC_NET_RETURN_HORIZON_FIELD,
        "eval_step_count",
        "max_drawdown",
        "max_drawdown_pct",
        "mdd",
        "raw_invalid_action_count",
        "trade_count",
        *SHAPED_REWARD_ALIAS_FIELDS,
    }
    if any(key in record for key in metric_keys):
        raise ValueError("completed cell metrics must be nested under metrics")
    raise ValueError("completed cell metrics are missing")


def _comparator_id(value: Any) -> str | None:
    key = str(value or "").strip()
    if not key:
        return None
    normalized = key.lower().replace(" ", "_")
    return COMPARATOR_ALIASES.get(normalized, normalized if normalized in protocol.COMPARATOR_ORDER else None)


def _extract_comparators(
    record: Mapping[str, Any],
    metrics: Mapping[str, Any],
    *,
    label: str,
    expected_cost_bps: int,
) -> tuple[dict[str, float], list[str], list[str]]:
    errors: list[str] = []
    observed: dict[str, list[float]] = {}
    sources = []
    for owner in (record, metrics):
        for key in ("comparators", "comparator_metrics", "baseline_metrics", "baselines"):
            value = owner.get(key) if isinstance(owner, Mapping) else None
            if value is not None:
                sources.append(value)
    for source in sources:
        if isinstance(source, Mapping):
            iterable = source.items()
        elif isinstance(source, Sequence) and not isinstance(source, (str, bytes, bytearray)):
            rows: list[tuple[Any, Any]] = []
            for row in source:
                if not isinstance(row, Mapping):
                    errors.append(f"{label}.comparators row is not an object")
                    continue
                raw_name = row.get("comparator_id", row.get("strategy", row.get("policy", row.get("name"))))
                rows.append((raw_name, row))
            iterable = rows
        else:
            errors.append(f"{label}.comparators has invalid shape")
            continue
        for raw_name, raw_metric in iterable:
            comparator = _comparator_id(raw_name)
            if comparator is None or comparator == "ppo_policy":
                continue
            try:
                if not isinstance(raw_metric, Mapping):
                    raise ValueError(
                        f"{label}.comparators.{comparator} must be an explicit economic net-return object with unit/cost/horizon"
                    )
                observed.setdefault(comparator, []).append(
                    _metric_return(
                        raw_metric,
                        label=f"{label}.comparators.{comparator}",
                        expected_cost_bps=expected_cost_bps,
                    )
                )
            except ValueError as exc:
                errors.append(str(exc))
    selected: dict[str, float] = {}
    duplicate_ids: list[str] = []
    for comparator in sorted(observed):
        values = observed[comparator]
        if len(values) == 1:
            selected[comparator] = values[0]
        else:
            duplicate_ids.append(comparator)
    return selected, errors, duplicate_ids


def _normal_metrics(record: Mapping[str, Any], *, cell: Mapping[str, Any], label: str) -> tuple[dict[str, Any] | None, dict[str, float], list[str], list[str]]:
    try:
        expected_cost_bps = int(cell["evaluation_cost_bps"])
        metrics = _extract_metrics(record)
        net_return = _metric_return(metrics, label=label, expected_cost_bps=expected_cost_bps)
        mdd_pct = _metric_mdd_pct(metrics, label=label)
        trade_count = _metric_trade_count(metrics, label=label)
        invalid_count, step_count, invalid_rate = _metric_invalid(metrics, label=label)
        comparators, comparator_errors, duplicate_comparator_ids = _extract_comparators(record, metrics, label=label, expected_cost_bps=expected_cost_bps)
        normalized = {
            "net_return": net_return,
            "economic_net_return": net_return,
            "economic_net_return_unit": ECONOMIC_NET_RETURN_UNIT,
            "economic_net_return_cost_bps": expected_cost_bps,
            "economic_net_return_horizon": SB3_ACCOUNTING_HORIZON,
            "max_drawdown_pct": mdd_pct,
            "trade_count": trade_count,
            "invalid_action_count": invalid_count,
            "eval_step_count": step_count,
            "invalid_action_rate": invalid_rate,
        }
        return normalized, comparators, comparator_errors, duplicate_comparator_ids
    except ValueError as exc:
        return None, {}, [str(exc)], []


def compute_iqm(values: Sequence[float], *, expected_seed_count: int = 5) -> float:
    """Return the five-seed interquartile mean with exact .3/.4/.3 weights.

    Passing ten fold metrics instead of five base-seed metrics is rejected rather
    than silently treating folds as independent seeds.
    """

    if len(values) != expected_seed_count:
        raise DailyPortfolioSb3AggregateError(
            f"IQM requires exactly {expected_seed_count} base-seed values; got {len(values)}"
        )
    if expected_seed_count != 5:
        raise DailyPortfolioSb3AggregateError("the frozen protocol defines exactly five base seeds")
    sorted_values = sorted(_finite_float(value, label="iqm.value") for value in values)
    return (0.3 * sorted_values[1]) + (0.4 * sorted_values[2]) + (0.3 * sorted_values[3])


def paired_bootstrap_iqm_ci(
    paired_deltas: Sequence[float],
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Return a paired PCG64 seed-0 bootstrap CI over five base-seed deltas."""

    if len(paired_deltas) != 5:
        raise DailyPortfolioSb3AggregateError(
            f"paired bootstrap requires exactly five base-seed deltas; got {len(paired_deltas)}"
        )
    if replicates != BOOTSTRAP_REPLICATES:
        raise DailyPortfolioSb3AggregateError("the frozen bootstrap uses exactly 10000 replicates")
    if seed != BOOTSTRAP_SEED:
        raise DailyPortfolioSb3AggregateError("the frozen bootstrap seed is pinned to 0")
    values = np.asarray([_finite_float(value, label="paired_delta") for value in paired_deltas], dtype=np.float64)
    generator = np.random.Generator(np.random.PCG64(seed))
    indices = generator.integers(0, len(values), size=(replicates, len(values)))
    sampled = np.sort(values[indices], axis=1)
    iqm_samples = (0.3 * sampled[:, 1]) + (0.4 * sampled[:, 2]) + (0.3 * sampled[:, 3])
    ordered = np.sort(iqm_samples)
    return {
        "method": "paired_iqm_delta_bootstrap",
        "bit_generator": "PCG64",
        "seed": seed,
        "replicates": replicates,
        "ci_indices": {"lower": BOOTSTRAP_CI_LOWER_INDEX, "upper": BOOTSTRAP_CI_UPPER_INDEX},
        "lower": float(ordered[BOOTSTRAP_CI_LOWER_INDEX]),
        "upper": float(ordered[BOOTSTRAP_CI_UPPER_INDEX]),
    }


def _aggregate_fold_metrics(seed_id: str, variant_id: str, fold_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    usable_by_fold: dict[str, Mapping[str, Any]] = {}
    for row in fold_rows:
        if row.get("status") != "COMPLETED" or not isinstance(row.get("metrics"), Mapping) or row.get("metric_errors"):
            continue
        fold_id = str(row.get("fold_id", ""))
        if fold_id in usable_by_fold:
            return None
        usable_by_fold[fold_id] = row
    if set(usable_by_fold) != set(protocol.FOLD_IDS):
        return None
    usable = [usable_by_fold[fold_id] for fold_id in protocol.FOLD_IDS]
    returns = [float(row["metrics"]["net_return"]) for row in usable]
    cost_bps = int(usable[0]["evaluation_cost_bps"])
    net_return = sum(returns) / float(len(returns))
    mdds = [float(row["metrics"]["max_drawdown_pct"]) for row in usable]
    trades = [int(row["metrics"]["trade_count"]) for row in usable]
    invalid_counts = [row["metrics"].get("invalid_action_count") for row in usable]
    step_counts = [row["metrics"].get("eval_step_count") for row in usable]
    if all(isinstance(value, int) for value in invalid_counts) and all(isinstance(value, int) for value in step_counts):
        invalid_count = int(sum(int(value) for value in invalid_counts))
        step_count = int(sum(int(value) for value in step_counts))
        invalid_rate = float(invalid_count) / float(step_count) if step_count else 0.0
    else:
        invalid_count = None
        step_count = None
        invalid_rate = max(float(row["metrics"].get("invalid_action_rate", 0.0)) for row in usable)
    return {
        "seed_id": seed_id,
        "variant_id": variant_id,
        "fold_ids": list(protocol.FOLD_IDS),
        "fold_count": len(usable),
        "net_return": net_return,
        "economic_net_return": net_return,
        "economic_net_return_unit": ECONOMIC_NET_RETURN_UNIT,
        "economic_net_return_cost_bps": cost_bps,
        "economic_net_return_horizon": SB3_ACCOUNTING_HORIZON,
        "max_drawdown_pct": min(mdds),
        "trade_count": int(sum(trades)),
        "invalid_action_count": invalid_count,
        "eval_step_count": step_count,
        "invalid_action_rate": invalid_rate,
    }


def _aggregate_comparator_seed_returns(
    cells: Sequence[Mapping[str, Any]],
    seed_metrics_by_variant: Mapping[str, list[dict[str, Any]]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    by_seed_variant = {
        (str(row["seed_id"]), str(row["variant_id"])): row
        for rows in seed_metrics_by_variant.values()
        for row in rows
    }
    comparator_fold_values: dict[tuple[str, str, str], list[float]] = {}
    duplicate_fold_keys: set[tuple[str, str, str]] = set()

    for cell in cells:
        if (
            cell["variant_id"] != PRIMARY_VARIANT_ID
            or cell.get("status") != "COMPLETED"
            or cell.get("state") != "PASS"
        ):
            continue
        seed_id = str(cell["seed_id"])
        fold_id = str(cell["fold_id"])
        comparators = cell.get("comparators") if isinstance(cell.get("comparators"), Mapping) else {}
        for raw_comparator, value in comparators.items():
            comparator = _comparator_id(raw_comparator)
            if comparator is None or comparator == "ppo_policy":
                continue
            comparator_fold_values.setdefault((seed_id, fold_id, comparator), []).append(float(value))
        for raw_comparator in cell.get("comparator_duplicate_ids") or []:
            comparator = _comparator_id(raw_comparator)
            if comparator is not None and comparator != "ppo_policy":
                duplicate_fold_keys.add((seed_id, fold_id, comparator))

    expected_fold_ids = list(protocol.FOLD_IDS)
    expected_seed_ids = [str(seed["seed_id"]) for seed in protocol.SEEDS]
    result: dict[str, list[dict[str, Any]]] = {}
    coverage: dict[str, dict[str, Any]] = {}

    for comparator in protocol.COMPARATOR_ORDER:
        rows: list[dict[str, Any]] = []
        seed_coverage: list[dict[str, Any]] = []
        if comparator == "ppo_policy":
            rows = [dict(row) for row in seed_metrics_by_variant.get(PRIMARY_VARIANT_ID, [])]
            by_seed = {str(row["seed_id"]): row for row in rows}
            for seed_id in expected_seed_ids:
                row = by_seed.get(seed_id)
                observed_fold_ids = list(row.get("fold_ids", [])) if isinstance(row, Mapping) else []
                complete = observed_fold_ids == expected_fold_ids
                seed_coverage.append(
                    {
                        "seed_id": seed_id,
                        "expected_fold_ids": expected_fold_ids,
                        "observed_fold_ids": observed_fold_ids,
                        "missing_fold_ids": [fold_id for fold_id in expected_fold_ids if fold_id not in observed_fold_ids],
                        "duplicate_fold_ids": [],
                        "complete": complete,
                    }
                )
        else:
            for seed_id in expected_seed_ids:
                observed_fold_ids: list[str] = []
                duplicate_fold_ids: list[str] = []
                values: list[float] = []

                if comparator == "no_trade_cash":
                    no_trade = by_seed_variant.get((seed_id, "no-trade"))
                    if no_trade is not None and list(no_trade.get("fold_ids", [])) == expected_fold_ids:
                        observed_fold_ids = list(expected_fold_ids)
                        values = [float(no_trade["net_return"])]
                else:
                    for fold_id in expected_fold_ids:
                        key = (seed_id, fold_id, comparator)
                        fold_values = comparator_fold_values.get(key, [])
                        if len(fold_values) == 1 and key not in duplicate_fold_keys:
                            observed_fold_ids.append(fold_id)
                            values.append(fold_values[0])
                        elif fold_values or key in duplicate_fold_keys:
                            duplicate_fold_ids.append(fold_id)

                missing_fold_ids = [
                    fold_id
                    for fold_id in expected_fold_ids
                    if fold_id not in observed_fold_ids and fold_id not in duplicate_fold_ids
                ]
                complete = observed_fold_ids == expected_fold_ids and not duplicate_fold_ids
                if complete:
                    net_return = sum(values) / float(len(values))
                    rows.append(
                        {
                            "seed_id": seed_id,
                            "comparator_id": comparator,
                            "fold_ids": list(expected_fold_ids),
                            "fold_count": len(expected_fold_ids),
                            "net_return": net_return,
                            "economic_net_return": net_return,
                            "economic_net_return_unit": ECONOMIC_NET_RETURN_UNIT,
                            "economic_net_return_cost_bps": PRIMARY_COST_BPS,
                            "economic_net_return_horizon": SB3_ACCOUNTING_HORIZON,
                        }
                    )
                seed_coverage.append(
                    {
                        "seed_id": seed_id,
                        "expected_fold_ids": list(expected_fold_ids),
                        "observed_fold_ids": observed_fold_ids,
                        "missing_fold_ids": missing_fold_ids,
                        "duplicate_fold_ids": duplicate_fold_ids,
                        "complete": complete,
                    }
                )
        result[comparator] = rows
        coverage[comparator] = {
            "comparator_id": comparator,
            "expected_seed_ids": expected_seed_ids,
            "expected_fold_ids": expected_fold_ids,
            "complete_seed_count": len(rows),
            "incomplete_seed_ids": [row["seed_id"] for row in seed_coverage if not row["complete"]],
            "seed_coverage": seed_coverage,
        }
    return result, coverage


def _summarize_seed_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if len(rows) != 5:
        return None
    returns = [float(row["net_return"]) for row in rows]
    return {
        "seed_count": 5,
        "seed_returns": returns,
        "iqm_return": compute_iqm(returns),
        "mean_return": sum(returns) / 5.0,
        "min_return": min(returns),
        "max_return": max(returns),
    }


def _paired_deltas(comparator_metrics: Mapping[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    ppo_by_seed = {row["seed_id"]: float(row["net_return"]) for row in comparator_metrics.get("ppo_policy", [])}
    result: dict[str, dict[str, Any]] = {}
    for comparator in protocol.COMPARATOR_ORDER:
        if comparator == "ppo_policy":
            continue
        baseline_by_seed = {row["seed_id"]: float(row["net_return"]) for row in comparator_metrics.get(comparator, [])}
        if set(ppo_by_seed) != {seed["seed_id"] for seed in protocol.SEEDS} or set(baseline_by_seed) != set(ppo_by_seed):
            result[comparator] = {"comparator_id": comparator, "available": False, "reason": "MISSING_PAIRED_SEED"}
            continue
        deltas = [ppo_by_seed[str(seed["seed_id"])] - baseline_by_seed[str(seed["seed_id"])] for seed in protocol.SEEDS]
        result[comparator] = {
            "comparator_id": comparator,
            "available": True,
            "seed_deltas": deltas,
            "iqm_delta": compute_iqm(deltas),
            "bootstrap_ci": paired_bootstrap_iqm_ci(deltas),
        }
    return result


def aggregate_cell_records(records_or_payload: Any, *, protocol_value: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Conserve the frozen 50-cell matrix and return deterministic aggregates."""

    frozen = _protocol_value(protocol_value)
    expected = _expected_cells(frozen)
    by_key = {_cell_key(str(cell["seed_id"]), str(cell["fold_id"]), str(cell["variant_id"])): cell for cell in expected}
    by_cell_uid = {str(cell["cell_uid"]): cell for cell in expected}
    records = _records_from_payload(records_or_payload)
    observed: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for index, raw_record in enumerate(records):
        record = _as_mapping(raw_record, f"record[{index}]")
        key = _record_key(record, by_cell_uid=by_cell_uid, by_key=by_key)
        if key in observed:
            raise DailyPortfolioSb3AggregateError(f"duplicate cell record for {key}")
        observed[key] = record

    cells: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    state_counts = {"PASS": 0, "FAIL": 0, "BLOCKED": 0, "PENDING": 0}
    metric_errors: list[dict[str, Any]] = []
    comparator_errors: list[dict[str, Any]] = []

    for cell in expected:
        key = _cell_key(str(cell["seed_id"]), str(cell["fold_id"]), str(cell["variant_id"]))
        record = observed.get(key)
        if record is None:
            status = "MISSING"
            normalized_metrics = None
            comparators: dict[str, float] = {}
            errors: list[str] = []
            cmp_errors: list[str] = []
            duplicate_comparator_ids: list[str] = []
            state = "PENDING"
            reason_codes = ["MISSING_CELL_RECORD"]
        else:
            status = _normalize_status(record.get("status", record.get("state", record.get("lifecycle_status", "COMPLETED"))))
            if status == "COMPLETED":
                normalized_metrics, comparators, errors, duplicate_comparator_ids = _normal_metrics(record, cell=cell, label=f"{cell['seed_id']}.{cell['fold_id']}.{cell['variant_id']}")
                cmp_errors = [error for error in errors if ".comparators" in error]
                metric_only_errors = [error for error in errors if ".comparators" not in error]
                errors = metric_only_errors
                state = "PASS" if normalized_metrics is not None and not errors and not cmp_errors else "FAIL"
                reason_codes = [] if state == "PASS" else ["NONFINITE_OR_MISSING_METRIC"]
            elif status == "STOPPED":
                normalized_metrics = None
                comparators = {}
                errors = []
                cmp_errors = []
                duplicate_comparator_ids = []
                state = "BLOCKED"
                reason_codes = ["CELL_STOPPED"]
            elif status == "FAILED":
                normalized_metrics = None
                comparators = {}
                errors = []
                cmp_errors = []
                duplicate_comparator_ids = []
                state = "BLOCKED"
                reason_codes = ["CELL_FAILED"]
            else:
                normalized_metrics = None
                comparators = {}
                errors = []
                cmp_errors = []
                duplicate_comparator_ids = []
                state = "PENDING"
                reason_codes = [f"CELL_{status}"]
        if errors:
            metric_errors.append({"cell_uid": cell["cell_uid"], "errors": errors})
        if cmp_errors:
            comparator_errors.append({"cell_uid": cell["cell_uid"], "errors": cmp_errors})
        status_counts[status] = status_counts.get(status, 0) + 1
        state_counts[state] += 1
        cells.append(
            {
                "ordinal": int(cell["ordinal"]),
                "cell_uid": str(cell["cell_uid"]),
                "attempt_uid": str(cell["attempt_uid"]),
                "seed_id": str(cell["seed_id"]),
                "seed": int(cell["seed"]),
                "base_seed": int(cell["seed"]),
                "rng_seed": int(cell["seed"]),
                "fold_id": str(cell["fold_id"]),
                "variant_id": str(cell["variant_id"]),
                "evaluation_cost_bps": int(cell["evaluation_cost_bps"]),
                "cost_scenario_id": str(cell["cost_scenario_id"]),
                "status": status,
                "state": state,
                "metrics": normalized_metrics,
                "comparators": comparators,
                "metric_errors": errors,
                "comparator_errors": cmp_errors,
                "comparator_duplicate_ids": duplicate_comparator_ids,
                "reason_codes": reason_codes,
            }
        )

    seed_metrics_by_variant: dict[str, list[dict[str, Any]]] = {variant_id: [] for variant_id in protocol.VARIANT_IDS}
    for variant_id in protocol.VARIANT_IDS:
        for seed in protocol.SEEDS:
            seed_id = str(seed["seed_id"])
            fold_rows = [cell for cell in cells if cell["seed_id"] == seed_id and cell["variant_id"] == variant_id]
            row = _aggregate_fold_metrics(seed_id, variant_id, fold_rows)
            if row is not None:
                seed_metrics_by_variant[variant_id].append(row)

    variant_summaries: dict[str, Any] = {}
    for variant_id in protocol.VARIANT_IDS:
        summary = _summarize_seed_rows(seed_metrics_by_variant[variant_id])
        variant_summaries[variant_id] = {
            "variant_id": variant_id,
            "complete_seed_count": len(seed_metrics_by_variant[variant_id]),
            "seed_metrics": seed_metrics_by_variant[variant_id],
            "summary": summary,
        }

    comparator_seed_metrics, comparator_coverage = _aggregate_comparator_seed_returns(cells, seed_metrics_by_variant)
    comparator_summaries: dict[str, Any] = {}
    for comparator in protocol.COMPARATOR_ORDER:
        rows = comparator_seed_metrics[comparator]
        summary = _summarize_seed_rows(rows)
        comparator_summaries[comparator] = {
            "comparator_id": comparator,
            "order_index": list(protocol.COMPARATOR_ORDER).index(comparator),
            "seed_metrics": rows,
            "complete_seed_count": len(rows),
            "expected_seed_count": len(protocol.SEEDS),
            "coverage": comparator_coverage[comparator],
            "summary": summary,
        }
    comparator_ranking = sorted(
        [
            {
                "comparator_id": comparator,
                "iqm_return": comparator_summaries[comparator]["summary"]["iqm_return"],
                "order_index": comparator_summaries[comparator]["order_index"],
            }
            for comparator in protocol.COMPARATOR_ORDER
            if comparator_summaries[comparator]["summary"] is not None
        ],
        key=lambda row: (-float(row["iqm_return"]), int(row["order_index"])),
    )
    for rank, row in enumerate(comparator_ranking, start=1):
        row["rank"] = rank

    paired = _paired_deltas(comparator_seed_metrics)
    primary_summary = variant_summaries[PRIMARY_VARIANT_ID]["summary"]
    sensitivities: dict[str, Any] = {}
    for variant_id in ("cost-00bp", "cost-46bp"):
        summary = variant_summaries[variant_id]["summary"]
        sensitivities[variant_id] = {
            "variant_id": variant_id,
            "cost_bps": 0 if variant_id == "cost-00bp" else 46,
            "summary": summary,
            "delta_vs_primary_iqm": None
            if summary is None or primary_summary is None
            else float(summary["iqm_return"]) - float(primary_summary["iqm_return"]),
            "verdict_input": False,
        }

    missing_required_comparators = [
        comparator
        for comparator in protocol.COMPARATOR_ORDER
        if comparator_summaries[comparator]["summary"] is None
    ]

    aggregate = {
        "schema": AGGREGATE_SCHEMA,
        "protocol_schema": protocol.PROTOCOL_SCHEMA,
        "protocol_version": frozen["statement"]["protocol_version"],
        "protocol_sha256": frozen["identity"]["protocol_sha256"],
        "source_contract": {
            "synthetic_verification_only": True,
            "fresh_oos_access_allowed": False,
            "fresh_oos_consumed": False,
            "fresh_oos_capability_consumed": False,
            "fresh_oos_data_read": False,
            "raw_oos_data_read": False,
            "raw_oos_access_allowed": False,
            "capability_consumed": False,
            "heavy_compute_allowed": False,
            "heavy_compute_consumed": False,
            "full_ppo_metadata_present": False,
            "model_training_stage": "NOT_RUN",
            "fresh_oos_status": frozen["statement"]["prerequisites"]["custody"]["status_in_protocol"],
            "accounting_horizon": frozen["statement"]["cost_model"]["accounting_horizon"],
            "primary_cost_bps": PRIMARY_COST_BPS,
            "evaluation_costs_bps": list(protocol.EVALUATION_COSTS_BPS),
            "comparator_order": list(protocol.COMPARATOR_ORDER),
        },
        "cell_conservation": {
            "expected_cell_count": 50,
            "observed_record_count": len(records),
            "emitted_cell_count": len(cells),
            "missing_count": status_counts.get("MISSING", 0),
            "stopped_count": status_counts.get("STOPPED", 0),
            "failed_count": status_counts.get("FAILED", 0),
            "completed_count": status_counts.get("COMPLETED", 0),
            "status_counts": dict(sorted(status_counts.items())),
            "state_counts": state_counts,
        },
        "cells": cells,
        "metric_errors": metric_errors,
        "comparator_errors": comparator_errors,
        "metric_error_count": len(metric_errors) + len(comparator_errors),
        "metric_definitions": {
            "seed_return": "Arithmetic mean of explicit economic_net_return fraction values for the two protocol folds of one base seed and variant.",
            "economic_net_return_contract": "Completed-cell metrics must use economic_net_return plus economic_net_return_unit='fraction', protocol cost bps, and SB3_T_DECIDE_T1_FILL_STATEFUL_V1 horizon; shaped reward aliases are rejected.",
            "seed_max_drawdown_pct": "Worst fold drawdown: the minimum, most negative explicit max_drawdown_pct.",
            "seed_trade_count": "Sum of explicit fold trade_count values for one base seed.",
            "seed_invalid_action_rate": "Sum raw_invalid_action_count divided by summed eval_step_count; missing invalid-action telemetry is rejected.",
            "iqm_5_seed_weights": "Sort the five base-seed values and apply weights 0.3, 0.4, 0.3 to positions 2, 3, 4.",
            "bootstrap_ci": "Paired base-seed resampling with numpy PCG64 seed 0 only, 10000 replicates, sorted CI indices 249 and 9749.",
        },
        "fold_to_base_seed": {
            "fold_ids": list(protocol.FOLD_IDS),
            "seed_ids": [str(seed["seed_id"]) for seed in protocol.SEEDS],
            "folds_as_seeds_detected": False,
            "rejection_policy": "IQM and bootstrap require exactly five base seeds; ten fold rows are rejected.",
        },
        "variant_summaries": variant_summaries,
        "primary_23bp": {
            "variant_id": PRIMARY_VARIANT_ID,
            "cost_bps": PRIMARY_COST_BPS,
            "summary": primary_summary,
            "seed_metrics": seed_metrics_by_variant[PRIMARY_VARIANT_ID],
            "verdict_input": True,
        },
        "sensitivities": sensitivities,
        "comparator_summaries": comparator_summaries,
        "comparator_coverage": comparator_coverage,
        "comparator_ranking": comparator_ranking,
        "missing_required_comparators": missing_required_comparators,
        "paired_deltas": paired,
        "shuffle_paired_delta": paired.get("shuffle_control"),
        "uncertainty": {
            "seed_count": len(seed_metrics_by_variant[PRIMARY_VARIANT_ID]),
            "expected_seed_count": 5,
            "bootstrap": {
                "bit_generator": "PCG64",
                "seed": BOOTSTRAP_SEED,
                "replicates": BOOTSTRAP_REPLICATES,
                "ci_indices": {"lower": BOOTSTRAP_CI_LOWER_INDEX, "upper": BOOTSTRAP_CI_UPPER_INDEX},
            },
        },
    }
    return aggregate


def canonical_aggregate_bytes(records_or_payload: Any, *, protocol_value: Mapping[str, Any] | None = None) -> bytes:
    """Build an aggregate and return its canonical RFC 8785 bytes."""

    return canonical_bytes(aggregate_cell_records(records_or_payload, protocol_value=protocol_value))


__all__ = [
    "AGGREGATE_SCHEMA",
    "BOOTSTRAP_CI_LOWER_INDEX",
    "BOOTSTRAP_CI_UPPER_INDEX",
    "BOOTSTRAP_REPLICATES",
    "BOOTSTRAP_SEED",
    "ECONOMIC_NET_RETURN_COST_BPS_FIELD",
    "ECONOMIC_NET_RETURN_FIELD",
    "ECONOMIC_NET_RETURN_HORIZON_FIELD",
    "ECONOMIC_NET_RETURN_UNIT",
    "ECONOMIC_NET_RETURN_UNIT_FIELD",
    "DailyPortfolioSb3AggregateError",
    "INVALID_ACTION_STOP_THRESHOLD",
    "MAX_DRAWDOWN_NO_GO_THRESHOLD_PCT",
    "PRIMARY_COST_BPS",
    "PRIMARY_VARIANT_ID",
    "SB3_ACCOUNTING_HORIZON",
    "aggregate_cell_records",
    "aggregate_sha256",
    "canonical_aggregate_bytes",
    "canonical_bytes",
    "compute_iqm",
    "paired_bootstrap_iqm_ci",
]
