"""Batch runner for research-only Daily OHLCV scenario/model experiments.

The dashboard API remains read-only. This module is the explicit CLI path for
running multiple pre-registered scenario configurations through the existing
D2 -> D3 -> D4 -> D5 pipeline and writing comparison artifacts under
``webui/rl_runs``.
"""

from __future__ import annotations

import argparse
import json
import hashlib
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .daily_ohlcv_db import REPO_ROOT
from .daily_scenario_runner import RESEARCH_GUARDRAIL, _validate_run_id, run_daily_model_scenario
from .daily_prediction import ROUND_TRIP_COST_BP
from .daily_rl_train import DEFAULT_PORTFOLIO_ROOT, SCORE_COLUMN, run_and_write_daily_rl
from .factory import run_registry

DEFAULT_SCENARIO_BATCH_ROOT = REPO_ROOT / "webui" / "rl_runs" / "daily_ohlcv_scenario_batches"
RUNNER_DEFAULTS: dict[str, Any] = {
    "max_symbols": None,
    "max_rows_per_symbol": None,
    "quality_table_limit": 0,
    "horizon_days": 1,
    "train_fraction": 0.6,
    "val_fraction": 0.2,
    "purge_days": 5,
    "embargo_days": 5,
    "candidate_limit": 20,
    "max_positions": 5,
    "episodes": 8,
    "rl_seed": 7,
    "n_folds": 5,
    "top_k": 20,
    "wf_seed": 17,
    "observation_mode": "v1",
    "action_prior_mode": "none",
    "action_prior_strength": 0.0,
    "action_filter_mode": "none",
}
SCENARIO_PARAM_KEYS = set(RUNNER_DEFAULTS)
MIN_REQUIRED_FOLDS = 5
MIN_REQUIRED_PURGE_DAYS = 5
MIN_REQUIRED_EMBARGO_DAYS = 5
D4_STABILITY_SEEDS = (7, 17, 29, 41, 53)
D4_STABILITY_EPISODES = (8, 32, 128)
D4_STABILITY_PREREG_DOC = REPO_ROOT / "docs" / "stom_daily_d4_stability_prereg_2026-07-12.md"
D4_STABILITY_SUMMARY_NAME = "stability_summary.json"
D4_STABILITY_PREREG_SHA256 = "fb53fe5b312996a58bc082ea8f864181a3d1fbc2ef07c54e61feeabd716a25ed"
D4_STABILITY_PREDICTION_MANIFEST_SHA256 = "b1d4b26d8561444dd826c66bb1fdc092200f52d0dd1d05a0ab6f24b4c0439936"
D4_STABILITY_FIXED_CONFIG: dict[str, Any] = {
    "score_column": SCORE_COLUMN,
    "candidate_limit": 20,
    "max_positions": 5,
    "observation_mode": "v1",
    "action_prior_mode": "none",
    "action_prior_strength": 0.0,
    "action_filter_mode": "none",
    "val_eval_every": 1,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _scenario_batch_dir(batch_id: str, *, root: Path | str | None = None, overwrite: bool = False) -> Path:
    base = Path(root or DEFAULT_SCENARIO_BATCH_ROOT).resolve()
    default_root = DEFAULT_SCENARIO_BATCH_ROOT.resolve()
    try:
        base.relative_to(default_root)
    except ValueError:
        if base != default_root:
            raise ValueError("Batch artifacts must stay under webui/rl_runs/daily_ohlcv_scenario_batches")
    bid = _validate_run_id(batch_id)
    out_dir = (base / bid).resolve()
    try:
        out_dir.relative_to(base)
    except ValueError as exc:
        raise ValueError("batch_id escapes daily scenario batch artifact root") from exc
    if out_dir.exists() and any(out_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"Scenario batch artifact batch_id already exists: {bid}")
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def load_batch_plan(path: Path | str) -> dict[str, Any]:
    plan_path = Path(path)
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Scenario batch plan must be a JSON object")
    return payload


def default_batch_plan(*, batch_id: str = "scenario_batch_smoke_001") -> dict[str, Any]:
    """Return a small valid plan users can save and edit before running."""

    return {
        "batch_id": batch_id,
        "description": "Research-only Daily OHLCV scenario smoke matrix; no live/broker/orders.",
        "defaults": {
            "max_symbols": 8,
            "max_rows_per_symbol": 120,
            "quality_table_limit": 0,
            "episodes": 3,
            "candidate_limit": 10,
            "max_positions": 3,
            "n_folds": 5,
            "top_k": 10,
            "purge_days": 5,
            "embargo_days": 5,
        },
        "scenarios": [
            {
                "scenario_id": "baseline_seed7_top10",
                "hypothesis": "Current-evidence baseline using top-k momentum controls.",
                "overrides": {"rl_seed": 7, "wf_seed": 17, "top_k": 10},
            },
            {
                "scenario_id": "seed11_top10",
                "hypothesis": "Seed robustness check without changing OOS gate rules.",
                "overrides": {"rl_seed": 11, "wf_seed": 31, "top_k": 10},
            },
            {
                "scenario_id": "top5_concentrated",
                "hypothesis": "Concentration stress test with fewer selected names.",
                "overrides": {"rl_seed": 7, "wf_seed": 17, "top_k": 5, "max_positions": 3},
            },
        ],
    }


def _merge_config(defaults: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    unknown_default_keys = set(defaults) - SCENARIO_PARAM_KEYS
    if unknown_default_keys:
        raise ValueError(f"Unknown scenario default keys: {sorted(unknown_default_keys)}")

    overrides = scenario.get("overrides", {})
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict):
        raise ValueError("scenario.overrides must be an object")

    inline_overrides = {key: value for key, value in scenario.items() if key in SCENARIO_PARAM_KEYS}
    unknown_override_keys = (set(overrides) | set(inline_overrides)) - SCENARIO_PARAM_KEYS
    if unknown_override_keys:
        raise ValueError(f"Unknown scenario override keys: {sorted(unknown_override_keys)}")

    config = dict(RUNNER_DEFAULTS)
    config.update(defaults)
    config.update(overrides)
    config.update(inline_overrides)
    _validate_research_gate_config(config)
    return config


def _validate_research_gate_config(config: dict[str, Any]) -> None:
    if int(config.get("n_folds") or 0) < MIN_REQUIRED_FOLDS:
        raise ValueError("n_folds must be >= 5 for scenario batch runs")
    if int(config.get("purge_days") or 0) < MIN_REQUIRED_PURGE_DAYS:
        raise ValueError("purge_days must be >= 5 for scenario batch runs")
    if int(config.get("embargo_days") or 0) < MIN_REQUIRED_EMBARGO_DAYS:
        raise ValueError("embargo_days must be >= 5 for scenario batch runs")


def _scenario_id(scenario: dict[str, Any], index: int) -> str:
    raw = scenario.get("scenario_id") or scenario.get("name") or f"scenario_{index:02d}"
    return _validate_run_id(str(raw))


def _comparison_row_from_manifest(*, scenario_id: str, run_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    gate = manifest.get("gate_verdict_summary") or {}
    return {
        "scenario_id": scenario_id,
        "run_id": run_id,
        "status": manifest.get("status", "NO-GO"),
        "readiness_status": manifest.get("readiness_status", "D5_NO_GO_RESEARCH_ONLY_GATE"),
        "selected_strategy": gate.get("selected_strategy"),
        "n_folds": gate.get("n_folds"),
        "purge_days": gate.get("purge_days"),
        "embargo_days": gate.get("embargo_days"),
        "cost_sensitivity_bp": gate.get("cost_sensitivity_bp"),
        "blocking_reasons": gate.get("reasons", []),
        "artifact_paths": manifest.get("artifact_paths", {}),
        "model_build_allowed": False,
        "go_summary_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
    }


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip().lower()
    if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("invalid_git_head_sha")
    return value


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _parse_int_grid(raw: str | list[int] | tuple[int, ...] | None, *, name: str, expected: tuple[int, ...]) -> tuple[int, ...]:
    if raw is None:
        values = expected
    elif isinstance(raw, str):
        values = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    else:
        values = tuple(int(value) for value in raw)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} contains duplicate values")
    if set(values) != set(expected):
        raise ValueError(f"{name} must exactly equal {expected}")
    return tuple(sorted(values))


def build_d4_stability_cells(
    *,
    seeds: str | list[int] | tuple[int, ...] | None = None,
    episodes: str | list[int] | tuple[int, ...] | None = None,
) -> list[dict[str, Any]]:
    resolved_seeds = _parse_int_grid(seeds, name="sweep_seeds", expected=D4_STABILITY_SEEDS)
    resolved_episodes = _parse_int_grid(episodes, name="sweep_episodes", expected=D4_STABILITY_EPISODES)
    return [
        {
            "seed": seed,
            "episodes": episode_count,
            "stage": "full" if episode_count == 128 else "smoke",
            "run_id": f"daily_d4_stability_2026_07_12_seed{seed}_ep{episode_count}",
            "config": {**D4_STABILITY_FIXED_CONFIG, "seed": seed, "episodes": episode_count},
        }
        for episode_count in resolved_episodes
        for seed in resolved_seeds
    ]


def _metric_by_split(result: dict[str, Any], split: str) -> dict[str, Any] | None:
    metrics = ((result.get("result") or {}).get("policy_metrics") or {}).get("metrics")
    if metrics is None:
        metrics = (result.get("policy_metrics") or {}).get("metrics")
    if not isinstance(metrics, list):
        return None
    for row in metrics:
        if isinstance(row, dict) and row.get("split") == split:
            return row
    return None


def _finite_float(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"missing_or_nonfinite_metric:{field}") from exc
    if not math.isfinite(number):
        raise ValueError(f"missing_or_nonfinite_metric:{field}")
    return number


def _split_metric_payload(metrics: dict[str, Any], *, split: str) -> dict[str, Any]:
    total_net_return = _finite_float(metrics.get("total_net_return"), field=f"{split}.total_net_return")
    max_drawdown = _finite_float(metrics.get("max_drawdown"), field=f"{split}.max_drawdown")
    if "trade_count" not in metrics:
        raise ValueError(f"missing_or_nonfinite_metric:{split}.trade_count")
    if "never_trade" not in metrics or not isinstance(metrics["never_trade"], bool):
        raise ValueError(f"missing_or_invalid_metric:{split}.never_trade")
    trade_count = int(_finite_float(metrics["trade_count"], field=f"{split}.trade_count"))
    never_trade = metrics["never_trade"]
    return {
        "total_net_return": total_net_return,
        "trade_count": trade_count,
        "never_trade": never_trade,
        "max_drawdown": max_drawdown,
    }


def _baseline_deltas(result_payload: dict[str, Any], *, val_test_return: float) -> dict[str, Any]:
    baseline = result_payload.get("baseline_comparison") or {}
    best = baseline.get("best_d3_total_net_return")
    equal_weight = baseline.get("equal_weight_topk_total_net_return")
    no_trade = baseline.get("no_trade_cash_total_net_return")
    return {
        "test_oos_primary": {
            "vs_no_trade_cash": None,
            "vs_equal_weight_topk_momentum": None,
            "vs_best_frozen_rule": None,
            "reason": "UNAVAILABLE_BASELINE_SCOPE_IS_VAL_TEST_SECONDARY_NOT_TEST_OOS",
        },
        "source_val_test_secondary_reference": {
            "vs_no_trade_cash": None if no_trade is None else val_test_return - _finite_float(no_trade, field="baseline.no_trade_cash_total_net_return"),
            "vs_equal_weight_topk_momentum": None if equal_weight is None else val_test_return - _finite_float(equal_weight, field="baseline.equal_weight_topk_total_net_return"),
            "vs_best_frozen_rule": None if best is None else val_test_return - _finite_float(best, field="baseline.best_d3_total_net_return"),
            "reason": "ARITHMETIC_REFERENCE_ONLY_BASELINES_SOURCED_FROM_VAL_TEST_COMPARISON",
        },
    }


def _artifact_hashes_from_written(written: dict[str, Any]) -> dict[str, str]:
    hashes = written.get("artifact_hashes")
    if isinstance(hashes, dict):
        return {str(key): str(value) for key, value in sorted(hashes.items())}
    return {}


def _artifact_total_bytes(run_dir: str | None) -> int:
    if not run_dir:
        return 0
    root = Path(run_dir)
    if not root.exists():
        return 0
    if root.is_file():
        return root.stat().st_size
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())




def _source_hashes_from_result(result_payload: dict[str, Any]) -> dict[str, str]:
    source_hashes = result_payload.get("source_hashes") or (result_payload.get("manifest") or {}).get("source_hashes") or {}
    if isinstance(source_hashes, dict):
        return {str(key): str(value) for key, value in sorted(source_hashes.items())}
    return {}


def _readiness_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    fields = ("checkpoint_readiness", "environment_readiness", "model_ready")
    if any(not isinstance(manifest.get(field), bool) for field in fields):
        raise ValueError("missing_or_invalid_readiness_contract")
    return {
        "checkpoint_readiness": manifest["checkpoint_readiness"],
        "environment_readiness": manifest["environment_readiness"],
        "model_ready": manifest["model_ready"],
        "readiness_status": manifest.get("readiness_status"),
    }


def _cell_success_payload(cell: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    result_payload = result.get("result") or result
    manifest = result_payload.get("manifest") or {}
    metrics_by_split: dict[str, Any] = {}
    for split in ("val", "test", "val+test"):
        row = _metric_by_split(result, split)
        if row is None:
            raise ValueError(f"missing_metric_split:{split}")
        metrics_by_split[split] = _split_metric_payload(row, split=split)
    artifact_hashes = _artifact_hashes_from_written(result.get("written") or {})
    return {
        "seed": cell["seed"],
        "episodes": cell["episodes"],
        "stage": cell["stage"],
        "run_id": cell["run_id"],
        "status": "done",
        "config": cell["config"],
        "config_hash": _sha256_text(_stable_json(cell["config"])),
        "metrics": metrics_by_split,
        "test_oos_primary": metrics_by_split["test"],
        "val_test_secondary": metrics_by_split["val+test"],
        "baseline_deltas_23bp": _baseline_deltas(result_payload, val_test_return=metrics_by_split["val+test"]["total_net_return"]),
        "source_hashes": _source_hashes_from_result(result_payload),
        "artifact_hashes": artifact_hashes,
        "readiness": _readiness_payload(manifest),
        "parent_training_run": manifest.get("parent_training_run"),
        "blockers": (result_payload.get("verdict") or {}).get("reasons", []),
        "run_dir": (result.get("written") or {}).get("artifact_dir") or manifest.get("artifact_dir"),
    }


def _cell_failure_payload(cell: dict[str, Any], exc: Exception) -> dict[str, Any]:
    return {
        "seed": cell["seed"],
        "episodes": cell["episodes"],
        "stage": cell["stage"],
        "run_id": cell["run_id"],
        "status": "failed",
        "config": cell["config"],
        "config_hash": _sha256_text(_stable_json(cell["config"])),
        "error": str(exc),
        "metrics": {},
        "test_oos_primary": None,
        "val_test_secondary": None,
        "baseline_deltas_23bp": {},
        "source_hashes": {},
        "artifact_hashes": {},
        "readiness": {
            "checkpoint_readiness": False,
            "environment_readiness": False,
            "model_ready": False,
            "readiness_status": "D4_STABILITY_CELL_FAILED",
        },
        "blockers": ["CELL_FAILED", str(exc)],
        "run_dir": None,
    }


def _stability_decision(cells: list[dict[str, Any]]) -> str:
    if len(cells) != len(D4_STABILITY_SEEDS) * len(D4_STABILITY_EPISODES):
        return "INCONCLUSIVE"
    if any(cell.get("status") != "done" for cell in cells):
        return "INCONCLUSIVE"
    try:
        for cell in cells:
            test = cell["metrics"]["test"]
            _finite_float(test["total_net_return"], field="test.total_net_return")
            _finite_float(test["max_drawdown"], field="test.max_drawdown")
            int(test["trade_count"])
    except Exception:
        return "INCONCLUSIVE"
    for episode_count in D4_STABILITY_EPISODES:
        cohort = [cell for cell in cells if cell["episodes"] == episode_count]
        signs = {0 if cell["metrics"]["test"]["total_net_return"] == 0 else (1 if cell["metrics"]["test"]["total_net_return"] > 0 else -1) for cell in cohort}
        never_trade = {bool(cell["metrics"]["test"]["never_trade"]) for cell in cohort}
        if len(signs) > 1 or len(never_trade) > 1:
            return "SEED_NOISE_NO_GO"
    return "STABLE_NO_GO"


def build_d4_stability_summary(
    *,
    summary_cells: list[dict[str, Any]],
    prereg_path: Path,
    prereg_hash: str,
    source_git_sha: str,
    prediction_dir: Path,
    prediction_manifest_hash: str,
    registry_events: list[dict[str, Any]],
    root: Path,
    dry_run: bool,
    generated_at: str | None = None,
) -> dict[str, Any]:
    decision = "INCONCLUSIVE" if dry_run else _stability_decision(summary_cells)
    deterministic_payload = {
        "schema_version": 1,
        "mode": "daily_d4_stability_sweep",
        "prereg_doc": str(prereg_path),
        "prereg_sha256": prereg_hash,
        "source_git_sha": source_git_sha,
        "prediction_run_dir": str(prediction_dir),
        "prediction_manifest_sha256": prediction_manifest_hash,
        "fixed_grid": {"seeds": list(D4_STABILITY_SEEDS), "episodes": list(D4_STABILITY_EPISODES)},
        "fixed_config": D4_STABILITY_FIXED_CONFIG,
        "cost_round_trip_bp": ROUND_TRIP_COST_BP,
        "cell_order": "(episodes, seed)",
        "dry_run": dry_run,
        "cell_count": len(summary_cells),
        "expected_cell_count": len(D4_STABILITY_SEEDS) * len(D4_STABILITY_EPISODES),
        "complete_grid": len(summary_cells) == len(D4_STABILITY_SEEDS) * len(D4_STABILITY_EPISODES),
        "decision": decision,
        "research_locks": {
            "model_build_allowed": False,
            "go_summary_allowed": False,
            "paper_forward_allowed": False,
            "live_broker_order_allowed": False,
            "test_oos_primary": True,
            "val_test_secondary_only": True,
            "aliases_excluded": True,
        },
        "blockers": sorted({reason for cell in summary_cells for reason in cell.get("blockers", [])}),
        "cells": summary_cells,
        "registry_events": registry_events,
    }
    return {
        **deterministic_payload,
        "generated_at": generated_at or _utc_now(),
        "deterministic_content_hash": _sha256_text(_stable_json(deterministic_payload)),
        "artifact_paths": {"stability_summary": str(root / D4_STABILITY_SUMMARY_NAME)},
    }


def run_d4_stability_sweep(
    *,
    sweep_seeds: str | list[int] | tuple[int, ...] | None = None,
    sweep_episodes: str | list[int] | tuple[int, ...] | None = None,
    prediction_run_dir: Path | str,
    stability_root: Path | str | None = None,
    registry_path: Path | str | None = None,
    prereg_doc: Path | str | None = None,
    source_git_sha: str | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
    stop_on_error: bool = False,
) -> dict[str, Any]:
    cells = build_d4_stability_cells(seeds=sweep_seeds, episodes=sweep_episodes)
    prediction_dir = Path(prediction_run_dir).resolve()
    prereg_path = Path(prereg_doc or D4_STABILITY_PREREG_DOC)
    if not prereg_path.is_file():
        raise FileNotFoundError(f"missing_prereg_doc:{prereg_path}")
    prereg_hash = _sha256_file(prereg_path)
    if prereg_hash != D4_STABILITY_PREREG_SHA256:
        raise ValueError(f"prereg_hash_mismatch:{prereg_hash}")
    prediction_manifest_path = prediction_dir / "prediction_manifest.json"
    if not prediction_manifest_path.is_file():
        raise FileNotFoundError(f"missing_prediction_manifest:{prediction_manifest_path}")
    prediction_manifest_hash = _sha256_file(prediction_manifest_path)
    if prediction_manifest_hash != D4_STABILITY_PREDICTION_MANIFEST_SHA256:
        raise ValueError(f"prediction_manifest_hash_mismatch:{prediction_manifest_hash}")
    actual_git_sha = _git_head_sha()
    declared_git_sha = str(source_git_sha or "").strip().lower()
    if not dry_run and not declared_git_sha:
        raise ValueError("source_git_sha is required for real D4 stability sweep runs")
    if declared_git_sha and declared_git_sha != actual_git_sha:
        raise ValueError(f"source_git_sha_mismatch:{declared_git_sha}!={actual_git_sha}")
    source_git_sha = actual_git_sha
    root = Path(
        stability_root
        or DEFAULT_PORTFOLIO_ROOT / "_scenario_runs" / "daily_d4_stability_2026_07_12"
    ).resolve()
    portfolio_root = DEFAULT_PORTFOLIO_ROOT.resolve()
    try:
        root.relative_to(portfolio_root)
    except ValueError as exc:
        raise ValueError("D4 stability artifacts must stay under daily_ohlcv_portfolio") from exc
    root.mkdir(parents=True, exist_ok=True)
    split_hash = prediction_manifest_hash
    summary_cells: list[dict[str, Any]] = []
    registry_events: list[dict[str, Any]] = []

    for cell in cells:
        run_dir = str((root / cell["run_id"]).resolve())
        if dry_run:
            summary_cells.append({**cell, "status": "dry_run", "run_dir": run_dir})
            continue
        registered = False
        try:
            if registry_path is not None:
                run_registry.register_run(
                    registry_path,
                    run_id=cell["run_id"],
                    split_hash=split_hash,
                    cost_bps=ROUND_TRIP_COST_BP,
                    seed=cell["seed"],
                    stage=cell["stage"],
                    prereg_doc=str(prereg_path),
                    parent_run=prediction_dir.name,
                    source_git_sha=source_git_sha,
                    run_dir=run_dir,
                    artifact_hashes=None,
                )
                registered = True
                registry_events.append({"run_id": cell["run_id"], "transition": "queued"})
                run_registry.set_status(registry_path, cell["run_id"], "running")
                registry_events.append({"run_id": cell["run_id"], "transition": "running"})
            result = run_and_write_daily_rl(
                run_id=cell["run_id"],
                artifact_root=root,
                overwrite=overwrite,
                enable_live_events=False,
                prediction_run_dir=prediction_dir,
                **cell["config"],
            )
            payload = _cell_success_payload(cell, result)
            if registry_path is not None and registered:
                run_registry.update_run_artifacts(
                    registry_path,
                    cell["run_id"],
                    run_dir=payload.get("run_dir") or run_dir,
                    artifact_hashes=payload["artifact_hashes"],
                    total_bytes=_artifact_total_bytes(payload.get("run_dir") or run_dir),
                )
                registry_events.append({"run_id": cell["run_id"], "transition": "artifacts_updated"})
            summary_cells.append(payload)
            if registry_path is not None and registered:
                run_registry.set_status(registry_path, cell["run_id"], "done", verdict="RESEARCH_ONLY")
                registry_events.append({"run_id": cell["run_id"], "transition": "done"})
        except Exception as exc:
            failure = _cell_failure_payload(cell, exc)
            summary_cells.append(failure)
            if registry_path is not None and registered:
                try:
                    run_registry.set_status(registry_path, cell["run_id"], "failed", verdict="INCONCLUSIVE")
                    registry_events.append({"run_id": cell["run_id"], "transition": "failed"})
                except Exception as registry_exc:
                    failure["registry_error"] = str(registry_exc)

    summary = build_d4_stability_summary(
        summary_cells=summary_cells,
        prereg_path=prereg_path,
        prereg_hash=prereg_hash,
        source_git_sha=source_git_sha,
        prediction_dir=prediction_dir,
        prediction_manifest_hash=prediction_manifest_hash,
        registry_events=registry_events,
        root=root,
        dry_run=dry_run,
    )
    _write_json(root / D4_STABILITY_SUMMARY_NAME, summary)
    return summary


def run_daily_scenario_batch(
    *,
    plan: dict[str, Any] | None = None,
    plan_path: Path | str | None = None,
    batch_id: str | None = None,
    overwrite: bool = False,
    stop_on_error: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run or preview a pre-registered batch of Daily OHLCV model scenarios."""

    if plan is None:
        if plan_path is None:
            plan = default_batch_plan(batch_id=batch_id or "scenario_batch_smoke_001")
        else:
            plan = load_batch_plan(plan_path)
    if not isinstance(plan, dict):
        raise ValueError("Scenario batch plan must be an object")

    resolved_batch_id = _validate_run_id(str(batch_id or plan.get("batch_id") or "").strip())
    scenarios = plan.get("scenarios") or []
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Scenario batch plan requires a non-empty scenarios list")
    defaults = plan.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise ValueError("Scenario batch defaults must be an object")

    out_dir = _scenario_batch_dir(resolved_batch_id, overwrite=overwrite)
    _write_json(out_dir / "scenario_batch_plan.json", plan)

    comparison_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    started_at = _utc_now()

    for index, raw_scenario in enumerate(scenarios, start=1):
        if not isinstance(raw_scenario, dict):
            raise ValueError("Each scenario entry must be an object")
        scenario_id = _scenario_id(raw_scenario, index)
        run_id = _validate_run_id(f"{resolved_batch_id}__{scenario_id}")
        config = _merge_config(defaults, raw_scenario)
        row_base = {
            "scenario_id": scenario_id,
            "run_id": run_id,
            "hypothesis": raw_scenario.get("hypothesis"),
            "assumption_tags": raw_scenario.get("assumption_tags", []),
            "config": config,
        }
        if dry_run:
            comparison_rows.append(
                {
                    **row_base,
                    "status": "DRY_RUN_NOT_EXECUTED",
                    "readiness_status": "SCENARIO_BATCH_DRY_RUN_ONLY",
                    "cost_sensitivity_bp": [0, 23, 46],
                    "blocking_reasons": ["DRY_RUN_NOT_EXECUTED"],
                    "model_build_allowed": False,
                    "go_summary_allowed": False,
                    "paper_forward_allowed": False,
                    "live_broker_order_allowed": False,
                }
            )
            continue
        try:
            child_manifest = run_daily_model_scenario(run_id=run_id, overwrite=overwrite, **config)
            comparison_rows.append(
                {
                    **row_base,
                    **_comparison_row_from_manifest(
                        scenario_id=scenario_id,
                        run_id=run_id,
                        manifest=child_manifest,
                    ),
                }
            )
        except Exception as exc:
            error_row = {
                **row_base,
                "status": "ERROR",
                "readiness_status": "SCENARIO_RUN_FAILED_RESEARCH_ONLY",
                "error": str(exc),
                "cost_sensitivity_bp": [0, 23, 46],
                "blocking_reasons": ["SCENARIO_RUN_FAILED", str(exc)],
                "model_build_allowed": False,
                "go_summary_allowed": False,
                "paper_forward_allowed": False,
                "live_broker_order_allowed": False,
            }
            errors.append(error_row)
            comparison_rows.append(error_row)
            if stop_on_error:
                break

    failed_count = sum(1 for row in comparison_rows if row.get("status") == "ERROR")
    manifest = {
        "schema_version": 1,
        "batch_id": resolved_batch_id,
        "generated_at": _utc_now(),
        "started_at": started_at,
        "mode": "daily_ohlcv_model_scenario_batch",
        "platform_stage": "SCENARIO_BATCH_RUNNER_MVP",
        "status": "DRY_RUN" if dry_run else ("PARTIAL_ERROR_RESEARCH_ONLY" if failed_count else "COMPLETED_RESEARCH_ONLY"),
        "read_only_artifact": True,
        "dry_run": dry_run,
        "guardrail": RESEARCH_GUARDRAIL,
        "model_build_allowed": False,
        "go_summary_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
        "no_live_broker_order_readiness": True,
        "scenario_count": len(scenarios),
        "completed_count": len(comparison_rows) - failed_count,
        "failed_count": failed_count,
        "gate_status_counts": _status_counts(comparison_rows),
        "plan": plan,
        "comparison_rows": comparison_rows,
        "errors": errors,
        "artifact_paths": {
            "scenario_batch_manifest": str(out_dir / "scenario_batch_manifest.json"),
            "scenario_batch_plan": str(out_dir / "scenario_batch_plan.json"),
        },
    }
    _write_json(out_dir / "scenario_batch_manifest.json", manifest)
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a research-only Daily OHLCV scenario batch from a JSON plan.")
    parser.add_argument("--plan", type=Path, help="JSON plan containing batch_id, defaults, and scenarios")
    parser.add_argument("--batch-id", help="Override or provide the batch id")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--emit-template", action="store_true", help="Print a small JSON batch plan template and exit")
    parser.add_argument("--sweep-seeds", help="Comma-separated D4 stability seeds; must exactly be 7,17,29,41,53")
    parser.add_argument("--sweep-episodes", help="Comma-separated D4 stability episodes; must exactly be 8,32,128")
    parser.add_argument("--prediction-run-dir", type=Path, help="Explicit frozen prediction run directory for D4 stability sweep")
    parser.add_argument("--stability-root", type=Path, help="Artifact root for D4 stability sweep outputs")
    parser.add_argument("--registry-path", type=Path, help="Optional factory run registry SQLite path")
    parser.add_argument("--prereg-doc", type=Path, help="D4 stability preregistration document path")
    parser.add_argument("--source-git-sha", help="Source Git SHA recorded in optional registry metadata")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.emit_template:
        print(json.dumps(default_batch_plan(batch_id=args.batch_id or "scenario_batch_smoke_001"), ensure_ascii=False, indent=2))
        return 0
    if args.sweep_seeds is not None or args.sweep_episodes is not None or args.prediction_run_dir is not None or args.stability_root is not None:
        if args.prediction_run_dir is None:
            raise ValueError("--prediction-run-dir is required for --sweep-* D4 stability runs")
        payload = run_d4_stability_sweep(
            sweep_seeds=args.sweep_seeds,
            sweep_episodes=args.sweep_episodes,
            prediction_run_dir=args.prediction_run_dir,
            stability_root=args.stability_root,
            registry_path=args.registry_path,
            prereg_doc=args.prereg_doc,
            source_git_sha=args.source_git_sha,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            stop_on_error=args.stop_on_error,
        )
    else:
        payload = run_daily_scenario_batch(
            plan_path=args.plan,
            batch_id=args.batch_id,
            overwrite=args.overwrite,
            stop_on_error=args.stop_on_error,
            dry_run=args.dry_run,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_SCENARIO_BATCH_ROOT",
    "RUNNER_DEFAULTS",
    "D4_STABILITY_EPISODES",
    "D4_STABILITY_FIXED_CONFIG",
    "D4_STABILITY_SEEDS",
    "build_arg_parser",
    "default_batch_plan",
    "build_d4_stability_cells",
    "load_batch_plan",
    "main",
    "run_daily_scenario_batch",
    "run_d4_stability_sweep",
]
