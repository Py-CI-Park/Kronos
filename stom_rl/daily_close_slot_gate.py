"""Fail-closed gate for daily close-slot research artifacts.

The gate validates dataset-policy-gate lineage and required controls before any
metric is surfaced. It keeps the lane research-only and never promotes live,
broker, account, order, paper-forward, or profitability readiness.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .daily_close_slot_dataset import COST_SENSITIVITY_BP, FILL_MODE, REPO_ROOT, ROUND_TRIP_COST_BP, validate_close_slot_dataset_lineage
from .daily_close_slot_train import DEFAULT_CLOSE_SLOT_TRAIN_ROOT, PRIMARY_COST_SCENARIO_ID

DEFAULT_CLOSE_SLOT_GATE_ROOT = REPO_ROOT / "webui" / "rl_runs" / "daily_close_slot_gate"
CLOSE_SLOT_GATE_SCHEMA_VERSION = 1
GATE_LINEAGE_SCHEMA_VERSION = 1
RUN_ID_RE = re.compile(r"^(?=.*[0-9A-Za-z])[0-9A-Za-z_.-]+$")
REQUIRED_BASELINES = {"no_trade_control", "deterministic_shuffle_top10_control"}
REQUIRED_DB_ACCESS_CONTRACT = {
    "access_mode": "read_only",
    "sqlite_uri_mode": "ro",
    "pragma_query_only": True,
    "mutation_allowed": False,
    "connection_helper": "stom_rl.daily_ohlcv_db.connect_readonly",
}
STABLE_GATE_ERRORS = {
    "GATE_MISSING_SCHEMA_VERSION",
    "GATE_MISSING_TRAIN_RUN_ID",
    "GATE_HASH_MISMATCH",
    "GATE_FILE_MISSING",
    "GATE_ROW_COUNT_MISMATCH",
    "GATE_UNSAFE_PATH",
    "GATE_STALE_OPTIMISTIC_FLAGS",
    "GATE_MISSING_23BP",
    "GATE_MISSING_REQUIRED_BASELINE",
    "GATE_OOS_RETUNING_NOT_BLOCKED",
    "GATE_MISSING_SPLIT_EVIDENCE",
    "GATE_D3_NOT_RELEDGERED",
    "GATE_READY_STATUS_FOR_UNRESOLVED_D0_D1",
    "GATE_DATASET_LINEAGE_NOT_PASS",
    "GATE_DATASET_DB_ACCESS_NOT_READ_ONLY",
    "GATE_MISSING_POLICY_SCORE_AUDIT",
    "GATE_V2_COST_MODEL_SCHEMA_MISSING",
    "GATE_V2_COST_SCENARIO_MISSING_BASE_OR_STRESS",
    "GATE_V2_COST_COMPONENT_MISSING",
    "GATE_V2_COST_ROUND_TRIP_DERIVATION_MISMATCH",
    "GATE_V2_SCALAR_ONLY_COST_ACCOUNTING",
    "GATE_V2_COST_SCENARIO_ID_MISSING",
    "GATE_V2_WF_WINDOWS_MISSING",
    "GATE_V2_THRESHOLD_GRID_MISSING",
    "GATE_V2_THRESHOLD_OOS_LEAKAGE",
    "GATE_V2_FEEDBACK_SOURCE_NOT_TRAIN",
    "GATE_V2_OOS_ROWS_USED_FOR_FIT_NONZERO",
    "GATE_V2_HELD_OUT_FREEZE_MISSING",
    "GATE_V2_REPLAY_LEDGER_MISSING",
    "GATE_V2_SHUFFLE_POLICY_PROMOTION",
    "GATE_V2_SELECTED_HOLD_COUNT_INVALID",
}
FALSE_FLAG_NAMES = [
    "promotion_allowed",
    "model_build_allowed",
    "paper_forward_allowed",
    "live_broker_order_allowed",
    "profitability_claim_allowed",
    "go_summary_allowed",
]
REQUIRED_POLICY_SCORE_AUDIT_FIELDS = {
    "dataset_run_id",
    "dataset_manifest_sha",
    "price_basis_status",
    "decision_grade_return_status",
    "upstream_gate_blockers",
    "fill_mode",
    "execution_realism",
    "round_trip_cost_bp",
    "primary_cost_scenario_id",
}
REQUIRED_V2_COST_SCENARIOS = {
    "zero_control_0bp": {
        "sell_tax_bp": 0.0,
        "buy_commission_bp": 0.0,
        "sell_commission_bp": 0.0,
        "buy_slippage_bp": 0.0,
        "sell_slippage_bp": 0.0,
        "total_bp": 0.0,
    },
    "base_23bp": {
        "sell_tax_bp": 20.0,
        "buy_commission_bp": 1.5,
        "sell_commission_bp": 1.5,
        "buy_slippage_bp": 0.0,
        "sell_slippage_bp": 0.0,
        "total_bp": 23.0,
    },
    "stress_46bp": {
        "sell_tax_bp": 20.0,
        "buy_commission_bp": 1.5,
        "sell_commission_bp": 1.5,
        "buy_slippage_bp": 11.5,
        "sell_slippage_bp": 11.5,
        "total_bp": 46.0,
    },
}



def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_run_id(run_id: str) -> str:
    rid = str(run_id or "").strip()
    if not RUN_ID_RE.fullmatch(rid) or rid in {".", ".."} or ".." in rid:
        raise ValueError(f"unsafe run_id: {run_id!r}")
    return rid


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


def _csv_row_count(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _fact_get(fact: Any, key: str) -> Any:
    if isinstance(fact, Mapping):
        return fact.get(key)
    return getattr(fact, key, None)


def _csv_fact(csv_facts: Mapping[str, Any] | None, key: str, path: Path, expected_sha256: Any) -> Any | None:
    if not isinstance(csv_facts, Mapping):
        return None
    fact = csv_facts.get(key)
    if fact is None:
        return None
    try:
        st = path.stat()
        resolved = str(path.resolve())
    except OSError:
        return None
    if not expected_sha256 or str(_fact_get(fact, "expected_sha256")) != str(expected_sha256):
        return None
    if (
        str(_fact_get(fact, "resolved_path")) != resolved
        or _safe_int(_fact_get(fact, "mtime_ns")) != st.st_mtime_ns
        or _safe_int(_fact_get(fact, "size")) != st.st_size
    ):
        return None
    return fact


def _rows_from_fact(fact: Any | None) -> list[dict[str, Any]] | None:
    if fact is None:
        return None
    rows = _fact_get(fact, "all_rows")
    if rows is None:
        return None
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            out.append({str(key): str(value) for key, value in row})
        except (TypeError, ValueError):
            return None
    return out


def _row_count_from_fact(fact: Any | None) -> int | None:
    if fact is None:
        return None
    return _safe_int(_fact_get(fact, "row_count"))


def _fieldnames_from_fact(fact: Any | None) -> set[str] | None:
    if fact is None:
        return None
    fieldnames = _fact_get(fact, "fieldnames")
    if not isinstance(fieldnames, (list, tuple)):
        return None
    return {str(field) for field in fieldnames}


def _distinct_from_fact(fact: Any | None) -> dict[str, set[str]] | None:
    if fact is None:
        return None
    distinct = _fact_get(fact, "distinct_values")
    if not isinstance(distinct, (list, tuple)):
        return None
    out: dict[str, set[str]] = {}
    for item in distinct:
        try:
            key, values = item
        except (TypeError, ValueError):
            return None
        if not isinstance(values, (list, tuple)):
            return None
        out[str(key)] = {str(value) for value in values}
    return out


def _safe_int(value: Any) -> int | None:
    try:
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) else None


def _v2_cost_scenarios_valid(train_manifest: Mapping[str, Any], errors: list[str]) -> None:
    if _safe_int(train_manifest.get("cost_model_schema_version")) != 2:
        errors.append("GATE_V2_COST_MODEL_SCHEMA_MISSING")
    if train_manifest.get("primary_cost_scenario_id") != PRIMARY_COST_SCENARIO_ID:
        errors.append("GATE_V2_COST_SCENARIO_ID_MISSING")
    scenarios = train_manifest.get("cost_scenarios")
    if not isinstance(scenarios, dict):
        errors.append("GATE_V2_COST_MODEL_SCHEMA_MISSING")
        return
    for scenario_id, expected in REQUIRED_V2_COST_SCENARIOS.items():
        scenario = scenarios.get(scenario_id)
        if not isinstance(scenario, dict):
            errors.append("GATE_V2_COST_SCENARIO_MISSING_BASE_OR_STRESS")
            continue
        for key, expected_value in expected.items():
            actual = _safe_float(scenario.get(key))
            if actual is None:
                errors.append("GATE_V2_COST_COMPONENT_MISSING")
            elif actual != expected_value:
                errors.append("GATE_V2_COST_ROUND_TRIP_DERIVATION_MISMATCH")
    if any("components_bp" in str(value) or "total_cost_bp" in str(value) for value in scenarios.values()):
        errors.append("GATE_V2_SCALAR_ONLY_COST_ACCOUNTING")



def _db_access_contract_is_read_only(value: Any) -> bool:
    return value == REQUIRED_DB_ACCESS_CONTRACT

def _validate_v2_train_artifacts(
    train_manifest: Mapping[str, Any],
    artifact_paths: Mapping[str, Path],
    artifact_hashes: Mapping[str, Any],
    expected_rows: Mapping[str, Any],
    errors: list[str],
    csv_facts: Mapping[str, Any] | None = None,
) -> None:
    _v2_cost_scenarios_valid(train_manifest, errors)
    artifacts_required = ["threshold_search", "walk_forward_windows", "replay_episode_ledgers", "cost_scenario_summary"]
    missing = [key for key in artifacts_required if key not in artifact_paths or not artifact_paths[key].exists()]
    if missing:
        if "walk_forward_windows" in missing:
            errors.append("GATE_V2_WF_WINDOWS_MISSING")
        if "threshold_search" in missing:
            errors.append("GATE_V2_THRESHOLD_GRID_MISSING")
        if "replay_episode_ledgers" in missing:
            errors.append("GATE_V2_REPLAY_LEDGER_MISSING")
        if "cost_scenario_summary" in missing:
            errors.append("GATE_V2_COST_SCENARIO_ID_MISSING")
        return

    threshold_fact = _csv_fact(csv_facts, "threshold_search", artifact_paths["threshold_search"], artifact_hashes.get("threshold_search"))
    threshold_rows = _rows_from_fact(threshold_fact)
    if threshold_rows is None:
        threshold_rows = _read_csv_rows(artifact_paths["threshold_search"])
    if not threshold_rows or not any(str(row.get("chosen")).lower() == "true" for row in threshold_rows):
        errors.append("GATE_V2_THRESHOLD_GRID_MISSING")
    if any(str(row.get("split")) != "train" or _safe_int(row.get("oos_rows_used_for_fit")) != 0 for row in threshold_rows):
        errors.append("GATE_V2_THRESHOLD_OOS_LEAKAGE")

    try:
        windows = json.loads(artifact_paths["walk_forward_windows"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append("GATE_V2_WF_WINDOWS_MISSING")
        windows = {}
    window_rows = windows.get("windows") if isinstance(windows, dict) else None
    if not isinstance(window_rows, list) or not window_rows or any(not isinstance(row, dict) for row in window_rows):
        errors.append("GATE_V2_WF_WINDOWS_MISSING")
        window_rows = []
    expected_window_count = _safe_int(expected_rows.get("walk_forward_windows"))
    if expected_window_count is None or len(window_rows) != expected_window_count:
        errors.append("GATE_ROW_COUNT_MISMATCH")
    if _safe_int(windows.get("oos_rows_used_for_fit") if isinstance(windows, dict) else None) != 0:
        errors.append("GATE_V2_OOS_ROWS_USED_FOR_FIT_NONZERO")
    if not isinstance(windows, dict) or not windows.get("threshold_grid"):
        errors.append("GATE_V2_THRESHOLD_GRID_MISSING")
    held_out_windows = [row for row in window_rows if row.get("feedback_source_split") == "none_frozen_held_out"]
    if not any(
        row.get("fit_split") == "train"
        and _safe_int(row.get("oos_rows_used_for_fit")) == 0
        and isinstance(row.get("held_out_replay_splits"), list)
        and {"val", "test"} <= {str(split) for split in row.get("held_out_replay_splits", [])}
        and bool(row.get("frozen_replay_start_date"))
        and bool(row.get("frozen_replay_end_date"))
        for row in held_out_windows
    ):
        errors.append("GATE_V2_HELD_OUT_FREEZE_MISSING")
    if any(_safe_int(row.get("oos_rows_used_for_fit")) != 0 for row in window_rows):
        errors.append("GATE_V2_OOS_ROWS_USED_FOR_FIT_NONZERO")

    try:
        replay = json.loads(artifact_paths["replay_episode_ledgers"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append("GATE_V2_REPLAY_LEDGER_MISSING")
        replay = {}
    episodes = replay.get("episodes") if isinstance(replay, dict) else None
    if not isinstance(episodes, list) or not episodes or any(not isinstance(row, dict) for row in episodes):
        errors.append("GATE_V2_REPLAY_LEDGER_MISSING")
        episodes = []
    expected_episode_count = _safe_int(expected_rows.get("replay_episode_ledgers"))
    if expected_episode_count is None or len(episodes) != expected_episode_count:
        errors.append("GATE_ROW_COUNT_MISMATCH")
    replay_splits: set[str] = set()
    for episode in episodes:
        if _safe_int(episode.get("oos_rows_used_for_fit")) != 0:
            errors.append("GATE_V2_OOS_ROWS_USED_FOR_FIT_NONZERO")
        split = str(episode.get("replay_split") or "")
        replay_splits.add(split)
        feedback_rows = episode.get("slot_feedback")
        if not isinstance(feedback_rows, list) or not feedback_rows or any(not isinstance(feedback, dict) for feedback in feedback_rows):
            errors.append("GATE_V2_REPLAY_LEDGER_MISSING")
            continue
        for feedback in feedback_rows:
            if split in {"val", "test"} and feedback.get("feedback_used_for_fit") is not False:
                errors.append("GATE_V2_FEEDBACK_SOURCE_NOT_TRAIN")
    if not {"val", "test"} <= replay_splits:
        errors.append("GATE_V2_REPLAY_LEDGER_MISSING")

    summary = {str(row.get("policy")): row for row in train_manifest.get("summary") or []}
    shuffle = summary.get("deterministic_shuffle_top10_control") or {}
    if shuffle.get("shuffle_baseline_only") is not True or shuffle.get("policy_action_allowed") is not False:
        errors.append("GATE_V2_SHUFFLE_POLICY_PROMOTION")

    cost_fact = _csv_fact(csv_facts, "cost_scenario_summary", artifact_paths["cost_scenario_summary"], artifact_hashes.get("cost_scenario_summary"))
    cost_rows = _rows_from_fact(cost_fact)
    if cost_rows is None:
        cost_rows = _read_csv_rows(artifact_paths["cost_scenario_summary"])
    cost_ids = {row.get("cost_scenario_id") for row in cost_rows}
    if not {"zero_control_0bp", "base_23bp", "stress_46bp"} <= cost_ids:
        errors.append("GATE_V2_COST_SCENARIO_MISSING_BASE_OR_STRESS")
    for row in cost_rows:
        scenario_id = str(row.get("cost_scenario_id") or "")
        expected = REQUIRED_V2_COST_SCENARIOS.get(scenario_id)
        for key in ["sell_tax_bp", "buy_commission_bp", "sell_commission_bp", "buy_slippage_bp", "sell_slippage_bp"]:
            actual = _safe_float(row.get(key))
            if actual is None:
                errors.append("GATE_V2_COST_COMPONENT_MISSING")
            elif expected is not None and actual != expected[key]:
                errors.append("GATE_V2_COST_ROUND_TRIP_DERIVATION_MISMATCH")
        actual_total = _safe_float(row.get("total_component_bp"))
        if actual_total is None:
            errors.append("GATE_V2_COST_COMPONENT_MISSING")
        elif expected is not None and actual_total != expected["total_bp"]:
            errors.append("GATE_V2_COST_ROUND_TRIP_DERIVATION_MISMATCH")
        if _safe_int(row.get("selected_count")) is None or _safe_int(row.get("hold_cash_count")) is None:
            errors.append("GATE_V2_SELECTED_HOLD_COUNT_INVALID")

def _resolve_artifact(value: Any, *, manifest_dir: Path, artifact_dir: Path) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = manifest_dir / path
    resolved = path.resolve()
    try:
        resolved.relative_to(artifact_dir.resolve())
    except ValueError:
        return None
    return resolved


def _load_manifest(manifest_or_path: Mapping[str, Any] | str | Path) -> tuple[dict[str, Any], Path]:
    if isinstance(manifest_or_path, (str, Path)):
        path = Path(manifest_or_path).resolve()
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, TypeError):
            return {"_manifest_load_failed": True, "artifact_dir": str(path.parent)}, path.parent
        if not isinstance(loaded, dict):
            return {"_manifest_load_failed": True, "artifact_dir": str(path.parent)}, path.parent
        return loaded, path.parent
    if not isinstance(manifest_or_path, Mapping):
        return {"_manifest_load_failed": True}, Path(str(".")).resolve()
    manifest = dict(manifest_or_path)
    return manifest, Path(str(manifest.get("artifact_dir") or ".")).resolve()


def validate_close_slot_gate(train_manifest_or_path: Mapping[str, Any] | str | Path, *, csv_facts: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a fail-closed gate report for a close-slot train artifact."""

    train_manifest, manifest_dir = _load_manifest(train_manifest_or_path)
    artifact_dir = Path(str(train_manifest.get("artifact_dir") or manifest_dir)).resolve()
    errors: list[str] = []
    try:
        _validate_run_id(str(train_manifest.get("run_id") or ""))
    except ValueError:
        errors.append("GATE_MISSING_TRAIN_RUN_ID")
    if _safe_int(train_manifest.get("schema_version")) != 2:
        errors.append("GATE_MISSING_SCHEMA_VERSION")
    if train_manifest.get("lineage_schema_version") != 1:
        errors.append("GATE_MISSING_SCHEMA_VERSION")
    if any(train_manifest.get(name) is not False for name in FALSE_FLAG_NAMES):
        errors.append("GATE_STALE_OPTIMISTIC_FLAGS")
    cost_ladder_raw = train_manifest.get("cost_sensitivity_bp")
    cost_ladder_values = [_safe_int(value) for value in cost_ladder_raw] if isinstance(cost_ladder_raw, list) else []
    primary_cost = _safe_int(train_manifest.get("round_trip_cost_bp"))
    if (
        not cost_ladder_values
        or None in cost_ladder_values
        or primary_cost != ROUND_TRIP_COST_BP
        or sorted(cost_ladder_values) != sorted(COST_SENSITIVITY_BP)
    ):
        errors.append("GATE_MISSING_23BP")
    if not bool(train_manifest.get("train_only_fit")) or not bool(train_manifest.get("validation_test_no_retune")):
        errors.append("GATE_OOS_RETUNING_NOT_BLOCKED")
    oos_rows_used_for_fit = _safe_int((train_manifest.get("fit_summary") or {}).get("oos_rows_used_for_fit"))
    if oos_rows_used_for_fit is None or oos_rows_used_for_fit != 0:
        errors.append("GATE_OOS_RETUNING_NOT_BLOCKED")
    present_baselines = {str(value) for value in train_manifest.get("required_baselines") or []}
    summary_policies = {str(row.get("policy")) for row in train_manifest.get("summary") or []}
    if not REQUIRED_BASELINES <= present_baselines or not REQUIRED_BASELINES <= summary_policies:
        errors.append("GATE_MISSING_REQUIRED_BASELINE")
    if train_manifest.get("fill_mode") != FILL_MODE:
        errors.append("GATE_MISSING_POLICY_SCORE_AUDIT")

    artifacts_value = train_manifest.get("artifacts")
    if isinstance(artifacts_value, Mapping):
        artifacts = artifacts_value
    else:
        artifacts = {}
        errors.append("GATE_UNSAFE_PATH")
    artifact_hashes_value = train_manifest.get("artifact_hashes")
    if isinstance(artifact_hashes_value, Mapping):
        artifact_hashes = artifact_hashes_value
    else:
        artifact_hashes = {}
        errors.append("GATE_HASH_MISMATCH")
    expected_rows_value = train_manifest.get("row_counts")
    if isinstance(expected_rows_value, Mapping):
        expected_rows = expected_rows_value
    else:
        expected_rows = {}
        errors.append("GATE_ROW_COUNT_MISMATCH")
    artifact_paths: dict[str, Path] = {}
    matching_csv_facts: dict[str, Any] = {}
    for key in ["policy_scores", "baseline_summary", "date_ledgers", "threshold_search", "walk_forward_windows", "replay_episode_ledgers", "cost_scenario_summary"]:
        path = _resolve_artifact(artifacts.get(key), manifest_dir=manifest_dir, artifact_dir=artifact_dir)
        if path is None:
            errors.append("GATE_UNSAFE_PATH")
            continue
        artifact_paths[key] = path
        if not path.exists():
            errors.append("GATE_FILE_MISSING")
            continue
        expected_hash = artifact_hashes.get(key)
        if not expected_hash or _file_sha(path) != expected_hash:
            errors.append("GATE_HASH_MISMATCH")
        fact = _csv_fact(csv_facts, key, path, expected_hash)
        if fact is not None:
            matching_csv_facts[key] = fact
        if key == "policy_scores":
            expected_count = _safe_int(expected_rows.get("policy_score_rows"))
            observed_count = _row_count_from_fact(fact)
            if observed_count is None:
                observed_count = _csv_row_count(path)
            if expected_count is None or observed_count != expected_count:
                errors.append("GATE_ROW_COUNT_MISMATCH")
        if key == "baseline_summary":
            expected_count = _safe_int(expected_rows.get("baseline_summary_rows"))
            observed_count = _row_count_from_fact(fact)
            if observed_count is None:
                observed_count = _csv_row_count(path)
            if expected_count is None or observed_count != expected_count:
                errors.append("GATE_ROW_COUNT_MISMATCH")
        if key == "threshold_search":
            expected_count = _safe_int(expected_rows.get("threshold_search_rows"))
            observed_count = _row_count_from_fact(fact)
            if observed_count is None:
                observed_count = _csv_row_count(path)
            if expected_count is None or observed_count != expected_count:
                errors.append("GATE_ROW_COUNT_MISMATCH")
        if key == "cost_scenario_summary":
            expected_count = _safe_int(expected_rows.get("cost_scenario_summary_rows"))
            observed_count = _row_count_from_fact(fact)
            if observed_count is None:
                observed_count = _csv_row_count(path)
            if expected_count is None or observed_count != expected_count:
                errors.append("GATE_ROW_COUNT_MISMATCH")

    policy_fact = matching_csv_facts.get("policy_scores")
    policy_row_count = _row_count_from_fact(policy_fact)
    if policy_row_count is None:
        policy_score_rows = _read_csv_rows(artifact_paths["policy_scores"]) if "policy_scores" in artifact_paths and artifact_paths["policy_scores"].exists() else []
        policy_row_count = len(policy_score_rows)
        fieldnames = set(policy_score_rows[0]) if policy_score_rows else set()
        distinct_values: dict[str, set[str]] = {
            field: {str(row.get(field, "")) for row in policy_score_rows}
            for field in REQUIRED_POLICY_SCORE_AUDIT_FIELDS
        }
    else:
        fieldnames = _fieldnames_from_fact(policy_fact) or set()
        distinct_values = _distinct_from_fact(policy_fact) or {}
    if policy_row_count and fieldnames:
        missing_audit = sorted(REQUIRED_POLICY_SCORE_AUDIT_FIELDS - fieldnames)
        policy_expected_values = {
            "dataset_run_id": str(train_manifest.get("dataset_run_id")),
            "dataset_manifest_sha": str(train_manifest.get("dataset_manifest_sha")),
            "price_basis_status": str(train_manifest.get("price_basis_status")),
            "decision_grade_return_status": str(train_manifest.get("decision_grade_return_status")),
            "fill_mode": FILL_MODE,
            "execution_realism": str(train_manifest.get("execution_realism")),
            "round_trip_cost_bp": str(ROUND_TRIP_COST_BP),
            "primary_cost_scenario_id": str(train_manifest.get("primary_cost_scenario_id")),
        }
        expected_blockers = "|".join(str(value) for value in train_manifest.get("upstream_gate_blockers", []))
        mismatched_audit = any(distinct_values.get(field) != {expected} for field, expected in policy_expected_values.items())
        mismatched_audit = mismatched_audit or distinct_values.get("upstream_gate_blockers") != {expected_blockers}
        if missing_audit or mismatched_audit:
            errors.append("GATE_MISSING_POLICY_SCORE_AUDIT")
    else:
        errors.append("GATE_MISSING_POLICY_SCORE_AUDIT")

    baseline_fact = matching_csv_facts.get("baseline_summary")
    baseline_summary_rows = _rows_from_fact(baseline_fact)
    if baseline_summary_rows is None:
        baseline_summary_rows = _read_csv_rows(artifact_paths["baseline_summary"]) if "baseline_summary" in artifact_paths and artifact_paths["baseline_summary"].exists() else []
    baseline_csv_policies = {str(row.get("policy")) for row in baseline_summary_rows}
    if not REQUIRED_BASELINES <= baseline_csv_policies:
        errors.append("GATE_MISSING_REQUIRED_BASELINE")
    _validate_v2_train_artifacts(train_manifest, artifact_paths, artifact_hashes, expected_rows, errors, csv_facts=matching_csv_facts)

    dataset_manifest_path = Path(str(train_manifest.get("dataset_manifest_path") or "")).resolve()
    dataset_manifest: dict[str, Any] = {}
    dataset_lineage_status = "MISSING"
    if not dataset_manifest_path.exists():
        errors.append("GATE_DATASET_LINEAGE_NOT_PASS")
    else:
        try:
            loaded_dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            dataset_lineage_status = "BLOCK"
            errors.append("GATE_DATASET_LINEAGE_NOT_PASS")
        else:
            if not isinstance(loaded_dataset_manifest, dict):
                dataset_lineage_status = "BLOCK"
                errors.append("GATE_DATASET_LINEAGE_NOT_PASS")
                dataset_manifest = {}
            else:
                dataset_manifest = loaded_dataset_manifest
                try:
                    dataset_lineage = validate_close_slot_dataset_lineage(dataset_manifest_path)
                    dataset_lineage_status = str(dataset_lineage.get("status"))
                except (TypeError, ValueError):
                    dataset_lineage_status = "BLOCK"
                    errors.append("GATE_DATASET_LINEAGE_NOT_PASS")
                else:
                    if dataset_lineage_status != "PASS" or dataset_manifest.get("lineage_validation_status") != "PASS":
                        errors.append("GATE_DATASET_LINEAGE_NOT_PASS")
                    if int(dataset_manifest.get("schema_version") or 1) == 2 and (
                        not _db_access_contract_is_read_only(dataset_manifest.get("daily_db_access"))
                        or not _db_access_contract_is_read_only(train_manifest.get("dataset_db_access"))
                    ):
                        errors.append("GATE_DATASET_DB_ACCESS_NOT_READ_ONLY")
                split_policy = dataset_manifest.get("split_policy") or {}
                purge_days = _safe_int(split_policy.get("purge_days"))
                embargo_days = _safe_int(split_policy.get("embargo_days"))
                if not split_policy.get("method") or purge_days is None or embargo_days is None or purge_days <= 0 or embargo_days <= 0:
                    errors.append("GATE_MISSING_SPLIT_EVIDENCE")

    d3 = train_manifest.get("d3_comparator") or {}
    if d3.get("present") and not d3.get("reledgered_through_close_slot_accounting"):
        errors.append("GATE_D3_NOT_RELEDGERED")
    if d3.get("present") and "frozen_d3_reledgered_score_and_pick" not in summary_policies:
        errors.append("GATE_D3_NOT_RELEDGERED")
    if d3.get("present") and "date_ledgers" in artifact_paths and artifact_paths["date_ledgers"].exists():
        try:
            date_ledgers = json.loads(artifact_paths["date_ledgers"].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            errors.append("GATE_D3_NOT_RELEDGERED")
        else:
            d3_ledgers = date_ledgers.get("frozen_d3_reledgered_score_and_pick") if isinstance(date_ledgers, dict) else None
            if not d3_ledgers or not all(
                isinstance(row, dict)
                and str(row.get("action_label")) == "selected_code_replay_adapter_only_not_policy_action"
                for row in d3_ledgers
            ):
                errors.append("GATE_D3_NOT_RELEDGERED")

    upstream_blockers = sorted(set(str(value) for value in list(train_manifest.get("upstream_gate_blockers") or []) + list(dataset_manifest.get("upstream_gate_blockers") or [])))
    status = str(train_manifest.get("status") or "")
    readiness_status = str(train_manifest.get("readiness_status") or "")
    if upstream_blockers and ("READY" in status.upper() or "READY" in readiness_status.upper()):
        errors.append("GATE_READY_STATUS_FOR_UNRESOLVED_D0_D1")
    gate_status = "WATCH_RESEARCH_ONLY" if upstream_blockers else "NO-GO_RESEARCH_ONLY"
    stable_errors = sorted(set(error for error in errors if error in STABLE_GATE_ERRORS))
    return {
        "schema_version": CLOSE_SLOT_GATE_SCHEMA_VERSION,
        "lineage_schema_version": GATE_LINEAGE_SCHEMA_VERSION,
        "checked_at": _utc_now(),
        "artifact_kind": "daily_close_slot_gate_report",
        "research_lane": "daily_close_slot",
        "gate_status": gate_status,
        "status": "PASS" if not stable_errors else "BLOCK",
        "errors": stable_errors,
        "train_run_id": train_manifest.get("run_id"),
        "train_manifest_sha": train_manifest.get("manifest_sha"),
        "dataset_run_id": train_manifest.get("dataset_run_id"),
        "dataset_manifest_sha": train_manifest.get("dataset_manifest_sha"),
        "dataset_lineage_status": dataset_lineage_status,
        "dataset_db_access": dataset_manifest.get("daily_db_access") if dataset_manifest else None,
        "train_dataset_db_access": train_manifest.get("dataset_db_access"),
        "required_baselines": sorted(REQUIRED_BASELINES),
        "present_baselines": sorted(summary_policies),
        "round_trip_cost_bp": train_manifest.get("round_trip_cost_bp"),
        "cost_sensitivity_bp": train_manifest.get("cost_sensitivity_bp"),
        "split_policy": dataset_manifest.get("split_policy") if dataset_manifest else None,
        "train_only_fit": train_manifest.get("train_only_fit"),
        "validation_test_no_retune": train_manifest.get("validation_test_no_retune"),
        "fit_summary": train_manifest.get("fit_summary"),
        "d3_comparator": d3,
        "upstream_gate_blockers": upstream_blockers,
    }


def write_close_slot_gate_artifacts(
    *,
    train_manifest_path: str | Path,
    train_manifest_sha: str,
    output_root: str | Path = DEFAULT_CLOSE_SLOT_GATE_ROOT,
    run_id: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    train_path = Path(train_manifest_path).resolve()
    train_manifest, _ = _load_manifest(train_path)
    if not train_manifest.get("_manifest_load_failed") and train_manifest.get("manifest_sha") != train_manifest_sha:
        raise ValueError("train manifest sha mismatch")
    rid = _validate_run_id(run_id or f"close_slot_gate_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
    root = Path(output_root).resolve()
    out_dir = (root / rid).resolve()
    try:
        out_dir.relative_to(root)
    except ValueError as exc:
        raise ValueError("gate run_id escapes output root") from exc
    if out_dir.exists() and any(out_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"close-slot gate run already exists: {rid}")
    out_dir.mkdir(parents=True, exist_ok=True)
    gate_report = validate_close_slot_gate(train_path)
    report_path = out_dir / "gate_report.json"
    manifest_path = out_dir / "close_slot_gate_manifest.json"
    report_path.write_text(json.dumps(gate_report, ensure_ascii=False, indent=2), encoding="utf-8")
    gate_manifest = {
        "schema_version": CLOSE_SLOT_GATE_SCHEMA_VERSION,
        "lineage_schema_version": GATE_LINEAGE_SCHEMA_VERSION,
        "created_at": _utc_now(),
        "artifact_kind": "daily_close_slot_gate",
        "research_lane": "daily_close_slot",
        "run_id": rid,
        "status": gate_report["gate_status"],
        "readiness_status": gate_report["gate_status"],
        "gate_validation_status": gate_report["status"],
        "gate_validation_errors": gate_report["errors"],
        "guardrail": "EXPERIMENTAL_ONLY RESEARCH_ONLY; no live/broker/account/order/paper-forward/profitability claim.",
        "promotion_allowed": False,
        "model_build_allowed": False,
        "paper_forward_allowed": False,
        "live_broker_order_allowed": False,
        "profitability_claim_allowed": False,
        "go_summary_allowed": False,
        "train_run_id": train_manifest.get("run_id"),
        "train_manifest_sha": train_manifest_sha,
        "train_manifest_path": str(train_path),
        "source_run_ids": {
            "train_run_id": train_manifest.get("run_id"),
            "train_manifest_sha": train_manifest_sha,
            "dataset_run_id": train_manifest.get("dataset_run_id"),
            "dataset_manifest_sha": train_manifest.get("dataset_manifest_sha"),
        },
        "artifacts": {"gate_report": str(report_path)},
        "artifact_hashes": {"gate_report": _file_sha(report_path)},
        "manifest_sha": _sha_json({"run_id": rid, "train_manifest_sha": train_manifest_sha, "gate_report": _file_sha(report_path)}),
    }
    manifest_path.write_text(json.dumps(gate_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "run_id": rid,
        "artifact_dir": str(out_dir),
        "gate_report_path": str(report_path),
        "gate_manifest_path": str(manifest_path),
        "gate_validation_status": gate_report["status"],
        "gate_validation_errors": gate_report["errors"],
        "manifest_sha": gate_manifest["manifest_sha"],
    }


__all__ = [
    "CLOSE_SLOT_GATE_SCHEMA_VERSION",
    "STABLE_GATE_ERRORS",
    "validate_close_slot_gate",
    "write_close_slot_gate_artifacts",
]
