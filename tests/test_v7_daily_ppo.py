"""Contract coverage for the V7 M2 PPO trainer (env, scoring, verdict)."""
from __future__ import annotations

from pathlib import Path

import pytest

from stom_rl.daily_v6_train import CAPITAL
from stom_rl.daily_v7_ppo import decide_verdict_m2, evaluate_policy_scores, make_env

from stom_rl.daily_v6_train import load_dataset, _sessions
from tests.test_v6_daily_train import _write_dataset

pytestmark = [
    pytest.mark.filterwarnings("ignore::UserWarning"),
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
    pytest.mark.filterwarnings("ignore::FutureWarning"),
]


def _baselines(rule_nav: float = CAPITAL) -> dict:
    return {name: {"nav": rule_nav if name != "no_trade" else CAPITAL}
            for name in ("no_trade", "rule_topk_ret5", "rule_topk_low_vol", "rule_topk_inst", "random_topk")}


def test_decide_verdict_m2_majority_and_control() -> None:
    results = {str(seed): {"final_val_metrics": {"nav": CAPITAL + 1}} for seed in range(3)}
    clean = {str(seed): {"control_fails": False} for seed in range(3)}
    assert decide_verdict_m2(results, _baselines(), clean)[0] == "GO_CANDIDATE_VALIDATION_ONLY"

    one = dict(results)
    one["1"] = {"final_val_metrics": {"nav": CAPITAL - 1}}
    one["2"] = {"final_val_metrics": {"nav": CAPITAL - 1}}
    assert decide_verdict_m2(one, _baselines(), clean)[0] == "INCONCLUSIVE"

    dirty = dict(clean)
    dirty["0"] = {"control_fails": True}
    verdict, reasons, _ = decide_verdict_m2(results, _baselines(), dirty)
    assert verdict == "NO_GO"
    assert "exposure-matched" in reasons[0]


def test_env_enforces_slots_and_reward_accounting(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    _write_dataset(root, "clean")
    rows = [row for row in load_dataset("clean", root)["rows"] if row["split"] == "train"]
    sessions = _sessions(rows)

    env = make_env(sessions, seed=0)
    observation, _ = env.reset(seed=0)
    assert observation.shape == (10,)
    total_reward = 0.0
    enters = 0
    terminated = False
    while not terminated:
        observation, reward, terminated, truncated, _ = env.step(1)
        assert truncated is False
        total_reward += reward
        if reward != 0.0:
            enters += 1
    # 3 distinct symbols per session -> at most 3 rewarded enters, never > slots
    assert 0 < enters <= 3
    # rewards are (label - cost) * 100 for the fixture labels
    expected = sum((label - 0.0023) * 100.0 for label in (-0.01, 0.005, 0.02))
    assert total_reward == pytest.approx(expected)


def test_evaluate_policy_scores_matches_slot_accounting(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    _write_dataset(root, "clean")
    val_rows = [row for row in load_dataset("clean", root)["rows"] if row["split"] == "val"]

    # score CCC (label +0.02) above threshold, everything else below
    scores = [0.9 if row["symbol"] == "CCC" else 0.1 for row in val_rows]
    metrics, pick_counts = evaluate_policy_scores(val_rows, scores)

    sessions = 5  # fixture: 5 val sessions
    assert pick_counts == [1] * sessions
    assert metrics["trade_count"] == sessions
    assert metrics["max_positions_per_session"] == 1
    expected_nav = CAPITAL + sessions * 5_000_000 * (0.02 - 0.0023)
    assert metrics["nav"] == pytest.approx(expected_nav)
    navs = metrics["cost_scenario_navs"]
    assert navs["0.0000"] >= navs["0.0023"] >= navs["0.0046"]


def test_ppo_smoke_training_writes_contract_manifest(tmp_path: Path) -> None:
    """SB3/torch cannot initialise inside this machine's pytest parent process
    (known c10.dll WinError 1114 quirk); follow the repo convention from
    tests/test_stom_rl_orderbook_sb3.py and run the trainer in a subprocess,
    skipping only when the DLL environment failure markers appear."""
    import json
    import subprocess
    import sys

    root = tmp_path / "runs"
    _write_dataset(root, "clean")

    result = subprocess.run(
        [sys.executable, "-m", "stom_rl.daily_v7_ppo", "--dataset", "clean", "--seeds", "0",
         "--smoke", "--out-root", str(root), "--total-timesteps", "512"],
        text=True, capture_output=True, check=False, cwd=str(Path(__file__).resolve().parents[1]),
    )
    combined = result.stdout + result.stderr
    if result.returncode != 0 and any(
        marker in combined for marker in ["ModuleNotFoundError", "DLL load failed", "WinError 1114", "c10.dll"]
    ):
        pytest.skip(combined)
    assert result.returncode == 0, combined

    run_dirs = sorted((root / "clean").glob("train_*"))
    assert len(run_dirs) == 1
    manifest = json.loads((run_dirs[0] / "run_manifest.json").read_text(encoding="utf-8"))

    assert manifest["trainer_version"] == "kronos_v7_m2_ppo.v1"
    assert manifest["prereg"]["id"] == "KRONOS-V7-PREREG-M2-2026-07-20"
    assert manifest["seeds"] == [0]
    assert set(manifest["baselines"]) == {"no_trade", "rule_topk_ret5", "rule_topk_low_vol", "rule_topk_inst", "random_topk"}
    seed_entry = manifest["per_seed"]["0"]
    assert "model" not in seed_entry and "pick_counts" not in seed_entry
    assert len(seed_entry["val_nav_curve"]) == seed_entry["episodes_ran"]
    assert manifest["exposure_matched_control"]["0"]["reps"] == 20
    assert isinstance(manifest["negative_control_checks"]["0"]["control_fails"], bool)
    assert manifest["test"] == {"state": "NOT_RUN"}
    assert manifest["verdict_candidate"]["value"] in {"NO_GO", "INCONCLUSIVE", "GO_CANDIDATE_VALIDATION_ONLY"}
    assert all(value is False for value in manifest["false_research_locks"].values())
    assert (run_dirs[0] / "events.jsonl").is_file()
