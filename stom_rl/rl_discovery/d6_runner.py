"""Public lifecycle boundary for D6 reused-validation runs."""

from __future__ import annotations

from pathlib import Path

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d6_execution import execute_d6
from stom_rl.rl_discovery.storage import RunDirectoryGuard, create_run_directory


def run_d6(
    repo_root: Path,
    *,
    run_root: Path,
    run_id: str,
    recovery_run: Path | None = None,
) -> Path:
    run_dir = create_run_directory(run_root, run_id)
    guard = RunDirectoryGuard.capture(run_root, run_dir)
    try:
        return execute_d6(repo_root, guard=guard, recovery_run=recovery_run)
    except BaseException as exc:  # BROAD_EXCEPT_OK terminal boundary
        receipt = guard.run_dir / "terminal_receipt.json"
        if not receipt.exists():
            _ = guard.publish_bytes(
                canonical_json_bytes(
                    {
                        "schema_version": "kronos.rl-discovery.d6.receipt.v1",
                        "profile": "PRIMARY",
                        "status": "FAILED",
                        "verdict": "NO_GO",
                        "error_type": type(exc).__name__,
                        "reused_validation": "FAILED",
                        "fresh_oos": "NOT_RUN_NO_READ",
                        "live_broker_order_allowed": False,
                    }
                ),
                "terminal_receipt.json",
            )
        raise


__all__ = ["run_d6"]
