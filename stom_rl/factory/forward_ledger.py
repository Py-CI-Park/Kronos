"""Read-only forward/paper evidence ledger writer for factory runs.

The writer lives under ``stom_rl/factory`` and writes only generated research
artifacts.  Web/dashboard code must remain read-only consumers of these files.
Records are model decisions and later outcomes, not orders or broker intents.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = 1
VALID_DECISIONS = {"TAKE", "SKIP"}
VALID_STATUS = {"pending", "resolved"}
GUARDRAIL = (
    "Read-only forward/paper evidence ledger; generated research artifact only; "
    "no orders, no broker integration, no live-readiness or profit claim."
)
DEFAULT_OUTPUT_ROOT = Path("webui") / "rl_runs" / "forward_ledger"



class ForwardLedgerError(ValueError):
    """Raised when forward-ledger inputs violate the schema contract."""


@dataclass(frozen=True, slots=True)
class ForwardLedgerConfig:
    edge_ledger_path: Path
    output_path: Path
    run_id: str
    model_version: str
    fill_assumption: str
    cost_bps: float = 23.0
    include_outcomes: bool = True
    recorded_at_utc: str | None = None
    output_root: Path | None = DEFAULT_OUTPUT_ROOT



def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_id(run_id: str, session: str, code: str) -> str:
    return f"{run_id}:{session}:{code}"


def load_edge_rows(edge_ledger_path: Path | str) -> list[dict[str, Any]]:
    payload = json.loads(Path(edge_ledger_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ForwardLedgerError("edge ledger must be a JSON object")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ForwardLedgerError("edge ledger rows must be a non-empty list")
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ForwardLedgerError(f"edge ledger row {idx} is not an object")
        missing = {"symbol", "session", "p_win", "edge_pct", "decision"} - set(row)
        if missing:
            raise ForwardLedgerError(f"edge ledger row {idx} missing columns: {sorted(missing)}")
        decision = str(row["decision"])
        if decision not in VALID_DECISIONS:
            raise ForwardLedgerError(f"edge ledger row {idx} has invalid decision: {decision}")
        out.append(dict(row))
    return out


def build_forward_records(config: ForwardLedgerConfig) -> list[dict[str, Any]]:
    """Convert probability-lane decisions into forward/paper ledger records."""

    if not config.run_id:
        raise ForwardLedgerError("run_id is required")
    if not config.model_version:
        raise ForwardLedgerError("model_version is required")
    if not config.fill_assumption:
        raise ForwardLedgerError("fill_assumption is required")
    recorded_at = config.recorded_at_utc or _utc_now()
    rows = load_edge_rows(config.edge_ledger_path)
    records: list[dict[str, Any]] = []
    for row in rows:
        session = str(row["session"])
        code = str(row["symbol"])
        outcome = row.get("net_pct_23bp") if config.include_outcomes else None
        status = "resolved" if outcome is not None else "pending"
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "record_id": _record_id(config.run_id, session, code),
                "recorded_at_utc": recorded_at,
                "session": session,
                "code": code,
                "run_id": config.run_id,
                "model_version": config.model_version,
                "p_win": float(row["p_win"]),
                "edge_pct": float(row["edge_pct"]),
                "decision": str(row["decision"]),
                "fill_assumption": config.fill_assumption,
                "realized_outcome_pct": float(outcome) if outcome is not None else None,
                "baseline_outcome_pct": float(outcome) if outcome is not None else None,
                "outcome_status": status,
                "cost_bps": float(config.cost_bps),
                "guardrail": GUARDRAIL,
            }
        )
    return records


def _read_existing_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ForwardLedgerError(f"existing ledger line {line_no} is not an object")
        record_id = payload.get("record_id")
        status = payload.get("outcome_status")
        if not isinstance(record_id, str) or not record_id:
            raise ForwardLedgerError(f"existing ledger line {line_no} lacks record_id")
        if status not in VALID_STATUS:
            raise ForwardLedgerError(f"existing ledger line {line_no} has invalid status: {status}")
        records.append(payload)
    return records
def _ensure_under_root(output_path: Path, output_root: Path | None) -> Path:
    path = output_path.expanduser().resolve(strict=False)
    if output_root is None:
        return path
    root = output_root.expanduser().resolve(strict=False)
    if path != root and not path.is_relative_to(root):
        raise ForwardLedgerError(f"output path must be under generated forward-ledger root: {root}")
    return path




def append_forward_records(
    output_path: Path | str,
    records: Iterable[Mapping[str, Any]],
    *,
    output_root: Path | str | None = None,
) -> dict[str, Any]:
    """Append records while skipping duplicate ``record_id`` values.

    Duplicate policy is intentionally conservative for auditability: existing
    records are left untouched and the duplicate is skipped.  A future resolved
    update must use a new record id or a separately preregistered migration.
    """

    root = Path(output_root) if output_root is not None else None
    path = _ensure_under_root(Path(output_path), root)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_existing_jsonl(path)
    seen = {str(row["record_id"]) for row in existing}
    appended: list[dict[str, Any]] = []
    skipped = 0
    for record in records:
        payload = dict(record)
        record_id = payload.get("record_id")
        status = payload.get("outcome_status")
        if not isinstance(record_id, str) or not record_id:
            raise ForwardLedgerError("record missing record_id")
        if status not in VALID_STATUS:
            raise ForwardLedgerError(f"record has invalid outcome_status: {status}")
        if record_id in seen:
            skipped += 1
            continue
        seen.add(record_id)
        appended.append(payload)
    if appended:
        with path.open("a", encoding="utf-8") as handle:
            for record in appended:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    status_counts: dict[str, int] = {}
    for record in [*existing, *appended]:
        status = str(record["outcome_status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "path": str(path),
        "existing_count": len(existing),
        "appended_count": len(appended),
        "skipped_duplicate_count": skipped,
        "total_count": len(existing) + len(appended),
        "status_counts": status_counts,
        "duplicate_policy": "skip_existing_record_id",
        "schema_version": SCHEMA_VERSION,
        "guardrail": GUARDRAIL,
    }


def write_forward_ledger(config: ForwardLedgerConfig) -> dict[str, Any]:
    records = build_forward_records(config)
    summary = append_forward_records(config.output_path, records, output_root=config.output_root)
    summary.update(
        {
            "run_id": config.run_id,
            "model_version": config.model_version,
            "fill_assumption": config.fill_assumption,
            "cost_bps": float(config.cost_bps),
            "include_outcomes": bool(config.include_outcomes),
            "source_edge_ledger_path": str(config.edge_ledger_path),
            "output_root": str(config.output_root) if config.output_root is not None else None,
        }
    )
    summary_path = Path(config.output_path).with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edge-ledger", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--fill-assumption", required=True)
    parser.add_argument("--cost-bps", type=float, default=23.0)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="generated forward-ledger root")
    parser.add_argument("--pending", action="store_true", help="write decisions without realized outcomes")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = write_forward_ledger(
        ForwardLedgerConfig(
            edge_ledger_path=Path(args.edge_ledger),
            output_path=Path(args.output),
            run_id=str(args.run_id),
            model_version=str(args.model_version),
            fill_assumption=str(args.fill_assumption),
            cost_bps=float(args.cost_bps),
            include_outcomes=not bool(args.pending),
            output_root=Path(args.output_root) if args.output_root else None,
        )
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
