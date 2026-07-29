"""Separate operator command for approving a completed D4 Smoke."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from stom_rl.rl_discovery.d4_approval import create_d4_smoke_approval


class D4ApprovalCliArgs(argparse.Namespace):
    smoke: Path = Path()
    run_root: Path = Path()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("smoke", type=Path)
    _ = parser.add_argument("--run-root", type=Path, required=True)
    namespace = parser.parse_args(namespace=D4ApprovalCliArgs())
    smoke = namespace.smoke
    run_root = namespace.run_root
    raw_key = os.environ.get("KRONOS_D4_APPROVAL_KEY_HEX", "")
    try:
        key = bytes.fromhex(raw_key)
    except ValueError:
        print("KRONOS_D4_APPROVAL_KEY_HEX must be hexadecimal", file=sys.stderr)
        return 1
    try:
        result = create_d4_smoke_approval(smoke, run_root=run_root, approval_key=key)
    except (OSError, PermissionError, ValueError) as exc:
        print(f"D4 approval failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
