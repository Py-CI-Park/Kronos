import pickle
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FINETUNE_DIR = PROJECT_ROOT / "finetune"
if str(FINETUNE_DIR) not in sys.path:
    sys.path.insert(0, str(FINETUNE_DIR))

from evaluate_stom_1s_checkpoint import (  # noqa: E402
    load_pickle_dataset,
    persistence_predictions,
    random_direction_predictions,
    rows_from_predictions,
    select_aligned_windows,
    summarize_prediction_frame,
    write_prediction_artifacts,
)


def _frame(rows: int = 12) -> pd.DataFrame:
    start = datetime(2026, 1, 2, 9, 0, 0)
    idx = [start + timedelta(seconds=i) for i in range(rows)]
    return pd.DataFrame(
        {
            "open": [100 + i for i in range(rows)],
            "high": [100 + i for i in range(rows)],
            "low": [100 + i for i in range(rows)],
            "close": [100 + i for i in range(rows)],
            "vol": [10 + i for i in range(rows)],
            "amt": [(100 + i) * (10 + i) for i in range(rows)],
        },
        index=pd.DatetimeIndex(idx, name="datetime"),
    )


def test_checkpoint_eval_baselines_write_dashboard_compatible_artifacts(tmp_path):
    dataset = tmp_path / "processed_datasets"
    dataset.mkdir()
    payload = {
        "KR000001_20260102": _frame(),
        "KR000002_20260102": _frame(),
    }
    with (dataset / "test_data.pkl").open("wb") as f:
        pickle.dump(payload, f)

    data = load_pickle_dataset(dataset)
    windows = select_aligned_windows(data, lookback_window=4, predict_window=3, max_symbols=2)
    persistence_df = rows_from_predictions(windows, persistence_predictions(windows), mode="persistence")
    random_df = rows_from_predictions(windows, random_direction_predictions(windows), mode="random")
    result = write_prediction_artifacts(
        {"persistence": persistence_df, "random": random_df},
        tmp_path / "predictions",
        "unit_eval",
        top_k=1,
    )

    assert len(windows) == 2
    assert persistence_df["symbol"].iloc[0] == "KR000001"
    assert persistence_df["horizon_step"].max() == 3
    assert summarize_prediction_frame(persistence_df)["windows"] == 2
    assert Path(result["files"]["persistence"]).exists()
    assert Path(result["comparison_path"]).exists()
    assert result["metrics"]["random"]["topk"]["k"] == 1
