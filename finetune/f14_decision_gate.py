"""Fail-closed F14 decision gate for the G013 R5 attribution result.

This module is intentionally pure by default: callers pass the already-loaded R5
machine-readable evidence, optional report text, and optional F14 preregistration
object.  The CLI is a thin JSON reader/writer around the same decision function.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
from pathlib import Path
from typing import Any

VALID_DECISIONS = {"NO_SIGNAL", "TUNING_HARMFUL", "INCONCLUSIVE", "TUNING_HELPED_COST"}
SUPERVISED_FORECAST_LABEL = "supervised forecast (not RL/trading alpha)"
F14_HORIZON_SECONDS = 300
REQUIRED_COSTS_BP = [0, 23, 46]
PRIMARY_COST_BP = 23


class DecisionGateError(ValueError):
    """Raised when evidence or preregistration input violates the gate contract."""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DecisionGateError(message)


def _decision_from_report(report_text: str) -> str | None:
    match = re.search(r"^##\s+Decision:\s*([A-Z_]+)\s*$", report_text, re.MULTILINE)
    return match.group(1) if match else None


def _validate_evidence(evidence: dict[str, Any], report_text: str | None = None) -> str:
    decision = evidence.get("decision")
    _require(isinstance(decision, str) and decision in VALID_DECISIONS, "unknown or missing R5 decision")
    _require(evidence.get("research_only") is True, "R5 evidence must be research_only=true")
    _require(
        evidence.get("no_live_broker_profit_go_rl_or_trading_alpha_claim") is True,
        "R5 evidence must explicitly disclaim live/broker/profit/GO/RL/trading-alpha claims",
    )
    _require(evidence.get("cost_gate_bp") == PRIMARY_COST_BP, "R5 cost gate must be 23bp")

    hashes = evidence.get("hashes")
    _require(isinstance(hashes, dict), "missing evidence hash section")
    _require(isinstance(hashes.get("hash_manifest"), str) and hashes["hash_manifest"], "missing evidence hash manifest")
    checks = evidence.get("missing_nan_hash_checks")
    _require(isinstance(checks, dict), "missing evidence integrity checks")
    _require(checks.get("hashes_json_present") is True, "missing hashes.json evidence")
    _require(checks.get("source_input_output_hashes_present") is True, "missing source/input/output hashes")
    _require(checks.get("selected_windows_is_681") is True, "R5 evidence must prove the exact 681-window lineage")
    _require(checks.get("metric_nan_detected") is False, "R5 evidence contains non-finite comparison metrics")
    _require(checks.get("comparison_jsons_present") is True, "R5 comparison JSON evidence is missing")
    _require(checks.get("tokenizer_mse_nan") is False, "R5 tokenizer reconstruction contains non-finite MSE")

    _require(isinstance(report_text, str) and report_text.strip(), "R5 report text is required")
    report_decision = _decision_from_report(report_text)
    _require(report_decision in VALID_DECISIONS, "report is missing a valid decision heading")
    _require(report_decision == decision, "report/JSON decision mismatch")
    return decision


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_prereg(prereg: dict[str, Any]) -> None:
    _require(isinstance(prereg, dict), "F14 preregistration must be an object")
    _require(_nonempty_string(prereg.get("dated_path")), "F14 preregistration requires dated_path")
    _require(re.search(r"20\d\d-\d\d-\d\d", prereg["dated_path"]) is not None, "F14 preregistration path must be dated")
    _require(_nonempty_string(prereg.get("sha256")), "F14 preregistration requires sha256")
    _require(re.fullmatch(r"[0-9a-f]{64}", prereg["sha256"]) is not None, "F14 preregistration sha256 must be a hex SHA-256")
    _require(prereg.get("model_label") == SUPERVISED_FORECAST_LABEL, "F14 preregistration must use the supervised forecast label")
    _require(prereg.get("horizon_seconds") == F14_HORIZON_SECONDS, "F14 preregistration horizon must be 300 seconds")
    _require(prereg.get("costs_bp") == REQUIRED_COSTS_BP, "F14 preregistration costs must be exactly [0, 23, 46]")
    _require(prereg.get("primary_cost_bp") == PRIMARY_COST_BP, "F14 preregistration primary cost must be 23bp")
    _require(prereg.get("stages") == ["smoke", "full"], "F14 preregistration stages must be smoke then full")

    seeds = prereg.get("seeds")
    _require(isinstance(seeds, list) and seeds and all(isinstance(seed, int) for seed in seeds), "F14 preregistration requires integer seeds")

    stop = prereg.get("stop_criteria")
    _require(isinstance(stop, dict), "F14 preregistration requires stop_criteria")
    _require(isinstance(stop.get("smoke"), list) and all(_nonempty_string(x) for x in stop["smoke"]) and stop["smoke"], "F14 preregistration requires explicit smoke stop criteria")
    _require(isinstance(stop.get("full"), list) and all(_nonempty_string(x) for x in stop["full"]) and stop["full"], "F14 preregistration requires explicit full stop criteria")


def _validate_runnable_command(command: Any, prereg: dict[str, Any]) -> str:
    _require(_nonempty_string(command), "F14 preregistration requires nonempty runnable_command")
    _require(not re.search(r"[;&|<>`$\n\r]", command), "F14 runnable_command contains shell metacharacters")
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        raise DecisionGateError(f"F14 runnable_command is malformed: {exc}") from exc

    _require(len(tokens) == 6, "F14 runnable_command must be exactly: python finetune/run_f14.py --horizon-seconds 300 --prereg <dated_path>")
    _require(tokens[0] in {"python", "python3"}, "F14 runnable_command must use the documented Python entrypoint")
    _require(tokens[1].replace("\\", "/") == "finetune/run_f14.py", "F14 runnable_command must use finetune/run_f14.py")
    args = {tokens[i]: tokens[i + 1] for i in range(2, len(tokens), 2)}
    _require(set(args) == {"--horizon-seconds", "--prereg"}, "F14 runnable_command must reference only horizon and prereg")
    _require(args["--horizon-seconds"] == str(F14_HORIZON_SECONDS), "F14 runnable_command must set horizon to 300 seconds")
    _require(args["--prereg"].replace("\\", "/") == prereg["dated_path"].replace("\\", "/"), "F14 runnable_command must reference the dated prereg path")
    return command


def decide_f14_gate(
    evidence: dict[str, Any],
    *,
    report_text: str | None = None,
    prereg: dict[str, Any] | None = None,
    inconclusive_reruns_used: int = 0,
) -> dict[str, Any]:
    """Return the F14 gate state for R5 attribution evidence.

    The function fails closed by raising :class:`DecisionGateError` on malformed
    evidence, report/evidence mismatch, invalid preregistration, or attempts to
    open F14 from a disallowed branch.
    """

    _require(isinstance(inconclusive_reruns_used, int) and inconclusive_reruns_used >= 0, "inconclusive_reruns_used must be a non-negative integer")
    decision = _validate_evidence(evidence, report_text=report_text)

    if decision in {"NO_SIGNAL", "TUNING_HARMFUL", "INCONCLUSIVE"} and prereg is not None:
        raise DecisionGateError(f"{decision} cannot submit an F14 preregistration")

    base = {
        "decision": decision,
        "model_label": SUPERVISED_FORECAST_LABEL,
        "f14_execution_allowed": False,
        "f14_prereg_allowed": False,
        "runnable_command": None,
        "blocked": True,
    }

    if decision == "NO_SIGNAL":
        return {
            **base,
            "reason": "NO_SIGNAL",
            "action": "Freeze predictor/F14 and redirect to data/horizon research.",
            "inconclusive_rerun_allowed": False,
        }

    if decision == "TUNING_HARMFUL":
        return {
            **base,
            "reason": "TUNING_HARMFUL",
            "action": "Freeze F14 and prioritize data/tokenizer repair.",
            "inconclusive_rerun_allowed": False,
        }

    if decision == "INCONCLUSIVE":
        _require(inconclusive_reruns_used <= 1, "INCONCLUSIVE permits at most one defect-specific preregistered rerun")
        return {
            **base,
            "reason": "INCONCLUSIVE",
            "action": "Permit exactly one defect-specific preregistered R5 rerun; F14 remains blocked.",
            "inconclusive_rerun_allowed": inconclusive_reruns_used == 0,
        }

    # TUNING_HELPED_COST opens only the preregistration lane unless a separate,
    # complete dated preregistration is provided and validated.
    if prereg is None:
        return {
            **base,
            "reason": "TUNING_HELPED_COST",
            "action": "Open only a new dated F14 preregistration gate; no runnable F14 job exists yet.",
            "f14_prereg_allowed": True,
            "blocked": True,
            "inconclusive_rerun_allowed": False,
        }

    _validate_prereg(prereg)
    runnable_command = _validate_runnable_command(prereg.get("runnable_command"), prereg)
    return {
        **base,
        "reason": "TUNING_HELPED_COST",
        "action": "Valid dated supervised F14 preregistration is present; execution permission is open under that preregistration only.",
        "f14_execution_allowed": True,
        "f14_prereg_allowed": True,
        "runnable_command": runnable_command,
        "blocked": False,
        "inconclusive_rerun_allowed": False,
        "prereg": {
            "dated_path": prereg["dated_path"],
            "sha256": prereg["sha256"],
            "horizon_seconds": F14_HORIZON_SECONDS,
            "costs_bp": REQUIRED_COSTS_BP,
            "primary_cost_bp": PRIMARY_COST_BP,
            "stages": ["smoke", "full"],
            "seeds": prereg["seeds"],
        },
    }


def build_current_decision_document(
    evidence_path: Path,
    report_path: Path,
    *,
    inconclusive_reruns_used: int = 0,
) -> dict[str, Any]:
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    report_text = report_path.read_text(encoding="utf-8")
    gate = decide_f14_gate(evidence, report_text=report_text, inconclusive_reruns_used=inconclusive_reruns_used)
    return {
        "schema": "stom_kronos_f14_decision.v1",
        "date": "2026-07-12",
        "source_task": "G014",
        "upstream_task": evidence.get("created_for", "G013"),
        "evidence": {
            "report_path": str(report_path).replace("\\", "/"),
            "report_sha256": _sha256_file(report_path),
            "summary_path": str(evidence_path).replace("\\", "/"),
            "summary_sha256": _sha256_file(evidence_path),
            "result_commit": evidence.get("result_commit"),
        },
        "gate": gate,
        "f14_status": "Not launched; blocked by TUNING_HARMFUL supervised forecast attribution evidence.",
        "constraints": {
            "no_f14_training_job_launched": True,
            "no_data_export_launched": True,
            "research_mode": "supervised forecast work, not RL/trading alpha",
            "conditional_costs_bp": REQUIRED_COSTS_BP,
            "conditional_primary_cost_bp": PRIMARY_COST_BP,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the fail-closed F14 decision gate from R5 evidence.")
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--prereg", type=Path)
    parser.add_argument("--inconclusive-reruns-used", type=int, default=0)
    parser.add_argument("--write-current-decision", type=Path)
    args = parser.parse_args(argv)

    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        report_text = args.report.read_text(encoding="utf-8") if args.report else None
        prereg = json.loads(args.prereg.read_text(encoding="utf-8")) if args.prereg else None
        gate = decide_f14_gate(
            evidence,
            report_text=report_text,
            prereg=prereg,
            inconclusive_reruns_used=args.inconclusive_reruns_used,
        )
        output: dict[str, Any] = gate
        if args.write_current_decision:
            _require(args.report is not None, "--write-current-decision requires --report")
            output = build_current_decision_document(args.evidence, args.report, inconclusive_reruns_used=args.inconclusive_reruns_used)
            args.write_current_decision.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except (DecisionGateError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "f14_execution_allowed": False, "f14_prereg_allowed": False, "runnable_command": None}, sort_keys=True))
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
