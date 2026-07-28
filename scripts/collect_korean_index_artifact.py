#!/usr/bin/env python3
"""Explicit pykrx-only Korean index artifact collector.

Importing this script is side-effect-free: pykrx is imported only inside the
runtime provider after the CLI is invoked.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stom_rl.korean_index_source import (  # noqa: E402
    KoreanIndexArtifactError,
    PYKRX_PACKAGE_VERSION,
    collect_and_write_index_artifacts,
    supported_markets,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect immutable pykrx-only KOSPI/KOSDAQ index level artifacts."
    )
    parser.add_argument("--market", required=True, choices=supported_markets(), help="Exact market: KOSPI or KOSDAQ.")
    parser.add_argument("--start-date", required=True, help="Requested start date, YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Requested end date, YYYY-MM-DD.")
    parser.add_argument("--output-dir", required=True, help="Directory for content-addressed JSON artifacts.")
    return parser.parse_args(argv)


def pykrx_package_version() -> str:
    """Return the installed pykrx package version without importing it."""

    try:
        return importlib.metadata.version("pykrx")
    except importlib.metadata.PackageNotFoundError as exc:
        raise KoreanIndexArtifactError("pykrx is not installed; install optional pykrx==1.2.8 research dependency") from exc


def pykrx_index_provider(*, market: str, index_code: str, index_name: str, start_date: str, end_date: str) -> Any:
    """Fetch pykrx index rows; this is the only pykrx import boundary."""

    del market, index_name
    from pykrx import stock  # type: ignore

    return stock.get_index_ohlcv_by_date(start_date.replace("-", ""), end_date.replace("-", ""), index_code)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    version = pykrx_package_version()
    if version != PYKRX_PACKAGE_VERSION:
        raise KoreanIndexArtifactError(f"pykrx must be exactly {PYKRX_PACKAGE_VERSION}, got {version}")
    receipt = collect_and_write_index_artifacts(
        market=args.market,
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=args.output_dir,
        provider=pykrx_index_provider,
        provider_package_version=version,
    )
    sys.stdout.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KoreanIndexArtifactError, OSError, ValueError) as exc:
        sys.stderr.write(f"korean index collection failed closed: {exc}\n")
        raise SystemExit(1)
