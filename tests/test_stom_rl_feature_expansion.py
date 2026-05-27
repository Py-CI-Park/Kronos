import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from finetune.qlib_stom_pipeline import (
    STOM_RL_CANONICAL_FEATURES,
    STOM_RL_TRADE_STRENGTH_AVG_WINDOW,
    build_stom_rl_feature_frame,
    export_stom_rl_features,
)
from stom_rl.trading_env import StomTickTradingEnv, StomTickTradingEnvConfig


# STOM tick DB column order (UTF-8 Korean names), trimmed to the fields needed
# by the RL feature export.  Mirrors the real per-symbol table layout so the
# export path can be exercised without the 29.7GB production database.
_FIXTURE_COLUMNS = [
    "index",
    "현재가",
    "시가",
    "고가",
    "저가",
    "초당매수수량",
    "초당매도수량",
    "체결강도",
    "초당거래대금",
    "회전율",
    "매수총잔량",
    "매도총잔량",
    "매수호가1",
    "매도호가1",
    "등락율",
    "시가총액",
    "고저평균대비등락율",
]


def _make_fixture_db(db_path: Path, rows: list[tuple]) -> None:
    """Create a tiny STOM-shaped sqlite DB with UTF-8 Korean column names."""

    conn = sqlite3.connect(str(db_path))
    try:
        column_defs = ", ".join(f'"{name}"' for name in _FIXTURE_COLUMNS)
        conn.execute(f'CREATE TABLE "000020" ({column_defs})')
        placeholders = ", ".join(["?"] * len(_FIXTURE_COLUMNS))
        conn.executemany(f'INSERT INTO "000020" VALUES ({placeholders})', rows)
        conn.commit()
    finally:
        conn.close()


def _fixture_row(idx: int, close: float, buy: float, sell: float, amount: float, strength: float = 200.0) -> tuple:
    # index, 현재가, 시가, 고가, 저가, 초당매수수량, 초당매도수량, 체결강도,
    # 초당거래대금, 회전율, 매수총잔량, 매도총잔량, 매수호가1, 매도호가1,
    # 등락율, 시가총액, 고저평균대비등락율
    return (
        idx,
        close,
        close,
        close + 10.0,
        close - 10.0,
        buy,
        sell,
        strength,
        amount,
        0.05,
        80.0,
        20.0,
        close - 10.0,
        close + 10.0,
        1.25,
        45000.0,
        -0.5,
    )


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


def test_export_stom_rl_features_yields_canonical_columns(tmp_path: Path):
    db_path = tmp_path / "fixture.db"
    rows = [
        _fixture_row(20221212090005 + i, close=9260.0 + i, buy=10.0 + i, sell=3.0 + i, amount=100.0 + i)
        for i in range(8)
    ]
    _make_fixture_db(db_path, rows)

    report = export_stom_rl_features(
        db_path=db_path,
        output_dir=tmp_path / "out",
        table="000020",
        session="20221212",
        time_start="090000",
        time_end="093000",
        max_rows=5000,
    )

    csv_path = Path(report["csv_path"])
    assert csv_path.exists()
    frame = pd.read_csv(csv_path, dtype={"symbol": str, "session": str}, encoding="utf-8-sig")

    feature_columns = [c for c in frame.columns if c in STOM_RL_CANONICAL_FEATURES]
    assert feature_columns == STOM_RL_CANONICAL_FEATURES
    assert list(frame.columns)[:3] == ["timestamp", "symbol", "session"]

    assert report["source"]["row_count"] == 8
    assert report["source"]["unresolved_targets"] == []
    assert report["source"]["encoding_confirmed"] is True
    assert frame["symbol"].iloc[0] == "000020"


def test_export_stom_rl_features_has_no_nan_or_inf(tmp_path: Path):
    db_path = tmp_path / "fixture.db"
    rows = [
        _fixture_row(20221212090005 + i, close=9260.0, buy=0.0, sell=0.0, amount=0.0)
        for i in range(5)
    ]
    _make_fixture_db(db_path, rows)

    report = export_stom_rl_features(
        db_path=db_path,
        output_dir=tmp_path / "out",
        table="000020",
        session="20221212",
    )

    assert report["scale"]["nan_inf_clean"] is True
    assert report["scale"]["has_nan"] is False
    assert report["scale"]["has_inf"] is False

    frame = pd.read_csv(Path(report["csv_path"]), encoding="utf-8-sig")
    feature_frame = frame[STOM_RL_CANONICAL_FEATURES]
    assert not feature_frame.isna().any().any()
    assert np.isfinite(feature_frame.to_numpy(dtype="float64")).all()


def test_export_stom_rl_features_is_leakage_free(tmp_path: Path):
    """A future-dated row beyond the window must not change features at rows <= T."""

    base_rows = [
        _fixture_row(20221212090005 + i, close=9260.0 + i, buy=10.0 + i, sell=3.0, amount=100.0 + i)
        for i in range(6)
    ]
    # A row outside the 09:00-09:30 window with extreme values that would shift
    # scale/diff features if it ever leaked backward into <= T rows.
    future_row = _fixture_row(20221212094000, close=99999.0, buy=99999.0, sell=99999.0, amount=99999.0)

    db_baseline = tmp_path / "baseline.db"
    db_with_future = tmp_path / "with_future.db"
    _make_fixture_db(db_baseline, base_rows)
    _make_fixture_db(db_with_future, base_rows + [future_row])

    report_baseline = export_stom_rl_features(
        db_path=db_baseline,
        output_dir=tmp_path / "out_baseline",
        table="000020",
        session="20221212",
        time_start="090000",
        time_end="093000",
    )
    report_future = export_stom_rl_features(
        db_path=db_with_future,
        output_dir=tmp_path / "out_future",
        table="000020",
        session="20221212",
        time_start="090000",
        time_end="093000",
    )

    frame_baseline = pd.read_csv(Path(report_baseline["csv_path"]), encoding="utf-8-sig")
    frame_future = pd.read_csv(Path(report_future["csv_path"]), encoding="utf-8-sig")

    # The window filter drops the future row, so both frames must be identical.
    assert frame_baseline.shape == frame_future.shape
    pd.testing.assert_frame_equal(
        frame_baseline[STOM_RL_CANONICAL_FEATURES],
        frame_future[STOM_RL_CANONICAL_FEATURES],
    )

    # Point-in-time check: amount_delta at row T equals amount[T] - amount[T-1]
    # (backward-only differencing, never forward-looking).
    amount = frame_baseline["amount"].to_numpy(dtype="float64")
    amount_delta = frame_baseline["amount_delta"].to_numpy(dtype="float64")
    assert amount_delta[0] == 0.0
    np.testing.assert_allclose(amount_delta[1:], amount[1:] - amount[:-1])


# ---------------------------------------------------------------------------
# Stage C feature expansion: the 4 new canonical features.
# ---------------------------------------------------------------------------
def test_build_stom_rl_feature_frame_adds_stage_c_features():
    """The 4 Stage C features are produced from DB-like Korean columns and
    are finite (no NaN/inf)."""

    n = 6
    frame = pd.DataFrame(
        {
            "symbol": ["000001"] * n,
            "session": ["20250103"] * n,
            "open": np.arange(n) + 100.0,
            "high": np.arange(n) + 101.0,
            "low": np.arange(n) + 99.0,
            "close": np.arange(n) + 100.0,
            "volume": np.arange(n) + 10.0,
            "amount": (np.arange(n) + 100.0) * 5.0,
            "체결강도": np.arange(n) + 200.0,
            "등락율": np.linspace(-2.0, 3.0, n),
            "시가총액": np.full(n, 45000.0),
            "고저평균대비등락율": np.linspace(-1.0, 1.0, n),
        }
    )

    features = build_stom_rl_feature_frame(frame)

    # Canonical set is now 18 wide and includes the 4 new columns.
    assert len(STOM_RL_CANONICAL_FEATURES) == 18
    for new_col in (
        "change_rate",
        "market_cap",
        "high_low_mid_change_rate",
        "trade_strength_avg_n",
    ):
        assert new_col in features.columns

    block = features[
        ["change_rate", "market_cap", "high_low_mid_change_rate", "trade_strength_avg_n"]
    ]
    assert not block.isna().any().any()
    assert np.isfinite(block.to_numpy(dtype="float64")).all()

    # Direct passthroughs map their source column values.
    np.testing.assert_allclose(features["change_rate"].to_numpy(), np.linspace(-2.0, 3.0, n))
    np.testing.assert_allclose(
        features["high_low_mid_change_rate"].to_numpy(), np.linspace(-1.0, 1.0, n)
    )
    # market_cap is log1p-normalized from the large 시가총액 magnitude.
    np.testing.assert_allclose(features["market_cap"].to_numpy(), np.log1p(45000.0))


def test_trade_strength_avg_n_is_causal_trailing_mean():
    """``trade_strength_avg_n`` at row T equals the trailing mean of
    trade_strength over rows <= T, and is UNCHANGED when future rows are
    appended or modified (no look-ahead)."""

    window = STOM_RL_TRADE_STRENGTH_AVG_WINDOW
    n = 40
    strengths = (np.arange(n) % 7) * 30.0 + 50.0  # within the [0, 500] band

    def _frame(values: np.ndarray) -> pd.DataFrame:
        m = len(values)
        return pd.DataFrame(
            {
                "symbol": ["000001"] * m,
                "session": ["20250103"] * m,
                "open": np.full(m, 100.0),
                "high": np.full(m, 101.0),
                "low": np.full(m, 99.0),
                "close": np.full(m, 100.0),
                "volume": np.full(m, 10.0),
                "amount": np.full(m, 500.0),
                "체결강도": values,
            }
        )

    base = build_stom_rl_feature_frame(_frame(strengths))
    avg = base["trade_strength_avg_n"].to_numpy(dtype="float64")

    # Reference: explicit backward-only window mean over rows [max(0, T-N+1), T].
    clipped = np.clip(strengths, 0.0, 500.0)
    expected = np.array(
        [clipped[max(0, t - window + 1) : t + 1].mean() for t in range(n)]
    )
    np.testing.assert_allclose(avg, expected)

    # Leakage guard: append extreme FUTURE rows; rows <= T must be byte-identical.
    future = np.concatenate([strengths, np.full(10, 9999.0)])
    extended = build_stom_rl_feature_frame(_frame(future))
    np.testing.assert_allclose(
        extended["trade_strength_avg_n"].to_numpy(dtype="float64")[:n], avg
    )

    # Modifying ONLY a future row must not change any row at or before T.
    mutated = strengths.copy()
    mutated_future = np.concatenate([mutated, np.full(5, 0.0)])
    mutated_future[n + 2] = 12345.0  # a far-future spike
    mutated_frame = build_stom_rl_feature_frame(_frame(mutated_future))
    np.testing.assert_allclose(
        mutated_frame["trade_strength_avg_n"].to_numpy(dtype="float64")[:n], avg
    )


def test_export_stom_rl_features_populates_stage_c_columns(tmp_path: Path):
    """The real export path emits the 4 new columns, populated and finite."""

    db_path = tmp_path / "fixture.db"
    rows = [
        _fixture_row(20221212090005 + i, close=9260.0 + i, buy=10.0 + i, sell=3.0 + i, amount=100.0 + i)
        for i in range(8)
    ]
    _make_fixture_db(db_path, rows)

    report = export_stom_rl_features(
        db_path=db_path,
        output_dir=tmp_path / "out",
        table="000020",
        session="20221212",
        time_start="090000",
        time_end="093000",
        max_rows=5000,
    )

    frame = pd.read_csv(Path(report["csv_path"]), encoding="utf-8-sig")
    for new_col in (
        "change_rate",
        "market_cap",
        "high_low_mid_change_rate",
        "trade_strength_avg_n",
    ):
        assert new_col in frame.columns
        assert np.isfinite(frame[new_col].to_numpy(dtype="float64")).all()

    # 등락율=1.25, 고저평균대비등락율=-0.5, 시가총액=45000 in every fixture row.
    np.testing.assert_allclose(frame["change_rate"].to_numpy(), 1.25)
    np.testing.assert_allclose(frame["high_low_mid_change_rate"].to_numpy(), -0.5)
    np.testing.assert_allclose(frame["market_cap"].to_numpy(), np.log1p(45000.0))
    # Constant strength=200 fixture -> trailing mean is 200 everywhere.
    np.testing.assert_allclose(frame["trade_strength_avg_n"].to_numpy(), 200.0)
    assert report["canonical_features"] == list(STOM_RL_CANONICAL_FEATURES)
