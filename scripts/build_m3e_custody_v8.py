"""Machine-only bootstrap for the V8 M3E partitioned custody artifacts.

The command prints commitments only.  It never prints rows, labels, test paths,
or test-derived statistics.  The sealed test sink must be placed in a separate
custodian-controlled location before production use.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from stom_rl.daily_v6_dataset import write_partitioned_h1_dataset


class DurableExclusiveSink:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = path.open("xb")
        self._closed = False

    def write(self, data: bytes) -> None:
        if self._closed:
            raise ValueError("sealed sink is closed")
        self._handle.write(data)

    def close(self) -> None:
        if self._closed:
            return
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self._handle.close()
        self._closed = True

    def abort(self) -> None:
        if not self._closed:
            self._handle.close()
            self._closed = True


def main() -> int:
    parser = argparse.ArgumentParser(description="Build partitioned M3E custody artifacts without displaying test data.")
    parser.add_argument("--public-root", required=True)
    parser.add_argument("--sealed-test-path", required=True)
    parser.add_argument("--custody-uid", required=True)
    parser.add_argument("--prereg-id", required=True)
    args = parser.parse_args()

    sealed_path = Path(args.sealed_test_path)
    sink = DurableExclusiveSink(sealed_path)
    try:
        result = write_partitioned_h1_dataset(
            public_root=Path(args.public_root),
            sealed_test_sink=sink,
            custody_uid=args.custody_uid,
            prereg_id=args.prereg_id,
        )
    except BaseException:
        sink.abort()
        sealed_path.unlink(missing_ok=True)
        raise

    manifest = result["manifest"]
    print(json.dumps({
        "status": "GENESIS_SEALED",
        "custody_uid": manifest["custody_uid"],
        "public_artifact_sha256": manifest["public_artifact"]["sha256"],
        "sealed_test_sha256": manifest["sealed_test_commitment"]["sha256"],
        "test_state": "NOT_RUN",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
