"""Verify official dashboard markers are preserved after Vite build."""
from html.parser import HTMLParser
from pathlib import Path
from pathlib import PurePosixPath
import subprocess
from urllib.parse import unquote, urlsplit

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_INDEX = (
    REPO_ROOT / "webui" / "static" / "v2" / "dist" / "index.html"
)
DIST_URL_PREFIX = "/static/v2/dist/"
OFFICIAL_SHELL_MARKER = "kronos-dashboard-shell"
LEGACY_PUBLIC_MARKERS = (
    "kronos-v2-version",
    "p1-ssr",
    "p1-5-spa",
)


class _DistReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        reference = attributes.get("src" if tag == "script" else "href")
        if tag in {"script", "link"} and reference and reference.startswith(DIST_URL_PREFIX):
            self.references.append((tag, reference))


def _dist_body() -> str:
    return DIST_INDEX.read_text(encoding="utf-8")


def _tracked_dist_paths(repo_root: Path, dist_dir: Path) -> frozenset[str]:
    try:
        dist_relative = dist_dir.relative_to(repo_root).as_posix()
    except ValueError as error:
        raise AssertionError(
            f"dist directory {dist_dir} is not beneath repository root {repo_root}"
        ) from error

    result = subprocess.run(
        ["git", "ls-files", "-z", "--", dist_relative],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise AssertionError(f"could not inspect tracked dist files with git: {detail}")
    return frozenset(
        path for path in result.stdout.decode("utf-8", errors="strict").split("\0") if path
    )


def _resolve_dist_reference(reference: str, dist_dir: Path) -> Path:
    parsed = urlsplit(reference)
    assert not parsed.scheme and not parsed.netloc, (
        f"dist reference must be a local /static URL, got {reference!r}"
    )
    path = unquote(parsed.path)
    assert path.startswith(DIST_URL_PREFIX), f"not a dist reference: {reference!r}"
    relative = path.removeprefix(DIST_URL_PREFIX)
    assert relative and not relative.startswith("/") and "\\" not in relative, (
        f"dist reference must be relative to {DIST_URL_PREFIX}, got {reference!r}"
    )
    relative_path = PurePosixPath(relative)
    assert all(part not in {".", ".."} for part in relative_path.parts), (
        f"dist reference must not traverse directories: {reference!r}"
    )

    dist_root = dist_dir.resolve()
    candidate = (dist_dir / relative_path).resolve()
    try:
        candidate.relative_to(dist_root)
    except ValueError as error:
        raise AssertionError(
            f"dist reference resolves outside {dist_root}: {reference!r}"
        ) from error
    return candidate


def _assert_dist_references_closed(
    body: str, *, repo_root: Path, dist_dir: Path, tracked_paths: frozenset[str]
) -> None:
    parser = _DistReferenceParser()
    parser.feed(body)
    parser.close()

    for tag, reference in parser.references:
        asset = _resolve_dist_reference(reference, dist_dir)
        assert asset.is_file(), (
            f"{tag} reference {reference!r} does not resolve to a regular dist file: {asset}"
        )
        asset_relative = asset.relative_to(repo_root.resolve()).as_posix()
        assert asset_relative in tracked_paths, (
            f"{tag} reference {reference!r} resolves to untracked dist file "
            f"{asset_relative}; rebuild and commit the complete bundle"
        )

        source_map = asset.with_name(f"{asset.name}.map")
        source_map_relative = source_map.relative_to(repo_root.resolve()).as_posix()
        if asset.suffix in {".js", ".css"} and source_map_relative in tracked_paths:
            assert source_map.is_file(), (
                f"tracked source map for {reference!r} is missing or not a regular file: "
                f"{source_map}"
            )


def _fixture_dist(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    dist_dir = repo_root / "webui" / "static" / "v2" / "dist"
    dist_dir.mkdir(parents=True)
    return repo_root, dist_dir


@pytest.mark.skipif(not DIST_INDEX.exists(), reason="dist has not been built yet")
def test_official_dist_marker_preserved_after_build():
    body = _dist_body()

    assert OFFICIAL_SHELL_MARKER in body
    for marker in LEGACY_PUBLIC_MARKERS:
        assert marker not in body


@pytest.mark.skipif(not DIST_INDEX.exists(), reason="dist has not been built yet")
def test_dist_base_url_matches_flask_static():
    body = _dist_body()

    assert "/static/v2/dist/assets/" in body


@pytest.mark.skipif(not DIST_INDEX.exists(), reason="dist has not been built yet")
def test_dist_fallback_first_paint_present():
    body = _dist_body()

    assert 'id="hero-strip"' in body
    assert 'data-tab="live-training"' in body


@pytest.mark.skipif(not DIST_INDEX.exists(), reason="dist has not been built yet")
def test_dist_public_copy_has_no_versioned_dashboard_label():
    body = _dist_body()

    assert "Kronos v2" not in body
    assert "P1" not in body
    assert "P1.5" not in body


@pytest.mark.skipif(not DIST_INDEX.exists(), reason="dist has not been built yet")
def test_tracked_dist_references_are_closed():
    _assert_dist_references_closed(
        _dist_body(),
        repo_root=REPO_ROOT,
        dist_dir=DIST_INDEX.parent,
        tracked_paths=_tracked_dist_paths(REPO_ROOT, DIST_INDEX.parent),
    )


def test_dist_reference_closure_rejects_missing_file(tmp_path: Path):
    repo_root, dist_dir = _fixture_dist(tmp_path)

    with pytest.raises(AssertionError, match="does not resolve to a regular dist file"):
        _assert_dist_references_closed(
            '<script src="/static/v2/dist/assets/missing.js"></script>',
            repo_root=repo_root,
            dist_dir=dist_dir,
            tracked_paths=frozenset({"webui/static/v2/dist/assets/missing.js"}),
        )


def test_dist_reference_closure_rejects_untracked_file(tmp_path: Path):
    repo_root, dist_dir = _fixture_dist(tmp_path)
    asset = dist_dir / "assets" / "bundle.js"
    asset.parent.mkdir()
    asset.write_text("", encoding="utf-8")

    with pytest.raises(AssertionError, match="untracked dist file"):
        _assert_dist_references_closed(
            '<script src="/static/v2/dist/assets/bundle.js"></script>',
            repo_root=repo_root,
            dist_dir=dist_dir,
            tracked_paths=frozenset(),
        )


@pytest.mark.parametrize(
    "reference",
    (
        "/static/v2/dist//absolute.js",
        "/static/v2/dist/assets/../escape.js",
    ),
)
def test_dist_reference_closure_rejects_absolute_and_traversal_paths(
    tmp_path: Path, reference: str
):
    repo_root, dist_dir = _fixture_dist(tmp_path)

    with pytest.raises(AssertionError, match="relative to|traverse"):
        _assert_dist_references_closed(
            f'<link rel="modulepreload" href="{reference}">',
            repo_root=repo_root,
            dist_dir=dist_dir,
            tracked_paths=frozenset(),
        )


def test_dist_reference_closure_rejects_non_file(tmp_path: Path):
    repo_root, dist_dir = _fixture_dist(tmp_path)
    (dist_dir / "assets" / "directory.js").mkdir(parents=True)

    with pytest.raises(AssertionError, match="does not resolve to a regular dist file"):
        _assert_dist_references_closed(
            '<link rel="stylesheet" href="/static/v2/dist/assets/directory.js">',
            repo_root=repo_root,
            dist_dir=dist_dir,
            tracked_paths=frozenset({"webui/static/v2/dist/assets/directory.js"}),
        )


def test_dist_source_maps_are_checked_only_when_tracked(tmp_path: Path):
    repo_root, dist_dir = _fixture_dist(tmp_path)
    asset = dist_dir / "assets" / "bundle.js"
    asset.parent.mkdir()
    asset.write_text("", encoding="utf-8")
    asset_path = "webui/static/v2/dist/assets/bundle.js"
    source_map_path = f"{asset_path}.map"
    body = '<script src="/static/v2/dist/assets/bundle.js"></script>'

    _assert_dist_references_closed(
        body,
        repo_root=repo_root,
        dist_dir=dist_dir,
        tracked_paths=frozenset({asset_path}),
    )
    with pytest.raises(AssertionError, match="tracked source map"):
        _assert_dist_references_closed(
            body,
            repo_root=repo_root,
            dist_dir=dist_dir,
            tracked_paths=frozenset({asset_path, source_map_path}),
        )
