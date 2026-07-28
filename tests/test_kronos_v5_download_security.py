from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from webui import v5_downloads as downloads
from webui.v5_downloads import DownloadError, download_artifact


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_snapshot(tmp_path: Path, artifact_root: Path, artifact: dict[str, object]) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps({"schema": "kronos_rl_run_state.v2", "artifact_root": str(artifact_root), "artifacts": [artifact]}),
        encoding="utf-8",
    )
    return path


def _artifact_record(
    artifact_id: str,
    relative_path: str,
    body: bytes,
    declared_media_type: str,
    **overrides: object,
) -> dict[str, object]:
    filename = Path(relative_path).name
    record: dict[str, object] = {
        "artifact_id": artifact_id,
        "path": relative_path,
        "filename": filename,
        "media_type": declared_media_type,
        "byte_length": len(body),
        "sha256": _sha(body),
    }
    record.update(overrides)
    return record


def _make_download(
    tmp_path: Path,
    relative_path: str,
    body: bytes,
    declared_media_type: str,
    **overrides: object,
) -> tuple[Path, Path]:
    root = tmp_path / "artifacts"
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    registry = _write_snapshot(tmp_path, root, _artifact_record("artifact-1", relative_path, body, declared_media_type, **overrides))
    return registry, root


def _stat_with(st_result: os.stat_result, *, mode: int | None = None, nlink: int | None = None) -> os.stat_result:
    values = list(st_result)
    if mode is not None:
        values[stat.ST_MODE] = mode
    if nlink is not None:
        values[stat.ST_NLINK] = nlink
    return os.stat_result(values)




@pytest.mark.parametrize(
    ("relative_path", "body", "media_type"),
    [
        ("reports/report.json", b'{"ok":true}', "application/json"),
        ("exports/table.csv", b"a,b\n1,2\n", "text/csv"),
        ("events/trace.jsonl", b'{"a":1}\n{"b":2}\n', "application/jsonl"),
        ("notes/readme.md", b"# evidence\n", "text/markdown"),
        ("images/screen.png", PNG_BYTES, "image/png"),
    ],
)
def test_allowed_binary_exception_extensions_return_exact_bytes_and_headers(
    tmp_path: Path, relative_path: str, body: bytes, media_type: str
) -> None:
    registry, root = _make_download(tmp_path, relative_path, body, media_type)

    result = download_artifact("artifact-1", registry_root=registry, fixture_root=root)

    assert result.body == body
    assert result.filename == Path(relative_path).name
    assert result.media_type == media_type
    assert result.sha256 == _sha(body)
    assert result.byte_length == len(body)
    assert result.headers["Content-Type"] == media_type
    assert result.headers["Content-Length"] == str(len(body))
    assert result.headers["Content-Disposition"] == (
        f"attachment; filename=\"{Path(relative_path).name}\"; filename*=UTF-8''{Path(relative_path).name}"
    )
    assert result.headers["X-Content-Type-Options"] == "nosniff"
    assert result.headers["Cache-Control"] == "no-store"
    assert result.headers["ETag"] == f'"sha256-{_sha(body)}"'
    assert result.metadata["headers"] == result.headers


def test_in_memory_registry_metadata_adapter_uses_same_hardened_path(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    target = root / "reports/report.json"
    target.parent.mkdir(parents=True)
    body = b'{"ok":true}'
    target.write_bytes(body)
    registry = {"schema": "kronos_rl_run_state.v2", "artifacts": [_artifact_record("artifact-1", "reports/report.json", body, "application/json")]}

    result = download_artifact("artifact-1", registry_root=registry, fixture_root=root)

    assert result.body == body
    assert result.headers["ETag"] == f'"sha256-{_sha(body)}"'

@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../report.json",
        "/tmp/report.json",
        "C:/tmp/report.json",
        "report.json:ads",
        "reports/../report.json",
        "reports/report.json:secret",
    ],
)
def test_rejects_traversal_absolute_windows_ads_paths_without_leaking_path(tmp_path: Path, unsafe_path: str) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    body = b'{"ok":true}'
    registry = _write_snapshot(tmp_path, root, _artifact_record("artifact-1", unsafe_path, body, "application/json"))

    with pytest.raises(DownloadError) as excinfo:
        download_artifact("artifact-1", registry_root=registry, fixture_root=root)

    assert excinfo.value.status_code == 400
    assert excinfo.value.code in {"UNSAFE_PATH", "DENIED_EXTENSION"}
    assert unsafe_path not in excinfo.value.message


@pytest.mark.parametrize(
    ("relative_path", "media_type", "expected_code"),
    [
        ("reports/model.json", "application/json", "DENIED_NAME"),
        ("reports/config.csv", "text/csv", "DENIED_NAME"),
        ("reports/fresh_oos.json", "application/json", "DENIED_NAME"),
        ("reports/report.db", "application/json", "DENIED_EXTENSION"),
        ("reports/weights.ckpt", "application/json", "DENIED_EXTENSION"),
        ("reports/archive.zip", "application/json", "DENIED_EXTENSION"),
        ("reports/readme.txt", "text/plain", "DENIED_EXTENSION"),
    ],
)
def test_rejects_denied_names_and_extensions(tmp_path: Path, relative_path: str, media_type: str, expected_code: str) -> None:
    root = tmp_path / "artifacts"
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    body = b'{"ok":true}'
    target.write_bytes(body)
    registry = _write_snapshot(tmp_path, root, _artifact_record("artifact-1", relative_path, body, media_type))

    with pytest.raises(DownloadError) as excinfo:
        download_artifact("artifact-1", registry_root=registry, fixture_root=root)

    assert excinfo.value.status_code == 400
    assert excinfo.value.code == expected_code


@pytest.mark.parametrize(
    "overrides",
    [
        {"byte_length": 99},
        {"sha256": "0" * 64},
        {"media_type": "text/csv"},
    ],
)
def test_rejects_size_hash_and_declared_mime_mismatch(tmp_path: Path, overrides: dict[str, object]) -> None:
    registry, root = _make_download(tmp_path, "reports/report.json", b'{"ok":true}', "application/json", **overrides)

    with pytest.raises(DownloadError) as excinfo:
        download_artifact("artifact-1", registry_root=registry, fixture_root=root)

    assert excinfo.value.status_code == 422
    assert excinfo.value.code in {"INTEGRITY_MISMATCH", "MIME_MISMATCH"}


def test_rejects_actual_mime_mismatch_for_png_extension(tmp_path: Path) -> None:
    registry, root = _make_download(tmp_path, "images/screen.png", b"not-a-png", "image/png")

    with pytest.raises(DownloadError) as excinfo:
        download_artifact("artifact-1", registry_root=registry, fixture_root=root)

    assert excinfo.value.status_code == 422
    assert excinfo.value.code == "MIME_MISMATCH"


def test_rejects_oversized_metadata_before_opening_bytes(tmp_path: Path) -> None:
    body = b'{"ok":true}'
    registry, root = _make_download(
        tmp_path,
        "reports/report.json",
        body,
        "application/json",
        byte_length=downloads.MAX_DOWNLOAD_BYTES + 1,
    )

    with pytest.raises(DownloadError) as excinfo:
        download_artifact("artifact-1", registry_root=registry, fixture_root=root)

    assert excinfo.value.status_code == 413
    assert excinfo.value.code == "ARTIFACT_TOO_LARGE"


def test_rejects_symlink_escape_without_platform_symlink_support(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    body = b'{"secret":true}'
    target = root / "report.json"
    target.write_bytes(body)
    registry = _write_snapshot(tmp_path, root, _artifact_record("artifact-1", "report.json", body, "application/json"))
    original_lstat = downloads.os.lstat

    def fake_lstat(path: Path | str) -> os.stat_result:
        result = original_lstat(path)
        if Path(path) == target:
            return _stat_with(result, mode=stat.S_IFLNK | 0o777)
        return result

    monkeypatch.setattr(downloads.os, "lstat", fake_lstat)

    with pytest.raises(DownloadError) as excinfo:
        download_artifact("artifact-1", registry_root=registry, fixture_root=root)

    assert excinfo.value.status_code == 410
    assert excinfo.value.code == "UNSAFE_LINK"


def test_rejects_hardlink_escape_without_platform_hardlink_support(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    body = b'{"secret":true}'
    target = root / "report.json"
    target.write_bytes(body)
    registry = _write_snapshot(tmp_path, root, _artifact_record("artifact-1", "report.json", body, "application/json"))
    original_lstat = downloads.os.lstat

    def fake_lstat(path: Path | str) -> os.stat_result:
        result = original_lstat(path)
        if Path(path) == target:
            return _stat_with(result, nlink=2)
        return result

    monkeypatch.setattr(downloads.os, "lstat", fake_lstat)

    with pytest.raises(DownloadError) as excinfo:
        download_artifact("artifact-1", registry_root=registry, fixture_root=root)

    assert excinfo.value.status_code == 410
    assert excinfo.value.code == "UNSAFE_LINK"


def test_rejects_special_files_without_platform_fifo_support(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    body = b""
    target = root / "report.json"
    target.write_bytes(body)
    registry = _write_snapshot(tmp_path, root, _artifact_record("artifact-1", "report.json", body, "application/json"))
    original_lstat = downloads.os.lstat

    def fake_lstat(path: Path | str) -> os.stat_result:
        result = original_lstat(path)
        if Path(path) == target:
            return _stat_with(result, mode=stat.S_IFIFO | 0o600)
        return result

    monkeypatch.setattr(downloads.os, "lstat", fake_lstat)

    with pytest.raises(DownloadError) as excinfo:
        download_artifact("artifact-1", registry_root=registry, fixture_root=root)

    assert excinfo.value.status_code == 410
    assert excinfo.value.code == "SPECIAL_FILE"


def test_rejects_toctou_identity_change_between_open_and_after_restat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry, root = _make_download(tmp_path, "reports/report.json", b'{"a":1}', "application/json")
    original_fstat = downloads.os.fstat
    calls = {"count": 0}

    def stale_after_open(fd: int) -> os.stat_result:
        result = original_fstat(fd)
        calls["count"] += 1
        if calls["count"] >= 2:
            values = list(result)
            values[stat.ST_SIZE] = result.st_size + 1
            return os.stat_result(values)
        return result

    monkeypatch.setattr(downloads.os, "fstat", stale_after_open)

    with pytest.raises(DownloadError) as excinfo:
        download_artifact("artifact-1", registry_root=registry, fixture_root=root)

    assert excinfo.value.status_code == 410
    assert excinfo.value.code == "TOCTOU_DETECTED"
