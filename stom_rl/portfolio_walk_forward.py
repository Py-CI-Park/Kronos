"""Portfolio walk-forward smoke validation with deterministic baselines."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .portfolio_env import ACTION_HOLD, PortfolioEnv, PortfolioEnvConfig, synthetic_candidates


DEFAULT_PORTFOLIO_WALK_FORWARD_OUTPUT_DIR = Path("webui") / "rl_runs" / "stom_portfolio_walk_forward"
DEFAULT_BASELINES = ("no_trade", "equal_weight_candidate", "buy_and_hold", "rule_baseline")


@dataclass(frozen=True)
class PortfolioWalkForwardConfig:
    candidate_path: Optional[str] = None
    output_dir: str = str(DEFAULT_PORTFOLIO_WALK_FORWARD_OUTPUT_DIR)
    n_folds: int = 2
    baselines: Tuple[str, ...] = DEFAULT_BASELINES
    top_k_candidates: int = 3
    max_positions: int = 2
    max_steps_per_fold: int = 24
    seed: int = 100
    initial_cash: float = 1_000_000.0
    cost_bps: float = 25.0
    slippage_bps: float = 0.0
    write_artifacts: bool = True


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _load_candidates(path: Optional[str]) -> pd.DataFrame:
    if path:
        frame = pd.read_csv(path, encoding="utf-8-sig")
    else:
        frame = synthetic_candidates()
    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    return frame.dropna(subset=["timestamp"]).sort_values(["timestamp", "symbol"]).reset_index(drop=True)


def _fold_candidate_frames(frame: pd.DataFrame, n_folds: int) -> List[Tuple[int, pd.DataFrame, str, str]]:
    timestamps = sorted(pd.Timestamp(ts) for ts in frame["timestamp"].dropna().unique())
    if not timestamps:
        raise ValueError("No timestamps available for portfolio walk-forward")
    bins = np.array_split(np.asarray(timestamps, dtype=object), min(max(1, int(n_folds)), len(timestamps)))
    folds: List[Tuple[int, pd.DataFrame, str, str]] = []
    for idx, bucket in enumerate(bins):
        bucket_ts = [pd.Timestamp(ts) for ts in bucket]
        if not bucket_ts:
            continue
        subset = frame[frame["timestamp"].isin(bucket_ts)].copy()
        folds.append((idx, subset, bucket_ts[0].isoformat(), bucket_ts[-1].isoformat()))
    return folds


def _action_for_policy(policy: str, env: PortfolioEnv, info: Mapping[str, Any]) -> int:
    mask = list(info["action_mask"])
    sell_offset = 1 + env.config.top_k_candidates
    if policy == "no_trade":
        return ACTION_HOLD
    if policy == "buy_and_hold":
        for action in range(1, sell_offset):
            if mask[action]:
                return action
        return ACTION_HOLD
    if policy == "rule_baseline" and int(info["current_step"]) % 4 == 3:
        for action in range(sell_offset, len(mask)):
            if mask[action]:
                return action
    for action in range(1, sell_offset):
        if mask[action]:
            return action
    for action in range(sell_offset, len(mask)):
        if policy == "rule_baseline" and mask[action]:
            return action
    return ACTION_HOLD


def _run_fold_policy(
    *,
    candidates: pd.DataFrame,
    fold_index: int,
    policy: str,
    config: PortfolioWalkForwardConfig,
) -> Dict[str, Any]:
    env = PortfolioEnv(
        PortfolioEnvConfig(
            top_k_candidates=config.top_k_candidates,
            max_positions=config.max_positions,
            initial_cash=config.initial_cash,
            cost_bps=config.cost_bps,
            slippage_bps=config.slippage_bps,
            seed=config.seed + fold_index,
        ),
        candidates=candidates,
    )
    _, info = env.reset(seed=config.seed + fold_index)
    terminated = False
    truncated = False
    rewards: List[float] = []
    steps = 0
    while not (terminated or truncated):
        if config.max_steps_per_fold and steps >= int(config.max_steps_per_fold):
            break
        action = _action_for_policy(policy, env, info)
        _, reward, terminated, truncated, info = env.step(action)
        rewards.append(float(reward))
        steps += 1
    return {
        "fold_index": fold_index,
        "policy": policy,
        "steps": steps,
        "final_nav": float(info["nav"]),
        "return_pct": (float(info["nav"]) / float(config.initial_cash) - 1.0) * 100.0,
        "trade_count": int(info["trade_count"]),
        "invalid_action_count": int(info["invalid_action_count"]),
        "total_reward": float(sum(rewards)),
    }


def run_portfolio_walk_forward(config: PortfolioWalkForwardConfig) -> Dict[str, Any]:
    candidates = _load_candidates(config.candidate_path)
    folds = _fold_candidate_frames(candidates, config.n_folds)
    rows: List[Dict[str, Any]] = []
    periods: List[Dict[str, Any]] = []
    for fold_index, fold_candidates, start, end in folds:
        periods.append(
            {
                "fold_index": fold_index,
                "period_start": start,
                "period_end": end,
                "candidate_count": int(len(fold_candidates)),
            }
        )
        for policy in config.baselines:
            rows.append(
                {
                    "period_start": start,
                    "period_end": end,
                    **_run_fold_policy(
                        candidates=fold_candidates,
                        fold_index=fold_index,
                        policy=policy,
                        config=config,
                    ),
                }
            )
    ranking = sorted(rows, key=lambda row: float(row["return_pct"]), reverse=True)
    output_dir = Path(config.output_dir)
    payload: Dict[str, Any] = {
        "mode": "stom_rl_portfolio_walk_forward",
        "config": asdict(config),
        "summary": {
            "n_folds": len(folds),
            "baseline_count": len(config.baselines),
            "smoke_success": bool(rows),
            "best_policy_by_return": ranking[0]["policy"] if ranking else None,
            "performance_success": bool(ranking and float(ranking[0]["return_pct"]) > 0.0),
            "performance_note": "Engineering completion requires generated fold artifacts; alpha superiority is tracked separately.",
        },
        "fold_periods": periods,
        "folds": rows,
        "artifacts": {
            "output_dir": str(output_dir),
            "report_json": str(output_dir / "portfolio_walk_forward_report.json"),
            "folds_csv": str(output_dir / "portfolio_walk_forward_folds.csv"),
        },
    }
    if config.write_artifacts:
        _write_json(output_dir / "portfolio_walk_forward_report.json", payload)
        _write_csv(
            output_dir / "portfolio_walk_forward_folds.csv",
            rows,
            [
                "fold_index",
                "period_start",
                "period_end",
                "policy",
                "steps",
                "final_nav",
                "return_pct",
                "trade_count",
                "invalid_action_count",
                "total_reward",
            ],
        )
    return payload


def _parse_baselines(raw: str) -> Tuple[str, ...]:
    baselines = tuple(part.strip() for part in raw.split(",") if part.strip())
    unknown = sorted(set(baselines) - set(DEFAULT_BASELINES))
    if unknown:
        raise ValueError(f"Unknown portfolio baselines: {unknown}. Available: {sorted(DEFAULT_BASELINES)}")
    return baselines


def _parse_args(argv: Optional[Sequence[str]] = None) -> PortfolioWalkForwardConfig:
    parser = argparse.ArgumentParser(description="Run portfolio walk-forward smoke validation.")
    parser.add_argument("--candidate-csv", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_PORTFOLIO_WALK_FORWARD_OUTPUT_DIR))
    parser.add_argument("--n-folds", type=int, default=2)
    parser.add_argument("--baselines", default=",".join(DEFAULT_BASELINES))
    parser.add_argument("--top-k-candidates", type=int, default=3)
    parser.add_argument("--max-positions", type=int, default=2)
    parser.add_argument("--max-steps-per-fold", type=int, default=24)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--initial-cash", type=float, default=1_000_000.0)
    parser.add_argument("--cost-bps", type=float, default=25.0)
    parser.add_argument("--slippage-bps", type=float, default=0.0)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    return PortfolioWalkForwardConfig(
        candidate_path=args.candidate_csv,
        output_dir=args.output_dir,
        n_folds=args.n_folds,
        baselines=_parse_baselines(args.baselines),
        top_k_candidates=args.top_k_candidates,
        max_positions=args.max_positions,
        max_steps_per_fold=args.max_steps_per_fold,
        seed=args.seed,
        initial_cash=args.initial_cash,
        cost_bps=args.cost_bps,
        slippage_bps=args.slippage_bps,
        write_artifacts=not args.no_write,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    payload = run_portfolio_walk_forward(_parse_args(argv))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
