"""Public run lifecycle for D6R2."""

from __future__ import annotations

from pathlib import Path

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d6r2_execution import D6R2RunProfile, execute_d6r2
from stom_rl.rl_discovery.storage import RunDirectoryGuard, create_run_directory


def run_d6r2(
    repo_root: Path,
    *,
    run_root: Path,
    run_id: str,
    profile: D6R2RunProfile,
    approved_smoke: Path | None = None,
) -> Path:
    run_dir = create_run_directory(run_root, run_id)
    guard = RunDirectoryGuard.capture(run_root, run_dir)
    try:
        return execute_d6r2(repo_root, guard=guard, profile=profile, approved_smoke=approved_smoke)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        if not (guard.run_dir / "terminal_receipt.json").exists():
            _ = guard.publish_bytes(
                canonical_json_bytes(
                    {
                        "schema_version": "kronos.rl-discovery.d6r2.receipt.v1",
                        "profile": profile.value,
                        "status": "FAILED",
                        "verdict": "NO_GO",
                        "error_type": type(exc).__name__,
                        "fresh_oos": "NOT_RUN_NO_READ",
                        "d7": "LOCKED",
                        "live_broker_order_allowed": False,
                    }
                ),
                "terminal_receipt.json",
            )
        raise


__all__ = ["D6R2RunProfile", "run_d6r2"]
