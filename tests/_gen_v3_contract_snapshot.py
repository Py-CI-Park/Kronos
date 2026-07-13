"""CLI: regenerate the committed F6 contract baseline.

Usage:
    py -3.11 tests/_gen_v3_contract_snapshot.py

Writes ``tests/_v3_contract_snapshot.json`` from ``build_snapshot()`` and prints
the reconciliation counts. Run this whenever a Gate-T source-substring
assertion is intentionally added, removed, or changed so the committed baseline
tracks the new contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _v3_contract import SNAPSHOT_PATH, build_snapshot, verify_snapshot  # noqa: E402


def main() -> int:
    snapshot = build_snapshot()
    # Sanity: the freshly built contract must hold against the current source
    # before we commit it as the baseline.
    verify_snapshot(snapshot)

    SNAPSHOT_PATH.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {SNAPSHOT_PATH.relative_to(Path(__file__).resolve().parents[1])}")
    print("reconciliation counts:")
    print(json.dumps(snapshot["counts"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
