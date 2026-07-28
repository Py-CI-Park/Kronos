import hashlib
import json

from webui import v6_platform_api


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def fixture(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    custody_root = tmp_path / "custody"
    run_dir = tmp_path / "runs" / "v8-m3e" / "train-1"
    prereg = docs / "kronos_v8_prereg_m3e_test.json"
    write_json(prereg, {"schema_version": "kronos_v8_prereg.v1", "prereg_id": "M3E", "status": "FROZEN"})
    run = {
        "schema_version": "kronos_v8_m3e_validation_run.v1",
        "trainer_version": "kronos_v8_m3e_contextual_bandit.v1",
        "prereg": {"id": "M3E", "sha256": sha(prereg)},
        "custody_uid": "custody-1",
        "seeds": [0, 1, 2, 3, 4],
        "members": [{"seed": seed} for seed in range(5)],
        "policy": {
            "price_basis": "EXACT_15_20_BAR_CLOSE_PROXY",
            "official_close": False,
            "primary_cost_rate": 0.0023,
        },
        "verdict": {"value": "NO_GO"},
        "test": {"state": "NOT_RUN"},
        "false_research_locks": dict(v6_platform_api.SIX_FALSE_LOCKS),
    }
    run_path = run_dir / "run_manifest.json"
    write_json(run_path, run)
    custody_path = custody_root / "custody-1" / "public" / "train_validation_manifest.json"
    write_json(custody_path, {
        "schema_version": "kronos_v8_daily_h1_custody.v1",
        "custody_uid": "custody-1",
        "public_artifact": {"sha256": "a" * 64},
    })
    report = {
        "schema_version": "kronos_v8_m3e_report.v1",
        "run_manifest_sha256": sha(run_path),
        "prereg_sha256": sha(prereg),
        "public_custody_manifest_sha256": sha(custody_path),
        "public_custody_sha256": "a" * 64,
        "test_state": "NOT_RUN",
        "verdict": "NO_GO",
    }
    monkeypatch.setattr(v6_platform_api, "DOCS_ROOT", docs)
    monkeypatch.setattr(v6_platform_api, "PREREG_GLOBS", ("kronos_v*_prereg_*.json",))
    monkeypatch.setattr(v6_platform_api, "M3E_CUSTODY_ROOT", custody_root)
    return run_dir, report, custody_path


def test_m3e_report_chain_is_verified_and_tamper_fails_closed(tmp_path, monkeypatch):
    run_dir, report, custody_path = fixture(tmp_path, monkeypatch)
    assert v6_platform_api._report_chain(run_dir, report) == ("CHAIN_OK", [])

    custody = json.loads(custody_path.read_text(encoding="utf-8"))
    custody["public_artifact"]["sha256"] = "b" * 64
    write_json(custody_path, custody)
    state, reasons = v6_platform_api._report_chain(run_dir, report)
    assert state == "CHAIN_INVALID"
    assert "PUBLIC_CUSTODY_MANIFEST_SHA_MISMATCH" in reasons
    assert "PUBLIC_CUSTODY_SHA_MISMATCH" in reasons

def test_m3e_report_verdict_and_run_identity_contradictions_fail_closed(tmp_path, monkeypatch):
    run_dir, report, _ = fixture(tmp_path, monkeypatch)

    report["verdict"] = "GO"
    state, reasons = v6_platform_api._report_chain(run_dir, report)
    assert state == "CHAIN_INVALID"
    assert "REPORT_VERDICT_MISMATCH" in reasons
    assert "REPORT_RUN_VERDICT_CONTRADICTION" in reasons

    run_path = run_dir / "run_manifest.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["trainer_version"] = "kronos_v8_m3e_other.v1"
    write_json(run_path, run)
    report["verdict"] = "NO_GO"
    state, reasons = v6_platform_api._report_chain(run_dir, report)
    assert state == "CHAIN_INVALID"
    assert "M3E_ALGORITHM_MISMATCH" in reasons

def test_m3e_run_states_distinguish_training_validation_and_untouched_test():
    states = v6_platform_api._run_states({
        "schema_version": "kronos_v8_m3e_validation_run.v1",
        "members": [{}, {}, {}, {}, {}],
        "ensemble": {"metrics": {"nav": 52_000_000}},
        "jackknives": {str(seed): {} for seed in range(5)},
        "test": {"state": "NOT_RUN"},
    })
    assert states == {
        "training_state": "COMPLETE",
        "validation_state": "REUSED_VALIDATION_COMPLETE",
        "test_state": "NOT_RUN",
        "evaluation_state": "TEST_NOT_RUN",
    }
