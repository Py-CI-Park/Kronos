"""Synthetic, deterministic V5 baseline evidence writer (no browser or product writes)."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import secrets
import struct
import unicodedata
import zlib
from typing import Any

import rfc8785


class BaselineError(ValueError):
    pass


def _load_manifest_path_guards() -> Any:
    spec = importlib.util.spec_from_file_location(
        "_kronos_v5_manifest_path_guards",
        Path(__file__).with_name("build_dashboard_v5_manifests.py"),
    )
    if spec is None or spec.loader is None:
        raise ImportError("build_dashboard_v5_manifests.py is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PATH_GUARDS = _load_manifest_path_guards()
_HASH_KEYS = ("producer_sha256", "schema_sha256", "instrument_sha256", "fixture_sha256")
_MANIFEST_ENTRY_KEYS = {"path", "sha256", "byte_length", "gzip9_byte_length", "browser_transfer_byte_length"}
_MANIFEST_KEYS = {"schema", "entries", "manifest_sha256", "raw_byte_length", "gzip9_byte_length", "browser_transfer_byte_length"}
_MANIFEST_SCHEMAS = (
    ("source", "kronos_source_manifest.v1"),
    ("bundle", "kronos_bundle_manifest.v1"),
    ("dist", "kronos_dist_manifest.v1"),
)


def _canonical(value: Any) -> bytes:
    return rfc8785.dumps(value)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _object_ref(uri: str, raw: bytes, schema: str) -> dict[str, Any]:
    return {"uri": uri, "sha256": _sha(raw), "byte_length": len(raw), "schema": schema}


def _reject_reserved_roots(path: Path) -> None:
    if _PATH_GUARDS._is_forbidden_path(path):
        raise BaselineError("tracked dist/OOS/database/db roots are forbidden")


def _candidate_output_root(value: str | Path) -> Path:
    path = Path(value)
    if ".." in path.parts:
        raise BaselineError("path traversal is forbidden")
    return path if path.is_absolute() else Path.cwd() / path


def _reject_symlinked_existing_path(path: Path) -> None:
    if _PATH_GUARDS._has_symlink_junction_or_reparse_ancestor(path):
        raise BaselineError("output_root must not be a symlink, junction, reparse point, or have such ancestors")


def _reject_parent_collision(path: Path) -> None:
    key = unicodedata.normalize("NFC", path.name).casefold()
    try:
        siblings = list(path.parent.iterdir())
    except OSError as exc:
        raise BaselineError("output_root parent is not readable") from exc
    for sibling in siblings:
        if unicodedata.normalize("NFC", sibling.name).casefold() == key:
            raise BaselineError("portable output path collision")


def _safe_output(output_root: str | Path) -> Path:
    root = _candidate_output_root(output_root)
    _reject_reserved_roots(root)
    _reject_symlinked_existing_path(root)
    parent = root.parent
    if not parent.exists() or _PATH_GUARDS._is_symlink_junction_or_reparse(parent) or not parent.is_dir():
        raise BaselineError("output_root parent must be an existing non-symlink/reparse directory")
    if root.exists() or _PATH_GUARDS._is_symlink_junction_or_reparse(root):
        raise BaselineError("output_root must be a fresh path")
    _reject_parent_collision(root)
    try:
        os.mkdir(root, 0o700)
    except FileExistsError as exc:
        raise BaselineError("output_root must be a fresh path") from exc
    if _PATH_GUARDS._is_symlink_junction_or_reparse(root) or not root.is_dir():
        raise BaselineError("output_root must be a fresh non-symlink/reparse directory")
    return root.resolve(strict=True)


def _mkdir_new_dir(parent: Path, name: str) -> Path:
    path = parent / name
    if _PATH_GUARDS._is_symlink_junction_or_reparse(parent) or not parent.is_dir():
        raise BaselineError("output parent must be a non-symlink/reparse directory")
    if path.exists() or _PATH_GUARDS._is_symlink_junction_or_reparse(path):
        raise BaselineError("output path already exists")
    try:
        os.mkdir(path, 0o700)
    except FileExistsError as exc:
        raise BaselineError("output path already exists") from exc
    if _PATH_GUARDS._is_symlink_junction_or_reparse(path) or not path.is_dir():
        raise BaselineError("output path must be a non-symlink/reparse directory")
    return path


def _write_new_file(path: Path, raw: bytes) -> None:
    if _PATH_GUARDS._is_symlink_junction_or_reparse(path.parent) or not path.parent.is_dir():
        raise BaselineError("output parent must be a non-symlink/reparse directory")
    if path.exists() or _PATH_GUARDS._is_symlink_junction_or_reparse(path):
        raise BaselineError("output path already exists")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise BaselineError("output path already exists") from exc
    except OSError as exc:
        raise BaselineError("output path is not safely writable") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(raw)
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    finally:
        if fd != -1:
            os.close(fd)


def _ensure_portable_output_paths(relative_paths: list[str]) -> None:
    seen: set[str] = set()
    for relative in relative_paths:
        normalized = unicodedata.normalize("NFC", relative)
        parts = normalized.split("/")
        if normalized != relative or normalized.startswith("/") or "\\" in normalized or any(part in {"", ".", ".."} for part in parts):
            raise BaselineError("unsafe output path")
        if _PATH_GUARDS._is_forbidden_relative_path(normalized):
            raise BaselineError("forbidden output path")
        key = normalized.casefold()
        if key in seen:
            raise BaselineError("portable output path collision")
        seen.add(key)


def _require_non_negative_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise BaselineError(f"{label} must be a non-negative integer")
    return value


def _validate_manifest_entry(entry: Any) -> str:
    if not isinstance(entry, dict) or set(entry) != _MANIFEST_ENTRY_KEYS:
        raise BaselineError("manifest entry has an invalid wire shape")
    path = entry["path"]
    if not isinstance(path, str) or not path:
        raise BaselineError("manifest entry path must be a non-empty string")
    normalized = unicodedata.normalize("NFC", path)
    parts = normalized.split("/")
    if normalized != path or normalized.startswith("/") or "\\" in normalized or any(part in {"", ".", ".."} for part in parts):
        raise BaselineError("manifest entry path is unsafe")
    if _PATH_GUARDS._is_forbidden_relative_path(normalized):
        raise BaselineError("manifest entry path is forbidden provenance")
    if not _is_sha256(entry["sha256"]):
        raise BaselineError("manifest entry sha256 must be lowercase SHA-256")
    _require_non_negative_int(entry["byte_length"], "manifest entry byte_length")
    _require_non_negative_int(entry["gzip9_byte_length"], "manifest entry gzip9_byte_length")
    _require_non_negative_int(entry["browser_transfer_byte_length"], "manifest entry browser_transfer_byte_length")
    return normalized.casefold()


def _validated_manifest_hash(manifest: dict[str, Any], schema: str) -> str:
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_KEYS or manifest.get("schema") != schema:
        raise BaselineError("baseline requires closed manifests")
    if not _is_sha256(manifest["manifest_sha256"]):
        raise BaselineError("manifest_sha256 must be lowercase SHA-256")
    entries = manifest["entries"]
    if not isinstance(entries, list) or not entries:
        raise BaselineError("manifest entries must be a non-empty array")
    encoded_paths = []
    collision_keys: set[str] = set()
    totals = {"raw_byte_length": 0, "gzip9_byte_length": 0, "browser_transfer_byte_length": 0}
    for entry in entries:
        key = _validate_manifest_entry(entry)
        if key in collision_keys:
            raise BaselineError("portable manifest path collision")
        collision_keys.add(key)
        encoded_paths.append(entry["path"].encode("utf-8"))
        totals["raw_byte_length"] += entry["byte_length"]
        totals["gzip9_byte_length"] += entry["gzip9_byte_length"]
        totals["browser_transfer_byte_length"] += entry["browser_transfer_byte_length"]
    if encoded_paths != sorted(encoded_paths):
        raise BaselineError("manifest entries must be sorted")
    for metric, expected in totals.items():
        actual_metric = _require_non_negative_int(manifest[metric], f"manifest {metric}")
        if actual_metric != expected:
            raise BaselineError("manifest aggregate metrics are stale")
    content = {
        "schema": schema,
        "entries": entries,
        "raw_byte_length": manifest["raw_byte_length"],
        "gzip9_byte_length": manifest["gzip9_byte_length"],
        "browser_transfer_byte_length": manifest["browser_transfer_byte_length"],
    }
    actual = _sha(_canonical(content))
    if manifest["manifest_sha256"] != actual:
        raise BaselineError("manifest hash mismatch")
    return actual


def _png() -> bytes:
    """A valid, deterministic non-uniform RGB PNG without imaging dependencies."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    # Two distinct scanlines, filter type 0, 2x2 RGB: black/red then green/blue.
    pixels = b"\x00\x00\x00\x00\xff\x00\x00\x00\xff\x00\x00\xff"
    scanlines = b"\x00" + pixels[:6] + b"\x00" + pixels[6:]
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(scanlines, 9)) + chunk(b"IEND", b"")


def capture_baseline(*, output_root: str | Path, producer_sha256: str, schema_sha256: str,
                     instrument_sha256: str, fixture_sha256: str, source_manifest: dict[str, Any],
                     bundle_manifest: dict[str, Any], dist_manifest: dict[str, Any]) -> dict[str, Any]:
    """Write closed synthetic engineering evidence and return its immutable receipt.

    All hashes are caller-supplied frozen producer inputs.  No product source,
    OOS, registry, database, or tracked dist path is read or modified.
    """
    hashes = {"producer_sha256": producer_sha256, "schema_sha256": schema_sha256,
              "instrument_sha256": instrument_sha256, "fixture_sha256": fixture_sha256}
    if set(hashes) != set(_HASH_KEYS) or any(not _is_sha256(value) for value in hashes.values()):
        raise BaselineError("frozen hashes must be lowercase SHA-256 values")
    input_manifests = {"source": source_manifest, "bundle": bundle_manifest, "dist": dist_manifest}
    manifest_hashes = {name: _validated_manifest_hash(input_manifests[name], schema) for name, schema in _MANIFEST_SCHEMAS}

    png = _png()
    png_sha = _sha(png)
    evidence = {
        "schema": "kronos_synthetic_screenshot.v1",
        "kind": "synthetic-engineering-evidence",
        "png_sha256": png_sha,
        "png_byte_length": len(png),
        "claim": "NOT_BROWSER_OR_LIVE_EVIDENCE",
    }
    evidence_raw = _canonical(evidence)
    evidence_sha = _sha(evidence_raw)
    screenshot_rel = f"objects/{png_sha}.png"
    metadata_rel = f"objects/{evidence_sha}.json"
    evidence_ref = _object_ref("agent://qa/baseline/synthetic-screenshot", evidence_raw, evidence["schema"])
    receipt = {
        "schema": "kronos_qa_baseline_receipt.v1",
        "kind": "SYNTHETIC_ENGINEERING_BASELINE",
        "six_locks_false": {
            "promotion_allowed": False,
            "model_build_allowed": False,
            "paper_forward_allowed": False,
            "live_broker_order_allowed": False,
            "profitability_claim_allowed": False,
            "go_summary_allowed": False,
        },
        "frozen_hashes": hashes,
        "manifest_sha256": manifest_hashes,
        "evidence_refs": [evidence_ref],
        "evidence_locations": {"screenshot": screenshot_rel, "metadata": metadata_rel},
        "status": "SYNTHETIC_NOT_GO",
    }
    receipt_raw = _canonical(receipt)
    receipt_sha = _sha(receipt_raw)
    receipt_rel = f"objects/{receipt_sha}.json"
    _ensure_portable_output_paths([screenshot_rel, metadata_rel, receipt_rel])

    root = _safe_output(output_root)
    run_root = _mkdir_new_dir(root, f"baseline-{secrets.token_hex(32)}")
    objects_root = _mkdir_new_dir(run_root, "objects")
    shot_path = objects_root / f"{png_sha}.png"
    evidence_path = objects_root / f"{evidence_sha}.json"
    receipt_path = objects_root / f"{receipt_sha}.json"
    _write_new_file(shot_path, png)
    _write_new_file(evidence_path, evidence_raw)
    _write_new_file(receipt_path, receipt_raw)
    return {**receipt, "receipt_ref": _object_ref("agent://qa/baseline/receipt", receipt_raw, receipt["schema"]), "receipt_location": str(receipt_path)}
