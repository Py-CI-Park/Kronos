"""Standalone CLI: rigorous RL evaluation statistics via ``rliable``.

RESEARCH_ONLY. This tool computes reliability-focused aggregate statistics
(IQM, mean, median, optimality gap) with stratified-bootstrap confidence
intervals over recorded RL runs. It makes NO profitability claim and emits NO
GO/NO-GO verdict — it only quantifies dispersion across runs for research.

Score source
------------
Runs are read from ``webui/rl_runs/*/rl_live_events.jsonl`` (the JSONL live-event
stream defined by ``stom_rl/rl_events.py``). For each distinct run and each
algorithm that carries equity in that run, the per-run score is the normalized
terminal-equity multiplier ``final_equity / first_equity`` (a dimensionless
growth factor, comparable across runs that use different equity scales). Scores
are grouped by algorithm; each distinct run acts as one "seed" row of the
rliable score matrix (shape ``(num_runs, 1)``).

If fewer than ``--min-seeds`` runs are available for every algorithm, the tool
prints a clear "insufficient runs for reliable stats" message and exits 0
(never crashes). Optional run metadata (``cost_bps``) is looked up from the
factory run registry when a run id matches.

Self-host / no-egress: reads only local files; performs no network calls.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Make ``stom_rl`` importable when invoked as a script from any cwd.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

RESEARCH_ONLY_NOTE = (
    "RESEARCH_ONLY: reliability statistics over recorded runs. Not a "
    "profitability estimate and not a GO/NO-GO verdict. Scores are normalized "
    "terminal-equity multipliers (final/first equity), grouped by algorithm."
)

DEFAULT_EVENTS_GLOB = "webui/rl_runs/*/rl_live_events.jsonl"
DEFAULT_REGISTRY = "webui/rl_runs/factory_registry.sqlite"
DEFAULT_OUT_DIR = "artifacts"
DEFAULT_NAME = "rl_runs"
DEFAULT_MIN_SEEDS = 2
DEFAULT_REPS = 10_000


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _read_events(path: Path) -> List[Dict[str, Any]]:
    """Read all JSONL events from a live-event file, tolerating malformed lines.

    Prefers ``stom_rl.rl_events.read_live_events`` (bounded, malformed-tolerant);
    falls back to a local line-by-line parser if that import is unavailable.
    """

    try:
        from stom_rl.rl_events import MAX_EVENT_LIMIT, read_live_events

        rows, _truncated = read_live_events(path, limit=MAX_EVENT_LIMIT, tail=False)
        return rows
    except Exception:
        rows2: List[Dict[str, Any]] = []
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return rows2
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows2.append(payload)
        return rows2


def _finite_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _run_scores_from_events(
    events: List[Dict[str, Any]],
) -> List[Tuple[str, str, float]]:
    """Extract ``(algorithm, run_id, score)`` triples from one run's events.

    Score = final_equity / first_equity per (algorithm, run_id) group, using the
    lowest/highest ``global_step`` equity-bearing events. Groups without usable
    equity are skipped.
    """

    # (algorithm, run_id) -> list of (global_step, equity)
    buckets: Dict[Tuple[str, str], List[Tuple[float, float]]] = defaultdict(list)
    for row in events:
        equity = _finite_float(row.get("equity"))
        if equity is None:
            continue
        algorithm = str(row.get("algorithm") or "unknown")
        run_id = str(row.get("run_id") or "unknown")
        step = _finite_float(row.get("global_step"))
        if step is None:
            step = float(len(buckets[(algorithm, run_id)]))
        buckets[(algorithm, run_id)].append((step, equity))

    triples: List[Tuple[str, str, float]] = []
    for (algorithm, run_id), points in buckets.items():
        if len(points) < 1:
            continue
        points.sort(key=lambda item: item[0])
        first_equity = points[0][1]
        final_equity = points[-1][1]
        if first_equity is None or first_equity == 0:
            continue
        score = final_equity / first_equity
        if not math.isfinite(score):
            continue
        triples.append((algorithm, run_id, score))
    return triples


def _load_registry_cost_bps(registry_path: Path) -> Dict[str, float]:
    """Return ``{run_id: cost_bps}`` from the factory registry, if readable."""

    mapping: Dict[str, float] = {}
    if not registry_path.is_file():
        return mapping
    try:
        import sqlite3

        conn = sqlite3.connect(str(registry_path))
        try:
            cursor = conn.execute("SELECT run_id, cost_bps FROM runs")
            for run_id, cost_bps in cursor.fetchall():
                value = _finite_float(cost_bps)
                if value is not None:
                    mapping[str(run_id)] = value
        finally:
            conn.close()
    except Exception:
        return mapping
    return mapping


def collect_scores(
    events_glob: str,
    *,
    repo_root: Path,
) -> Tuple[Dict[str, List[Tuple[str, float]]], List[str]]:
    """Scan the events glob and group per-run scores by algorithm.

    Returns ``(scores_by_algo, scanned_files)`` where ``scores_by_algo`` maps an
    algorithm to a list of ``(run_id, score)`` deduped by run_id (first wins).
    """

    pattern = events_glob
    if not os.path.isabs(pattern):
        pattern = str(repo_root / events_glob)

    scanned: List[str] = []
    # algorithm -> {run_id: score}  (dedupe by run_id across duplicate dirs)
    grouped: Dict[str, Dict[str, float]] = defaultdict(dict)
    for file_path in sorted(glob.glob(pattern)):
        path = Path(file_path)
        scanned.append(str(path))
        events = _read_events(path)
        if not events:
            continue
        for algorithm, run_id, score in _run_scores_from_events(events):
            grouped[algorithm].setdefault(run_id, score)

    scores_by_algo: Dict[str, List[Tuple[str, float]]] = {
        algorithm: sorted(run_scores.items())
        for algorithm, run_scores in grouped.items()
    }
    return scores_by_algo, scanned


def _compute_rliable(
    score_dict: Dict[str, Any],
    *,
    reps: int,
) -> Optional[Dict[str, Dict[str, Any]]]:
    """Run rliable interval estimates; return per-algorithm aggregates or None.

    Defensive: any failure inside rliable returns None so callers degrade
    gracefully instead of crashing.
    """

    try:
        import numpy as np
        from rliable import library, metrics
    except Exception:
        return None

    metric_names = ["median", "iqm", "mean", "optimality_gap"]

    def _aggregate(scores: "np.ndarray") -> "np.ndarray":
        return np.array(
            [
                metrics.aggregate_median(scores),
                metrics.aggregate_iqm(scores),
                metrics.aggregate_mean(scores),
                metrics.aggregate_optimality_gap(scores),
            ]
        )

    try:
        point, cis = library.get_interval_estimates(
            score_dict, _aggregate, reps=int(reps)
        )
    except Exception:
        return None

    results: Dict[str, Dict[str, Any]] = {}
    try:
        for algorithm in score_dict:
            point_vals = point[algorithm]
            ci_vals = cis[algorithm]  # shape (2, num_metrics): [lower, upper]
            per_metric: Dict[str, Any] = {}
            for idx, name in enumerate(metric_names):
                per_metric[name] = {
                    "point": float(point_vals[idx]),
                    "ci_lower": float(ci_vals[0][idx]),
                    "ci_upper": float(ci_vals[1][idx]),
                }
            results[algorithm] = per_metric
    except Exception:
        return None
    return results


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gen_rliable_stats.py",
        description="Compute research-only rliable statistics over recorded RL runs.",
    )
    parser.add_argument(
        "--events-glob",
        default=DEFAULT_EVENTS_GLOB,
        help=f"Glob for RL live-event JSONL files (default: {DEFAULT_EVENTS_GLOB}).",
    )
    parser.add_argument(
        "--registry",
        default=DEFAULT_REGISTRY,
        help=f"Factory run registry sqlite for cost_bps metadata (default: {DEFAULT_REGISTRY}).",
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Directory for the output JSON (default: {DEFAULT_OUT_DIR}).",
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_NAME,
        help=f"Output basename; writes <out-dir>/<name>_rliable.json (default: {DEFAULT_NAME}).",
    )
    parser.add_argument(
        "--min-seeds",
        type=int,
        default=DEFAULT_MIN_SEEDS,
        help=f"Minimum runs (seeds) per algorithm required (default: {DEFAULT_MIN_SEEDS}).",
    )
    parser.add_argument(
        "--reps",
        type=int,
        default=DEFAULT_REPS,
        help=f"Stratified bootstrap resamples (default: {DEFAULT_REPS}).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Always returns 0 on the no/insufficient-data path."""

    parser = _build_argparser()
    args = parser.parse_args(argv)

    repo_root = _REPO_ROOT
    scores_by_algo, scanned = collect_scores(args.events_glob, repo_root=repo_root)

    total_runs = sum(len(rows) for rows in scores_by_algo.values())
    print(
        f"[gen_rliable_stats] scanned {len(scanned)} event file(s); "
        f"found {len(scores_by_algo)} algorithm group(s), {total_runs} run-score(s)."
    )

    eligible = {
        algorithm: rows
        for algorithm, rows in scores_by_algo.items()
        if len(rows) >= int(args.min_seeds)
    }

    if not eligible:
        best = max((len(r) for r in scores_by_algo.values()), default=0)
        print(
            f"[gen_rliable_stats] insufficient runs for reliable stats "
            f"(need >={args.min_seeds} seeds per algorithm; best group has {best}). "
            "No output written."
        )
        print(RESEARCH_ONLY_NOTE)
        return 0

    # Registry cost_bps metadata (best-effort; most live-event run ids will not match).
    registry_path = Path(args.registry)
    if not registry_path.is_absolute():
        registry_path = repo_root / args.registry
    cost_bps_by_run = _load_registry_cost_bps(registry_path)

    # Build the rliable score dict: {algorithm: ndarray shape (num_runs, 1)}.
    try:
        import numpy as np
    except Exception:
        print("[gen_rliable_stats] numpy unavailable; cannot compute stats. Exiting 0.")
        print(RESEARCH_ONLY_NOTE)
        return 0

    score_dict: Dict[str, Any] = {}
    algo_metadata: Dict[str, Any] = {}
    for algorithm, rows in sorted(eligible.items()):
        run_ids = [run_id for run_id, _score in rows]
        scores = [float(score) for _run_id, score in rows]
        score_dict[algorithm] = np.array(scores, dtype=float).reshape(len(scores), 1)
        cost_values = sorted(
            {cost_bps_by_run[r] for r in run_ids if r in cost_bps_by_run}
        )
        algo_metadata[algorithm] = {
            "run_ids": run_ids,
            "seed_count": len(run_ids),
            "cost_bps": cost_values or None,
            "run_scores": {run_id: float(score) for run_id, score in rows},
        }

    aggregates = _compute_rliable(score_dict, reps=args.reps)

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = repo_root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.name}_rliable.json"

    if aggregates is None:
        print(
            "[gen_rliable_stats] rliable computation unavailable/failed; "
            "writing metadata-only summary."
        )

    payload = {
        "schema": "kronos_rliable_stats.v1",
        "generated_utc": _utc_now_iso(),
        "research_only": True,
        "note": RESEARCH_ONLY_NOTE,
        "score_definition": "normalized terminal-equity multiplier (final_equity / first_equity)",
        "metric_names": ["median", "iqm", "mean", "optimality_gap"],
        "confidence_interval": 0.95,
        "bootstrap_reps": int(args.reps),
        "min_seeds": int(args.min_seeds),
        "events_glob": args.events_glob,
        "scanned_file_count": len(scanned),
        "algorithms": sorted(eligible.keys()),
        "aggregates": aggregates if aggregates is not None else {},
        "metadata": algo_metadata,
    }

    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"[gen_rliable_stats] wrote {out_path} "
        f"({len(eligible)} algorithm group(s) with >={args.min_seeds} seeds)."
    )
    if aggregates is not None:
        for algorithm in sorted(aggregates.keys()):
            iqm = aggregates[algorithm]["iqm"]
            print(
                f"  {algorithm}: IQM={iqm['point']:.4f} "
                f"[{iqm['ci_lower']:.4f}, {iqm['ci_upper']:.4f}] "
                f"(n={algo_metadata[algorithm]['seed_count']})"
            )
    print(RESEARCH_ONLY_NOTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
