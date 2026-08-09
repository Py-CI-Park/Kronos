"""Fast, read-only catalog of heterogeneous Kronos research run directories."""
from __future__ import annotations

import re
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, TypedDict

from webui.v6_research_metadata import observe_metadata

RUN_SEGMENT_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,120}$")
MAX_CATALOG_RUNS: Final = 240
MAX_CATALOG_ARTIFACTS: Final = 100


class ResearchRunPayload(TypedDict):
    run_id: str
    name: str
    lane: str
    status: str
    algorithm: str
    dataset_id: str
    updated_at: str
    source_file: str
    artifact_count: int
    detail_url: str


@dataclass(frozen=True, slots=True)
class ResearchRun:
    """One recorded run directory and only its directly observed metadata."""

    run_id: str
    name: str
    lane: str
    status: str
    algorithm: str
    dataset_id: str
    updated_at: str
    updated_ns: int
    source_file: str
    artifact_count: int
    directory: Path

    def to_payload(self) -> ResearchRunPayload:
        return {
            "run_id": self.run_id,
            "name": self.name,
            "lane": self.lane,
            "status": self.status,
            "algorithm": self.algorithm,
            "dataset_id": self.dataset_id,
            "updated_at": self.updated_at,
            "source_file": self.source_file,
            "artifact_count": self.artifact_count,
            "detail_url": f"/api/v6/research-runs/{self.run_id}",
        }


@dataclass(frozen=True, slots=True)
class ResearchQuery:
    search: str = ""
    lane: str = ""
    status: str = ""
    page: int = 1
    page_size: int = 40


@dataclass(frozen=True, slots=True)
class ResearchPage:
    items: tuple[ResearchRun, ...]
    total: int
    page: int
    page_size: int


def research_lane(run_id: str) -> str:
    lowered = run_id.lower()
    if lowered.startswith(("daily_", "v6_daily", "v8_daily")):
        return "daily_close"
    if "orderbook" in lowered:
        return "orderbook"
    if lowered.startswith(("opening_", "gap_up", "stom_1s")):
        return "intraday"
    if lowered.startswith("portfolio"):
        return "portfolio"
    if "discovery" in lowered:
        return "discovery"
    return "other"


def _safe_regular_file(path: Path) -> bool:
    try:
        result = path.lstat()
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = int(getattr(result, "st_file_attributes", 0))
    return stat.S_ISREG(result.st_mode) and not attributes & reparse_flag


def _safe_directory(path: Path) -> bool:
    try:
        result = path.lstat()
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = int(getattr(result, "st_file_attributes", 0))
    return stat.S_ISDIR(result.st_mode) and not attributes & reparse_flag


def _children(directory: Path) -> tuple[Path, ...]:
    try:
        return tuple(directory.iterdir())
    except OSError:
        return ()


def discover_artifact_files(directory: Path, *, maximum: int = MAX_CATALOG_ARTIFACTS) -> tuple[Path, ...]:
    """List direct evidence plus bounded model checkpoints without following links."""
    files = [path for path in _children(directory) if _safe_regular_file(path)]
    model_root = directory / "models"
    if _safe_directory(model_root):
        for child in _children(model_root):
            if _safe_regular_file(child):
                files.append(child)
            elif _safe_directory(child):
                files.extend(path for path in _children(child) if _safe_regular_file(path))
    ordered = sorted(files, key=lambda path: path.relative_to(directory).as_posix())
    return tuple(ordered[: max(0, maximum)])


def _artifact_count(directory: Path) -> int:
    return len(discover_artifact_files(directory))


def _direct_children(directory: Path) -> tuple[Path, ...]:
    return tuple(path for path in _children(directory) if _safe_directory(path))


def _has_direct_file(directory: Path) -> bool:
    return any(_safe_regular_file(path) for path in _children(directory))


def _is_within_root(root: Path, directory: Path) -> bool:
    try:
        _ = directory.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return False
    return True


def discover_run_directories(root: Path) -> tuple[tuple[str, Path], ...]:
    """Expand one grouping level so the catalog represents actual runs, not containers."""
    top_level = tuple(path for path in _children(root) if _safe_directory(path))
    rows: list[tuple[str, Path]] = []
    for directory in top_level:
        children = _direct_children(directory)
        if _has_direct_file(directory) or not children:
            rows.append((directory.name, directory))
        rows.extend(
            (f"{directory.name}/{child.name}", child)
            for child in children
            if _has_direct_file(child) or not _direct_children(child)
        )
    return tuple(rows)


def discover_runs(root: Path) -> tuple[ResearchRun, ...]:
    """Discover bounded run metadata without opening models, logs, or report chains."""
    rows: list[ResearchRun] = []
    for run_id, directory in discover_run_directories(root):
        if len(rows) >= MAX_CATALOG_RUNS:
            break
        if not _is_within_root(root, directory):
            continue
        try:
            stat_result = directory.lstat()
        except OSError:
            continue
        metadata = observe_metadata(directory)
        updated = datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        rows.append(
            ResearchRun(
                run_id=run_id,
                name=directory.name,
                lane=research_lane(run_id),
                status=metadata.status,
                algorithm=metadata.algorithm,
                dataset_id=metadata.dataset_id,
                updated_at=updated,
                updated_ns=stat_result.st_mtime_ns,
                source_file=metadata.source_file,
                artifact_count=_artifact_count(directory),
                directory=directory,
            )
        )
    return tuple(sorted(rows, key=lambda row: (-row.updated_ns, row.run_id)))


def filter_runs(rows: tuple[ResearchRun, ...], query: ResearchQuery) -> ResearchPage:
    """Filter and paginate a stable catalog snapshot."""
    search = query.search.casefold()
    status = query.status.casefold()
    filtered = tuple(
        row
        for row in rows
        if (not search or search in row.run_id.casefold() or search in row.algorithm.casefold())
        and (not query.lane or row.lane == query.lane)
        and (not status or status in row.status.casefold())
    )
    start = (query.page - 1) * query.page_size
    return ResearchPage(filtered[start : start + query.page_size], len(filtered), query.page, query.page_size)


def resolve_run_directory(root: Path, run_id: str) -> Path | None:
    """Resolve one or two safe path segments below the research root."""
    segments = run_id.split("/")
    if not 1 <= len(segments) <= 2 or any(RUN_SEGMENT_RE.fullmatch(segment) is None for segment in segments):
        return None
    candidate = root.joinpath(*segments)
    try:
        resolved = candidate.resolve(strict=True)
        _ = resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return None
    if not resolved.is_dir() or resolved.is_symlink():
        return None
    return resolved
