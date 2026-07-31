"""Stable metadata registry for RL discovery dashboard artifacts."""

from __future__ import annotations

from stom_rl.rl_discovery.storage import JsonValue

TRAIN_COST_TYPES = frozenset(
    {
        "rl_discovery_d5",
        "rl_discovery_d5r",
        "rl_discovery_d5s",
        "rl_discovery_d6",
        "rl_discovery_d6r",
        "rl_discovery_d6r2",
    }
)
CUSTODIED_PREREG_TYPES = frozenset(
    {
        "rl_discovery_d5r",
        "rl_discovery_d5s",
        "rl_discovery_d6",
        "rl_discovery_d6r",
        "rl_discovery_d6r2",
    }
)

_SCHEMAS = {
    "rl_discovery_d2": "kronos.rl-discovery.d2.result.v1",
    "rl_discovery_d3": "kronos.rl-discovery.d3.result.v1",
    "rl_discovery_d4": "kronos.rl-discovery.d4.result.v1",
    "rl_discovery_d5": "kronos.rl-discovery.d5.result.v1",
    "rl_discovery_d5r": "kronos.rl-discovery.d5r.capacity.v1",
    "rl_discovery_d5s": "kronos.rl-discovery.d5s.stability.v1",
    "rl_discovery_d6": "kronos.rl-discovery.d6.validation.v1",
    "rl_discovery_d6r": "kronos.rl-discovery.d6r.falsification.v1",
    "rl_discovery_d6r2": "kronos.rl-discovery.d6r2.falsification.v1",
}

_OUTCOMES = {
    "rl_discovery_d4": "D4_TRAIN_ONLY_CONFIRMED",
    "rl_discovery_d5": "D5_TRAIN_ONLY_EVALUATED",
    "rl_discovery_d5r": "D5R_CAPACITY_EVALUATED",
    "rl_discovery_d5s": "D5S_STABILITY_EVALUATED",
}


def expected_discovery_schema(artifact_type: str) -> str | None:
    return _SCHEMAS.get(artifact_type)


def discovery_type1_outcome(
    artifact_type: str,
    payload: dict[str, JsonValue],
) -> str:
    if artifact_type in {"rl_discovery_d6", "rl_discovery_d6r", "rl_discovery_d6r2"}:
        return str(payload.get("verdict", "COMPLETE_NO_GO"))
    return _OUTCOMES.get(artifact_type, "COMPLETE_NO_GO")
