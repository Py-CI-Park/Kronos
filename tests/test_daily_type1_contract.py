from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from stom_rl.daily_type1_contract import (
    FEATURES,
    Type1Contract,
    canonical_json_bytes,
    sha256_canonical,
)


def test_type1_contract_freezes_all_v1_values() -> None:
    contract = Type1Contract()
    assert contract.to_dict() == {
        "features": (
            "ret_1d_prev", "ret_5d_prev", "ret_20d_prev", "vol_z_20",
            "foreign_ratio_prev", "foreign_ratio_delta_5", "inst_netbuy_norm_5",
        ),
        "seeds": (0, 1, 2, 3, 4),
        "primary_cost_bp": 23,
        "cost_scenarios_bp": (0, 23, 46),
        "initial_nav_krw": 60_000_000,
        "slot_notional_krw": 5_000_000,
        "max_slots": 10,
        "stable_slots": 500,
        "execution_proxy": "15:20_bar_close_proxy",
        "proxy_time": "15:20:00",
        "proxy_timezone": "Asia/Seoul",
        "session_stride": 2,
        "split_label": "RESEARCH_ONLY_HISTORICAL_SECONDARY",
        "partition_label": "historical_secondary_only",
        "observation_cutoffs": ("D-1", "D-2"),
        "missing_entry_policy": "NO_FILL",
        "fresh_oos_access_allowed": False,
        "official_close": False,
    }
    with pytest.raises(FrozenInstanceError):
        contract.max_slots = 11  # type: ignore[misc]


@pytest.mark.parametrize("field,value", [
    ("features", FEATURES[:-1]), ("seeds", (0, 1, 2)), ("primary_cost_bp", 22),
    ("cost_scenarios_bp", (0, 23)), ("initial_nav_krw", 1), ("slot_notional_krw", 1),
    ("max_slots", 11), ("stable_slots", 499), ("execution_proxy", "official_close"),
    ("proxy_time", "15:30:00"), ("proxy_timezone", "UTC"), ("session_stride", 1),
    ("split_label", "fresh_oos"), ("partition_label", "fresh_oos"),
    ("observation_cutoffs", ("D-1",)), ("missing_entry_policy", "FALLBACK"),
    ("fresh_oos_access_allowed", True), ("official_close", True),
])
def test_type1_contract_rejects_schema_changes(field: str, value: object) -> None:
    values = Type1Contract().to_dict()
    values[field] = value
    with pytest.raises(ValueError):
        Type1Contract(**values)


def test_contract_mapping_and_canonical_hash_are_order_independent() -> None:
    contract = Type1Contract()
    assert Type1Contract.from_mapping(contract.to_dict()) == contract
    first = {"z": [Decimal("1.20"), "000250"], "a": True}
    second = {"a": True, "z": [Decimal("1.20"), "000250"]}
    assert canonical_json_bytes(first) == b'{"a":true,"z":["1.20","000250"]}'
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert sha256_canonical(first) == sha256_canonical(second)

def test_type1_contract_from_mapping_fails_closed() -> None:
    contract_mapping = Type1Contract().to_dict()
    missing_field = dict(contract_mapping)
    missing_field.pop("proxy_timezone")
    unknown_field = {**contract_mapping, "unexpected": "value"}
    malformed_value = {**contract_mapping, "max_slots": True}

    with pytest.raises(ValueError, match=r"^Type1Contract mapping has missing or unknown fields$"):
        Type1Contract.from_mapping(missing_field)
    with pytest.raises(ValueError, match=r"^Type1Contract mapping has missing or unknown fields$"):
        Type1Contract.from_mapping(unknown_field)
    with pytest.raises(ValueError, match=r"^Type1Contract mapping must be a mapping$"):
        Type1Contract.from_mapping(None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"^max_slots must be 10$"):
        Type1Contract.from_mapping(malformed_value)


@pytest.mark.parametrize("value", [{"x": float("nan")}, {"x": Decimal("Infinity")}, {1: "x"}])
def test_canonical_json_rejects_noncanonical_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        canonical_json_bytes(value)
