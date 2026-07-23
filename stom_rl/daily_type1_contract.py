"""Frozen public contract for the Type 1 daily-close research environment."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from decimal import Decimal
import hashlib
import json
import math
from typing import Any, Mapping

FEATURES: tuple[str, ...] = (
    "ret_1d_prev",
    "ret_5d_prev",
    "ret_20d_prev",
    "vol_z_20",
    "foreign_ratio_prev",
    "foreign_ratio_delta_5",
    "inst_netbuy_norm_5",
)
SEEDS: tuple[int, ...] = (0, 1, 2, 3, 4)

PRIMARY_COST_BP = 23
ZERO_COST_BP = 0
STRESS_COST_BP = 46
COST_SCENARIOS_BP: tuple[int, ...] = (ZERO_COST_BP, PRIMARY_COST_BP, STRESS_COST_BP)
INITIAL_NAV_KRW = 60_000_000
SLOT_NOTIONAL_KRW = 5_000_000
MAX_SLOTS = 10
STABLE_SLOTS = 500
EXECUTION_PROXY = "15:20_bar_close_proxy"
PROXY_TIME = "15:20:00"
PROXY_TIMEZONE = "Asia/Seoul"
SESSION_STRIDE = 2
RESEARCH_SPLIT_LABEL = "RESEARCH_ONLY_HISTORICAL_SECONDARY"
PARTITION_LABEL = "historical_secondary_only"
OBSERVATION_CUTOFFS: tuple[str, ...] = ("D-1", "D-2")
MISSING_ENTRY_POLICY = "NO_FILL"
FRESH_OOS_ACCESS_ALLOWED = False
OFFICIAL_CLOSE = False
FRESH_OOS_START_DATE = "2026-08-03"
FRESH_OOS_END_DATE = "2027-07-30"
REWARD_QUANTUM = Decimal("0.000000000001")


def _canonical_value(value: Any) -> Any:
    """Return a JSON-compatible value, rejecting lossy or non-finite inputs."""
    if is_dataclass(value) and not isinstance(value, type):
        return _canonical_value(asdict(value))
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("canonical JSON object keys must be strings")
        return {key: _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("canonical JSON does not permit non-finite Decimal values")
        return format(value, "f")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical JSON does not permit non-finite float values")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"canonical JSON does not support {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize supported data deterministically as UTF-8 JSON bytes."""
    return json.dumps(
        _canonical_value(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_canonical(value: Any) -> str:
    """Return the lower-case SHA-256 digest of :func:`canonical_json_bytes`."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


@dataclass(frozen=True)
class Type1Contract:
    """Validated, immutable Type 1 v1 experiment schema."""

    features: tuple[str, ...] = FEATURES
    seeds: tuple[int, ...] = SEEDS
    primary_cost_bp: int = PRIMARY_COST_BP
    cost_scenarios_bp: tuple[int, ...] = COST_SCENARIOS_BP
    initial_nav_krw: int = INITIAL_NAV_KRW
    slot_notional_krw: int = SLOT_NOTIONAL_KRW
    max_slots: int = MAX_SLOTS
    stable_slots: int = STABLE_SLOTS
    execution_proxy: str = EXECUTION_PROXY
    proxy_time: str = PROXY_TIME
    proxy_timezone: str = PROXY_TIMEZONE
    session_stride: int = SESSION_STRIDE
    split_label: str = RESEARCH_SPLIT_LABEL
    partition_label: str = PARTITION_LABEL
    observation_cutoffs: tuple[str, ...] = OBSERVATION_CUTOFFS
    missing_entry_policy: str = MISSING_ENTRY_POLICY
    fresh_oos_access_allowed: bool = FRESH_OOS_ACCESS_ALLOWED
    official_close: bool = OFFICIAL_CLOSE

    def __post_init__(self) -> None:
        integer_fields = (
            ("primary_cost_bp", self.primary_cost_bp, PRIMARY_COST_BP),
            ("initial_nav_krw", self.initial_nav_krw, INITIAL_NAV_KRW),
            ("slot_notional_krw", self.slot_notional_krw, SLOT_NOTIONAL_KRW),
            ("max_slots", self.max_slots, MAX_SLOTS),
            ("stable_slots", self.stable_slots, STABLE_SLOTS),
            ("session_stride", self.session_stride, SESSION_STRIDE),
        )
        if (
            not isinstance(self.features, tuple)
            or not all(isinstance(feature, str) for feature in self.features)
            or self.features != FEATURES
        ):
            raise ValueError("features must equal the frozen Type 1 D-1 feature schema")
        if (
            not isinstance(self.seeds, tuple)
            or not all(type(seed) is int for seed in self.seeds)
            or self.seeds != SEEDS
        ):
            raise ValueError("seeds must equal (0, 1, 2, 3, 4)")
        if (
            not isinstance(self.cost_scenarios_bp, tuple)
            or not all(type(cost) is int for cost in self.cost_scenarios_bp)
            or self.cost_scenarios_bp != COST_SCENARIOS_BP
        ):
            raise ValueError("cost_scenarios_bp must equal (0, 23, 46)")
        for field, value, expected in integer_fields:
            if type(value) is not int or value != expected:
                raise ValueError(f"{field} must be {expected}")
        if self.execution_proxy != EXECUTION_PROXY:
            raise ValueError("execution_proxy must be 15:20_bar_close_proxy")
        if self.proxy_time != PROXY_TIME or self.proxy_timezone != PROXY_TIMEZONE:
            raise ValueError("proxy timestamp must be 15:20:00 Asia/Seoul")
        if self.split_label != RESEARCH_SPLIT_LABEL or self.partition_label != PARTITION_LABEL:
            raise ValueError("split must be research-only historical-secondary, never fresh OOS")
        if self.observation_cutoffs != OBSERVATION_CUTOFFS:
            raise ValueError("observation_cutoffs must equal ('D-1', 'D-2')")
        if self.missing_entry_policy != MISSING_ENTRY_POLICY:
            raise ValueError("missing_entry_policy must be NO_FILL")
        if self.fresh_oos_access_allowed is not False or self.official_close is not False:
            raise ValueError("Type 1 is exact-15:20 research-only and cannot access fresh OOS")

    def to_dict(self) -> dict[str, Any]:
        """Return the schema as a plain, canonical-JSON-compatible mapping."""
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Type1Contract":
        """Construct only when the complete mapping matches the frozen schema."""
        if not isinstance(value, Mapping):
            raise ValueError("Type1Contract mapping must be a mapping")
        expected = set(cls().__dict__)
        if set(value) != expected:
            raise ValueError("Type1Contract mapping has missing or unknown fields")
        normalized = dict(value)
        for field in ("features", "seeds", "cost_scenarios_bp", "observation_cutoffs"):
            if isinstance(normalized[field], list):
                normalized[field] = tuple(normalized[field])
        try:
            return cls(**normalized)
        except TypeError as exc:
            raise ValueError("Type1Contract mapping is malformed") from exc
