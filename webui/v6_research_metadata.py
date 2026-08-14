"""Bounded metadata extraction for heterogeneous research evidence files."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from pydantic import TypeAdapter

from webui.v6_daily_market_publication import observe_daily_market_publication

MAX_SUMMARY_BYTES: Final = 512 * 1024
JSON_OBJECT: Final = TypeAdapter(dict[str, object])
SUMMARY_NAMES: Final = (
    "rl_live_summary.json",
    "run_manifest.json",
    "dataset_manifest.json",
    "research_receipt.json",
    "summary.json",
)


@dataclass(frozen=True, slots=True)
class ObservedMetadata:
    status: str
    algorithm: str
    dataset_id: str
    source_file: str


def _candidates(directory: Path) -> tuple[Path, ...]:
    try:
        files = tuple(
            path
            for path in directory.iterdir()
            if path.is_file() and not path.is_symlink()
        )
    except OSError:
        return ()
    verdicts = sorted(
        (
            path
            for path in files
            if path.suffix.lower() == ".json" and "verdict" in path.name.lower()
        ),
        key=lambda path: path.name,
    )
    by_name = {path.name: path for path in files}
    summaries = [
        by_name[name]
        for name in SUMMARY_NAMES
        if name in by_name and by_name[name] not in verdicts
    ]
    remaining = sorted(
        (
            path
            for path in files
            if path not in verdicts
            and path not in summaries
            and path.suffix.lower() == ".json"
            and any(
                token in path.name.lower()
                for token in ("summary", "manifest", "receipt")
            )
        ),
        key=lambda path: path.name,
    )
    return tuple(verdicts + summaries + remaining)


def _first_text(mapping: Mapping[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = mapping.get(key)
        if type(value) is str and value.strip():
            return value.strip()
    return "MISSING"


def _algorithm(mapping: Mapping[str, object]) -> str:
    direct = _first_text(
        mapping, ("algorithm", "algorithm_family", "model_family", "policy")
    )
    if direct != "MISSING":
        return direct
    if mapping.get("schema_version") == "kronos_existing_db_60_historical_summary.v1":
        return "CQL"
    algorithms = mapping.get("algorithms")
    algorithm_map = (
        cast(dict[object, object], algorithms) if isinstance(algorithms, dict) else {}
    )
    if len(algorithm_map) == 1:
        key = next(iter(algorithm_map))
        if type(key) is str and key.strip():
            return key.strip()
    return "MISSING"


def _dataset_id(mapping: Mapping[str, object]) -> str:
    direct = _first_text(mapping, ("dataset_id", "dataset_run_id", "dataset"))
    if direct != "MISSING":
        return direct
    if mapping.get("schema_version") == "kronos_existing_db_60_historical_summary.v1":
        return "EXISTING_DB_60_SCORE_DAYS_20260309_20260611"
    return "MISSING"


def _read_mapping(source: Path) -> tuple[dict[str, object] | None, str | None]:
    try:
        if source.stat().st_size > MAX_SUMMARY_BYTES:
            return None, "EVIDENCE_TOO_LARGE"
        raw = JSON_OBJECT.validate_python(
            cast(object, json.loads(source.read_text(encoding="utf-8-sig")))
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "CORRUPT_EVIDENCE"
    return raw, None


def observe_metadata(directory: Path) -> ObservedMetadata:
    """Prefer explicit verdicts while supplementing missing descriptive fields."""
    publication = observe_daily_market_publication(directory)
    if publication.state == "INVALID":
        source = (
            "bundle_manifest.json"
            if (directory / "bundle_manifest.json").exists()
            else "publication_incomplete"
        )
        return ObservedMetadata("CORRUPT_EVIDENCE", "MISSING", "MISSING", source)
    if publication.state == "VALID" and publication.summary_bytes is not None:
        try:
            mapping = JSON_OBJECT.validate_python(
                cast(
                    object,
                    json.loads(publication.summary_bytes.decode("utf-8-sig")),
                )
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return ObservedMetadata(
                "CORRUPT_EVIDENCE", "MISSING", "MISSING", "summary.json"
            )
        observed_status = _first_text(
            mapping,
            ("verdict", "state", "status", "result"),
        )
        if directory.name == "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_001":
            observed_status = "LEGACY_EXPLORATORY_CANDIDATE_TEST_FEATURES_CONSUMED"
        return ObservedMetadata(
            observed_status,
            _algorithm(mapping),
            _dataset_id(mapping),
            publication.source_file or "summary.json",
        )
    candidates = _candidates(directory)
    if not candidates:
        return ObservedMetadata("RECORDED", "MISSING", "MISSING", "MISSING")

    status = algorithm = dataset_id = "MISSING"
    source_file = "MISSING"
    first_failure: tuple[str, str] | None = None
    valid_source = "MISSING"
    for source in candidates:
        mapping, failure = _read_mapping(source)
        if failure is not None:
            if first_failure is None:
                first_failure = (failure, source.name)
            continue
        if mapping is None:
            continue
        if valid_source == "MISSING":
            valid_source = source.name
        candidate_status = _first_text(
            mapping, ("verdict", "state", "status", "result")
        )
        if status == "MISSING" and candidate_status != "MISSING":
            status = candidate_status
            source_file = source.name
        if algorithm == "MISSING":
            algorithm = _algorithm(mapping)
        if dataset_id == "MISSING":
            dataset_id = _dataset_id(mapping)

    if status != "MISSING":
        return ObservedMetadata(status, algorithm, dataset_id, source_file)
    if valid_source != "MISSING":
        return ObservedMetadata("RECORDED", algorithm, dataset_id, valid_source)
    if first_failure is not None:
        return ObservedMetadata(
            first_failure[0], "MISSING", "MISSING", first_failure[1]
        )
    return ObservedMetadata("RECORDED", "MISSING", "MISSING", "MISSING")
