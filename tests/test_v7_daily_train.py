"""Contract coverage for the V7 M1 tabular-Q v2 trainer."""
from __future__ import annotations

from pathlib import Path

from stom_rl.daily_v6_train import CAPITAL
from stom_rl.daily_v7_train import decide_verdict, run_training

from tests.test_v6_daily_train import _write_dataset


def _seed_result(nav: float) -> dict:
    return {"final_val_metrics": {"nav": nav}}


def _baselines(rule_nav: float = CAPITAL) -> dict:
    return {name: {"nav": rule_nav if name != "no_trade" else CAPITAL}
            for name in ("no_trade", "rule_topk_ret5", "rule_topk_low_vol", "rule_topk_inst", "random_topk")}


def test_decide_verdict_requires_majority_and_exposure_matched_control() -> None:
    passing = {str(seed): _seed_result(CAPITAL + 1_000_000) for seed in range(5)}
    clean_controls = {str(seed): {"control_fails": False} for seed in range(5)}

    verdict, reasons, qualifying = decide_verdict(passing, _baselines(), clean_controls)
    assert verdict == "GO_CANDIDATE_VALIDATION_ONLY"
    assert len(qualifying) == 5

    two_pass = {str(seed): _seed_result(CAPITAL + (1_000_000 if seed < 2 else -1_000_000)) for seed in range(5)}
    verdict, reasons, qualifying = decide_verdict(two_pass, _baselines(), clean_controls)
    assert verdict == "INCONCLUSIVE"
    assert qualifying == ["0", "1"]

    none_pass = {str(seed): _seed_result(CAPITAL - 1_000_000) for seed in range(5)}
    verdict, reasons, _ = decide_verdict(none_pass, _baselines(), clean_controls)
    assert verdict == "NO_GO"

    # control failure dominates even a full sweep of qualifying seeds
    dirty_controls = dict(clean_controls)
    dirty_controls["3"] = {"control_fails": True}
    verdict, reasons, _ = decide_verdict(passing, _baselines(), dirty_controls)
    assert verdict == "NO_GO"
    assert "exposure-matched" in reasons[0]


def test_v7_training_manifest_records_exposure_matched_control(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    _write_dataset(root, "clean")

    result = run_training("clean", seeds=(0, 1), out_root=root, train_run_id="v7one", smoke=True)
    manifest = result["manifest"]

    assert manifest["trainer_version"] == "kronos_v7_m1_tabular_q.v2"
    assert manifest["prereg"]["id"] == "KRONOS-V7-PREREG-M1-2026-07-20"
    assert set(manifest["baselines"]) == {"no_trade", "rule_topk_ret5", "rule_topk_low_vol", "rule_topk_inst", "random_topk"}
    assert manifest["baselines"]["no_trade"]["nav"] == CAPITAL
    # smoke keeps only the first seed
    assert manifest["seeds"] == [0]
    control = manifest["exposure_matched_control"]["0"]
    assert control["reps"] == 20
    assert control["threshold_nav"] >= CAPITAL
    check = manifest["negative_control_checks"]["0"]
    assert check["threshold_nav"] == control["threshold_nav"]
    assert isinstance(check["control_fails"], bool)
    assert manifest["shuffled_label_control"]["0"]["train_labels_changed"] is True
    assert manifest["test"] == {"state": "NOT_RUN"}
    assert manifest["verdict_candidate"]["value"] in {"NO_GO", "INCONCLUSIVE", "GO_CANDIDATE_VALIDATION_ONLY"}
    assert all(value is False for value in manifest["false_research_locks"].values())

    # deterministic rerun
    second = run_training("clean", seeds=(0, 1), out_root=root, train_run_id="v7two", smoke=True)["manifest"]
    for key in ("per_seed", "baselines", "exposure_matched_control", "negative_control_checks", "verdict_candidate"):
        assert manifest[key] == second[key]


def test_v7_go_candidate_gate_controls_test_split(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    _write_dataset(root, "clean")

    result = run_training("clean", seeds=(0, 1, 2, 3, 4), out_root=root, train_run_id="v7full", final_test=True)
    manifest = result["manifest"]

    if manifest["verdict_candidate"]["value"] == "GO_CANDIDATE_VALIDATION_ONLY":
        assert manifest["test"]["state"] == "RUN"
    else:
        assert manifest["test"] == {"state": "NOT_RUN"}
