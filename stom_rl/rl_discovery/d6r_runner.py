"""Public lifecycle and terminal receipt boundary for D6R runs."""

from __future__ import annotations

from pathlib import Path

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d6r_execution import D6RRunProfile, execute_d6r
from stom_rl.rl_discovery.storage import RunDirectoryGuard, create_run_directory


def run_d6r(
    repo_root: Path,
    *,
    run_root: Path,
    run_id: str,
    profile: D6RRunProfile,
    approved_smoke: Path | None = None,
) -> Path:
    run_dir = create_run_directory(run_root, run_id)
    guard = RunDirectoryGuard.capture(run_root, run_dir)
    try:
        return execute_d6r(
            repo_root,
            guard=guard,
            profile=profile,
            approved_smoke=approved_smoke,
        )
    except BaseException as exc:  # BROAD_EXCEPT_OK terminal boundary
        receipt = guard.run_dir / "terminal_receipt.json"
        if not receipt.exists():
            _ = guard.publish_bytes(
                canonical_json_bytes(
                    {
                        "schema_version": "kronos.rl-discovery.d6r.receipt.v1",
                        "profile": profile.value,
                        "status": "FAILED",
                        "verdict": "NO_GO",
                        "error_type": type(exc).__name__,
                        "reused_validation": "NO_READ_ALREADY_CONSUMED_DIAGNOSTIC_ONLY",
                        "fresh_oos": "NOT_RUN_NO_READ",
                        "d7": "LOCKED",
                        "live_broker_order_allowed": False,
                    }
                ),
                "terminal_receipt.json",
            )
        raise


__all__ = ["D6RRunProfile", "run_d6r"]
