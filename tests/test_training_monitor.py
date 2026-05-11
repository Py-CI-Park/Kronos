
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEBUI_DIR = REPO_ROOT / "webui"
if str(WEBUI_DIR) not in sys.path:
    sys.path.insert(0, str(WEBUI_DIR))

import training_monitor  # noqa: E402


def _write_progress(run_dir: Path, stage: str = "predictor") -> None:
    logs = run_dir / "logs"
    logs.mkdir(parents=True)
    stdout = logs / f"{stage}.stdout.log"
    stdout.write_text("line 1\nline 2\n", encoding="utf-8")
    progress = {
        "schema_version": 1,
        "created_at": "2026-05-11T00:00:00Z",
        "updated_at": "2026-05-11T00:01:00Z",
        "status": "running",
        "run_name": run_dir.name,
        "horizon": 60,
        "mode": "full",
        "train_stage": stage,
        "stage": {"index": 2, "count": 2, "name": stage, "percent": 25.0, "overall_percent": 62.5},
        "progress": {"epoch": 1, "epochs": 1, "step": 25, "total_steps": 100},
        "metrics": {"last_loss": 0.5, "last_validation_loss": None, "best_val_loss": None},
        "timing": {"elapsed_seconds": 10, "eta_seconds": 30, "samples_per_second": 10.0},
        "paths": {"stdout_log": str(stdout), "stderr_log": str(logs / f"{stage}.stderr.log")},
        "last_line": "latest",
    }
    (logs / f"{stage}.progress.json").write_text(json.dumps(progress), encoding="utf-8")


def test_training_monitor_lists_status_and_tails_logs(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    run_dir = output_root / "unit_run"
    _write_progress(run_dir)
    monkeypatch.setattr(training_monitor, "OUTPUT_ROOTS", [output_root])

    runs = training_monitor.list_training_runs()
    status = training_monitor.load_training_status("unit_run")
    tail = training_monitor.tail_training_log("unit_run", stage="predictor", lines=1)

    assert runs[0]["name"] == "unit_run"
    assert runs[0]["status"] == "running"
    assert status["overall_percent"] == 62.5
    assert status["latest_stage"]["train_stage"] == "predictor"
    assert tail["lines"] == ["line 2"]


def test_training_monitor_rejects_path_traversal(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    output_root.mkdir()
    monkeypatch.setattr(training_monitor, "OUTPUT_ROOTS", [output_root])

    try:
        training_monitor.resolve_run_dir("..\\secret")
    except ValueError as exc:
        assert "direct" in str(exc)
    else:
        raise AssertionError("path traversal run name was accepted")


def test_query_gpu_status_parses_nvidia_smi(monkeypatch):
    class Completed:
        returncode = 0
        stdout = "0, NVIDIA GeForce RTX 4080 SUPER, 75, 9000, 16376, 250.5, 320.0, 61\n"
        stderr = ""

    monkeypatch.setattr(training_monitor.subprocess, "run", lambda *args, **kwargs: Completed())

    status = training_monitor.query_gpu_status()

    assert status["available"] is True
    assert status["gpus"][0]["name"] == "NVIDIA GeForce RTX 4080 SUPER"
    assert status["gpus"][0]["utilization_gpu_percent"] == 75.0
    assert status["total_power_draw_watts"] == 250.5


def test_training_dashboard_routes_register(monkeypatch):
    import app as webapp  # noqa: E402

    monkeypatch.setattr(webapp, "list_training_runs", lambda limit=50: [])
    monkeypatch.setattr(webapp, "load_training_status", lambda run_name=None: {"run_name": "unit", "stages": []})
    monkeypatch.setattr(webapp, "tail_training_log", lambda run_name=None, stage=None, lines=200: {"lines": [], "text": ""})
    monkeypatch.setattr(webapp, "query_gpu_status", lambda: {"available": False, "gpus": []})

    client = webapp.app.test_client()

    training_html = client.get("/training").get_data(as_text=True)
    index_html = client.get("/").get_data(as_text=True)
    stom_html = client.get("/stom").get_data(as_text=True)

    assert "autoRefreshEnabled" in training_html
    assert "refreshIntervalSeconds" in training_html
    assert "trainingInlinePanel" in index_html
    assert "stomTrainingStrip" in stom_html
    assert client.get("/api/training/runs").get_json() == {"runs": []}
    assert client.get("/api/training/status").get_json()["run_name"] == "unit"
    assert client.get("/api/training/logs").get_json()["text"] == ""
    assert client.get("/api/training/gpu").get_json()["available"] is False


def test_training_dashboard_refresh_interval_is_configurable_and_clamped(monkeypatch):
    import app as webapp  # noqa: E402

    monkeypatch.setattr(webapp, "list_training_runs", lambda limit=50: [])
    monkeypatch.setattr(webapp, "load_training_status", lambda run_name=None: {"run_name": "unit", "stages": []})
    monkeypatch.setattr(webapp, "tail_training_log", lambda run_name=None, stage=None, lines=200: {"lines": [], "text": ""})
    monkeypatch.setattr(webapp, "query_gpu_status", lambda: {"available": False, "gpus": []})

    client = webapp.app.test_client()

    too_fast = client.get("/training?refresh_interval=1").get_data(as_text=True)
    custom = client.get("/training?refresh_interval=17").get_data(as_text=True)
    too_slow = client.get("/training?refresh_interval=99999").get_data(as_text=True)
    index_custom = client.get("/?refresh_interval=11").get_data(as_text=True)
    stom_custom = client.get("/stom?refresh_interval=13").get_data(as_text=True)

    assert 'data-default-refresh-seconds="2"' in too_fast
    assert 'value="17"' in custom
    assert 'data-default-refresh-seconds="3600"' in too_slow
    assert 'data-default-refresh-seconds="11"' in index_custom
    assert 'data-default-refresh-seconds="13"' in stom_custom
