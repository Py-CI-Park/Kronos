"""Fail-closed R7 rliable report from G019 D4 stability summaries.

RESEARCH_ONLY. Consumes one authoritative identical-config seed cohort from
``stability_summary.json`` and emits deterministic IQM, stratified bootstrap CI,
performance-profile data, hashes, split/cost/seed metadata, and no profitability
or readiness claim.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_ONLY_NOTE = (
    "RESEARCH_ONLY: reliability statistics over G019 test-OOS seed cohorts. "
    "No live, paper, model-readiness, or profitability claim."
)
DEFAULT_COST_BP = 23.0
DEFAULT_MIN_SEEDS = 3
DEFAULT_REPS = 10_000
DEFAULT_THRESHOLDS = (-0.10, -0.05, 0.0, 0.05, 0.10)


class RliableReportError(ValueError):
    """Raised when the stability summary is not an acceptable G019 cohort."""



def _stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite_float(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RliableReportError(f"missing_or_nonfinite:{field}") from exc
    if not math.isfinite(number):
        raise RliableReportError(f"missing_or_nonfinite:{field}")
    return number

def _required_hash_map(value: Any, *, field: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise RliableReportError(f"missing_or_invalid:{field}")
    result: dict[str, str] = {}
    for key, raw_hash in sorted(value.items(), key=lambda item: str(item[0])):
        clean_key = str(key).strip()
        clean_hash = str(raw_hash).strip().lower()
        if not clean_key or len(clean_hash) != 64 or any(char not in "0123456789abcdef" for char in clean_hash):
            raise RliableReportError(f"missing_or_invalid:{field}.{clean_key or 'key'}")
        result[clean_key] = clean_hash
    return result



def _scrub_seed_from_config(config: Mapping[str, Any]) -> dict[str, Any]:
    scrubbed = dict(config)
    for key in ("seed", "rl_seed", "wf_seed", "run_id"):
        scrubbed.pop(key, None)
    return scrubbed


def _rliable_statistics(
    values: Sequence[float],
    *,
    thresholds: Sequence[float],
    reps: int,
    seed: int,
) -> dict[str, Any]:
    if reps <= 0:
        raise RliableReportError("bootstrap_reps_must_be_positive")
    try:
        import numpy as np
        from rliable import library as rly
        from rliable import metrics
    except ImportError as exc:
        raise RliableReportError("rliable_dependency_unavailable") from exc

    score_dict = {"D4": np.asarray([float(value) for value in values], dtype=float)[:, None]}
    random_state = np.random.get_state()
    try:
        np.random.seed(int(seed))
        aggregate_scores, aggregate_cis = rly.get_interval_estimates(
            score_dict,
            lambda scores: np.asarray([metrics.aggregate_iqm(scores)], dtype=float),
            reps=int(reps),
            random_state=np.random.RandomState(int(seed)),
        )
        np.random.seed(int(seed))
        profile_scores, profile_cis = rly.create_performance_profile(
            score_dict,
            np.asarray([float(value) for value in thresholds], dtype=float),
            reps=int(reps),
        )
    finally:
        np.random.set_state(random_state)

    profile = [
        {
            "threshold_total_net_return": float(threshold),
            "fraction_above_threshold": float(profile_scores["D4"][index]),
            "ci_lower": float(profile_cis["D4"][0, index]),
            "ci_upper": float(profile_cis["D4"][1, index]),
        }
        for index, threshold in enumerate(thresholds)
    ]
    return {
        "backend": {
            "library": "rliable",
            "version": importlib.metadata.version("rliable"),
            "aggregate_api": "library.get_interval_estimates(metrics.aggregate_iqm)",
            "profile_api": "library.create_performance_profile",
        },
        "iqm": {
            "point": float(aggregate_scores["D4"][0]),
            "ci_lower": float(aggregate_cis["D4"][0, 0]),
            "ci_upper": float(aggregate_cis["D4"][1, 0]),
        },
        "performance_profile": profile,
    }


def _mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values))


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[midpoint])
    return float((ordered[midpoint - 1] + ordered[midpoint]) / 2.0)




def _cohort_cells(summary: Mapping[str, Any], *, episodes: int | None) -> list[dict[str, Any]]:
    cells = summary.get("cells")
    if not isinstance(cells, list):
        raise RliableReportError("missing_cells")
    done = [cell for cell in cells if isinstance(cell, dict) and cell.get("status") == "done"]
    if episodes is not None:
        done = [cell for cell in done if int(cell.get("episodes")) == int(episodes)]
    if not done:
        raise RliableReportError("no_done_cells_for_requested_cohort")
    episode_values = {int(cell.get("episodes")) for cell in done}
    if len(episode_values) != 1:
        raise RliableReportError("mixed_episode_cohorts_require_explicit_episodes")
    return sorted(done, key=lambda cell: (int(cell["seed"]), str(cell["run_id"])))


def _validate_cost(summary: Mapping[str, Any], *, expected_cost_bp: float) -> float:
    cost = _finite_float(summary.get("cost_round_trip_bp"), field="cost_round_trip_bp")
    if cost != float(expected_cost_bp):
        raise RliableReportError(f"unexpected_cost_bp:{cost:g}")
    return cost


def validate_stability_cohort(
    summary: Mapping[str, Any],
    *,
    episodes: int | None = None,
    expected_cost_bp: float = DEFAULT_COST_BP,
    min_seeds: int = DEFAULT_MIN_SEEDS,
) -> dict[str, Any]:
    """Return a validated one-episode G019 cohort or raise fail-closed errors."""

    cost_bp = _validate_cost(summary, expected_cost_bp=expected_cost_bp)
    cells = _cohort_cells(summary, episodes=episodes)
    seen_seeds: set[int] = set()
    seen_run_ids: set[str] = set()
    config_hashes: set[str] = set()
    runs: list[dict[str, Any]] = []
    source_hashes: dict[str, Any] = {}
    artifact_hashes: dict[str, Any] = {}

    for cell in cells:
        if cell.get("alias_of") or cell.get("ALIAS_OF") or cell.get("is_alias"):
            raise RliableReportError("aliases_are_not_seed_runs")
        seed_raw = cell.get("seed")
        if isinstance(seed_raw, bool) or seed_raw is None:
            raise RliableReportError("missing_explicit_seed")
        try:
            seed = int(seed_raw)
        except (TypeError, ValueError) as exc:
            raise RliableReportError("missing_explicit_seed") from exc
        if seed in seen_seeds:
            raise RliableReportError(f"duplicate_seed:{seed}")
        seen_seeds.add(seed)

        run_id = str(cell.get("run_id") or "")
        if not run_id:
            raise RliableReportError("missing_run_id")
        if run_id in seen_run_ids:
            raise RliableReportError(f"duplicate_run_id:{run_id}")
        seen_run_ids.add(run_id)

        config = cell.get("config")
        if not isinstance(config, dict):
            raise RliableReportError("missing_config")
        cohort_config = _scrub_seed_from_config(config)
        config_hashes.add(_sha256_text(_stable_json(cohort_config)))
        declared_config_hash = str(cell.get("config_hash") or "").strip().lower()
        actual_config_hash = _sha256_text(_stable_json(config))
        if declared_config_hash != actual_config_hash:
            raise RliableReportError(f"config_hash_mismatch:{run_id}")
        cell_cost_values = [
            config[key]
            for key in ("round_trip_cost_bp", "cost_round_trip_bp", "cost_bps")
            if key in config
        ]
        if cell_cost_values:
            if any(
                _finite_float(value, field=f"config.cost:{run_id}") != cost_bp
                for value in cell_cost_values
            ):
                raise RliableReportError(f"cell_cost_mismatch:{run_id}")
        elif not isinstance(cell.get("baseline_deltas_23bp"), dict):
            raise RliableReportError(f"missing_per_run_cost_evidence:{run_id}")

        metrics = cell.get("metrics")
        if not isinstance(metrics, dict) or "test" not in metrics:
            raise RliableReportError("missing_explicit_test_oos_metrics")
        test_metrics = metrics.get("test")
        if not isinstance(test_metrics, dict):
            raise RliableReportError("missing_explicit_test_oos_metrics")
        if cell.get("test_oos_primary") != test_metrics:
            raise RliableReportError("test_oos_primary_must_match_metrics_test")
        score = _finite_float(test_metrics.get("total_net_return"), field="metrics.test.total_net_return")
        max_drawdown = _finite_float(test_metrics.get("max_drawdown"), field="metrics.test.max_drawdown")
        trade_count = int(_finite_float(test_metrics.get("trade_count"), field="metrics.test.trade_count"))
        if "never_trade" not in test_metrics or not isinstance(test_metrics["never_trade"], bool):
            raise RliableReportError("missing_or_invalid:metrics.test.never_trade")

        source_hashes[run_id] = _required_hash_map(
            cell.get("source_hashes"),
            field=f"source_hashes:{run_id}",
        )
        artifact_hashes[run_id] = _required_hash_map(
            cell.get("artifact_hashes"),
            field=f"artifact_hashes:{run_id}",
        )

        runs.append(
            {
                "seed": seed,
                "run_id": run_id,
                "score_total_net_return": score,
                "max_drawdown": max_drawdown,
                "trade_count": trade_count,
                "never_trade": bool(test_metrics["never_trade"]),
                "config_hash": actual_config_hash,
            }
        )

    if len(seen_seeds) < int(min_seeds):
        raise RliableReportError(f"insufficient_unique_seeds:{len(seen_seeds)}")
    if len(config_hashes) != 1:
        raise RliableReportError("mixed_configs")

    return {
        "episodes": int(cells[0]["episodes"]),
        "cost_round_trip_bp": cost_bp,
        "split": "test",
        "seed_set": sorted(seen_seeds),
        "run_ids": [run["run_id"] for run in runs],
        "cohort_config": _scrub_seed_from_config(cells[0]["config"]),
        "cohort_config_hash": next(iter(config_hashes)),
        "runs": sorted(runs, key=lambda row: row["seed"]),
        "source_hashes_by_run_id": source_hashes,
        "artifact_hashes_by_run_id": artifact_hashes,
    }


def build_report(
    summary: Mapping[str, Any],
    *,
    input_path: Path | None = None,
    episodes: int | None = None,
    expected_cost_bp: float = DEFAULT_COST_BP,
    min_seeds: int = DEFAULT_MIN_SEEDS,
    reps: int = DEFAULT_REPS,
    seed: int = 0,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
    generated_at: str | None = None,
) -> dict[str, Any]:
    cohort = validate_stability_cohort(
        summary,
        episodes=episodes,
        expected_cost_bp=expected_cost_bp,
        min_seeds=min_seeds,
    )
    scores = [run["score_total_net_return"] for run in cohort["runs"]]
    rliable_stats = _rliable_statistics(
        scores,
        thresholds=thresholds,
        reps=int(reps),
        seed=int(seed),
    )
    resolved_generated_at = str(
        generated_at if generated_at is not None else summary.get("generated_at") or "NOT_RECORDED"
    )
    generation_time_basis = (
        "caller_override" if generated_at is not None else "source_summary_generated_at"
    )
    deterministic_payload = {
        "schema": "kronos_rl_r7_rliable_report.v1",
        "research_only": True,
        "note": RESEARCH_ONLY_NOTE,
        "input_path": None if input_path is None else str(input_path),
        "input_sha256": None if input_path is None else _sha256_file(input_path),
        "source_summary_hash": summary.get("deterministic_content_hash"),
        "split": cohort["split"],
        "score_definition": "test-OOS metrics.test.total_net_return at 23bp round-trip cost",
        "cost_round_trip_bp": cohort["cost_round_trip_bp"],
        "episodes": cohort["episodes"],
        "min_seeds": int(min_seeds),
        "seed_set": cohort["seed_set"],
        "run_ids": cohort["run_ids"],
        "cohort_config_hash": cohort["cohort_config_hash"],
        "cohort_config": cohort["cohort_config"],
        "bootstrap": {
            "method": "rliable_stratified_seed_resample",
            "reps": int(reps),
            "seed": int(seed),
            "confidence": 0.95,
        },
        "rliable_backend": rliable_stats["backend"],
        "metrics": {
            "iqm": rliable_stats["iqm"],
            "mean": {"point": _mean(scores)},
            "median": {"point": _median(scores)},
        },
        "performance_profile": rliable_stats["performance_profile"],
        "runs": cohort["runs"],
        "source_hashes_by_run_id": cohort["source_hashes_by_run_id"],
        "artifact_hashes_by_run_id": cohort["artifact_hashes_by_run_id"],
        "generation_time_basis": generation_time_basis,
    }
    return {
        **deterministic_payload,
        "generated_at": resolved_generated_at,
        "deterministic_report_hash": _sha256_text(_stable_json(deterministic_payload)),
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RliableReportError("input_must_be_json_object")
    return payload


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a fail-closed R7 reliability report from G019 stability_summary.json.")
    parser.add_argument("--sweep", required=True, help="Path to G019 stability_summary.json")
    parser.add_argument("--episodes", type=int, required=False, help="Episode/config cohort to report; required when the summary has multiple cohorts.")
    parser.add_argument("--out", required=False, help="Output JSON path. Defaults to stdout only.")
    parser.add_argument("--min-seeds", type=int, default=DEFAULT_MIN_SEEDS)
    parser.add_argument("--cost-bp", type=float, default=DEFAULT_COST_BP)
    parser.add_argument("--reps", type=int, default=DEFAULT_REPS)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--generated-at",
        help="Deterministic report timestamp override; defaults to source summary generated_at.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_argparser()
    args = parser.parse_args(argv)
    try:
        sweep_path = Path(args.sweep)
        summary = _load_json(sweep_path)
        report = build_report(
            summary,
            input_path=sweep_path,
            episodes=args.episodes,
            expected_cost_bp=args.cost_bp,
            min_seeds=args.min_seeds,
            reps=args.reps,
            seed=args.seed,
            generated_at=args.generated_at,
        )
    except Exception as exc:
        print(f"[rl_report_rliable] rejected input: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"[rl_report_rliable] wrote {out_path}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
