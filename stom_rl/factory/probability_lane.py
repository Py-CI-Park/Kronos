"""Probability lane: calibrated P(win) meta-label gate with edge accounting.

This is a ``supervised gate`` experiment, NOT reinforcement learning. The
``ts_imb`` strategy remains a RULE baseline. Nothing here is a profit claim,
live-trading readiness claim, or broker integration.

Preregistrations:
- ``docs/stom_probability_lane_prereg_2026-06-11.md`` (mode ``edge_all``)
- ``docs/stom_probability_lane_stacked_prereg_2026-06-11.md`` (modes
  ``stacked_ts_imb`` primary and ``matched_threshold`` supporting)

All hypotheses, features, labels, folds, thresholds, and gates are frozen in
those documents; this module only executes them. Logged instances carry 25bp
net pct; the 23bp conversion adds ``+0.02`` percentage points (resume
2026-05-29 rule).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd  # noqa: PANDAS_OK - logged gap-up instances are tabular

from .walk_forward import Fold, chronological_folds, enforce_sample_power, fold_manifest

CAUSAL_FEATURES: tuple[str, ...] = (
    "entry_change_rate",
    "entry_trade_strength",
    "entry_bid_ask_imbalance",
    "entry_sec_amount",
    "entry_price",
)
OUTCOME_COLUMN = "tp5_sl1_net_pct"
COST_CONVERSION_PCT = 0.02  # 25bp cache -> 23bp round trip
DEFAULT_SEED = 100
DEFAULT_MIN_OOS_TAKE = 100
RELIABILITY_BINS = 10
LANE_MODES = ("edge_all", "stacked_ts_imb", "matched_threshold")
GUARDRAIL = (
    "supervised gate evidence, not RL, not live-ready, no profit claim; "
    "ts_imb remains a RULE baseline; cost basis 23bp via +0.02pp conversion"
)


@dataclass(frozen=True, slots=True)
class LaneConfig:
    """Frozen run configuration mirroring the preregistration documents."""

    run_id: str
    instances_path: Path
    output_dir: Path
    n_folds: int = 5
    seed: int = DEFAULT_SEED
    min_oos_take: int = DEFAULT_MIN_OOS_TAKE
    cost_bps: float = 23.0
    allow_few_folds: bool = False
    mode: str = "edge_all"
    prereg_doc: str = "docs/stom_probability_lane_prereg_2026-06-11.md"
    expected_split_hash: str = ""
    fill_mode: str = "unknown"
    parent_run: str | None = None


class ProbabilityLaneError(ValueError):
    """Raised when lane inputs violate the preregistered contract."""


def load_candidate_frame(instances_path: Path | str) -> pd.DataFrame:
    """Load logged gap-up candidates and apply the frozen 23bp conversion."""

    raw = json.loads(Path(instances_path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ProbabilityLaneError("instances artifact must be a non-empty list")
    frame = pd.DataFrame(raw)
    required = set(CAUSAL_FEATURES) | {OUTCOME_COLUMN, "session", "symbol", "pass_ts_imb"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ProbabilityLaneError(f"instances missing required columns: {missing}")
    frame = frame.copy()
    frame["symbol"] = frame["symbol"].astype(str)
    frame["session"] = frame["session"].astype(str)
    frame["net_pct_23bp"] = frame[OUTCOME_COLUMN].astype(float) + COST_CONVERSION_PCT
    frame["win"] = (frame["net_pct_23bp"] > 0.0).astype(int)
    frame = frame.dropna(subset=list(CAUSAL_FEATURES)).reset_index(drop=True)
    return frame


def _fit_calibrated_classifier(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    *,
    features: Sequence[str],
    seed: int,
):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.isotonic import IsotonicRegression

    clf = HistGradientBoostingClassifier(random_state=seed)
    clf.fit(train[list(features)].to_numpy(), train["win"].to_numpy())
    calibrator = None
    if len(validation) >= 10 and validation["win"].nunique() > 1:
        raw_val = clf.predict_proba(validation[list(features)].to_numpy())[:, 1]
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(raw_val, validation["win"].to_numpy())
    return clf, calibrator


def _predict_proba(clf, calibrator, frame: pd.DataFrame, features: Sequence[str]) -> np.ndarray:
    raw = clf.predict_proba(frame[list(features)].to_numpy())[:, 1]
    if calibrator is not None:
        raw = calibrator.predict(raw)
    return np.clip(raw.astype(float), 0.0, 1.0)


def _conditional_returns(in_sample: pd.DataFrame) -> tuple[float, float]:
    wins = in_sample.loc[in_sample["win"] == 1, "net_pct_23bp"]
    losses = in_sample.loc[in_sample["win"] == 0, "net_pct_23bp"]
    e_win = float(wins.mean()) if len(wins) else 0.0
    e_loss = float(losses.mean()) if len(losses) else 0.0
    return e_win, e_loss


def _edge(probabilities: np.ndarray, e_win: float, e_loss: float) -> np.ndarray:
    return probabilities * e_win + (1.0 - probabilities) * e_loss


def _brier(probabilities: np.ndarray, outcomes: np.ndarray) -> float:
    return float(np.mean((probabilities - outcomes) ** 2))


def _reliability_bins(probabilities: np.ndarray, outcomes: np.ndarray, bins: int = RELIABILITY_BINS) -> list[dict[str, Any]]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, Any]] = []
    for i in range(bins):
        lo, hi = float(edges[i]), float(edges[i + 1])
        mask = (probabilities >= lo) & (probabilities < hi if i < bins - 1 else probabilities <= hi)
        count = int(mask.sum())
        rows.append(
            {
                "bin": i,
                "lo": lo,
                "hi": hi,
                "count": count,
                "mean_predicted": float(probabilities[mask].mean()) if count else None,
                "observed_rate": float(outcomes[mask].mean()) if count else None,
            }
        )
    return rows


def _frame_for_sessions(frame: pd.DataFrame, sessions: Sequence[str]) -> pd.DataFrame:
    wanted = set(str(s) for s in sessions)
    return frame[frame["session"].isin(wanted)].reset_index(drop=True)


def _matched_threshold(
    clf,
    calibrator,
    validation: pd.DataFrame,
    *,
    features: Sequence[str],
    e_win: float,
    e_loss: float,
) -> float:
    """Per-fold threshold so the validation TAKE rate matches the ts_imb rate.

    Frozen in the stacked preregistration: tau is chosen on VALIDATION only;
    OOS is never used for threshold selection.
    """

    if validation.empty:
        return float("inf")
    ts_rate = float(validation["pass_ts_imb"].astype(bool).mean())
    if ts_rate <= 0.0:
        return float("inf")
    if ts_rate >= 1.0:
        return float("-inf")
    proba = _predict_proba(clf, calibrator, validation, features)
    edges = _edge(proba, e_win, e_loss)
    return float(np.quantile(edges, 1.0 - ts_rate))


def _evaluate_fold(
    frame: pd.DataFrame,
    fold: Fold,
    *,
    features: Sequence[str],
    seed: int,
    shuffle_labels: bool = False,
    rng: np.random.Generator | None = None,
    mode: str = "edge_all",
) -> dict[str, Any]:
    if mode not in LANE_MODES:
        raise ProbabilityLaneError(f"unknown lane mode: {mode!r}")
    train = _frame_for_sessions(frame, fold.train_sessions)
    validation = _frame_for_sessions(frame, fold.validation_sessions)
    oos = _frame_for_sessions(frame, fold.oos_sessions)
    if train.empty or oos.empty:
        raise ProbabilityLaneError(f"fold {fold.fold_id} has empty train or oos")
    if shuffle_labels:
        if rng is None:
            rng = np.random.default_rng(seed)
        train = train.copy()
        train["win"] = rng.permutation(train["win"].to_numpy())
        validation = validation.copy()
        if len(validation):
            validation["win"] = rng.permutation(validation["win"].to_numpy())
    clf, calibrator = _fit_calibrated_classifier(train, validation, features=features, seed=seed)
    e_win, e_loss = _conditional_returns(pd.concat([train, validation], ignore_index=True))

    if mode == "stacked_ts_imb":
        decision = oos[oos["pass_ts_imb"].astype(bool)].reset_index(drop=True)
    else:
        decision = oos
    if decision.empty:
        decision = decision.copy()

    proba = (
        _predict_proba(clf, calibrator, decision, features)
        if len(decision)
        else np.zeros(0, dtype=float)
    )
    edge = _edge(proba, e_win, e_loss)

    threshold = 0.0
    if mode == "matched_threshold":
        threshold = _matched_threshold(
            clf, calibrator, validation, features=features, e_win=e_win, e_loss=e_loss
        )
        take = edge >= threshold
    else:
        take = edge > 0.0

    outcomes = decision["win"].to_numpy(dtype=float) if len(decision) else np.zeros(0)
    base_rate = float(pd.concat([train, validation], ignore_index=True)["win"].mean())
    take_returns = decision.loc[take, "net_pct_23bp"] if len(decision) else pd.Series(dtype=float)
    ts_imb_mask = decision["pass_ts_imb"].astype(bool) if len(decision) else pd.Series(dtype=bool)
    ts_imb_returns = decision.loc[ts_imb_mask, "net_pct_23bp"] if len(decision) else pd.Series(dtype=float)
    skipped_returns = decision.loc[~take, "net_pct_23bp"] if len(decision) else pd.Series(dtype=float)

    ledger = [
        {
            "symbol": str(row.symbol),
            "session": str(row.session),
            "p_win": round(float(p), 6),
            "edge_pct": round(float(e), 6),
            "decision": "TAKE" if t else "SKIP",
            "net_pct_23bp": round(float(row.net_pct_23bp), 6),
        }
        for row, p, e, t in zip(decision.itertuples(index=False), proba, edge, take)
    ]
    return {
        "fold_id": fold.fold_id,
        "mode": mode,
        "edge_threshold": float(threshold) if math.isfinite(threshold) else None,
        "oos_candidates": int(len(decision)),
        "take_count": int(take.sum()) if len(decision) else 0,
        "take_mean_net_pct": float(take_returns.mean()) if len(take_returns) else None,
        "take_total_net_pct": float(take_returns.sum()) if len(take_returns) else 0.0,
        "take_all_mean_net_pct": float(decision["net_pct_23bp"].mean()) if len(decision) else None,
        "ts_imb_count": int(ts_imb_mask.sum()) if len(decision) else 0,
        "ts_imb_mean_net_pct": float(ts_imb_returns.mean()) if len(ts_imb_returns) else None,
        "skipped_count": int(len(skipped_returns)),
        "skipped_mean_net_pct": float(skipped_returns.mean()) if len(skipped_returns) else None,
        "skipped_total_net_pct": float(skipped_returns.sum()) if len(skipped_returns) else 0.0,
        "e_win_pct": e_win,
        "e_loss_pct": e_loss,
        "brier": _brier(proba, outcomes) if len(decision) else None,
        "brier_constant": _brier(np.full_like(proba, base_rate), outcomes) if len(decision) else None,
        "reliability_bins": _reliability_bins(proba, outcomes) if len(decision) else [],
        "edge_ledger": ledger,
    }


def _aggregate(fold_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    takes = [r for r in fold_rows if r["take_count"]]
    take_count = int(sum(r["take_count"] for r in fold_rows))
    weighted = [
        (r["take_mean_net_pct"], r["take_count"]) for r in takes if r["take_mean_net_pct"] is not None
    ]
    take_mean = (
        float(sum(m * c for m, c in weighted) / sum(c for _, c in weighted)) if weighted else None
    )
    counted = [r for r in fold_rows if r["oos_candidates"] and r["take_all_mean_net_pct"] is not None]
    all_counts = int(sum(r["oos_candidates"] for r in counted))
    take_all_mean = (
        float(sum(r["take_all_mean_net_pct"] * r["oos_candidates"] for r in counted) / all_counts)
        if all_counts
        else None
    )
    ts_counts = int(sum(r["ts_imb_count"] for r in fold_rows))
    ts_mean = (
        float(
            sum((r["ts_imb_mean_net_pct"] or 0.0) * r["ts_imb_count"] for r in fold_rows) / ts_counts
        )
        if ts_counts
        else None
    )
    briers = [r["brier"] for r in fold_rows if r.get("brier") is not None]
    briers_const = [r["brier_constant"] for r in fold_rows if r.get("brier_constant") is not None]
    skipped_count = int(sum(r.get("skipped_count", 0) for r in fold_rows))
    skipped_total = float(sum(r.get("skipped_total_net_pct", 0.0) for r in fold_rows))
    return {
        "oos_take_count": take_count,
        "oos_take_mean_net_pct": take_mean,
        "oos_take_total_net_pct": float(sum(r["take_total_net_pct"] for r in fold_rows)),
        "take_all_mean_net_pct": take_all_mean,
        "ts_imb_mean_net_pct": ts_mean,
        "ts_imb_count": ts_counts,
        "skipped_count": skipped_count,
        "skipped_total_net_pct": skipped_total,
        "skipped_mean_net_pct": (skipped_total / skipped_count) if skipped_count else None,
        "brier": float(np.mean(briers)) if briers else None,
        "brier_constant": float(np.mean(briers_const)) if briers_const else None,
    }


def _passes_g3(aggregate: Mapping[str, Any]) -> bool:
    take_mean = aggregate.get("oos_take_mean_net_pct")
    base_mean = aggregate.get("take_all_mean_net_pct")
    return take_mean is not None and base_mean is not None and take_mean > base_mean


def evaluate_gates(
    aggregate: Mapping[str, Any],
    shuffled_aggregate: Mapping[str, Any],
    ablation_rows: Sequence[Mapping[str, Any]],
    *,
    min_oos_take: int = DEFAULT_MIN_OOS_TAKE,
) -> dict[str, Any]:
    """Apply preregistered gates G1..G7 (mode ``edge_all``) and return evidence."""

    reasons: list[str] = []
    power = enforce_sample_power(int(aggregate["oos_take_count"]), min_required=min_oos_take)
    if not power["sufficient"]:
        reasons.append("insufficient_oos_take_trades")
    take_mean = aggregate.get("oos_take_mean_net_pct")
    if take_mean is None or take_mean <= 0.0:
        reasons.append("failed_absolute")
    if not _passes_g3(aggregate):
        reasons.append("failed_baseline:take_all")
    ts_mean = aggregate.get("ts_imb_mean_net_pct")
    if take_mean is None or ts_mean is None or take_mean < ts_mean:
        reasons.append("failed_baseline:ts_imb_rule")
    shuffled_beats_baseline = _passes_g3(shuffled_aggregate)
    if shuffled_beats_baseline:
        reasons.append("failed_controls")
    if aggregate.get("brier") is None or float(aggregate["brier"]) > float(aggregate["brier_constant"]):
        reasons.append("failed_calibration_skill")
    better = _ablations_better_than_full(aggregate, ablation_rows)
    if better >= 3:
        reasons.append("failed_ablations")
    return {
        "verdict": _verdict_from_reasons(reasons),
        "blocking_reasons": reasons,
        "sample_power": power,
        "ablations_better_than_full": better,
        "guardrail": GUARDRAIL,
    }


def _ablations_better_than_full(
    aggregate: Mapping[str, Any], ablation_rows: Sequence[Mapping[str, Any]]
) -> int:
    take_mean = aggregate.get("oos_take_mean_net_pct")
    base_mean = aggregate.get("take_all_mean_net_pct")
    full_margin = (take_mean - base_mean) if take_mean is not None and base_mean is not None else None
    better = 0
    for row in ablation_rows:
        m = row.get("oos_take_mean_net_pct")
        b = row.get("take_all_mean_net_pct")
        if m is not None and b is not None and full_margin is not None and (m - b) > full_margin:
            better += 1
    return better


def _verdict_from_reasons(reasons: Sequence[str]) -> str:
    verdict = "GO_CANDIDATE"
    if "insufficient_oos_take_trades" in reasons:
        verdict = "INCONCLUSIVE"
    if "failed_controls" in reasons or "failed_calibration_skill" in reasons:
        verdict = "NO-GO_CONTROL"
    elif "failed_ablations" in reasons:
        verdict = "NO-GO_ABLATION"
    elif any(r.startswith("failed_baseline") or r == "failed_fold_consistency" for r in reasons):
        verdict = "NO-GO_BASELINE"
    elif "failed_absolute" in reasons:
        verdict = "NO-GO"
    return verdict


def evaluate_stacked_gates(
    aggregate: Mapping[str, Any],
    fold_rows: Sequence[Mapping[str, Any]],
    shuffled_aggregate: Mapping[str, Any],
    ablation_rows: Sequence[Mapping[str, Any]],
    *,
    min_oos_take: int = DEFAULT_MIN_OOS_TAKE,
    min_consistent_folds: int = 3,
) -> dict[str, Any]:
    """Apply preregistered gates A-G1..A-G7 (mode ``stacked_ts_imb``).

    In stacked mode the decision universe is the ts_imb subset, so
    ``take_all_mean_net_pct`` equals the ts_imb-alone mean: A-G3 is the
    incremental-edge test against the RULE baseline.
    """

    reasons: list[str] = []
    power = enforce_sample_power(int(aggregate["oos_take_count"]), min_required=min_oos_take)
    if not power["sufficient"]:
        reasons.append("insufficient_oos_take_trades")
    take_mean = aggregate.get("oos_take_mean_net_pct")
    if take_mean is None or take_mean <= 0.0:
        reasons.append("failed_absolute")
    if not _passes_g3(aggregate):
        reasons.append("failed_baseline:ts_imb_rule")
    consistent = 0
    for row in fold_rows:
        m = row.get("take_mean_net_pct")
        b = row.get("take_all_mean_net_pct")
        if m is not None and b is not None and m > b:
            consistent += 1
    if consistent < min_consistent_folds:
        reasons.append("failed_fold_consistency")
    if _passes_g3(shuffled_aggregate):
        reasons.append("failed_controls")
    if aggregate.get("brier") is None or float(aggregate["brier"]) > float(aggregate["brier_constant"]):
        reasons.append("failed_calibration_skill")
    better = _ablations_better_than_full(aggregate, ablation_rows)
    if better >= 3:
        reasons.append("failed_ablations")
    return {
        "verdict": _verdict_from_reasons(reasons),
        "blocking_reasons": reasons,
        "sample_power": power,
        "consistent_folds": consistent,
        "min_consistent_folds": min_consistent_folds,
        "ablations_better_than_full": better,
        "guardrail": GUARDRAIL,
    }


def evaluate_matched_gates(
    aggregate: Mapping[str, Any],
    *,
    min_oos_take: int = DEFAULT_MIN_OOS_TAKE,
) -> dict[str, Any]:
    """Apply gates B-G1..B-G3 (mode ``matched_threshold``).

    Supporting evidence only: the stacked preregistration forbids claiming
    success from this experiment. Verdict labels are SUPPORTING_PASS /
    SUPPORTING_FAIL / INCONCLUSIVE.
    """

    reasons: list[str] = []
    power = enforce_sample_power(int(aggregate["oos_take_count"]), min_required=min_oos_take)
    if not power["sufficient"]:
        reasons.append("insufficient_oos_take_trades")
    take_count = int(aggregate.get("oos_take_count") or 0)
    ts_count = int(aggregate.get("ts_imb_count") or 0)
    ratio = (take_count / ts_count) if ts_count else None
    if ratio is None or not 0.8 <= ratio <= 1.2:
        reasons.append("failed_count_match")
    take_mean = aggregate.get("oos_take_mean_net_pct")
    ts_mean = aggregate.get("ts_imb_mean_net_pct")
    if take_mean is None or ts_mean is None or take_mean < ts_mean:
        reasons.append("failed_baseline:ts_imb_rule")
    if "insufficient_oos_take_trades" in reasons:
        verdict = "INCONCLUSIVE"
    elif reasons:
        verdict = "SUPPORTING_FAIL"
    else:
        verdict = "SUPPORTING_PASS"
    return {
        "verdict": verdict,
        "blocking_reasons": reasons,
        "sample_power": power,
        "take_to_ts_imb_ratio": ratio,
        "role": "supporting_evidence_only",
        "guardrail": GUARDRAIL,
    }


def run_probability_lane(config: LaneConfig) -> dict[str, Any]:
    """Execute the full preregistered lane and write artifacts."""

    if config.mode not in LANE_MODES:
        raise ProbabilityLaneError(f"unknown lane mode: {config.mode!r}")
    frame = load_candidate_frame(config.instances_path)
    sessions = sorted(frame["session"].unique().tolist())
    folds = chronological_folds(
        sessions, n_folds=config.n_folds, allow_few_folds=config.allow_few_folds
    )
    manifest = fold_manifest(folds, split_seed=config.seed)
    if config.expected_split_hash and manifest["split_hash"] != config.expected_split_hash:
        raise ProbabilityLaneError(
            "split hash mismatch: expected "
            f"{config.expected_split_hash}, got {manifest['split_hash']}; "
            "preregistration requires the frozen split"
        )

    fold_rows = [
        _evaluate_fold(frame, fold, features=CAUSAL_FEATURES, seed=config.seed, mode=config.mode)
        for fold in folds
    ]
    aggregate = _aggregate(fold_rows)

    shuffled_aggregate: dict[str, Any] | None = None
    ablation_results: list[dict[str, Any]] = []
    if config.mode in ("edge_all", "stacked_ts_imb"):
        shuffle_rng = np.random.default_rng(config.seed)
        shuffled_rows = [
            _evaluate_fold(
                frame,
                fold,
                features=CAUSAL_FEATURES,
                seed=config.seed,
                shuffle_labels=True,
                rng=shuffle_rng,
                mode=config.mode,
            )
            for fold in folds
        ]
        shuffled_aggregate = _aggregate(shuffled_rows)
        for dropped in CAUSAL_FEATURES:
            kept = tuple(f for f in CAUSAL_FEATURES if f != dropped)
            rows = [
                _evaluate_fold(frame, fold, features=kept, seed=config.seed, mode=config.mode)
                for fold in folds
            ]
            agg = _aggregate(rows)
            agg["ablation_id"] = f"no_{dropped}"
            ablation_results.append(agg)

    if config.mode == "edge_all":
        gates = evaluate_gates(
            aggregate, shuffled_aggregate or {}, ablation_results, min_oos_take=config.min_oos_take
        )
    elif config.mode == "stacked_ts_imb":
        gates = evaluate_stacked_gates(
            aggregate,
            fold_rows,
            shuffled_aggregate or {},
            ablation_results,
            min_oos_take=config.min_oos_take,
        )
    else:
        gates = evaluate_matched_gates(aggregate, min_oos_take=config.min_oos_take)

    payload: dict[str, Any] = {
        "artifact_type": "probability_lane_run",
        "run_id": config.run_id,
        "mode": config.mode,
        "decision_universe": "ts_imb" if config.mode == "stacked_ts_imb" else "all_candidates",
        "parent_run": config.parent_run,
        "prereg_doc": config.prereg_doc,
        "strategy_label": "supervised gate (meta-label), NOT RL",
        "cost_bps": config.cost_bps,
        "cost_conversion_pct": COST_CONVERSION_PCT,
        "seed": config.seed,
        "features": list(CAUSAL_FEATURES),
        "fill_mode": config.fill_mode,
        "outcome_column": OUTCOME_COLUMN,
        "candidate_count": int(len(frame)),
        "session_count": len(sessions),
        "split": manifest,
        "fold_thresholds": [
            {"fold_id": row["fold_id"], "edge_threshold": row["edge_threshold"]}
            for row in fold_rows
        ],
        "folds": [
            {k: v for k, v in row.items() if k not in {"edge_ledger", "reliability_bins"}}
            for row in fold_rows
        ],
        "aggregate": aggregate,
        "shuffled_label_control": shuffled_aggregate,
        "ablations": ablation_results,
        "gates": gates,
        "verdict": gates["verdict"],
        "guardrail": GUARDRAIL,
    }

    output_dir = Path(config.output_dir) / config.run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "probability_lane_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    calibration = {
        "artifact_type": "probability_lane_calibration",
        "run_id": config.run_id,
        "mode": config.mode,
        "brier": aggregate["brier"],
        "brier_constant": aggregate["brier_constant"],
        "folds": [
            {"fold_id": r["fold_id"], "brier": r["brier"], "reliability_bins": r["reliability_bins"]}
            for r in fold_rows
        ],
        "guardrail": GUARDRAIL,
    }
    (output_dir / "calibration.json").write_text(
        json.dumps(calibration, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ledger = {
        "artifact_type": "probability_lane_edge_ledger",
        "run_id": config.run_id,
        "mode": config.mode,
        "breakeven_note": "net pct already includes 23bp; breakeven edge is 0",
        "rows": [row for fold in fold_rows for row in fold["edge_ledger"]],
        "guardrail": GUARDRAIL,
    }
    (output_dir / "edge_ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    payload["output_dir"] = str(output_dir)
    return payload
