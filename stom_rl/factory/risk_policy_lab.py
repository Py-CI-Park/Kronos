"""Risk-policy search lab for P2 model-build readiness.

This module evaluates deterministic, pre-declared non-RL risk policies on the
probability-lane edge ledger.  It is a research gate for deciding whether a
restricted RL sizing/exit controller may even be considered.  It does not train
an RL policy, does not place orders, and makes no profit/live-readiness claim.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd  # noqa: PANDAS_OK - edge ledgers are tabular research artifacts

VALID_DECISIONS = {"TAKE", "SKIP"}
DEFAULT_OUTPUT_ROOT = Path("webui") / "rl_runs" / "risk_policy_lab"
DEFAULT_BASIS_FRACTION = 0.5
GUARDRAIL = (
    "Research-only risk-policy gate; deterministic non-RL sizing/de-risk rules; "
    "no broker/orders, no live-readiness, no profit claim. ts_imb remains a RULE baseline."
)
BASELINE_LABEL = "same-fill ts_imb RULE baseline"
STRATEGY_LABEL = "stacked supervised gate risk policy - operations design, NOT RL"


class RiskPolicyLabError(ValueError):
    """Raised when risk-policy inputs violate the expected contract."""


@dataclass(frozen=True, slots=True)
class PolicySpec:
    policy_id: str
    min_p_win: float | None
    high_p_win: float | None
    low_size: float
    high_size: float
    halt_loss_pct: float | None = None
    description: str = ""


POLICY_SPECS: tuple[PolicySpec, ...] = (
    PolicySpec("take_all_fixed_050", None, None, 0.5, 0.5, None, "Original stacked TAKE at fixed 0.5 sizing."),
    PolicySpec("pwin_gt_040_size_050_100", 0.40, 0.55, 0.5, 1.0, None, "TAKE rows with p_win>0.40; size 1.0 when p_win>=0.55 else 0.5."),
    PolicySpec("pwin_gt_040_size_050_100_halt_25", 0.40, 0.55, 0.5, 1.0, 2.5, "Same p_win bucket policy with causal per-session -2.5pp halt."),
    PolicySpec("pwin_gt_045_size_050_100_halt_25", 0.45, 0.55, 0.5, 1.0, 2.5, "Higher-confidence p_win bucket with causal per-session -2.5pp halt."),
    PolicySpec("pwin_gt_050_size_050_100_halt_25", 0.50, 0.60, 0.5, 1.0, 2.5, "Strict p_win bucket with causal per-session -2.5pp halt."),
    PolicySpec("pwin_gt_055_fixed_050", 0.55, None, 0.5, 0.5, None, "High-confidence TAKE subset at fixed 0.5 sizing."),
    PolicySpec("pwin_gt_060_fixed_050", 0.60, None, 0.5, 0.5, None, "Very high-confidence TAKE subset at fixed 0.5 sizing."),
)


def _ensure_under_root(output_path: Path, output_root: Path | None) -> Path:
    path = output_path.expanduser().resolve(strict=False)
    if output_root is None:
        return path
    root = output_root.expanduser().resolve(strict=False)
    if path != root and not path.is_relative_to(root):
        raise RiskPolicyLabError(f"output path must be under generated risk-policy root: {root}")
    return path


def load_edge_ledger(ledger_path: Path | str) -> pd.DataFrame:
    payload = json.loads(Path(ledger_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RiskPolicyLabError("edge ledger must be a JSON object")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RiskPolicyLabError("edge ledger rows must be a non-empty list")
    frame = pd.DataFrame(rows)
    required = {"symbol", "session", "decision", "p_win", "edge_pct", "net_pct_23bp"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise RiskPolicyLabError(f"edge ledger missing required columns: {missing}")
    frame = frame.copy()
    frame["symbol"] = frame["symbol"].astype(str)
    frame["session"] = frame["session"].astype(str)
    frame["decision"] = frame["decision"].astype(str)
    invalid = sorted(set(frame["decision"]) - VALID_DECISIONS)
    if invalid:
        raise RiskPolicyLabError(f"edge ledger has invalid decisions: {invalid}")
    frame["p_win"] = frame["p_win"].astype(float)
    frame["edge_pct"] = frame["edge_pct"].astype(float)
    frame["net_pct_23bp"] = frame["net_pct_23bp"].astype(float)
    return frame.sort_values(["session", "symbol"], kind="mergesort").reset_index(drop=True)


def _curve_metrics(contributions_pct: Iterable[float]) -> dict[str, Any]:
    values = np.asarray(list(contributions_pct), dtype=float)
    if values.size == 0:
        raise RiskPolicyLabError("policy produced no contributions")
    cumulative = np.cumsum(values)
    curve = np.concatenate(([0.0], cumulative))
    running_peak = np.maximum.accumulate(curve)
    max_drawdown = float(np.max(running_peak - curve))
    std = float(np.std(values, ddof=1)) if values.size > 1 else 0.0
    mean = float(np.mean(values)) if values.size else 0.0
    longest = current = 0
    for value in values:
        current = current + 1 if value < 0.0 else 0
        longest = max(longest, current)
    return {
        "total_pct": float(cumulative[-1]),
        "max_drawdown_pct": max_drawdown,
        "longest_losing_streak": int(longest),
        "n_trades": int(values.size),
        "mean_trade_pct": mean,
        "std_trade_pct": std,
        "risk_adjusted_mean_over_std": (mean / std) if std > 0.0 else None,
        "worst_trade_pct": float(np.min(values)),
    }


def _baseline_payload(frame: pd.DataFrame, *, basis_fraction: float) -> dict[str, Any]:
    contributions = basis_fraction * frame["net_pct_23bp"].to_numpy(dtype=float)
    payload = _curve_metrics(contributions)
    payload.update(
        {
            "strategy_label": BASELINE_LABEL,
            "basis_fraction": float(basis_fraction),
            "n_source_rows": int(len(frame)),
            "n_sessions": int(frame["session"].nunique()),
        }
    )
    return payload


def _apply_policy(frame: pd.DataFrame, spec: PolicySpec) -> dict[str, Any]:
    take = frame[frame["decision"] == "TAKE"].copy()
    source_take_count = int(len(take))
    if spec.min_p_win is not None:
        selected = take[take["p_win"] > float(spec.min_p_win)].copy()
    else:
        selected = take.copy()
    if selected.empty:
        raise RiskPolicyLabError(f"policy {spec.policy_id} selected no TAKE rows")

    if spec.high_p_win is None:
        sizes = np.full(len(selected), float(spec.low_size), dtype=float)
    else:
        sizes = np.where(
            selected["p_win"].to_numpy(dtype=float) >= float(spec.high_p_win),
            float(spec.high_size),
            float(spec.low_size),
        )
    selected["size"] = sizes
    selected["contribution_pct"] = sizes * selected["net_pct_23bp"].to_numpy(dtype=float)

    halted_sessions = 0
    skipped_halt = 0
    contributions: list[float] = []
    for _, group in selected.groupby("session", sort=True):
        session_cum = 0.0
        halted = False
        for _, row in group.iterrows():
            if halted:
                skipped_halt += 1
                continue
            value = float(row["contribution_pct"])
            contributions.append(value)
            session_cum += value
            if spec.halt_loss_pct is not None and session_cum <= -float(spec.halt_loss_pct):
                halted = True
        if halted:
            halted_sessions += 1

    metrics = _curve_metrics(contributions)
    metrics.update(
        {
            "policy_id": spec.policy_id,
            "description": spec.description,
            "strategy_label": STRATEGY_LABEL,
            "min_p_win": spec.min_p_win,
            "high_p_win": spec.high_p_win,
            "low_size": float(spec.low_size),
            "high_size": float(spec.high_size),
            "halt_loss_pct": spec.halt_loss_pct,
            "source_take_count": source_take_count,
            "selected_before_halt": int(len(selected)),
            "trades_skipped_filter": int(source_take_count - len(selected)),
            "trades_skipped_halt": int(skipped_halt),
            "sessions_halted": int(halted_sessions),
            "n_sessions": int(selected["session"].nunique()),
            "mean_size_before_halt": float(np.mean(sizes)),
        }
    )
    return metrics


def _compare(policy: Mapping[str, Any], baseline: Mapping[str, Any], *, min_total_delta_pct: float) -> dict[str, Any]:
    p_ra = policy.get("risk_adjusted_mean_over_std")
    b_ra = baseline.get("risk_adjusted_mean_over_std")
    total_delta = float(policy["total_pct"]) - float(baseline["total_pct"])
    dd_delta = float(policy["max_drawdown_pct"]) - float(baseline["max_drawdown_pct"])
    risk_adjusted_improvement = p_ra is not None and b_ra is not None and float(p_ra) > float(b_ra)
    drawdown_improvement = dd_delta < 0.0
    total_noninferior = total_delta >= float(min_total_delta_pct)
    return {
        "total_pct_delta": total_delta,
        "max_drawdown_delta": dd_delta,
        "risk_adjusted_delta": (float(p_ra) - float(b_ra)) if p_ra is not None and b_ra is not None else None,
        "risk_adjusted_improvement": bool(risk_adjusted_improvement),
        "drawdown_improvement": bool(drawdown_improvement),
        "total_noninferior": bool(total_noninferior),
        "p2_candidate_pass": bool(risk_adjusted_improvement and drawdown_improvement and total_noninferior),
    }


def _sort_key(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    comparison = candidate["comparison"]
    policy = candidate["policy"]
    return (
        bool(comparison["p2_candidate_pass"]),
        float(comparison["total_pct_delta"]),
        -float(policy["max_drawdown_pct"]),
        float(comparison.get("risk_adjusted_delta") or -999.0),
    )


def run_risk_policy_lab(
    ledger_path: Path | str,
    output_path: Path | str,
    *,
    run_id: str,
    fill_mode: str,
    basis_fraction: float = DEFAULT_BASIS_FRACTION,
    min_total_delta_pct: float = 0.0,
    output_root: Path | str | None = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    frame = load_edge_ledger(ledger_path)
    baseline = _baseline_payload(frame, basis_fraction=float(basis_fraction))
    candidates: list[dict[str, Any]] = []
    for spec in POLICY_SPECS:
        policy = _apply_policy(frame, spec)
        comparison = _compare(policy, baseline, min_total_delta_pct=float(min_total_delta_pct))
        candidates.append({"policy": policy, "comparison": comparison})
    candidates.sort(key=_sort_key, reverse=True)
    best = candidates[0]
    gate = {
        "verdict": "P2_RISK_POLICY_CANDIDATE" if best["comparison"]["p2_candidate_pass"] else "P2_RISK_POLICY_NO_GO",
        "best_policy_id": best["policy"]["policy_id"],
        "candidate_p2_pass": bool(best["comparison"]["p2_candidate_pass"]),
        "implementation_unlocked": False,
        "unlock_note": (
            "Research candidate only: policy was selected by this lab and requires preregistered fresh OOS/forward validation before RL implementation unlock."
            if best["comparison"]["p2_candidate_pass"]
            else "No policy met risk-adjusted, drawdown, and total non-inferiority gates."
        ),
        "min_total_delta_pct": float(min_total_delta_pct),
    }
    payload: dict[str, Any] = {
        "artifact_type": "risk_policy_lab",
        "run_id": run_id,
        "fill_mode": fill_mode,
        "input_kind": "probability_lane_edge_ledger",
        "edge_ledger_path": str(ledger_path),
        "strategy_label": STRATEGY_LABEL,
        "baseline_label": BASELINE_LABEL,
        "guardrail": GUARDRAIL,
        "cost_bps": 23.0,
        "basis_fraction": float(basis_fraction),
        "selection_bias_note": "Policies are deterministic, but choosing the best policy after this full OOS review is hypothesis generation, not deployable model proof.",
        "baseline": baseline,
        "best": best,
        "candidates": candidates,
        "gate": gate,
    }
    output = _ensure_under_root(Path(output_path), Path(output_root) if output_root is not None else None)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["output_path"] = str(output)
    return payload


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edge-ledger", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--fill-mode", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--basis-fraction", type=float, default=DEFAULT_BASIS_FRACTION)
    parser.add_argument("--min-total-delta-pct", type=float, default=0.0)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_risk_policy_lab(
        args.edge_ledger,
        args.output,
        run_id=str(args.run_id),
        fill_mode=str(args.fill_mode),
        basis_fraction=float(args.basis_fraction),
        min_total_delta_pct=float(args.min_total_delta_pct),
        output_root=Path(args.output_root) if args.output_root else None,
    )
    print(json.dumps({"output_path": payload["output_path"], "gate": payload["gate"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
