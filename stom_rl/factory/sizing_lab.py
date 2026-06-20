"""Sizing/risk operations lab for opening gap-up RULE/supervised-gate tracks.

This module computes research-only account-level risk summaries.  The default
input is the ``ts_imb`` opening gap-up RULE baseline; a probability-lane edge
ledger can also be supplied to compare stacked supervised-gate TAKE decisions
against the same-fill ``ts_imb`` decision universe.  Nothing here is
reinforcement learning, live-trading readiness, or a profit claim.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd  # noqa: PANDAS_OK - logged gap-up instances are tabular

OUTCOME_COLUMN = "tp5_sl1_net_pct"
COST_CONVERSION_PCT = 0.02  # 25bp cache -> 23bp round trip
COST_NOTE = "23bp via +0.02pp conversion from 25bp cache"
RULE_STRATEGY_LABEL = "ts_imb RULE baseline - operations design, NOT RL"
STACKED_STRATEGY_LABEL = "stacked supervised gate TAKE - operations design, NOT RL"
BASELINE_LABEL = "same-fill ts_imb RULE baseline"
GUARDRAIL = (
    "Research-only sizing/risk evidence; not RL, not live-ready, no broker/orders, "
    "no profit claim. ts_imb remains a RULE baseline."
)
FIXED_FRACTIONS: tuple[float, ...] = (0.25, 0.5, 1.0)
HALT_THRESHOLDS_PCT: tuple[float, ...] = (2.0, 3.0, 5.0)
VOL_TARGET_PCT = 1.0
CAPACITY_CAP_PER_SESSION = 10
DEFAULT_INSTANCES = Path(".omx") / "artifacts" / "gap_up_full" / "instances.json"
DEFAULT_OUTPUT = (
    Path("webui")
    / "rl_runs"
    / "sizing_lab"
    / "ts_imb_sizing_2026_06_11"
    / "sizing_summary.json"
)


class SizingLabError(ValueError):
    """Raised when sizing-lab inputs violate the expected contract."""


def load_rule_trades(
    instances_path: Path | str,
    *,
    tp_sl_key: str = OUTCOME_COLUMN,
    cost_conversion_pct: float = COST_CONVERSION_PCT,
) -> pd.DataFrame:
    """Load ``pass_ts_imb`` RULE trades at 23bp, chronologically ordered.

    Symbol codes stay strings (leading zeros preserved). Rows are sorted by
    ``(session, symbol)`` so per-session simulation is deterministic.
    """

    raw = json.loads(Path(instances_path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise SizingLabError("instances artifact must be a non-empty list")
    frame = pd.DataFrame(raw)
    required = {"symbol", "session", "pass_ts_imb", tp_sl_key}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise SizingLabError(f"instances missing required columns: {missing}")
    frame = frame.copy()
    frame["symbol"] = frame["symbol"].astype(str)
    frame["session"] = frame["session"].astype(str)
    frame = frame[frame["pass_ts_imb"].astype(bool)]
    frame["net_pct_23bp"] = frame[tp_sl_key].astype(float) + float(cost_conversion_pct)
    frame["decision"] = "TAKE"
    frame = frame.sort_values(["session", "symbol"], kind="mergesort").reset_index(drop=True)
    if frame.empty:
        raise SizingLabError("no pass_ts_imb trades in instances artifact")
    return frame[["symbol", "session", "decision", tp_sl_key, "net_pct_23bp"]]


def load_decision_ledger(
    ledger_path: Path | str,
    *,
    decision: str | None = None,
) -> pd.DataFrame:
    """Load a probability-lane edge ledger at the 23bp net basis.

    ``decision=None`` returns the full decision universe (same-fill ``ts_imb`` in
    stacked mode). ``decision='TAKE'`` returns the supervised gate's selected
    trades.  This function never invents outcomes; it only reads the artifact.
    """

    payload = json.loads(Path(ledger_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SizingLabError("edge ledger must be a JSON object")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise SizingLabError("edge ledger rows must be a non-empty list")
    frame = pd.DataFrame(rows)
    required = {"symbol", "session", "decision", "net_pct_23bp"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise SizingLabError(f"edge ledger missing required columns: {missing}")
    frame = frame.copy()
    frame["symbol"] = frame["symbol"].astype(str)
    frame["session"] = frame["session"].astype(str)
    frame["decision"] = frame["decision"].astype(str)
    invalid = sorted(set(frame["decision"]) - {"TAKE", "SKIP"})
    if invalid:
        raise SizingLabError(f"edge ledger has invalid decisions: {invalid}")
    frame["net_pct_23bp"] = frame["net_pct_23bp"].astype(float)
    if decision is not None:
        if decision not in {"TAKE", "SKIP"}:
            raise SizingLabError("decision must be TAKE, SKIP, or None")
        frame = frame[frame["decision"] == decision]
    frame = frame.sort_values(["session", "symbol"], kind="mergesort").reset_index(drop=True)
    if frame.empty:
        raise SizingLabError("edge ledger decision filter produced no trades")
    return frame[["symbol", "session", "decision", "net_pct_23bp"]]


def _curve_metrics(contributions: np.ndarray) -> dict[str, Any]:
    """Metrics on a non-compounded cumulative-sum equity curve (pct points)."""

    cumulative = np.cumsum(contributions)
    # Prepend the flat start so a drawdown from zero equity is counted.
    curve = np.concatenate(([0.0], cumulative))
    running_peak = np.maximum.accumulate(curve)
    max_drawdown = float(np.max(running_peak - curve))
    longest = current = 0
    for value in contributions:
        current = current + 1 if value < 0.0 else 0
        longest = max(longest, current)
    std = float(np.std(contributions, ddof=1)) if len(contributions) > 1 else 0.0
    mean = float(np.mean(contributions)) if len(contributions) else 0.0
    return {
        "total_pct": float(cumulative[-1]),
        "max_drawdown_pct": max_drawdown,
        "longest_losing_streak": int(longest),
        "n_trades": int(len(contributions)),
        "mean_trade_pct": mean,
        "std_trade_pct": std,
        "risk_adjusted_mean_over_std": (mean / std) if std > 0.0 else None,
        "worst_trade_pct": float(np.min(contributions)),
    }


def fixed_fraction_curve(returns_pct: Sequence[float], fraction: float) -> dict[str, Any]:
    """Non-compounded curve where each trade contributes ``fraction * net_pct``."""

    returns = np.asarray(returns_pct, dtype=float)
    if returns.size == 0:
        raise SizingLabError("returns_pct must be non-empty")
    metrics = _curve_metrics(float(fraction) * returns)
    metrics["fraction"] = float(fraction)
    return metrics


def _causal_scales(
    returns: np.ndarray,
    *,
    target_pct: float,
    window: int,
    max_leverage: float,
    min_periods: int = 10,
) -> np.ndarray:
    """Per-trade scale from trailing realized vol, shifted by 1 (no lookahead)."""

    series = pd.Series(returns)
    trailing_std = series.rolling(window, min_periods=min_periods).std().shift(1)
    scales = float(target_pct) / trailing_std
    scales = scales.clip(upper=float(max_leverage))
    # Unknown vol (warm-up) or zero vol -> default to max_leverage.
    scales = scales.where(np.isfinite(scales), float(max_leverage))
    return scales.to_numpy(dtype=float)


def volatility_targeted_curve(
    returns_pct: Sequence[float],
    *,
    target_pct: float = VOL_TARGET_PCT,
    window: int = 50,
    max_leverage: float = 1.0,
) -> dict[str, Any]:
    """Scale each trade by ``min(max_leverage, target / trailing_std)``.

    The trailing std uses only trades strictly before the current one
    (rolling window shifted by 1), so sizing is causal.
    """

    returns = np.asarray(returns_pct, dtype=float)
    if returns.size == 0:
        raise SizingLabError("returns_pct must be non-empty")
    scales = _causal_scales(
        returns, target_pct=target_pct, window=window, max_leverage=max_leverage
    )
    metrics = _curve_metrics(scales * returns)
    metrics["mean_scale"] = float(np.mean(scales))
    metrics["target_pct"] = float(target_pct)
    metrics["window"] = int(window)
    metrics["max_leverage"] = int(max_leverage)
    return metrics


def session_concurrency(frame: pd.DataFrame) -> dict[str, Any]:
    """Trades-per-session distribution for the concurrent-positions limit."""

    counts = frame.groupby("session").size()
    if counts.empty:
        raise SizingLabError("frame has no sessions")
    values = counts.to_numpy(dtype=float)
    return {
        "n_sessions": int(counts.size),
        "max_trades_per_session": int(values.max()),
        "p95_trades_per_session": float(np.percentile(values, 95)),
        "mean_trades_per_session": float(values.mean()),
    }


def capacity_capped_frame(frame: pd.DataFrame, *, max_trades_per_session: int) -> pd.DataFrame:
    """Keep the first N deterministic trades per session; report skipped capacity."""

    if max_trades_per_session <= 0:
        raise SizingLabError("max_trades_per_session must be positive")
    ordered = frame.sort_values(["session", "symbol"], kind="mergesort").copy()
    rank = ordered.groupby("session").cumcount()
    return ordered[rank < int(max_trades_per_session)].reset_index(drop=True)


def capacity_cap(frame: pd.DataFrame, *, max_trades_per_session: int = CAPACITY_CAP_PER_SESSION) -> dict[str, Any]:
    capped = capacity_capped_frame(frame, max_trades_per_session=max_trades_per_session)
    skipped = int(len(frame) - len(capped))
    metrics = _curve_metrics(capped["net_pct_23bp"].to_numpy(dtype=float))
    metrics.update(
        {
            "max_trades_per_session": int(max_trades_per_session),
            "trades_taken": int(len(capped)),
            "trades_skipped_capacity": skipped,
            "no_cap_total_pct": float(frame["net_pct_23bp"].sum()),
        }
    )
    return metrics


def daily_loss_halt(frame: pd.DataFrame, *, halt_loss_pct: float) -> dict[str, Any]:
    """Sequential per-session sim: stop the session once cum net <= -halt_loss_pct."""

    if halt_loss_pct <= 0.0:
        raise SizingLabError("halt_loss_pct must be positive")
    threshold = -float(halt_loss_pct)
    halted_total = 0.0
    sessions_halted = 0
    trades_taken = 0
    trades_skipped = 0
    for _, session_frame in frame.groupby("session", sort=True):
        session_cum = 0.0
        halted = False
        for net in session_frame["net_pct_23bp"].to_numpy(dtype=float):
            if halted:
                trades_skipped += 1
                continue
            session_cum += net
            trades_taken += 1
            if session_cum <= threshold:
                halted = True
        if halted:
            sessions_halted += 1
        halted_total += session_cum
    return {
        "halt_loss_pct": float(halt_loss_pct),
        "total_pct": float(halted_total),
        "no_halt_total_pct": float(frame["net_pct_23bp"].sum()),
        "sessions_halted": int(sessions_halted),
        "trades_taken": int(trades_taken),
        "trades_skipped": int(trades_skipped),
    }


def worst_session(frame: pd.DataFrame) -> dict[str, Any]:
    session_returns = frame.groupby("session")["net_pct_23bp"].sum().sort_values()
    if session_returns.empty:
        raise SizingLabError("frame has no sessions")
    session = str(session_returns.index[0])
    return {
        "session": session,
        "net_pct": float(session_returns.iloc[0]),
        "n_trades": int((frame["session"] == session).sum()),
    }


def _one_strategy_payload(frame: pd.DataFrame, *, strategy_label: str) -> dict[str, Any]:
    returns = frame["net_pct_23bp"].to_numpy(dtype=float)
    return {
        "strategy_label": strategy_label,
        "n_trades": int(len(frame)),
        "n_sessions": int(frame["session"].nunique()),
        "session_first": str(frame["session"].min()),
        "session_last": str(frame["session"].max()),
        "fixed_fraction": {
            str(fraction): fixed_fraction_curve(returns, fraction)
            for fraction in FIXED_FRACTIONS
        },
        "vol_target": volatility_targeted_curve(returns, target_pct=VOL_TARGET_PCT),
        "concurrency": session_concurrency(frame),
        "capacity_cap": capacity_cap(frame, max_trades_per_session=CAPACITY_CAP_PER_SESSION),
        "daily_halt": {
            str(halt): daily_loss_halt(frame, halt_loss_pct=halt)
            for halt in HALT_THRESHOLDS_PCT
        },
        "worst_session": worst_session(frame),
    }


def _compare_strategy_to_baseline(strategy: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    s_half = strategy["fixed_fraction"]["0.5"]
    b_half = baseline["fixed_fraction"]["0.5"]
    s_ra = s_half.get("risk_adjusted_mean_over_std")
    b_ra = b_half.get("risk_adjusted_mean_over_std")
    return {
        "basis_fraction": 0.5,
        "strategy_total_pct": s_half["total_pct"],
        "baseline_total_pct": b_half["total_pct"],
        "strategy_max_drawdown_pct": s_half["max_drawdown_pct"],
        "baseline_max_drawdown_pct": b_half["max_drawdown_pct"],
        "strategy_risk_adjusted_mean_over_std": s_ra,
        "baseline_risk_adjusted_mean_over_std": b_ra,
        "risk_adjusted_improvement": (
            s_ra is not None and b_ra is not None and s_ra > b_ra
        ),
        "drawdown_improvement": s_half["max_drawdown_pct"] < b_half["max_drawdown_pct"],
        "total_pct_delta": s_half["total_pct"] - b_half["total_pct"],
        "max_drawdown_delta": s_half["max_drawdown_pct"] - b_half["max_drawdown_pct"],
    }


def run_sizing_lab(instances_path: Path | str, output_path: Path | str) -> dict[str, Any]:
    """Compute the default ts_imb RULE sizing/risk lab and write JSON."""

    frame = load_rule_trades(instances_path)
    payload: dict[str, Any] = {
        "artifact_type": "sizing_risk_lab",
        "input_kind": "instances",
        "strategy_label": RULE_STRATEGY_LABEL,
        "guardrail": GUARDRAIL,
        "cost_note": COST_NOTE,
        "instances_path": str(instances_path),
        "tp_sl_key": OUTCOME_COLUMN,
        **_one_strategy_payload(frame, strategy_label=RULE_STRATEGY_LABEL),
    }
    _write_payload(payload, output_path)
    return payload


def run_stacked_sizing_lab(
    ledger_path: Path | str,
    output_path: Path | str,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Compare stacked TAKE sizing/risk against the same-fill ts_imb baseline."""

    baseline_frame = load_decision_ledger(ledger_path, decision=None)
    take_frame = load_decision_ledger(ledger_path, decision="TAKE")
    baseline = _one_strategy_payload(baseline_frame, strategy_label=BASELINE_LABEL)
    strategy = _one_strategy_payload(take_frame, strategy_label=STACKED_STRATEGY_LABEL)
    comparison = _compare_strategy_to_baseline(strategy, baseline)
    payload: dict[str, Any] = {
        "artifact_type": "stacked_sizing_risk_lab",
        "input_kind": "probability_lane_edge_ledger",
        "strategy_label": STACKED_STRATEGY_LABEL,
        "baseline_label": BASELINE_LABEL,
        "guardrail": GUARDRAIL,
        "cost_note": "net_pct_23bp read directly from probability-lane edge ledger",
        "run_id": run_id,
        "edge_ledger_path": str(ledger_path),
        "baseline": baseline,
        "strategy": strategy,
        "comparison": comparison,
        "p5_prerequisite": {
            "account_level_risk_adjusted_improvement": bool(
                comparison["risk_adjusted_improvement"]
                and comparison["drawdown_improvement"]
            ),
            "note": (
                "P5 also requires P1 fill hard gates and P3 schema freeze; this field only covers P2."
            ),
        },
    }
    _write_payload(payload, output_path)
    return payload


def _write_payload(payload: dict[str, Any], output_path: Path | str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", default=str(DEFAULT_INSTANCES))
    parser.add_argument("--decision-ledger", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.decision_ledger:
        payload = run_stacked_sizing_lab(
            args.decision_ledger,
            args.output,
            run_id=args.run_id or None,
        )
    else:
        payload = run_sizing_lab(args.instances, args.output)
    print(
        json.dumps(
            {
                "artifact_type": payload["artifact_type"],
                "input_kind": payload["input_kind"],
                "run_id": payload.get("run_id"),
                "strategy_label": payload["strategy_label"],
                "n_trades": payload.get("n_trades") or payload.get("strategy", {}).get("n_trades"),
                "n_sessions": payload.get("n_sessions") or payload.get("strategy", {}).get("n_sessions"),
                "comparison": payload.get("comparison"),
                "p5_prerequisite": payload.get("p5_prerequisite"),
                "output": str(args.output),
                "guardrail": payload["guardrail"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
