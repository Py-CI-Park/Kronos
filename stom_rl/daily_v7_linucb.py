"""V7 M3: preregistered LinUCB contextual-bandit trainer over the V6 joined dataset.

Identical 60,000,000 KRW / 10-slot accounting, baselines, and exposure-matched
negative control as M1/M2 so results are directly comparable. Frozen by
KRONOS-V7-PREREG-M3-2026-07-20; research-only, no live/profit claims.

Interpretability: the final linear coefficients per feature are recorded in the
run manifest (and therefore in the HTML report appendix inputs).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from stom_rl.daily_v6_train import (
    CAPITAL,
    DEFAULT_OUT_ROOT,
    PRIMARY_COST,
    _sessions,
    load_dataset,
)
from stom_rl.daily_v7_ppo import FEATURES, _row_features, decide_verdict_m2, evaluate_policy_scores
from stom_rl.daily_v7_train import EXPOSURE_REPS, _exposure_matched_random, compute_baselines

REPO_ROOT = Path(__file__).resolve().parents[1]
PREREG_PATH_V7_M3 = REPO_ROOT / "docs" / "kronos_v7_prereg_m3_2026-07-20.json"
SCHEMA_VERSION = "kronos_v6_train_run.v1"
TRAINER_VERSION = "kronos_v7_m3_linucb.v1"
DEFAULT_SEEDS: tuple[int, ...] = (0, 1, 2)
CONTEXT_DIM = len(FEATURES) + 1  # + bias
ALPHA_UCB = 1.0
RIDGE_LAMBDA = 1.0
SLOTS = 10
ENTER_SCORE_THRESHOLD = 0.0
EVAL_CHECKPOINTS = 6


def _context(row: dict[str, Any]) -> list[float]:
    values, _ = _row_features(row)
    return values + [1.0]


def _mat_vec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(row[j] * vector[j] for j in range(len(vector))) for row in matrix]


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve A x = b via Gaussian elimination (A is SPD, dim 8)."""
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        a[col], a[pivot] = a[pivot], a[col]
        factor = a[col][col]
        a[col] = [value / factor for value in a[col]]
        for r in range(n):
            if r != col and a[r][col] != 0.0:
                scale = a[r][col]
                a[r] = [a[r][j] - scale * a[col][j] for j in range(n + 1)]
    return [a[i][n] for i in range(n)]


class LinUcbModel:
    def __init__(self) -> None:
        self.a_matrix = [[RIDGE_LAMBDA if i == j else 0.0 for j in range(CONTEXT_DIM)] for i in range(CONTEXT_DIM)]
        self.b_vector = [0.0] * CONTEXT_DIM

    def theta(self) -> list[float]:
        return _solve(self.a_matrix, self.b_vector)

    def ucb_scores(self, contexts: list[list[float]]) -> list[float]:
        theta = self.theta()
        scores = []
        for x in contexts:
            mean = sum(t * v for t, v in zip(theta, x))
            a_inv_x = _solve(self.a_matrix, x)
            variance = max(sum(v * w for v, w in zip(x, a_inv_x)), 0.0)
            scores.append(mean + ALPHA_UCB * math.sqrt(variance))
        return scores

    def update(self, x: list[float], reward: float) -> None:
        for i in range(CONTEXT_DIM):
            for j in range(CONTEXT_DIM):
                self.a_matrix[i][j] += x[i] * x[j]
            self.b_vector[i] += reward * x[i]


def _greedy_scores(model: LinUcbModel, rows: list[dict[str, Any]]) -> list[float]:
    theta = model.theta()
    return [sum(t * v for t, v in zip(theta, _context(row))) for row in rows]


def _train_linucb_seed(train_sessions: list[list[dict[str, Any]]], val_rows: list[dict[str, Any]], *, seed: int,
                       events: list[dict[str, Any]], labels: list[float] | None = None) -> dict[str, Any]:
    label_offsets: list[int] = []
    offset = 0
    for session_rows in train_sessions:
        label_offsets.append(offset)
        offset += len(session_rows)
    order = list(range(len(train_sessions)))
    random.Random(seed).shuffle(order)
    model = LinUcbModel()
    curve: list[float] = []
    checkpoint_stride = max(len(order) // EVAL_CHECKPOINTS, 1)
    for step, session_index in enumerate(order, start=1):
        session_rows = train_sessions[session_index]
        contexts = [_context(row) for row in session_rows]
        scores = model.ucb_scores(contexts)
        ranked = sorted(range(len(session_rows)), key=lambda i: (-scores[i], session_rows[i]["symbol"]))
        picked: list[int] = []
        symbols: set[str] = set()
        for index in ranked:
            if scores[index] <= ENTER_SCORE_THRESHOLD:
                break
            symbol = session_rows[index]["symbol"]
            if symbol in symbols:
                continue
            picked.append(index)
            symbols.add(symbol)
            if len(picked) == SLOTS:
                break
        for index in picked:
            label = labels[label_offsets[session_index] + index] if labels is not None else session_rows[index]["future_return_h1_1520_proxy"]
            model.update(contexts[index], label - PRIMARY_COST)
        if step % checkpoint_stride == 0 or step == len(order):
            metrics, _ = evaluate_policy_scores(val_rows, _greedy_scores(model, val_rows), threshold=ENTER_SCORE_THRESHOLD)
            curve.append(metrics["nav"])
            events.append({"seed": seed, "episode": len(curve), "val_nav": metrics["nav"],
                           "sessions_seen": step, "shuffled": labels is not None})
    final_metrics, pick_counts = evaluate_policy_scores(val_rows, _greedy_scores(model, val_rows), threshold=ENTER_SCORE_THRESHOLD)
    best_episode = max(range(len(curve)), key=lambda i: curve[i]) + 1 if curve else 0
    return {"model": model, "episodes_ran": len(curve), "best_episode": best_episode,
            "val_nav_curve": curve, "final_val_metrics": final_metrics, "pick_counts": pick_counts,
            "theta": dict(zip([*FEATURES, "bias"], model.theta()))}


def run_training(dataset_run_id: str, *, seeds: Iterable[int] = DEFAULT_SEEDS, smoke: bool = False,
                 final_test: bool = False, out_root: Path | str = DEFAULT_OUT_ROOT,
                 train_run_id: str | None = None, prereg_path: Path | str = PREREG_PATH_V7_M3) -> dict[str, Any]:
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
    train_sessions = _sessions(train_rows)
    events: list[dict[str, Any]] = []
    seed_results = {str(seed): _train_linucb_seed(train_sessions, val_rows, seed=seed, events=events)
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
        result = _train_linucb_seed(train_sessions, val_rows, seed=seed, events=[], labels=shuffled_labels)
        exposure = _exposure_matched_random(val_rows, result["pick_counts"], reps=EXPOSURE_REPS, seed=seed)
        control_nav = result["final_val_metrics"]["nav"]
        control_checks[str(seed)] = {"control_nav": control_nav, "threshold_nav": exposure["threshold_nav"],
                                     "control_fails": control_nav > exposure["threshold_nav"]}
        exposure_controls[str(seed)] = exposure
        shuffled[str(seed)] = {
            "episodes_ran": result["episodes_ran"], "best_episode": result["best_episode"],
            "val_nav_curve": result["val_nav_curve"], "final_val_metrics": result["final_val_metrics"],
            "train_labels_sha256": source_sha,
            "shuffled_train_labels_sha256": hashlib.sha256(repr(shuffled_labels).encode()).hexdigest(),
            "train_labels_changed": shuffled_labels != source_labels,
        }

    verdict, reasons, qualifying = decide_verdict_m2(seed_results, baselines, control_checks)
    test: dict[str, Any] = {"state": "NOT_RUN"}
    if final_test and verdict == "GO_CANDIDATE_VALIDATION_ONLY":
        per_seed_test = {}
        for seed, result in seed_results.items():
            metrics, _ = evaluate_policy_scores(test_rows, _greedy_scores(result["model"], test_rows),
                                                threshold=ENTER_SCORE_THRESHOLD)
            per_seed_test[seed] = metrics
        test = {"state": "RUN", "per_seed": per_seed_test}

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
        "hyperparams": {
            "algorithm": "linucb_contextual_bandit", "alpha_ucb": ALPHA_UCB, "ridge_lambda": RIDGE_LAMBDA,
            "context_dim": CONTEXT_DIM, "enter_score_threshold": ENTER_SCORE_THRESHOLD,
            "capital_krw": CAPITAL, "slot_budget_krw": 5000000.0, "slots": SLOTS,
            "max_invested_krw": 50000000.0, "primary_cost_rate": PRIMARY_COST,
            "exposure_matched_reps": EXPOSURE_REPS,
            "nav_formula": "NAV = 60000000 + sum over completed positions of 5000000 * (future_return_h1_1520_proxy - cost_rate); reserve remains untouched.",
        },
        "per_seed": {seed: {key: value for key, value in result.items() if key not in {"model", "pick_counts"}}
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
    parser = argparse.ArgumentParser(description="Run the preregistered V7 M3 LinUCB trainer.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--seeds", default=",".join(str(seed) for seed in DEFAULT_SEEDS))
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--final-test", action="store_true")
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--prereg", default=str(PREREG_PATH_V7_M3))
    args = parser.parse_args()
    seeds = tuple(int(value) for value in args.seeds.split(",") if value.strip())
    result = run_training(args.dataset, seeds=seeds, smoke=args.smoke, final_test=args.final_test,
                          out_root=args.out_root, prereg_path=args.prereg)
    print(json.dumps({"output_dir": str(result["output_dir"]),
                      "verdict_candidate": result["manifest"]["verdict_candidate"],
                      "qualifying_seeds": result["manifest"]["qualifying_seeds"]}))


if __name__ == "__main__":
    main()
