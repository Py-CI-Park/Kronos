"""Frozen risk-policy fresh validation gate.

This module validates the selected deterministic risk policy on data that was
not used to choose the policy.  It does not search thresholds, train RL, place
orders, or claim live/profit readiness.  Passing this gate only means the
restricted RL sizing/exit implementation may be considered next.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd  # noqa: PANDAS_OK - validation ledgers are tabular research artifacts

DEFAULT_OUTPUT_ROOT = Path("webui") / "rl_runs" / "fresh_policy_validation"
VALID_DECISIONS = {"TAKE", "SKIP"}
FRESH_SCOPES = {"fresh_oos", "fresh_forward"}
VALID_SCOPES = FRESH_SCOPES | {"current_replay", "smoke"}
POLICY_ID = "pwin_gt_040_size_050_100_halt_25"
MIN_P_WIN = 0.40
HIGH_P_WIN = 0.55
LOW_SIZE = 0.5
HIGH_SIZE = 1.0
HALT_LOSS_PCT = 2.5
BASIS_FRACTION = 0.5
COST_BPS = 23.0
BASELINE_LABEL = "same-fill ts_imb RULE baseline"
STRATEGY_LABEL = "frozen deterministic risk policy validation - NOT RL"
GUARDRAIL = (
    "Research-only frozen policy validation; no profit claim, no live-readiness, "
    "no broker/orders. ts_imb remains a RULE baseline; net pct assumes 23bp round-trip cost."
)


class FrozenPolicyValidationError(ValueError):
    """Raised when frozen-policy validation inputs violate the contract."""


@dataclass(frozen=True, slots=True)
class FrozenPolicyConfig:
    source_path: Path
    output_path: Path
    run_id: str
    fill_mode: str
    validation_scope: str
    min_total_delta_pct: float = 0.0
    min_trades: int = 100
    output_root: Path | None = DEFAULT_OUTPUT_ROOT


def _ensure_under_root(output_path: Path, output_root: Path | None) -> Path:
    path = output_path.expanduser().resolve(strict=False)
    if output_root is None:
        return path
    root = output_root.expanduser().resolve(strict=False)
    if path != root and not path.is_relative_to(root):
        raise FrozenPolicyValidationError(f"output path must be under generated fresh-validation root: {root}")
    return path


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise FrozenPolicyValidationError(f"JSONL line {line_no} is not an object")
        rows.append(payload)
    return rows


def _load_rows(source_path: Path | str) -> list[dict[str, Any]]:
    path = Path(source_path)
    if path.suffix.lower() == ".jsonl":
        rows = _load_jsonl(path)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise FrozenPolicyValidationError("validation source must be a JSON object or JSONL records")
        rows = payload.get("rows")
        if not isinstance(rows, list):
            raise FrozenPolicyValidationError("validation source JSON must contain a rows list")
    if not rows:
        raise FrozenPolicyValidationError("validation source rows must be non-empty")
    return rows


def load_validation_frame(source_path: Path | str) -> pd.DataFrame:
    """Load edge-ledger or forward-ledger rows into the frozen validation schema."""
    normalized: list[dict[str, Any]] = []
    for idx, row in enumerate(_load_rows(source_path)):
        if not isinstance(row, dict):
            raise FrozenPolicyValidationError(f"validation row {idx} is not an object")
        code = row.get("symbol", row.get("code"))
        session = row.get("session")
        decision = row.get("decision")
        p_win = row.get("p_win")
        edge_pct = row.get("edge_pct")
        outcome = row.get("net_pct_23bp")
        if outcome is None:
            outcome = row.get("realized_outcome_pct")
        baseline_outcome = row.get("baseline_outcome_pct")
        if baseline_outcome is None:
            baseline_outcome = outcome
        missing = [
            name
            for name, value in {
                "symbol/code": code,
                "session": session,
                "decision": decision,
                "p_win": p_win,
                "edge_pct": edge_pct,
                "net_pct_23bp/realized_outcome_pct": outcome,
            }.items()
            if value is None
        ]
        if missing:
            raise FrozenPolicyValidationError(f"validation row {idx} missing columns: {missing}")
        decision = str(decision)
        if decision not in VALID_DECISIONS:
            raise FrozenPolicyValidationError(f"validation row {idx} has invalid decision: {decision}")
        normalized.append(
            {
                "symbol": str(code),
                "session": str(session),
                "decision": decision,
                "p_win": float(p_win),
                "edge_pct": float(edge_pct),
                "outcome_pct_23bp": float(outcome),
                "baseline_outcome_pct_23bp": float(baseline_outcome),
            }
        )
    frame = pd.DataFrame(normalized)
    return frame.sort_values(["session", "symbol"], kind="mergesort").reset_index(drop=True)


def _curve_metrics(contributions_pct: Iterable[float]) -> dict[str, Any]:
    values = np.asarray(list(contributions_pct), dtype=float)
    if values.size == 0:
        raise FrozenPolicyValidationError("metric calculation received no contributions")
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


def _baseline_payload(frame: pd.DataFrame) -> dict[str, Any]:
    contributions = BASIS_FRACTION * frame["baseline_outcome_pct_23bp"].to_numpy(dtype=float)
    payload = _curve_metrics(contributions)
    payload.update(
        {
            "strategy_label": BASELINE_LABEL,
            "basis_fraction": BASIS_FRACTION,
            "n_source_rows": int(len(frame)),
            "n_sessions": int(frame["session"].nunique()),
        }
    )
    return payload


def _apply_frozen_policy(frame: pd.DataFrame) -> dict[str, Any]:
    take = frame[frame["decision"] == "TAKE"].copy()
    source_take_count = int(len(take))
    selected = take[take["p_win"] > MIN_P_WIN].copy()
    if selected.empty:
        raise FrozenPolicyValidationError("frozen policy selected no TAKE rows")
    sizes = np.where(
        selected["p_win"].to_numpy(dtype=float) >= HIGH_P_WIN,
        HIGH_SIZE,
        LOW_SIZE,
    )
    selected["size"] = sizes
    selected["contribution_pct"] = sizes * selected["outcome_pct_23bp"].to_numpy(dtype=float)

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
            if session_cum <= -HALT_LOSS_PCT:
                halted = True
        if halted:
            halted_sessions += 1

    metrics = _curve_metrics(contributions)
    metrics.update(
        {
            "policy_id": POLICY_ID,
            "description": "Frozen p_win bucket policy with causal per-session -2.5pp halt.",
            "strategy_label": STRATEGY_LABEL,
            "min_p_win": MIN_P_WIN,
            "high_p_win": HIGH_P_WIN,
            "low_size": LOW_SIZE,
            "high_size": HIGH_SIZE,
            "halt_loss_pct": HALT_LOSS_PCT,
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


def _compare(policy: Mapping[str, Any], baseline: Mapping[str, Any], *, min_total_delta_pct: float, min_trades: int) -> dict[str, Any]:
    p_ra = policy.get("risk_adjusted_mean_over_std")
    b_ra = baseline.get("risk_adjusted_mean_over_std")
    total_delta = float(policy["total_pct"]) - float(baseline["total_pct"])
    dd_delta = float(policy["max_drawdown_pct"]) - float(baseline["max_drawdown_pct"])
    risk_adjusted_improvement = p_ra is not None and b_ra is not None and float(p_ra) > float(b_ra)
    drawdown_improvement = dd_delta < 0.0
    total_noninferior = total_delta >= float(min_total_delta_pct)
    enough_trades = int(policy["n_trades"]) >= int(min_trades)
    return {
        "total_pct_delta": total_delta,
        "max_drawdown_delta": dd_delta,
        "risk_adjusted_delta": (float(p_ra) - float(b_ra)) if p_ra is not None and b_ra is not None else None,
        "risk_adjusted_improvement": bool(risk_adjusted_improvement),
        "drawdown_improvement": bool(drawdown_improvement),
        "total_noninferior": bool(total_noninferior),
        "min_trades": int(min_trades),
        "enough_trades": bool(enough_trades),
        "fresh_gate_pass": bool(risk_adjusted_improvement and drawdown_improvement and total_noninferior and enough_trades),
    }


def run_frozen_policy_validation(config: FrozenPolicyConfig) -> dict[str, Any]:
    if not config.run_id:
        raise FrozenPolicyValidationError("run_id is required")
    if not config.fill_mode:
        raise FrozenPolicyValidationError("fill_mode is required")
    scope = str(config.validation_scope)
    if scope not in VALID_SCOPES:
        raise FrozenPolicyValidationError(f"validation_scope must be one of {sorted(VALID_SCOPES)}")

    frame = load_validation_frame(config.source_path)
    baseline = _baseline_payload(frame)
    policy = _apply_frozen_policy(frame)
    comparison = _compare(
        policy,
        baseline,
        min_total_delta_pct=float(config.min_total_delta_pct),
        min_trades=int(config.min_trades),
    )
    is_fresh = scope in FRESH_SCOPES
    fresh_validation_pass = bool(is_fresh and comparison["fresh_gate_pass"])
    if not is_fresh:
        verdict = "NOT_FRESH_REPLAY"
    elif fresh_validation_pass:
        verdict = "FRESH_VALIDATION_PASS"
    else:
        verdict = "FRESH_VALIDATION_FAIL"

    payload: dict[str, Any] = {
        "artifact_type": "frozen_policy_fresh_validation",
        "schema_version": 1,
        "run_id": config.run_id,
        "fill_mode": config.fill_mode,
        "validation_scope": scope,
        "is_fresh_validation": is_fresh,
        "source_path": str(config.source_path),
        "strategy_label": STRATEGY_LABEL,
        "baseline_label": BASELINE_LABEL,
        "guardrail": GUARDRAIL,
        "cost_bps": COST_BPS,
        "selection_bias_guardrail": "Frozen parameters only; this command does not search or retune policy thresholds.",
        "baseline": baseline,
        "policy": policy,
        "comparison": comparison,
        "gate": {
            "verdict": verdict,
            "fresh_validation_pass": fresh_validation_pass,
            "implementation_unlocked": fresh_validation_pass,
            "unlock_note": (
                "Fresh validation passed; restricted RL sizing/exit implementation may be considered next under explicit research guardrails."
                if fresh_validation_pass
                else "Restricted RL remains locked until a fresh_oos or fresh_forward run passes all gates."
            ),
            "min_total_delta_pct": float(config.min_total_delta_pct),
            "min_trades": int(config.min_trades),
        },
    }
    output = _ensure_under_root(config.output_path, config.output_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["output_path"] = str(output)
    return payload


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="edge_ledger.json or forward ledger JSONL")
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--fill-mode", required=True)
    parser.add_argument("--validation-scope", required=True, choices=sorted(VALID_SCOPES))
    parser.add_argument("--min-total-delta-pct", type=float, default=0.0)
    parser.add_argument("--min-trades", type=int, default=100)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_frozen_policy_validation(
        FrozenPolicyConfig(
            source_path=Path(args.source),
            output_path=Path(args.output),
            run_id=str(args.run_id),
            fill_mode=str(args.fill_mode),
            validation_scope=str(args.validation_scope),
            min_total_delta_pct=float(args.min_total_delta_pct),
            min_trades=int(args.min_trades),
            output_root=Path(args.output_root) if args.output_root else None,
        )
    )
    print(json.dumps({"output_path": payload["output_path"], "gate": payload["gate"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
