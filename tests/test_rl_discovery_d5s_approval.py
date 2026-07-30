from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from stom_rl.rl_discovery.d5s_approval import (
    approve_d5s_smoke,
    create_d5s_smoke_approval,
)
from stom_rl.rl_discovery.d5s_contract import load_d5s_prereg_bytes
from stom_rl.rl_discovery.storage import artifact_manifest_sha256

ROOT = Path(__file__).resolve().parents[1]


def test_d5s_smoke_requires_detached_exact_approval(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    smoke = run_root / "smoke"
    (smoke / "inputs").mkdir(parents=True)
    prereg_source = ROOT / "docs/kronos_rl_discovery_type2_d5s_prereg_2026-07-30.json"
    shutil.copyfile(prereg_source, smoke / "inputs/prereg.json")
    models = []
    metric = {
        "accuracy": 0.5,
        "reward_ratio": 0.5,
        "total_reward": 0.5,
        "oracle_reward": 1.0,
        "trade_rate": 0.5,
        "dominant_action_rate": 0.5,
        "invalid_action_count": 0,
    }
    for arm in ("NATIVE", "SHUFFLED"):
        model = smoke / "models" / arm / "seed-0" / "steps-4096" / "model.zip"
        outcome = smoke / "outcomes" / arm / "seed-0" / "steps-4096.json"
        model.parent.mkdir(parents=True)
        outcome.parent.mkdir(parents=True)
        model.write_bytes(b"model")
        outcome.write_text("{}", encoding="utf-8")
        models.append(
            {
                "reward_arm": arm,
                "seed": 0,
                "total_steps": 4096,
                "fit_23bp": metric,
                "native_23bp": metric,
                "native_0bp": metric,
            }
        )
    summary = {
        "schema_version": "kronos.rl-discovery.d5s.stability.v1",
        "profile": "SMOKE",
        "status": "COMPLETE",
        "verdict": "D5S_SMOKE_COMPLETE",
        "gate": None,
        "models": models,
        "source_run": "type2-d5r-primary-20260730-001",
        "approved_smoke": None,
        "d5_verdict_unchanged": "D5_FULL_TRAIN_COST_NOT_CONFIRMED",
        "d5r_verdict_unchanged": "D5R_CAPACITY_NOT_CONFIRMED",
        "reused_validation": "NOT_RUN_NO_READ",
        "fresh_oos": "NOT_RUN_NO_READ",
        "promotion_allowed": False,
        "profitability_claim_allowed": False,
        "live_broker_order_allowed": False,
    }
    (smoke / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    digest = artifact_manifest_sha256(smoke)
    receipt = {
        "schema_version": "kronos.rl-discovery.d5s.receipt.v1",
        "profile": "SMOKE",
        "status": "COMPLETE",
        "verdict": "D5S_SMOKE_COMPLETE",
        "artifact_manifest_sha256": digest,
        "fresh_oos": "NOT_RUN_NO_READ",
        "live_broker_order_allowed": False,
    }
    (smoke / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    key = bytes(range(32))
    prereg_bytes = prereg_source.read_bytes()
    prereg = load_d5s_prereg_bytes(prereg_bytes)

    _ = create_d5s_smoke_approval(smoke, run_root=run_root, approval_key=key)
    approved = approve_d5s_smoke(
        smoke,
        run_root=run_root,
        approval_key=key,
        prereg_sha=hashlib.sha256(prereg_bytes).hexdigest(),
        episode_sha=prereg.source_run.episode_snapshot_sha256,
    )

    assert approved == "smoke"
