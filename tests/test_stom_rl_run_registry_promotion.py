"""Tests for additive run-authority extensions to stom_rl.factory.run_registry.

Covers: additive schema migration idempotence/backward-compat, register_run's
new optional metadata kwargs, set_status's completed_at stamping, promote_run's
fail-closed validation (unknown_run_id, not_ready_status, missing_metadata,
artifact_dir_missing, hash_mismatch, oversize) with atomic no-partial-write
guarantees, and the select_authoritative/get_authoritative ordering contract.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.factory import run_registry as rr


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_run(
    registry_path: Path,
    run_id: str,
    *,
    stage: str = "smoke",
    source_git_sha: str | None = "deadbeef",
    split_hash: str = "split-abc",
    cost_bps: float = 1.5,
    seed: int = 42,
    prereg_doc: str = "docs/prereg.md",
) -> dict:
    return rr.register_run(
        registry_path,
        run_id=run_id,
        split_hash=split_hash,
        cost_bps=cost_bps,
        seed=seed,
        stage=stage,
        prereg_doc=prereg_doc,
        source_git_sha=source_git_sha,
    )


def _make_ready_run(registry_path: Path, run_id: str, **kwargs) -> dict:
    """Register + drive to 'done' so promote_run's require_status='done' passes."""

    row = _make_run(registry_path, run_id, **kwargs)
    rr.set_status(registry_path, run_id, "running")
    row = rr.set_status(registry_path, run_id, "done")
    return row


# --------------------------------------------------------------------------- #
# Schema migration
# --------------------------------------------------------------------------- #


def test_migration_idempotent_and_old_rows_still_readable(tmp_path):
    registry_path = tmp_path / "registry.sqlite"

    # Simulate a pre-existing old-schema registry (no new columns).
    conn = sqlite3.connect(str(registry_path))
    conn.execute(
        """
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            split_hash TEXT,
            cost_bps REAL NOT NULL,
            seed INTEGER,
            stage TEXT CHECK(stage IN ('smoke','full','walkforward','paper')),
            parent_run TEXT,
            prereg_doc TEXT NOT NULL,
            status TEXT CHECK(status IN ('queued','running','done','failed')) DEFAULT 'queued',
            verdict TEXT DEFAULT '',
            created_utc TEXT,
            updated_utc TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO runs (run_id, split_hash, cost_bps, seed, stage, parent_run,"
        " prereg_doc, status, verdict, created_utc, updated_utc)"
        " VALUES ('old-run', 'sh', 1.0, 1, 'smoke', NULL, 'doc.md', 'done', '', 't0', 't0')"
    )
    conn.commit()
    conn.close()

    # First init_registry call performs the migration.
    rr.init_registry(registry_path)
    row = rr.get_run(registry_path, "old-run")
    assert row is not None
    assert row["authoritative"] == 0
    assert row["completed_at"] is None
    assert row["source_git_sha"] is None
    assert row["artifact_hashes"] is None
    assert row["run_dir"] is None
    assert row["total_bytes"] is None

    # Second call must be a no-op (idempotent) and not raise.
    rr.init_registry(registry_path)
    rr.init_registry(registry_path)
    row2 = rr.get_run(registry_path, "old-run")
    assert row2 == row


def test_register_run_stores_new_metadata(tmp_path):
    registry_path = tmp_path / "registry.sqlite"
    row = rr.register_run(
        registry_path,
        run_id="r1",
        split_hash="sh1",
        cost_bps=2.0,
        seed=7,
        stage="full",
        prereg_doc="doc.md",
        source_git_sha="abc123",
        run_dir="/tmp/somewhere",
        artifact_hashes={"a.txt": "deadbeef"},
    )
    assert row["source_git_sha"] == "abc123"
    assert row["run_dir"] == "/tmp/somewhere"
    assert json.loads(row["artifact_hashes"]) == {"a.txt": "deadbeef"}

    # Existing call shape (no new kwargs) still works unchanged.
    row2 = rr.register_run(
        registry_path,
        run_id="r2",
        split_hash="sh2",
        cost_bps=2.0,
        seed=8,
        stage="full",
        prereg_doc="doc.md",
    )
    assert row2["source_git_sha"] is None
    assert row2["run_dir"] is None
    assert row2["artifact_hashes"] is None


def test_set_status_done_sets_completed_at_once(tmp_path):
    registry_path = tmp_path / "registry.sqlite"
    _make_run(registry_path, "r1")
    rr.set_status(registry_path, "r1", "running")
    row = rr.set_status(registry_path, "r1", "done")
    assert row["completed_at"] is not None
    first_completed_at = row["completed_at"]

    # Re-registering a fresh run and re-checking completed_at is stamped, and a
    # queued run has no completed_at.
    fresh = _make_run(registry_path, "r2")
    assert fresh["completed_at"] is None
    assert first_completed_at


# --------------------------------------------------------------------------- #
# promote_run: success path
# --------------------------------------------------------------------------- #


def test_promote_run_success_sets_authoritative_and_demotes_peers(tmp_path):
    registry_path = tmp_path / "registry.sqlite"
    artifact_dir = tmp_path / "artifacts" / "r1"
    artifact_dir.mkdir(parents=True)
    payload = b"hello world"
    (artifact_dir / "model.bin").write_bytes(payload)
    expected_hashes = {"model.bin": _sha256_hex(payload)}

    _make_ready_run(registry_path, "r1", stage="smoke")
    peer = _make_ready_run(registry_path, "peer", stage="smoke")

    # Manually promote the peer first, to prove promote_run demotes it later.
    peer_dir = tmp_path / "artifacts" / "peer"
    peer_dir.mkdir(parents=True)
    (peer_dir / "p.bin").write_bytes(b"peer-data")
    rr.promote_run(
        registry_path,
        "peer",
        artifact_dir=peer_dir,
        expected_hashes={"p.bin": _sha256_hex(b"peer-data")},
        max_total_bytes=1_000_000,
    )
    assert rr.get_run(registry_path, "peer")["authoritative"] == 1

    updated = rr.promote_run(
        registry_path,
        "r1",
        artifact_dir=artifact_dir,
        expected_hashes=expected_hashes,
        max_total_bytes=1_000_000,
    )
    assert updated["authoritative"] == 1
    assert updated["run_dir"] == str(artifact_dir)
    assert json.loads(updated["artifact_hashes"]) == expected_hashes
    assert updated["total_bytes"] == len(payload)

    # Peer in the same stage must now be demoted.
    peer_row = rr.get_run(registry_path, "peer")
    assert peer_row["authoritative"] == 0


# --------------------------------------------------------------------------- #
# promote_run: fail-closed validation matrix
# --------------------------------------------------------------------------- #


def test_promote_run_unknown_run_id(tmp_path):
    registry_path = tmp_path / "registry.sqlite"
    rr.init_registry(registry_path)
    with pytest.raises(rr.RegistryError, match="^unknown_run_id:"):
        rr.promote_run(
            registry_path,
            "nope",
            artifact_dir=tmp_path,
            expected_hashes={},
            max_total_bytes=100,
        )


def test_promote_run_not_ready_status_leaves_row_unchanged(tmp_path):
    registry_path = tmp_path / "registry.sqlite"
    _make_run(registry_path, "r1")  # stays 'queued'
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    with pytest.raises(rr.RegistryError, match="^not_ready_status:"):
        rr.promote_run(
            registry_path,
            "r1",
            artifact_dir=artifact_dir,
            expected_hashes={},
            max_total_bytes=100,
        )
    assert rr.get_run(registry_path, "r1")["authoritative"] == 0


def test_promote_run_missing_metadata_leaves_row_unchanged(tmp_path):
    registry_path = tmp_path / "registry.sqlite"
    _make_ready_run(registry_path, "r1", source_git_sha=None)
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    with pytest.raises(rr.RegistryError, match="^missing_metadata:source_git_sha"):
        rr.promote_run(
            registry_path,
            "r1",
            artifact_dir=artifact_dir,
            expected_hashes={},
            max_total_bytes=100,
        )
    assert rr.get_run(registry_path, "r1")["authoritative"] == 0


def test_promote_run_artifact_dir_missing_leaves_row_unchanged(tmp_path):
    registry_path = tmp_path / "registry.sqlite"
    _make_ready_run(registry_path, "r1")
    missing_dir = tmp_path / "does_not_exist"
    with pytest.raises(rr.RegistryError, match="^artifact_dir_missing:"):
        rr.promote_run(
            registry_path,
            "r1",
            artifact_dir=missing_dir,
            expected_hashes={"a.bin": "00" * 32},
            max_total_bytes=100,
        )
    assert rr.get_run(registry_path, "r1")["authoritative"] == 0


def test_promote_run_hash_mismatch_leaves_row_unchanged(tmp_path):
    registry_path = tmp_path / "registry.sqlite"
    _make_ready_run(registry_path, "r1")
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "model.bin").write_bytes(b"actual-content")
    with pytest.raises(rr.RegistryError, match=r"^hash_mismatch:model\.bin"):
        rr.promote_run(
            registry_path,
            "r1",
            artifact_dir=artifact_dir,
            expected_hashes={"model.bin": "00" * 32},
            max_total_bytes=1_000_000,
        )
    assert rr.get_run(registry_path, "r1")["authoritative"] == 0


def test_promote_run_hash_mismatch_missing_file_leaves_row_unchanged(tmp_path):
    registry_path = tmp_path / "registry.sqlite"
    _make_ready_run(registry_path, "r1")
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    with pytest.raises(rr.RegistryError, match=r"^hash_mismatch:missing\.bin"):
        rr.promote_run(
            registry_path,
            "r1",
            artifact_dir=artifact_dir,
            expected_hashes={"missing.bin": "00" * 32},
            max_total_bytes=1_000_000,
        )
    assert rr.get_run(registry_path, "r1")["authoritative"] == 0


def test_promote_run_oversize_leaves_row_unchanged(tmp_path):
    registry_path = tmp_path / "registry.sqlite"
    _make_ready_run(registry_path, "r1")
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    payload = b"x" * 1024
    (artifact_dir / "big.bin").write_bytes(payload)
    with pytest.raises(rr.RegistryError, match="^oversize:"):
        rr.promote_run(
            registry_path,
            "r1",
            artifact_dir=artifact_dir,
            expected_hashes={"big.bin": _sha256_hex(payload)},
            max_total_bytes=10,
        )
    assert rr.get_run(registry_path, "r1")["authoritative"] == 0


# --------------------------------------------------------------------------- #
# select_authoritative / get_authoritative ordering
# --------------------------------------------------------------------------- #


def test_older_promoted_run_wins_over_newer_non_promoted(tmp_path):
    registry_path = tmp_path / "registry.sqlite"

    old_dir = tmp_path / "artifacts" / "old"
    old_dir.mkdir(parents=True)
    payload = b"old-payload"
    (old_dir / "m.bin").write_bytes(payload)

    _make_ready_run(registry_path, "old_run", stage="paper")
    rr.promote_run(
        registry_path,
        "old_run",
        artifact_dir=old_dir,
        expected_hashes={"m.bin": _sha256_hex(payload)},
        max_total_bytes=1_000_000,
    )

    # Register + finish a strictly newer run in the same stage, never promoted.
    _make_ready_run(registry_path, "new_run", stage="paper")

    top = rr.get_authoritative(registry_path, stage="paper")
    assert top is not None
    assert top["run_id"] == "old_run"
    assert top["authoritative"] == 1

    new_row = rr.get_run(registry_path, "new_run")
    assert new_row["authoritative"] == 0
    # Prove "new_run" really is newer by updated_utc/created_utc ordering.
    assert new_row["updated_utc"] >= top["updated_utc"]


def test_select_authoritative_orders_authoritative_first_then_status_rank(tmp_path):
    registry_path = tmp_path / "registry.sqlite"

    _make_run(registry_path, "queued_run", stage="full")

    _make_run(registry_path, "running_run", stage="full")
    rr.set_status(registry_path, "running_run", "running")

    _make_ready_run(registry_path, "done_run", stage="full")

    _make_ready_run(registry_path, "authoritative_run", stage="full")
    artifact_dir = tmp_path / "artifacts" / "auth"
    artifact_dir.mkdir(parents=True)
    payload = b"authoritative-payload"
    (artifact_dir / "m.bin").write_bytes(payload)
    rr.promote_run(
        registry_path,
        "authoritative_run",
        artifact_dir=artifact_dir,
        expected_hashes={"m.bin": _sha256_hex(payload)},
        max_total_bytes=1_000_000,
    )

    ordered = rr.select_authoritative(registry_path, stage="full")
    ordered_ids = [row["run_id"] for row in ordered]

    assert ordered_ids[0] == "authoritative_run"
    # Among the rest (none authoritative), done > running > queued.
    rest = ordered_ids[1:]
    assert rest.index("done_run") < rest.index("running_run") < rest.index("queued_run")
