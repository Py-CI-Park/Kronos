"""Verdict projection for deterministic daily Portfolio SB3 aggregates.

The evaluator keeps model-quality claims separate from engineering/research
aggregation.  Because the frozen G008 protocol grants no fresh-OOS capability,
the model verdict is always ``NOT_RUN`` even when synthetic historical metrics are
present.  The research verdict below is a first-match diagnostic over the 23bp
primary aggregate only; 0/46bp controls remain sensitivities.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any, Final

from stom_rl import daily_portfolio_sb3_protocol as protocol
from stom_rl.daily_portfolio_sb3_aggregate import (
    AGGREGATE_SCHEMA,
    INVALID_ACTION_STOP_THRESHOLD,
    MAX_DRAWDOWN_NO_GO_THRESHOLD_PCT,
    PRIMARY_COST_BPS,
    aggregate_cell_records,
    aggregate_sha256,
    canonical_bytes,
)


EVALUATION_SCHEMA: Final = "kronos_daily_sb3_evaluation.v1"

VERDICT_RULE_ORDER: Final = (
    "MISSING_CELLS",
    "STOPPED_CELLS",
    "FAILED_CELLS",
    "NONFINITE_METRICS",
    "FOLDS_AS_SEEDS_REJECTED",
    "PRIMARY_23BP_INCOMPLETE",
    "MISSING_REQUIRED_COMPARATORS",
    "INVALID_ACTION_RATE_ABOVE_0_05",
    "NON_IMPROVING_23BP",
    "NEVER_TRADED_23BP",
    "SHUFFLE_CONTROL_NOT_BEATEN",
    "BEST_COMPARATOR_NOT_BEATEN",
    "MAX_DRAWDOWN_BELOW_-20PCT",
    "SEED_NOISE_CI_CROSSES_ZERO",
    "WATCH_RESEARCH_ONLY",
)

RULE_VERDICTS: Final = {
    "MISSING_CELLS": "INCONCLUSIVE",
    "STOPPED_CELLS": "INCONCLUSIVE",
    "FAILED_CELLS": "INCONCLUSIVE",
    "NONFINITE_METRICS": "INCONCLUSIVE",
    "FOLDS_AS_SEEDS_REJECTED": "INCONCLUSIVE",
    "PRIMARY_23BP_INCOMPLETE": "INCONCLUSIVE",
    "MISSING_REQUIRED_COMPARATORS": "INCONCLUSIVE",
    "INVALID_ACTION_RATE_ABOVE_0_05": "INCONCLUSIVE",
    "NON_IMPROVING_23BP": "NO-GO",
    "NEVER_TRADED_23BP": "NO-GO",
    "SHUFFLE_CONTROL_NOT_BEATEN": "NO-GO",
    "BEST_COMPARATOR_NOT_BEATEN": "NO-GO",
    "MAX_DRAWDOWN_BELOW_-20PCT": "NO-GO",
    "SEED_NOISE_CI_CROSSES_ZERO": "SEED_NOISE_NO_GO",
    "WATCH_RESEARCH_ONLY": "WATCH_RESEARCH_ONLY",
}


class DailyPortfolioSb3EvaluatorError(ValueError):
    """Raised when a verdict input is not a daily Portfolio SB3 aggregate."""

NOT_RUN_REQUIRED_FALSE_FIELDS: Final = frozenset(
    {
        "capability_consumed",
        "fresh_oos_access_allowed",
        "fresh_oos_consumed",
        "fresh_oos_capability_consumed",
        "fresh_oos_data_read",
        "full_ppo_metadata_present",
        "heavy_compute_allowed",
        "heavy_compute_consumed",
        "raw_oos_data_read",
        "raw_oos_access_allowed",
    }
)
NOT_RUN_FORBIDDEN_TRUTHY_KEYS: Final = frozenset(
    {
        "capability_consumed",
        "fresh_oos_access_allowed",
        "fresh_oos_consumed",
        "fresh_oos_capability_consumed",
        "fresh_oos_data_read",
        "full_ppo_metadata_present",
        "fresh_oos_download",
        "heavy_compute_allowed",
        "heavy_compute_consumed",
        "may_read_fresh_oos",
        "may_train",
        "oos_capability_consumed",
        "raw_oos_data_read",
        "raw_oos_access_allowed",
        "raw_oos_download",
        "sb3_learn_allowed",
        "training_allowed",
    }
)
NOT_RUN_FORBIDDEN_PRESENT_KEYS: Final = frozenset(
    {
        "full_ppo_manifest",
        "full_ppo_metadata",
        "full_ppo_run",
        "heavy_compute_metadata",
        "model_zip",
        "ppo_config",
        "ppo_full_metadata",
        "ppo_metadata",
        "total_timesteps",
        "total_timesteps_per_seed_fold",
    }
)
NOT_RUN_STAGE_KEYS: Final = frozenset({"model_stage", "model_training_stage", "ppo_stage", "run_stage", "stage", "training_stage"})
NOT_RUN_ALLOWED_EMPTY_STRING_STATES: Final = frozenset(
    {"", "0", "FALSE", "NULL", "NONE", "EMPTY", "DENIED", "NOT_RUN"}
)



def _require_aggregate(value: Mapping[str, Any]) -> None:
    if value.get("schema") != AGGREGATE_SCHEMA:
        raise DailyPortfolioSb3EvaluatorError("input is not a daily Portfolio SB3 aggregate")
    frozen = protocol.build_protocol()
    protocol.validate_protocol(frozen)
    if value.get("protocol_sha256") != frozen["identity"]["protocol_sha256"]:
        raise DailyPortfolioSb3EvaluatorError("aggregate is not bound to the frozen G008 protocol")


def _normalized_not_run_state(value: str) -> str:
    return value.strip().upper().replace("-", "_").replace(" ", "_")


def _explicit_empty_or_not_run_state(value: Any) -> bool:
    if value is None or value is False:
        return True
    if value is True:
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        return math.isfinite(numeric) and numeric == 0.0
    if isinstance(value, str):
        return _normalized_not_run_state(value) in NOT_RUN_ALLOWED_EMPTY_STRING_STATES
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _meaningful_forbidden_value(value: Any) -> bool:
    return not _explicit_empty_or_not_run_state(value)


def _walk_values(value: Any, *, path: str = "aggregate") -> list[tuple[str, str, Any]]:
    rows: list[tuple[str, str, Any]] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            child_path = f"{path}.{key}"
            rows.append((child_path, key, child))
            rows.extend(_walk_values(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_walk_values(child, path=f"{path}[{index}]"))
    return rows


def _assert_not_run_projection_contract(aggregate: Mapping[str, Any]) -> None:
    source = aggregate.get("source_contract")
    if not isinstance(source, Mapping):
        raise DailyPortfolioSb3EvaluatorError("aggregate missing source_contract for NOT_RUN projection")
    if source.get("synthetic_verification_only") is not True:
        raise DailyPortfolioSb3EvaluatorError("NOT_RUN projection requires synthetic_verification_only=true")
    if source.get("fresh_oos_status") != "FRESH_OOS_NOT_RUN":
        raise DailyPortfolioSb3EvaluatorError("NOT_RUN projection requires fresh_oos_status=FRESH_OOS_NOT_RUN")
    for field in sorted(NOT_RUN_REQUIRED_FALSE_FIELDS):
        if source.get(field) is not False:
            raise DailyPortfolioSb3EvaluatorError(f"NOT_RUN projection requires source_contract.{field}=false")
    for path, key, value in _walk_values(aggregate):
        normalized_key = key.lower().replace("-", "_").replace(" ", "_")
        if normalized_key in NOT_RUN_FORBIDDEN_TRUTHY_KEYS and _meaningful_forbidden_value(value):
            raise DailyPortfolioSb3EvaluatorError(f"NOT_RUN projection rejects consumed capability at {path}")
        if normalized_key in NOT_RUN_FORBIDDEN_PRESENT_KEYS and _meaningful_forbidden_value(value):
            raise DailyPortfolioSb3EvaluatorError(f"NOT_RUN projection rejects heavy/full PPO metadata at {path}")
        if normalized_key in NOT_RUN_STAGE_KEYS and _meaningful_forbidden_value(value):
            raise DailyPortfolioSb3EvaluatorError(f"NOT_RUN projection rejects heavy/full stage metadata at {path}")



def _rule(rule_id: str, reasons: list[str], *, details: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "rule_index": VERDICT_RULE_ORDER.index(rule_id) + 1,
        "verdict": RULE_VERDICTS[rule_id],
        "reasons": reasons,
        "details": dict(details or {}),
    }


def _primary_seed_metrics(aggregate: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    primary = aggregate.get("primary_23bp")
    if not isinstance(primary, Mapping):
        return []
    rows = primary.get("seed_metrics")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _primary_summary(aggregate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    primary = aggregate.get("primary_23bp")
    if not isinstance(primary, Mapping):
        return None
    summary = primary.get("summary")
    return summary if isinstance(summary, Mapping) else None



def _paired_delta(aggregate: Mapping[str, Any], comparator_id: str) -> Mapping[str, Any] | None:
    paired = aggregate.get("paired_deltas")
    if not isinstance(paired, Mapping):
        return None
    row = paired.get(comparator_id)
    return row if isinstance(row, Mapping) and row.get("available") is True else None


def _best_non_ppo_comparator(aggregate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    ranking = aggregate.get("comparator_ranking")
    if not isinstance(ranking, list):
        return None
    for row in ranking:
        if isinstance(row, Mapping) and row.get("comparator_id") != "ppo_policy":
            return row
    return None


def research_verdict(aggregate: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact first-match 23bp research diagnostic verdict."""

    _require_aggregate(aggregate)
    conservation = aggregate.get("cell_conservation")
    if not isinstance(conservation, Mapping):
        raise DailyPortfolioSb3EvaluatorError("aggregate missing cell_conservation")

    missing_count = int(conservation.get("missing_count", 0))
    if missing_count:
        return _rule("MISSING_CELLS", ["One or more frozen protocol cells are MISSING."], details={"missing_count": missing_count})

    stopped_count = int(conservation.get("stopped_count", 0))
    if stopped_count:
        return _rule("STOPPED_CELLS", ["One or more frozen protocol cells are STOPPED."], details={"stopped_count": stopped_count})

    failed_count = int(conservation.get("failed_count", 0))
    if failed_count:
        return _rule("FAILED_CELLS", ["One or more frozen protocol cells FAILED."], details={"failed_count": failed_count})

    metric_error_count = int(aggregate.get("metric_error_count", 0))
    if metric_error_count:
        return _rule("NONFINITE_METRICS", ["One or more completed cells has missing or non-finite metrics."], details={"metric_error_count": metric_error_count})

    fold_to_seed = aggregate.get("fold_to_base_seed")
    uncertainty = aggregate.get("uncertainty")
    folds_as_seeds = isinstance(fold_to_seed, Mapping) and fold_to_seed.get("folds_as_seeds_detected") is True
    seed_count = int(uncertainty.get("seed_count", 0)) if isinstance(uncertainty, Mapping) else 0
    expected_seed_count = int(uncertainty.get("expected_seed_count", 5)) if isinstance(uncertainty, Mapping) else 5
    if folds_as_seeds or seed_count > expected_seed_count:
        return _rule(
            "FOLDS_AS_SEEDS_REJECTED",
            ["Uncertainty inputs must be five base seeds, not fold rows treated as seeds."],
            details={"seed_count": seed_count, "expected_seed_count": expected_seed_count, "folds_as_seeds_detected": bool(folds_as_seeds)},
        )

    primary_summary = _primary_summary(aggregate)
    primary_rows = _primary_seed_metrics(aggregate)
    if primary_summary is None or len(primary_rows) != 5:
        return _rule(
            "PRIMARY_23BP_INCOMPLETE",
            ["The 23bp primary verdict cohort does not contain exactly five base-seed summaries."],
            details={"primary_seed_count": len(primary_rows)},
        )

    missing_comparators = list(aggregate.get("missing_required_comparators") or [])
    required_missing = [item for item in missing_comparators if item in protocol.COMPARATOR_ORDER]
    if required_missing:
        return _rule(
            "MISSING_REQUIRED_COMPARATORS",
            ["The 23bp comparator table is incomplete."],
            details={"missing_required_comparators": required_missing},
        )

    max_invalid = max(float(row.get("invalid_action_rate", 0.0)) for row in primary_rows)
    if max_invalid > INVALID_ACTION_STOP_THRESHOLD:
        return _rule(
            "INVALID_ACTION_RATE_ABOVE_0_05",
            ["A 23bp primary seed exceeds the protocol invalid-action stop threshold."],
            details={"max_invalid_action_rate": max_invalid, "threshold": INVALID_ACTION_STOP_THRESHOLD},
        )

    ppo_iqm = float(primary_summary["iqm_return"])
    if ppo_iqm <= 0.0:
        return _rule(
            "NON_IMPROVING_23BP",
            ["The 23bp primary five-seed IQM is not positive."],
            details={"ppo_policy_iqm_return": ppo_iqm, "cost_bps": PRIMARY_COST_BPS},
        )

    total_trades = sum(int(row.get("trade_count", 0)) for row in primary_rows)
    if total_trades <= 0:
        return _rule(
            "NEVER_TRADED_23BP",
            ["The 23bp primary cohort has zero executed trades across all base seeds."],
            details={"total_trade_count": total_trades},
        )

    shuffle = _paired_delta(aggregate, "shuffle_control")
    if shuffle is None or float(shuffle.get("iqm_delta", 0.0)) <= 0.0:
        return _rule(
            "SHUFFLE_CONTROL_NOT_BEATEN",
            ["The 23bp primary paired IQM delta versus shuffle_control is not positive."],
            details={"shuffle_paired_delta": None if shuffle is None else dict(shuffle)},
        )

    best = _best_non_ppo_comparator(aggregate)
    if best is None:
        return _rule("MISSING_REQUIRED_COMPARATORS", ["No non-PPO comparator is available."], details={})
    best_id = str(best["comparator_id"])
    best_delta = _paired_delta(aggregate, best_id)
    if best_delta is None or float(best_delta.get("iqm_delta", 0.0)) <= 0.0:
        return _rule(
            "BEST_COMPARATOR_NOT_BEATEN",
            ["The 23bp primary policy does not beat the best fixed-order comparator."],
            details={"best_comparator_id": best_id, "paired_delta": None if best_delta is None else dict(best_delta)},
        )

    worst_mdd = min(float(row.get("max_drawdown_pct", 0.0)) for row in primary_rows)
    if worst_mdd < MAX_DRAWDOWN_NO_GO_THRESHOLD_PCT:
        return _rule(
            "MAX_DRAWDOWN_BELOW_-20PCT",
            ["The 23bp primary cohort breaches the maximum drawdown guardrail."],
            details={"worst_max_drawdown_pct": worst_mdd, "threshold_pct": MAX_DRAWDOWN_NO_GO_THRESHOLD_PCT},
        )

    ci = best_delta.get("bootstrap_ci") if isinstance(best_delta, Mapping) else None
    ci_lower = float(ci.get("lower")) if isinstance(ci, Mapping) and ci.get("lower") is not None else None
    if ci_lower is None or ci_lower <= 0.0:
        return _rule(
            "SEED_NOISE_CI_CROSSES_ZERO",
            ["The paired 23bp bootstrap CI is not strictly above zero."],
            details={"best_comparator_id": best_id, "ci_lower": ci_lower, "paired_delta": dict(best_delta)},
        )

    return _rule(
        "WATCH_RESEARCH_ONLY",
        ["Synthetic 23bp historical diagnostics clear local checks but do not create a model promotion claim."],
        details={"cost_bps": PRIMARY_COST_BPS, "ppo_policy_iqm_return": ppo_iqm, "best_comparator_id": best_id, "ci_lower": ci_lower},
    )


def model_verdict(aggregate: Mapping[str, Any]) -> dict[str, Any]:
    """Return the unscored model verdict.  Frozen G008 has no fresh-OOS read."""

    _require_aggregate(aggregate)
    _assert_not_run_projection_contract(aggregate)
    return {
        "verdict": "NOT_RUN",
        "reason_codes": ["FRESH_OOS_NOT_RUN", "NO_FRESH_OOS_CAPABILITY_IN_PROTOCOL"],
        "fresh_oos_consumed": False,
        "raw_oos_data_read": False,
        "promotion_allowed": False,
        "model_build_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
        "profitability_claim_allowed": False,
        "go_summary_allowed": False,
        "score_contribution": 0,
    }


def evaluate_aggregate(aggregate: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate a deterministic aggregate into research and model verdicts."""

    _require_aggregate(aggregate)
    research = research_verdict(aggregate)
    model = model_verdict(aggregate)
    return {
        "schema": EVALUATION_SCHEMA,
        "protocol_schema": protocol.PROTOCOL_SCHEMA,
        "protocol_sha256": aggregate["protocol_sha256"],
        "aggregate_schema": AGGREGATE_SCHEMA,
        "aggregate_sha256": aggregate_sha256(aggregate),
        "primary_verdict_cost_bps": PRIMARY_COST_BPS,
        "sensitivities_verdict_input": False,
        "research_verdict": research,
        "model_verdict": model,
        "score_independence": {
            "model_verdict_contributes_to_engineering_score": False,
            "positive_alpha_bonus_points": 0,
            "model_verdict_points": 0,
            "research_verdict_points": 0,
        },
        "false_locks": {
            "promotion_allowed": False,
            "model_build_allowed": False,
            "paper_forward_allowed": False,
            "live_broker_order_allowed": False,
            "profitability_claim_allowed": False,
            "go_summary_allowed": False,
        },
        "verdict_rule_order": list(VERDICT_RULE_ORDER),
    }


def evaluate_records(records_or_payload: Any) -> dict[str, Any]:
    """Convenience wrapper: aggregate raw cell records, then evaluate them."""

    return evaluate_aggregate(aggregate_cell_records(records_or_payload))


def canonical_evaluation_bytes(aggregate: Mapping[str, Any]) -> bytes:
    """Return canonical RFC 8785 bytes for an evaluation result."""

    return canonical_bytes(evaluate_aggregate(aggregate))


__all__ = [
    "EVALUATION_SCHEMA",
    "RULE_VERDICTS",
    "VERDICT_RULE_ORDER",
    "DailyPortfolioSb3EvaluatorError",
    "canonical_evaluation_bytes",
    "evaluate_aggregate",
    "evaluate_records",
    "model_verdict",
    "research_verdict",
]
