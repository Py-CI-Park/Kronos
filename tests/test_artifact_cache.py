"""Tests for webui/artifact_cache.py (Kronos 90->95 Todo 9 backend memoization).

Covers: cache hits on unchanged files, invalidation on size change, invalidation
on mtime-only change (touch), missing files never counted as hits, bounded LRU
eviction, and byte-for-byte parity with stom_rl.rl_events.read_live_events.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from webui import artifact_cache  # noqa: E402
from stom_rl.rl_events import read_live_events  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_cache():
    artifact_cache.clear_cache()
    artifact_cache.configure(artifact_cache.DEFAULT_MAXSIZE)
    yield
    artifact_cache.clear_cache()
    artifact_cache.configure(artifact_cache.DEFAULT_MAXSIZE)


def _bump_mtime(path: Path, *, offset_seconds: float = 5.0) -> None:
    """Force a distinct mtime (Windows FS mtime resolution can be coarse)."""

    stat = path.stat()
    new_time = stat.st_mtime + offset_seconds
    os.utime(path, (new_time, new_time))


def test_cached_load_json_hits_on_unchanged_file(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"a": 1}), encoding="utf-8")

    first = artifact_cache.cached_load_json(path)
    stats_after_first = artifact_cache.cache_stats()
    second = artifact_cache.cached_load_json(path)
    stats_after_second = artifact_cache.cache_stats()

    assert first == {"a": 1}
    assert second == {"a": 1}
    assert second == first
    assert second is not first  # isolated deep copy so a consumer cannot corrupt the cache
    assert stats_after_first["misses"] == 1
    assert stats_after_first["hits"] == 0
    assert stats_after_second["hits"] == 1
    assert stats_after_second["misses"] == 1


def test_cached_load_json_returns_isolated_copy_mutation_safe(tmp_path):
    # Regression: cached_load_json must return an isolated copy so a consumer
    # that mutates the result in place (like load_daily_db_summary) cannot
    # corrupt the cached canonical on the NEXT hit for the unchanged file.
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"price_basis": "artifact_value", "rows": [1, 2, 3]}), encoding="utf-8")
    first = artifact_cache.cached_load_json(path)
    first["price_basis"] = "OVERWRITTEN"
    first["rows"] = first["rows"][:1]
    second = artifact_cache.cached_load_json(path)  # cache hit on the unchanged file
    assert second["price_basis"] == "artifact_value"
    assert second["rows"] == [1, 2, 3]
    assert second is not first


def test_cached_by_stat_returns_isolated_copy(tmp_path):
    path = tmp_path / "csv.txt"
    path.write_text("x", encoding="utf-8")
    first = artifact_cache.cached_by_stat(path, lambda: {"k": [1, 2]}, extra="t")
    first["k"].append(999)
    second = artifact_cache.cached_by_stat(path, lambda: {"k": [1, 2]}, extra="t")
    assert second == {"k": [1, 2]}  # hit is not corrupted by the prior mutation
    assert second is not first


def test_cached_load_json_invalidates_on_size_change(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"a": 1}), encoding="utf-8")
    first = artifact_cache.cached_load_json(path)
    assert first == {"a": 1}

    # Different content with a different byte size -> must NOT be stale.
    path.write_text(json.dumps({"a": 1, "b": "much longer payload value"}), encoding="utf-8")
    second = artifact_cache.cached_load_json(path)

    assert second == {"a": 1, "b": "much longer payload value"}
    stats = artifact_cache.cache_stats()
    assert stats["misses"] == 2
    assert stats["hits"] == 0


def test_cached_load_json_invalidates_on_mtime_only_change(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"a": 1}), encoding="utf-8")
    first = artifact_cache.cached_load_json(path)
    assert first == {"a": 1}

    # Same size, different content, mtime bumped explicitly -> must invalidate.
    path.write_text(json.dumps({"a": 2}), encoding="utf-8")
    assert len(json.dumps({"a": 2})) == len(json.dumps({"a": 1}))
    _bump_mtime(path)

    second = artifact_cache.cached_load_json(path)
    assert second == {"a": 2}
    stats = artifact_cache.cache_stats()
    assert stats["misses"] == 2
    assert stats["hits"] == 0


def test_cached_load_json_missing_file_not_cached_as_hit(tmp_path):
    path = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError):
        artifact_cache.cached_load_json(path)
    with pytest.raises(FileNotFoundError):
        artifact_cache.cached_load_json(path)

    stats = artifact_cache.cache_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 2
    assert stats["size"] == 0


def test_cached_load_json_malformed_json_not_cached_as_hit(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        artifact_cache.cached_load_json(path)
    with pytest.raises(json.JSONDecodeError):
        artifact_cache.cached_load_json(path)

    stats = artifact_cache.cache_stats()
    assert stats["hits"] == 0
    assert stats["size"] == 0


def test_lru_is_bounded_and_evicts_oldest(tmp_path):
    artifact_cache.configure(maxsize=3)
    paths = []
    for i in range(5):
        path = tmp_path / f"file_{i}.json"
        path.write_text(json.dumps({"i": i}), encoding="utf-8")
        paths.append(path)
        artifact_cache.cached_load_json(path)

    stats = artifact_cache.cache_stats()
    assert stats["size"] == 3

    # The two oldest entries (file_0, file_1) were evicted -> fresh misses.
    misses_before = artifact_cache.cache_stats()["misses"]
    artifact_cache.cached_load_json(paths[0])
    misses_after = artifact_cache.cache_stats()["misses"]
    assert misses_after == misses_before + 1

    # The most recently used entries are still cached -> hits.
    hits_before = artifact_cache.cache_stats()["hits"]
    artifact_cache.cached_load_json(paths[4])
    hits_after = artifact_cache.cache_stats()["hits"]
    assert hits_after == hits_before + 1


def test_cached_read_live_events_matches_underlying_for_same_args(tmp_path):
    path = tmp_path / "events.jsonl"
    lines = [json.dumps({"global_step": i, "phase": "train"}) for i in range(10)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    expected = read_live_events(path, limit=5, tail=True)
    actual = artifact_cache.cached_read_live_events(path, limit=5, tail=True)
    assert actual == expected

    expected_head = read_live_events(path, limit=4, tail=False)
    actual_head = artifact_cache.cached_read_live_events(path, limit=4, tail=False)
    assert actual_head == expected_head


def test_cached_read_live_events_hits_and_invalidates(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps({"global_step": 1}) + "\n", encoding="utf-8")

    first = artifact_cache.cached_read_live_events(path, limit=500, tail=True)
    stats = artifact_cache.cache_stats()
    assert stats["misses"] == 1

    second = artifact_cache.cached_read_live_events(path, limit=500, tail=True)
    stats = artifact_cache.cache_stats()
    assert stats["hits"] == 1
    assert second == first

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"global_step": 2}) + "\n")

    third = artifact_cache.cached_read_live_events(path, limit=500, tail=True)
    stats = artifact_cache.cache_stats()
    assert stats["misses"] == 2
    assert third != first
    assert len(third[0]) == 2


def test_cached_read_live_events_missing_file_matches_underlying(tmp_path):
    path = tmp_path / "missing_events.jsonl"

    expected = read_live_events(path, limit=500, tail=True)
    actual = artifact_cache.cached_read_live_events(path, limit=500, tail=True)

    assert actual == expected
    assert actual == ([], False)
    stats = artifact_cache.cache_stats()
    assert stats["hits"] == 0
