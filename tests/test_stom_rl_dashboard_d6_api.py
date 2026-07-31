from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Literal

import pytest

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d3_env import D3Episode
from stom_rl.rl_discovery.d3_training import D3Metrics
from stom_rl.rl_discovery.d6_contract import load_d6_prereg_bytes
from stom_rl.rl_discovery.d6_gate import D6Evaluation, D6GateThresholds, evaluate_d6_gate
from stom_rl.rl_discovery.storage import JsonValue, artifact_manifest_sha256
from webui import rl_dashboard, rl_dashboard_d6
from webui.rl_dashboard_d6 import valid_d6_primary
from webui.rl_dashboard_discovery import find_discovery_evidence

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "docs/kronos_rl_discovery_type2_d6_prereg_2026-07-31.json"


def _metric(accuracy: float, ratio: float, reward: float) -> D3Metrics:
    return D3Metrics(accuracy, ratio, reward, 1.0, 0.9, 0.3, 0)


def _evaluations() -> tuple[D6Evaluation, ...]:
    values = (
        ("NATIVE", 0, 0.18, -0.04, -0.30, 0.60),
        ("NATIVE", 1, 0.15, -0.03, -0.26, 0.80),
        ("NATIVE", 2, 0.18, -0.10, -0.85, 1.10),
        ("SHUFFLED", 0, 0.14, -0.10, -0.82, 1.05),
        ("SHUFFLED", 1, 0.15, 0.002, 0.015, 0.30),
        ("SHUFFLED", 2, 0.21, 0.055, 0.44, 0.68),
    )
    rows: list[D6Evaluation] = []
    for arm, seed, accuracy, ratio, reward, drawdown in values:
        reward_arm: Literal["NATIVE", "SHUFFLED"] = (
            "NATIVE" if arm == "NATIVE" else "SHUFFLED"
        )
        rows.append(D6Evaluation(reward_arm, seed, _metric(accuracy, ratio, reward), drawdown))
    return tuple(rows)


def _allow_custody(_run_dir: Path, _digest: str) -> bool:
    return True


def _write_primary(run: Path) -> tuple[dict[str, JsonValue], dict[str, JsonValue], str]:
    prereg_bytes = PREREG.read_bytes()
    prereg = load_d6_prereg_bytes(prereg_bytes)
    inputs = run / "inputs"
    inputs.mkdir(parents=True)
    _ = (inputs / "prereg.json").write_bytes(prereg_bytes)
    features = (0.0,) * 14
    episodes = tuple(
        D3Episode(
            f"validation-{index:03d}",
            tuple((f"{candidate:06d}", features, 0.01) for candidate in range(5)),
            features,
            index / 127,
        )
        for index in range(128)
    )
    snapshot = canonical_json_bytes([asdict(episode) for episode in episodes])
    _ = (inputs / "validation_episodes.json").write_bytes(snapshot)
    evaluations = _evaluations()
    rows: list[JsonValue] = []
    for evaluation in evaluations:
        row: dict[str, JsonValue] = {
            "reward_arm": evaluation.reward_arm,
            "seed": evaluation.seed,
            "selected_steps": 100_000,
            "source_model_sha256": next(
                model.sha256
                for model in prereg.source_run.models
                if model.reward_arm == evaluation.reward_arm and model.seed == evaluation.seed
            ),
            "validation_23bp": asdict(evaluation.metrics),
            "validation_0bp": asdict(evaluation.metrics),
            "maximum_drawdown_23bp": evaluation.maximum_drawdown,
        }
        rows.append(row)
        outcome = run / "outcomes" / evaluation.reward_arm / f"seed-{evaluation.seed}.json"
        outcome.parent.mkdir(parents=True, exist_ok=True)
        _ = outcome.write_text(
            json.dumps({**row, "events": {"validation_23bp": [], "validation_0bp": []}}),
            encoding="utf-8",
        )
    thresholds = D6GateThresholds(
        prereg.gate.minimum_native_median_accuracy,
        prereg.gate.minimum_native_median_reward_ratio,
        prereg.gate.minimum_native_median_total_reward,
        prereg.gate.minimum_native_reward_delta_vs_shuffled,
        prereg.gate.minimum_passing_native_seed_fraction,
        prereg.gate.maximum_native_median_reward_drawdown,
        prereg.gate.zero_invalid_actions,
    )
    gate = evaluate_d6_gate(evaluations, thresholds=thresholds)
    summary: dict[str, JsonValue] = {
        "schema_version": "kronos.rl-discovery.d6.validation.v1",
        "profile": "PRIMARY",
        "status": "COMPLETE",
        "verdict": gate.verdict,
        "gate": asdict(gate),
        "evaluations": rows,
        "source_run": prereg.source_run.run_name,
        "selected_steps": 100_000,
        "validation_episode_count": 128,
        "validation_episode_sha256": hashlib.sha256(snapshot).hexdigest(),
        "input_hashes": {},
        "validation_origin": "FAILED_RUN_SNAPSHOT",
        "recovery_run": "type2-d6-primary-20260731-001",
        "validation_read_count": 1,
        "reused_validation": "COMPLETE",
        "fresh_oos": "NOT_RUN_NO_READ",
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "live_broker_order_allowed": False,
    }
    _ = (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    digest = artifact_manifest_sha256(run)
    receipt: dict[str, JsonValue] = {
        "schema_version": "kronos.rl-discovery.d6.receipt.v1",
        "profile": "PRIMARY",
        "status": "COMPLETE",
        "verdict": gate.verdict,
        "artifact_manifest_sha256": digest,
        "validation_episode_sha256": hashlib.sha256(snapshot).hexdigest(),
        "validation_origin": "FAILED_RUN_SNAPSHOT",
        "recovery_run": "type2-d6-primary-20260731-001",
        "reused_validation": "COMPLETE",
        "fresh_oos": "NOT_RUN_NO_READ",
        "live_broker_order_allowed": False,
    }
    _ = (run / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return summary, receipt, digest


def test_d6_primary_is_fail_closed_and_discoverable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    run = tmp_path / "type2-d6-primary"
    run.mkdir()
    summary, receipt, digest = _write_primary(run)
    monkeypatch.setattr(rl_dashboard_d6, "_matches_custody", _allow_custody)
    monkeypatch.setattr(rl_dashboard, "RL_RUN_ROOTS", [tmp_path])
    captured = {
        path.relative_to(run).as_posix(): path.read_bytes()
        for path in run.rglob("*.json")
        if path.name != "terminal_receipt.json"
    }
    paths = frozenset(path.relative_to(run).as_posix() for path in run.rglob("*") if path.is_file())

    # When
    valid = valid_d6_primary(run, summary, receipt, digest, paths, captured)
    record = next(item for item in rl_dashboard.list_rl_runs() if item["name"] == run.name)
    compact, detail = find_discovery_evidence(run, "rl_discovery_d6")

    # Then
    assert valid
    assert record["artifact_type"] == "rl_discovery_d6"
    assert compact["type1_outcome"] == "D6_REUSED_VALIDATION_NOT_CONFIRMED"
    assert detail["fresh_oos"] == "NOT_RUN_NO_READ"

    (run / "outcomes/SHUFFLED/seed-2.json").unlink()
    blocked, blocked_detail = find_discovery_evidence(run, "rl_discovery_d6")
    assert blocked["status"] == "BLOCK"
    assert blocked_detail == {}
