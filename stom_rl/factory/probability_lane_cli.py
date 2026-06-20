"""CLI runner for preregistered probability lane experiments.

Registers the run in the factory queue (preregistration enforced), executes
the lane, and records the final verdict. ``supervised gate`` evidence only —
NOT RL, not live-ready, no profit claim. Cost basis 23bp.

Modes (frozen in the preregistration documents):
- ``edge_all``           docs/stom_probability_lane_prereg_2026-06-11.md
- ``stacked_ts_imb``     docs/stom_probability_lane_stacked_prereg_2026-06-11.md (primary)
- ``matched_threshold``  docs/stom_probability_lane_stacked_prereg_2026-06-11.md (supporting)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .experiment_queue import enqueue_experiment, mark_done, mark_failed, mark_running
from .probability_lane import (
    DEFAULT_MIN_OOS_TAKE,
    DEFAULT_SEED,
    LANE_MODES,
    LaneConfig,
    run_probability_lane,
)
from .run_registry import get_run, init_registry, register_run

DEFAULT_PREREG_DOC = "docs/stom_probability_lane_prereg_2026-06-11.md"
DEFAULT_INSTANCES = Path(".omx") / "artifacts" / "gap_up_full" / "instances.json"
DEFAULT_OUTPUT_DIR = Path("webui") / "rl_runs" / "probability_lane"
DEFAULT_REGISTRY = Path("webui") / "rl_runs" / "factory_registry.sqlite"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=LANE_MODES, default="edge_all")
    parser.add_argument("--prereg-doc", default=DEFAULT_PREREG_DOC)
    parser.add_argument("--instances", default=str(DEFAULT_INSTANCES))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--n-folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--min-oos-take", type=int, default=DEFAULT_MIN_OOS_TAKE)
    parser.add_argument("--expected-split-hash", default="")
    parser.add_argument("--parent-run", default="")
    parser.add_argument("--fill-mode", default="unknown")
    parser.add_argument("--stage", choices=("smoke", "walkforward"), default="walkforward")
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args(argv)


def _ensure_parent(registry: Path, args: argparse.Namespace) -> str:
    """Return the lineage parent run id, creating a smoke parent when absent."""

    if args.parent_run:
        if get_run(registry, args.parent_run) is None:
            raise SystemExit(f"parent run not found in registry: {args.parent_run}")
        return str(args.parent_run)
    smoke_parent = f"{args.run_id}_smoke_parent"
    if get_run(registry, smoke_parent) is None:
        register_run(
            registry,
            run_id=smoke_parent,
            split_hash="",
            cost_bps=23.0,
            seed=int(args.seed),
            stage="smoke",
            prereg_doc=args.prereg_doc,
        )
        mark_running(registry, smoke_parent)
        mark_done(registry, smoke_parent, verdict="SMOKE_PARENT")
    return smoke_parent


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    registry = Path(args.registry)
    init_registry(registry)
    parent_run = _ensure_parent(registry, args) if args.stage == "walkforward" else (args.parent_run or None)

    if get_run(registry, args.run_id) is None:
        enqueue_experiment(
            registry,
            run_id=args.run_id,
            split_hash=args.expected_split_hash,
            cost_bps=23.0,
            seed=int(args.seed),
            stage=args.stage,
            prereg_doc=args.prereg_doc,
            parent_run=parent_run,
            repo_root=args.repo_root,
        )
    mark_running(registry, args.run_id)

    config = LaneConfig(
        run_id=args.run_id,
        instances_path=Path(args.instances),
        output_dir=Path(args.output_dir),
        n_folds=int(args.n_folds),
        seed=int(args.seed),
        min_oos_take=int(args.min_oos_take),
        mode=args.mode,
        prereg_doc=args.prereg_doc,
        expected_split_hash=str(args.expected_split_hash),
        fill_mode=str(args.fill_mode),
        parent_run=parent_run,
    )
    try:
        payload = run_probability_lane(config)
    except Exception as exc:  # noqa: BLE001 - verdict must be recorded truthfully
        mark_failed(registry, args.run_id, verdict=f"FAILED:{exc}")
        raise
    mark_done(registry, args.run_id, verdict=str(payload["verdict"]))
    print(json.dumps({
        "run_id": args.run_id,
        "mode": args.mode,
        "fill_mode": args.fill_mode,
        "verdict": payload["verdict"],
        "blocking_reasons": payload["gates"]["blocking_reasons"],
        "oos_take_count": payload["aggregate"]["oos_take_count"],
        "oos_take_mean_net_pct": payload["aggregate"]["oos_take_mean_net_pct"],
        "oos_take_total_net_pct": payload["aggregate"]["oos_take_total_net_pct"],
        "take_all_mean_net_pct": payload["aggregate"]["take_all_mean_net_pct"],
        "ts_imb_mean_net_pct": payload["aggregate"]["ts_imb_mean_net_pct"],
        "ts_imb_count": payload["aggregate"]["ts_imb_count"],
        "skipped_count": payload["aggregate"]["skipped_count"],
        "skipped_mean_net_pct": payload["aggregate"]["skipped_mean_net_pct"],
        "brier": payload["aggregate"]["brier"],
        "brier_constant": payload["aggregate"]["brier_constant"],
        "split_hash": payload["split"]["split_hash"],
        "output_dir": payload["output_dir"],
        "guardrail": payload["guardrail"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
