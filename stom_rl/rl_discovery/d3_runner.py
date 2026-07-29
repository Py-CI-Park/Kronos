"""CLI and terminal receipt boundary for Type2-D3 execution."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

from stom_rl.daily_type1_contract import canonical_json_bytes
from stom_rl.rl_discovery.d2_custody import assert_plain_path
from stom_rl.rl_discovery.d3_execution import D3RunProfile, approve_d3_smoke, execute_d3
from stom_rl.rl_discovery.storage import atomic_write_bytes, contained_path


def run_d3(repo_root: Path, *, profile: D3RunProfile, run_id: str | None = None, approved_smoke: Path | None = None) -> Path:
    """Create one immutable run and terminalize every failure or interrupt."""

    root = repo_root.absolute()
    run_root = root / "webui" / "rl_runs" / "rl_discovery"
    assert_plain_path(run_root, anchor=root, require_file=False)
    timestamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    selected_id = run_id or f"type2-d3-{profile.value.lower()}-{timestamp}"
    run_dir = contained_path(run_root, selected_id)
    if run_dir.exists():
        raise FileExistsError("D3 run ID already exists")
    run_dir.mkdir(parents=True)
    try:
        return execute_d3(root, run_dir, profile=profile, approved_smoke=approved_smoke)
    except BaseException as exc:  # noqa: BROAD_EXCEPT_OK - terminal receipt must include KeyboardInterrupt.
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
    parser.add_argument("--profile", choices=[item.value for item in D3RunProfile], required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--run-id")
    parser.add_argument("--approved-smoke", type=Path)
    args = parser.parse_args()
    try:
        result = run_d3(
            args.repo_root.resolve(),
            profile=D3RunProfile(args.profile),
            run_id=args.run_id,
            approved_smoke=args.approved_smoke,
        )
    except BaseException as exc:  # noqa: BROAD_EXCEPT_OK - CLI boundary reports every terminal failure.
        print(f"D3 failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
