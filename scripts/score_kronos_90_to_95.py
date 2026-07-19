"""Deterministic, non-gameable scorer for the Kronos 90->95 completion plan.

RESEARCH/ENGINEERING GOVERNANCE ONLY. This tool converts an evidence file into
a reproducible engineering-quality score against
``docs/kronos_90_to_95_scorecard_v1.json``. It makes NO profitability claim and
awards NO bonus for positive model alpha; the model verdict is a separate,
unscored output.

Scoring model (fixed, no discretion):
- Each of the 20 criteria (A1..E4) has exactly five criterion-specific binary
  one-point checks. A criterion scores an integer 0-5 (count of passed checks).
- Each category (A..E) scores an integer 0-20 (sum of its four criteria).
- The total is an integer 0-100 (sum of the five categories).
- There is no PARTIAL value, no discretionary rounding, and no narrative bonus.

Fail-closed validation (raises ``ScorecardError``):
- a check value that is not strictly binary (bool or 0/1),
- a passed check with no evidence reference (missing evidence),
- an unknown check id or unknown hard-cap id.

Gate decisions (never raise; reported as booleans):
- ``gate_90``/``gate_95`` require total >= min AND every category floor met AND
  no active hard cap at or below that gate's threshold.

Determinism: for identical scorecard + evidence input the serialized JSON output
is byte-identical (sorted keys, no timestamps, no environment data).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_SCORECARD = _REPO_ROOT / "docs" / "kronos_90_to_95_scorecard_v1.json"


class ScorecardError(ValueError):
    """Raised when evidence or scorecard structure is invalid (fail closed)."""


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _coerce_binary(check_id: str, raw: Any) -> bool:
    """Return a strict bool for a check's ``passed`` value or fail closed.

    Accepts only ``True``/``False`` and the integers ``0``/``1``. Everything
    else (floats, strings such as "partial", other ints) is rejected so the
    scorecard cannot be gamed with a fractional or narrative value.
    """
    if isinstance(raw, bool):
        return raw
    # ``bool`` is a subclass of ``int``; the isinstance above already handled it.
    if isinstance(raw, int) and raw in (0, 1):
        return bool(raw)
    raise ScorecardError(
        f"check {check_id!r} has non-binary value {raw!r}; "
        "only true/false or 0/1 are allowed (no PARTIAL)"
    )


def _check_ids(scorecard: Dict[str, Any]) -> List[str]:
    kinds = list(scorecard["check_kinds"])
    ids: List[str] = []
    for cid in scorecard["criteria"]:
        for kind in kinds:
            ids.append(f"{cid}.{kind}")
    return ids


def _evaluate_check(
    check_id: str,
    entry: Any,
) -> Tuple[bool, Optional[str]]:
    """Return (passed, evidence_ref) for one evidence entry, failing closed."""
    if not isinstance(entry, dict):
        raise ScorecardError(
            f"check {check_id!r} evidence must be an object with 'passed' and "
            f"'evidence_ref', got {type(entry).__name__}"
        )
    if "passed" not in entry:
        raise ScorecardError(f"check {check_id!r} evidence missing 'passed'")
    passed = _coerce_binary(check_id, entry["passed"])
    ref = entry.get("evidence_ref")
    ref_str = str(ref).strip() if ref is not None else ""
    if passed and not ref_str:
        raise ScorecardError(
            f"check {check_id!r} is marked passed but cites no evidence_ref "
            "(missing evidence)"
        )
    return passed, (ref_str or None)


def score(scorecard: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the deterministic score dict from scorecard + evidence.

    ``evidence`` shape::

        {
          "checks": {"A1.contract": {"passed": true, "evidence_ref": "..."}, ...},
          "hard_caps_active": ["failed_test_or_build", ...],
          "model_verdict": "NO-GO"
        }
    """
    criteria = scorecard["criteria"]
    categories = scorecard["categories"]
    kinds = list(scorecard["check_kinds"])

    raw_checks = evidence.get("checks", {})
    if not isinstance(raw_checks, dict):
        raise ScorecardError("evidence 'checks' must be an object")

    valid_ids = set(_check_ids(scorecard))
    for cid in raw_checks:
        if cid not in valid_ids:
            raise ScorecardError(f"unknown check id {cid!r} not in scorecard")

    # Per-criterion / per-check evaluation. A check absent from evidence scores 0.
    criterion_scores: Dict[str, int] = {}
    check_results: Dict[str, bool] = {}
    for cid in criteria:
        passed_count = 0
        for kind in kinds:
            key = f"{cid}.{kind}"
            if key in raw_checks:
                passed, _ref = _evaluate_check(key, raw_checks[key])
            else:
                passed = False
            check_results[key] = passed
            if passed:
                passed_count += 1
        criterion_scores[cid] = passed_count

    category_scores: Dict[str, int] = {}
    for cat_id, cat in categories.items():
        category_scores[cat_id] = sum(criterion_scores[c] for c in cat["criteria"])

    total = sum(category_scores.values())

    # Hard caps.
    known_caps = {c["id"]: int(c["caps_below"]) for c in scorecard["hard_caps"]}
    active = evidence.get("hard_caps_active", []) or []
    if not isinstance(active, list):
        raise ScorecardError("evidence 'hard_caps_active' must be a list")
    active_caps: List[str] = []
    for cap in active:
        if cap not in known_caps:
            raise ScorecardError(f"unknown hard cap id {cap!r} not in scorecard")
        active_caps.append(cap)
    active_caps = sorted(set(active_caps))

    def _gate(gate_id: str) -> Dict[str, Any]:
        gate = scorecard["gates"][gate_id]
        total_min = int(gate["total_min"])
        floor_failures: List[str] = []
        for cat_id, cat in categories.items():
            floor = int(cat["floor"][gate_id])
            if category_scores[cat_id] < floor:
                floor_failures.append(cat_id)
        blocking_caps = sorted(
            cap for cap in active_caps if known_caps[cap] in set(gate["blocks_on_caps_below"])
        )
        passed = (
            total >= total_min
            and not floor_failures
            and not blocking_caps
        )
        return {
            "passed": passed,
            "total_min": total_min,
            "total_met": total >= total_min,
            "floor_failures": floor_failures,
            "blocking_caps": blocking_caps,
        }

    result: Dict[str, Any] = {
        "scorecard_id": scorecard["scorecard_id"],
        "schema_version": scorecard["schema_version"],
        "base_sha": scorecard.get("base_sha"),
        "criterion_scores": dict(sorted(criterion_scores.items())),
        "category_scores": dict(sorted(category_scores.items())),
        "total": total,
        "check_results": dict(sorted(check_results.items())),
        "active_hard_caps": active_caps,
        "gates": {"gate_90": _gate("gate_90"), "gate_95": _gate("gate_95")},
        "outputs": {},
        "model_verdict": evidence.get("model_verdict"),
    }

    for out_id, out in scorecard["outputs"].items():
        if not out.get("categories"):
            continue
        result["outputs"][out_id] = {
            "categories": list(out["categories"]),
            "score": sum(category_scores[c] for c in out["categories"]),
            "max": int(out.get("max", 20 * len(out["categories"]))),
        }

    return result


def serialize(result: Dict[str, Any]) -> str:
    """Byte-stable serialization used for determinism guarantees."""
    return json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score Kronos 90->95 completion evidence (deterministic)."
    )
    parser.add_argument(
        "--scorecard",
        default=str(_DEFAULT_SCORECARD),
        help="Path to scorecard JSON (default: %(default)s)",
    )
    parser.add_argument(
        "--evidence",
        required=True,
        help="Path to the evidence JSON file to score",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to write the scored JSON (default: stdout only)",
    )
    args = parser.parse_args(argv)

    scorecard = load_json(Path(args.scorecard))
    evidence = load_json(Path(args.evidence))
    try:
        result = score(scorecard, evidence)
    except ScorecardError as exc:
        print(f"SCORECARD_REJECTED: {exc}", file=sys.stderr)
        return 2

    encoded = serialize(result)
    if args.out:
        Path(args.out).write_text(encoded + "\n", encoding="utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # no-op if already utf-8
    except (AttributeError, ValueError):
        pass
    print(encoded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
