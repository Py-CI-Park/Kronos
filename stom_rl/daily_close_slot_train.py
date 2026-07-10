"""Training/baseline runner for the daily close-slot research lane.

This module consumes an explicit close-slot dataset run id and manifest hash,
then emits research-only score tables and baseline ledgers. It is intentionally
not a live, broker, account, order, paper-forward, or profitability surface.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .daily_close_slot_dataset import (
    COST_MODEL_SCHEMA_VERSION,
    COST_SENSITIVITY_BP,
    DEFAULT_CLOSE_SLOT_DATASET_ROOT,
    DEFAULT_SLOT_COUNT,
    DEFAULT_TOTAL_CAPITAL_KRW,
    REPO_ROOT,
    FILL_MODE,
    ROUND_TRIP_COST_BP,
    validate_close_slot_dataset_lineage,
)
from .daily_close_slot_env import (
    COST_SCENARIO_BASE_23BP,
    COST_SCENARIO_STRESS_46BP,
    COST_SCENARIO_ZERO_CONTROL_0BP,
    COST_SCENARIOS,
    evaluate_close_slot_day,
)
from .rl_events import RlLiveEventWriter

DEFAULT_CLOSE_SLOT_TRAIN_ROOT = REPO_ROOT / "webui" / "rl_runs" / "daily_close_slot_train"
LIVE_EVENTS_FILE_NAME = "rl_live_events.jsonl"
CLOSE_SLOT_TRAIN_SCHEMA_VERSION = 2
TRAIN_LINEAGE_SCHEMA_VERSION = 1
RUN_ID_RE = re.compile(r"^(?=.*[0-9A-Za-z])[0-9A-Za-z_.-]+$")
POLICY_CONTEXTUAL_BANDIT = "contextual_bandit_linear_train_only_score_and_pick"
POLICY_MOMENTUM = "momentum_top10_score_and_pick"
POLICY_SHUFFLE = "deterministic_shuffle_top10_control"
POLICY_NO_TRADE = "no_trade_control"
POLICY_D3_FROZEN = "frozen_d3_reledgered_score_and_pick"
POLICY_CONTEXTUAL_BANDIT_TOP10_DIAGNOSTIC = "contextual_bandit_linear_top10_forced_diagnostic"
TRAIN_REPLAY_MODE_ID = "expanding_train_replay_reward_weighted_refit_v1"
PRIMARY_COST_SCENARIO_ID = COST_SCENARIO_BASE_23BP
COST_SCENARIO_IDS = (COST_SCENARIO_ZERO_CONTROL_0BP, COST_SCENARIO_BASE_23BP, COST_SCENARIO_STRESS_46BP)
FALSE_GUARDRAIL_FLAGS = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}


@dataclass(frozen=True)
class CloseSlotTrainConfig:
    dataset_run_id: str
    dataset_manifest_sha: str
    dataset_artifact_root: str | Path = DEFAULT_CLOSE_SLOT_DATASET_ROOT
    output_root: str | Path = DEFAULT_CLOSE_SLOT_TRAIN_ROOT
    run_id: str | None = None
    total_capital_krw: int = DEFAULT_TOTAL_CAPITAL_KRW
    slot_count: int = DEFAULT_SLOT_COUNT
    cost_bp: int = ROUND_TRIP_COST_BP
    seed: int = 100
    frozen_d3_score_path: str | Path | None = None
    replay_mode_id: str = TRAIN_REPLAY_MODE_ID
    min_fit_dates: int = 60
    replay_window_dates: int = 20
    freeze_cadence_dates: int = 20
    overwrite: bool = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_run_id(run_id: str) -> str:
    rid = str(run_id or "").strip()
    if not RUN_ID_RE.fullmatch(rid) or rid in {".", ".."} or ".." in rid:
        raise ValueError(f"unsafe run_id: {run_id!r}")
    return rid


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha_json(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fallback_fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        fieldnames = sorted({key for row in rows for key in row.keys()})
    else:
        fieldnames = list(fallback_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _candidate_code(row: Mapping[str, Any]) -> str:
    return str(row.get("code") or "").strip().zfill(6)


def _row_feature_names(rows: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]) -> list[str]:
    names = [str(name) for name in manifest.get("feature_columns") or []]
    available = set(rows[0].keys()) if rows else set()
    return [name for name in names if name in available and name not in {"future_return_1d"}]


def _group_by_date(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("date")), []).append(dict(row))
    return {date: grouped[date] for date in sorted(grouped)}


def _load_dataset_manifest(dataset_artifact_root: str | Path, dataset_run_id: str, expected_manifest_sha: str) -> tuple[dict[str, Any], Path]:
    rid = _validate_run_id(dataset_run_id)
    if not str(expected_manifest_sha or "").strip():
        raise ValueError("dataset_manifest_sha is required")
    root = Path(dataset_artifact_root).resolve()
    manifest_path = (root / rid / "close_slot_dataset_manifest.json").resolve()
    try:
        manifest_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("dataset run escapes artifact root") from exc
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("run_id") != rid:
        raise ValueError("dataset manifest run_id mismatch")
    if manifest.get("manifest_sha") != expected_manifest_sha:
        raise ValueError("dataset manifest sha mismatch")
    lineage = validate_close_slot_dataset_lineage(manifest_path)
    if lineage.get("status") != "PASS":
        raise ValueError(f"dataset lineage validation failed: {lineage.get('errors')}")
    if manifest.get("lineage_validation_status") != "PASS":
        raise ValueError("dataset manifest lineage_validation_status is not PASS")
    return manifest, manifest_path


def load_close_slot_dataset_run(
    *,
    dataset_artifact_root: str | Path,
    dataset_run_id: str,
    dataset_manifest_sha: str,
) -> dict[str, Any]:
    manifest, manifest_path = _load_dataset_manifest(dataset_artifact_root, dataset_run_id, dataset_manifest_sha)
    panel_path = Path(str((manifest.get("artifacts") or {}).get("close_slot_panel"))).resolve()
    rows = _read_csv_rows(panel_path)
    return {"manifest": manifest, "manifest_path": str(manifest_path), "panel_rows": rows}


def _eligible_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in rows
        if str(row.get("eligible_for_selection", "True")).lower() in {"true", "1", "yes"}
        and _safe_float(row.get("future_return_1d")) is not None
        and _safe_float(row.get("entry_close")) is not None
        and _safe_float(row.get("next_close")) is not None
    ]


def _row_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("date")), _candidate_code(row))


def _fit_contextual_bandit_weights(
    rows: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
    feedback_weight_by_key: Mapping[tuple[str, str], float] | None = None,
) -> dict[str, Any]:
    """Fit a train-only linear score with per-feature standardization.

    Features are z-scored using train-split statistics *before* the weighted
    covariance fit, so a large-scale feature (e.g. institutional_net_buy ~1e6)
    can no longer dominate small-scale return features (~1e-2) after L1
    normalization. The fitted mean/std are frozen inside the returned model and
    re-applied at scoring time (see :func:`_contextual_bandit_score`); a missing
    feature imputes to the train mean (z=0). Returns a model dict (weights +
    scaler), not a bare weight map — scoring accepts either for back-compat.
    """
    weights: dict[str, float] = {name: 0.0 for name in feature_names}
    feature_mean: dict[str, float] = {name: 0.0 for name in feature_names}
    feature_std: dict[str, float] = {name: 0.0 for name in feature_names}
    model: dict[str, Any] = {
        "weights": weights,
        "feature_mean": feature_mean,
        "feature_std": feature_std,
        "fit_method": "train_only_zscore_covariance_l1_v1",
    }
    train_rows = [row for row in _eligible_rows(rows) if str(row.get("split")) == "train"]
    if not train_rows:
        return model
    sample_weights = [
        max(0.0, float((feedback_weight_by_key or {}).get(_row_key(row), 1.0)))
        for row in train_rows
    ]
    weight_sum = sum(sample_weights) or 1.0
    labels = [_safe_float(row.get("future_return_1d")) or 0.0 for row in train_rows]
    label_mean = sum(label * weight for label, weight in zip(labels, sample_weights)) / weight_sum
    # Pass 1 — frozen per-feature train mean/std (weighted, missing values skipped).
    for name in feature_names:
        pairs = [
            (float(value), sample_weight)
            for value, sample_weight in zip(
                (_safe_float(row.get(name)) for row in train_rows), sample_weights
            )
            if value is not None
        ]
        if not pairs:
            continue
        pair_weight_sum = sum(sample_weight for _value, sample_weight in pairs) or 1.0
        mean = sum(value * sample_weight for value, sample_weight in pairs) / pair_weight_sum
        variance = sum((value - mean) ** 2 * sample_weight for value, sample_weight in pairs) / pair_weight_sum
        feature_mean[name] = mean
        feature_std[name] = math.sqrt(max(0.0, variance))
    # Pass 2 — weighted covariance of the STANDARDIZED feature against the label.
    raw: dict[str, float] = {}
    for name in feature_names:
        mean = feature_mean[name]
        std = feature_std[name]
        triples = [
            ((float(value) - mean) / std if std > 1e-9 else 0.0, label, sample_weight)
            for value, label, sample_weight in zip(
                (_safe_float(row.get(name)) for row in train_rows), labels, sample_weights
            )
            if value is not None
        ]
        if not triples:
            raw[name] = 0.0
            continue
        triple_weight_sum = sum(sample_weight for _z, _label, sample_weight in triples) or 1.0
        z_mean = sum(z * sample_weight for z, _label, sample_weight in triples) / triple_weight_sum
        raw[name] = (
            sum((z - z_mean) * (label - label_mean) * sample_weight for z, label, sample_weight in triples)
            / triple_weight_sum
        )
    normalizer = sum(abs(value) for value in raw.values()) or 1.0
    for name in feature_names:
        weights[name] = raw[name] / normalizer
    return model


def _feedback_weight_by_key(policy_payload: Mapping[str, Any]) -> dict[tuple[str, str], float]:
    weights: dict[tuple[str, str], float] = {}
    for ledger in policy_payload.get("date_ledgers", []):
        if str(ledger.get("split") or "") not in {"", "train"} and str(ledger.get("split")) != "train":
            continue
        for slot in ledger.get("ledger", []):
            code = str(slot.get("code") or "").zfill(6)
            if not code or code == "000000" or str(slot.get("slot_state")) == "cash_hold":
                continue
            slot_reward = abs(float(slot.get("net_return_on_total_capital") or 0.0))
            weights[(str(ledger.get("date")), code)] = 1.0 + min(4.0, slot_reward * 1000.0)
    return weights


def _contextual_bandit_score(row: Mapping[str, Any], model: Mapping[str, Any]) -> float:
    """Score a candidate under the fitted linear model.

    Applies the model's frozen train mean/std (z-score). A missing feature or a
    zero-variance feature contributes 0 (i.e. missing imputes to the train mean).
    A legacy bare weight map (no scaler keys) falls back to the raw dot product.
    """
    weights = model.get("weights") if "weights" in model else model
    feature_mean = model.get("feature_mean") or {}
    feature_std = model.get("feature_std") or {}
    if not feature_mean and not feature_std:
        return sum(float(weight) * float(_safe_float(row.get(name)) or 0.0) for name, weight in weights.items())
    total = 0.0
    for name, weight in weights.items():
        raw = _safe_float(row.get(name))
        std = float(feature_std.get(name, 0.0))
        if raw is None or std <= 1e-9:
            continue
        total += float(weight) * ((float(raw) - float(feature_mean.get(name, 0.0))) / std)
    return total


def _deterministic_shuffle_score(row: Mapping[str, Any], *, seed: int) -> float:
    payload = f"{int(seed)}|{row.get('date')}|{_candidate_code(row)}|{row.get('table')}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(16**16 - 1)


def _rows_with_policy_score(rows: Sequence[Mapping[str, Any]], policy: str, score_by_key: Mapping[tuple[str, str], float]) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        key = (str(row.get("date")), _candidate_code(row))
        item["score"] = float(score_by_key.get(key, 0.0))
        item["policy"] = policy
        item["code"] = _candidate_code(item)
        scored.append(item)
    return scored


def _score_table_for_policy(
    rows: Sequence[Mapping[str, Any]],
    *,
    policy: str,
    weights: Mapping[str, float] | None = None,
    seed: int = 100,
) -> list[dict[str, Any]]:
    score_by_key: dict[tuple[str, str], float] = {}
    for row in rows:
        key = (str(row.get("date")), _candidate_code(row))
        if policy == POLICY_CONTEXTUAL_BANDIT:
            score = _contextual_bandit_score(row, weights or {})
        elif policy == POLICY_MOMENTUM:
            score = _safe_float(row.get("candidate_score_causal_momentum"))
            if score is None:
                score = _safe_float(row.get("score")) or 0.0
        elif policy == POLICY_SHUFFLE:
            score = _deterministic_shuffle_score(row, seed=seed)
        else:
            score = 0.0
        score_by_key[key] = float(score)
    return _rows_with_policy_score(rows, policy, score_by_key)


def _threshold_text(threshold: float) -> str:
    return f"{float(threshold):.12g}"


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (len(sorted_values) - 1) * q
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(sorted_values[lower])
    weight = position - lower
    return float(sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight)


def _threshold_grid(train_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    scores = sorted(float(_safe_float(row.get("score")) or 0.0) for row in train_rows)
    if not scores:
        return [{"threshold": 0.0, "threshold_text": "0", "threshold_source": "empty_train_scores"}]
    minimum = scores[0]
    maximum = scores[-1]
    raw = [minimum - 1.0]
    raw.extend(_quantile(scores, step / 20.0) for step in range(21))
    raw.append(maximum + 1.0)
    grid: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, threshold in enumerate(raw):
        text = _threshold_text(threshold)
        if text in seen:
            continue
        seen.add(text)
        if index == 0:
            source = "below_min_sentinel"
        elif index == len(raw) - 1:
            source = "above_max_sentinel"
        else:
            source = f"quantile_{(index - 1) * 5:03d}"
        grid.append({"threshold": float(threshold), "threshold_text": text, "threshold_source": source})
    return grid


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    middle = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return float(sorted_values[middle])
    return float((sorted_values[middle - 1] + sorted_values[middle]) / 2.0)


def _evaluate_policy_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    policy: str,
    total_capital_krw: int,
    slot_count: int,
    cost_bp: int,
    selected_by_date: Mapping[str, Sequence[str]] | None = None,
    selection_threshold: float | None = None,
    threshold_text: str | None = None,
    cost_scenario_id: str = PRIMARY_COST_SCENARIO_ID,
    lineage: str = "train_v2",
    policy_action_allowed: bool = True,
) -> dict[str, Any]:
    by_date = _group_by_date(rows)
    date_ledgers: list[dict[str, Any]] = []
    policy_score_rows: list[dict[str, Any]] = []
    for date, date_rows in by_date.items():
        selected_codes = None if selected_by_date is None else selected_by_date.get(date, [])
        evaluated = evaluate_close_slot_day(
            date_rows,
            date=date,
            total_capital_krw=total_capital_krw,
            slot_count=slot_count,
            cost_bp=cost_bp,
            selected_codes=selected_codes,
            cost_scenario_id=cost_scenario_id,
            selection_threshold=selection_threshold,
            max_slot_count=slot_count,
        )
        normalized = evaluated["normalized_action"]
        ledger = dict(evaluated["ledger"])
        ledger.update(
            {
                "policy": policy,
                "threshold": selection_threshold,
                "threshold_text": threshold_text or ("" if selection_threshold is None else _threshold_text(selection_threshold)),
                "selected_count": int(ledger.get("selected_count", 0)),
                "hold_cash_count": int(ledger.get("hold_cash_count", 0)),
                "max_slot_count": int(ledger.get("max_slot_count", slot_count)),
                "cost_scenario_id": ledger.get("cost_scenario_id", cost_scenario_id),
                "lineage": lineage,
                "policy_action_allowed": bool(policy_action_allowed and selected_by_date is None),
            }
        )
        date_ledgers.append(ledger)
        selected_slots = {
            str((slot.get("candidate") or {}).get("code") or slot.get("code") or "").zfill(6): slot
            for slot in normalized.get("selection_slots", [])
            if slot.get("status") == "selected"
        }
        selected_count = int(normalized.get("selected_count", 0))
        hold_cash_count = int(normalized.get("hold_cash_count", 0))
        for ranked in normalized["ranked_candidates"]:
            code = ranked["code"]
            selected_slot = selected_slots.get(code)
            selected = selected_slot is not None
            policy_score_rows.append(
                {
                    "date": ranked["date"],
                    "split": next((str(row.get("split")) for row in date_rows if _candidate_code(row) == code), ""),
                    "table": ranked["table"],
                    "code": code,
                    "score": ranked["score"],
                    "policy": policy,
                    "threshold": ledger["threshold_text"],
                    "selection_threshold": ledger["threshold"],
                    "selected": selected,
                    "selection_reason": "selected_by_threshold" if selected else "cash_hold_threshold_or_rank",
                    "selected_count": selected_count,
                    "hold_cash_count": hold_cash_count,
                    "cost_scenario_id": ledger["cost_scenario_id"],
                    "lineage": lineage,
                    "policy_action_allowed": bool(policy_action_allowed and selected_by_date is None),
                    "slot_state_feedback": selected_slot.get("slot_state", "filled") if selected_slot else "cash_hold",
                }
            )
    total_net = sum(float(row["net_pnl_krw"]) for row in date_ledgers)
    total_cost = sum(float(row["cost_krw"]) for row in date_ledgers)
    rewards = [float(row["reward"]) for row in date_ledgers]
    filled_slots = sum(int(row["filled_slots"]) for row in date_ledgers)
    return {
        "policy": policy,
        "date_count": len(date_ledgers),
        "filled_slots": filled_slots,
        "total_net_pnl_krw": total_net,
        "total_cost_krw": total_cost,
        "mean_reward": sum(rewards) / len(rewards) if rewards else 0.0,
        "cumulative_reward": sum(rewards),
        "selection_threshold": selection_threshold,
        "threshold_text": threshold_text or ("" if selection_threshold is None else _threshold_text(selection_threshold)),
        "oos_rows_used_for_fit": 0,
        "date_ledgers": date_ledgers,
        "policy_score_rows": policy_score_rows,
    }


def _read_frozen_d3_scores(path: str | Path) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    score_path = Path(path)
    if score_path.suffix.lower() == ".json":
        raw = json.loads(score_path.read_text(encoding="utf-8"))
        rows = raw if isinstance(raw, list) else raw.get("rows", [])
    else:
        rows = _read_csv_rows(score_path)
    score_rows: list[dict[str, Any]] = []
    selected_by_date: dict[str, list[str]] = {}
    for row in rows:
        item = dict(row)
        code = _candidate_code(item)
        item["code"] = code
        item["score"] = _safe_float(item.get("score")) or 0.0
        item["policy"] = POLICY_D3_FROZEN
        score_rows.append(item)
        selected_flag = str(item.get("selected", item.get("selected_code", ""))).strip().lower()
        if selected_flag in {"1", "true", "yes", "y", code.lower()}:
            selected_by_date.setdefault(str(item.get("date")), []).append(code)
    return score_rows, selected_by_date


def _merge_score_rows(base_rows: Sequence[Mapping[str, Any]], score_rows: Sequence[Mapping[str, Any]], policy: str) -> list[dict[str, Any]]:
    score_by_key = {(str(row.get("date")), _candidate_code(row)): float(_safe_float(row.get("score")) or 0.0) for row in score_rows}
    return _rows_with_policy_score(base_rows, policy, score_by_key)


def _top_codes_by_date(rows: Sequence[Mapping[str, Any]], slot_count: int) -> dict[str, list[str]]:
    selected: dict[str, list[str]] = {}
    for date, date_rows in _group_by_date(rows).items():
        ranked = sorted(
            date_rows,
            key=lambda row: (-(float(_safe_float(row.get("score")) or 0.0)), _candidate_code(row), str(row.get("table") or "")),
        )
        selected[date] = [_candidate_code(row) for row in ranked[: int(slot_count)]]
    return selected


def _choose_train_threshold(
    scored_rows: Sequence[Mapping[str, Any]],
    *,
    total_capital_krw: int,
    slot_count: int,
    cost_bp: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    train_rows = [dict(row) for row in scored_rows if str(row.get("split")) == "train"]
    search_rows: list[dict[str, Any]] = []
    for threshold in _threshold_grid(train_rows):
        evaluated = _evaluate_policy_rows(
            train_rows,
            policy=POLICY_CONTEXTUAL_BANDIT,
            total_capital_krw=total_capital_krw,
            slot_count=slot_count,
            cost_bp=cost_bp,
            selection_threshold=float(threshold["threshold"]),
            threshold_text=str(threshold["threshold_text"]),
            lineage="threshold_search_train_only",
        )
        rewards = [float(row["reward"]) for row in evaluated["date_ledgers"]]
        selected_counts = [int(row["selected_count"]) for row in evaluated["date_ledgers"]]
        search_rows.append(
            {
                "window_id": "primary_train_fit",
                "split": "train",
                "fit_start_date": min((str(row.get("date")) for row in train_rows), default=""),
                "fit_end_date": max((str(row.get("date")) for row in train_rows), default=""),
                "fit_date_count": len(_group_by_date(train_rows)),
                "threshold": threshold["threshold"],
                "threshold_text": threshold["threshold_text"],
                "threshold_source": threshold["threshold_source"],
                "is_no_trade_sentinel": threshold["threshold_source"] == "above_max_sentinel",
                "mean_daily_reward_base_23bp": sum(rewards) / len(rewards) if rewards else 0.0,
                "median_daily_reward_base_23bp": _median(rewards),
                "mean_selected_count": sum(selected_counts) / len(selected_counts) if selected_counts else 0.0,
                "oos_rows_used_for_fit": 0,
                "chosen": False,
            }
        )
    chosen = sorted(
        search_rows,
        key=lambda row: (
            -float(row["mean_daily_reward_base_23bp"]),
            -float(row["median_daily_reward_base_23bp"]),
            # F2: prefer surfacing a signal over empty selection on reward ties
            # (was ascending mean_selected_count, which biased toward no-trade).
            -float(row["mean_selected_count"]),
            -float(row["threshold"]),
            str(row["threshold_text"]),
        ),
    )[0]
    chosen["chosen_is_no_trade_sentinel"] = bool(chosen.get("is_no_trade_sentinel", False))
    chosen["tie_break_policy"] = "reward_median_then_prefer_more_selections_v2"
    for row in search_rows:
        row["chosen"] = row["threshold_text"] == chosen["threshold_text"]
    return chosen, search_rows


def _walk_forward_artifacts(
    rows: Sequence[Mapping[str, Any]],
    policy_payload: Mapping[str, Any],
    threshold_grid: Sequence[Mapping[str, Any]],
    config: CloseSlotTrainConfig,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_date = _group_by_date(rows)
    train_dates = [date for date, date_rows in by_date.items() if any(str(row.get("split")) == "train" for row in date_rows)]
    oos_dates = [date for date in by_date if date not in set(train_dates)]
    min_fit_dates = min(int(config.min_fit_dates), len(train_dates)) if train_dates else 0
    replay_rounds = max(1, math.floor((len(train_dates) - min_fit_dates) / max(1, int(config.freeze_cadence_dates)))) if train_dates else 1
    threshold_text = str(policy_payload.get("threshold_text") or "")
    threshold = policy_payload.get("selection_threshold")
    windows = {
        "mode_id": config.replay_mode_id,
        "min_fit_dates": int(config.min_fit_dates),
        "effective_min_fit_dates": min_fit_dates,
        "replay_window_dates": int(config.replay_window_dates),
        "freeze_cadence_dates": int(config.freeze_cadence_dates),
        "replay_rounds": replay_rounds,
        "oos_rows_used_for_fit": 0,
        "threshold_grid": list(threshold_grid),
        "windows": [
            {
                "window_id": "primary_train_fit",
                "fit_split": "train",
                "fit_start_date": train_dates[0] if train_dates else "",
                "fit_end_date": train_dates[min_fit_dates - 1] if min_fit_dates else "",
                "frozen_replay_start_date": train_dates[min_fit_dates] if len(train_dates) > min_fit_dates else "",
                "frozen_replay_end_date": train_dates[-1] if train_dates else "",
                "freeze_time": _utc_now(),
                "threshold": threshold,
                "threshold_text": threshold_text,
                "feedback_source_split": "train",
                "held_out_replay_splits": ["val", "test"],
                "oos_rows_used_for_fit": 0,
            },
            {
                "window_id": "held_out_val_test_replay",
                "fit_split": "train",
                "fit_start_date": train_dates[0] if train_dates else "",
                "fit_end_date": train_dates[-1] if train_dates else "",
                "frozen_replay_start_date": oos_dates[0] if oos_dates else "",
                "frozen_replay_end_date": oos_dates[-1] if oos_dates else "",
                "freeze_time": _utc_now(),
                "threshold": threshold,
                "threshold_text": threshold_text,
                "feedback_source_split": "none_frozen_held_out",
                "held_out_replay_splits": ["val", "test"],
                "oos_rows_used_for_fit": 0,
            },
        ],
    }
    replay_ledgers: list[dict[str, Any]] = []
    for ledger in policy_payload.get("date_ledgers", []):
        split = next((str(row.get("split")) for row in rows if str(row.get("date")) == str(ledger.get("date"))), "")
        slot_feedback = []
        for slot in ledger.get("ledger", []):
            state = str(slot.get("slot_state") or "")
            if state == "filled":
                feedback = "success" if float(slot.get("net_pnl_krw") or 0.0) > 0 else "failure"
            elif state == "cash_hold":
                feedback = "neutral_cash_hold"
            else:
                feedback = "failure"
            slot_feedback.append(
                {
                    "slot": slot.get("slot"),
                    "code": slot.get("code"),
                    "slot_state": state,
                    "feedback": feedback,
                    "feedback_weight": 1 + min(4.0, abs(float(slot.get("net_return_on_total_capital") or 0.0)) * 1000),
                    "feedback_used_for_fit": split == "train" and feedback in {"success", "failure"},
                }
            )
        replay_ledgers.append(
            {
                "replay_split": split,
                "date": ledger.get("date"),
                "policy": ledger.get("policy"),
                "threshold": ledger.get("threshold"),
                "threshold_text": ledger.get("threshold_text"),
                "selected_count": ledger.get("selected_count"),
                "hold_cash_count": ledger.get("hold_cash_count"),
                "cost_scenario_id": ledger.get("cost_scenario_id"),
                "slot_feedback": slot_feedback,
                "next_window_update": split == "train",
                "oos_rows_used_for_fit": 0,
            }
        )
    return replay_ledgers, windows


def _episode_ledgers_from_policy_payload(
    policy_payload: Mapping[str, Any],
    source_rows: Sequence[Mapping[str, Any]],
    *,
    window_id: str,
    only_splits: set[str] | None = None,
) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    split_by_date = {
        str(row.get("date")): str(row.get("split") or "")
        for row in source_rows
    }
    for ledger in policy_payload.get("date_ledgers", []):
        split = split_by_date.get(str(ledger.get("date")), "")
        if only_splits is not None and split not in only_splits:
            continue
        slot_feedback = []
        for slot in ledger.get("ledger", []):
            state = str(slot.get("slot_state") or "")
            if state == "filled":
                feedback = "success" if float(slot.get("net_pnl_krw") or 0.0) > 0 else "failure"
            elif state == "cash_hold":
                feedback = "neutral_cash_hold"
            else:
                feedback = "failure"
            slot_feedback.append(
                {
                    "slot": slot.get("slot"),
                    "code": slot.get("code"),
                    "slot_state": state,
                    "feedback": feedback,
                    "feedback_weight": 1 + min(4.0, abs(float(slot.get("net_return_on_total_capital") or 0.0)) * 1000),
                    "feedback_used_for_fit": split == "train" and feedback in {"success", "failure"},
                }
            )
        episodes.append(
            {
                "window_id": window_id,
                "replay_split": split,
                "date": ledger.get("date"),
                "policy": ledger.get("policy"),
                "threshold": ledger.get("threshold"),
                "threshold_text": ledger.get("threshold_text"),
                "selected_count": ledger.get("selected_count"),
                "hold_cash_count": ledger.get("hold_cash_count"),
                "cost_scenario_id": ledger.get("cost_scenario_id"),
                "reward": ledger.get("reward"),
                "net_pnl_krw": ledger.get("net_pnl_krw"),
                "cost_krw": ledger.get("cost_krw"),
                "filled_slots": ledger.get("filled_slots"),
                "slot_feedback": slot_feedback,
                "next_window_update": split == "train",
                "oos_rows_used_for_fit": 0,
            }
        )
    return episodes


def _expanding_refit_artifacts(
    rows: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
    config: CloseSlotTrainConfig,
    *,
    event_writer: "RlLiveEventWriter | None" = None,
) -> dict[str, Any]:
    by_date = _group_by_date(rows)
    train_dates = [
        date
        for date, date_rows in by_date.items()
        if any(str(row.get("split")) == "train" for row in date_rows)
    ]
    train_rows_all = [row for row in rows if str(row.get("split")) == "train"]
    feedback_weights: dict[tuple[str, str], float] = {}
    threshold_search_rows: list[dict[str, Any]] = []
    replay_episode_ledgers: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    fit_count = min(max(1, int(config.min_fit_dates)), len(train_dates)) if train_dates else 0
    replay_span = max(1, int(config.replay_window_dates))
    freeze_cadence = max(1, int(config.freeze_cadence_dates))
    first_threshold_text = ""
    final_weights = _fit_contextual_bandit_weights(train_rows_all, feature_names)
    final_chosen: dict[str, Any] = {
        "threshold": 0.0,
        "threshold_text": "0",
        "mean_daily_reward_base_23bp": 0.0,
        "median_daily_reward_base_23bp": 0.0,
        "mean_selected_count": 0.0,
    }
    final_threshold_grid: list[dict[str, Any]] = _threshold_grid([])

    window_index = 0
    while train_dates and fit_count:
        window_id = f"train_replay_refit_{window_index:03d}"
        fit_dates = train_dates[:fit_count]
        replay_start = fit_count
        replay_end = min(len(train_dates), replay_start + replay_span)
        replay_dates = train_dates[replay_start:replay_end]
        if not replay_dates:
            break
        fit_rows = [row for row in train_rows_all if str(row.get("date")) in set(fit_dates)]
        window_weights = _fit_contextual_bandit_weights(fit_rows, feature_names, feedback_weights)
        scored_fit_rows = _score_table_for_policy(fit_rows, policy=POLICY_CONTEXTUAL_BANDIT, weights=window_weights)
        chosen, search_rows = _choose_train_threshold(
            scored_fit_rows,
            total_capital_krw=config.total_capital_krw,
            slot_count=config.slot_count,
            cost_bp=config.cost_bp,
        )
        if not first_threshold_text:
            first_threshold_text = str(chosen["threshold_text"])
        for row in search_rows:
            annotated = dict(row)
            annotated["window_id"] = window_id
            threshold_search_rows.append(annotated)

        replay_rows = [row for row in train_rows_all if str(row.get("date")) in set(replay_dates)]
        replay_scored_rows = _score_table_for_policy(replay_rows, policy=POLICY_CONTEXTUAL_BANDIT, weights=window_weights)
        replay_payload = _evaluate_policy_rows(
            replay_scored_rows,
            policy=POLICY_CONTEXTUAL_BANDIT,
            total_capital_krw=config.total_capital_krw,
            slot_count=config.slot_count,
            cost_bp=config.cost_bp,
            selection_threshold=float(chosen["threshold"]),
            threshold_text=str(chosen["threshold_text"]),
            lineage=window_id,
        )
        replay_episode_ledgers.extend(
            _episode_ledgers_from_policy_payload(replay_payload, replay_rows, window_id=window_id)
        )
        replay_date_ledgers = replay_payload["date_ledgers"]
        replay_selected_counts = [int(ledger.get("selected_count") or 0) for ledger in replay_date_ledgers]
        if event_writer is not None:
            event_writer.write_step(
                algorithm="contextual_bandit",
                phase="walk_forward",
                global_step=window_index,
                reward=replay_payload.get("mean_reward"),
                source="daily_close_slot_train",
                info={"window_id": window_id, "threshold_text": str(chosen["threshold_text"])},
            )
        feedback_weights.update(_feedback_weight_by_key(replay_payload))
        windows.append(
            {
                "window_id": window_id,
                "fit_split": "train",
                "fit_start_date": fit_dates[0] if fit_dates else "",
                "fit_end_date": fit_dates[-1] if fit_dates else "",
                "frozen_replay_start_date": replay_dates[0] if replay_dates else "",
                "frozen_replay_end_date": replay_dates[-1] if replay_dates else "",
                "freeze_time": _utc_now(),
                "threshold": chosen["threshold"],
                "threshold_text": chosen["threshold_text"],
                "feedback_source_split": "train",
                "held_out_replay_splits": [],
                "feedback_weighted_refit_used": bool(feedback_weights),
                "feedback_weighted_train_rows": len(feedback_weights),
                "oos_rows_used_for_fit": 0,
                "replay_mean_reward_base_23bp": replay_payload.get("mean_reward"),
                "replay_cumulative_reward": replay_payload.get("cumulative_reward"),
                "mean_selected_count": (
                    sum(replay_selected_counts) / len(replay_selected_counts) if replay_selected_counts else 0.0
                ),
                "date_count": replay_payload.get("date_count"),
            }
        )
        if fit_count >= len(train_dates):
            break
        fit_count = min(len(train_dates), fit_count + freeze_cadence)
        window_index += 1

    if train_rows_all:
        final_weights = _fit_contextual_bandit_weights(train_rows_all, feature_names, feedback_weights)
        final_scored_fit_rows = _score_table_for_policy(train_rows_all, policy=POLICY_CONTEXTUAL_BANDIT, weights=final_weights)
        final_chosen, final_search_rows = _choose_train_threshold(
            final_scored_fit_rows,
            total_capital_krw=config.total_capital_krw,
            slot_count=config.slot_count,
            cost_bp=config.cost_bp,
        )
        for row in final_search_rows:
            annotated = dict(row)
            annotated["window_id"] = "final_train_refit_for_held_out"
            threshold_search_rows.append(annotated)
        final_threshold_grid = _threshold_grid(final_scored_fit_rows)

    oos_dates = [date for date, date_rows in by_date.items() if any(str(row.get("split")) in {"val", "test"} for row in date_rows)]
    windows.append(
        {
            "window_id": "final_held_out_val_test_replay",
            "fit_split": "train",
            "fit_start_date": train_dates[0] if train_dates else "",
            "fit_end_date": train_dates[-1] if train_dates else "",
            "frozen_replay_start_date": oos_dates[0] if oos_dates else "",
            "frozen_replay_end_date": oos_dates[-1] if oos_dates else "",
            "freeze_time": _utc_now(),
            "threshold": final_chosen["threshold"],
            "threshold_text": final_chosen["threshold_text"],
            "feedback_source_split": "none_frozen_held_out",
            "held_out_replay_splits": ["val", "test"],
            "feedback_weighted_refit_used": bool(feedback_weights),
            "feedback_weighted_train_rows": len(feedback_weights),
            "oos_rows_used_for_fit": 0,
        }
    )
    return {
        "weights": final_weights,
        "chosen_threshold": final_chosen,
        "initial_threshold_text": first_threshold_text or final_chosen["threshold_text"],
        "feedback_weights": feedback_weights,
        "threshold_search_rows": threshold_search_rows,
        "threshold_grid": final_threshold_grid,
        "replay_episode_ledgers": replay_episode_ledgers,
        "walk_forward_windows": {
            "mode_id": config.replay_mode_id,
            "min_fit_dates": int(config.min_fit_dates),
            "effective_min_fit_dates": min(max(1, int(config.min_fit_dates)), len(train_dates)) if train_dates else 0,
            "replay_window_dates": int(config.replay_window_dates),
            "freeze_cadence_dates": int(config.freeze_cadence_dates),
            "replay_rounds": len([window for window in windows if window["window_id"].startswith("train_replay_refit_")]),
            "oos_rows_used_for_fit": 0,
            "threshold_grid": final_threshold_grid,
            "feedback_weighted_refit": {
                "mode_id": config.replay_mode_id,
                "initial_threshold_text": first_threshold_text or final_chosen["threshold_text"],
                "final_threshold_text": final_chosen["threshold_text"],
                "feedback_weighted_train_rows": len(feedback_weights),
                "oos_rows_used_for_fit": 0,
            },
            "windows": windows,
        },
    }

def _cost_scenario_summary_rows(
    policies: Mapping[str, Mapping[str, Any]],
    base_rows_by_policy: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    total_capital_krw: int,
    slot_count: int,
    cost_bp: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for policy, payload in policies.items():
        threshold = payload.get("selection_threshold")
        selected_by_date = None
        if payload.get("selected_by_date") is not None:
            selected_by_date = payload.get("selected_by_date")
        if policy == POLICY_NO_TRADE:
            selected_by_date = {date: [] for date in _group_by_date(base_rows_by_policy[policy])}
        elif policy == POLICY_SHUFFLE:
            selected_by_date = _top_codes_by_date(base_rows_by_policy[policy], slot_count)
        for scenario_id in COST_SCENARIO_IDS:
            scenario_payload = _evaluate_policy_rows(
                base_rows_by_policy[policy],
                policy=policy,
                total_capital_krw=total_capital_krw,
                slot_count=slot_count,
                cost_bp=cost_bp,
                selected_by_date=selected_by_date,
                selection_threshold=threshold if policy == POLICY_CONTEXTUAL_BANDIT else None,
                threshold_text=payload.get("threshold_text"),
                cost_scenario_id=scenario_id,
                lineage="cost_scenario_summary",
                policy_action_allowed=policy not in {POLICY_SHUFFLE, POLICY_NO_TRADE, POLICY_D3_FROZEN},
            )
            scenario = COST_SCENARIOS[scenario_id]
            by_split: dict[str, list[dict[str, Any]]] = {}
            for ledger in scenario_payload["date_ledgers"]:
                split = next((str(row.get("split")) for row in base_rows_by_policy[policy] if str(row.get("date")) == str(ledger.get("date"))), "")
                by_split.setdefault(split, []).append(ledger)
            for split, ledgers in sorted(by_split.items()):
                slot_ledgers = [slot for ledger in ledgers for slot in ledger.get("ledger", [])]
                rows.append(
                    {
                        "policy": policy,
                        "split": split,
                        "cost_scenario_id": scenario_id,
                        "sell_tax_bp": scenario.sell_tax_bp,
                        "buy_commission_bp": scenario.buy_commission_bp,
                        "sell_commission_bp": scenario.sell_commission_bp,
                        "buy_slippage_bp": scenario.buy_slippage_bp,
                        "sell_slippage_bp": scenario.sell_slippage_bp,
                        "total_component_bp": scenario.total_bp,
                        "sell_tax_krw": sum(float(slot.get("sell_tax_krw") or 0.0) for slot in slot_ledgers),
                        "buy_commission_krw": sum(float(slot.get("buy_commission_krw") or 0.0) for slot in slot_ledgers),
                        "sell_commission_krw": sum(float(slot.get("sell_commission_krw") or 0.0) for slot in slot_ledgers),
                        "buy_slippage_krw": sum(float(slot.get("buy_slippage_krw") or 0.0) for slot in slot_ledgers),
                        "sell_slippage_krw": sum(float(slot.get("sell_slippage_krw") or 0.0) for slot in slot_ledgers),
                        "total_cost_krw": sum(float(ledger.get("cost_krw") or 0.0) for ledger in ledgers),
                        "reward": sum(float(ledger.get("reward") or 0.0) for ledger in ledgers),
                        "selected_count": sum(int(ledger.get("selected_count") or 0) for ledger in ledgers),
                        "hold_cash_count": sum(int(ledger.get("hold_cash_count") or 0) for ledger in ledgers),
                    }
                )
    return rows


def run_close_slot_training(
    config: CloseSlotTrainConfig,
    *,
    event_writer: "RlLiveEventWriter | None" = None,
) -> dict[str, Any]:
    dataset = load_close_slot_dataset_run(
        dataset_artifact_root=config.dataset_artifact_root,
        dataset_run_id=config.dataset_run_id,
        dataset_manifest_sha=config.dataset_manifest_sha,
    )
    dataset_manifest = dataset["manifest"]
    rows = dataset["panel_rows"]
    if int(config.cost_bp) != ROUND_TRIP_COST_BP:
        raise ValueError("close-slot training primary cost must remain 23bp; use gate sensitivity for 0/46bp variants")
    feature_names = _row_feature_names(rows, dataset_manifest)

    # Hoisted ahead of the (expensive) expanding refit so a live-events file can
    # be written to output_dir while training runs (F4). The non-empty-dir guard
    # allows exactly one pre-existing file here: the live-events log itself.
    rid = _validate_run_id(config.run_id or f"close_slot_train_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
    output_root = Path(config.output_root).resolve()
    output_dir = (output_root / rid).resolve()
    try:
        output_dir.relative_to(output_root)
    except ValueError as exc:
        raise ValueError("train run_id escapes output root") from exc
    if output_dir.exists():
        unexpected_names = {path.name for path in output_dir.iterdir()} - {LIVE_EVENTS_FILE_NAME}
        if unexpected_names and not config.overwrite:
            raise FileExistsError(f"close-slot train run already exists: {rid}")
    output_dir.mkdir(parents=True, exist_ok=True)

    refit_artifacts = _expanding_refit_artifacts(rows, feature_names, config, event_writer=event_writer)
    weights = refit_artifacts["weights"]
    chosen_threshold = refit_artifacts["chosen_threshold"]
    threshold_search_rows = refit_artifacts["threshold_search_rows"]
    threshold_grid = refit_artifacts["threshold_grid"]
    feedback_weights = refit_artifacts["feedback_weights"]
    contextual_rows = _score_table_for_policy(rows, policy=POLICY_CONTEXTUAL_BANDIT, weights=weights)

    policies: dict[str, dict[str, Any]] = {}
    base_rows_by_policy: dict[str, list[dict[str, Any]]] = {}
    no_trade_rows = _score_table_for_policy(rows, policy=POLICY_NO_TRADE)
    base_rows_by_policy[POLICY_NO_TRADE] = no_trade_rows
    no_trade_selected = {date: [] for date in _group_by_date(rows)}
    policies[POLICY_NO_TRADE] = _evaluate_policy_rows(
        no_trade_rows,
        policy=POLICY_NO_TRADE,
        total_capital_krw=config.total_capital_krw,
        slot_count=config.slot_count,
        cost_bp=config.cost_bp,
        selected_by_date=no_trade_selected,
        policy_action_allowed=False,
        lineage="baseline_no_trade",
    )
    shuffle_rows = _score_table_for_policy(rows, policy=POLICY_SHUFFLE, seed=config.seed)
    momentum_rows = _score_table_for_policy(rows, policy=POLICY_MOMENTUM)
    base_rows_by_policy.update(
        {
            POLICY_SHUFFLE: shuffle_rows,
            POLICY_MOMENTUM: momentum_rows,
            POLICY_CONTEXTUAL_BANDIT: contextual_rows,
        }
    )
    for policy, score_rows in [
        (POLICY_SHUFFLE, shuffle_rows),
        (POLICY_MOMENTUM, momentum_rows),
    ]:
        policies[policy] = _evaluate_policy_rows(
            score_rows,
            policy=policy,
            total_capital_krw=config.total_capital_krw,
            slot_count=config.slot_count,
            cost_bp=config.cost_bp,
            selected_by_date=_top_codes_by_date(score_rows, config.slot_count) if policy == POLICY_SHUFFLE else None,
            policy_action_allowed=policy != POLICY_SHUFFLE,
            lineage="baseline_control" if policy == POLICY_SHUFFLE else "baseline_momentum",
        )
    policies[POLICY_CONTEXTUAL_BANDIT] = _evaluate_policy_rows(
        contextual_rows,
        policy=POLICY_CONTEXTUAL_BANDIT,
        total_capital_krw=config.total_capital_krw,
        slot_count=config.slot_count,
        cost_bp=config.cost_bp,
        selection_threshold=float(chosen_threshold["threshold"]),
        threshold_text=str(chosen_threshold["threshold_text"]),
        lineage="primary_train_threshold_frozen_replay",
    )
    if event_writer is not None:
        running_net_pnl_krw = 0.0
        for step_index, ledger in enumerate(policies[POLICY_CONTEXTUAL_BANDIT]["date_ledgers"]):
            running_net_pnl_krw += float(ledger.get("net_pnl_krw") or 0.0)
            event_writer.write_step(
                algorithm="contextual_bandit",
                phase="primary_eval",
                global_step=step_index,
                reward=ledger.get("reward"),
                equity=running_net_pnl_krw,
                timestamp=str(ledger.get("date") or ""),
                source="daily_close_slot_train",
                info={"threshold_text": str(chosen_threshold["threshold_text"])},
            )
    # F2 diagnostic: what the fitted score would pick if forced to take the top
    # slots each day (no threshold). Separates "signal too weak to clear 23bp"
    # (threshold honestly picks cash) from "score degenerate". Research-only,
    # never a selectable/primary policy action.
    forced_top10_diagnostic = _evaluate_policy_rows(
        contextual_rows,
        policy=POLICY_CONTEXTUAL_BANDIT_TOP10_DIAGNOSTIC,
        total_capital_krw=config.total_capital_krw,
        slot_count=config.slot_count,
        cost_bp=config.cost_bp,
        selection_threshold=None,
        lineage="forced_top10_diagnostic_not_policy_action",
        policy_action_allowed=False,
    )

    d3_payload: dict[str, Any] | None = None
    if config.frozen_d3_score_path is not None:
        d3_score_rows, selected_by_date = _read_frozen_d3_scores(config.frozen_d3_score_path)
        d3_rows = _merge_score_rows(rows, d3_score_rows, POLICY_D3_FROZEN)
        base_rows_by_policy[POLICY_D3_FROZEN] = d3_rows
        d3_payload = _evaluate_policy_rows(
            d3_rows,
            policy=POLICY_D3_FROZEN,
            total_capital_krw=config.total_capital_krw,
            slot_count=config.slot_count,
            cost_bp=config.cost_bp,
            selected_by_date=selected_by_date,
            lineage="frozen_d3_reledgered_v2",
            policy_action_allowed=False,
        )
        d3_payload["reledgered_through_close_slot_accounting"] = True
        d3_payload["source_score_path"] = str(config.frozen_d3_score_path)
        d3_payload["selected_by_date"] = selected_by_date
        policies[POLICY_D3_FROZEN] = d3_payload

    replay_episode_ledgers = list(refit_artifacts["replay_episode_ledgers"])
    walk_forward_windows = dict(refit_artifacts["walk_forward_windows"])
    replay_episode_ledgers.extend(
        _episode_ledgers_from_policy_payload(
            policies[POLICY_CONTEXTUAL_BANDIT],
            rows,
            window_id="final_held_out_val_test_replay",
            only_splits={"val", "test"},
        )
    )
    cost_scenario_rows = _cost_scenario_summary_rows(
        policies,
        base_rows_by_policy,
        total_capital_krw=config.total_capital_krw,
        slot_count=config.slot_count,
        cost_bp=config.cost_bp,
    )


    all_score_rows = [row for policy in policies.values() for row in policy["policy_score_rows"]]
    policy_score_audit_fields = {
        "dataset_run_id": config.dataset_run_id,
        "dataset_manifest_sha": config.dataset_manifest_sha,
        "price_basis_status": dataset_manifest.get("price_basis_status"),
        "decision_grade_return_status": dataset_manifest.get("decision_grade_return_status"),
        "upstream_gate_blockers": "|".join(str(value) for value in dataset_manifest.get("upstream_gate_blockers", [])),
        "fill_mode": FILL_MODE,
        "execution_realism": dataset_manifest.get("execution_realism"),
        "round_trip_cost_bp": int(config.cost_bp),
        "primary_cost_scenario_id": PRIMARY_COST_SCENARIO_ID,
    }
    for row in all_score_rows:
        row.update(policy_score_audit_fields)
        row["primary_cost_scenario_id"] = PRIMARY_COST_SCENARIO_ID
    summary_rows = [
        {
            "policy": name,
            "date_count": payload["date_count"],
            "filled_slots": payload["filled_slots"],
            "total_net_pnl_krw": payload["total_net_pnl_krw"],
            "total_cost_krw": payload["total_cost_krw"],
            "mean_reward": payload["mean_reward"],
            "cumulative_reward": payload["cumulative_reward"],
            "selection_threshold": payload.get("selection_threshold"),
            "threshold_text": payload.get("threshold_text"),
            "oos_rows_used_for_fit": payload.get("oos_rows_used_for_fit", 0),
            "shuffle_baseline_only": name == POLICY_SHUFFLE,
            "policy_action_allowed": name not in {POLICY_SHUFFLE, POLICY_NO_TRADE, POLICY_D3_FROZEN},
        }
        for name, payload in policies.items()
    ]
    summary_rows.append(
        {
            "policy": POLICY_CONTEXTUAL_BANDIT_TOP10_DIAGNOSTIC,
            "date_count": forced_top10_diagnostic["date_count"],
            "filled_slots": forced_top10_diagnostic["filled_slots"],
            "total_net_pnl_krw": forced_top10_diagnostic["total_net_pnl_krw"],
            "total_cost_krw": forced_top10_diagnostic["total_cost_krw"],
            "mean_reward": forced_top10_diagnostic["mean_reward"],
            "cumulative_reward": forced_top10_diagnostic["cumulative_reward"],
            "selection_threshold": None,
            "threshold_text": "forced_top10_no_threshold",
            "oos_rows_used_for_fit": 0,
            "shuffle_baseline_only": False,
            "policy_action_allowed": False,
        }
    )
    paths = {
        "policy_scores": output_dir / "policy_scores.csv",
        "baseline_summary": output_dir / "baseline_summary.csv",
        "date_ledgers": output_dir / "date_ledgers.json",
        "threshold_search": output_dir / "threshold_search.csv",
        "walk_forward_windows": output_dir / "walk_forward_windows.json",
        "replay_episode_ledgers": output_dir / "replay_episode_ledgers.json",
        "cost_scenario_summary": output_dir / "cost_scenario_summary.csv",
        "train_manifest": output_dir / "close_slot_train_manifest.json",
    }
    _write_csv(paths["policy_scores"], all_score_rows, ["date", "split", "table", "code", "score", "policy"])
    _write_csv(paths["baseline_summary"], summary_rows, ["policy", "date_count", "filled_slots", "total_net_pnl_krw", "total_cost_krw", "mean_reward", "cumulative_reward"])
    _write_csv(paths["threshold_search"], threshold_search_rows, ["window_id", "split", "fit_start_date", "fit_end_date", "threshold", "mean_daily_reward_base_23bp", "median_daily_reward_base_23bp", "mean_selected_count", "chosen", "oos_rows_used_for_fit"])
    _write_csv(paths["cost_scenario_summary"], cost_scenario_rows, ["policy", "split", "cost_scenario_id", "sell_tax_bp", "buy_commission_bp", "sell_commission_bp", "buy_slippage_bp", "sell_slippage_bp", "total_component_bp", "total_cost_krw", "reward", "selected_count", "hold_cash_count"])
    _write_json(paths["date_ledgers"], {name: payload["date_ledgers"] for name, payload in policies.items()})
    _write_json(paths["walk_forward_windows"], walk_forward_windows)
    _write_json(paths["replay_episode_ledgers"], {"mode_id": config.replay_mode_id, "episodes": replay_episode_ledgers})
    artifact_hashes = {key: _file_sha(path) for key, path in paths.items() if key != "train_manifest"}
    manifest = {
        "schema_version": CLOSE_SLOT_TRAIN_SCHEMA_VERSION,
        "lineage_schema_version": TRAIN_LINEAGE_SCHEMA_VERSION,
        "created_at": _utc_now(),
        "artifact_kind": "daily_close_slot_train",
        "research_lane": "daily_close_slot",
        "status": dataset_manifest.get("status", "WATCH_RESEARCH_ONLY"),
        "readiness_status": dataset_manifest.get("readiness_status", dataset_manifest.get("status", "WATCH_RESEARCH_ONLY")),
        "guardrail": "EXPERIMENTAL_ONLY RESEARCH_ONLY; no live/broker/account/order/paper-forward/profitability claim.",
        "artifact_generation_allowed": True,
        **FALSE_GUARDRAIL_FLAGS,
        "run_id": rid,
        "artifact_dir": str(output_dir),
        "dataset_run_id": config.dataset_run_id,
        "dataset_manifest_sha": config.dataset_manifest_sha,
        "dataset_manifest_path": dataset["manifest_path"],
        "source_run_ids": {
            "dataset_run_id": config.dataset_run_id,
            "dataset_manifest_sha": config.dataset_manifest_sha,
        },
        "source_hashes": {
            "close_slot_panel_hash": (dataset_manifest.get("artifact_hashes") or {}).get("close_slot_panel"),
            "dataset_manifest_sha": config.dataset_manifest_sha,
        },
        "price_basis": dataset_manifest.get("price_basis"),
        "price_basis_status": dataset_manifest.get("price_basis_status"),
        "decision_grade_return_status": dataset_manifest.get("decision_grade_return_status"),
        "upstream_gate_blockers": dataset_manifest.get("upstream_gate_blockers", []),
        "dataset_db_access": dataset_manifest.get("daily_db_access"),
        "fill_mode": FILL_MODE,
        "execution_realism": dataset_manifest.get("execution_realism"),
        "round_trip_cost_bp": int(config.cost_bp),
        "cost_sensitivity_bp": list(COST_SENSITIVITY_BP),
        "cost_model_schema_version": COST_MODEL_SCHEMA_VERSION,
        "primary_cost_scenario_id": PRIMARY_COST_SCENARIO_ID,
        "cost_scenarios": {scenario_id: COST_SCENARIOS[scenario_id].as_payload() for scenario_id in COST_SCENARIO_IDS},
        "slot_count": int(config.slot_count),
        "total_capital_krw": int(config.total_capital_krw),
        "integer_shares_primary": True,
        "train_only_fit": True,
        "validation_test_no_retune": True,
        "shuffle_baseline_only": True,
        "replay_mode_id": config.replay_mode_id,
        "walk_forward_config": {
            "mode_id": config.replay_mode_id,
            "min_fit_dates": int(config.min_fit_dates),
            "replay_window_dates": int(config.replay_window_dates),
            "freeze_cadence_dates": int(config.freeze_cadence_dates),
            "oos_rows_used_for_fit": 0,
        },
        "threshold_selection": {
            "policy": POLICY_CONTEXTUAL_BANDIT,
            "split": "train",
            "threshold": chosen_threshold["threshold"],
            "threshold_text": chosen_threshold["threshold_text"],
            "metric": "mean_daily_reward_base_23bp",
            "tie_break": [
                "higher_median_daily_reward_base_23bp",
                "lower_mean_selected_count",
                "higher_threshold",
                "lexicographically_smallest_threshold_text",
            ],
            "oos_rows_used_for_fit": 0,
        },
        "feature_columns": feature_names,
        "fit_summary": {
            "policy": POLICY_CONTEXTUAL_BANDIT,
            "train_rows": sum(1 for row in _eligible_rows(rows) if str(row.get("split")) == "train"),
            "weights": weights,
            "fit_method": weights.get("fit_method") if isinstance(weights, Mapping) else None,
            "feature_standardized": True,
            "chosen_is_no_trade_sentinel": bool(chosen_threshold.get("chosen_is_no_trade_sentinel", False)),
            "oos_rows_used_for_fit": 0,
            "initial_threshold_text": refit_artifacts["initial_threshold_text"],
            "feedback_weighted_refit_used": True,
            "feedback_weighted_train_rows": len(feedback_weights),
            "selection_threshold": chosen_threshold["threshold"],
            "threshold_text": chosen_threshold["threshold_text"],
        },
        "forced_top10_diagnostic": {
            "policy": POLICY_CONTEXTUAL_BANDIT_TOP10_DIAGNOSTIC,
            "filled_slots": forced_top10_diagnostic["filled_slots"],
            "mean_reward": forced_top10_diagnostic["mean_reward"],
            "date_count": forced_top10_diagnostic["date_count"],
            "purpose": "separates weak-signal-cash from degenerate-score; not a policy action",
        },
        "required_baselines": [POLICY_NO_TRADE, POLICY_SHUFFLE, POLICY_MOMENTUM, POLICY_CONTEXTUAL_BANDIT],
        "policy_score_contract": {
            "audit_fields": sorted(policy_score_audit_fields),
            "selected_code_lists": "test_or_replay_adapter_only_not_policy_action",
            "policy_action": "deterministic threshold score-and-pick scores only",
            "shuffle_baseline_only": True,
            "v2_fields": [
                "threshold",
                "selected",
                "selection_reason",
                "selected_count",
                "hold_cash_count",
                "cost_scenario_id",
                "lineage",
                "slot_state_feedback",
            ],
        },
        "d3_comparator": {
            "present": d3_payload is not None,
            "reledgered_through_close_slot_accounting": bool(d3_payload),
            "source_score_path": str(config.frozen_d3_score_path) if config.frozen_d3_score_path else None,
        },
        "artifacts": {key: str(path) for key, path in paths.items() if key != "train_manifest"},
        "artifact_hashes": artifact_hashes,
        "row_counts": {
            "policy_score_rows": len(all_score_rows),
            "baseline_summary_rows": len(summary_rows),
            "date_count": len(_group_by_date(rows)),
            "threshold_search_rows": len(threshold_search_rows),
            "walk_forward_windows": len(walk_forward_windows.get("windows", [])),
            "replay_episode_ledgers": len(replay_episode_ledgers),
            "cost_scenario_summary_rows": len(cost_scenario_rows),
        },
        "summary": summary_rows,
    }
    manifest["manifest_sha"] = _sha_json(
        {
            "run_id": rid,
            "dataset_manifest_sha": config.dataset_manifest_sha,
            "artifact_hashes": artifact_hashes,
            "summary": summary_rows,
            "fit_summary": manifest["fit_summary"],
        }
    )
    _write_json(paths["train_manifest"], manifest)
    return {"manifest": manifest, "policies": policies, "paths": {key: str(path) for key, path in paths.items()}}


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run daily close-slot research baselines.")
    parser.add_argument("--dataset-run-id", required=True)
    parser.add_argument("--dataset-manifest-sha", required=True)
    parser.add_argument("--dataset-artifact-root", default=str(DEFAULT_CLOSE_SLOT_DATASET_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_CLOSE_SLOT_TRAIN_ROOT))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--total-capital-krw", type=int, default=DEFAULT_TOTAL_CAPITAL_KRW)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--frozen-d3-score-path", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    result = run_close_slot_training(
        CloseSlotTrainConfig(
            dataset_run_id=args.dataset_run_id,
            dataset_manifest_sha=args.dataset_manifest_sha,
            dataset_artifact_root=args.dataset_artifact_root,
            output_root=args.output_root,
            run_id=args.run_id,
            total_capital_krw=args.total_capital_krw,
            seed=args.seed,
            frozen_d3_score_path=args.frozen_d3_score_path,
            overwrite=args.overwrite,
        )
    )
    print(json.dumps({"manifest": result["manifest"], "paths": result["paths"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CLOSE_SLOT_TRAIN_SCHEMA_VERSION",
    "CloseSlotTrainConfig",
    "load_close_slot_dataset_run",
    "run_close_slot_training",
]
