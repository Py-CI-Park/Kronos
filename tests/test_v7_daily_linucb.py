"""Contract coverage for the V7 M3 LinUCB trainer."""
from __future__ import annotations

from pathlib import Path

import pytest

from stom_rl.daily_v6_train import CAPITAL
from stom_rl.daily_v7_linucb import LinUcbModel, _context, _solve, run_training

from tests.test_v6_daily_train import _write_dataset


def test_solve_recovers_known_linear_system() -> None:
    matrix = [[4.0, 1.0], [1.0, 3.0]]
    solution = _solve(matrix, [1.0, 2.0])
    assert solution[0] == pytest.approx(1.0 / 11.0)
    assert solution[1] == pytest.approx(7.0 / 11.0)


def test_linucb_model_learns_positive_reward_direction() -> None:
    model = LinUcbModel()
    positive = {"ret_1d_prev": 1.0, "ret_5d_prev": 1.0, "ret_20d_prev": 1.0, "vol_z_20": 0.0,
                "foreign_ratio_prev": 0.0, "foreign_ratio_delta_5": 0.0, "inst_netbuy_norm_5": 0.0}
    negative = {key: -value for key, value in positive.items()}
    for _ in range(50):
        model.update(_context(positive), 0.02)
        model.update(_context(negative), -0.02)
    theta = model.theta()
    score_positive = sum(t * v for t, v in zip(theta, _context(positive)))
    score_negative = sum(t * v for t, v in zip(theta, _context(negative)))
    assert score_positive > 0 > score_negative


def test_linucb_training_manifest_contract_and_determinism(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    _write_dataset(root, "clean")

    result = run_training("clean", seeds=(0, 1, 2), out_root=root, train_run_id="ucb-one")
    manifest = result["manifest"]

    assert manifest["trainer_version"] == "kronos_v7_m3_linucb.v1"
    assert manifest["prereg"]["id"] == "KRONOS-V7-PREREG-M3-2026-07-20"
    assert manifest["seeds"] == [0, 1, 2]
    assert set(manifest["baselines"]) == {"no_trade", "rule_topk_ret5", "rule_topk_low_vol", "rule_topk_inst", "random_topk"}
    for seed in ("0", "1", "2"):
        entry = manifest["per_seed"][seed]
        assert set(entry["theta"]) == {"ret_1d_prev", "ret_5d_prev", "ret_20d_prev", "vol_z_20",
                                       "foreign_ratio_prev", "foreign_ratio_delta_5", "inst_netbuy_norm_5", "bias"}
        assert entry["final_val_metrics"]["max_positions_per_session"] <= 10
        assert entry["final_val_metrics"]["max_invested_krw"] <= 50_000_000
        navs = entry["final_val_metrics"]["cost_scenario_navs"]
        assert navs["0.0000"] >= navs["0.0023"] >= navs["0.0046"]
        assert isinstance(manifest["negative_control_checks"][seed]["control_fails"], bool)
        assert manifest["exposure_matched_control"][seed]["reps"] == 20
    assert manifest["baselines"]["no_trade"]["nav"] == CAPITAL
    assert manifest["test"] == {"state": "NOT_RUN"}
    assert manifest["verdict_candidate"]["value"] in {"NO_GO", "INCONCLUSIVE", "GO_CANDIDATE_VALIDATION_ONLY"}
    assert all(value is False for value in manifest["false_research_locks"].values())

    second = run_training("clean", seeds=(0, 1, 2), out_root=root, train_run_id="ucb-two")["manifest"]
    for key in ("per_seed", "baselines", "negative_control_checks", "verdict_candidate"):
        assert manifest[key] == second[key]
