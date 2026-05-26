"""Portfolio RL smoke runner.

This page-4 runner proves the portfolio environment contract and artifact
schema without requiring a heavy RL dependency.  The deterministic smoke policy
uses the same fixed Discrete action layout that an RL agent will consume.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pandas as pd

from .portfolio_env import ACTION_HOLD, PortfolioEnv, PortfolioEnvConfig


DEFAULT_PORTFOLIO_TRAIN_OUTPUT_DIR = Path("webui") / "rl_runs" / "stom_portfolio_smoke"


@dataclass(frozen=True)
class PortfolioTrainConfig:
    candidate_path: Optional[str] = None
    output_dir: str = str(DEFAULT_PORTFOLIO_TRAIN_OUTPUT_DIR)
    top_k_candidates: int = 3
    max_positions: int = 2
    max_steps: int = 12
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


def _deterministic_action(env: PortfolioEnv, info: Mapping[str, Any]) -> int:
    mask = list(info["action_mask"])
    sell_offset = 1 + env.config.top_k_candidates
    if int(info["current_step"]) % 4 == 3:
        for action in range(sell_offset, len(mask)):
            if mask[action]:
                return action
    for action in range(1, sell_offset):
        if mask[action]:
            return action
    return ACTION_HOLD


def run_portfolio_smoke(config: PortfolioTrainConfig) -> Dict[str, Any]:
    candidates = None
    if config.candidate_path:
        candidates = pd.read_csv(config.candidate_path, encoding="utf-8-sig")
    env = PortfolioEnv(
        PortfolioEnvConfig(
            candidate_path=config.candidate_path,
            top_k_candidates=config.top_k_candidates,
            max_positions=config.max_positions,
            initial_cash=config.initial_cash,
            cost_bps=config.cost_bps,
            slippage_bps=config.slippage_bps,
            seed=config.seed,
        ),
        candidates=candidates,
    )
    observation, info = env.reset(seed=config.seed)
    terminated = False
    truncated = False
    rewards: List[float] = []
    steps = 0
    while not (terminated or truncated):
        if config.max_steps and steps >= int(config.max_steps):
            break
        action = _deterministic_action(env, info)
        observation, reward, terminated, truncated, info = env.step(action)
        rewards.append(float(reward))
        steps += 1

    output_dir = Path(config.output_dir)
    payload: Dict[str, Any] = {
        "mode": "stom_rl_portfolio_train_smoke",
        "config": asdict(config),
        "summary": {
            "steps": steps,
            "final_nav": float(info["nav"]),
            "total_reward": float(sum(rewards)),
            "trade_count": int(info["trade_count"]),
            "invalid_action_count": int(info["invalid_action_count"]),
            "observation_shape": list(observation.shape),
            "action_space_n": int(env.action_space.n),
            "candidate_mask_last": info["candidate_mask"],
            "holding_mask_last": info["holding_mask"],
        },
        "artifacts": {
            "output_dir": str(output_dir),
            "summary_json": str(output_dir / "portfolio_train_summary.json"),
            "actions_csv": str(output_dir / "actions.csv"),
            "trades_csv": str(output_dir / "trades.csv"),
            "nav_csv": str(output_dir / "nav.csv"),
            "blocked_actions_json": str(output_dir / "blocked_actions.json"),
        },
    }
    if config.write_artifacts:
        _write_json(output_dir / "portfolio_train_summary.json", payload)
        _write_csv(
            output_dir / "actions.csv",
            env.action_log,
            ["timestamp", "action", "action_type", "slot", "invalid_action", "blocked_reason", "reward", "nav_after"],
        )
        _write_csv(output_dir / "trades.csv", env.trade_log, ["timestamp", "symbol", "side", "price", "quantity", "gross_value", "cost", "cash_after", "realized_pnl"])
        _write_csv(output_dir / "nav.csv", env.nav_log, ["timestamp", "step", "nav", "cash", "position_count"])
        _write_json(output_dir / "blocked_actions.json", {"blocked_actions": env.invalid_actions})
    return payload


def _parse_args(argv: Optional[Sequence[str]] = None) -> PortfolioTrainConfig:
    parser = argparse.ArgumentParser(description="Run portfolio environment smoke training.")
    parser.add_argument("--smoke", action="store_true", help="Use deterministic synthetic candidates when no CSV is provided.")
    parser.add_argument("--candidate-csv", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_PORTFOLIO_TRAIN_OUTPUT_DIR))
    parser.add_argument("--top-k-candidates", type=int, default=3)
    parser.add_argument("--max-positions", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--initial-cash", type=float, default=1_000_000.0)
    parser.add_argument("--cost-bps", type=float, default=25.0)
    parser.add_argument("--slippage-bps", type=float, default=0.0)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    return PortfolioTrainConfig(
        candidate_path=args.candidate_csv,
        output_dir=args.output_dir,
        top_k_candidates=args.top_k_candidates,
        max_positions=args.max_positions,
        max_steps=args.max_steps,
        seed=args.seed,
        initial_cash=args.initial_cash,
        cost_bps=args.cost_bps,
        slippage_bps=args.slippage_bps,
        write_artifacts=not args.no_write,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    payload = run_portfolio_smoke(_parse_args(argv))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
