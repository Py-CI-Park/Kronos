"""Custody-safe runner for the frozen M3E reused-validation screen.

The CLI accepts a custody root, never a dataset/test path, and only loads the
public train/validation artifact through ``daily_v8_custody``.  It has no OOS
or final-test switch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from stom_rl.daily_v8_custody import MANIFEST_FILENAME, load_train_validation
from stom_rl.daily_v8_m3e import SEEDS, TRAINER_VERSION, fit_evaluate
from stom_rl.v5_oos_custody import canonical_bytes

REPO_ROOT = Path(__file__).resolve().parents[1]
PREREG_PATH = REPO_ROOT / "docs" / "kronos_v8_prereg_m3e_2026-07-21.json"
DEFAULT_OUT_ROOT = Path("webui/rl_runs/v8_daily_m3e")
RUN_SCHEMA = "kronos_v8_m3e_validation_run.v1"
RUNNER_VERSION = "kronos_v8_m3e_custody_runner.v1"
TRAINER_PRINCIPAL = "agent://m3e-trainer"
CUSTODIAN_PRINCIPAL = "agent://m3e-custodian"
NUMERIC_FIELDS = (
    "ret_1d_prev", "ret_5d_prev", "ret_20d_prev", "vol_z_20",
    "foreign_ratio_prev", "foreign_ratio_delta_5", "inst_netbuy_norm_5",
    "entry_close_1520", "future_return_h1_1520_proxy",
)
PROTOCOL: Mapping[str, Any] = {
    "classification": "CONTEXTUAL_BANDIT_RESEARCH_EXPERIMENT",
    "seeds": list(SEEDS),
    "train_passes": 1,
    "aggregation": "unweighted_raw_member_score_mean_before_ranking_score_gt_0",
    "ranking": "top_10_distinct_by_score_then_symbol",
    "member_selection_allowed": False,
    "checkpoint_selection_allowed": False,
    "capital_krw": 60_000_000,
    "slot_budget_krw": 5_000_000,
    "slots": 10,
    "primary_cost_rate": 0.0023,
    "test_state": "NOT_RUN",
}
SIX_FALSE_LOCKS = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}


class M3ERunError(ValueError):
    """Raised when frozen custody or protocol evidence does not match."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def protocol_sha256() -> str:
    return _sha256(canonical_bytes(PROTOCOL))


def trainer_sha256() -> str:
    engine = Path(__file__).with_name("daily_v8_m3e.py")
    sources = {
        "engine_path": "stom_rl/daily_v8_m3e.py",
        "engine_sha256": _sha256_file(engine),
        "runner_path": "stom_rl/daily_v8_m3e_run.py",
        "runner_sha256": _sha256_file(Path(__file__)),
    }
    return _sha256(canonical_bytes(sources))


def _number(value: Any) -> float | None:
    if value is None or not str(value).strip():
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _typed_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    output: list[dict[str, Any]] = []
    excluded = {"train": 0, "val": 0}
    for raw in rows:
        split = raw["split"]
        if split not in excluded:
            raise M3ERunError("custody loader returned a forbidden split")
        row: dict[str, Any] = {
            "symbol": str(raw["symbol"]),
            "session_yyyymmdd": int(raw["session_yyyymmdd"]),
            "split": split,
        }
        for field in NUMERIC_FIELDS:
            row[field] = _number(raw.get(field))
        if row["future_return_h1_1520_proxy"] is None:
            excluded[split] += 1
            continue
        output.append(row)
    return output, excluded


def _result_sections(result: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    baseline = {
        "baselines": result["baselines"],
        "exposure_matched_random": result["exposure_matched_random"],
    }
    controls = {"shuffled_label_ensemble": result["shuffled_label_ensemble"]}
    primary = {
        "ensemble": {key: result["ensemble"][key] for key in ("metrics", "pick_counts")},
        "jackknives": {
            seed: {key: item[key] for key in ("metrics", "pick_counts", "passes")}
            for seed, item in result["jackknives"].items()
        },
        "verdict": result["verdict"],
        "member_hashes": result["member_hashes"],
    }
    return primary, baseline, controls


def _with_pass_flags(result: dict[str, Any]) -> None:
    baseline_nav = max(
        result["baselines"][name]["nav"]
        for name in ("rule_topk_ret5", "rule_topk_low_vol", "rule_topk_inst", "random_topk")
    )
    passing = set(result["verdict"]["passing_jackknives"])
    for seed, item in result["jackknives"].items():
        computed = item["metrics"]["nav"] > 60_000_000 and item["metrics"]["nav"] > baseline_nav
        if computed != (seed in passing):
            raise M3ERunError("jackknife pass evidence is internally inconsistent")
        item["passes"] = computed


def _validate_frozen_contract(prereg: Mapping[str, Any], custody: Mapping[str, Any]) -> None:
    if prereg.get("status") != "FROZEN":
        raise M3ERunError("M3E preregistration is not frozen")
    source = prereg.get("source_contract")
    if not isinstance(source, Mapping):
        raise M3ERunError("frozen source contract is missing")
    if source.get("trainer_sha256") != trainer_sha256() or source.get("protocol_sha256") != protocol_sha256():
        raise M3ERunError("trainer or protocol differs from frozen preregistration")
    dataset = prereg.get("dataset")
    if not isinstance(dataset, Mapping):
        raise M3ERunError("frozen custody dataset contract is missing")
    expected = {
        "custody_uid": custody.get("custody_uid"),
        "public_artifact_sha256": custody.get("public_artifact", {}).get("sha256"),
        "sealed_test_sha256": custody.get("sealed_test_commitment", {}).get("sha256"),
    }
    if any(dataset.get(key) != value for key, value in expected.items()):
        raise M3ERunError("custody commitments differ from frozen preregistration")
    if custody.get("prereg_id") != prereg.get("prereg_id"):
        raise M3ERunError("custody artifact belongs to another preregistration")


def build_validation_manifest(
    result: dict[str, Any], *, prereg_bytes: bytes, custody: Mapping[str, Any],
    public_rows: int, excluded_labels: Mapping[str, int], generated_utc: str,
) -> dict[str, Any]:
    _with_pass_flags(result)
    primary, baseline, controls = _result_sections(result)
    commitments = {
        "trainer_sha256": trainer_sha256(),
        "protocol_sha256": protocol_sha256(),
        "public_artifact_sha256": custody["public_artifact"]["sha256"],
        "result_sha256": _sha256(canonical_bytes(primary)),
        "baseline_sha256": _sha256(canonical_bytes(baseline)),
        "control_sha256": _sha256(canonical_bytes(controls)),
    }
    return {
        "schema_version": RUN_SCHEMA,
        "runner_version": RUNNER_VERSION,
        "trainer_version": TRAINER_VERSION,
        "prereg": {"id": json.loads(prereg_bytes)["prereg_id"], "sha256": _sha256(prereg_bytes)},
        "custody_uid": custody["custody_uid"],
        "seeds": list(SEEDS),
        "policy": {
            "score_rule": PROTOCOL["aggregation"],
            "ranking": PROTOCOL["ranking"],
            "capital_krw": PROTOCOL["capital_krw"],
            "slot_budget_krw": PROTOCOL["slot_budget_krw"],
            "slots": PROTOCOL["slots"],
            "primary_cost_rate": PROTOCOL["primary_cost_rate"],
        },
        "members": result["members"],
        "member_artifact_sha256": result["member_hashes"],
        "ensemble": {key: result["ensemble"][key] for key in ("metrics", "pick_counts")},
        "jackknives": {
            seed: {key: item[key] for key in ("metrics", "pick_counts", "passes")}
            for seed, item in result["jackknives"].items()
        },
        "baselines": result["baselines"],
        "exposure_matched_random": result["exposure_matched_random"],
        "shuffled_label_ensemble": result["shuffled_label_ensemble"],
        "verdict": result["verdict"],
        "public_rows_loaded": public_rows,
        "missing_h1_label_excluded": dict(excluded_labels),
        "test": {"state": "NOT_RUN"},
        "false_research_locks": dict(SIX_FALSE_LOCKS),
        "artifact_commitments": commitments,
        "principals": {
            "trainer_principal_uri": TRAINER_PRINCIPAL,
            "custodian_principal_uri": CUSTODIAN_PRINCIPAL,
        },
        "generated_utc": generated_utc,
    }


def run_validation(
    custody_root: Path | str, *, out_root: Path | str = DEFAULT_OUT_ROOT,
    run_id: str | None = None, prereg_path: Path | str = PREREG_PATH,
) -> dict[str, Any]:
    root = Path(custody_root)
    custody_path = root / MANIFEST_FILENAME
    custody = json.loads(custody_path.read_text(encoding="utf-8"))
    prereg_file = Path(prereg_path)
    prereg_bytes = prereg_file.read_bytes()
    prereg = json.loads(prereg_bytes)
    _validate_frozen_contract(prereg, custody)
    raw_rows = load_train_validation(custody_path, root)
    rows, excluded = _typed_rows(raw_rows)
    train_rows = [row for row in rows if row["split"] == "train"]
    validation_rows = [row for row in rows if row["split"] == "val"]
    if not train_rows or not validation_rows:
        raise M3ERunError("public custody artifact requires non-empty train and validation labels")
    result = fit_evaluate(train_rows, validation_rows)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    component = run_id or timestamp
    if not component or Path(component).name != component:
        raise M3ERunError("run_id must be one path component")
    destination = Path(out_root) / custody["custody_uid"] / f"train_{component}"
    destination.mkdir(parents=True, exist_ok=False)
    generated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest = build_validation_manifest(
        result, prereg_bytes=prereg_bytes, custody=custody,
        public_rows=len(raw_rows), excluded_labels=excluded, generated_utc=generated,
    )
    manifest_bytes = canonical_bytes(manifest)
    (destination / "run_manifest.json").write_bytes(manifest_bytes)
    event = {
        "event": "REUSED_VALIDATION_SCREEN_COMPLETE",
        "verdict": manifest["verdict"]["value"],
        "test_state": "NOT_RUN",
        "generated_utc": generated,
    }
    (destination / "events.jsonl").write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
    return {"output_dir": destination, "manifest": manifest}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run frozen M3E train/reused-validation from public custody only.")
    parser.add_argument("--custody-root", required=True)
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--run-id")
    args = parser.parse_args()
    result = run_validation(args.custody_root, out_root=args.out_root, run_id=args.run_id)
    print(json.dumps({
        "output_dir": str(result["output_dir"]),
        "verdict": result["manifest"]["verdict"],
        "test": result["manifest"]["test"],
    }))


if __name__ == "__main__":
    main()
