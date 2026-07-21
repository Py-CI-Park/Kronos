"""V7 M1: preregistered tabular-Q v2 trainer with exposure-matched negative control.

Reuses the audited V6 dataset loader / bucketing / per-seed trainer and changes
only what KRONOS-V7-PREREG-M1-2026-07-20 froze:

- five seeds with a majority (>=3/5) validation criterion,
- RULE baselines extended to momentum / low-volatility / institutional-flow,
- the shuffled-label negative control is judged against an exposure-matched
  random distribution (same per-session pick counts) instead of no-trade only.

Research-only. No live/broker/profit claims; verdict tokens are recorded raw.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from stom_rl.daily_v6_train import (
    CAPITAL,
    COST_SCENARIOS,
    DEFAULT_OUT_ROOT,
    PRIMARY_COST,
    SLOT_BUDGET,
    SLOTS,
    _evaluate,
    _sessions,
    _top_distinct,
    _train_seed,
    bucket_state,
    compute_bucket_boundaries,
    load_dataset,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PREREG_PATH_V7_M1 = REPO_ROOT / "docs" / "kronos_v7_prereg_m1_2026-07-20.json"
SCHEMA_VERSION = "kronos_v6_train_run.v1"
TRAINER_VERSION = "kronos_v7_m1_tabular_q.v2"
DEFAULT_SEEDS: tuple[int, ...] = (0, 1, 2, 3, 4)
EXPOSURE_REPS = 20


def _session_pick_counts(q: dict[tuple[Any, ...], list[float]], rows: list[dict[str, Any]],
                         boundaries: dict[str, list[float]]) -> list[int]:
    """Replay the greedy policy over validation sessions and record pick counts."""
    counts: list[int] = []
    for candidates in _sessions(rows):
        scored = []
        for row in candidates:
            values = q.get(bucket_state(row, boundaries), [0.0, 0.0])
            if values[1] > values[0]:
                scored.append((values[1] - values[0], row))
        counts.append(len(_top_distinct(scored)))
    return counts


def _exposure_matched_random(rows: list[dict[str, Any]], pick_counts: list[int], *, reps: int, seed: int) -> dict[str, Any]:
    """NAV distribution of random policies matched on per-session pick counts."""
    sessions = _sessions(rows)
    rng = random.Random(1000 + seed)
    navs: list[float] = []
    for _ in range(reps):
        nav = CAPITAL
        for session_rows, count in zip(sessions, pick_counts):
            if count <= 0:
                continue
            unique: dict[str, dict[str, Any]] = {}
            for row in session_rows:
                unique.setdefault(row["symbol"], row)
            pool = list(unique.values())
            for row in rng.sample(pool, min(count, len(pool))):
                nav += SLOT_BUDGET * (row["future_return_h1_1520_proxy"] - PRIMARY_COST)
        navs.append(nav)
    mean = sum(navs) / len(navs)
    variance = sum((nav - mean) ** 2 for nav in navs) / (len(navs) - 1) if len(navs) > 1 else 0.0
    std = math.sqrt(variance)
    return {"reps": reps, "mean_nav": mean, "std_nav": std,
            "threshold_nav": max(CAPITAL, mean + 2.0 * std), "total_picks": sum(pick_counts)}


def _rule_baseline(rows: list[dict[str, Any]], score: Callable[[dict[str, Any]], float | None]) -> dict[str, Any]:
    navs = {cost: CAPITAL for cost in COST_SCENARIOS}
    for candidates in _sessions(rows):
        scored = [(value, row) for row in candidates if (value := score(row)) is not None]
        chosen = [row for _, row in _top_distinct(scored)]
        for cost in navs:
            navs[cost] += sum(SLOT_BUDGET * (row["future_return_h1_1520_proxy"] - cost) for row in chosen)
    return {"nav": navs[PRIMARY_COST], "cost_scenario_navs": {f"{cost:.4f}": navs[cost] for cost in COST_SCENARIOS}}


def _random_baseline(rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    navs = {cost: CAPITAL for cost in COST_SCENARIOS}
    for candidates in _sessions(rows):
        unique: dict[str, dict[str, Any]] = {}
        for row in candidates:
            unique.setdefault(row["symbol"], row)
        pool = list(unique.values())
        chosen = rng.sample(pool, min(SLOTS, len(pool)))
        for cost in navs:
            navs[cost] += sum(SLOT_BUDGET * (row["future_return_h1_1520_proxy"] - cost) for row in chosen)
    return {"nav": navs[PRIMARY_COST], "cost_scenario_navs": {f"{cost:.4f}": navs[cost] for cost in COST_SCENARIOS}}


def compute_baselines(val_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "no_trade": {"nav": CAPITAL, "cost_scenario_navs": {f"{cost:.4f}": CAPITAL for cost in COST_SCENARIOS}},
        "rule_topk_ret5": _rule_baseline(val_rows, lambda row: row["ret_5d_prev"]),
        "rule_topk_low_vol": _rule_baseline(val_rows, lambda row: None if row["vol_z_20"] is None else -row["vol_z_20"]),
        "rule_topk_inst": _rule_baseline(val_rows, lambda row: row["inst_netbuy_norm_5"]),
        "random_topk": _random_baseline(val_rows, 0),
    }


def decide_verdict(seed_results: dict[str, dict[str, Any]], baselines: dict[str, Any],
                   control_checks: dict[str, dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    rule_nav = max(baselines[name]["nav"] for name in ("rule_topk_ret5", "rule_topk_low_vol", "rule_topk_inst", "random_topk"))
    qualifying = [seed for seed, result in sorted(seed_results.items())
                  if result["final_val_metrics"]["nav"] > CAPITAL and result["final_val_metrics"]["nav"] >= rule_nav]
    failed_controls = [seed for seed, check in sorted(control_checks.items()) if check["control_fails"]]
    if failed_controls:
        return "NO_GO", [f"shuffled-label control exceeded exposure-matched threshold for seeds {failed_controls}"], qualifying
    if len(qualifying) >= 3:
        return "GO_CANDIDATE_VALIDATION_ONLY", ["at least three of five seeds satisfy validation criterion"], qualifying
    if qualifying:
        return "INCONCLUSIVE", [f"only {len(qualifying)} seed(s) satisfy validation criterion"], qualifying
    return "NO_GO", ["validation criterion not met"], qualifying


def run_training(dataset_run_id: str, *, seeds: Iterable[int] = DEFAULT_SEEDS, smoke: bool = False,
                 final_test: bool = False, out_root: Path | str = DEFAULT_OUT_ROOT,
                 train_run_id: str | None = None, prereg_path: Path | str = PREREG_PATH_V7_M1) -> dict[str, Any]:
    root = Path(out_root)
    loaded = load_dataset(dataset_run_id, root)
    rows = loaded["rows"]
    train_rows = [row for row in rows if row["split"] == "train"]
    val_rows = [row for row in rows if row["split"] == "val"]
    test_rows = [row for row in rows if row["split"] == "test"]
    if not train_rows or not val_rows:
        raise ValueError("dataset requires non-empty train and validation rows with H1 labels")
    seed_list = list(seeds)
    if not seed_list or len(set(seed_list)) != len(seed_list):
        raise ValueError("seeds must be unique and non-empty")
    if smoke:
        seed_list = seed_list[:1]
    boundaries = compute_bucket_boundaries(train_rows)
    max_episodes = 12 if smoke else 300
    events: list[dict[str, Any]] = []
    seed_results = {str(seed): _train_seed(train_rows, val_rows, boundaries, seed, max_episodes, events)
                    for seed in seed_list}
    baselines = compute_baselines(val_rows)

    shuffled: dict[str, Any] = {}
    exposure_controls: dict[str, Any] = {}
    control_checks: dict[str, Any] = {}
    source_labels = [row["future_return_h1_1520_proxy"] for row in train_rows]
    source_sha = hashlib.sha256(repr(source_labels).encode()).hexdigest()
    for seed in seed_list:
        shuffled_labels = source_labels.copy()
        random.Random(seed).shuffle(shuffled_labels)
        result = _train_seed(train_rows, val_rows, boundaries, seed, max_episodes, [], shuffled_labels)
        pick_counts = _session_pick_counts(result["q"], val_rows, boundaries)
        exposure = _exposure_matched_random(val_rows, pick_counts, reps=EXPOSURE_REPS, seed=seed)
        control_nav = result["final_val_metrics"]["nav"]
        control_checks[str(seed)] = {
            "control_nav": control_nav,
            "threshold_nav": exposure["threshold_nav"],
            "control_fails": control_nav > exposure["threshold_nav"],
        }
        exposure_controls[str(seed)] = exposure
        entry = {key: value for key, value in result.items() if key != "q"}
        entry["train_labels_sha256"] = source_sha
        entry["shuffled_train_labels_sha256"] = hashlib.sha256(repr(shuffled_labels).encode()).hexdigest()
        entry["train_labels_changed"] = shuffled_labels != source_labels
        shuffled[str(seed)] = entry

    verdict, reasons, qualifying = decide_verdict(seed_results, baselines, control_checks)
    test: dict[str, Any] = {"state": "NOT_RUN"}
    if final_test and verdict == "GO_CANDIDATE_VALIDATION_ONLY":
        test = {"state": "RUN", "per_seed": {seed: _evaluate(seed_results[seed]["q"], test_rows, boundaries)
                                             for seed in seed_results}}

    prereg_file = Path(prereg_path)
    prereg_bytes = prereg_file.read_bytes()
    run_id = train_run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not run_id or Path(run_id).name != run_id:
        raise ValueError("train_run_id must be a non-empty single path component")
    output = root / dataset_run_id / f"train_{run_id}"
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "trainer_version": TRAINER_VERSION,
        "prereg": {"id": json.loads(prereg_bytes)["prereg_id"], "sha256": hashlib.sha256(prereg_bytes).hexdigest()},
        "dataset_run_id": dataset_run_id,
        "dataset_csv_sha256": loaded["dataset_sha256"],
        "missing_h1_label_excluded": loaded["missing_h1_label_excluded"],
        "seeds": seed_list,
        "bucket_boundaries": boundaries,
        "hyperparams": {
            "alpha": 0.1, "epsilon_initial": 0.1, "epsilon_decay": 0.98, "epsilon_floor": 0.01,
            "episodes_max": max_episodes, "capital_krw": CAPITAL, "slot_budget_krw": SLOT_BUDGET,
            "slots": SLOTS, "max_invested_krw": SLOT_BUDGET * SLOTS, "primary_cost_rate": PRIMARY_COST,
            "exposure_matched_reps": EXPOSURE_REPS,
            "nav_formula": "NAV = 60000000 + sum over completed positions of 5000000 * (future_return_h1_1520_proxy - cost_rate); reserve remains untouched.",
        },
        "per_seed": {seed: {key: value for key, value in result.items() if key != "q"}
                     for seed, result in seed_results.items()},
        "baselines": baselines,
        "shuffled_label_control": shuffled,
        "exposure_matched_control": exposure_controls,
        "negative_control_checks": control_checks,
        "qualifying_seeds": qualifying,
        "test": test,
        "verdict_candidate": {"value": verdict, "reasons": reasons},
        "false_research_locks": {"promotion_allowed": False, "model_build_allowed": False,
                                 "paper_forward_allowed": False, "live_broker_order_allowed": False,
                                 "profitability_claim_allowed": False, "go_summary_allowed": False},
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    (output / "events.jsonl").write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")
    (output / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"output_dir": output, "manifest": manifest}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the preregistered V7 M1 tabular-Q v2 trainer.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--seeds", default=",".join(str(seed) for seed in DEFAULT_SEEDS))
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--final-test", action="store_true")
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--prereg", default=str(PREREG_PATH_V7_M1))
    args = parser.parse_args()
    seeds = tuple(int(value) for value in args.seeds.split(",") if value.strip())
    result = run_training(args.dataset, seeds=seeds, smoke=args.smoke, final_test=args.final_test,
                          out_root=args.out_root, prereg_path=args.prereg)
    print(json.dumps({"output_dir": str(result["output_dir"]),
                      "verdict_candidate": result["manifest"]["verdict_candidate"],
                      "qualifying_seeds": result["manifest"]["qualifying_seeds"]}))


if __name__ == "__main__":
    main()
