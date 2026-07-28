from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from stom_rl.rl_discovery.custody import build_custody_manifest


def test_custody_manifest_hashes_every_run_file_and_source_boundary(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    model_path = run_dir / "models" / "A_PPO_ONLY" / "seed-0" / "model.zip"
    model_path.parent.mkdir(parents=True)
    _ = model_path.write_bytes(b"model")
    receipt_path = run_dir / "terminal_receipt.json"
    prereg_sha256 = hashlib.sha256(b"prereg").hexdigest()
    receipt = (
        '{"status":"PRIMARY_COMPLETE","verdict":"NO_GO",'
        '"fresh_oos":"NOT_RUN_NO_READ","promotion_allowed":false,'
        f'"profitability_claim_allowed":false,"prereg_sha256":"{prereg_sha256}"}}'
    )
    _ = receipt_path.write_text(receipt, encoding="utf-8")
    fixture_path = tmp_path / "fixture.json"
    prereg_path = tmp_path / "prereg.json"
    _ = fixture_path.write_bytes(b"fixture")
    _ = prereg_path.write_bytes(b"prereg")

    manifest = build_custody_manifest(
        run_dir,
        producer_commit="a" * 40,
        producer_tree="b" * 40,
        fixture_path=fixture_path,
        prereg_path=prereg_path,
    )

    assert manifest.run_name == "run"
    assert manifest.fixture_sha256 == hashlib.sha256(b"fixture").hexdigest()
    assert manifest.prereg_sha256 == hashlib.sha256(b"prereg").hexdigest()
    assert manifest.fixture_binding == "PRODUCER_DECLARED_LEGACY_UNVERIFIED"
    assert tuple(entry.path for entry in manifest.artifacts) == (
        "models/A_PPO_ONLY/seed-0/model.zip",
        "terminal_receipt.json",
    )
    assert manifest.artifacts[0].sha256 == hashlib.sha256(b"model").hexdigest()
    assert len(manifest.evidence_manifest_sha256) == 64


def test_custody_manifest_rejects_preregistration_not_bound_by_receipt(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    receipt = (
        '{"status":"PRIMARY_COMPLETE","verdict":"NO_GO",'
        '"fresh_oos":"NOT_RUN_NO_READ","promotion_allowed":false,'
        f'"profitability_claim_allowed":false,"prereg_sha256":"{"a" * 64}"}}'
    )
    _ = (run_dir / "terminal_receipt.json").write_text(receipt, encoding="utf-8")
    fixture_path = tmp_path / "fixture.json"
    prereg_path = tmp_path / "prereg.json"
    _ = fixture_path.write_bytes(b"fixture")
    _ = prereg_path.write_bytes(b"prereg")

    with pytest.raises(ValueError, match="preregistration hash"):
        _ = build_custody_manifest(
            run_dir,
            producer_commit="a" * 40,
            producer_tree="b" * 40,
            fixture_path=fixture_path,
            prereg_path=prereg_path,
        )
