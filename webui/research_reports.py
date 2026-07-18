"""Read-only V5.1 research report catalog service.

The catalog intentionally has no Flask dependency. API routes can inject a
``ResearchReportCatalog`` instance and expose its pure ``list_reports`` and
``read_report`` methods without granting filesystem write or traversal access.
"""
from __future__ import annotations

import errno
import hashlib
import html
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Final, Iterable, Mapping

SCHEMA_VERSION: Final = "kronos_v51_research_report_catalog.v1"
MAX_REPORT_BYTES: Final = 1 * 1024 * 1024
REPO_ROOT: Final = Path(__file__).resolve().parents[1]

ALLOWED_REPORT_MEDIA_TYPES: Final = {
    ".md": "text/markdown; charset=utf-8",
    ".html": "text/html; charset=utf-8",
}
_FALSE_LOCKS: Final = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}
FALSE_LOCKS: Final = dict(_FALSE_LOCKS)
NO_CLAIMS: Final = {
    "live_broker_order_claim": False,
    "paper_forward_claim": False,
    "paper_trading_claim": False,
    "profitability_claim": False,
    "official_close_claim": False,
    "production_readiness_claim": False,
}
SOURCE_PROTOCOL: Final = {
    "schema_version": SCHEMA_VERSION,
    "read_only": True,
    "writes_allowed": False,
    "root_policy": "explicit_allowlist_existing_directories_only",
    "allowed_extensions": tuple(ALLOWED_REPORT_MEDIA_TYPES),
    "encoding": "utf-8",
    "html_policy": "escaped_pre_article_no_executable_markup",
    "causal_cutoff_kst": "15:20:00",
    "price_basis": "15:20_bar_close_proxy",
    "official_close": False,
    "symbol_policy": "preserve_six_digit_strings",
    "cost_identifier_policy": "preserve_internal_bp_identifiers",
    "claim_policy": dict(NO_CLAIMS),
}

DEFAULT_APPROVED_REPORT_ROOT_CANDIDATES: Final = (
    REPO_ROOT / "docs" / "wiki",
    REPO_ROOT / "docs" / "research_reports",
    REPO_ROOT / "docs" / "research-reports",
    REPO_ROOT / "research_reports",
    REPO_ROOT / "research-reports",
)

_ID_SEGMENT_RE: Final = re.compile(r"[^a-z0-9._-]+")
_MARKDOWN_HEADING_RE: Final = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_HTML_TITLE_RE: Final = re.compile(r"<title\b[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_TAG_RE: Final = re.compile(r"<[^>]+>")
_REPORT_HTML_ESCAPE_PROTOCOL_RE: Final = re.compile(r"javascript\s*:", re.IGNORECASE)
_WINDOWS_RESERVED_BASENAMES: Final = frozenset(
    {"con", "prn", "aux", "nul", *(f"com{number}" for number in range(1, 10)), *(f"lpt{number}" for number in range(1, 10))}
)
_DENIED_INNER_EXTENSIONS: Final = frozenset(
    {
        ".bat",
        ".cmd",
        ".com",
        ".cpl",
        ".dll",
        ".exe",
        ".hta",
        ".js",
        ".jse",
        ".msi",
        ".msp",
        ".ps1",
        ".scr",
        ".sh",
        ".sys",
        ".vbe",
        ".vbs",
        ".wsf",
    }
)


class ResearchReportCatalogError(ValueError):
    """Typed catalog error that does not leak local filesystem paths."""

    status_code: int
    code: str
    message: str

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    def to_response(self) -> dict[str, object]:
        return {"status_code": self.status_code, "code": self.code, "message": self.message}


@dataclass(frozen=True)
class _ApprovedRoot:
    root_id: str
    path: Path
    resolved: Path
    key: str


@dataclass(frozen=True)
class _ReportRecord:
    report_id: str
    root_id: str
    relative_path: str
    filename: str
    media_type: str
    byte_length: int
    content_sha256: str
    updated_at: str
    updated_metadata: Mapping[str, object]
    title: str
    path: Path

    def to_metadata(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "report_id": self.report_id,
            "root_id": self.root_id,
            "relative_path": self.relative_path,
            "filename": self.filename,
            "title": self.title,
            "media_type": self.media_type,
            "mime": self.media_type,
            "mime_type": self.media_type,
            "byte_length": self.byte_length,
            "content_sha256": self.content_sha256,
            "sha256": self.content_sha256,
            "updated_at": self.updated_at,
            "updated_metadata": dict(self.updated_metadata),
            "updated": dict(self.updated_metadata),
            "source_protocol": _source_protocol(),
            "false_locks": _false_locks(),
            "locks": _false_locks(),
            "no_claims": dict(NO_CLAIMS),
        }


def _raise(status_code: int, code: str, message: str) -> None:
    raise ResearchReportCatalogError(status_code, code, message)


def _false_locks() -> dict[str, bool]:
    return dict(_FALSE_LOCKS)


def _source_protocol() -> dict[str, object]:
    protocol = dict(SOURCE_PROTOCOL)
    protocol["allowed_extensions"] = list(ALLOWED_REPORT_MEDIA_TYPES)
    protocol["claim_policy"] = dict(NO_CLAIMS)
    return protocol


def _default_approved_report_roots() -> tuple[Path, ...]:
    return tuple(path for path in DEFAULT_APPROVED_REPORT_ROOT_CANDIDATES if path.is_dir())


DEFAULT_APPROVED_REPORT_ROOTS: Final = _default_approved_report_roots()


def _is_reparse_stat(st_result: os.stat_result) -> bool:
    attrs = getattr(st_result, "st_file_attributes", 0) or 0
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(int(attrs) & flag)


def _reject_link_or_reparse(st_result: os.stat_result) -> None:
    if stat.S_ISLNK(st_result.st_mode) or _is_reparse_stat(st_result):
        _raise(422, "UNSAFE_LINK", "report path uses a symlink or reparse point")


def _stat_ns(st_result: os.stat_result, ns_attr: str, seconds_attr: str) -> int:
    value = getattr(st_result, ns_attr, None)
    if value is not None:
        return int(value)
    seconds = getattr(st_result, seconds_attr, None)
    if seconds is None:
        return 0
    return int(seconds * 1_000_000_000)


def _identity(st_result: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        int(st_result.st_dev),
        int(st_result.st_ino),
        int(st_result.st_mode),
        int(st_result.st_size),
        _stat_ns(st_result, "st_mtime_ns", "st_mtime"),
        int(getattr(st_result, "st_nlink", 1)),
    )


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return _identity(left) == _identity(right)


def _canonical_path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=True))).casefold()


def _safe_id_segment(value: str) -> str:
    folded = value.casefold().strip(" .")
    folded = _ID_SEGMENT_RE.sub("-", folded).strip("-._")
    return folded or "root"


def _root_id_for(path: Path) -> str:
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(REPO_ROOT.resolve(strict=True))
    except ValueError:
        digest = hashlib.sha256(str(resolved).encode("utf-8", "surrogateescape")).hexdigest()[:8]
        return f"{_safe_id_segment(resolved.name)}-{digest}"
    segments = tuple(_safe_id_segment(part) for part in relative.parts if part not in {"", os.curdir})
    return "/".join(segments) or f"reports-{hashlib.sha256(str(resolved).encode('utf-8')).hexdigest()[:8]}"


def _is_windows_reserved(segment: str) -> bool:
    folded = segment.casefold().strip(" .")
    stem = folded.rsplit(".", 1)[0]
    return stem in _WINDOWS_RESERVED_BASENAMES


def _safe_path_segment(segment: str) -> bool:
    return (
        bool(segment)
        and segment not in {".", ".."}
        and "\x00" not in segment
        and ":" not in segment
        and "/" not in segment
        and "\\" not in segment
        and segment == segment.rstrip(" .")
        and not _is_windows_reserved(segment)
    )


def _safe_relative_parts(parts: Iterable[str]) -> tuple[str, ...] | None:
    safe = tuple(parts)
    if not safe or len(safe) > 32 or any(not _safe_path_segment(part) for part in safe):
        return None
    return safe


def _safe_relative_path(path: Path) -> tuple[str, ...] | None:
    posix = PurePosixPath(path.as_posix())
    windows = PureWindowsPath(path.as_posix())
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        return None
    return _safe_relative_parts(posix.parts)


def _allowed_report_filename(filename: str) -> bool:
    if not _safe_path_segment(filename):
        return False
    suffixes = tuple(suffix.casefold() for suffix in PurePosixPath(filename).suffixes)
    if not suffixes or suffixes[-1] not in ALLOWED_REPORT_MEDIA_TYPES:
        return False
    return not any(suffix in _DENIED_INNER_EXTENSIONS for suffix in suffixes[:-1])


def _media_type_for(path: Path) -> str:
    suffix = path.suffix.casefold()
    media_type = ALLOWED_REPORT_MEDIA_TYPES.get(suffix)
    if media_type is None:
        _raise(422, "DENIED_EXTENSION", "report extension is not allowlisted")
    return media_type


def _validate_report_id(report_id: object) -> str:
    if not isinstance(report_id, str) or not report_id or len(report_id) > 512 or "\x00" in report_id:
        _raise(400, "INVALID_REPORT_ID", "report_id must be a bounded safe catalog id")
    if ":" in report_id or "\\" in report_id or report_id.startswith(("/", "//")) or "//" in report_id:
        _raise(400, "INVALID_REPORT_ID", "report_id must not be absolute or platform-specific")
    posix = PurePosixPath(report_id)
    windows = PureWindowsPath(report_id)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        _raise(400, "INVALID_REPORT_ID", "report_id must be relative to the catalog")
    parts = _safe_relative_parts(posix.parts)
    if parts is None:
        _raise(400, "INVALID_REPORT_ID", "report_id contains traversal or unsafe path segments")
    return "/".join(parts)


def _report_id(root_id: str, relative_parts: Iterable[str]) -> str:
    folded_relative = "/".join(part.casefold() for part in relative_parts)
    return _validate_report_id(f"{root_id}/{folded_relative}")


def _updated_at(st_result: os.stat_result) -> str:
    timestamp = datetime.fromtimestamp(float(st_result.st_mtime), tz=timezone.utc)
    return timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")


def _updated_metadata(st_result: os.stat_result) -> dict[str, object]:
    return {
        "updated_at": _updated_at(st_result),
        "mtime_ns": _stat_ns(st_result, "st_mtime_ns", "st_mtime"),
        "size_bytes": int(st_result.st_size),
    }


def _open_nofollow(path: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    if os.name != "nt":
        flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(path, flags)
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.EMLINK}:
            _raise(422, "UNSAFE_LINK", "report path uses a symlink or reparse point")
        if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
            _raise(404, "REPORT_NOT_FOUND", "report is no longer available")
        _raise(410, "REPORT_STALE", "report could not be opened safely")


def _read_fd_bounded(fd: int, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, min(64 * 1024, max_bytes + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > max_bytes:
            _raise(413, "REPORT_TOO_LARGE", "report exceeds the catalog byte limit")
    return b"".join(chunks)


def _read_report_bytes(path: Path, *, max_bytes: int) -> tuple[bytes, os.stat_result]:
    try:
        st_before = os.lstat(path)
    except OSError as exc:
        if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
            _raise(404, "REPORT_NOT_FOUND", "report is no longer available")
        _raise(410, "REPORT_STALE", "report could not be inspected safely")
    _reject_link_or_reparse(st_before)
    if not stat.S_ISREG(st_before.st_mode):
        _raise(422, "SPECIAL_FILE", "report path is not a regular file")
    if int(st_before.st_size) > max_bytes:
        _raise(413, "REPORT_TOO_LARGE", "report exceeds the catalog byte limit")

    fd = _open_nofollow(path)
    try:
        st_open = os.fstat(fd)
        if not stat.S_ISREG(st_open.st_mode):
            _raise(422, "SPECIAL_FILE", "report path is not a regular file")
        if not _same_file_identity(st_before, st_open):
            _raise(410, "TOCTOU_DETECTED", "report changed while it was being opened")
        raw = _read_fd_bounded(fd, max_bytes)
        st_after_fd = os.fstat(fd)
    finally:
        os.close(fd)

    try:
        st_after_path = os.lstat(path)
    except OSError:
        _raise(410, "TOCTOU_DETECTED", "report changed while it was being read")
    _reject_link_or_reparse(st_after_path)
    if not (_same_file_identity(st_before, st_after_fd) and _same_file_identity(st_before, st_after_path)):
        _raise(410, "TOCTOU_DETECTED", "report changed while it was being read")
    return raw, st_after_path


def _decode_text(raw: bytes) -> str:
    if b"\x00" in raw:
        _raise(422, "BINARY_CONTENT", "report contains NUL bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ResearchReportCatalogError(422, "INVALID_ENCODING", "report is not strict UTF-8 text") from exc
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        _raise(422, "BINARY_CONTENT", "report contains binary control characters")
    return text


def escaped_pre_report_html(text: str) -> str:
    escaped = html.escape(text, quote=True)
    escaped = _REPORT_HTML_ESCAPE_PROTOCOL_RE.sub(lambda match: match.group(0).replace(":", "&#58;"), escaped)
    return f'<article data-kronos-report-html="escaped-pre"><pre>{escaped}</pre></article>'


def _title_from_text(text: str, path: Path) -> str:
    if path.suffix.casefold() == ".html":
        match = _HTML_TITLE_RE.search(text)
        if match:
            title = _TAG_RE.sub("", match.group(1))
            title = html.unescape(" ".join(title.split()))
            if title:
                return title[:200]
    for line in text.splitlines():
        match = _MARKDOWN_HEADING_RE.match(line)
        if match:
            title = match.group(1).strip()
            if title:
                return title[:200]
    return path.stem.replace("_", " ").replace("-", " ")[:200]


def _read_text_report(path: Path, *, max_bytes: int) -> tuple[bytes, str, os.stat_result]:
    raw, st_result = _read_report_bytes(path, max_bytes=max_bytes)
    return raw, _decode_text(raw), st_result


class ResearchReportCatalog:
    """Allowlisted, read-only catalog for Markdown/HTML research reports."""

    def __init__(self, approved_roots: Iterable[str | Path] | None = None, *, max_bytes: int = MAX_REPORT_BYTES) -> None:
        if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
            _raise(400, "INVALID_LIMIT", "max_bytes must be a positive integer")
        self._max_bytes = max_bytes
        root_values = _default_approved_report_roots() if approved_roots is None else tuple(approved_roots)
        self._roots = self._normalize_roots(root_values)

    @property
    def approved_roots(self) -> tuple[str, ...]:
        """Resolved approved root paths, exposed for diagnostics only."""

        return tuple(str(root.resolved) for root in self._roots)

    def list_reports(self) -> list[dict[str, object]]:
        """Return stable metadata for all currently readable reports."""

        return [record.to_metadata() for record in self._index().values()]

    def read_report(self, report_id: str) -> dict[str, object]:
        """Return raw UTF-8 text plus non-executable escaped HTML for a report."""

        safe_id = _validate_report_id(report_id)
        record = self._index().get(safe_id)
        if record is None:
            _raise(404, "REPORT_NOT_FOUND", "report_id is not in the allowlisted catalog")
        raw, text, st_result = _read_text_report(record.path, max_bytes=self._max_bytes)
        metadata = _ReportRecord(
            report_id=record.report_id,
            root_id=record.root_id,
            relative_path=record.relative_path,
            filename=record.filename,
            media_type=record.media_type,
            byte_length=len(raw),
            content_sha256=hashlib.sha256(raw).hexdigest(),
            updated_at=_updated_at(st_result),
            updated_metadata=_updated_metadata(st_result),
            title=_title_from_text(text, record.path),
            path=record.path,
        ).to_metadata()
        safe_html = escaped_pre_report_html(text)
        metadata.update(
            {
                "content": text,
                "raw_text": text,
                "text": text,
                "html": safe_html,
                "safe_html": safe_html,
            }
        )
        return metadata

    def _normalize_roots(self, raw_roots: Iterable[str | Path]) -> tuple[_ApprovedRoot, ...]:
        roots: list[_ApprovedRoot] = []
        seen: set[str] = set()
        for raw_root in raw_roots:
            if isinstance(raw_root, str) and "\x00" in raw_root:
                _raise(400, "UNSAFE_ROOT", "approved root contains NUL")
            root = Path(raw_root)
            try:
                st_root = os.lstat(root)
            except OSError as exc:
                if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
                    continue
                _raise(503, "ROOT_UNAVAILABLE", "approved root could not be inspected")
            _reject_link_or_reparse(st_root)
            if not stat.S_ISDIR(st_root.st_mode):
                continue
            try:
                resolved = root.resolve(strict=True)
                key = _canonical_path_key(root)
            except OSError:
                _raise(503, "ROOT_UNAVAILABLE", "approved root could not be resolved")
            if key in seen:
                continue
            seen.add(key)
            roots.append(_ApprovedRoot(root_id=_root_id_for(resolved), path=root, resolved=resolved, key=key))
        return tuple(roots)

    def _iter_report_paths(self, root: _ApprovedRoot) -> Iterable[Path]:
        for dirpath, dirnames, filenames in os.walk(root.path, topdown=True, followlinks=False):
            current = Path(dirpath)
            try:
                st_current = os.lstat(current)
                _reject_link_or_reparse(st_current)
            except ResearchReportCatalogError:
                dirnames[:] = []
                continue
            if not stat.S_ISDIR(st_current.st_mode):
                dirnames[:] = []
                continue

            safe_dirnames: list[str] = []
            for dirname in sorted(dirnames, key=lambda value: value.casefold()):
                if not _safe_path_segment(dirname):
                    continue
                candidate = current / dirname
                try:
                    st_candidate = os.lstat(candidate)
                    _reject_link_or_reparse(st_candidate)
                except (OSError, ResearchReportCatalogError):
                    continue
                if stat.S_ISDIR(st_candidate.st_mode):
                    safe_dirnames.append(dirname)
            dirnames[:] = safe_dirnames

            for filename in sorted(filenames, key=lambda value: value.casefold()):
                if not _allowed_report_filename(filename):
                    continue
                yield current / filename

    def _record_for(self, root: _ApprovedRoot, path: Path) -> _ReportRecord | None:
        try:
            relative = path.relative_to(root.path)
        except ValueError:
            return None
        relative_parts = _safe_relative_path(relative)
        if relative_parts is None or not _allowed_report_filename(relative_parts[-1]):
            return None
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root.resolved)
        except (OSError, ValueError):
            return None
        try:
            raw, text, st_result = _read_text_report(path, max_bytes=self._max_bytes)
        except ResearchReportCatalogError as exc:
            if exc.code in {"BINARY_CONTENT", "DENIED_EXTENSION", "INVALID_ENCODING", "REPORT_TOO_LARGE", "SPECIAL_FILE", "UNSAFE_LINK"}:
                return None
            raise
        return _ReportRecord(
            report_id=_report_id(root.root_id, relative_parts),
            root_id=root.root_id,
            relative_path="/".join(relative_parts),
            filename=relative_parts[-1],
            media_type=_media_type_for(path),
            byte_length=len(raw),
            content_sha256=hashlib.sha256(raw).hexdigest(),
            updated_at=_updated_at(st_result),
            updated_metadata=_updated_metadata(st_result),
            title=_title_from_text(text, path),
            path=path,
        )

    def _index(self) -> dict[str, _ReportRecord]:
        records: dict[str, _ReportRecord] = {}
        for root in self._roots:
            for path in self._iter_report_paths(root):
                record = self._record_for(root, path)
                if record is None:
                    continue
                if record.report_id in records:
                    _raise(503, "DUPLICATE_REPORT_ID", "approved report roots produce duplicate report ids")
                records[record.report_id] = record
        return dict(sorted(records.items(), key=lambda item: item[0]))


__all__ = [
    "ALLOWED_REPORT_MEDIA_TYPES",
    "DEFAULT_APPROVED_REPORT_ROOTS",
    "DEFAULT_APPROVED_REPORT_ROOT_CANDIDATES",
    "FALSE_LOCKS",
    "MAX_REPORT_BYTES",
    "escaped_pre_report_html",
    "NO_CLAIMS",
    "ResearchReportCatalog",
    "ResearchReportCatalogError",
    "SCHEMA_VERSION",
    "SOURCE_PROTOCOL",
]
