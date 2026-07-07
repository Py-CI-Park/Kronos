"""Tests for the additive experiment-tracking backbone (P8).

Covers:
* Clean imports of both new modules.
* ``experiment_tracking.is_enabled()`` defaults to False and ``log_run`` is a
  no-op that never raises when disabled.
* With ``KRONOS_MLFLOW_ENABLED=1`` and a temp file-store, ``log_run`` writes
  without error and returns a run id (never polluting ``artifacts/mlruns``).
* ``gen_rliable_stats.main`` handles the no/insufficient-data path gracefully
  (exit 0 + clear message) and produces a valid JSON when enough runs exist.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _import_experiment_tracking():
    return importlib.import_module("stom_rl.experiment_tracking")


def _import_gen_rliable():
    return importlib.import_module("gen_rliable_stats")


# --------------------------------------------------------------------------- #
# Import + graceful-degradation contract
# --------------------------------------------------------------------------- #


def test_both_modules_import_cleanly():
    et = _import_experiment_tracking()
    gen = _import_gen_rliable()
    assert hasattr(et, "is_enabled")
    assert hasattr(et, "log_run")
    assert hasattr(et, "tracking_uri")
    assert callable(gen.main)


def test_is_enabled_false_by_default(monkeypatch):
    et = _import_experiment_tracking()
    monkeypatch.delenv(et.ENABLED_ENV_VAR, raising=False)
    assert et.is_enabled() is False


def test_log_run_is_silent_noop_when_disabled(monkeypatch):
    et = _import_experiment_tracking()
    monkeypatch.delenv(et.ENABLED_ENV_VAR, raising=False)
    # Must not raise and must return None when disabled.
    result = et.log_run(
        "disabled_run",
        params={"seed": 100},
        metrics={"final_equity_mult": 1.05},
        tags={"research_only": "true"},
    )
    assert result is None


def test_tracked_run_yields_none_when_disabled(monkeypatch):
    et = _import_experiment_tracking()
    monkeypatch.delenv(et.ENABLED_ENV_VAR, raising=False)
    with et.tracked_run("disabled_ctx", params={"seed": 1}) as run:
        assert run is None


def test_tracking_uri_is_local_file(monkeypatch, tmp_path):
    et = _import_experiment_tracking()
    monkeypatch.delenv(et.DIR_ENV_VAR, raising=False)
    # Default resolves under the repo's artifacts/mlruns and is a file: URI.
    default_uri = et.tracking_uri()
    assert default_uri.startswith("file:")
    assert "mlruns" in default_uri
    assert "://" in default_uri  # never a bare remote host / http scheme
    assert not default_uri.startswith("http")
    # Override resolves under the provided temp dir (self-host, no egress).
    override_uri = et.tracking_uri(base_dir=tmp_path)
    assert override_uri.startswith("file:")
    assert (tmp_path).as_uri() in override_uri or str(tmp_path.name) in override_uri


# --------------------------------------------------------------------------- #
# Enabled path — writes to a temp file store, never pollutes artifacts/mlruns
# --------------------------------------------------------------------------- #


def test_log_run_enabled_writes_to_temp_store(monkeypatch, tmp_path):
    et = _import_experiment_tracking()
    pytest.importorskip("mlflow")

    store = tmp_path / "mlruns"
    monkeypatch.setenv(et.ENABLED_ENV_VAR, "1")
    monkeypatch.setenv(et.DIR_ENV_VAR, str(store))

    assert et.is_enabled() is True

    run_id = et.log_run(
        "enabled_run",
        params={"seed": 100, "cost_bps": 23.0},
        metrics={"final_equity_mult": 1.08, "nan_metric": float("nan")},
        tags={"stage": "smoke", "research_only": "true"},
    )
    assert isinstance(run_id, str) and run_id

    # The local file store must have been created under the temp dir only.
    assert store.exists()
    # The canonical artifacts/mlruns must NOT be touched by this test.
    repo_store = REPO_ROOT / "artifacts" / "mlruns"
    # (It may pre-exist from real usage; assert our run id is not under it.)
    if repo_store.exists():
        assert run_id not in {p.name for p in repo_store.rglob("*")}


# --------------------------------------------------------------------------- #
# gen_rliable_stats — insufficient and sufficient data paths
# --------------------------------------------------------------------------- #


def test_gen_rliable_insufficient_data_exits_zero(tmp_path, capsys):
    gen = _import_gen_rliable()
    empty_glob = str(tmp_path / "*" / "rl_live_events.jsonl")
    code = gen.main(
        [
            "--events-glob",
            empty_glob,
            "--out-dir",
            str(tmp_path / "out"),
            "--registry",
            str(tmp_path / "missing_registry.sqlite"),
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "insufficient runs" in out.lower()
    assert "RESEARCH_ONLY" in out
    # No output JSON should be written on the insufficient path.
    assert not (tmp_path / "out" / "rl_runs_rliable.json").exists()


def _write_events(path: Path, run_id: str, algorithm: str, equities):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for step, equity in enumerate(equities, start=1):
        lines.append(
            json.dumps(
                {
                    "run_id": run_id,
                    "algorithm": algorithm,
                    "phase": "eval",
                    "global_step": step,
                    "equity": equity,
                    "schema_version": "stom_rl_live_event.v1",
                }
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_gen_rliable_sufficient_data_writes_json(tmp_path, capsys):
    gen = _import_gen_rliable()
    runs_dir = tmp_path / "runs"
    # Two runs of the same algorithm => a 2-seed score matrix.
    _write_events(runs_dir / "runA" / "rl_live_events.jsonl", "runA", "algoX", [1.0, 1.10])
    _write_events(runs_dir / "runB" / "rl_live_events.jsonl", "runB", "algoX", [1.0, 0.95])
    _write_events(runs_dir / "runC" / "rl_live_events.jsonl", "runC", "algoX", [1.0, 1.05])

    out_dir = tmp_path / "out"
    code = gen.main(
        [
            "--events-glob",
            str(runs_dir / "*" / "rl_live_events.jsonl"),
            "--out-dir",
            str(out_dir),
            "--name",
            "unit",
            "--min-seeds",
            "2",
            "--reps",
            "200",
            "--registry",
            str(tmp_path / "missing_registry.sqlite"),
        ]
    )
    assert code == 0

    out_path = out_dir / "unit_rliable.json"
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["research_only"] is True
    assert "algoX" in payload["algorithms"]
    meta = payload["metadata"]["algoX"]
    assert meta["seed_count"] == 3
    assert set(meta["run_ids"]) == {"runA", "runB", "runC"}
    # rliable is installed in this environment; aggregates should be present.
    assert "algoX" in payload["aggregates"]
    for metric in ("median", "iqm", "mean", "optimality_gap"):
        entry = payload["aggregates"]["algoX"][metric]
        assert "point" in entry and "ci_lower" in entry and "ci_upper" in entry
    out = capsys.readouterr().out
    assert "RESEARCH_ONLY" in out
