"""Bounded, mtime+size-keyed memoization for repeated artifact reads.

Non-frozen wrapper module (Kronos 90->95 Todo 9). Repeated dashboard requests
re-stat and re-parse the same JSON artifacts and the same JSONL live-event
tail files many times per request/poll. This module adds a small bounded LRU
in front of those reads, keyed by ``(resolved_path, st_mtime_ns, st_size)`` so
a changed artifact (different mtime OR different size) is always a fresh
read -- never a stale cache hit.

``stom_rl/rl_events.py`` is schema-frozen and MUST NOT be edited; this module
only wraps ``read_live_events`` from the outside.

Design invariants:
- A missing file, a read error, or a parse error is NEVER cached and NEVER
  reported as a cache hit. Those cases always fall through to (and return or
  raise) exactly what the wrapped function/call would produce on its own.
- The cache is bounded (LRU eviction) so it cannot grow without limit.
- Thread-safe: a single lock guards cache mutation and stats bookkeeping.
"""

from __future__ import annotations

import json
import copy
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from stom_rl.rl_events import read_live_events as _read_live_events

DEFAULT_MAXSIZE = 256

StatKey = Tuple[str, int, int]

__all__ = [
    "DEFAULT_MAXSIZE",
    "cached_read_live_events",
    "cached_load_json",
    "cache_stats",
    "clear_cache",
    "configure",
]


class _BoundedLRU:
    """A minimal thread-unsafe (caller-locked) bounded LRU dict."""

    def __init__(self, maxsize: int = DEFAULT_MAXSIZE) -> None:
        self.maxsize = max(1, int(maxsize))
        self._data: "OrderedDict[Any, Any]" = OrderedDict()

    def get(self, key: Any) -> Tuple[Any, bool]:
        try:
            value = self._data.pop(key)
        except KeyError:
            return None, False
        self._data[key] = value  # mark as most-recently-used
        return value, True

    def set(self, key: Any, value: Any) -> None:
        if key in self._data:
            self._data.pop(key)
        self._data[key] = value
        self._trim()

    def _trim(self) -> None:
        while len(self._data) > self.maxsize:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)


_lock = threading.Lock()
_stats = {"hits": 0, "misses": 0}
_json_cache = _BoundedLRU(DEFAULT_MAXSIZE)
_events_cache = _BoundedLRU(DEFAULT_MAXSIZE)
_generic_cache = _BoundedLRU(DEFAULT_MAXSIZE)


def _safe_stat_key(path: Path) -> StatKey | None:
    """Return ``(resolved_path, mtime_ns, size)`` or ``None`` if stat fails.

    A ``None`` result (missing file, permission error, etc.) means the caller
    MUST NOT consult or populate the cache -- the underlying read is left to
    fail/return on its own so errors and "missing" outcomes are never masked.
    """

    try:
        resolved = str(path.resolve())
        st = path.stat()
    except OSError:
        return None
    return resolved, st.st_mtime_ns, st.st_size


def configure(maxsize: int = DEFAULT_MAXSIZE) -> None:
    """Resize both bounded caches (mainly for tests)."""

    with _lock:
        _json_cache.maxsize = max(1, int(maxsize))
        _events_cache.maxsize = max(1, int(maxsize))
        _generic_cache.maxsize = max(1, int(maxsize))
        _json_cache._trim()
        _events_cache._trim()
        _generic_cache._trim()


def cached_read_live_events(
    path: str | Path, *, limit: int = 500, tail: bool = True
) -> Tuple[List[Dict[str, Any]], bool]:
    """Memoized wrapper around ``stom_rl.rl_events.read_live_events``.

    Cache key includes ``limit``/``tail`` so different call shapes never
    collide. A file that is missing (or otherwise fails to stat) is never
    cached; every call re-invokes ``read_live_events`` and returns exactly
    what it returns.
    """

    path = Path(path)
    stat_key = _safe_stat_key(path)
    if stat_key is None:
        with _lock:
            _stats["misses"] += 1
        return _read_live_events(path, limit=limit, tail=tail)

    cache_key = (*stat_key, int(limit), bool(tail))
    with _lock:
        cached, hit = _events_cache.get(cache_key)
        if hit:
            _stats["hits"] += 1
            return copy.deepcopy(cached)
        _stats["misses"] += 1

    result = _read_live_events(path, limit=limit, tail=tail)
    with _lock:
        _events_cache.set(cache_key, result)
    return copy.deepcopy(result)


def cached_load_json(path: str | Path) -> Dict[str, Any]:
    """Memoized JSON load keyed by ``(resolved_path, mtime_ns, size)``.

    Behaves exactly like ``json.loads(Path(path).read_text(encoding="utf-8"))``:
    a missing file raises ``FileNotFoundError`` and malformed JSON raises
    ``json.JSONDecodeError``. Neither outcome is cached or counted as a hit.
    """

    path = Path(path)
    stat_key = _safe_stat_key(path)
    if stat_key is None:
        with _lock:
            _stats["misses"] += 1
        return json.loads(path.read_text(encoding="utf-8"))

    with _lock:
        cached, hit = _json_cache.get(stat_key)
        if hit:
            _stats["hits"] += 1
            return copy.deepcopy(cached)
        _stats["misses"] += 1

    value = json.loads(path.read_text(encoding="utf-8"))
    with _lock:
        _json_cache.set(stat_key, value)
    return copy.deepcopy(value)


def cached_by_stat(path: str | Path, compute, *, extra: Any = None):
    """Memoize an arbitrary ``compute()`` keyed by a file's stat + ``extra``.

    Use for expensive artifact VALIDATION whose result is a pure function of a
    keying file (e.g. a gate manifest) plus a scalar ``extra`` (e.g. sample
    limit). Invalidates on any mtime/size change of ``path``; when stat fails the
    cache is bypassed and ``compute()`` runs directly (never a masked hit).
    Returns a deep copy of the cached value so the caller may mutate it freely
    without corrupting the cached canonical.
    """

    stat_key = _safe_stat_key(Path(path))
    if stat_key is None:
        with _lock:
            _stats["misses"] += 1
        return compute()
    key = (stat_key, extra)
    with _lock:
        cached, hit = _generic_cache.get(key)
        if hit:
            _stats["hits"] += 1
            return copy.deepcopy(cached)
        _stats["misses"] += 1
    value = compute()
    with _lock:
        _generic_cache.set(key, value)
    return copy.deepcopy(value)


def cache_stats() -> Dict[str, int]:
    """Return ``{"hits": int, "misses": int, "size": int}`` for observability."""

    with _lock:
        return {
            "hits": _stats["hits"],
            "misses": _stats["misses"],
            "size": len(_json_cache) + len(_events_cache) + len(_generic_cache),
        }


def clear_cache() -> None:
    """Drop all cached entries and reset hit/miss counters."""

    with _lock:
        _json_cache.clear()
        _events_cache.clear()
        _generic_cache.clear()
        _stats["hits"] = 0
        _stats["misses"] = 0
