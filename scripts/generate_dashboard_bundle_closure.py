"""Generate or verify the tracked dashboard bundle closure receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import cast

from typing_extensions import override

REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = REPO_ROOT / "webui" / "static" / "v2" / "dist"
OUTPUT = REPO_ROOT / "docs" / "kronos_v1_29_0_dashboard_bundle_closure_2026-08-14.json"
PREFIX = "/static/v2/dist/"


class _References(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: list[str] = []

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        reference = values.get("src" if tag == "script" else "href")
        if tag in {"script", "link"} and reference and reference.startswith(PREFIX):
            self.values.append(reference.removeprefix(PREFIX))


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _git_bytes(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _tracked_identity(path: Path, revision: str) -> dict[str, object]:
    relative = path.relative_to(REPO_ROOT).as_posix()
    payload = _git_bytes("show", f"{revision}:{relative}")
    return {
        "path": relative,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def build_manifest() -> dict[str, object]:
    """Build a deterministic receipt from tracked dist files and index references."""
    index = DIST_DIR / "index.html"
    parser = _References()
    parser.feed(index.read_text(encoding="utf-8"))
    parser.close()
    tracked = tuple(
        path
        for path in _git("ls-files", "--", "webui/static/v2/dist").splitlines()
        if path
    )
    tracked_set = frozenset(tracked)
    references = tuple(sorted(set(parser.values)))
    missing = tuple(
        reference for reference in references if not (DIST_DIR / reference).is_file()
    )
    untracked = tuple(
        reference
        for reference in references
        if f"webui/static/v2/dist/{reference}" not in tracked_set
    )
    stale = tuple(path for path in tracked if not (REPO_ROOT / path).is_file())
    source_commit = _git(
        "log",
        "-1",
        "--format=%H",
        "--",
        "webui/v2_src",
        "webui/static/v2/dist",
    )
    return {
        "schema": "kronos_dashboard_bundle_closure.v1",
        "generated_from_commit": source_commit,
        "generated_from_commit_time": _git("show", "-s", "--format=%cI", source_commit),
        "build_command": "npm run build",
        "frontend_source_tree": _git("rev-parse", f"{source_commit}:webui/v2_src"),
        "build_source": _tracked_identity(
            REPO_ROOT / "webui" / "v2_src" / "vite.config.ts", source_commit
        ),
        "package_lock": _tracked_identity(
            REPO_ROOT / "webui" / "v2_src" / "package-lock.json", source_commit
        ),
        "index": _tracked_identity(index, source_commit),
        "referenced_assets": [
            _tracked_identity(DIST_DIR / path, source_commit)
            for path in references
            if path not in missing
        ],
        "tracked_dist_files": [
            _tracked_identity(REPO_ROOT / path, source_commit)
            for path in tracked
            if path not in stale
        ],
        "missing_references": list(missing),
        "untracked_references": list(untracked),
        "stale_tracked_files": list(stale),
        "closure_passed": not (missing or untracked or stale),
    }


def _canonical(manifest: dict[str, object]) -> bytes:
    return (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    manifest = build_manifest()
    expected = _canonical(manifest)
    if cast(bool, arguments.check):
        if not OUTPUT.is_file():
            return 1
        try:
            recorded = cast(object, json.loads(OUTPUT.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            return 1
        return 0 if recorded == manifest else 1
    _ = OUTPUT.write_bytes(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
