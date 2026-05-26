import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from finetune.qlib_stom_pipeline import STOM_RL_CANONICAL_FEATURES, build_stom_rl_feature_frame
from stom_rl.trading_env import StomTickTradingEnv, StomTickTradingEnvConfig


def test_build_stom_rl_feature_frame_maps_db_like_columns():
    frame = pd.DataFrame(
        {
            "symbol": ["000001", "000001"],
            "session": ["20250103", "20250103"],
            "open": [100, 101],
            "high": [101, 102],
            "low": [99, 100],
            "close": [100, 101],
            "volume": [10, 11],
            "amount": [1000, 1111],
            "trade_strength": [600, 250],
            "buy_qty": [7, 9],
            "sell_qty": [2, 3],
            "bid_qty": [80, 90],
            "ask_qty": [20, 30],
            "bid_price": [99, 100],
            "ask_price": [101, 102],
            "turnover_rate": [1.5, 1.7],
        }
    )

    features = build_stom_rl_feature_frame(frame)

    assert list(features.columns) == STOM_RL_CANONICAL_FEATURES
    assert features["trade_strength"].iloc[0] == 500
    assert features["net_buy_qty_1s"].tolist() == [5, 6]
    assert features["bid_ask_imbalance"].iloc[0] == pytest.approx(0.8)
    assert features["spread_ticks"].iloc[0] == pytest.approx(2.0)
    assert features["amount_delta"].tolist() == [0.0, 111.0]


def test_trading_env_accepts_configured_extra_feature_columns(tmp_path: Path):
    csv_path = tmp_path / "KR000001_20250103.csv"
    base = pd.Timestamp("2025-01-03 09:00:00")
    rows = 16
    frame = pd.DataFrame(
        {
            "symbol": "KR000001",
            "date": [(base + pd.Timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(rows)],
            "open": np.arange(rows) + 100.0,
            "high": np.arange(rows) + 101.0,
            "low": np.arange(rows) + 99.0,
            "close": np.arange(rows) + 100.0,
            "volume": np.arange(rows) + 10.0,
            "amount": (np.arange(rows) + 100.0) * (np.arange(rows) + 10.0),
            "trade_strength": np.arange(rows) + 200.0,
            "net_buy_qty_1s": np.arange(rows) - 2.0,
        }
    )
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "episodes": [
                    {
                        "episode_id": "000001_20250103",
                        "symbol": "000001",
                        "session": "20250103",
                        "split": "train",
                        "source_csv": str(csv_path),
                    }
                ]
            }
        ),
        encoding="utf-8-sig",
    )

    env = StomTickTradingEnv(
        StomTickTradingEnvConfig(
            manifest_path=str(manifest_path),
            split="train",
            lookback_window=5,
            reward_horizon_seconds=3,
            feature_columns=("open", "close", "trade_strength", "net_buy_qty_1s"),
        )
    )
    observation, info = env.reset(seed=1)

    assert observation.shape == (5, 7)
    assert info["feature_columns"] == [
        "open",
        "close",
        "trade_strength",
        "net_buy_qty_1s",
        "position",
        "unrealized_return",
        "time_in_position",
    ]
