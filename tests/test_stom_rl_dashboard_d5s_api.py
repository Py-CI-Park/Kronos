from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d5_approval import primary_custody_signature
from stom_rl.rl_discovery.d5s_contract import load_d5s_prereg_bytes
from stom_rl.rl_discovery.d5s_gate import (
    D5SBaseline,
    D5SCheckpointOutcome,
    evaluate_d5s_stability_gate,
)
from stom_rl.rl_discovery.storage import JsonValue, artifact_manifest_sha256
from webui import rl_dashboard
from webui.rl_dashboard_d5s import valid_d5s_primary
from webui.rl_dashboard_discovery import find_discovery_evidence

CHECKPOINTS = (50_000, 100_000, 150_000, 200_000, 300_000, 400_000)
PREREG_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "kronos_rl_discovery_type2_d5s_prereg_2026-07-30.json"
)


def _metric(accuracy: float, reward_ratio: float) -> dict[str, JsonValue]:
    return {
        "accuracy": accuracy,
        "reward_ratio": reward_ratio,
        "total_reward": reward_ratio,
        "oracle_reward": 1.0,
        "trade_rate": 0.8,
        "dominant_action_rate": 0.4,
        "invalid_action_count": 0,
    }


def _write_primary(
    run: Path,
    key: bytes,
) -> tuple[dict[str, JsonValue], dict[str, JsonValue], str]:
    prereg_bytes = PREREG_PATH.read_bytes()
    prereg = load_d5s_prereg_bytes(prereg_bytes)
    inputs = run / "inputs"
    inputs.mkdir(parents=True)
    _ = (inputs / "prereg.json").write_bytes(prereg_bytes)
    rows: list[JsonValue] = []
    outcomes: list[D5SCheckpointOutcome] = []
    rewards = {50_000: 0.82, 100_000: 0.86, 150_000: 0.89, 200_000: 0.91, 300_000: 0.90, 400_000: 0.88}
    for arm in ("NATIVE", "SHUFFLED"):
        for seed in range(3):
            for steps in CHECKPOINTS:
                reward = rewards[steps] + seed * 0.01 if arm == "NATIVE" else 0.10 + seed * 0.01
                accuracy = 0.73 + seed * 0.01 if arm == "NATIVE" else 0.20
                metric = _metric(accuracy, reward)
                row: dict[str, JsonValue] = {
                    "reward_arm": arm,
                    "seed": seed,
                    "total_steps": steps,
                    "fit_23bp": metric,
                    "native_23bp": metric,
                    "native_0bp": metric,
                }
                rows.append(row)
                outcomes.append(
                    D5SCheckpointOutcome(
                        arm,
                        seed,
                        steps,
                        D3Metrics(accuracy, reward, reward, 1.0, 0.8, 0.4, 0),
                    )
                )
                model = run / "models" / arm / f"seed-{seed}" / f"steps-{steps}" / "model.zip"
                outcome = run / "outcomes" / arm / f"seed-{seed}" / f"steps-{steps}.json"
                model.parent.mkdir(parents=True, exist_ok=True)
                outcome.parent.mkdir(parents=True, exist_ok=True)
                _ = model.write_bytes(b"model")
                _ = outcome.write_text(
                    json.dumps({**row, "events": {"fit_23bp": [], "native_23bp": [], "native_0bp": []}}),
                    encoding="utf-8",
                )
    baselines = (
        D5SBaseline(0, 0.7120418848167539, 0.8727793884825973),
        D5SBaseline(1, 0.6614310645724258, 0.8503857573981751),
        D5SBaseline(2, 0.7277486910994765, 0.9037528526603933),
    )
    gate = evaluate_d5s_stability_gate(tuple(outcomes), baselines)
    gate_payload: dict[str, JsonValue] = {
        "verdict": gate.verdict,
        "selected_steps": gate.selected_steps,
        "selected_native_median_accuracy": gate.selected_native_median_accuracy,
        "selected_native_median_reward_ratio": gate.selected_native_median_reward_ratio,
        "selected_native_reward_delta_vs_shuffled": gate.selected_native_reward_delta_vs_shuffled,
        "accuracy_degradation_at_400k": gate.accuracy_degradation_at_400k,
        "reward_ratio_degradation_at_400k": gate.reward_ratio_degradation_at_400k,
        "preserved_native_seed_fraction": gate.preserved_native_seed_fraction,
        "invalid_action_count": gate.invalid_action_count,
    }
    summary: dict[str, JsonValue] = {
        "schema_version": "kronos.rl-discovery.d5s.stability.v1",
        "profile": "PRIMARY",
        "status": "COMPLETE",
        "verdict": gate.verdict,
        "gate": gate_payload,
        "models": rows,
        "source_run": prereg.source_run.run_name,
        "approved_smoke": "type2-d5s-smoke",
        "d5_verdict_unchanged": "D5_FULL_TRAIN_COST_NOT_CONFIRMED",
        "d5r_verdict_unchanged": "D5R_CAPACITY_NOT_CONFIRMED",
        "reused_validation": "NOT_RUN_NO_READ",
        "fresh_oos": "NOT_RUN_NO_READ",
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "live_broker_order_allowed": False,
    }
    _ = (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    digest = artifact_manifest_sha256(run)
    receipt: dict[str, JsonValue] = {
        "schema_version": "kronos.rl-discovery.d5s.receipt.v1",
        "profile": "PRIMARY",
        "status": "COMPLETE",
        "verdict": gate.verdict,
        "artifact_manifest_sha256": digest,
        "fresh_oos": "NOT_RUN_NO_READ",
        "live_broker_order_allowed": False,
        "primary_custody_hmac_sha256": primary_custody_signature(
            key,
            run_name=run.name,
            prereg_sha=hashlib.sha256(prereg_bytes).hexdigest(),
            episode_sha=prereg.source_run.episode_snapshot_sha256,
            manifest_sha=digest,
            approved_smoke="type2-d5s-smoke",
        ),
    }
    _ = (run / "terminal_receipt.json").write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )
    return summary, receipt, digest


def test_d5s_primary_requires_authenticated_exact_stability_matrix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = tmp_path / "type2-d5s-primary"
    run.mkdir()
    key = bytes(range(32))
    summary, receipt, digest = _write_primary(run, key)
    monkeypatch.setenv("KRONOS_D5S_APPROVAL_KEY_HEX", key.hex())
    captured = {
        path.relative_to(run).as_posix(): path.read_bytes()
        for path in run.rglob("*.json")
        if path.name != "terminal_receipt.json"
    }
    paths = frozenset(path.relative_to(run).as_posix() for path in run.rglob("*") if path.is_file())

    assert valid_d5s_primary(run, summary, receipt, digest, paths, captured)

    (run / "models/NATIVE/seed-0/steps-50000/model.zip").unlink()
    paths = frozenset(path.relative_to(run).as_posix() for path in run.rglob("*") if path.is_file())
    assert not valid_d5s_primary(run, summary, receipt, digest, paths, captured)


def test_d5s_primary_blocks_unsigned_receipt_safety_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = tmp_path / "type2-d5s-primary-tamper"
    run.mkdir()
    key = bytes(range(32))
    summary, receipt, digest = _write_primary(run, key)
    receipt["live_broker_order_allowed"] = True
    monkeypatch.setenv("KRONOS_D5S_APPROVAL_KEY_HEX", key.hex())
    captured = {
        path.relative_to(run).as_posix(): path.read_bytes()
        for path in run.rglob("*.json")
        if path.name != "terminal_receipt.json"
    }
    paths = frozenset(path.relative_to(run).as_posix() for path in run.rglob("*") if path.is_file())

    assert not valid_d5s_primary(run, summary, receipt, digest, paths, captured)


def test_d5s_primary_is_discoverable_as_dashboard_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = tmp_path / "type2-d5s-primary-dashboard"
    run.mkdir()
    key = bytes(range(32))
    _ = _write_primary(run, key)
    monkeypatch.setenv("KRONOS_D5S_APPROVAL_KEY_HEX", key.hex())
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])

    record = next(item for item in rl_dashboard.list_rl_runs() if item["name"] == run.name)
    detail = rl_dashboard.load_rl_run(run.name)
    compact, evidence = find_discovery_evidence(run, "rl_discovery_d5s")

    assert record["artifact_type"] == "rl_discovery_d5s"
    assert record["strategy_context"]["line"] == "rl_experiment"
    assert record["strategy_context"]["is_reinforcement_learning"] is True
    assert record["strategy_context"]["is_live_ready"] is False
    assert detail["detail"]["gate"]["selected_steps"] == 200_000
    assert compact["type1_outcome"] == "D5S_STABILITY_EVALUATED"
    assert compact["primary_round_trip_cost_bp"] == 23
    assert evidence["live_broker_order_allowed"] is False

    (run / "outcomes/SHUFFLED/seed-2/steps-400000.json").unlink()
    blocked = rl_dashboard.load_rl_run(run.name)
    assert blocked["summary"]["status"] == "BLOCK"
    assert blocked["summary"]["verdict"] == "NO_GO"
    assert blocked["detail"] == {}
