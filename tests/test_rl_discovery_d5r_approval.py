from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from stom_rl.rl_discovery.d5r_approval import approve_d5r_smoke, create_d5r_smoke_approval
from stom_rl.rl_discovery.d5r_contract import load_d5r_prereg_bytes
from stom_rl.rl_discovery.storage import artifact_manifest_sha256

ROOT = Path(__file__).resolve().parents[1]


def test_d5r_smoke_requires_detached_exact_approval(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    smoke = run_root / "smoke"
    (smoke / "inputs").mkdir(parents=True)
    prereg_source = ROOT / "docs/kronos_rl_discovery_type2_d5r_prereg_2026-07-30.json"
    shutil.copyfile(prereg_source, smoke / "inputs/prereg.json")
    models = []
    for arm in ("NATIVE", "SHUFFLED"):
        model = smoke / "models" / arm / "seed-0" / "steps-2048" / "model.zip"
        outcome = smoke / "outcomes" / arm / "seed-0" / "steps-2048.json"
        model.parent.mkdir(parents=True)
        outcome.parent.mkdir(parents=True)
        model.write_bytes(b"model")
        outcome.write_text("{}", encoding="utf-8")
        models.append({"reward_arm": arm, "seed": 0, "total_steps": 2048})
    summary = {
        "schema_version": "kronos.rl-discovery.d5r.capacity.v1",
        "profile": "SMOKE",
        "status": "COMPLETE",
        "verdict": "D5R_SMOKE_COMPLETE",
        "models": models,
    }
    (smoke / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    digest = artifact_manifest_sha256(smoke)
    receipt = {
        "profile": "SMOKE",
        "status": "COMPLETE",
        "verdict": "D5R_SMOKE_COMPLETE",
        "artifact_manifest_sha256": digest,
    }
    (smoke / "terminal_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    key = bytes(range(32))
    prereg_bytes = prereg_source.read_bytes()
    prereg = load_d5r_prereg_bytes(prereg_bytes)

    _ = create_d5r_smoke_approval(smoke, run_root=run_root, approval_key=key)
    approved = approve_d5r_smoke(
        smoke,
        run_root=run_root,
        approval_key=key,
        prereg_sha=hashlib.sha256(prereg_bytes).hexdigest(),
        episode_sha=prereg.source_run.episode_snapshot_sha256,
    )

    assert approved == "smoke"
