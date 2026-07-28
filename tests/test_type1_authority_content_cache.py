"""Regression coverage for content-bound Type1 authority computation reuse."""
from __future__ import annotations

import builtins
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier, Lock
from types import MappingProxyType

import pytest
import rfc8785

from stom_rl import daily_type1_authority, daily_type1_content_cache
from stom_rl.daily_type1_content_cache import (
    canonical_json_cached,
    validate_authority_cached,
)


def test_canonical_json_translates_missing_rfc8785(monkeypatch) -> None:
    original_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "rfc8785":
            raise ImportError("blocked for test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    with pytest.raises(daily_type1_authority.AuthorityError, match="rfc8785 is required"):
        daily_type1_authority.canonical_json({"marker": str(uuid.uuid4())})


def test_canonical_json_reuses_rfc8785_result_for_identical_content(monkeypatch) -> None:
    marker = str(uuid.uuid4())
    first = {"marker": marker, "rows": [{"value": 1.25}]}
    calls: list[str] = []
    original_dumps = rfc8785.dumps

    def observed_dumps(value) -> bytes:
        calls.append(value["marker"])
        return original_dumps(value)

    monkeypatch.setattr(rfc8785, "dumps", observed_dumps)

    first_raw = daily_type1_authority.canonical_json(first)
    second_raw = daily_type1_authority.canonical_json(deepcopy(first))

    assert first_raw == second_raw
    assert calls == [marker]


def test_validate_authority_reuses_completed_validation_for_identical_content(monkeypatch) -> None:
    marker = f"cache-test-{uuid.uuid4()}"
    raw_responses = {
        "calendar": {},
        "historical_anchor_by_market": {},
        "traded_value_by_session": {},
        "typed_current": {},
        "typed_delisted_chunks": [],
    }
    authority = {
        "authority_id": daily_type1_authority.AUTHORITY_ID,
        "anchor_date": daily_type1_authority.ANCHOR,
        "approved_dates": {"calendar_start": "2018-01-02", "public_end": daily_type1_authority.PUBLIC_END},
        "provider": {"name": "KRX public data portal", "retrieval_utc": marker},
        "query_profile": {},
        "classification_profile": {},
        "candidate_exclusions": [],
        "raw_responses": raw_responses,
        "raw_sha256": daily_type1_authority.sha256_canonical(raw_responses),
        "sessions": {},
        "ranking": {},
        "stable_symbols": [],
        "fresh_oos": {"status": "NOT_RUN", "no_read": True},
    }
    envelope = {"authority": authority, "integrity": {}, "schema": daily_type1_authority.SCHEMA}
    signature_calls: list[str] = []
    reconstruction_calls: list[str] = []

    monkeypatch.setattr(
        daily_type1_authority,
        "_validate_signature",
        lambda value, integrity: signature_calls.append(value["provider"]["retrieval_utc"]),
    )
    monkeypatch.setattr(
        daily_type1_authority,
        "_validate_reconstruction",
        lambda value: reconstruction_calls.append(value["provider"]["retrieval_utc"]),
    )

    daily_type1_authority.validate_authority(envelope)
    daily_type1_authority.validate_authority(deepcopy(envelope))

    assert signature_calls == [marker]
    assert reconstruction_calls == [marker]


def test_validation_cache_preserves_list_and_tuple_types() -> None:
    calls: list[type[object]] = []

    def validator(value) -> None:
        calls.append(type(value["ordered"]))

    validate_authority_cached({"ordered": [1]}, validator, RuntimeError)
    validate_authority_cached({"ordered": (1,)}, validator, RuntimeError)

    assert calls == [list, tuple]


def test_validation_cache_falls_back_for_unpicklable_mapping() -> None:
    value = MappingProxyType({"marker": str(uuid.uuid4())})
    calls: list[object] = []

    validate_authority_cached(value, calls.append, RuntimeError)

    assert calls == [value]


def test_failed_validation_is_not_cached() -> None:
    value = {"marker": str(uuid.uuid4())}
    calls = 0

    def reject(_value) -> None:
        nonlocal calls
        calls += 1
        raise ValueError("invalid")

    with pytest.raises(ValueError, match="invalid"):
        validate_authority_cached(value, reject, RuntimeError)
    with pytest.raises(ValueError, match="invalid"):
        validate_authority_cached(deepcopy(value), reject, RuntimeError)

    assert calls == 2


def test_concurrent_validation_misses_are_single_flight() -> None:
    value = {"marker": str(uuid.uuid4())}
    barrier = Barrier(6)
    call_lock = Lock()
    calls = 0

    def validator(_value) -> None:
        nonlocal calls
        with call_lock:
            calls += 1
        time.sleep(0.05)

    def validate_copy() -> None:
        barrier.wait()
        validate_authority_cached(deepcopy(value), validator, RuntimeError)

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(validate_copy) for _ in range(6)]
        for future in futures:
            future.result()

    assert calls == 1


def test_oversized_canonical_result_is_not_retained(monkeypatch) -> None:
    value = {"marker": str(uuid.uuid4())}
    calls = 0

    def serializer(_value) -> bytes:
        nonlocal calls
        calls += 1
        return b"x" * 64

    monkeypatch.setattr(daily_type1_content_cache, "_CONTENT_CACHE_LIMIT_BYTES", 32)

    assert canonical_json_cached(value, serializer) == b"x" * 64
    assert canonical_json_cached(deepcopy(value), serializer) == b"x" * 64
    assert calls == 2
