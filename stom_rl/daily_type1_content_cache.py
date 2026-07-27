"""Bounded, content-addressed reuse for immutable Type1 authority values."""
from __future__ import annotations

import hashlib
import pickle
from collections import OrderedDict
from collections.abc import Callable
from threading import RLock
from typing import TypeVar

_Value = TypeVar("_Value")
_CONTENT_CACHE_LIMIT_BYTES = 96 * 1024 * 1024
_VALIDATION_CACHE_LIMIT = 16
_CANONICAL_BY_DIGEST: OrderedDict[bytes, bytes] = OrderedDict()
_canonical_cache_bytes = 0
_VALIDATED_DIGESTS: OrderedDict[bytes, None] = OrderedDict()
_CACHE_LOCK = RLock()


def _content_digest(value: object) -> bytes | None:
    """Return a type-preserving digest, or decline caching unsupported values."""
    try:
        encoded = pickle.dumps(value, protocol=5)
    except (AttributeError, pickle.PicklingError, TypeError):
        return None
    return hashlib.sha256(encoded).digest()


def canonical_json_cached(value: _Value, serializer: Callable[[_Value], bytes]) -> bytes:
    """Serialize once per concrete, type-preserving content digest."""
    global _canonical_cache_bytes

    digest = _content_digest(value)
    if digest is None:
        return serializer(value)
    with _CACHE_LOCK:
        cached = _CANONICAL_BY_DIGEST.get(digest)
        if cached is not None:
            _CANONICAL_BY_DIGEST.move_to_end(digest)
            return cached
        canonical = serializer(value)
        if _content_digest(value) != digest:
            raise RuntimeError("value changed during canonical serialization")
        entry_bytes = len(digest) + len(canonical)
        if entry_bytes > _CONTENT_CACHE_LIMIT_BYTES:
            return canonical
        _CANONICAL_BY_DIGEST[digest] = canonical
        _canonical_cache_bytes += entry_bytes
        while _canonical_cache_bytes > _CONTENT_CACHE_LIMIT_BYTES:
            evicted_digest, evicted = _CANONICAL_BY_DIGEST.popitem(last=False)
            _canonical_cache_bytes -= len(evicted_digest) + len(evicted)
        return canonical


def validate_authority_cached(
    value: _Value,
    validator: Callable[[_Value], None],
    mutation_error: Callable[[], Exception],
) -> None:
    """Run a successful validation once; concurrent misses are single-flight."""
    digest = _content_digest(value)
    if digest is None:
        validator(value)
        return
    with _CACHE_LOCK:
        if digest in _VALIDATED_DIGESTS:
            _VALIDATED_DIGESTS.move_to_end(digest)
            return
        validator(value)
        if _content_digest(value) != digest:
            raise mutation_error()
        _VALIDATED_DIGESTS[digest] = None
        while len(_VALIDATED_DIGESTS) > _VALIDATION_CACHE_LIMIT:
            _ = _VALIDATED_DIGESTS.popitem(last=False)


__all__ = ["canonical_json_cached", "validate_authority_cached"]
