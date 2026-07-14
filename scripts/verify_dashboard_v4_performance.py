"""Verify a G008 dashboard-v4 performance capture against the fixed all-tab
performance budgets encoded in
`webui/v2_src/src/v4/qa/performanceBudget.ts`.

This script is:
  - standard-library only (no third-party imports),
  - read-only and side-effect free on product state (it only reads the
    `--input` capture file and optionally writes a report to `--out`),
  - never makes a network call.

It accepts a JSON performance capture (a mapping of budget metric name to
either a single already-reduced duration in milliseconds, or a list of raw
sample durations that this script reduces with the 95th percentile —
`percentile95`, never the mean, so a slow tail cannot be averaged away). The
`isolatedCardRetryVisible` field is a strict boolean requirement, not a
duration.

Any missing key, non-finite/negative/empty-sample value, or over-budget
value fails closed: the report's `pass` is `false` and the process exits 1.
There is no code path that lets a malformed or incomplete capture report as
passing.

Usage:
    py -3.11 scripts/verify_dashboard_v4_performance.py --input capture.json
    py -3.11 scripts/verify_dashboard_v4_performance.py --input capture.json --out report.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

Number = Union[int, float]

# Keep these limits byte-for-byte in sync with the TypeScript contract in
# webui/v2_src/src/v4/qa/performanceBudget.ts (PERFORMANCE_BUDGET_LIMITS_MS).
PERFORMANCE_BUDGET_LIMITS_MS: Dict[str, int] = {
    "firstCriticalCardColdMs": 3_000,
    "firstCriticalCardWarmMs": 1_500,
    "fullCriticalHydrationColdMs": 10_000,
    "fullCriticalHydrationWarmMs": 6_000,
    "warmCriticalApiMs": 2_000,
    "coldCriticalApiMs": 5_000,
    "isolatedCardTimeoutMs": 20_500,
    "commandPaletteOpenMs": 100,
    "thousandItemQueryFilterMs": 150,
}

RETRY_KEY = "isolatedCardRetryVisible"
REQUIRED_KEYS = tuple(PERFORMANCE_BUDGET_LIMITS_MS) + (RETRY_KEY,)


class CaptureError(RuntimeError):
    """Raised when the capture payload cannot be evaluated at all."""


def _is_finite_number(value: Any) -> bool:
    # bool is an int subclass in Python; a capture field must be a genuine
    # number, not True/False leaking in as 1/0.
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def percentile95(samples: Any) -> Optional[Number]:
    """Reduce raw samples to their 95th percentile via nearest-rank.

    Returns None (fail-closed) for anything that is not a non-empty list of
    finite, non-negative numbers, instead of coercing it into a value that
    could pass silently.
    """
    if not isinstance(samples, list) or len(samples) == 0:
        return None
    cleaned: List[Number] = []
    for sample in samples:
        if not _is_finite_number(sample) or sample < 0:
            return None
        cleaned.append(sample)
    cleaned.sort()
    rank = min(len(cleaned), max(1, math.ceil(0.95 * len(cleaned))))
    return cleaned[rank - 1]


def _resolve_metric(value: Any) -> Optional[Number]:
    if isinstance(value, list):
        return percentile95(value)
    if _is_finite_number(value) and value >= 0:
        return value
    return None


def evaluate_capture(capture: Dict[str, Any]) -> Dict[str, Any]:
    """Fail-closed evaluation of one capture against every named budget."""
    if not isinstance(capture, dict):
        raise CaptureError("capture payload must be a JSON object")

    failures: List[str] = []
    metrics: Dict[str, Any] = {}
    missing_keys = [key for key in REQUIRED_KEYS if key not in capture]

    for key, limit in PERFORMANCE_BUDGET_LIMITS_MS.items():
        if key not in capture:
            failures.append(f"{key}:missing")
            metrics[key] = {"resolved": None, "limit": limit, "pass": False}
            continue
        resolved = _resolve_metric(capture[key])
        if resolved is None:
            failures.append(f"{key}:invalid")
            metrics[key] = {"resolved": None, "limit": limit, "pass": False}
        elif resolved > limit:
            failures.append(f"{key}:{resolved}>{limit}")
            metrics[key] = {"resolved": resolved, "limit": limit, "pass": False}
        else:
            metrics[key] = {"resolved": resolved, "limit": limit, "pass": True}

    if RETRY_KEY not in capture:
        failures.append(f"{RETRY_KEY}:missing")
        retry_pass = False
    else:
        retry_pass = capture[RETRY_KEY] is True
        if not retry_pass:
            failures.append(f"{RETRY_KEY}:missing_or_false")

    return {
        "schema_ok": len(missing_keys) == 0,
        "missing_keys": missing_keys,
        "metrics": metrics,
        RETRY_KEY: {"declared": capture.get(RETRY_KEY, None), "pass": retry_pass},
        "failures": failures,
        "pass": len(failures) == 0,
    }


def load_capture(input_path: Path) -> Dict[str, Any]:
    text = input_path.read_text(encoding="utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise CaptureError(f"{input_path}: top-level JSON must be an object")
    return payload


def build_report(input_path: Path) -> Dict[str, Any]:
    try:
        capture = load_capture(input_path)
    except (OSError, json.JSONDecodeError, CaptureError) as exc:
        return {
            "input": str(input_path),
            "schema_ok": False,
            "missing_keys": list(REQUIRED_KEYS),
            "metrics": {},
            RETRY_KEY: {"declared": None, "pass": False},
            "failures": [f"capture_unreadable:{exc}"],
            "pass": False,
        }
    result = evaluate_capture(capture)
    return {"input": str(input_path), **result}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a dashboard-v4 performance capture against the fixed G008 "
            "budgets. Read-only, standard-library only, no network calls."
        )
    )
    parser.add_argument("--input", required=True, help="Path to a JSON performance capture file.")
    parser.add_argument("--out", default=None, help="Optional path to write the deterministic JSON report.")
    args = parser.parse_args(argv)

    report = build_report(Path(args.input))
    rendered = json.dumps(report, indent=2, sort_keys=True)

    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
