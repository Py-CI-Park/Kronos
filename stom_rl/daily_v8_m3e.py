"""Pure deterministic M3E contextual-bandit validation engine.

This module deliberately accepts already-loaded train and validation rows only.  It
performs no dataset, report, artifact, or test-split I/O.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from typing import Any, Iterable, Sequence

from stom_rl.daily_v6_train import CAPITAL, COST_SCENARIOS, PRIMARY_COST, SLOT_BUDGET, SLOTS
from stom_rl.daily_v7_linucb import LinUcbModel, _context
from stom_rl.daily_v7_train import EXPOSURE_REPS, _exposure_matched_random, compute_baselines

SEEDS: tuple[int, ...] = (0, 1, 2, 3, 4)
ENTER_SCORE_THRESHOLD = 0.0
TRAIN_PASSES = 1
TRAINER_VERSION = "kronos_v8_m3e_contextual_bandit.v1"


def _sessions(rows: Iterable[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Return chronological sessions, retaining symbols exactly as supplied."""
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["session_yyyymmdd"]].append(row)
    return [sorted(grouped[session], key=lambda row: row["symbol"]) for session in sorted(grouped)]


def _select(rows: Sequence[dict[str, Any]], scores: Sequence[float]) -> list[int]:
    """Select positive-score, descending-score/ascending-symbol, distinct slots."""
    ranked = sorted(range(len(rows)), key=lambda index: (-scores[index], rows[index]["symbol"]))
    selected: list[int] = []
    symbols: set[str] = set()
    for index in ranked:
        if scores[index] <= ENTER_SCORE_THRESHOLD:
            break
        symbol = rows[index]["symbol"]
        if symbol in symbols:
            continue
        selected.append(index)
        symbols.add(symbol)
        if len(selected) == SLOTS:
            break
    return selected


def _theta_hash(theta: Sequence[float]) -> str:
    encoded = json.dumps(list(theta), separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def fit_member(train_rows: list[dict[str, Any]], seed: int, *, labels: Sequence[float] | None = None) -> dict[str, Any]:
    """Fit exactly one online LinUCB pass with the frozen seed's session order."""
    if seed not in SEEDS:
        raise ValueError(f"seed must be one of frozen seeds {SEEDS}")
    sessions = _sessions(train_rows)
    flattened = [row for session in sessions for row in session]
    if labels is not None and len(labels) != len(flattened):
        raise ValueError("labels must align with chronological flattened train rows")
    offsets: list[int] = []
    offset = 0
    for session in sessions:
        offsets.append(offset)
        offset += len(session)
    order = list(range(len(sessions)))
    random.Random(seed).shuffle(order)
    model = LinUcbModel()
    for session_index in order:
        rows = sessions[session_index]
        contexts = [_context(row) for row in rows]
        selected = _select(rows, model.ucb_scores(contexts))
        for index in selected:
            reward = labels[offsets[session_index] + index] if labels is not None else rows[index]["future_return_h1_1520_proxy"]
            model.update(contexts[index], float(reward) - PRIMARY_COST)
    theta = model.theta()
    return {"seed": seed, "theta": theta, "member_hash": _theta_hash(theta), "train_passes": TRAIN_PASSES}


def ensemble_scores(rows: Sequence[dict[str, Any]], thetas: Sequence[Sequence[float]]) -> list[float]:
    """Raw unweighted arithmetic mean of member greedy scores before ranking."""
    if not thetas:
        raise ValueError("at least one member theta is required")
    width = len(thetas[0])
    if any(len(theta) != width for theta in thetas):
        raise ValueError("member theta dimensions must match")
    return [sum(sum(weight * value for weight, value in zip(theta, _context(row))) for theta in thetas) / len(thetas)
            for row in rows]


def evaluate_scores(validation_rows: list[dict[str, Any]], scores: Sequence[float]) -> tuple[dict[str, Any], list[int]]:
    """Evaluate supplied policy scores with frozen 60M/5M-slot/23bp accounting."""
    if len(validation_rows) != len(scores):
        raise ValueError("scores must align with validation rows")
    grouped: dict[Any, list[tuple[dict[str, Any], float]]] = defaultdict(list)
    for row, score in zip(validation_rows, scores):
        grouped[row["session_yyyymmdd"]].append((row, score))
    navs = {cost: CAPITAL for cost in COST_SCENARIOS}
    high_water = CAPITAL
    max_drawdown = 0.0
    trades = turnover_days = max_positions = 0
    max_invested = 0.0
    pick_counts: list[int] = []
    for session_id in sorted(grouped):
        scored_session = sorted(grouped[session_id], key=lambda item: item[0]["symbol"])
        session = [row for row, _ in scored_session]
        selected = _select(session, [score for _, score in scored_session])
        pick_counts.append(len(selected))
        max_positions = max(max_positions, len(selected))
        max_invested = max(max_invested, len(selected) * SLOT_BUDGET)
        if selected:
            turnover_days += 1
        trades += len(selected)
        for cost in navs:
            navs[cost] += sum(SLOT_BUDGET * (session[index]["future_return_h1_1520_proxy"] - cost) for index in selected)
        high_water = max(high_water, navs[PRIMARY_COST])
        max_drawdown = max(max_drawdown, (high_water - navs[PRIMARY_COST]) / high_water)
    return ({"nav": navs[PRIMARY_COST], "total_net_return_pct": (navs[PRIMARY_COST] / CAPITAL - 1.0) * 100,
             "max_drawdown": max_drawdown, "trade_count": trades, "turnover_days": turnover_days,
             "cost_scenario_navs": {f"{cost:.4f}": navs[cost] for cost in COST_SCENARIOS},
             "max_positions_per_session": max_positions, "max_invested_krw": max_invested}, pick_counts)


def evaluate_ensemble(
    validation_rows: list[dict[str, Any]],
    members: Sequence[dict[str, Any]],
    *,
    include_scores: bool = True,
) -> dict[str, Any]:
    """Score an ensemble once: member scores are averaged before selection."""
    scores = ensemble_scores(validation_rows, [member["theta"] for member in members])
    metrics, pick_counts = evaluate_scores(validation_rows, scores)
    result = {"metrics": metrics, "pick_counts": pick_counts,
              "member_hashes": [member["member_hash"] for member in members]}
    if include_scores:
        result["scores"] = scores
    return result


def _control_check(validation_rows: list[dict[str, Any]], result: dict[str, Any], *, seed: int) -> dict[str, Any]:
    exposure = _exposure_matched_random(validation_rows, result["pick_counts"], reps=EXPOSURE_REPS, seed=seed)
    return {"metrics": result["metrics"], "pick_counts": result["pick_counts"], "exposure_matched_random": exposure,
            "control_fails": result["metrics"]["nav"] > exposure["threshold_nav"]}


def decide_verdict(full_metrics: dict[str, Any], jackknife_metrics: dict[str, dict[str, Any]], baselines: dict[str, Any],
                   shuffled_controls: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    """Apply the frozen M3E screen; it intentionally has no GO outcome."""
    baseline_nav = max(baselines[name]["nav"] for name in ("rule_topk_ret5", "rule_topk_low_vol", "rule_topk_inst", "random_topk"))
    failures = sorted(name for name, control in shuffled_controls.items() if control["control_fails"])
    full_passes = full_metrics["nav"] > CAPITAL and full_metrics["nav"] > baseline_nav
    passed_jackknives = sorted(name for name, result in jackknife_metrics.items()
                               if result["metrics"]["nav"] > CAPITAL and result["metrics"]["nav"] > baseline_nav)
    if failures:
        return "NO_GO", [f"shuffled-label control failure(s): {failures}"], passed_jackknives
    if full_passes and len(passed_jackknives) >= 4:
        return "OOS_OPEN_ELIGIBLE_REUSED_VALIDATION_SCREEN", ["full ensemble and at least four jackknives clear the frozen validation screen"], passed_jackknives
    if full_passes and 1 <= len(passed_jackknives) <= 3:
        return "INCONCLUSIVE", ["full ensemble clears but only one to three jackknives clear the frozen validation screen"], passed_jackknives
    return "NO_GO", ["frozen full-ensemble/jackknife validation screen not satisfied"], passed_jackknives


def fit_evaluate(train_rows: list[dict[str, Any]], validation_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the complete five-member M3E validation screen without any I/O."""
    members = [fit_member(train_rows, seed) for seed in SEEDS]
    full = evaluate_ensemble(validation_rows, members, include_scores=False)
    jackknives = {str(omitted): evaluate_ensemble(
        validation_rows,
        [member for member in members if member["seed"] != omitted],
        include_scores=False,
    ) for omitted in SEEDS}
    baselines = compute_baselines(validation_rows)
    labels = [row["future_return_h1_1520_proxy"] for session in _sessions(train_rows) for row in session]
    shuffled_members = []
    for seed in SEEDS:
        shuffled = labels.copy()
        random.Random(seed).shuffle(shuffled)
        shuffled_members.append(fit_member(train_rows, seed, labels=shuffled))
    shuffled_full = evaluate_ensemble(validation_rows, shuffled_members, include_scores=False)
    shuffled_jackknives = {str(omitted): evaluate_ensemble(
        validation_rows,
        [member for member in shuffled_members if member["seed"] != omitted],
        include_scores=False,
    ) for omitted in SEEDS}
    shuffled_controls = {"full": _control_check(validation_rows, shuffled_full, seed=0),
                         **{f"jackknife_{omitted}": _control_check(validation_rows, result, seed=omitted)
                            for omitted, result in ((int(name), value) for name, value in shuffled_jackknives.items())}}
    verdict, reasons, passed_jackknives = decide_verdict(full["metrics"], jackknives, baselines, shuffled_controls)
    return {"members": members, "member_hashes": [member["member_hash"] for member in members],
            "thetas": [member["theta"] for member in members], "ensemble": full, "jackknives": jackknives,
            "baselines": baselines,
            "exposure_matched_random": _exposure_matched_random(validation_rows, full["pick_counts"], reps=EXPOSURE_REPS, seed=0),
            "shuffled_label_ensemble": {"members": shuffled_members, "ensemble": shuffled_full, "jackknives": shuffled_jackknives,
                                          "controls": shuffled_controls},
            "verdict": {"value": verdict, "reasons": reasons, "passing_jackknives": passed_jackknives}}


def build_manifest(result: dict[str, Any]) -> dict[str, Any]:
    """Build an in-memory research manifest; the untouched test state is immutable."""
    return {**result, "trainer_version": TRAINER_VERSION, "seeds": list(SEEDS),
            "policy": {"train_passes": TRAIN_PASSES, "score_rule": "raw unweighted mean before ranking; score > 0",
                       "ranking": "descending score, ascending symbol", "capital_krw": CAPITAL,
                       "slot_budget_krw": SLOT_BUDGET, "slots": SLOTS, "primary_cost_rate": PRIMARY_COST},
            "test": {"state": "NOT_RUN"},
            "false_research_locks": {"promotion_allowed": False, "model_build_allowed": False,
                                     "paper_forward_allowed": False, "live_broker_order_allowed": False,
                                     "profitability_claim_allowed": False, "go_summary_allowed": False,
                                     "test_evaluation_allowed": False, "test_data_exposure_allowed": False}}
