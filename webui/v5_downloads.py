"""Secure binary exception downloads for the Kronos V5 dashboard API.

The V5 API is JSON-first.  This module is the only binary exception boundary and
therefore accepts only small, pinned, artifact-registry entries with portable
filenames and deterministic response metadata.  It never follows artifact links
and it fails closed on every metadata, path, file-type, and byte-integrity
mismatch.
"""
from __future__ import annotations

import email.utils
import errno
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final
from urllib.parse import quote


MAX_DOWNLOAD_BYTES: Final = 25 * 1024 * 1024
ALLOWED_DOWNLOAD_MEDIA_TYPES: Final = {
    ".json": "application/json",
    ".csv": "text/csv",
    ".jsonl": "application/jsonl",
    ".md": "text/markdown",
    ".png": "image/png",
}
SNAPSHOT_FILENAMES: Final = (
    "kronos_rl_run_state.v2.json",
    "run_state.json",
    "registry_snapshot.json",
    "registry.json",
    "snapshot.json",
)

DOWNLOAD_ERROR_STATUS: Final = {
    "INVALID_ARTIFACT_ID": 400,
    "UNSAFE_PATH": 400,
    "DENIED_NAME": 400,
    "DENIED_EXTENSION": 400,
    "ARTIFACT_NOT_FOUND": 404,
    "ARTIFACT_STALE": 410,
    "UNSAFE_LINK": 410,
    "SPECIAL_FILE": 410,
    "TOCTOU_DETECTED": 410,
    "ARTIFACT_TOO_LARGE": 413,
    "INVALID_METADATA": 422,
    "INTEGRITY_MISMATCH": 422,
    "MIME_MISMATCH": 422,
    "REGISTRY_UNAVAILABLE": 503,
}

_ERROR_MESSAGES: Final = {
    "INVALID_ARTIFACT_ID": "artifact id is not portable",
    "UNSAFE_PATH": "artifact path is outside the download boundary",
    "DENIED_NAME": "artifact name is not downloadable",
    "DENIED_EXTENSION": "artifact extension is not downloadable",
    "ARTIFACT_NOT_FOUND": "artifact was not found",
    "ARTIFACT_STALE": "artifact bytes are not available",
    "UNSAFE_LINK": "artifact link topology is not downloadable",
    "SPECIAL_FILE": "artifact is not a regular file",
    "TOCTOU_DETECTED": "artifact changed while being opened",
    "ARTIFACT_TOO_LARGE": "artifact exceeds the download byte limit",
    "INVALID_METADATA": "artifact metadata is invalid",
    "INTEGRITY_MISMATCH": "artifact metadata does not match bytes",
    "MIME_MISMATCH": "artifact bytes do not match declared media type",
    "REGISTRY_UNAVAILABLE": "artifact registry is unavailable",
}

_ARTIFACT_ID_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_SHA256_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_FILENAME_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,180}\.(?:json|csv|jsonl|md|png)\Z")
_SAFE_SEGMENT_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,180}\Z")
_TOKEN_SPLIT_RE: Final = re.compile(r"[^a-z0-9]+")
_WINDOWS_RESERVED_BASENAMES: Final = frozenset(
    {"con", "prn", "aux", "nul", *(f"com{number}" for number in range(1, 10)), *(f"lpt{number}" for number in range(1, 10))}
)
_DENIED_NAME_TOKENS: Final = frozenset({"db", "database", "model", "archive", "checkpoint", "ckpt", "key", "config", "oos", "ciphertext"})
_DENIED_EXTENSIONS: Final = frozenset(
    {
        ".7z",
        ".bin",
        ".cfg",
        ".ckpt",
        ".conf",
        ".db",
        ".env",
        ".gz",
        ".h5",
        ".ini",
        ".joblib",
        ".key",
        ".onnx",
        ".parquet",
        ".pem",
        ".pkl",
        ".pt",
        ".pth",
        ".rar",
        ".sqlite",
        ".sqlite3",
        ".tar",
        ".tgz",
        ".toml",
        ".yaml",
        ".yml",
        ".zip",
    }
)
_PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"


class DownloadError(ValueError):
    """Typed backend error for V5 artifact download routes."""

    status_code: int
    code: str
    message: str

    def __init__(self, status_code: int, code: str, message: str) -> None:
        if status_code not in {400, 404, 410, 413, 422, 503}:
            raise ValueError("download errors must use the frozen status set")
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    def to_response(self) -> dict[str, object]:
        """Return the route-layer JSON error shape without leaking filesystem paths."""

        return {"status_code": self.status_code, "code": self.code, "message": self.message}


@dataclass(frozen=True)
class DownloadResult:
    """Pinned response payload and metadata for a successful binary download."""

    body: bytes
    filename: str
    media_type: str
    sha256: str
    byte_length: int
    etag: str | None = None
    last_modified: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    artifact_id: str | None = None

    @property
    def metadata(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "filename": self.filename,
            "media_type": self.media_type,
            "byte_length": self.byte_length,
            "sha256": self.sha256,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "headers": dict(self.headers),
        }


@dataclass(frozen=True)
class _ArtifactMetadata:
    artifact_id: str
    path: str
    filename: str
    extension: str
    media_type: str
    byte_length: int
    sha256: str


def _raise(code: str) -> None:
    raise DownloadError(DOWNLOAD_ERROR_STATUS[code], code, _ERROR_MESSAGES[code])


def _is_reparse_stat(st_result: os.stat_result) -> bool:
    attrs = getattr(st_result, "st_file_attributes", 0) or 0
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(int(attrs) & flag)

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


def _reject_link_or_reparse(path: Path, st_result: os.stat_result) -> None:
    if stat.S_ISLNK(st_result.st_mode) or _is_reparse_stat(st_result):
        _raise("UNSAFE_LINK")


def _reject_denied_name(segment: str) -> None:
    folded = segment.casefold().strip(" .")
    stem = folded.rsplit(".", 1)[0]
    if stem in _WINDOWS_RESERVED_BASENAMES:
        _raise("DENIED_NAME")
    tokens = {token for token in _TOKEN_SPLIT_RE.split(stem.replace("_", "-")) if token}
    if "oos" in folded or tokens & _DENIED_NAME_TOKENS:
        _raise("DENIED_NAME")


def _validate_artifact_id(artifact_id: str) -> None:
    if not isinstance(artifact_id, str) or not _ARTIFACT_ID_RE.fullmatch(artifact_id):
        _raise("INVALID_ARTIFACT_ID")


def _validate_filename(filename: object) -> tuple[str, str]:
    if not isinstance(filename, str) or ":" in filename or "/" in filename or "\\" in filename:
        _raise("UNSAFE_PATH")
    if not _FILENAME_RE.fullmatch(filename):
        extension = Path(filename).suffix.casefold() if isinstance(filename, str) else ""
        if extension in _DENIED_EXTENSIONS or extension not in ALLOWED_DOWNLOAD_MEDIA_TYPES:
            _raise("DENIED_EXTENSION")
        _raise("DENIED_NAME")
    _reject_denied_name(filename)
    extension = Path(filename).suffix.casefold()
    if extension not in ALLOWED_DOWNLOAD_MEDIA_TYPES:
        _raise("DENIED_EXTENSION")
    return filename, extension


def _path_segments(raw_path: object) -> tuple[str, ...]:
    if not isinstance(raw_path, str) or raw_path == "" or "\x00" in raw_path or ":" in raw_path:
        _raise("UNSAFE_PATH")
    if raw_path.endswith(("/", "\\")) or re.search(r"[\\/]{2,}", raw_path):
        _raise("UNSAFE_PATH")
    if PurePosixPath(raw_path).is_absolute() or PureWindowsPath(raw_path).is_absolute() or PureWindowsPath(raw_path).drive:
        _raise("UNSAFE_PATH")
    parts = tuple(re.split(r"[\\/]+", raw_path))
    if not parts or len(parts) > 32:
        _raise("UNSAFE_PATH")
    for index, part in enumerate(parts):
        if part in {".", ".."}:
            _raise("UNSAFE_PATH")
        if "." in part:
            if index != len(parts) - 1 or not _FILENAME_RE.fullmatch(part):
                extension = Path(part).suffix.casefold()
                if extension in _DENIED_EXTENSIONS or extension not in ALLOWED_DOWNLOAD_MEDIA_TYPES:
                    _raise("DENIED_EXTENSION")
                _raise("UNSAFE_PATH")
        elif not _SAFE_SEGMENT_RE.fullmatch(part):
            _raise("UNSAFE_PATH")
        _reject_denied_name(part)
    return parts


def _normalize_metadata(artifact_id: str, record: Mapping[str, Any]) -> _ArtifactMetadata:
    filename, extension = _validate_filename(record.get("filename"))
    parts = _path_segments(record.get("path"))
    if parts[-1] != filename:
        _raise("INVALID_METADATA")

    media_type = record.get("media_type")
    if media_type != ALLOWED_DOWNLOAD_MEDIA_TYPES[extension]:
        _raise("MIME_MISMATCH")

    byte_length = record.get("byte_length")
    if not isinstance(byte_length, int) or isinstance(byte_length, bool) or byte_length < 0:
        _raise("INVALID_METADATA")
    if byte_length > MAX_DOWNLOAD_BYTES:
        _raise("ARTIFACT_TOO_LARGE")

    sha256 = record.get("sha256")
    if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
        _raise("INVALID_METADATA")

    return _ArtifactMetadata(
        artifact_id=artifact_id,
        path="/".join(parts),
        filename=filename,
        extension=extension,
        media_type=media_type,
        byte_length=byte_length,
        sha256=sha256,
    )


def _load_json_file(path: Path) -> Mapping[str, Any]:
    try:
        st_before = os.lstat(path)
        _reject_link_or_reparse(path, st_before)
        if not stat.S_ISREG(st_before.st_mode):
            _raise("REGISTRY_UNAVAILABLE")
        raw = path.read_bytes()
        st_after = os.lstat(path)
    except DownloadError:
        raise
    except OSError as exc:
        if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
            _raise("REGISTRY_UNAVAILABLE")
        _raise("REGISTRY_UNAVAILABLE")
    if not _same_file_identity(st_before, st_after):
        _raise("REGISTRY_UNAVAILABLE")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _raise("REGISTRY_UNAVAILABLE")
    if not isinstance(value, Mapping):
        _raise("REGISTRY_UNAVAILABLE")
    return value


def _snapshot_path(registry_root: Path) -> Path:
    try:
        st_root = os.lstat(registry_root)
        _reject_link_or_reparse(registry_root, st_root)
    except DownloadError:
        raise
    except OSError:
        _raise("REGISTRY_UNAVAILABLE")
    if stat.S_ISREG(st_root.st_mode):
        return registry_root
    if not stat.S_ISDIR(st_root.st_mode):
        _raise("REGISTRY_UNAVAILABLE")
    for name in SNAPSHOT_FILENAMES:
        candidate = registry_root / name
        try:
            st_candidate = os.lstat(candidate)
        except FileNotFoundError:
            continue
        except OSError:
            _raise("REGISTRY_UNAVAILABLE")
        _reject_link_or_reparse(candidate, st_candidate)
        if stat.S_ISREG(st_candidate.st_mode):
            return candidate
    _raise("REGISTRY_UNAVAILABLE")


def _load_snapshot(registry_root: Path | str | Mapping[str, Any]) -> tuple[Mapping[str, Any], Path]:
    if isinstance(registry_root, Mapping):
        snapshot = registry_root
        snapshot_path = Path.cwd()
    else:
        root = Path(registry_root)
        snapshot_path = _snapshot_path(root)
        snapshot = _load_json_file(snapshot_path)
    if snapshot.get("schema") != "kronos_rl_run_state.v2" and snapshot.get("schema_version") != "kronos_rl_run_state.v2":
        _raise("REGISTRY_UNAVAILABLE")
    return snapshot, snapshot_path


def _artifact_boundary(snapshot: Mapping[str, Any], snapshot_path: Path, fixture_root: Path | str | None) -> Path:
    if fixture_root is not None:
        root = Path(fixture_root)
    else:
        value = snapshot.get("artifact_root") or snapshot.get("fixture_root")
        root = Path(value) if isinstance(value, str) and value else snapshot_path.parent
    try:
        st_root = os.lstat(root)
        _reject_link_or_reparse(root, st_root)
        if not stat.S_ISDIR(st_root.st_mode):
            _raise("REGISTRY_UNAVAILABLE")
    except DownloadError:
        raise
    except OSError:
        _raise("REGISTRY_UNAVAILABLE")
    return root


def _find_artifact(snapshot: Mapping[str, Any], artifact_id: str) -> Mapping[str, Any]:
    artifacts = snapshot.get("artifacts")
    if not isinstance(artifacts, list):
        _raise("REGISTRY_UNAVAILABLE")
    match: Mapping[str, Any] | None = None
    for item in artifacts:
        if not isinstance(item, Mapping):
            _raise("REGISTRY_UNAVAILABLE")
        if item.get("artifact_id") == artifact_id:
            if match is not None:
                _raise("REGISTRY_UNAVAILABLE")
            match = item
    if match is None:
        _raise("ARTIFACT_NOT_FOUND")
    return match


def _safe_candidate(root: Path, metadata: _ArtifactMetadata) -> tuple[Path, os.stat_result]:
    parts = _path_segments(metadata.path)
    current = root
    try:
        root_real = root.resolve(strict=True)
    except OSError:
        _raise("REGISTRY_UNAVAILABLE")
    st_final: os.stat_result | None = None
    for index, part in enumerate(parts):
        current = current / part
        try:
            st_current = os.lstat(current)
        except OSError as exc:
            if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
                _raise("ARTIFACT_STALE")
            _raise("ARTIFACT_STALE")
        _reject_link_or_reparse(current, st_current)
        if index < len(parts) - 1:
            if not stat.S_ISDIR(st_current.st_mode):
                _raise("ARTIFACT_STALE")
        else:
            st_final = st_current
    if st_final is None:
        _raise("UNSAFE_PATH")
    if not stat.S_ISREG(st_final.st_mode):
        _raise("SPECIAL_FILE")
    if int(getattr(st_final, "st_nlink", 1)) != 1:
        _raise("UNSAFE_LINK")
    try:
        candidate_real = current.resolve(strict=True)
        candidate_real.relative_to(root_real)
    except (OSError, ValueError):
        _raise("UNSAFE_PATH")
    return current, st_final


def _open_nofollow(path: Path) -> int:
    if os.name == "nt":
        return _open_nofollow_windows(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(path, flags)
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.EMLINK}:
            _raise("UNSAFE_LINK")
        if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
            _raise("ARTIFACT_STALE")
        _raise("ARTIFACT_STALE")


def _open_nofollow_windows(path: Path) -> int:
    if sys.platform != "win32":
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        try:
            return os.open(path, flags)
        except OSError:
            _raise("ARTIFACT_STALE")

    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    generic_read = 0x80000000
    file_share_read = 0x00000001
    open_existing = 3
    file_flag_open_reparse_point = 0x00200000
    file_flag_sequential_scan = 0x08000000
    file_attribute_normal = 0x00000080
    invalid_handle_value = wintypes.HANDLE(-1).value
    handle = create_file(
        str(path),
        generic_read,
        file_share_read,
        None,
        open_existing,
        file_attribute_normal | file_flag_open_reparse_point | file_flag_sequential_scan,
        None,
    )
    if handle == invalid_handle_value:
        last_error = ctypes.get_last_error()
        if last_error == 2:
            _raise("ARTIFACT_STALE")
        if last_error == 4390:
            _raise("UNSAFE_LINK")
        _raise("ARTIFACT_STALE")
    try:
        return msvcrt.open_osfhandle(handle, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except OSError:
        close_handle(handle)
        _raise("ARTIFACT_STALE")


def _read_fd_bounded(fd: int, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, min(1024 * 1024, max_bytes + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > max_bytes:
            _raise("ARTIFACT_TOO_LARGE")
    return b"".join(chunks)


def _read_regular_file(path: Path, st_before: os.stat_result) -> tuple[bytes, os.stat_result]:
    if int(st_before.st_size) > MAX_DOWNLOAD_BYTES:
        _raise("ARTIFACT_TOO_LARGE")
    fd = _open_nofollow(path)
    try:
        st_open = os.fstat(fd)
        if not stat.S_ISREG(st_open.st_mode):
            _raise("SPECIAL_FILE")
        if int(getattr(st_open, "st_nlink", 1)) != 1:
            _raise("UNSAFE_LINK")
        if not _same_file_identity(st_before, st_open):
            _raise("TOCTOU_DETECTED")
        body = _read_fd_bounded(fd, MAX_DOWNLOAD_BYTES)
        st_after_fd = os.fstat(fd)
    finally:
        os.close(fd)
    try:
        st_after_path = os.lstat(path)
    except OSError:
        _raise("TOCTOU_DETECTED")
    if not (_same_file_identity(st_before, st_after_fd) and _same_file_identity(st_before, st_after_path)):
        _raise("TOCTOU_DETECTED")
    return body, st_after_path


def _assert_content_media(body: bytes, metadata: _ArtifactMetadata) -> None:
    if metadata.extension == ".png":
        if not body.startswith(_PNG_SIGNATURE):
            _raise("MIME_MISMATCH")
        return
    if b"\x00" in body:
        _raise("MIME_MISMATCH")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        _raise("MIME_MISMATCH")
    if metadata.extension == ".json":
        try:
            json.loads(text)
        except json.JSONDecodeError:
            _raise("MIME_MISMATCH")
    elif metadata.extension == ".jsonl":
        try:
            for line in text.splitlines():
                if line.strip():
                    json.loads(line)
        except json.JSONDecodeError:
            _raise("MIME_MISMATCH")
    elif metadata.extension in {".csv", ".md"}:
        return
    else:  # pragma: no cover - guarded by metadata normalization.
        _raise("DENIED_EXTENSION")


def _headers(filename: str, media_type: str, byte_length: int, sha256: str, last_modified: str | None) -> dict[str, str]:
    disposition = f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename, safe='')}"
    headers = {
        "Content-Type": media_type,
        "Content-Length": str(byte_length),
        "Content-Disposition": disposition,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
        "ETag": f'"sha256-{sha256}"',
    }
    if last_modified is not None:
        headers["Last-Modified"] = last_modified
    return headers


def download_artifact(artifact_id: str, *, registry_root: Path | str | Mapping[str, Any], fixture_root: Path | str | None = None) -> DownloadResult:
    """Return pinned artifact bytes or raise ``DownloadError``.

    ``registry_root`` may be an in-memory snapshot mapping, a full
    ``kronos_rl_run_state.v2`` JSON snapshot file, or a directory containing one
    of ``SNAPSHOT_FILENAMES``.  Artifact records are read from the snapshot's
    top-level ``artifacts`` list and must include ``artifact_id``, ``path``,
    ``filename``, ``media_type``, ``byte_length`` and ``sha256``.  ``fixture_root``
    is the artifact boundary; when omitted, the snapshot's
    ``artifact_root``/``fixture_root`` value is used, then finally the snapshot
    directory.
    """

    _validate_artifact_id(artifact_id)
    snapshot, snapshot_path = _load_snapshot(registry_root)
    record = _find_artifact(snapshot, artifact_id)
    metadata = _normalize_metadata(artifact_id, record)
    root = _artifact_boundary(snapshot, snapshot_path, fixture_root)
    candidate, st_before = _safe_candidate(root, metadata)
    body, st_after = _read_regular_file(candidate, st_before)

    byte_length = len(body)
    if byte_length != metadata.byte_length or byte_length != int(st_after.st_size):
        _raise("INTEGRITY_MISMATCH")
    digest = hashlib.sha256(body).hexdigest()
    if digest != metadata.sha256:
        _raise("INTEGRITY_MISMATCH")
    _assert_content_media(body, metadata)

    last_modified = email.utils.formatdate(st_after.st_mtime, usegmt=True)
    headers = _headers(metadata.filename, metadata.media_type, byte_length, digest, last_modified)
    return DownloadResult(
        body=body,
        filename=metadata.filename,
        media_type=metadata.media_type,
        sha256=digest,
        byte_length=byte_length,
        etag=headers["ETag"],
        last_modified=last_modified,
        headers=headers,
        artifact_id=artifact_id,
    )
