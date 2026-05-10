"""Launch reproducible STOM 1-second Kronos QlibDataset fine-tuning runs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT_ROOT = PROJECT_ROOT / "finetune" / "qlib_exports"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "finetune" / "outputs"
DEFAULT_TOKENIZER = "NeoQuasar/Kronos-Tokenizer-base"
DEFAULT_PREDICTOR = "NeoQuasar/Kronos-small"
STOM_1S_FULL_SAMPLE_POOLS = {
    30: {"train": 75_277_195, "val": 16_275_307},
    60: {"train": 73_718_875, "val": 15_938_107},
}
SAMPLE_STAGE_PRESETS = {
    "budget_20k": {"train": 20_000, "val": 4_000},
    "expand_200k": {"train": 200_000, "val": 40_000},
    "expand_1m": {"train": 1_000_000, "val": 100_000},
    "expand_5m": {"train": 5_000_000, "val": 250_000},
    "full_window": None,
}
TRAIN_STAGES = {"tokenizer", "predictor", "both"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mode_default(value: Optional[int], mode: str, smoke: int, stage: int, full: int) -> int:
    if value is not None:
        return value
    if mode == "smoke":
        return smoke
    if mode == "stage":
        return stage
    return full


def _tail(text: str, limit: int = 8000) -> str:
    return text[-limit:] if len(text) > limit else text


def sample_stage_budget(stage: Optional[str], horizon: int) -> Optional[Dict[str, int]]:
    if not stage:
        return None
    if stage == "full_window":
        return dict(STOM_1S_FULL_SAMPLE_POOLS[horizon])
    preset = SAMPLE_STAGE_PRESETS.get(stage)
    if preset is None:
        raise ValueError(f"Unknown sample stage: {stage}")
    return dict(preset)


def build_run(
    horizon: int,
    args: argparse.Namespace,
    mode: str,
    train_stage: Optional[str] = None,
) -> Dict[str, Any]:
    dataset_dir = Path(args.dataset_dir) if args.dataset_dir else (
        DEFAULT_EXPORT_ROOT / f"stom_1s_grid_pred{horizon}_full" / "processed_datasets"
    )
    dataset_dir = dataset_dir.resolve()
    if not dataset_dir.exists():
        raise FileNotFoundError(f"processed_datasets not found: {dataset_dir}")
    for required in ["train_data.pkl", "val_data.pkl"]:
        if not (dataset_dir / required).exists():
            raise FileNotFoundError(f"required dataset file missing: {dataset_dir / required}")

    sample_budget = sample_stage_budget(args.sample_stage, horizon)
    run_suffix = args.sample_stage or mode
    run_name = args.run_name or f"stom_1s_grid_pred{horizon}_{run_suffix}"
    save_path = (Path(args.output_root).resolve() if args.output_root else DEFAULT_OUTPUT_ROOT) / run_name
    log_dir = save_path / "logs"
    normalized_stage = train_stage or getattr(args, "train_stage", "predictor")
    if normalized_stage == "both":
        normalized_stage = "predictor"
    manifest_name = "run_manifest.json" if normalized_stage == "predictor" else f"{normalized_stage}_run_manifest.json"
    manifest_path = save_path / manifest_name

    epochs = _mode_default(args.epochs, mode, smoke=1, stage=1, full=1)
    batch_size = _mode_default(args.batch_size, mode, smoke=1, stage=4, full=4)
    default_train = sample_budget["train"] if sample_budget else _mode_default(None, mode, smoke=2, stage=512, full=20_000)
    default_val = sample_budget["val"] if sample_budget else _mode_default(None, mode, smoke=2, stage=128, full=4_000)
    n_train_iter = args.n_train_iter if args.n_train_iter is not None else default_train
    n_val_iter = args.n_val_iter if args.n_val_iter is not None else default_val
    log_interval = _mode_default(args.log_interval, mode, smoke=1, stage=25, full=100)

    env = {
        "KRONOS_DATASET_PATH": str(dataset_dir),
        "KRONOS_LOOKBACK_WINDOW": str(args.lookback_window),
        "KRONOS_PREDICT_WINDOW": str(horizon),
        "KRONOS_EPOCHS": str(epochs),
        "KRONOS_BATCH_SIZE": str(batch_size),
        "KRONOS_N_TRAIN_ITER": str(n_train_iter),
        "KRONOS_N_VAL_ITER": str(n_val_iter),
        "KRONOS_LOG_INTERVAL": str(log_interval),
        "KRONOS_NUM_WORKERS": str(args.num_workers),
        "KRONOS_USE_COMET": "0",
        "KRONOS_SAVE_PATH": str(save_path),
        "KRONOS_TOKENIZER_SAVE_FOLDER": args.tokenizer_save_folder,
        "KRONOS_PREDICTOR_SAVE_FOLDER": args.predictor_save_folder,
        "KRONOS_PRETRAINED_TOKENIZER_PATH": args.pretrained_tokenizer_path,
        "KRONOS_PRETRAINED_PREDICTOR_PATH": args.pretrained_predictor_path,
        "KRONOS_DDP_BACKEND": args.ddp_backend,
        "KRONOS_DATASET_SAMPLE_MODE": args.dataset_sample_mode,
        "USE_LIBUV": "0",
    }
    if args.nproc_per_node == 1:
        env.update(
            {
                "RANK": "0",
                "WORLD_SIZE": "1",
                "LOCAL_RANK": "0",
                "MASTER_ADDR": args.master_addr,
                "MASTER_PORT": str(args.master_port),
                "KRONOS_DISABLE_DDP": "1",
            }
        )
    if args.finetuned_tokenizer_path:
        env["KRONOS_FINETUNED_TOKENIZER_PATH"] = str(Path(args.finetuned_tokenizer_path).resolve())
    elif normalized_stage == "predictor" and getattr(args, "train_stage", "predictor") == "both":
        tokenizer_checkpoint = save_path / args.tokenizer_save_folder / "checkpoints" / "best_model"
        env["KRONOS_FINETUNED_TOKENIZER_PATH"] = str(tokenizer_checkpoint)
    if args.finetuned_predictor_path:
        env["KRONOS_FINETUNED_PREDICTOR_PATH"] = str(Path(args.finetuned_predictor_path).resolve())

    if args.nproc_per_node == 1:
        script_name = "train_tokenizer.py" if normalized_stage == "tokenizer" else "train_predictor.py"
        command = [sys.executable, str(PROJECT_ROOT / "finetune" / script_name)]
    else:
        script_name = "train_tokenizer.py" if normalized_stage == "tokenizer" else "train_predictor.py"
        command = [
            sys.executable,
            "-m",
            "torch.distributed.run",
            "--standalone",
            "--nproc_per_node",
            str(args.nproc_per_node),
            str(PROJECT_ROOT / "finetune" / script_name),
        ]

    return {
        "horizon": horizon,
        "mode": mode,
        "train_stage": normalized_stage,
        "sample_stage": args.sample_stage,
        "target_train_samples": n_train_iter,
        "target_val_samples": n_val_iter,
        "known_full_sample_pool": STOM_1S_FULL_SAMPLE_POOLS.get(horizon),
        "run_name": run_name,
        "dataset_dir": str(dataset_dir),
        "save_path": str(save_path),
        "log_dir": str(log_dir),
        "manifest_path": str(manifest_path),
        "command": command,
        "env": env,
    }


def execute_run(spec: Mapping[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    save_path = Path(str(spec["save_path"]))
    log_dir = Path(str(spec["log_dir"]))
    manifest_path = Path(str(spec["manifest_path"]))
    log_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    payload: Dict[str, Any] = {
        "created_at": _utc_now(),
        "status": "dry_run" if dry_run else "running",
        **{k: v for k, v in spec.items() if k not in {"env"}},
        "env_overrides": dict(spec["env"]),
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if dry_run:
        return payload

    env = os.environ.copy()
    env.update({str(k): str(v) for k, v in spec["env"].items()})
    started = datetime.now(timezone.utc)
    completed = subprocess.run(
        list(spec["command"]),
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    stdout_path = log_dir / "train.stdout.log"
    stderr_path = log_dir / "train.stderr.log"
    stdout_path.write_text(completed.stdout or "", encoding="utf-8")
    stderr_path.write_text(completed.stderr or "", encoding="utf-8")

    payload.update(
        {
            "completed_at": _utc_now(),
            "duration_seconds": (datetime.now(timezone.utc) - started).total_seconds(),
            "returncode": completed.returncode,
            "status": "ok" if completed.returncode == 0 else "failed",
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
            "stdout_tail": _tail(completed.stdout or ""),
            "stderr_tail": _tail(completed.stderr or ""),
        }
    )
    summary_folder_key = (
        "KRONOS_TOKENIZER_SAVE_FOLDER" if spec.get("train_stage") == "tokenizer" else "KRONOS_PREDICTOR_SAVE_FOLDER"
    )
    summary_path = save_path / str(spec["env"][summary_folder_key]) / "summary.json"
    if summary_path.exists():
        payload["summary_path"] = str(summary_path)
        payload["summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"{spec.get('train_stage', 'predictor')} fine-tuning failed for pred{spec['horizon']}; see {stderr_path}")
    return payload


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run STOM 1-second Kronos fine-tuning from QlibDataset pickles.")
    parser.add_argument("--horizon", choices=["30", "60", "all"], default="all")
    parser.add_argument("--mode", choices=["smoke", "stage", "full"], default="stage")
    parser.add_argument(
        "--train-stage",
        choices=sorted(TRAIN_STAGES),
        default="predictor",
        help="Run tokenizer, predictor, or tokenizer then predictor. Official Kronos fine-tuning uses both.",
    )
    parser.add_argument(
        "--sample-stage",
        choices=sorted(SAMPLE_STAGE_PRESETS),
        default=None,
        help=(
            "Optional staged full-data training budget. "
            "Use budget_20k -> expand_200k -> expand_1m -> expand_5m -> full_window."
        ),
    )
    parser.add_argument("--dataset-dir", default=None, help="Override processed_datasets directory; only valid for one horizon.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--run-name", default=None, help="Override run name; only valid for one horizon.")
    parser.add_argument("--lookback-window", type=int, default=300)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--n-train-iter", type=int, default=None)
    parser.add_argument("--n-val-iter", type=int, default=None)
    parser.add_argument("--log-interval", type=int, default=None)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument(
        "--dataset-sample-mode",
        choices=["sample_random", "full_sequential"],
        default="sample_random",
        help="sample_random keeps the original Kronos demo behavior; full_sequential makes dataset idx authoritative.",
    )
    parser.add_argument("--nproc-per-node", type=int, default=1)
    parser.add_argument("--ddp-backend", default="gloo")
    parser.add_argument("--master-addr", default="127.0.0.1")
    parser.add_argument("--master-port", type=int, default=29531)
    parser.add_argument("--pretrained-tokenizer-path", default=DEFAULT_TOKENIZER)
    parser.add_argument("--pretrained-predictor-path", default=DEFAULT_PREDICTOR)
    parser.add_argument("--finetuned-tokenizer-path", default=None)
    parser.add_argument("--finetuned-predictor-path", default=None)
    parser.add_argument("--tokenizer-save-folder", default="finetune_tokenizer")
    parser.add_argument("--predictor-save-folder", default="finetune_predictor")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.dataset_dir and args.horizon == "all":
        raise ValueError("--dataset-dir can only be used with --horizon 30 or --horizon 60")
    if args.run_name and args.horizon == "all":
        raise ValueError("--run-name can only be used with --horizon 30 or --horizon 60")

    horizons: List[int] = [30, 60] if args.horizon == "all" else [int(args.horizon)]
    results = []
    for horizon in horizons:
        stages = ["tokenizer", "predictor"] if args.train_stage == "both" else [args.train_stage]
        for stage in stages:
            spec = build_run(horizon, args, args.mode, train_stage=stage)
            result = execute_run(spec, dry_run=args.dry_run)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
