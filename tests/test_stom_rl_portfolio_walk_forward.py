import numpy as np
import pandas as pd

from stom_rl.portfolio_walk_forward import (
    PortfolioWalkForwardConfig,
    build_expanding_window_folds,
    run_portfolio_walk_forward,
)


def _holdout_candidates(n_steps: int = 12) -> pd.DataFrame:
    """Tiny in-memory candidate frame with many distinct timestamps.

    Two symbols, ``n_steps`` one-second bars each, carrying the Page 9 T+1 fill
    contract (``price`` = close at T, ``fill_price`` = next-bar close, last bar
    unfillable).  Enough distinct timestamps for a real train/test split with no
    DB dependency.
    """

    base = pd.Timestamp("2025-07-09 09:00:00")
    rows = []
    for symbol, start in (("A", 100.0), ("B", 50.0)):
        series = [start + step for step in range(n_steps)]
        for t, price in enumerate(series):
            fill = series[t + 1] if t + 1 < len(series) else float("nan")
            rows.append(
                {
                    "timestamp": (base + pd.Timedelta(seconds=t)).isoformat(),
                    "symbol": symbol,
                    "condition_id": "holdout_fixture",
                    "passed": True,
                    "rank_score": float((100 - t) if symbol == "A" else (50 - t)),
                    "price": float(price),
                    "fill_price": fill,
                    "fillable": not np.isnan(fill),
                    "feature_momentum": float(t),
                }
            )
    return pd.DataFrame(rows)


def _config(tmp_path, **overrides) -> PortfolioWalkForwardConfig:
    params = dict(output_dir=str(tmp_path), n_folds=3, max_steps_per_fold=8, write_artifacts=False)
    params.update(overrides)
    return PortfolioWalkForwardConfig(**params)


def test_eval_segment_is_disjoint_and_strictly_later_than_train():
    """Every fold's TEST timestamps are disjoint from AND strictly later than TRAIN."""

    frame = _holdout_candidates()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    folds = build_expanding_window_folds(frame, n_folds=3)

    assert len(folds) >= 2
    for fold in folds:
        train_ts = set(pd.Timestamp(ts) for ts in fold.train_frame["timestamp"].unique())
        test_ts = set(pd.Timestamp(ts) for ts in fold.test_frame["timestamp"].unique())
        assert train_ts and test_ts
        # Disjoint: no shared timestamp between train and test (no in-sample eval).
        assert not (train_ts & test_ts)
        # Strictly later: the earliest test bar comes after the latest train bar.
        assert min(test_ts) > max(train_ts)
        # Expanding window: train of fold N contains train of fold N-1.
    for earlier, later in zip(folds, folds[1:]):
        earlier_train = set(pd.Timestamp(ts) for ts in earlier.train_frame["timestamp"].unique())
        later_train = set(pd.Timestamp(ts) for ts in later.train_frame["timestamp"].unique())
        assert earlier_train < later_train


def test_fold_split_is_deterministic(tmp_path):
    """Same input + seed -> identical fold rows (split + eval determinism)."""

    config = _config(tmp_path)
    first = run_portfolio_walk_forward(config)
    second = run_portfolio_walk_forward(config)
    assert first["fold_periods"] == second["fold_periods"]
    assert first["folds"] == second["folds"]


def test_baseline_metrics_are_populated(tmp_path):
    """The fold report carries the 5 baselines + costed metrics on the TEST segment."""

    payload = run_portfolio_walk_forward(_config(tmp_path))

    assert payload["summary"]["smoke_success"] is True
    assert payload["summary"]["cost_bps"] == 25.0
    policies = {row["policy"] for row in payload["folds"]}
    assert policies == {
        "no_trade",
        "equal_weight_candidate",
        "buy_and_hold",
        "rule_baseline",
        "rl_baseline",
    }
    # Each fold period exposes explicit train/test ranges.
    for period in payload["fold_periods"]:
        assert period["train_end"] < period["test_start"]
        assert period["test_candidate_count"] > 0
    # Costed metrics are present on every row, with cost_bps kept explicit.
    for row in payload["folds"]:
        for key in ("return_pct", "max_drawdown_pct", "turnover", "trade_count", "total_cost", "cost_bps"):
            assert key in row
        assert row["cost_bps"] == 25.0
        assert row["total_cost"] >= 0.0
        assert row["turnover"] >= 0.0


def test_walk_forward_writes_fold_report_artifacts(tmp_path):
    payload = run_portfolio_walk_forward(_config(tmp_path, write_artifacts=True))
    assert (tmp_path / "portfolio_walk_forward_report.json").is_file()
    assert (tmp_path / "portfolio_walk_forward_folds.csv").is_file()
    assert payload["summary"]["holdout"] == "expanding_window_train_le_N_eval_N_plus_1"


def _policy_returns(payload, policy):
    return [row["return_pct"] for row in payload["folds"] if row["policy"] == policy]


def test_leakage_canary_future_column_does_not_change_holdout_eval(tmp_path):
    """Backward-only canary: a forward-looking *column* must not alter results.

    We inject a column whose values are the *next bar's* price (``future_close``)
    plus a perfect ``future_return`` — exactly the kind of forward-looking signal
    a leaky pipeline would consume.  The split geometry is untouched (same
    timestamps), so any change in held-out metrics would be a pure leak.  The
    correct backward-only env ignores unknown future columns, so the fold report
    is byte-identical with and without the injected future signal.
    """

    frame = _holdout_candidates(n_steps=12)
    clean_csv = tmp_path / "clean_cols.csv"
    frame.to_csv(clean_csv, index=False, encoding="utf-8-sig")

    leaky = frame.copy()
    # Perfect foresight columns: the realised next-bar move, only knowable later.
    leaky["future_close"] = leaky["fill_price"].fillna(leaky["price"])
    leaky["future_return"] = (leaky["future_close"] - leaky["price"]) / leaky["price"]
    leaky_csv = tmp_path / "leaky_cols.csv"
    leaky.to_csv(leaky_csv, index=False, encoding="utf-8-sig")

    clean_payload = run_portfolio_walk_forward(_config(tmp_path, candidate_path=str(clean_csv)))
    leaky_payload = run_portfolio_walk_forward(_config(tmp_path, candidate_path=str(leaky_csv)))

    # Identical timestamps -> identical splits; backward-only eval ignores the
    # future columns, so the held-out fold report is unchanged.  If a leak were
    # introduced (the env consuming future_return), these would diverge.
    assert clean_payload["fold_periods"] == leaky_payload["fold_periods"]
    assert clean_payload["folds"] == leaky_payload["folds"]


def test_leakage_canary_detects_forward_looking_corruption(tmp_path):
    """The canary has teeth: corrupting the TEST segment's prices shifts results.

    This proves the harness is sensitive to the data it evaluates on, so a real
    forward-looking leak (e.g. fills using a future price) would be *detected*
    as a performance change rather than silently passing.
    """

    frame = _holdout_candidates(n_steps=12)
    clean_csv = tmp_path / "clean.csv"
    frame.to_csv(clean_csv, index=False, encoding="utf-8-sig")
    clean = run_portfolio_walk_forward(_config(tmp_path, candidate_path=str(clean_csv)))

    corrupted = frame.copy()
    # Inject a forward-looking shock into fill prices (a leak would raise fills).
    corrupted["fill_price"] = corrupted["fill_price"] * 5.0
    corrupt_csv = tmp_path / "corrupt.csv"
    corrupted.to_csv(corrupt_csv, index=False, encoding="utf-8-sig")
    corrupt = run_portfolio_walk_forward(_config(tmp_path, candidate_path=str(corrupt_csv)))

    clean_returns = _policy_returns(clean, "rl_baseline")
    corrupt_returns = _policy_returns(corrupt, "rl_baseline")
    # Performance changes (collapses/inflates) under forward-looking corruption.
    assert clean_returns != corrupt_returns


def test_too_few_timestamps_raises(tmp_path):
    """A single distinct timestamp cannot form a holdout split (fails loudly)."""

    frame = _holdout_candidates(n_steps=1)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    try:
        build_expanding_window_folds(frame, n_folds=3)
    except ValueError as exc:
        assert "two time segments" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError for too few timestamps")
