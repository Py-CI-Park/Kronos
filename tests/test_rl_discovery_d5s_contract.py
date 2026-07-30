import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from stom_rl.rl_discovery.d3_env import D3Episode
from stom_rl.rl_discovery.d5r_contract import load_d5r_prereg_bytes
from stom_rl.rl_discovery.d5r_source import D5RSourceBundle, D5RSourceUnit
from stom_rl.rl_discovery.d5s_contract import load_d5s_prereg_bytes
from stom_rl.rl_discovery.storage import JsonValue, artifact_manifest_sha256

ROOT = Path(__file__).resolve().parents[1]


def test_d5s_contract_freezes_stability_selection_and_claim_boundaries() -> None:
    prereg = load_d5s_prereg_bytes(
        (ROOT / "docs/kronos_rl_discovery_type2_d5s_prereg_2026-07-30.json").read_bytes()
    )

    assert prereg.execution.checkpoint_total_steps == (
        50_000,
        100_000,
        150_000,
        200_000,
        300_000,
        400_000,
    )
    assert prereg.selection.per_seed_or_per_arm_checkpoint_selection_allowed is False
    assert prereg.gate.maximum_400k_reward_ratio_degradation_from_selected == 0.05
    assert prereg.claims_boundary.fresh_oos == "NOT_RUN_NO_READ"


def test_d5s_source_binds_d5r_primary_and_d5_baselines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from stom_rl.rl_discovery import d5s_source

    run = tmp_path / "webui/rl_runs/rl_discovery/type2-d5r-primary-20260730-001"
    summary = run / "summary.json"
    receipt = run / "terminal_receipt.json"
    run.mkdir(parents=True)
    _ = summary.write_text("{}", encoding="utf-8")
    _ = receipt.write_text("{}", encoding="utf-8")
    for arm in ("NATIVE", "SHUFFLED"):
        for seed in range(3):
            for steps in (400_000, 800_000):
                model = run / "models" / arm / f"seed-{seed}" / f"steps-{steps}" / "model.zip"
                outcome = run / "outcomes" / arm / f"seed-{seed}" / f"steps-{steps}.json"
                model.parent.mkdir(parents=True, exist_ok=True)
                outcome.parent.mkdir(parents=True, exist_ok=True)
                _ = model.write_bytes(b"model")
                _ = outcome.write_text("{}", encoding="utf-8")

    prereg_payload = cast(
        JsonValue,
        json.loads(
            (ROOT / "docs/kronos_rl_discovery_type2_d5s_prereg_2026-07-30.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    if not isinstance(prereg_payload, dict):
        raise AssertionError("D5S prereg fixture must be an object")
    source_run = prereg_payload.get("source_run")
    if not isinstance(source_run, dict):
        raise AssertionError("D5S source-run fixture must be an object")
    source_run["summary_sha256"] = hashlib.sha256(summary.read_bytes()).hexdigest()
    source_run["terminal_receipt_sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
    source_run["artifact_manifest_sha256"] = artifact_manifest_sha256(
        run,
        excluded_relative_paths=frozenset({"terminal_receipt.json"}),
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    prereg_path = docs / "kronos_rl_discovery_type2_d5s_prereg_2026-07-30.json"
    _ = prereg_path.write_text(json.dumps(prereg_payload), encoding="utf-8")

    d5r_prereg_bytes = (
        ROOT / "docs/kronos_rl_discovery_type2_d5r_prereg_2026-07-30.json"
    ).read_bytes()
    d5r_prereg = load_d5r_prereg_bytes(d5r_prereg_bytes)
    features = (0.0,) * 14
    episode = D3Episode(
        "20260102",
        tuple((f"{index:06d}", features, 0.0) for index in range(5)),
        features,
        0.0,
    )
    d5r_bundle = D5RSourceBundle(
        d5r_prereg,
        d5r_prereg_bytes,
        hashlib.sha256(d5r_prereg_bytes).hexdigest(),
        (episode,) * 573,
        tuple(D5RSourceUnit("NATIVE", seed, 0.72, 0.88, ()) for seed in range(3)),
    )

    def fake_d5r_source(_repo_root: Path) -> D5RSourceBundle:
        return d5r_bundle

    monkeypatch.setattr(d5s_source, "load_d5r_source", fake_d5r_source)

    source = d5s_source.load_d5s_source(tmp_path)

    assert len(source.episodes) == 573
    assert len(source.baselines) == 3
    assert {row.seed for row in source.baselines} == {0, 1, 2}
    assert source.prereg.source_run.verdict == "D5R_CAPACITY_NOT_CONFIRMED"
