"""V7 M2: preregistered SB3 PPO trainer over the V6 joined dataset.

Identical 60,000,000 KRW / 10-slot accounting, baselines, and negative
controls as the M1 tabular-Q v2 trainer so results are directly comparable.
Frozen by KRONOS-V7-PREREG-M2-2026-07-20; research-only, no live/profit claims.

The gymnasium environment walks one trading session per episode; the policy
score used for portfolio evaluation is P(action=enter), and the session
portfolio is the top-10 distinct symbols among rows with P > 0.5.
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
    COST_SCENARIOS,
    DEFAULT_OUT_ROOT,
    PRIMARY_COST,
    SLOT_BUDGET,
    SLOTS,
    _sessions,
    _top_distinct,
    load_dataset,
)
from stom_rl.daily_v7_train import (
    EXPOSURE_REPS,
    _exposure_matched_random,
    compute_baselines,
)


def decide_verdict_m2(seed_results: dict[str, dict[str, Any]], baselines: dict[str, Any],
                      control_checks: dict[str, dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    """Frozen M2 rule: >=2 of 3 seeds qualify; exposure-matched control dominates."""
    rule_nav = max(baselines[name]["nav"] for name in ("rule_topk_ret5", "rule_topk_low_vol", "rule_topk_inst", "random_topk"))
    qualifying = [seed for seed, result in sorted(seed_results.items())
                  if result["final_val_metrics"]["nav"] > CAPITAL and result["final_val_metrics"]["nav"] >= rule_nav]
    failed_controls = [seed for seed, check in sorted(control_checks.items()) if check["control_fails"]]
    if failed_controls:
        return "NO_GO", [f"shuffled-label control exceeded exposure-matched threshold for seeds {failed_controls}"], qualifying
    if len(qualifying) >= 2:
        return "GO_CANDIDATE_VALIDATION_ONLY", ["at least two of three seeds satisfy validation criterion"], qualifying
    if qualifying:
        return "INCONCLUSIVE", ["only one seed satisfies validation criterion"], qualifying
    return "NO_GO", ["validation criterion not met"], qualifying

REPO_ROOT = Path(__file__).resolve().parents[1]
PREREG_PATH_V7_M2 = REPO_ROOT / "docs" / "kronos_v7_prereg_m2_2026-07-20.json"
SCHEMA_VERSION = "kronos_v6_train_run.v1"
TRAINER_VERSION = "kronos_v7_m2_ppo.v1"
DEFAULT_SEEDS: tuple[int, ...] = (0, 1, 2)
FEATURES: tuple[str, ...] = (
    "ret_1d_prev", "ret_5d_prev", "ret_20d_prev", "vol_z_20",
    "foreign_ratio_prev", "foreign_ratio_delta_5", "inst_netbuy_norm_5",
)
OBS_DIM = len(FEATURES) + 3  # + missing_count/7 + slots_used/10 + session_progress
REWARD_SCALE = 100.0
ENTER_THRESHOLD = 0.5
TOTAL_TIMESTEPS_FULL = 120_000
TOTAL_TIMESTEPS_SMOKE = 8_000
EVAL_CHECKPOINTS = 6


def _row_features(row: dict[str, Any]) -> tuple[list[float], int]:
    values: list[float] = []
    missing = 0
    for name in FEATURES:
        value = row.get(name)
        if value is None or not math.isfinite(value):
            values.append(0.0)
            missing += 1
        else:
            values.append(float(value))
    return values, missing


def _observation(row: dict[str, Any], slots_used: int, index: int, session_size: int) -> Any:
    import numpy as np

    values, missing = _row_features(row)
    values.extend([missing / len(FEATURES), slots_used / SLOTS, index / max(session_size, 1)])
    return np.asarray(values, dtype=np.float32)


def make_env(sessions: list[list[dict[str, Any]]], *, labels: list[float] | None = None, seed: int = 0):
    """Gymnasium env: one session per episode, candidate rows in symbol order."""
    import gymnasium
    import numpy as np

    label_offsets: list[int] = []
    offset = 0
    for session_rows in sessions:
        label_offsets.append(offset)
        offset += len(session_rows)

    class DailySlotEnv(gymnasium.Env):
        metadata = {"render_modes": []}

        def __init__(self) -> None:
            self.observation_space = gymnasium.spaces.Box(low=-np.inf, high=np.inf, shape=(OBS_DIM,), dtype=np.float32)
            self.action_space = gymnasium.spaces.Discrete(2)
            self._rng = random.Random(seed)
            self._session_index = 0
            self._row_index = 0
            self._slots_used = 0
            self._held: set[str] = set()

        def _session(self) -> list[dict[str, Any]]:
            return sessions[self._session_index]

        def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
            super().reset(seed=seed)
            self._session_index = self._rng.randrange(len(sessions))
            self._row_index = 0
            self._slots_used = 0
            self._held = set()
            session = self._session()
            return _observation(session[0], 0, 0, len(session)), {}

        def step(self, action: int):
            session = self._session()
            row = session[self._row_index]
            reward = 0.0
            enter = int(action) == 1 and self._slots_used < SLOTS and row["symbol"] not in self._held
            if enter:
                label = labels[label_offsets[self._session_index] + self._row_index] if labels is not None else row["future_return_h1_1520_proxy"]
                reward = (label - PRIMARY_COST) * REWARD_SCALE
                self._slots_used += 1
                self._held.add(row["symbol"])
            self._row_index += 1
            terminated = self._row_index >= len(session)
            if terminated:
                observation = _observation(row, self._slots_used, len(session), len(session))
            else:
                observation = _observation(session[self._row_index], self._slots_used, self._row_index, len(session))
            return observation, reward, terminated, False, {}

    return DailySlotEnv()


def _enter_probabilities(model: Any, rows: list[dict[str, Any]]) -> list[float]:
    """P(action=enter) per row with neutral portfolio context (score for ranking)."""
    import numpy as np
    import torch

    batch = np.stack([_observation(row, 0, 0, 1) for row in rows])
    with torch.no_grad():
        tensor = torch.as_tensor(batch, device=model.policy.device)
        distribution = model.policy.get_distribution(tensor)
        probs = distribution.distribution.probs[:, 1].detach().cpu().numpy()
    return [float(value) for value in probs]


def evaluate_policy_scores(rows: list[dict[str, Any]], scores: list[float]) -> tuple[dict[str, Any], list[int]]:
    """Portfolio evaluation identical in accounting to the tabular trainers."""
    by_id = {id(row): score for row, score in zip(rows, scores)}
    navs = {cost: CAPITAL for cost in COST_SCENARIOS}
    high_water, max_drawdown = CAPITAL, 0.0
    trades = turnover_days = max_positions = 0
    max_invested = 0.0
    pick_counts: list[int] = []
    for candidates in _sessions(rows):
        scored = [(by_id[id(row)], row) for row in candidates if by_id[id(row)] > ENTER_THRESHOLD]
        selected = _top_distinct(scored)
        pick_counts.append(len(selected))
        max_positions = max(max_positions, len(selected))
        max_invested = max(max_invested, len(selected) * SLOT_BUDGET)
        if selected:
            turnover_days += 1
        trades += len(selected)
        for cost in navs:
            navs[cost] += sum(SLOT_BUDGET * (row["future_return_h1_1520_proxy"] - cost) for _, row in selected)
        high_water = max(high_water, navs[PRIMARY_COST])
        max_drawdown = max(max_drawdown, (high_water - navs[PRIMARY_COST]) / high_water)
    metrics = {"nav": navs[PRIMARY_COST], "total_net_return_pct": (navs[PRIMARY_COST] / CAPITAL - 1.0) * 100,
               "max_drawdown": max_drawdown, "trade_count": trades, "turnover_days": turnover_days,
               "cost_scenario_navs": {f"{cost:.4f}": navs[cost] for cost in COST_SCENARIOS},
               "max_positions_per_session": max_positions, "max_invested_krw": max_invested}
    return metrics, pick_counts


def _train_ppo_seed(train_sessions: list[list[dict[str, Any]]], val_rows: list[dict[str, Any]], *, seed: int,
                    total_timesteps: int, events: list[dict[str, Any]],
                    labels: list[float] | None = None) -> dict[str, Any]:
    import copy

    from stable_baselines3 import PPO

    env = make_env(train_sessions, labels=labels, seed=seed)
    model = PPO("MlpPolicy", env, seed=seed, n_steps=2048, batch_size=256, learning_rate=3e-4,
                gamma=0.99, verbose=0, device="auto")
    chunk = max(total_timesteps // EVAL_CHECKPOINTS, 1)
    curve: list[float] = []
    best_nav = -math.inf
    best_state = None
    best_checkpoint = 0
    for checkpoint in range(1, EVAL_CHECKPOINTS + 1):
        model.learn(total_timesteps=chunk, reset_num_timesteps=False, progress_bar=False)
        scores = _enter_probabilities(model, val_rows)
        metrics, _ = evaluate_policy_scores(val_rows, scores)
        curve.append(metrics["nav"])
        events.append({"seed": seed, "episode": checkpoint, "val_nav": metrics["nav"],
                       "timesteps": checkpoint * chunk, "shuffled": labels is not None})
        if metrics["nav"] > best_nav:
            best_nav = metrics["nav"]
            best_state = copy.deepcopy(model.policy.state_dict())
            best_checkpoint = checkpoint
    if best_state is not None:
        model.policy.load_state_dict(best_state)
    scores = _enter_probabilities(model, val_rows)
    final_metrics, pick_counts = evaluate_policy_scores(val_rows, scores)
    return {"model": model, "episodes_ran": len(curve), "best_episode": best_checkpoint,
            "val_nav_curve": curve, "final_val_metrics": final_metrics, "pick_counts": pick_counts}


def run_training(dataset_run_id: str, *, seeds: Iterable[int] = DEFAULT_SEEDS, smoke: bool = False,
                 final_test: bool = False, out_root: Path | str = DEFAULT_OUT_ROOT,
                 train_run_id: str | None = None, prereg_path: Path | str = PREREG_PATH_V7_M2,
                 total_timesteps: int | None = None) -> dict[str, Any]:
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
    budget = total_timesteps if total_timesteps is not None else (TOTAL_TIMESTEPS_SMOKE if smoke else TOTAL_TIMESTEPS_FULL)
    train_sessions = _sessions(train_rows)
    events: list[dict[str, Any]] = []

    seed_results: dict[str, dict[str, Any]] = {}
    for seed in seed_list:
        result = _train_ppo_seed(train_sessions, val_rows, seed=seed, total_timesteps=budget, events=events)
        seed_results[str(seed)] = result

    baselines = compute_baselines(val_rows)

    shuffled: dict[str, Any] = {}
    exposure_controls: dict[str, Any] = {}
    control_checks: dict[str, Any] = {}
    source_labels = [row["future_return_h1_1520_proxy"] for row in train_rows]
    source_sha = hashlib.sha256(repr(source_labels).encode()).hexdigest()
    for seed in seed_list:
        shuffled_labels = source_labels.copy()
        random.Random(seed).shuffle(shuffled_labels)
        result = _train_ppo_seed(train_sessions, val_rows, seed=seed, total_timesteps=budget,
                                 events=[], labels=shuffled_labels)
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
            scores = _enter_probabilities(result["model"], test_rows)
            metrics, _ = evaluate_policy_scores(test_rows, scores)
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
            "algorithm": "sb3_ppo_mlp", "n_steps": 2048, "batch_size": 256, "learning_rate": 0.0003,
            "gamma": 0.99, "total_timesteps": budget, "eval_checkpoints": EVAL_CHECKPOINTS,
            "reward_scale": REWARD_SCALE, "enter_threshold": ENTER_THRESHOLD,
            "capital_krw": CAPITAL, "slot_budget_krw": SLOT_BUDGET, "slots": SLOTS,
            "max_invested_krw": SLOT_BUDGET * SLOTS, "primary_cost_rate": PRIMARY_COST,
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
    parser = argparse.ArgumentParser(description="Run the preregistered V7 M2 PPO trainer.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--seeds", default=",".join(str(seed) for seed in DEFAULT_SEEDS))
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--final-test", action="store_true")
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--prereg", default=str(PREREG_PATH_V7_M2))
    parser.add_argument("--total-timesteps", type=int, default=None)
    args = parser.parse_args()
    seeds = tuple(int(value) for value in args.seeds.split(",") if value.strip())
    result = run_training(args.dataset, seeds=seeds, smoke=args.smoke, final_test=args.final_test,
                          out_root=args.out_root, prereg_path=args.prereg, total_timesteps=args.total_timesteps)
    print(json.dumps({"output_dir": str(result["output_dir"]),
                      "verdict_candidate": result["manifest"]["verdict_candidate"],
                      "qualifying_seeds": result["manifest"]["qualifying_seeds"]}))


if __name__ == "__main__":
    main()
