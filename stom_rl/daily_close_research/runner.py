"""G1-G6 daily-close research runner with immutable JSON evidence."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from stom_rl.etf_research.data import load_price_series

from .contracts import (
    CloseExecutionMode,
    ExecutionAuditReceipt,
    ExecutionEvidence,
    audit_execution_readiness,
    registered_execution_contract,
)
from .costs import InstrumentKind, TradingVenue, registered_cost_contract
from .evaluation import CalibrationReceipt, run_synthetic_calibration
from .features import build_rank_samples
from .models import OfflineAlgorithm, TrainingConfig, train_offline_q
from .offline_data import synthetic_market_dataset
from .signal_floor import RankSignalReceipt, SignalFloorConfig, evaluate_rank_signal

_REGISTERED_CODES = (
    "005930", "000660", "035420", "051910", "207940",
    "006400", "068270", "035720", "105560", "055550",
    "000270", "005380", "012330", "066570", "028260",
    "032830", "086790", "003550", "096770", "034730",
)


@dataclass(frozen=True, slots=True)
class ResearchRunConfig:
    database: Path
    codes: tuple[str, ...]
    output_directory: Path
    seeds: tuple[int, ...]
    calibration_epochs: int
    execution_evidence: ExecutionEvidence

    @classmethod
    def registered(cls, database: Path, output_directory: Path) -> ResearchRunConfig:
        return cls(database, _REGISTERED_CODES, output_directory, (0, 1, 2), 120, ExecutionEvidence.unverified())


@dataclass(frozen=True, slots=True)
class ResearchReceipt:
    research_id: str
    target_model: str
    overall_verdict: str
    model_scope: str
    stock_round_trip_cost_percent: float
    execution_mode: str
    initial_nav_krw: int
    maximum_exposure_krw: int
    maximum_slots: int
    execution_audit: ExecutionAuditReceipt
    signal_floor: RankSignalReceipt
    calibration: CalibrationReceipt
    calibration_model_created: bool
    calibration_model_path: str
    economic_model_created: bool
    fresh_oos_state: str
    maturity_score: int
    next_action: str


def run_research(config: ResearchRunConfig) -> ResearchReceipt:
    costs = registered_cost_contract(InstrumentKind.STOCK, TradingVenue.KRX)
    execution = registered_execution_contract(CloseExecutionMode.POST_CLOSE_NEXT_OPEN)
    execution_audit = audit_execution_readiness(execution, config.execution_evidence)
    series = load_price_series(config.database, config.codes)
    samples = build_rank_samples(series, horizons=(5, 10, 20), holding_days=5)
    signal_floor = evaluate_rank_signal(
        samples,
        SignalFloorConfig.registered(round_trip_cost_percent=costs.round_trip_percent),
        shuffle_seeds=config.seeds,
    )
    calibration = run_synthetic_calibration(seeds=config.seeds, epochs=config.calibration_epochs)
    model_path = config.output_directory / "models" / "synthetic_cql_seed_0.pt"
    model_seed = config.seeds[0] if config.seeds else 0
    model_data = synthetic_market_dataset(seed=model_seed, episode_count=30, episode_length=20)
    train_offline_q(
        model_data,
        TrainingConfig.registered(
            algorithm=OfflineAlgorithm.CQL,
            seed=model_seed,
            epochs=config.calibration_epochs,
        ),
        output=model_path,
    )
    verdict, next_action = _verdict(execution_audit, signal_floor, calibration)
    return ResearchReceipt(
        research_id="DAILY_CLOSE_OFFLINE_RL_G1_G6_V2",
        target_model="KR_STOCK_DAILY_CLOSE_60M_10_SLOT_CONTROLLER",
        overall_verdict=verdict,
        model_scope="SYNTHETIC_CALIBRATION_ONLY",
        stock_round_trip_cost_percent=costs.round_trip_percent,
        execution_mode=execution.mode.value,
        initial_nav_krw=60_000_000,
        maximum_exposure_krw=50_000_000,
        maximum_slots=10,
        execution_audit=execution_audit,
        signal_floor=signal_floor,
        calibration=calibration,
        calibration_model_created=model_path.is_file(),
        calibration_model_path=str(model_path.resolve()),
        economic_model_created=False,
        fresh_oos_state="NOT_RUN_NO_READ",
        maturity_score=_maturity_score(execution_audit, signal_floor, calibration),
        next_action=next_action,
    )


def write_research_receipt(receipt: ResearchReceipt, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(
        json.dumps(asdict(receipt), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)


def _verdict(
    execution: ExecutionAuditReceipt,
    signal: RankSignalReceipt,
    calibration: CalibrationReceipt,
) -> tuple[str, str]:
    calibrated = calibration.verdict == "PASS_SYNTHETIC_OFFLINE_RL"
    prefix = "IMPLEMENTED_CALIBRATED" if calibrated else "IMPLEMENTED_MODEL_ARTIFACT"
    if execution.verdict != "PASS_EXECUTION_READY":
        return f"{prefix}_NO_GO_DATA_CUSTODY", "PIT universe와 available_at 증거를 등록한다"
    if signal.verdict != "PASS_SIGNAL_FLOOR":
        return f"{prefix}_NO_GO_SIGNAL_FLOOR", "새 가설을 사전등록하고 signal floor를 재실행한다"
    if not calibrated:
        return "IMPLEMENTED_NO_GO_SYNTHETIC_CALIBRATION", "CQL 보상 스케일과 환경 전이를 재검토한다"
    return "READY_FOR_MARKET_OFFLINE_MODEL_PREREG", "실제 시장 offline controller 실행을 별도 사전등록한다"


def _maturity_score(
    execution: ExecutionAuditReceipt,
    signal: RankSignalReceipt,
    calibration: CalibrationReceipt,
) -> int:
    score = 30
    if execution.verdict == "PASS_EXECUTION_READY":
        score += 15
    if signal.verdict == "PASS_SIGNAL_FLOOR":
        score += 20
    if calibration.verdict == "PASS_SYNTHETIC_OFFLINE_RL":
        score += 20
    if len(calibration.cql.per_seed_returns) >= 3:
        score += 5
    return score


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Kronos daily-close G1-G6 research")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=120)
    arguments = parser.parse_args()
    registered = ResearchRunConfig.registered(arguments.database, arguments.output_directory)
    config = ResearchRunConfig(
        registered.database,
        registered.codes,
        registered.output_directory,
        registered.seeds,
        arguments.epochs,
        registered.execution_evidence,
    )
    receipt = run_research(config)
    output = config.output_directory / "research_receipt.json"
    write_research_receipt(receipt, output)
    print(json.dumps(asdict(receipt), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

