from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from stom_rl.experiment_tracking_aim import aim_enabled, maybe_create_tracker, sha256_payload


_REPORT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "rl_report_rliable.py"
_SPEC = importlib.util.spec_from_file_location("rl_report_rliable", _REPORT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
rl_report_rliable = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rl_report_rliable)


def _cell(seed: int, episodes: int = 128, score: float | None = None, run_id: str | None = None) -> dict:
    value = (seed / 1000.0) if score is None else score
    config = {
        "seed": seed,
        "episodes": episodes,
        "round_trip_cost_bp": 23,
        "top_k": 10,
        "n_folds": 5,
        "purge_days": 5,
        "embargo_days": 5,
    }
    metrics = {
        "test": {
            "total_net_return": value,
            "trade_count": 2,
            "never_trade": False,
            "max_drawdown": -0.01,
        },
        "val": {
            "total_net_return": value / 2,
            "trade_count": 1,
            "never_trade": False,
            "max_drawdown": -0.02,
        },
        "val+test": {
            "total_net_return": value * 1.5,
            "trade_count": 3,
            "never_trade": False,
            "max_drawdown": -0.03,
        },
    }
    return {
        "seed": seed,
        "episodes": episodes,
        "stage": "full",
        "run_id": run_id or f"daily_d4_stability_2026_07_12_seed{seed}_ep{episodes}",
        "status": "done",
        "config": config,
        "config_hash": sha256_payload(config),
        "metrics": metrics,
        "test_oos_primary": metrics["test"],
        "source_hashes": {"daily_rl_train.py": "a" * 64},
        "artifact_hashes": {"rl_manifest.json": "b" * 64},
    }


def _summary(cells: list[dict]) -> dict:
    deterministic = {
        "schema_version": 1,
        "mode": "daily_d4_stability_sweep",
        "cost_round_trip_bp": 23,
        "fixed_grid": {"seeds": [cell["seed"] for cell in cells], "episodes": sorted({cell["episodes"] for cell in cells})},
        "research_locks": {"test_oos_primary": True, "aliases_excluded": True},
        "cells": cells,
    }
    return {
        **deterministic,
        "generated_at": "2026-07-12T00:00:00+00:00",
        "deterministic_content_hash": sha256_payload(deterministic),
    }


def test_aim_adapter_disabled_has_no_aim_dependency_and_is_noop(tmp_path):
    env = {"KRONOS_USE_AIM": "0", "KRONOS_AIM_REPO": str(tmp_path / "aim")}

    tracker = maybe_create_tracker(
        run_name="disabled",
        config={"seed": 7},
        hashes={"manifest": "abc"},
        env=env,
    )

    assert aim_enabled(env) is False
    assert tracker.enabled is False
    assert tracker.run is None
    tracker.log_metrics({"reward": 1.25}, step=1)
    tracker.close()


def test_rliable_report_happy_path_is_deterministic_and_exposes_contract_metadata(tmp_path):
    sweep = _summary([
        _cell(7, score=0.01),
        _cell(17, score=0.03),
        _cell(29, score=-0.02),
        _cell(41, score=0.04),
    ])
    sweep_path = tmp_path / "stability_summary.json"
    sweep_path.write_text(json.dumps(sweep, ensure_ascii=False, indent=2), encoding="utf-8")

    report_a = rl_report_rliable.build_report(
        sweep,
        input_path=sweep_path,
        episodes=128,
        reps=200,
        seed=123,
        generated_at="fixed",
    )
    report_b = rl_report_rliable.build_report(
        sweep,
        input_path=sweep_path,
        episodes=128,
        reps=200,
        seed=123,
        generated_at="fixed",
    )

    assert report_a == report_b
    assert report_a["research_only"] is True
    assert "RESEARCH_ONLY" in report_a["note"]
    assert report_a["rliable_backend"]["library"] == "rliable"
    assert report_a["rliable_backend"]["version"]
    assert report_a["bootstrap"]["method"] == "rliable_stratified_seed_resample"
    assert report_a["split"] == "test"
    assert report_a["cost_round_trip_bp"] == 23.0
    assert report_a["seed_set"] == [7, 17, 29, 41]
    assert report_a["input_sha256"] == rl_report_rliable._sha256_file(sweep_path)
    assert report_a["source_summary_hash"] == sweep["deterministic_content_hash"]
    assert report_a["metrics"]["iqm"]["ci_lower"] <= report_a["metrics"]["iqm"]["point"] <= report_a["metrics"]["iqm"]["ci_upper"]
    assert [row["threshold_total_net_return"] for row in report_a["performance_profile"]] == [-0.10, -0.05, 0.0, 0.05, 0.10]
    assert all(row["ci_lower"] <= row["fraction_above_threshold"] <= row["ci_upper"] for row in report_a["performance_profile"])
    assert report_a["source_hashes_by_run_id"]["daily_d4_stability_2026_07_12_seed7_ep128"]
    assert report_a["artifact_hashes_by_run_id"]["daily_d4_stability_2026_07_12_seed7_ep128"]

    report_default_a = rl_report_rliable.build_report(
        sweep,
        input_path=sweep_path,
        episodes=128,
        reps=200,
        seed=123,
    )
    report_default_b = rl_report_rliable.build_report(
        sweep,
        input_path=sweep_path,
        episodes=128,
        reps=200,
        seed=123,
    )
    assert report_default_a == report_default_b
    assert report_default_a["generated_at"] == sweep["generated_at"]
    assert report_default_a["generation_time_basis"] == "source_summary_generated_at"


def test_rliable_report_rejects_mixed_episode_cohorts_without_explicit_filter():
    sweep = _summary([_cell(7, episodes=8), _cell(17, episodes=8), _cell(29, episodes=8), _cell(7), _cell(17), _cell(29)])

    with pytest.raises(rl_report_rliable.RliableReportError, match="mixed_episode_cohorts"):
        rl_report_rliable.build_report(sweep, reps=20, seed=1, generated_at="fixed")


def test_rliable_report_rejects_missing_cost_split_and_nonfinite_data():
    missing_cost = _summary([_cell(7), _cell(17), _cell(29)])
    missing_cost.pop("cost_round_trip_bp")
    with pytest.raises(rl_report_rliable.RliableReportError, match="cost_round_trip_bp"):
        rl_report_rliable.build_report(missing_cost, episodes=128, reps=20, seed=1)

    missing_test = _summary([_cell(7), _cell(17), _cell(29)])
    missing_test["cells"][0]["metrics"].pop("test")
    with pytest.raises(rl_report_rliable.RliableReportError, match="test"):
        rl_report_rliable.build_report(missing_test, episodes=128, reps=20, seed=1)

    nonfinite = _summary([_cell(7), _cell(17), _cell(29)])
    nonfinite["cells"][1]["metrics"]["test"]["total_net_return"] = float("nan")
    nonfinite["cells"][1]["test_oos_primary"] = nonfinite["cells"][1]["metrics"]["test"]
    with pytest.raises(rl_report_rliable.RliableReportError, match="nonfinite"):
        rl_report_rliable.build_report(nonfinite, episodes=128, reps=20, seed=1)

    wrong_cell_cost = _summary([_cell(7), _cell(17), _cell(29)])
    wrong_cell_cost["cells"][0]["config"]["round_trip_cost_bp"] = 46
    wrong_cell_cost["cells"][0]["config_hash"] = sha256_payload(
        wrong_cell_cost["cells"][0]["config"]
    )
    with pytest.raises(rl_report_rliable.RliableReportError, match="cell_cost_mismatch"):
        rl_report_rliable.build_report(wrong_cell_cost, episodes=128, reps=20, seed=1)

    missing_source_hashes = _summary([_cell(7), _cell(17), _cell(29)])
    missing_source_hashes["cells"][0]["source_hashes"] = {}
    with pytest.raises(rl_report_rliable.RliableReportError, match="source_hashes"):
        rl_report_rliable.build_report(missing_source_hashes, episodes=128, reps=20, seed=1)

    missing_artifact_hashes = _summary([_cell(7), _cell(17), _cell(29)])
    missing_artifact_hashes["cells"][0]["artifact_hashes"] = {}
    with pytest.raises(rl_report_rliable.RliableReportError, match="artifact_hashes"):
        rl_report_rliable.build_report(missing_artifact_hashes, episodes=128, reps=20, seed=1)

    config_hash_mismatch = _summary([_cell(7), _cell(17), _cell(29)])
    config_hash_mismatch["cells"][0]["config_hash"] = "0" * 64
    with pytest.raises(rl_report_rliable.RliableReportError, match="config_hash_mismatch"):
        rl_report_rliable.build_report(config_hash_mismatch, episodes=128, reps=20, seed=1)


def test_rliable_report_rejects_duplicate_run_ids_mixed_configs_and_seed_aliases():
    duplicate_run = _summary([_cell(7, run_id="same"), _cell(17, run_id="same"), _cell(29)])
    with pytest.raises(rl_report_rliable.RliableReportError, match="duplicate_run_id"):
        rl_report_rliable.build_report(duplicate_run, episodes=128, reps=20, seed=1)

    mixed_config = _summary([_cell(7), _cell(17), _cell(29)])
    mixed_config["cells"][1]["config"]["top_k"] = 5
    mixed_config["cells"][1]["config_hash"] = sha256_payload(
        mixed_config["cells"][1]["config"]
    )
    with pytest.raises(rl_report_rliable.RliableReportError, match="mixed_configs"):
        rl_report_rliable.build_report(mixed_config, episodes=128, reps=20, seed=1)

    alias = _summary([_cell(7), _cell(17), _cell(29)])
    alias["cells"][0]["alias_of"] = "daily_d4_stability_2026_07_12_seed7_ep128"
    with pytest.raises(rl_report_rliable.RliableReportError, match="aliases"):
        rl_report_rliable.build_report(alias, episodes=128, reps=20, seed=1)


def test_rliable_report_rejects_six_run_ids_all_seed100_as_one_seed_not_six():
    cells = [_cell(100, run_id=f"candidate_alias_{idx}", score=0.01 + idx / 1000) for idx in range(6)]
    sweep = _summary(cells)

    with pytest.raises(rl_report_rliable.RliableReportError, match="duplicate_seed:100"):
        rl_report_rliable.build_report(sweep, episodes=128, reps=20, seed=1)
