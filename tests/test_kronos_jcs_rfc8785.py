"""Deterministic RFC 8785 canonical-byte contract vectors for Kronos V5."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import pytest
import rfc8785


_ROOT = Path(__file__).resolve().parent.parent
_PROFILE_PATH = _ROOT / "docs" / "schemas" / "kronos_jcs_profile.v1.json"
_VECTORS_PATH = Path(__file__).resolve().parent / "data" / "kronos_jcs_rfc8785_v1_vectors.json"


class CanonicalInputError(ValueError):
    """Raised when JSON is outside the V5 I-JSON input domain."""


def _unique_object_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalInputError("duplicate object member names")
        result[key] = value
    return result


def _reject_nonfinite(_: str) -> None:
    raise CanonicalInputError("non-finite numbers")


def _reject_lone_surrogates(value: Any) -> None:
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise CanonicalInputError("lone UTF-16 surrogate code points")
        return
    if isinstance(value, list):
        for item in value:
            _reject_lone_surrogates(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_lone_surrogates(key)
            _reject_lone_surrogates(item)


def _checked_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        _reject_nonfinite(token)
    return value


def _checked_int(token: str) -> int:
    value = int(token)
    if abs(value) > 9007199254740991:
        raise CanonicalInputError("integers outside the IEEE 754 safe integer range")
    return value


def _strict_load(source: str) -> Any:
    if source.startswith("\ufeff"):
        raise CanonicalInputError("UTF-8 BOM")
    value = json.loads(
        source,
        object_pairs_hook=_unique_object_members,
        parse_constant=_reject_nonfinite,
        parse_float=_checked_float,
        parse_int=_checked_int,
    )
    _reject_lone_surrogates(value)
    return value


def _load_utf8_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes().decode("utf-8"))


VECTORS = _load_utf8_json(_VECTORS_PATH)


@pytest.mark.parametrize("vector", VECTORS["accepted"], ids=lambda vector: vector["id"])
def test_rfc8785_vectors_have_exact_canonical_utf8_bytes_and_sha256(
    vector: dict[str, str],
) -> None:
    canonical = rfc8785.dumps(_strict_load(vector["input_utf8"]))
    expected = vector["canonical_utf8"].encode("utf-8")

    assert canonical == expected
    assert hashlib.sha256(canonical).hexdigest() == vector["sha256"]


_PARSE_REJECTIONS = frozenset(
    {
        "UTF-8 BOM",
        "duplicate object member names",
        "lone UTF-16 surrogate code points",
        "non-finite numbers",
        "integers outside the IEEE 754 safe integer range",
    }
)
_CANONICALIZE_REJECTIONS: dict[str, type[Exception]] = {}


@pytest.mark.parametrize("vector", VECTORS["rejected"], ids=lambda vector: vector["id"])
def test_v5_jcs_rejects_inputs_outside_the_i_json_domain(
    vector: dict[str, str],
) -> None:
    stage = vector["stage"]
    rejection = vector["rejection"]

    if stage == "parse":
        assert rejection in _PARSE_REJECTIONS
        with pytest.raises(CanonicalInputError, match=f"^{re.escape(rejection)}$"):
            _strict_load(vector["input_utf8"])
    elif stage == "canonicalize":
        expected_error = _CANONICALIZE_REJECTIONS.get(rejection)
        assert expected_error is not None
        with pytest.raises(expected_error):
            rfc8785.dumps(_strict_load(vector["input_utf8"]))
    else:
        pytest.fail(f"unknown rejection stage: {stage}")


def test_v5_jcs_profile_and_vectors_are_closed_and_non_vacuous() -> None:
    profile = _load_utf8_json(_PROFILE_PATH)

    assert profile["additionalProperties"] is False
    assert profile["properties"]["profile"]["const"] == VECTORS["profile"]
    assert profile["properties"]["encoding"]["const"] == VECTORS["encoding"]
    assert {vector["id"] for vector in VECTORS["accepted"]} >= {
        "property-order-ascii",
        "property-order-utf16-code-units",
        "ecmascript-number-formatting",
        "negative-zero",
        "utf8-and-string-escaping",
        "safe-integer-positive-endpoint",
        "safe-integer-negative-endpoint",
    }
    assert {vector["rejection"] for vector in VECTORS["rejected"]} == set(
        profile["properties"]["rejected_inputs"]["items"]["enum"]
    )
