"""Public lifecycle and terminal receipt boundary for D5S runs."""

from __future__ import annotations

from pathlib import Path

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d5s_execution import D5SProfile, execute_d5s
from stom_rl.rl_discovery.storage import RunDirectoryGuard, create_run_directory


def run_d5s(
    repo_root: Path,
    *,
    run_root: Path,
    run_id: str,
    profile: D5SProfile,
    approved_smoke: Path | None = None,
    approval_key: bytes | None = None,
) -> Path:
    run_dir = create_run_directory(run_root, run_id)
    guard = RunDirectoryGuard.capture(run_root, run_dir)
    try:
        return execute_d5s(
            repo_root,
            guard=guard,
            profile=profile,
            approved_smoke=approved_smoke,
            approval_key=approval_key,
        )
    except BaseException as exc:  # noqa: BLE001  # BROAD_EXCEPT_OK terminal boundary
        receipt = guard.run_dir / "terminal_receipt.json"
        if not receipt.exists():
            _ = guard.publish_bytes(
                canonical_json_bytes(
                    {
                        "schema_version": "kronos.rl-discovery.d5s.receipt.v1",
                        "profile": profile.value,
                        "status": "FAILED",
                        "verdict": "NO_GO",
                        "error_type": type(exc).__name__,
                        "fresh_oos": "NOT_RUN_NO_READ",
                        "live_broker_order_allowed": False,
                    }
                ),
                "terminal_receipt.json",
            )
        raise


__all__ = ["D5SProfile", "run_d5s"]
