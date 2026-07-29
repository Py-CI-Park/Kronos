"""CLI and terminal receipt boundary for Type2-D4 execution."""

from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import sys

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d2_custody import assert_plain_path
from stom_rl.rl_discovery.d4_execution import D4RunProfile, execute_d4
from stom_rl.rl_discovery.storage import atomic_write_bytes, contained_path


class D4CliArgs(argparse.Namespace):
    profile: str = ""
    repo_root: Path = Path()
    run_id: str | None = None
    approved_smoke: Path | None = None


def run_d4(
    repo_root: Path,
    *,
    profile: D4RunProfile,
    run_id: str | None = None,
    approved_smoke: Path | None = None,
    approval_key: bytes | None = None,
) -> Path:
    """Create one immutable D4 run and terminalize every failure or interrupt."""

    root = repo_root.absolute()
    run_root = root / "webui" / "rl_runs" / "rl_discovery"
    _ = assert_plain_path(run_root, anchor=root, require_file=False)
    timestamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    selected_id = run_id or f"type2-d4-{profile.value.lower()}-{timestamp}"
    run_dir = contained_path(run_root, selected_id)
    if run_dir.exists():
        raise FileExistsError("D4 run ID already exists")
    run_dir.mkdir(parents=True)
    try:
        return execute_d4(
            root,
            run_dir,
            profile=profile,
            approved_smoke=approved_smoke,
            approval_key=approval_key,
        )
    except BaseException as exc:  # noqa: BLE001 - terminal receipt must include operator interrupts.
        receipt = contained_path(run_dir, "terminal_receipt.json")
        if not receipt.exists():
            atomic_write_bytes(receipt, canonical_json_bytes({
                "profile": profile.value,
                "status": "FAILED",
                "verdict": "NO_GO",
                "reason": f"{type(exc).__name__}: {exc}",
                "fresh_oos": "NOT_RUN_NO_READ",
            }))
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--profile", choices=[item.value for item in D4RunProfile], required=True)
    _ = parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    _ = parser.add_argument("--run-id")
    _ = parser.add_argument("--approved-smoke", type=Path)
    args = parser.parse_args(namespace=D4CliArgs())
    raw_key = os.environ.get("KRONOS_D4_APPROVAL_KEY_HEX", "")
    try:
        approval_key = bytes.fromhex(raw_key) if raw_key else None
    except ValueError:
        print("D4 failed: KRONOS_D4_APPROVAL_KEY_HEX must be hexadecimal", file=sys.stderr)
        return 1
    try:
        result = run_d4(
            args.repo_root.resolve(),
            profile=D4RunProfile(args.profile),
            run_id=args.run_id,
            approved_smoke=args.approved_smoke,
            approval_key=approval_key,
        )
    except BaseException as exc:  # noqa: BLE001 - CLI boundary reports every terminal failure.
        print(f"D4 failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
