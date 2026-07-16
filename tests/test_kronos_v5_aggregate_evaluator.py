from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from stom_rl import daily_portfolio_sb3_protocol as protocol
from stom_rl import daily_portfolio_sb3_aggregate as aggregate
from stom_rl import daily_portfolio_sb3_evaluator as evaluator


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests" / "data" / "kronos_v5_aggregate_evaluator_fixture.json").read_text(encoding="utf-8"))


def _economic_return_metric(value: float, cost_bps: int) -> dict[str, object]:
    return {
        "economic_net_return": float(value),
        "economic_net_return_unit": "fraction",
        "economic_net_return_cost_bps": int(cost_bps),
        "economic_net_return_horizon": aggregate.SB3_ACCOUNTING_HORIZON,
    }


def _cell_metrics(
    *,
    net_return: float,
    cost_bps: int,
    max_drawdown_pct: float,
    trade_count: int,
    raw_invalid_action_count: int = 0,
    eval_step_count: int = 100,
) -> dict[str, object]:
    return {
        **_economic_return_metric(net_return, cost_bps),
        "max_drawdown_pct": max_drawdown_pct,
        "trade_count": trade_count,
        "raw_invalid_action_count": raw_invalid_action_count,
        "eval_step_count": eval_step_count,
    }


def _comparator_metrics(comparators: dict[str, float], *, cost_bps: int = 23) -> dict[str, dict[str, object]]:
    return {name: _economic_return_metric(value, cost_bps) for name, value in comparators.items()}


def _base_records() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    variant_adjustments = FIXTURE["variant_return_adjustments"]
    comparators = FIXTURE["comparators_23bp"]
    for cell in protocol.build_protocol()["matrix"]["cells"]:
        seed_id = cell["seed_id"]
        fold_id = cell["fold_id"]
        variant_id = cell["variant_id"]
        cost_bps = int(cell["evaluation_cost_bps"])
        if variant_id == "no-trade":
            net_return = 0.0
            trade_count = 0
            max_drawdown_pct = 0.0
        else:
            net_return = float(FIXTURE["seed_fold_returns"][seed_id][fold_id]) + float(variant_adjustments[variant_id])
            trade_count = 2 if fold_id == "fold-01" else 3
            max_drawdown_pct = -4.0 if fold_id == "fold-01" else -5.0
        metrics = _cell_metrics(
            net_return=net_return,
            cost_bps=cost_bps,
            max_drawdown_pct=max_drawdown_pct,
            trade_count=trade_count,
        )
        if variant_id == "cost-23bp":
            metrics["comparators"] = _comparator_metrics(comparators, cost_bps=cost_bps)
        records.append(
            {
                "cell_uid": cell["cell_uid"],
                "seed_id": seed_id,
                "fold_id": fold_id,
                "variant_id": variant_id,
                "base_seed": int(cell["seed"]),
                "rng_seed": int(cell["seed"]),
                "status": "COMPLETED",
                "metrics": metrics,
            }
        )
    return records


def _matches(record: dict[str, object], selector: dict[str, str]) -> bool:
    return all(record[key] == value for key, value in selector.items())


def _set_primary_returns(records: list[dict[str, object]], returns_by_seed: dict[str, float]) -> None:
    for record in records:
        if record["variant_id"] == "cost-23bp":
            record["metrics"]["economic_net_return"] = float(returns_by_seed[record["seed_id"]])


def _set_primary_comparators(records: list[dict[str, object]], comparators: dict[str, float]) -> None:
    for record in records:
        if record["variant_id"] == "cost-23bp":
            record["metrics"]["comparators"] = _comparator_metrics(comparators)

def _scenario_records(scenario: dict[str, object]) -> list[dict[str, object]]:
    records = _base_records()
    mutation = scenario.get("mutation", {})
    for selector in mutation.get("drop", []):
        records = [record for record in records if not _matches(record, selector)]
    for update in mutation.get("set_status", []):
        for record in records:
            if _matches(record, {key: update[key] for key in ("seed_id", "fold_id", "variant_id")}):
                record["status"] = update["status"]
    for update in mutation.get("set_cell_metric", []):
        for record in records:
            if _matches(record, {key: update[key] for key in ("seed_id", "fold_id", "variant_id")}):
                record["metrics"][update["key"]] = update["value"]
    if mutation.get("remove_primary_comparators"):
        for record in records:
            if record["variant_id"] == "cost-23bp":
                record["metrics"].pop("comparators", None)
    for update in mutation.get("remove_primary_comparator", []):
        for record in records:
            if _matches(record, {key: update[key] for key in ("seed_id", "fold_id", "variant_id")}):
                record["metrics"].get("comparators", {}).pop(update["comparator_id"], None)
    if "primary_returns_by_seed" in mutation:
        _set_primary_returns(records, mutation["primary_returns_by_seed"])
    if "comparators" in mutation:
        _set_primary_comparators(records, mutation["comparators"])
    if "primary_trade_count" in mutation:
        for record in records:
            if record["variant_id"] == "cost-23bp":
                record["metrics"]["trade_count"] = mutation["primary_trade_count"]
    if "primary_invalid_action_count" in mutation:
        for record in records:
            if record["variant_id"] == "cost-23bp":
                record["metrics"]["raw_invalid_action_count"] = mutation["primary_invalid_action_count"]
                record["metrics"]["eval_step_count"] = mutation["primary_eval_step_count"]
    if "primary_max_drawdown_pct" in mutation:
        for record in records:
            if record["variant_id"] == "cost-23bp":
                record["metrics"]["max_drawdown_pct"] = mutation["primary_max_drawdown_pct"]
    return records


def _first_primary_record(records: list[dict[str, object]]) -> dict[str, object]:
    return next(record for record in records if record["seed_id"] == "seed-01" and record["fold_id"] == "fold-01" and record["variant_id"] == "cost-23bp")


def _metric_error_text(result: dict[str, object]) -> str:
    errors = []
    for group in ("metric_errors", "comparator_errors"):
        for row in result[group]:
            errors.extend(row["errors"])
    return "\n".join(errors)


def test_conserves_50_cells_and_folds_collapse_to_five_base_seeds() -> None:
    result = aggregate.aggregate_cell_records(_base_records())

    assert result["cell_conservation"]["expected_cell_count"] == 50
    assert result["cell_conservation"]["emitted_cell_count"] == 50
    assert result["cell_conservation"]["missing_count"] == 0
    assert result["cell_conservation"]["stopped_count"] == 0
    assert [cell["ordinal"] for cell in result["cells"]] == list(range(1, 51))
    assert result["cells"][0]["base_seed"] == 7
    assert result["cells"][0]["rng_seed"] == 7

    primary_rows = result["primary_23bp"]["seed_metrics"]
    assert len(primary_rows) == 5
    assert primary_rows[0]["fold_count"] == 2
    assert primary_rows[0]["net_return"] == pytest.approx((0.08 + 0.06) / 2.0)
    assert primary_rows[0]["economic_net_return_unit"] == "fraction"
    assert primary_rows[0]["economic_net_return_cost_bps"] == 23
    assert primary_rows[0]["economic_net_return_horizon"] == aggregate.SB3_ACCOUNTING_HORIZON
    assert primary_rows[0]["max_drawdown_pct"] == -5.0
    assert primary_rows[0]["trade_count"] == 5
    assert primary_rows[0]["invalid_action_rate"] == 0.0

    sorted_returns = sorted(row["net_return"] for row in primary_rows)
    expected_iqm = (0.3 * sorted_returns[1]) + (0.4 * sorted_returns[2]) + (0.3 * sorted_returns[3])
    assert result["primary_23bp"]["summary"]["iqm_return"] == pytest.approx(expected_iqm)
    assert result["metric_definitions"]["iqm_5_seed_weights"].endswith("0.3, 0.4, 0.3 to positions 2, 3, 4.")
    assert set(result["sensitivities"]) == {"cost-00bp", "cost-46bp"}
    assert result["sensitivities"]["cost-00bp"]["verdict_input"] is False


@pytest.mark.parametrize(
    ("case", "fragment"),
    [
        ("reward_alias", "shaped reward or legacy return aliases"),
        ("missing_unit", "economic_net_return_unit"),
        ("wrong_cost", "does not match protocol cost 23"),
        ("missing_horizon", "economic_net_return_horizon"),
        ("missing_mdd", "max_drawdown_pct is missing"),
        ("missing_trades", "trade_count is missing"),
        ("missing_invalid_count", "raw_invalid_action_count is missing"),
        ("missing_invalid_denominator", "eval_step_count is missing"),
        ("nonfinite_mdd", "max_drawdown_pct is not finite"),
        ("scalar_comparator", "must be an explicit economic net-return object"),
    ],
)
def test_metric_contract_rejects_aliases_missing_telemetry_and_nonfinite_values(case: str, fragment: str) -> None:
    records = _base_records()
    metrics = _first_primary_record(records)["metrics"]
    if case == "reward_alias":
        metrics["reward"] = metrics.pop("economic_net_return")
    elif case == "missing_unit":
        metrics.pop("economic_net_return_unit")
    elif case == "wrong_cost":
        metrics["economic_net_return_cost_bps"] = 0
    elif case == "missing_horizon":
        metrics.pop("economic_net_return_horizon")
    elif case == "missing_mdd":
        metrics.pop("max_drawdown_pct")
    elif case == "missing_trades":
        metrics.pop("trade_count")
    elif case == "missing_invalid_count":
        metrics.pop("raw_invalid_action_count")
    elif case == "missing_invalid_denominator":
        metrics.pop("eval_step_count")
    elif case == "nonfinite_mdd":
        metrics["max_drawdown_pct"] = "NaN"
    elif case == "scalar_comparator":
        metrics["comparators"]["shuffle_control"] = 0.01

    result = aggregate.aggregate_cell_records(records)

    assert result["metric_error_count"] >= 1
    assert fragment in _metric_error_text(result)
    assert evaluator.research_verdict(result)["rule_id"] == "NONFINITE_METRICS"


def test_seed_identity_rejects_protocol_mismatch_and_fold_offset_aliases() -> None:
    for field in ("base_seed", "rng_seed"):
        records = _base_records()
        target = _first_primary_record(records)
        target[field] = int(target[field]) + 1
        with pytest.raises(aggregate.DailyPortfolioSb3AggregateError, match="does not match protocol seed"):
            aggregate.aggregate_cell_records(records)

    for field in ("base_seed", "rng_seed"):
        records = _base_records()
        _first_primary_record(records).pop(field)
        with pytest.raises(aggregate.DailyPortfolioSb3AggregateError, match=f"{field} is missing"):
            aggregate.aggregate_cell_records(records)

    records = _base_records()
    _first_primary_record(records)["fold_offset_seed"] = 8
    with pytest.raises(aggregate.DailyPortfolioSb3AggregateError, match="forbidden fold-offset seed alias"):
        aggregate.aggregate_cell_records(records)


def test_missing_and_stopped_cells_are_conserved_in_the_matrix() -> None:
    scenario = next(item for item in FIXTURE["scenarios"] if item["id"] == "first_match_missing_before_stopped")
    result = aggregate.aggregate_cell_records(_scenario_records(scenario))

    assert len(result["cells"]) == 50
    assert result["cell_conservation"]["missing_count"] == 1
    assert result["cell_conservation"]["stopped_count"] == 1
    statuses = {(cell["seed_id"], cell["fold_id"], cell["variant_id"]): cell["status"] for cell in result["cells"]}
    assert statuses[("seed-01", "fold-01", "baseline")] == "MISSING"
    assert statuses[("seed-01", "fold-02", "cost-23bp")] == "STOPPED"


def test_partial_and_duplicate_comparator_folds_are_incomplete_not_verdict_inputs() -> None:
    records = _base_records()
    partial = next(
        record
        for record in records
        if record["seed_id"] == "seed-01" and record["fold_id"] == "fold-02" and record["variant_id"] == "cost-23bp"
    )
    partial["metrics"]["comparators"].pop("shuffle_control")

    result = aggregate.aggregate_cell_records(records)

    shuffle = result["comparator_summaries"]["shuffle_control"]
    seed_coverage = result["comparator_coverage"]["shuffle_control"]["seed_coverage"][0]
    assert shuffle["summary"] is None
    assert shuffle["complete_seed_count"] == 4
    assert seed_coverage["seed_id"] == "seed-01"
    assert seed_coverage["observed_fold_ids"] == ["fold-01"]
    assert seed_coverage["missing_fold_ids"] == ["fold-02"]
    assert seed_coverage["duplicate_fold_ids"] == []
    assert seed_coverage["complete"] is False
    assert "shuffle_control" in result["missing_required_comparators"]
    assert evaluator.research_verdict(result)["rule_id"] == "MISSING_REQUIRED_COMPARATORS"

    duplicate_records = _base_records()
    duplicate = _first_primary_record(duplicate_records)
    duplicate["comparators"] = {"shuffle_control": _economic_return_metric(0.03, 23)}

    duplicate_result = aggregate.aggregate_cell_records(duplicate_records)

    duplicate_coverage = duplicate_result["comparator_coverage"]["shuffle_control"]["seed_coverage"][0]
    assert duplicate_result["metric_error_count"] == 0
    assert duplicate_result["comparator_summaries"]["shuffle_control"]["summary"] is None
    assert duplicate_coverage["observed_fold_ids"] == ["fold-02"]
    assert duplicate_coverage["missing_fold_ids"] == []
    assert duplicate_coverage["duplicate_fold_ids"] == ["fold-01"]
    assert duplicate_coverage["complete"] is False
    assert evaluator.research_verdict(duplicate_result)["rule_id"] == "MISSING_REQUIRED_COMPARATORS"


@pytest.mark.parametrize("scenario", FIXTURE["scenarios"], ids=[scenario["id"] for scenario in FIXTURE["scenarios"]])
def test_synthetic_boundary_fixture_covers_exact_first_match_verdict_branches(scenario: dict[str, object]) -> None:
    result = evaluator.evaluate_aggregate(aggregate.aggregate_cell_records(_scenario_records(scenario)))

    assert result["research_verdict"]["rule_id"] == scenario["expected_rule"]
    assert result["research_verdict"]["verdict"] == scenario["expected_verdict"]
    assert result["research_verdict"]["rule_index"] == evaluator.VERDICT_RULE_ORDER.index(scenario["expected_rule"]) + 1
    assert result["model_verdict"]["verdict"] == "NOT_RUN"
    assert result["model_verdict"]["fresh_oos_consumed"] is False


def test_folds_as_seeds_are_rejected_for_iqm_and_evaluator_guard() -> None:
    with pytest.raises(aggregate.DailyPortfolioSb3AggregateError):
        aggregate.compute_iqm(FIXTURE["folds_as_seeds_direct_values"])

    result = aggregate.aggregate_cell_records(_base_records())
    tampered = deepcopy(result)
    tampered["fold_to_base_seed"]["folds_as_seeds_detected"] = True
    tampered["uncertainty"]["seed_count"] = 10

    verdict = evaluator.research_verdict(tampered)
    assert verdict["rule_id"] == "FOLDS_AS_SEEDS_REJECTED"


@pytest.mark.parametrize(
    "case",
    [
        "fresh_oos_status",
        "fresh_oos_consumed",
        "raw_oos_data_read",
        "capability_consumed",
        "heavy_compute_consumed",
        "full_ppo_metadata_present",
        "top_level_full_ppo_metadata",
        "top_level_full_stage",
        "raw_oos_download_allowed",
        "raw_oos_download_not_allowed_alias",
        "top_level_fresh_oos_numeric",
        "top_level_raw_oos_object",
        "top_level_heavy_compute_array",
        "top_level_total_timesteps_nonzero",
        "top_level_full_ppo_metadata_present_numeric",
        "top_level_ppo_config_alternate_string",
        "top_level_stage_partial",
    ],
)
def test_model_not_run_projection_rejects_contradictory_oos_capability_and_heavy_metadata(case: str) -> None:
    result = aggregate.aggregate_cell_records(_base_records())
    if case == "fresh_oos_status":
        result["source_contract"]["fresh_oos_status"] = "FRESH_OOS_CONSUMED"
    elif case == "fresh_oos_consumed":
        result["source_contract"]["fresh_oos_consumed"] = True
    elif case == "raw_oos_data_read":
        result["source_contract"]["raw_oos_data_read"] = True
    elif case == "capability_consumed":
        result["source_contract"]["capability_consumed"] = True
    elif case == "heavy_compute_consumed":
        result["source_contract"]["heavy_compute_consumed"] = True
    elif case == "full_ppo_metadata_present":
        result["source_contract"]["full_ppo_metadata_present"] = True
    elif case == "top_level_full_ppo_metadata":
        result["full_ppo_metadata"] = {"total_timesteps_per_seed_fold": 200_000}
    elif case == "top_level_full_stage":
        result["training_stage"] = "full"
    elif case == "raw_oos_download_allowed":
        result["raw_oos_download"] = "ALLOWED"
    elif case == "raw_oos_download_not_allowed_alias":
        result["raw_oos_download"] = "NOT_ALLOWED"
    elif case == "top_level_fresh_oos_numeric":
        result["fresh_oos_consumed"] = 1
    elif case == "top_level_raw_oos_object":
        result["raw_oos_data_read"] = {"path": "forbidden.csv"}
    elif case == "top_level_heavy_compute_array":
        result["heavy_compute_consumed"] = ["gpu"]
    elif case == "top_level_total_timesteps_nonzero":
        result["total_timesteps"] = 1
    elif case == "top_level_full_ppo_metadata_present_numeric":
        result["full_ppo_metadata_present"] = 1
    elif case == "top_level_ppo_config_alternate_string":
        result["ppo_config"] = "available"
    elif case == "top_level_stage_partial":
        result["training_stage"] = "partial"

    with pytest.raises(evaluator.DailyPortfolioSb3EvaluatorError, match="NOT_RUN projection"):
        evaluator.model_verdict(result)


def test_model_not_run_projection_allows_only_explicit_empty_denied_not_run_states() -> None:
    result = aggregate.aggregate_cell_records(_base_records())
    result["fresh_oos_consumed"] = 0
    result["raw_oos_data_read"] = None
    result["fresh_oos_download"] = "DENIED"
    result["raw_oos_download"] = "NOT_RUN"
    result["heavy_compute_consumed"] = []
    result["full_ppo_metadata"] = {}
    result["full_ppo_metadata_present"] = 0
    result["total_timesteps"] = 0
    result["ppo_config"] = ""
    result["training_stage"] = "NOT_RUN"

    assert evaluator.model_verdict(result)["verdict"] == "NOT_RUN"


def test_deterministic_canonical_outputs_paired_bootstrap_and_shuffle_delta() -> None:
    records = _base_records()
    canonical_a = aggregate.canonical_aggregate_bytes(records)
    canonical_b = aggregate.canonical_aggregate_bytes(list(reversed(records)))

    assert canonical_a == canonical_b

    result = aggregate.aggregate_cell_records(records)
    shuffle = result["shuffle_paired_delta"]
    assert shuffle["available"] is True
    assert shuffle["bootstrap_ci"]["bit_generator"] == "PCG64"
    assert shuffle["bootstrap_ci"]["seed"] == 0
    assert shuffle["bootstrap_ci"]["replicates"] == 10_000
    assert shuffle["bootstrap_ci"]["ci_indices"] == {"lower": 249, "upper": 9749}
    assert shuffle["bootstrap_ci"]["lower"] == pytest.approx(0.0205)
    assert shuffle["bootstrap_ci"]["upper"] == pytest.approx(0.055499999999999994)
    expected_deltas = [
        row["net_return"] - 0.01
        for row in result["primary_23bp"]["seed_metrics"]
    ]
    assert shuffle["seed_deltas"] == pytest.approx(expected_deltas)
    assert aggregate.paired_bootstrap_iqm_ci(expected_deltas) == shuffle["bootstrap_ci"]

    with pytest.raises(aggregate.DailyPortfolioSb3AggregateError):
        aggregate.paired_bootstrap_iqm_ci(expected_deltas, seed=1)


def test_comparator_tie_ranking_uses_protocol_order() -> None:
    records = _base_records()
    for record in records:
        record["metrics"]["economic_net_return"] = 0.01
        if record["variant_id"] == "cost-23bp":
            record["metrics"]["comparators"] = _comparator_metrics({comparator: 0.01 for comparator in protocol.COMPARATOR_ORDER if comparator != "ppo_policy"})

    result = aggregate.aggregate_cell_records(records)
    assert [row["comparator_id"] for row in result["comparator_ranking"]] == list(protocol.COMPARATOR_ORDER)


def test_23bp_verdict_ignores_0bp_46bp_sensitivities_and_score_independence() -> None:
    records = _base_records()
    baseline = evaluator.evaluate_aggregate(aggregate.aggregate_cell_records(records))

    mutated = _base_records()
    for record in mutated:
        if record["variant_id"] == "cost-00bp":
            record["metrics"]["economic_net_return"] = -999.0
        if record["variant_id"] == "cost-46bp":
            record["metrics"]["economic_net_return"] = 999.0
    changed = evaluator.evaluate_aggregate(aggregate.aggregate_cell_records(mutated))

    assert changed["research_verdict"] == baseline["research_verdict"]
    assert changed["primary_verdict_cost_bps"] == 23
    assert changed["sensitivities_verdict_input"] is False
    assert changed["model_verdict"]["verdict"] == "NOT_RUN"
    assert changed["score_independence"] == {
        "model_verdict_contributes_to_engineering_score": False,
        "positive_alpha_bonus_points": 0,
        "model_verdict_points": 0,
        "research_verdict_points": 0,
    }
    assert set(changed["false_locks"]) == {
        "promotion_allowed",
        "model_build_allowed",
        "paper_forward_allowed",
        "live_broker_order_allowed",
        "profitability_claim_allowed",
        "go_summary_allowed",
    }
    assert all(value is False for value in changed["false_locks"].values())


def test_evaluation_canonical_bytes_are_deterministic() -> None:
    result = aggregate.aggregate_cell_records(_base_records())
    assert evaluator.canonical_evaluation_bytes(result) == evaluator.canonical_evaluation_bytes(deepcopy(result))
