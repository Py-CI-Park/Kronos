"""Q1/Q2 foundation runner and stable JSON receipt writer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from stom_rl.rl_discovery.storage import JsonValue

from .data import DataAuditReceipt, DataCustodyEvidence, audit_data_readiness, load_price_series
from .signal_floor import SignalFloorReceipt, SignalFloorThresholds, build_momentum_samples, evaluate_signal_floor
from .synthetic_gate import SyntheticGateReceipt, evaluate_synthetic_environment


@dataclass(frozen=True, slots=True)
class FoundationRunConfig:
    database: Path
    codes: tuple[str, ...]
    shuffle_seeds: tuple[int, ...]
    lookback_days: int
    holding_days: int

    @classmethod
    def registered(cls, database: Path) -> FoundationRunConfig:
        return cls(database, ("069500", "102110", "091160", "091170"), (0, 1, 2), 20, 5)


@dataclass(frozen=True, slots=True)
class FoundationReceipt:
    lane_id: str
    overall_verdict: str
    q3_ppo_allowed: bool
    primary_cost_bps: float
    diagnostic_cost_bps: float
    data_audit: DataAuditReceipt
    signal_floor: SignalFloorReceipt
    synthetic_gate: SyntheticGateReceipt


def run_foundation(config: FoundationRunConfig) -> FoundationReceipt:
    """Execute canary diagnostics while preserving Q1 promotion locks."""
    series = load_price_series(config.database, config.codes)
    data_audit = audit_data_readiness(series, DataCustodyEvidence.unverified())
    samples = build_momentum_samples(
        series,
        lookback_days=config.lookback_days,
        holding_days=config.holding_days,
    )
    signal_floor = evaluate_signal_floor(
        samples,
        SignalFloorThresholds.registered(),
        shuffle_seeds=config.shuffle_seeds,
        evidence_scope="DIAGNOSTIC_ONLY",
    )
    synthetic_gate = evaluate_synthetic_environment(config.shuffle_seeds)
    overall = _overall_verdict(data_audit, signal_floor, synthetic_gate)
    return FoundationReceipt(
        lane_id="ETF_STATEFUL_MDP_Q0_Q2",
        overall_verdict=overall,
        q3_ppo_allowed=overall == "READY_FOR_Q3_PREREG",
        primary_cost_bps=23.0,
        diagnostic_cost_bps=9.0,
        data_audit=data_audit,
        signal_floor=signal_floor,
        synthetic_gate=synthetic_gate,
    )


def write_foundation_receipt(receipt: FoundationReceipt, output: Path) -> None:
    """Atomically persist a stable, human-readable evidence receipt."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(_receipt_payload(receipt), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)


def _overall_verdict(
    data_audit: DataAuditReceipt,
    signal_floor: SignalFloorReceipt,
    synthetic_gate: SyntheticGateReceipt,
) -> str:
    if data_audit.verdict == "BLOCKED_DATA_CUSTODY":
        return "BLOCKED_Q1_DATA_CUSTODY"
    if data_audit.verdict != "PASS_DATA_READY":
        return "BLOCKED_Q1_DATA_INTEGRITY"
    if signal_floor.verdict != "PASS_SIGNAL_FLOOR":
        return "NO_GO_Q2A_SIGNAL_FLOOR"
    if synthetic_gate.verdict != "PASS_SYNTHETIC_STATEFUL_MDP":
        return "NO_GO_Q2B_ENVIRONMENT"
    return "READY_FOR_Q3_PREREG"


def _receipt_payload(receipt: FoundationReceipt) -> JsonValue:
    data_payload: dict[str, JsonValue] = {
        "verdict": receipt.data_audit.verdict,
        "codes": list(receipt.data_audit.codes),
        "gates": {gate.name: gate.passed for gate in receipt.data_audit.gate_results},
        "gate_evidence": {gate.name: gate.evidence for gate in receipt.data_audit.gate_results},
        "blockers": list(receipt.data_audit.blockers),
        "q3_ppo_allowed": receipt.data_audit.q3_ppo_allowed,
    }
    return {
        "lane_id": receipt.lane_id,
        "overall_verdict": receipt.overall_verdict,
        "q3_ppo_allowed": receipt.q3_ppo_allowed,
        "primary_cost_bps": receipt.primary_cost_bps,
        "diagnostic_cost_bps": receipt.diagnostic_cost_bps,
        "data_audit": data_payload,
        "signal_floor": asdict(receipt.signal_floor),
        "synthetic_gate": asdict(receipt.synthetic_gate),
    }
