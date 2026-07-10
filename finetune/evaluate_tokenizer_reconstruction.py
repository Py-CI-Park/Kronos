"""Evaluate KronosTokenizer reconstruction MSE on STOM test-split windows.

Reuses the pickle-loading pattern from ``evaluate_stom_1s_checkpoint.py`` (same
``<dataset>/test_data.pkl`` layout) and the window-normalization pattern from
``QlibDataset`` in ``dataset.py`` (mean/std computed on the window, then clipped)
so the reconstruction metric below is directly comparable to the validation MSE
computed in ``train_tokenizer.py``: ``F.mse_loss(z, x)`` where ``z`` is the
tokenizer's full-codebook reconstruction of the normalized input ``x``.

Batch size is fixed at 1 (one window per forward pass) and the seed is fixed so
repeated runs against the same ``--tokenizer-path``/``--data`` are deterministic.
Purpose: quantify base vs fine-tuned tokenizer reconstruction quality (WP-R5c).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

try:
    import torch
    import torch.nn.functional as F
except ImportError:  # pragma: no cover - module must still parse without torch installed
    torch = None
    F = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
FINETUNE_DIR = Path(__file__).resolve().parent
if str(FINETUNE_DIR) not in sys.path:
    sys.path.insert(0, str(FINETUNE_DIR))

from config import Config  # noqa: E402
from evaluate_stom_1s_checkpoint import load_pickle_dataset  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_normalized_windows(
    data: Mapping[str, Any],
    feature_list: Sequence[str],
    window: int,
    clip: float,
    max_windows: int,
    stride: int,
) -> List["np.ndarray"]:
    """Slice deterministic per-symbol windows and apply QlibDataset-style normalization.

    Mirrors ``QlibDataset.__getitem__`` in ``dataset.py``: mean/std are computed on
    the window itself (fixed test-window length, no train/val leakage concern here)
    and applied + clipped across the same window, matching the tensor the tokenizer
    consumes during training-time validation.
    """
    windows: List["np.ndarray"] = []
    for symbol in sorted(data.keys()):
        if len(windows) >= max_windows:
            break
        frame = data[symbol]
        values = np.asarray(frame[list(feature_list)].to_numpy(), dtype=np.float32)
        n = len(values)
        if n < window:
            continue
        for start in range(0, n - window + 1, max(1, stride)):
            if len(windows) >= max_windows:
                break
            win = values[start : start + window]
            mean = win.mean(axis=0)
            std = win.std(axis=0)
            norm = (win - mean) / (std + 1e-5)
            norm = np.clip(norm, -clip, clip)
            windows.append(norm)
    return windows


def evaluate_tokenizer_reconstruction(
    tokenizer_path: str,
    windows: Sequence["np.ndarray"],
    device: str = "cpu",
) -> Dict[str, Any]:
    """Run batch-1 reconstruction MSE for every window, matching train_tokenizer.py's val metric."""
    if torch is None or F is None:
        raise RuntimeError("torch is required to evaluate tokenizer reconstruction; install torch first.")
    from model import KronosTokenizer

    tokenizer = KronosTokenizer.from_pretrained(tokenizer_path)
    tokenizer.to(device)
    tokenizer.eval()

    losses: List[float] = []
    with torch.inference_mode():
        for window in windows:
            batch_x = torch.from_numpy(window).unsqueeze(0).to(device)
            zs, _, _, _ = tokenizer(batch_x)
            _, z = zs
            loss = F.mse_loss(z, batch_x)
            losses.append(float(loss.item()))

    mean_loss = float(np.mean(losses)) if losses else float("nan")
    return {
        "tokenizer_path": tokenizer_path,
        "windows": len(losses),
        "mse_mean": mean_loss,
        "mse_values": losses,
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate KronosTokenizer reconstruction MSE on a STOM test_data.pkl split."
    )
    parser.add_argument("--data", required=True, help="processed_datasets directory containing test_data.pkl")
    parser.add_argument("--tokenizer-path", required=True, help="Tokenizer checkpoint dir or HF model id")
    parser.add_argument("--output", default=None, help="Result JSON path (default: alongside --tokenizer-path)")
    parser.add_argument("--lookback-window", type=int, default=None, help="Defaults to config.py lookback_window.")
    parser.add_argument("--predict-window", type=int, default=None, help="Defaults to config.py predict_window.")
    parser.add_argument("--max-windows", type=int, default=50)
    parser.add_argument("--stride", type=int, default=300)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=100)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    random.seed(args.seed)
    np.random.seed(args.seed)
    if torch is not None:
        torch.manual_seed(args.seed)

    config = Config()
    lookback_window = args.lookback_window if args.lookback_window is not None else config.lookback_window
    predict_window = args.predict_window if args.predict_window is not None else config.predict_window
    window = lookback_window + predict_window + 1  # matches QlibDataset.window

    data = load_pickle_dataset(Path(args.data), split="test")
    windows = build_normalized_windows(
        data,
        feature_list=config.feature_list,
        window=window,
        clip=config.clip,
        max_windows=args.max_windows,
        stride=args.stride,
    )
    if not windows:
        raise ValueError("No evaluation windows were built from the test split.")

    result = evaluate_tokenizer_reconstruction(args.tokenizer_path, windows, device=args.device)
    result["created_at"] = _utc_now()
    result["data_path"] = str(Path(args.data))
    result["lookback_window"] = lookback_window
    result["predict_window"] = predict_window
    result["window"] = window
    result["stride"] = args.stride
    result["seed"] = args.seed

    if args.output:
        output_path = Path(args.output)
    elif Path(args.tokenizer_path).is_dir():
        output_path = Path(args.tokenizer_path) / "tokenizer_reconstruction_eval.json"
    else:
        output_path = Path.cwd() / "tokenizer_reconstruction_eval.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["output_path"] = str(output_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
