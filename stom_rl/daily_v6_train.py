"""Research-only preregistered tabular-Q trainer for the V6 joined dataset."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

NUMERIC_FIELDS: tuple[str, ...] = (
    "ret_1d_prev", "ret_5d_prev", "ret_20d_prev", "vol_z_20",
    "foreign_ratio_prev", "foreign_ratio_delta_5", "inst_netbuy_norm_5",
    "entry_close_1520", "future_return_h1_1520_proxy",
)
REQUIRED_FIELDS: tuple[str, ...] = ("symbol", "table", "session_yyyymmdd", "split", *NUMERIC_FIELDS)

SCHEMA_VERSION = "kronos_v6_train_run.v1"
DEFAULT_OUT_ROOT = Path("webui/rl_runs/v6_daily_h1")
REPO_ROOT = Path(__file__).resolve().parents[1]
PREREG_PATH = REPO_ROOT / "docs" / "kronos_v6_prereg_h1_2026-07-19.json"
CAPITAL = 60_000_000.0
SLOT_BUDGET = 5_000_000.0
SLOTS = 10
PRIMARY_COST = 0.0023
COST_SCENARIOS = (0.0, PRIMARY_COST, 0.0046)
STATE_FEATURES = ("ret_5d_prev", "vol_z_20", "foreign_ratio_delta_5", "inst_netbuy_norm_5")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def load_dataset(run_id: str, out_root: Path | str = DEFAULT_OUT_ROOT) -> dict[str, Any]:
    """Load and integrity-check a joined dataset, retaining its label exclusions."""
    if not run_id or Path(run_id).name != run_id:
        raise ValueError("run_id must be a non-empty single path component")
    directory = Path(out_root) / run_id
    csv_path, manifest_path = directory / "dataset.csv", directory / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "kronos_v6_joined_dataset.v1":
        raise ValueError("dataset manifest has unexpected schema_version")
    actual_sha = _sha256_file(csv_path)
    if actual_sha != manifest.get("dataset_sha256"):
        raise ValueError("dataset.csv sha256 does not match dataset manifest")
    rows: list[dict[str, Any]] = []
    missing_labels = {"train": 0, "val": 0, "test": 0, "other": 0}
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        missing_fields = [field for field in REQUIRED_FIELDS if field not in fieldnames]
        if missing_fields:
            raise ValueError(f"dataset.csv is missing joined-dataset contract columns: {missing_fields}")
        for raw in reader:
            row: dict[str, Any] = {"symbol": raw["symbol"], "session_yyyymmdd": int(raw["session_yyyymmdd"]),
                                   "split": raw["split"]}
            for field in NUMERIC_FIELDS:
                row[field] = _number(raw[field])
            if row["future_return_h1_1520_proxy"] is None:
                missing_labels[row["split"] if row["split"] in missing_labels else "other"] += 1
                continue
            rows.append(row)
    return {"rows": rows, "manifest": manifest, "dataset_sha256": actual_sha,
            "missing_h1_label_excluded": missing_labels}


def _quantile_boundaries(values: Iterable[float], divisions: int) -> list[float]:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("train split has no usable values for state bucketing")
    output = []
    for index in range(1, divisions):
        position = (len(ordered) - 1) * index / divisions
        low, high = math.floor(position), math.ceil(position)
        output.append(ordered[low] + (ordered[high] - ordered[low]) * (position - low))
    return output


def compute_bucket_boundaries(train_rows: Iterable[dict[str, Any]]) -> dict[str, list[float]]:
    rows = list(train_rows)
    return {"ret_5d_prev": _quantile_boundaries((r["ret_5d_prev"] for r in rows if r["ret_5d_prev"] is not None), 5),
            "vol_z_20": _quantile_boundaries((r["vol_z_20"] for r in rows if r["vol_z_20"] is not None), 3)}


def _ordinal(value: float | None, boundaries: list[float]) -> int | str:
    if value is None:
        return "missing"
    return sum(value > boundary for boundary in boundaries)


def _sign(value: float | None) -> int | str:
    if value is None:
        return "missing"
    return 1 if value > 0 else -1 if value < 0 else 0


def bucket_state(row: dict[str, Any], boundaries: dict[str, list[float]]) -> tuple[Any, ...]:
    return (_ordinal(row["ret_5d_prev"], boundaries["ret_5d_prev"]),
            _ordinal(row["vol_z_20"], boundaries["vol_z_20"]),
            _sign(row["foreign_ratio_delta_5"]), _sign(row["inst_netbuy_norm_5"]))


def _sessions(rows: Iterable[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["session_yyyymmdd"]].append(row)
    return [sorted(grouped[session], key=lambda row: row["symbol"]) for session in sorted(grouped)]
def _top_distinct(scored: Iterable[tuple[float, dict[str, Any]]]) -> list[tuple[float, dict[str, Any]]]:
    selected: list[tuple[float, dict[str, Any]]] = []
    symbols: set[str] = set()
    for score, row in sorted(scored, key=lambda item: (-item[0], item[1]["symbol"])):
        if row["symbol"] not in symbols:
            selected.append((score, row))
            symbols.add(row["symbol"])
        if len(selected) == SLOTS:
            break
    return selected



def _evaluate(q: dict[tuple[Any, ...], list[float]], rows: list[dict[str, Any]], boundaries: dict[str, list[float]],
              cost_rates: Iterable[float] = COST_SCENARIOS, rng: random.Random | None = None,
              epsilon: float = 0.0) -> dict[str, Any]:
    navs = {cost: CAPITAL for cost in cost_rates}
    high_water = CAPITAL
    max_drawdown = 0.0
    trades = 0
    turnover_days = 0
    max_positions = 0
    max_invested = 0.0
    for candidates in _sessions(rows):
        selected = []
        for row in candidates:
            values = q.get(bucket_state(row, boundaries), [0.0, 0.0])
            enter = values[1] > values[0]
            if rng is not None and epsilon and rng.random() < epsilon:
                enter = not enter
            if enter:
                selected.append((values[1] - values[0], row))
        selected = _top_distinct(selected)
        max_positions = max(max_positions, len(selected))
        max_invested = max(max_invested, len(selected) * SLOT_BUDGET)
        if selected:
            turnover_days += 1
        trades += len(selected)
        for cost in navs:
            navs[cost] += sum(SLOT_BUDGET * (row["future_return_h1_1520_proxy"] - cost) for _, row in selected)
        high_water = max(high_water, navs[PRIMARY_COST])
        max_drawdown = max(max_drawdown, (high_water - navs[PRIMARY_COST]) / high_water)
    return {"nav": navs[PRIMARY_COST], "total_net_return_pct": (navs[PRIMARY_COST] / CAPITAL - 1.0) * 100,
            "max_drawdown": max_drawdown, "trade_count": trades, "turnover_days": turnover_days,
            "cost_scenario_navs": {f"{cost:.4f}": navs[cost] for cost in COST_SCENARIOS},
            "max_positions_per_session": max_positions, "max_invested_krw": max_invested}


def _rule_topk(rows: list[dict[str, Any]], random_seed: int | None = None) -> dict[str, Any]:
    navs = {cost: CAPITAL for cost in COST_SCENARIOS}
    rng = random.Random(random_seed)
    for candidates in _sessions(rows):
        eligible = [row for row in candidates if row["ret_5d_prev"] is not None]
        if random_seed is None:
            scored = [(row["ret_5d_prev"], row) for row in eligible]
        else:
            scored = [(0.0, row) for row in rng.sample(eligible, len(eligible))]
        chosen = [row for _, row in _top_distinct(scored)]
        for cost in navs:
            navs[cost] += sum(SLOT_BUDGET * (row["future_return_h1_1520_proxy"] - cost) for row in chosen)
    return {"nav": navs[PRIMARY_COST], "cost_scenario_navs": {f"{cost:.4f}": navs[cost] for cost in COST_SCENARIOS}}


def _train_seed(train_rows: list[dict[str, Any]], val_rows: list[dict[str, Any]], boundaries: dict[str, list[float]],
                seed: int, max_episodes: int, events: list[dict[str, Any]], labels: list[float] | None = None) -> dict[str, Any]:
    rng = random.Random(seed)
    q: dict[tuple[Any, ...], list[float]] = {}
    best_q: dict[tuple[Any, ...], list[float]] = {}
    curve: list[float] = []
    negative_slopes = 0
    best_rolling = -math.inf
    for episode in range(1, max_episodes + 1):
        epsilon = max(0.01, 0.1 * (0.98 ** (episode - 1)))
        reward_sum = 0.0
        label_index = 0
        for candidates in _sessions(train_rows):
            selected: set[int] = set()
            scored = []
            for index, row in enumerate(candidates):
                state = bucket_state(row, boundaries)
                values = q.setdefault(state, [0.0, 0.0])
                enter = values[1] > values[0]
                if rng.random() < epsilon:
                    enter = not enter
                if enter:
                    scored.append((values[1] - values[0], index))
            for _, row in _top_distinct(
                (score, candidates[index]) for score, index in scored
            ):
                selected.add(candidates.index(row))
            for index, row in enumerate(candidates):
                state = bucket_state(row, boundaries)
                action = 1 if index in selected else 0
                reward = (labels[label_index] if labels is not None else row["future_return_h1_1520_proxy"]) - PRIMARY_COST if action else 0.0
                q[state][action] += 0.1 * (reward - q[state][action])
                reward_sum += reward
                label_index += 1
        metrics = _evaluate(q, val_rows, boundaries)
        curve.append(metrics["nav"])
        rolling = sum(curve[-3:]) / min(3, len(curve))
        if rolling > best_rolling:
            best_rolling, best_q, best_episode = rolling, deepcopy(q), episode
        if len(curve) >= 4 and rolling < sum(curve[-4:-1]) / 3:
            negative_slopes += 1
        else:
            negative_slopes = 0
        events.append({"seed": seed, "episode": episode, "train_reward_sum": reward_sum,
                       "val_nav": metrics["nav"], "epsilon": epsilon})
        if episode >= 10 and negative_slopes >= 3:
            break
    final = _evaluate(best_q, val_rows, boundaries)
    return {"q": best_q, "episodes_ran": len(curve), "best_episode": best_episode,
            "val_nav_curve": curve, "final_val_metrics": final}


def run_training(dataset_run_id: str, *, seeds: Iterable[int] = (0, 1, 2), smoke: bool = False,
                 final_test: bool = False, out_root: Path | str = DEFAULT_OUT_ROOT,
                 train_run_id: str | None = None) -> dict[str, Any]:
    """Train only on train rows and select frozen checkpoints solely by validation NAV."""
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
    events: list[dict[str, Any]] = []
    max_episodes = min(12, 300) if smoke else 300
    seed_results = {str(seed): _train_seed(train_rows, val_rows, boundaries, seed, max_episodes, events) for seed in seed_list}
    baselines = {"no_trade": {"nav": CAPITAL, "cost_scenario_navs": {f"{cost:.4f}": CAPITAL for cost in COST_SCENARIOS}},
                 "rule_topk_ret5": _rule_topk(val_rows), "random_topk": _rule_topk(val_rows, 0)}
    shuffled: dict[str, Any] = {}
    source_labels = [row["future_return_h1_1520_proxy"] for row in train_rows]
    for seed in seed_list:
        shuffled_labels = source_labels.copy()
        random.Random(seed).shuffle(shuffled_labels)
        result = _train_seed(train_rows, val_rows, boundaries, seed, max_episodes, [], shuffled_labels)
        shuffled[str(seed)] = {key: value for key, value in result.items() if key != "q"}
        shuffled[str(seed)]["train_labels_sha256"] = hashlib.sha256(repr(source_labels).encode()).hexdigest()
        shuffled[str(seed)]["shuffled_train_labels_sha256"] = hashlib.sha256(repr(shuffled_labels).encode()).hexdigest()
        shuffled[str(seed)]["train_labels_changed"] = shuffled_labels != source_labels
    rule_nav = max(baselines["rule_topk_ret5"]["nav"], baselines["random_topk"]["nav"])
    qualifying = [seed for seed, result in seed_results.items()
                  if result["final_val_metrics"]["nav"] > CAPITAL and result["final_val_metrics"]["nav"] >= rule_nav]
    control_passes = any(result["final_val_metrics"]["nav"] > CAPITAL for result in shuffled.values())
    if control_passes:
        verdict, reasons = "NO_GO", ["shuffled-label control exceeded no-trade at primary cost"]
    elif len(qualifying) >= 2:
        verdict, reasons = "GO_CANDIDATE_VALIDATION_ONLY", ["at least two seeds satisfy validation criterion"]
    elif len(qualifying) == 1:
        verdict, reasons = "INCONCLUSIVE", ["only one seed satisfies validation criterion"]
    else:
        verdict, reasons = "NO_GO", ["validation criterion not met"]
    test: dict[str, Any] = {"state": "NOT_RUN"}
    if final_test and len(qualifying) >= 2:
        test = {"state": "RUN", "per_seed": {seed: _evaluate(seed_results[seed]["q"], test_rows, boundaries)
                for seed in seed_results}}
    prereg_bytes = PREREG_PATH.read_bytes()
    run_id = train_run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not run_id or Path(run_id).name != run_id:
        raise ValueError("train_run_id must be a non-empty single path component")
    output = root / dataset_run_id / f"train_{run_id}"
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": SCHEMA_VERSION, "prereg": {"id": json.loads(prereg_bytes)["prereg_id"], "sha256": hashlib.sha256(prereg_bytes).hexdigest()},
                "dataset_run_id": dataset_run_id, "dataset_csv_sha256": loaded["dataset_sha256"],
                "missing_h1_label_excluded": loaded["missing_h1_label_excluded"], "seeds": seed_list,
                "bucket_boundaries": boundaries, "hyperparams": {"alpha": 0.1, "epsilon_initial": 0.1,
                "epsilon_decay": 0.98, "epsilon_floor": 0.01, "episodes_max": max_episodes,
                "capital_krw": CAPITAL, "slot_budget_krw": SLOT_BUDGET, "slots": SLOTS,
                "max_invested_krw": SLOT_BUDGET * SLOTS, "primary_cost_rate": PRIMARY_COST,
                "nav_formula": "NAV = 60000000 + sum over completed positions of 5000000 * (future_return_h1_1520_proxy - cost_rate); reserve remains untouched."},
                "per_seed": {seed: {key: value for key, value in result.items() if key != "q"} for seed, result in seed_results.items()},
                "baselines": baselines, "shuffled_label_control": shuffled, "test": test,
                "verdict_candidate": {"value": verdict, "reasons": reasons},
                "false_research_locks": {"promotion_allowed": False, "model_build_allowed": False,
                "paper_forward_allowed": False, "live_broker_order_allowed": False,
                "profitability_claim_allowed": False, "go_summary_allowed": False},
                "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    (output / "events.jsonl").write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")
    (output / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"output_dir": output, "manifest": manifest}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the preregistered V6 research trainer.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--final-test", action="store_true")
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    args = parser.parse_args()
    seeds = tuple(int(value) for value in args.seeds.split(",") if value.strip())
    result = run_training(args.dataset, seeds=seeds, smoke=args.smoke, final_test=args.final_test, out_root=args.out_root)
    print(json.dumps({"output_dir": str(result["output_dir"]), "verdict_candidate": result["manifest"]["verdict_candidate"]}))


if __name__ == "__main__":
    main()
