"""Tests for the factory run registry and preregistration-enforcing queue.

Cost assumption pinned at 23.0bp round trip throughout.
"""

import sqlite3

import pytest

from stom_rl.factory.experiment_queue import (
    QueueGuardError,
    enqueue_experiment,
    mark_done,
    mark_failed,
    mark_running,
    next_queued,
    queue_snapshot,
)
from stom_rl.factory.run_registry import (
    RegistryError,
    get_run,
    init_registry,
    lineage,
    list_runs,
    register_run,
    set_status,
)


def _registry(tmp_path):
    return tmp_path / "factory_registry.sqlite"


def _prereg(tmp_path, name="prereg.md"):
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    doc = docs / name
    doc.write_text("# prereg\n", encoding="utf-8")
    return f"docs/{name}"


def _enqueue(tmp_path, run_id, *, stage="smoke", parent_run=None, cost_bps=23.0):
    return enqueue_experiment(
        _registry(tmp_path),
        run_id=run_id,
        split_hash="splitabc",
        cost_bps=cost_bps,
        seed=7,
        stage=stage,
        prereg_doc=_prereg(tmp_path),
        parent_run=parent_run,
        repo_root=tmp_path,
    )


def test_init_registry_idempotent(tmp_path):
    path = _registry(tmp_path)
    init_registry(path)
    init_registry(path)
    row = register_run(
        path,
        run_id="r1",
        split_hash="s1",
        cost_bps=23.0,
        seed=0,
        stage="smoke",
        prereg_doc="docs/prereg.md",
    )
    assert row["status"] == "queued"
    assert row["verdict"] == ""


def test_enqueue_rejects_missing_prereg_doc(tmp_path):
    with pytest.raises(QueueGuardError, match="missing_prereg_doc"):
        enqueue_experiment(
            _registry(tmp_path),
            run_id="r1",
            split_hash="s1",
            cost_bps=23.0,
            seed=0,
            stage="smoke",
            prereg_doc="docs/does_not_exist.md",
            repo_root=tmp_path,
        )


def test_enqueue_rejects_empty_prereg_doc(tmp_path):
    with pytest.raises(QueueGuardError, match="missing_prereg_doc"):
        enqueue_experiment(
            _registry(tmp_path),
            run_id="r1",
            split_hash="s1",
            cost_bps=23.0,
            seed=0,
            stage="smoke",
            prereg_doc="",
            repo_root=tmp_path,
        )


def test_enqueue_rejects_non_23bp_cost(tmp_path):
    _prereg(tmp_path)
    with pytest.raises(QueueGuardError, match="cost_must_be_23bp"):
        _enqueue(tmp_path, "r1", cost_bps=25.0)


def test_enqueue_rejects_duplicate_run_id(tmp_path):
    _enqueue(tmp_path, "r1")
    with pytest.raises(QueueGuardError, match="duplicate_run_id"):
        _enqueue(tmp_path, "r1")


def test_enqueue_full_stage_requires_parent(tmp_path):
    with pytest.raises(QueueGuardError, match="missing_parent_lineage"):
        _enqueue(tmp_path, "r1", stage="full")
    with pytest.raises(QueueGuardError, match="missing_parent_lineage"):
        _enqueue(tmp_path, "r2", stage="walkforward", parent_run="ghost")
    _enqueue(tmp_path, "parent")
    row = _enqueue(tmp_path, "child", stage="full", parent_run="parent")
    assert row["parent_run"] == "parent"


def test_legal_lifecycle_records_verdict(tmp_path):
    path = _registry(tmp_path)
    _enqueue(tmp_path, "r1")
    assert next_queued(path)["run_id"] == "r1"
    assert mark_running(path, "r1")["status"] == "running"
    done = mark_done(path, "r1", verdict="NO-GO_CONTROL")
    assert done["status"] == "done"
    assert done["verdict"] == "NO-GO_CONTROL"
    assert next_queued(path) is None
    stored = get_run(path, "r1")
    assert stored["verdict"] == "NO-GO_CONTROL"


def test_failed_lifecycle(tmp_path):
    path = _registry(tmp_path)
    _enqueue(tmp_path, "r1")
    mark_running(path, "r1")
    failed = mark_failed(path, "r1", verdict="crash")
    assert failed["status"] == "failed"
    assert failed["verdict"] == "crash"


def test_illegal_transition_raises(tmp_path):
    path = _registry(tmp_path)
    _enqueue(tmp_path, "r1")
    with pytest.raises(RegistryError, match="illegal_transition"):
        set_status(path, "r1", "done")
    with pytest.raises(RegistryError, match="unknown_run_id"):
        set_status(path, "ghost", "running")


def test_lineage_chain_root_first(tmp_path):
    path = _registry(tmp_path)
    _enqueue(tmp_path, "root")
    _enqueue(tmp_path, "mid", stage="full", parent_run="root")
    _enqueue(tmp_path, "leaf", stage="walkforward", parent_run="mid")
    chain = lineage(path, "leaf")
    assert [row["run_id"] for row in chain] == ["root", "mid", "leaf"]


def test_lineage_cycle_safe(tmp_path):
    path = _registry(tmp_path)
    register_run(path, run_id="a", split_hash="s", cost_bps=23.0, seed=0, stage="smoke", prereg_doc="docs/p.md", parent_run="b")
    register_run(path, run_id="b", split_hash="s", cost_bps=23.0, seed=0, stage="smoke", prereg_doc="docs/p.md", parent_run="a")
    chain = lineage(path, "a")
    assert {row["run_id"] for row in chain} == {"a", "b"}
    assert len(chain) == 2


def test_list_runs_filters_by_status(tmp_path):
    path = _registry(tmp_path)
    _enqueue(tmp_path, "r1")
    _enqueue(tmp_path, "r2")
    mark_running(path, "r1")
    queued = list_runs(path, status="queued")
    assert [row["run_id"] for row in queued] == ["r2"]
    running = list_runs(path, status="running")
    assert [row["run_id"] for row in running] == ["r1"]
    smoke = list_runs(path, stage="smoke")
    assert len(smoke) == 2


def test_queue_snapshot_counts(tmp_path):
    path = _registry(tmp_path)
    _enqueue(tmp_path, "r1")
    _enqueue(tmp_path, "r2")
    _enqueue(tmp_path, "r3")
    mark_running(path, "r1")
    mark_done(path, "r1", verdict="INCONCLUSIVE")
    mark_running(path, "r2")
    snap = queue_snapshot(path)
    assert snap["counts_by_status"] == {"queued": 1, "running": 1, "done": 1, "failed": 0}
    assert len(snap["latest_runs"]) == 3
    assert snap["registry_path"] == str(path)
    assert "read-only" in snap["read_only_dashboard_note"]


def test_registry_status_check_constraint(tmp_path):
    path = _registry(tmp_path)
    init_registry(path)
    with sqlite3.connect(str(path)) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO runs (run_id, cost_bps, stage, prereg_doc, status)"
                " VALUES ('x', 23.0, 'smoke', 'docs/p.md', 'bogus')"
            )
