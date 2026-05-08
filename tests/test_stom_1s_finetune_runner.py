import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FINETUNE_DIR = PROJECT_ROOT / "finetune"
if str(FINETUNE_DIR) not in sys.path:
    sys.path.insert(0, str(FINETUNE_DIR))

from run_stom_1s_finetune import build_run, execute_run, parse_args, sample_stage_budget  # noqa: E402
from model_source import resolve_model_source  # noqa: E402


def test_resolve_model_source_falls_back_to_hf_identifier_for_missing_local_path():
    source = resolve_model_source(
        "outputs/missing/tokenizer/checkpoints/best_model",
        "NeoQuasar/Kronos-Tokenizer-base",
        "Tokenizer",
    )

    assert source == "NeoQuasar/Kronos-Tokenizer-base"


def test_runner_dry_run_records_reproducible_env(tmp_path):
    dataset_dir = tmp_path / "processed_datasets"
    dataset_dir.mkdir()
    (dataset_dir / "train_data.pkl").write_bytes(b"not loaded in dry-run")
    (dataset_dir / "val_data.pkl").write_bytes(b"not loaded in dry-run")

    args = parse_args(
        [
            "--horizon",
            "30",
            "--mode",
            "smoke",
            "--dataset-dir",
            str(dataset_dir),
            "--output-root",
            str(tmp_path / "outputs"),
            "--run-name",
            "unit_smoke",
            "--dry-run",
        ]
    )
    spec = build_run(30, args, "smoke")
    result = execute_run(spec, dry_run=True)

    manifest = Path(result["manifest_path"])
    assert manifest.exists()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["status"] == "dry_run"
    assert payload["env_overrides"]["KRONOS_DATASET_PATH"] == str(dataset_dir.resolve())
    assert payload["env_overrides"]["KRONOS_PREDICT_WINDOW"] == "30"
    assert payload["env_overrides"]["KRONOS_USE_COMET"] == "0"
    assert payload["env_overrides"]["KRONOS_DDP_BACKEND"] == "gloo"
    assert payload["env_overrides"]["USE_LIBUV"] == "0"
    assert payload["env_overrides"]["WORLD_SIZE"] == "1"
    assert payload["env_overrides"]["KRONOS_DISABLE_DDP"] == "1"
    assert payload["command"][-1].endswith("train_predictor.py")


def test_sample_stage_sets_staged_full_training_budget(tmp_path):
    dataset_dir = tmp_path / "processed_datasets"
    dataset_dir.mkdir()
    (dataset_dir / "train_data.pkl").write_bytes(b"not loaded in dry-run")
    (dataset_dir / "val_data.pkl").write_bytes(b"not loaded in dry-run")

    args = parse_args(
        [
            "--horizon",
            "60",
            "--mode",
            "full",
            "--sample-stage",
            "expand_200k",
            "--dataset-dir",
            str(dataset_dir),
            "--output-root",
            str(tmp_path / "outputs"),
            "--dry-run",
        ]
    )
    spec = build_run(60, args, "full")

    assert spec["sample_stage"] == "expand_200k"
    assert spec["run_name"] == "stom_1s_grid_pred60_expand_200k"
    assert spec["target_train_samples"] == 200_000
    assert spec["target_val_samples"] == 40_000
    assert spec["env"]["KRONOS_N_TRAIN_ITER"] == "200000"
    assert spec["env"]["KRONOS_N_VAL_ITER"] == "40000"


def test_full_window_sample_stage_uses_known_full_sample_pool():
    assert sample_stage_budget("full_window", 30) == {"train": 75_277_195, "val": 16_275_307}
    assert sample_stage_budget("full_window", 60) == {"train": 73_718_875, "val": 15_938_107}
