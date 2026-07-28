"""V5 point-score CLI and C2 Git-blob identity evaluator."""
from __future__ import annotations

import os
import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import rfc8785

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_SCORECARD = _ROOT / "docs" / "kronos_dashboard_v5_scorecard_v2.json"
_DEFAULT_SOURCE_SCOPE = _ROOT / "docs" / "kronos_dashboard_v5_source_scope_v1.json"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_PINNED_SCORECARD_SHA256 = "4afa3656e8bed8e5adae8bc3e99f89d5b450f8c56561429cb121aa601458ec7b"


class ScorecardError(ValueError):
    """Raised when V5 score evidence is not a closed candidate input."""


class SourceIdentityError(ValueError):
    """Raised when C2 source identity cannot be resolved fail-closed."""


def load_json(path: Path) -> Dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path} must not contain a UTF-8 BOM")

    def unique_members(pairs: List[tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{path} contains a duplicate JSON member {key!r}")
            result[key] = value
        return result

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_members, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"non-finite JSON number {token}")))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    _validate_jcs_value(value)
    return value


def _validate_jcs_value(value: Any) -> None:
    if isinstance(value, str):
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("JCS input contains a lone surrogate")
    elif isinstance(value, int) and not isinstance(value, bool):
        if abs(value) > 9007199254740991:
            raise ValueError("JCS input contains an unsafe integer")
    elif isinstance(value, float):
        raise ValueError("V5 JCS inputs must not use binary floating-point values")
    elif isinstance(value, list):
        for item in value:
            _validate_jcs_value(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JCS object keys must be strings")
            _validate_jcs_value(key)
            _validate_jcs_value(item)


def _jcs_bytes(value: Any) -> bytes:
    _validate_jcs_value(value)
    try:
        return rfc8785.dumps(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("value is outside the pinned RFC 8785 profile") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_jcs_bytes(value)).hexdigest()


_CANONICAL_SCORECARD = load_json(_DEFAULT_SCORECARD)
if (
    _CANONICAL_SCORECARD.get("schema") != "kronos_dashboard_v5_scorecard.v2"
    or _jcs_bytes(_CANONICAL_SCORECARD) != _DEFAULT_SCORECARD.read_bytes()
):
    raise RuntimeError("approved V2 scorecard is not canonical RFC8785 bytes")
_CANONICAL_SCORECARD_DIGEST = _digest(_CANONICAL_SCORECARD)
if _CANONICAL_SCORECARD_DIGEST != _PINNED_SCORECARD_SHA256:
    raise RuntimeError("approved V2 scorecard digest does not match the pin")
_CANONICAL_SCOPE = load_json(_DEFAULT_SOURCE_SCOPE)
_CANONICAL_SCOPE_DIGEST = _digest(_CANONICAL_SCOPE)


def _require_nfc(value: str, label: str) -> None:
    if unicodedata.normalize("NFC", value) != value:
        raise SourceIdentityError(f"{label} must be UTF-8 NFC")


def _validate_glob(pattern: str) -> None:
    if not isinstance(pattern, str) or not pattern or pattern.startswith("/") or "\\" in pattern or "//" in pattern:
        raise SourceIdentityError(f"invalid KRONOS_POSIX_GLOB_V1 pattern {pattern!r}")
    _require_nfc(pattern, "glob")
    for segment in pattern.split("/"):
        if segment in ("", ".", "..") or any(c in segment for c in "[]{}") or any(ord(c) < 32 or ord(c) == 127 for c in segment):
            raise SourceIdentityError(f"invalid KRONOS_POSIX_GLOB_V1 pattern {pattern!r}")
        if "**" in segment and segment != "**":
            raise SourceIdentityError(f"** must occupy a whole glob component: {pattern!r}")


def _validate_path(path: str) -> None:
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path or "//" in path or "%" in path:
        raise SourceIdentityError(f"invalid repository path {path!r}")
    _require_nfc(path, "path")
    if any(part in ("", ".", "..") or any(ord(c) < 32 or ord(c) == 127 for c in part) for part in path.split("/")):
        raise SourceIdentityError(f"invalid repository path {path!r}")


def _validate_scope(scope: Mapping[str, Any]) -> None:
    required = {"schema", "include", "exclude", "forbid_modes", "path_policy", "blob_basis"}
    if set(scope) != required or scope != _CANONICAL_SCOPE:
        raise SourceIdentityError("source scope is not the pinned V5 authority")
    if scope["schema"] != "kronos_source_scope.v1" or scope["forbid_modes"] != ["120000", "160000"]:
        raise SourceIdentityError("unsupported closed source scope")
    if scope["path_policy"] != "UTF8-NFC-POSIX-CASE-COLLISION-FORBIDDEN" or scope["blob_basis"] != "GIT_BLOB_CONTENT_BYTES":
        raise SourceIdentityError("unsupported source scope policy")
    for key in ("include", "exclude"):
        if not isinstance(scope[key], list) or not scope[key] or len(set(scope[key])) != len(scope[key]):
            raise SourceIdentityError(f"source scope {key!r} must be a unique nonempty list")
        for pattern in scope[key]:
            _validate_glob(pattern)


def _segment_matches(pattern: str, segment: str) -> bool:
    expression = "".join("[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char) for char in pattern)
    return re.fullmatch(expression, segment, flags=re.DOTALL) is not None


def restricted_posix_glob_matches(pattern: str, path: str) -> bool:
    _validate_glob(pattern)
    _validate_path(path)
    patterns, paths = pattern.split("/"), path.split("/")

    @lru_cache(maxsize=None)
    def match(pattern_index: int, path_index: int) -> bool:
        if pattern_index == len(patterns):
            return path_index == len(paths)
        part = patterns[pattern_index]
        if part == "**":
            return match(pattern_index + 1, path_index) or (path_index < len(paths) and match(pattern_index, path_index + 1))
        return path_index < len(paths) and _segment_matches(part, paths[path_index]) and match(pattern_index + 1, path_index + 1)

    return match(0, 0)


def _selected(path: str, scope: Mapping[str, Any]) -> bool:
    return any(restricted_posix_glob_matches(pattern, path) for pattern in scope["include"]) and not any(restricted_posix_glob_matches(pattern, path) for pattern in scope["exclude"])


def _git(args: Iterable[str], cwd: Optional[Path] = None) -> bytes:
    completed = subprocess.run(["git", *args], cwd=cwd or _ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode:
        raise SourceIdentityError(completed.stderr.decode("utf-8", "replace").strip() or "git command failed")
    return completed.stdout


def build_source_identity(candidate: str, scope: Mapping[str, Any], cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Return the exact C2 source-identity object from Git object storage only."""
    _validate_scope(scope)
    object_format = _git(["rev-parse", "--show-object-format"], cwd).decode("ascii").strip()
    if object_format != "sha1":
        raise SourceIdentityError("V5 source identity supports only Git SHA-1 object format")
    commit = _git(["rev-parse", "--verify", f"{candidate}^{{commit}}"], cwd).decode("ascii").strip()
    tree = _git(["rev-parse", "--verify", f"{commit}^{{tree}}"], cwd).decode("ascii").strip()
    if not _GIT_SHA1.fullmatch(commit) or not _GIT_SHA1.fullmatch(tree):
        raise SourceIdentityError("candidate commit/tree is not a lowercase SHA-1 OID")
    files: List[Dict[str, Any]] = []
    casefolded_paths = set()
    for record in _git(["ls-tree", "-r", "-z", commit], cwd).split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_type, object_id = metadata.split(b" ")
            path = raw_path.decode("utf-8", "strict")
            mode_text, kind, oid = mode.decode("ascii"), object_type.decode("ascii"), object_id.decode("ascii")
        except (UnicodeDecodeError, ValueError) as exc:
            raise SourceIdentityError("malformed or non-UTF-8 Git tree entry") from exc
        _validate_path(path)
        folded = path.casefold()
        if folded in casefolded_paths:
            raise SourceIdentityError("Windows Unicode case-fold path collision")
        casefolded_paths.add(folded)
        if not _selected(path, scope):
            continue
        if mode_text in scope["forbid_modes"] or kind != "blob" or mode_text not in ("100644", "100755"):
            raise SourceIdentityError(f"forbidden non-regular selected tree entry for {path}: {mode_text} {kind}")
        if not _GIT_SHA1.fullmatch(oid):
            raise SourceIdentityError("tree blob OID is not a lowercase SHA-1 OID")
        blob = _git(["cat-file", "blob", oid], cwd)
        files.append({"path": path, "git_mode": mode_text, "sha256": hashlib.sha256(blob).hexdigest(), "byte_length": len(blob)})
    if not files:
        raise SourceIdentityError("candidate selected authority sources must not be empty")
    files.sort(key=lambda entry: entry["path"].encode("utf-8"))
    if len({entry["path"] for entry in files}) != len(files):
        raise SourceIdentityError("duplicate selected source path")
    return {"schema": "kronos_source_identity.v1", "source_commit": commit, "source_tree": tree, "scope_manifest_sha256": _CANONICAL_SCOPE_DIGEST, "files": files}


def source_identity_sha256(identity: Mapping[str, Any]) -> str:
    required = {"schema", "source_commit", "source_tree", "scope_manifest_sha256", "files"}
    if set(identity) != required or identity.get("schema") != "kronos_source_identity.v1":
        raise ScorecardError("candidate source identity has an invalid wire shape")
    if not _GIT_SHA1.fullmatch(identity["source_commit"]) or not _GIT_SHA1.fullmatch(identity["source_tree"]) or identity["scope_manifest_sha256"] != _CANONICAL_SCOPE_DIGEST:
        raise ScorecardError("candidate source identity has invalid C2 identifiers")
    files = identity["files"]
    if not isinstance(files, list) or not files:
        raise ScorecardError("candidate source identity must contain selected files")
    previous = b""
    casefolded_paths = set()
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "git_mode", "sha256", "byte_length"}:
            raise ScorecardError("candidate source identity has an invalid file member")
        try:
            _validate_path(entry["path"])
        except SourceIdentityError as exc:
            raise ScorecardError("candidate source identity has an invalid file path") from exc
        if not _selected(entry["path"], _CANONICAL_SCOPE):
            raise ScorecardError("candidate source identity contains an out-of-scope file")
        folded = entry["path"].casefold()
        if folded in casefolded_paths:
            raise ScorecardError("candidate source identity contains a case-fold collision")
        casefolded_paths.add(folded)
        encoded_path = entry["path"].encode("utf-8")
        byte_length = entry["byte_length"]
        if isinstance(byte_length, bool) or not isinstance(byte_length, int) or byte_length < 0:
            raise ScorecardError("candidate source identity file byte_length is invalid")
        if encoded_path <= previous or entry["git_mode"] not in ("100644", "100755") or not isinstance(entry["sha256"], str) or not _SHA256.fullmatch(entry["sha256"]):
            raise ScorecardError("candidate source identity file ordering or fields are invalid")
        previous = encoded_path
    return _digest(identity)


def score_candidate_map(candidate_map_raw: bytes, *, resolver: Any, process_label: str = "") -> bytes:
    """Return the authoritative ``kronos_point_score.v2`` RFC8785 bytes plus LF."""
    root = str(_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from stom_rl.v5_score_dag import score_candidate_map as authoritative_score

    return authoritative_score(candidate_map_raw, resolver=resolver, process_label=process_label)


def _snapshot_objects(directory: Path) -> Dict[str, bytes]:
    """Read an immutable, digest-addressed object snapshot before scoring."""
    if not directory.is_dir():
        raise ScorecardError("object directory does not exist")
    snapshot: Dict[str, bytes] = {}
    for entry in directory.iterdir():
        if not entry.is_file() or _SHA256.fullmatch(entry.name) is None:
            continue
        raw = entry.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry.name:
            raise ScorecardError(f"object filename does not match its SHA-256: {entry.name}")
        snapshot[entry.name] = raw
    return snapshot


def _write_atomically(path: Path, raw: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(raw)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Emit the authoritative V5 candidate point score.")
    parser.add_argument("--candidate-map", required=True, help="Canonical kronos_candidate_map.v2 bytes")
    parser.add_argument("--objects-dir", required=True, help="Directory of SHA-256-named canonical evidence objects")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        candidate_map_raw = Path(args.candidate_map).read_bytes()
        snapshot = _snapshot_objects(Path(args.objects_dir))

        def resolve(reference: Mapping[str, Any]) -> bytes:
            try:
                return snapshot[reference["sha256"]]
            except (KeyError, TypeError) as exc:
                raise ScorecardError("referenced object is absent from the atomic snapshot") from exc

        encoded = score_candidate_map(candidate_map_raw, resolver=resolve)
    except (ScorecardError, SourceIdentityError, ValueError, OSError) as exc:
        print(f"V5_SCORE_REJECTED: {exc}", file=sys.stderr)
        return 2
    if args.out:
        _write_atomically(Path(args.out), encoded)
    sys.stdout.buffer.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
