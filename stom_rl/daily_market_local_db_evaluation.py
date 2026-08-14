"""Re-adjudicate existing local-DB evidence without reopening market rows."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal, cast

from pydantic import BaseModel, ConfigDict

from .daily_market_authority_contract import AuthorityFileIdentity
from .daily_market_authority_file_custody import read_stable_file_bytes
from .daily_market_local_db_audit import LocalDbCustodyReceipt
from .daily_market_path_custody import has_reparse_component
from .daily_market_rl_contract import DailyMarketRlContractError

_REQUIRED_ALGORITHMS = ("DQN", "CQL", "CQL_REWARD_SHUFFLED", "CQL_ACTION_SHUFFLED")
_REQUIRED_SEEDS = (0, 1, 2, 3, 4)
_REQUIRED_CONTROLS = ("NO_TRADE", "COST_AWARE_MOMENTUM_RULE")


@dataclass(frozen=True, slots=True)
class LocalDbEvaluationPaths:
    source_experiment_receipt: Path
    source_custody_receipt: Path
    output_directory: Path

    @classmethod
    def registered(cls, repository_root: Path) -> "LocalDbEvaluationPaths":
        root = repository_root.resolve()
        return cls(
            source_experiment_receipt=(
                root
                / "webui"
                / "rl_runs"
                / "daily_market_offline_rl"
                / "DAILY_MARKET_CQL_2026_08_09_001"
                / "experiment_receipt.json"
            ),
            source_custody_receipt=(
                root
                / "webui"
                / "rl_runs"
                / "daily_market_local_db"
                / "DAILY_MARKET_LOCAL_DB_CUSTODY_2026_08_14_001"
                / "local_db_custody_receipt.json"
            ),
            output_directory=(
                root
                / "webui"
                / "rl_runs"
                / "daily_market_local_db"
                / "DAILY_MARKET_LOCAL_DB_BASELINE_2026_08_14_001"
            ),
        )


class LocalDbEconomicGateReceipt(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_local_db_economic_gate.v1"]
    research_id: Literal["DAILY_MARKET_LOCAL_DB_BASELINE_2026_08_14_001"]
    verdict: Literal["NO_GO_LOCAL_DB_BASELINE"]
    status: Literal["COMPLETE_LOCAL_RESEARCH_ONLY"]
    source_experiment: AuthorityFileIdentity
    source_custody: AuthorityFileIdentity
    source_research_id: Literal["DAILY_MARKET_CQL_2026_08_09_001"]
    source_verdict: Literal["NO_GO_HISTORICAL_ECONOMIC_GATE"]
    model_seed_matrix: dict[str, tuple[int, ...]]
    base_cost_bps: Literal[23]
    stress_cost_bps: Literal[46]
    controls_observed: tuple[str, ...]
    controls_required_next: tuple[str, ...]
    failed_checks: tuple[str, ...]
    best_control_return_percent: float
    cql_base_median_return_percent: float
    cql_stress_median_return_percent: float
    random_control_evaluated: Literal[False]
    historical_test_state: Literal["CONTAMINATED_LOCAL_RESEARCH_ONLY"]
    fresh_holdout_state: Literal["NOT_RUN_NO_READ"]
    retuning_allowed: Literal[False]
    independent_oos_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    paper_live_allowed: Literal[False]


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise DailyMarketRlContractError("LOCAL_DB_EVIDENCE_SHAPE_INVALID", label)
    return cast(Mapping[str, object], value)


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise DailyMarketRlContractError("LOCAL_DB_EVIDENCE_SHAPE_INVALID", label)
    return cast(Sequence[object], value)


def _identity(path: Path, *, max_bytes: int) -> tuple[bytes, AuthorityFileIdentity]:
    if has_reparse_component(path) or not path.is_file():
        raise DailyMarketRlContractError("LOCAL_DB_EVIDENCE_UNTRUSTED", str(path))
    return read_stable_file_bytes(path, max_bytes=max_bytes)


def _number(source: Mapping[str, object], key: str) -> float:
    value = source.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DailyMarketRlContractError("LOCAL_DB_EVIDENCE_NUMBER_INVALID", key)
    return float(value)


def evaluate_local_db_baseline(
    paths: LocalDbEvaluationPaths,
) -> LocalDbEconomicGateReceipt:
    """Validate the frozen historical receipt; do not read DB rows or retune."""
    experiment_raw, experiment_identity = _identity(
        paths.source_experiment_receipt, max_bytes=4 * 1024 * 1024
    )
    custody_raw, custody_identity = _identity(
        paths.source_custody_receipt, max_bytes=256 * 1024
    )
    try:
        source = _mapping(cast(object, json.loads(experiment_raw)), "experiment")
        custody = LocalDbCustodyReceipt.model_validate_json(custody_raw)
    except (json.JSONDecodeError, ValueError) as error:
        raise DailyMarketRlContractError("LOCAL_DB_EVIDENCE_INVALID") from error
    if not custody.local_research_allowed or not custody.quality.quality_passed:
        raise DailyMarketRlContractError("LOCAL_DB_CUSTODY_QUALITY_BLOCKED")
    if (
        source.get("schema_version") != "kronos_daily_market_offline_rl_experiment.v1"
        or source.get("research_id") != "DAILY_MARKET_CQL_2026_08_09_001"
        or source.get("verdict") != "NO_GO_HISTORICAL_ECONOMIC_GATE"
    ):
        raise DailyMarketRlContractError("LOCAL_DB_SOURCE_VERDICT_INVALID")
    matrix: dict[str, tuple[int, ...]] = {}
    observed_costs: set[float] = set()
    for item in _sequence(source.get("model_runs"), "model_runs"):
        run = _mapping(item, "model_run")
        algorithm, seed = run.get("algorithm"), run.get("seed")
        if isinstance(algorithm, str) and isinstance(seed, int):
            _ = matrix.setdefault(algorithm, ())
            matrix[algorithm] = (*matrix[algorithm], seed)
        for scenario in ("historical_test_base", "historical_test_stress"):
            result = _mapping(run.get(scenario), scenario)
            cost = result.get("round_trip_cost_percent")
            if isinstance(cost, (int, float)):
                observed_costs.add(float(cost))
    canonical_matrix = {
        algorithm: tuple(sorted(matrix.get(algorithm, ())))
        for algorithm in _REQUIRED_ALGORITHMS
    }
    if any(seeds != _REQUIRED_SEEDS for seeds in canonical_matrix.values()):
        raise DailyMarketRlContractError("LOCAL_DB_MODEL_SEED_MATRIX_INVALID")
    if observed_costs != {0.23, 0.46}:
        raise DailyMarketRlContractError("LOCAL_DB_COST_SCENARIOS_INVALID")
    controls = tuple(
        sorted(
            {
                str(_mapping(item, "control").get("policy"))
                for item in _sequence(
                    source.get("controls_historical_test_base"), "controls"
                )
            }
        )
    )
    if any(control not in controls for control in _REQUIRED_CONTROLS):
        raise DailyMarketRlContractError("LOCAL_DB_REQUIRED_CONTROL_MISSING")
    gate = _mapping(source.get("economic_gate"), "economic_gate")
    failed = tuple(
        str(value) for value in _sequence(gate.get("failed_checks"), "failed_checks")
    )
    blockers = (
        *failed,
        "RANDOM_POLICY_CONTROL_NOT_EVALUATED",
        "HISTORICAL_TEST_CONTAMINATED",
    )
    return LocalDbEconomicGateReceipt(
        schema_version="kronos_daily_market_local_db_economic_gate.v1",
        research_id="DAILY_MARKET_LOCAL_DB_BASELINE_2026_08_14_001",
        verdict="NO_GO_LOCAL_DB_BASELINE",
        status="COMPLETE_LOCAL_RESEARCH_ONLY",
        source_experiment=experiment_identity,
        source_custody=custody_identity,
        source_research_id="DAILY_MARKET_CQL_2026_08_09_001",
        source_verdict="NO_GO_HISTORICAL_ECONOMIC_GATE",
        model_seed_matrix=canonical_matrix,
        base_cost_bps=23,
        stress_cost_bps=46,
        controls_observed=controls,
        controls_required_next=(
            "NO_TRADE",
            "RULE",
            "RANDOM_SEEDS_0_TO_4",
            "SHUFFLE_SEEDS_0_TO_4",
        ),
        failed_checks=blockers,
        best_control_return_percent=_number(gate, "best_control_return_percent"),
        cql_base_median_return_percent=_number(gate, "cql_base_median_return_percent"),
        cql_stress_median_return_percent=_number(
            gate, "cql_stress_median_return_percent"
        ),
        random_control_evaluated=False,
        historical_test_state="CONTAMINATED_LOCAL_RESEARCH_ONLY",
        fresh_holdout_state="NOT_RUN_NO_READ",
        retuning_allowed=False,
        independent_oos_claim_allowed=False,
        promotion_allowed=False,
        paper_live_allowed=False,
    )


def write_local_db_evaluation(
    receipt: LocalDbEconomicGateReceipt, output: Path
) -> Path:
    if has_reparse_component(output) or output.exists():
        raise DailyMarketRlContractError("LOCAL_DB_EVALUATION_OUTPUT_UNTRUSTED")
    output.mkdir(parents=True, exist_ok=False)
    path = output / "local_db_economic_gate.json"
    with path.open("x", encoding="utf-8", newline="") as handle:
        _ = handle.write(f"{receipt.model_dump_json(indent=2)}\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        raise DailyMarketRlContractError("LOCAL_DB_EVALUATION_REQUIRES_REPOSITORY_ROOT")
    paths = LocalDbEvaluationPaths.registered(Path(arguments[0]))
    receipt = evaluate_local_db_baseline(paths)
    _ = write_local_db_evaluation(receipt, paths.output_directory)
    print(json.dumps(receipt.model_dump(mode="json"), ensure_ascii=False))
    return 0


__all__ = [
    "LocalDbEconomicGateReceipt",
    "LocalDbEvaluationPaths",
    "evaluate_local_db_baseline",
    "write_local_db_evaluation",
]


if __name__ == "__main__":
    raise SystemExit(main())
