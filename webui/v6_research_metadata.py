"""Bounded metadata extraction for heterogeneous research evidence files."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

MAX_SUMMARY_BYTES: Final = 512 * 1024
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
        files = tuple(path for path in directory.iterdir() if path.is_file() and not path.is_symlink())
    except OSError:
        return ()
    verdicts = sorted(
        (path for path in files if path.suffix.lower() == ".json" and "verdict" in path.name.lower()),
        key=lambda path: path.name,
    )
    by_name = {path.name: path for path in files}
    summaries = [by_name[name] for name in SUMMARY_NAMES if name in by_name and by_name[name] not in verdicts]
    remaining = sorted(
        (
            path
            for path in files
            if path not in verdicts
            and path not in summaries
            and path.suffix.lower() == ".json"
            and any(token in path.name.lower() for token in ("summary", "manifest", "receipt"))
        ),
        key=lambda path: path.name,
    )
    return tuple(verdicts + summaries + remaining)


def _first_text(mapping, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = mapping.get(key)
        if type(value) is str and value.strip():
            return value.strip()
    return "MISSING"


def _algorithm(mapping) -> str:
    direct = _first_text(mapping, ("algorithm", "algorithm_family", "model_family", "policy"))
    if direct != "MISSING":
        return direct
    algorithms = mapping.get("algorithms")
    if type(algorithms) is dict and len(algorithms) == 1:
        key = next(iter(algorithms))
        if type(key) is str and key.strip():
            return key.strip()
    return "MISSING"


def _read_mapping(source: Path) -> tuple[dict | None, str | None]:
    try:
        if source.stat().st_size > MAX_SUMMARY_BYTES:
            return None, "EVIDENCE_TOO_LARGE"
        raw = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "CORRUPT_EVIDENCE"
    if type(raw) is not dict:
        return None, "CORRUPT_EVIDENCE"
    return raw, None


def observe_metadata(directory: Path) -> ObservedMetadata:
    """Prefer explicit verdicts while supplementing missing descriptive fields."""
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
        candidate_status = _first_text(mapping, ("verdict", "state", "status", "result"))
        if status == "MISSING" and candidate_status != "MISSING":
            status = candidate_status
            source_file = source.name
        if algorithm == "MISSING":
            algorithm = _algorithm(mapping)
        if dataset_id == "MISSING":
            dataset_id = _first_text(mapping, ("dataset_id", "dataset_run_id", "dataset"))

    if status != "MISSING":
        return ObservedMetadata(status, algorithm, dataset_id, source_file)
    if valid_source != "MISSING":
        return ObservedMetadata("RECORDED", algorithm, dataset_id, valid_source)
    if first_failure is not None:
        return ObservedMetadata(first_failure[0], "MISSING", "MISSING", first_failure[1])
    return ObservedMetadata("RECORDED", "MISSING", "MISSING", "MISSING")
