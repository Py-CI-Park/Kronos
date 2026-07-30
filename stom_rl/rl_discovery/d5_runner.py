"""CLI and terminal receipt boundary for Type2-D5 execution."""

from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import sys

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d2_custody import assert_plain_path
from stom_rl.rl_discovery.d5_execution import D5RunProfile, execute_d5
from stom_rl.rl_discovery.storage import (
    RunDirectoryGuard,
    create_run_directory,
)


class D5CliArgs(argparse.Namespace):
    profile: str = ""
    repo_root: Path = Path()
    run_id: str | None = None
    approved_smoke: Path | None = None


def run_d5(
    repo_root: Path,
    *,
    profile: D5RunProfile,
    run_id: str | None = None,
    approved_smoke: Path | None = None,
    approval_key: bytes | None = None,
) -> Path:
    """Create one immutable D5 run and terminalize every failure."""

    root = repo_root.absolute()
    run_root = root / "webui" / "rl_runs" / "rl_discovery"
    _ = assert_plain_path(run_root, anchor=root, require_file=False)
    timestamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    selected_id = run_id or f"type2-d5-{profile.value.lower()}-{timestamp}"
    run_dir = create_run_directory(run_root, selected_id)
    run_guard = RunDirectoryGuard.capture(run_root, run_dir)
    try:
        return execute_d5(
            root,
            run_dir,
            run_guard=run_guard,
            profile=profile,
            approved_smoke=approved_smoke,
            approval_key=approval_key,
        )
    # Terminal evidence must also cover operator interrupts such as KeyboardInterrupt.
    except (BaseException,) as exc:
        receipt = run_guard.verify() / "terminal_receipt.json"
        if not receipt.exists():
            _ = run_guard.publish_bytes(
                canonical_json_bytes(
                    {
                        "profile": profile.value,
                        "status": "FAILED",
                        "verdict": "NO_GO",
                        "reason": f"{type(exc).__name__}: {exc}",
                        "fresh_oos": "NOT_RUN_NO_READ",
                    }
                ),
                "terminal_receipt.json",
            )
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--profile", choices=[item.value for item in D5RunProfile], required=True
    )
    _ = parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    _ = parser.add_argument("--run-id")
    _ = parser.add_argument("--approved-smoke", type=Path)
    args = parser.parse_args(namespace=D5CliArgs())
    raw_key = os.environ.get("KRONOS_D5_APPROVAL_KEY_HEX", "")
    try:
        approval_key = bytes.fromhex(raw_key) if raw_key else None
    except ValueError:
        print(
            "D5 failed: KRONOS_D5_APPROVAL_KEY_HEX must be hexadecimal", file=sys.stderr
        )
        return 1
    try:
        result = run_d5(
            args.repo_root.resolve(),
            profile=D5RunProfile(args.profile),
            run_id=args.run_id,
            approved_smoke=args.approved_smoke,
            approval_key=approval_key,
        )
    # The CLI translates every terminal condition to a stable non-zero exit.
    except (BaseException,) as exc:
        print(f"D5 failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
