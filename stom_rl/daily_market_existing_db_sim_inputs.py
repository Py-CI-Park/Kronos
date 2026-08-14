"""Fail-closed input loading for the existing-DB historical simulation."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .daily_market_allocation_q import load_allocation_q
from .daily_market_allocation_rl_contract import (
    AllocationAlgorithm,
    AllocationTrainingConfig,
)
from .daily_market_allocation_run_contract import DailyMarketAllocationPaths
from .daily_market_authority_contract import AuthorityFileIdentity
from .daily_market_authority_file_custody import read_stable_file_bytes
from .daily_market_errors import DailyMarketDataError
from .daily_market_existing_db_sim_engine import NamedModelPolicy
from .daily_market_local_db_audit import LocalDbCustodyReceipt
from .daily_market_rl_contract import DailyMarketRlContractError
from .daily_market_rl_dataset import MarketDay, TrainScoreScale, fit_train_score_scale
from .daily_market_score_dataset import load_market_score_dataset
from .daily_market_state_dataset import build_market_state_dataset
from .daily_market_transition_db import load_daily_market_candidates

RESEARCH_ID = "DAILY_MARKET_EXISTING_DB_60_SIM_2026_08_14_001"


@dataclass(frozen=True, slots=True)
class ExistingDbSimulationPaths:
    allocation: DailyMarketAllocationPaths
    allocation_receipt: Path
    custody_receipt: Path
    output_directory: Path

    @classmethod
    def registered(cls, repository_root: Path) -> "ExistingDbSimulationPaths":
        root = repository_root.resolve()
        allocation = DailyMarketAllocationPaths.registered(root)
        return cls(
            allocation=allocation,
            allocation_receipt=allocation.output_directory / "validation_receipt.json",
            custody_receipt=(
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
                / "daily_market_existing_db_sim"
                / RESEARCH_ID
            ),
        )


@dataclass(frozen=True, slots=True)
class ExistingDbSimulationInputs:
    database_identity: AuthorityFileIdentity
    database_stat: tuple[int, int]
    allocation_identity: AuthorityFileIdentity
    checkpoint_identities: tuple[AuthorityFileIdentity, ...]
    policies: tuple[NamedModelPolicy, ...]
    score_dataset_hash: str
    state_dataset_hash: str
    scale: TrainScoreScale
    days: tuple[MarketDay, ...]
    blocked_days: tuple[str, ...]


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_SOURCE_INVALID", label)
    return cast(Mapping[str, object], value)


def _stable_json(
    path: Path, max_bytes: int
) -> tuple[Mapping[str, object], AuthorityFileIdentity]:
    raw, identity = read_stable_file_bytes(path, max_bytes=max_bytes)
    try:
        return _mapping(cast(object, json.loads(raw)), path.name), identity
    except json.JSONDecodeError as error:
        raise DailyMarketRlContractError(
            "HISTORICAL_SIMULATION_SOURCE_INVALID", path.name
        ) from error


def _sha256_file(path: Path) -> str:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise DailyMarketRlContractError(
            "HISTORICAL_SIMULATION_INPUT_CHANGED", path.name
        )
    return digest.hexdigest()


def _database_identity(
    database: Path, custody_path: Path
) -> tuple[AuthorityFileIdentity, tuple[int, int]]:
    custody_raw, _ = _stable_json(custody_path, 256 * 1024)
    custody = LocalDbCustodyReceipt.model_validate(custody_raw)
    stat = database.stat()
    if (
        stat.st_size != custody.daily_database.size_bytes
        or _sha256_file(database) != custody.daily_database.sha256
    ):
        raise DailyMarketRlContractError(
            "HISTORICAL_SIMULATION_DATABASE_IDENTITY_MISMATCH"
        )
    return custody.daily_database, (stat.st_size, stat.st_mtime_ns)


def _load_window_days(
    paths: ExistingDbSimulationPaths,
) -> tuple[str, str, TrainScoreScale, tuple[MarketDay, ...], tuple[str, ...]]:
    direct = paths.allocation
    scores = load_market_score_dataset(
        direct.candidate_scores,
        source_manifest_path=direct.source_manifest,
        artifact_root=direct.dataset_root,
    )
    states = build_market_state_dataset(
        scores,
        panel_csv_path=direct.causal_panel,
        artifact_root=direct.dataset_root,
    )
    score_days = tuple(sorted(scores.days, key=lambda row: row.decision_date))[-60:]
    if (
        len(score_days) != 60
        or score_days[0].decision_date.isoformat() != "2026-03-09"
        or score_days[-1].decision_date.isoformat() != "2026-06-11"
        or Counter(day.split for day in score_days) != {"VALIDATION": 14, "TEST": 46}
    ):
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_WINDOW_DRIFTED")
    state_by_key = {(day.decision_date, day.split): day for day in states.days}
    market_days: list[MarketDay] = []
    blocked: list[str] = []
    for score_day in score_days:
        state_day = state_by_key.get(
            (score_day.decision_date.isoformat(), score_day.split)
        )
        if state_day is None:
            raise DailyMarketRlContractError("HISTORICAL_SIMULATION_STATE_MISSING")
        try:
            batch = load_daily_market_candidates(
                score_day.scores, db_path=direct.daily_database
            )
        except DailyMarketDataError as error:
            blocked.append(f"{score_day.decision_date.isoformat()}:{error}")
            continue
        if batch.split_hash != score_day.day_hash:
            raise DailyMarketRlContractError(
                "HISTORICAL_SIMULATION_SCORE_HASH_MISMATCH"
            )
        market_days.append(MarketDay(score_day, state_day, batch.candidates))
    return (
        scores.dataset_hash,
        states.state_dataset_hash,
        fit_train_score_scale(scores),
        tuple(market_days),
        tuple(blocked),
    )


def _load_cql_policies(
    paths: ExistingDbSimulationPaths,
    receipt: Mapping[str, object],
) -> tuple[tuple[NamedModelPolicy, ...], tuple[AuthorityFileIdentity, ...]]:
    runs = receipt.get("model_runs")
    if not isinstance(runs, list):
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_MODEL_MATRIX_INVALID")
    policies: list[NamedModelPolicy] = []
    identities: list[AuthorityFileIdentity] = []
    for value in cast(Sequence[object], runs):
        run = _mapping(value, "model_run")
        seed, relative, expected = (
            run.get("seed"),
            run.get("checkpoint_path"),
            run.get("checkpoint_sha256"),
        )
        if run.get("algorithm") != "CQL":
            continue
        if (
            type(seed) is not int
            or not isinstance(relative, str)
            or not isinstance(expected, str)
        ):
            raise DailyMarketRlContractError(
                "HISTORICAL_SIMULATION_MODEL_MATRIX_INVALID"
            )
        checkpoint = paths.allocation.output_directory / relative
        raw, identity = read_stable_file_bytes(checkpoint, max_bytes=64 * 1024 * 1024)
        if identity.sha256 != expected or not raw:
            raise DailyMarketRlContractError(
                "HISTORICAL_SIMULATION_CHECKPOINT_MISMATCH"
            )
        config = AllocationTrainingConfig.registered(
            algorithm=AllocationAlgorithm.CQL, seed=seed
        )
        policies.append(
            NamedModelPolicy(
                f"CQL_SEED_{seed}", seed, load_allocation_q(checkpoint, config)
            )
        )
        identities.append(identity)
    policies.sort(key=lambda policy: policy.seed)
    identities.sort(key=lambda identity: identity.path_suffix)
    if tuple(policy.seed for policy in policies) != (0, 1, 2, 3, 4):
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_MODEL_MATRIX_INVALID")
    return tuple(policies), tuple(identities)


def load_existing_db_simulation_inputs(
    paths: ExistingDbSimulationPaths,
) -> ExistingDbSimulationInputs:
    """Hash all authority inputs and read rewards only for the fixed 60-day window."""
    database_identity, database_stat = _database_identity(
        paths.allocation.daily_database, paths.custody_receipt
    )
    allocation, allocation_identity = _stable_json(
        paths.allocation_receipt, 2 * 1024 * 1024
    )
    if (
        allocation.get("research_id") != "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002"
        or allocation.get("verdict") != "REPRODUCTION_ONLY_VALIDATION_CONSUMED"
    ):
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_ALLOCATION_INVALID")
    policies, checkpoint_identities = _load_cql_policies(paths, allocation)
    score_hash, state_hash, scale, days, blocked = _load_window_days(paths)
    return ExistingDbSimulationInputs(
        database_identity,
        database_stat,
        allocation_identity,
        checkpoint_identities,
        policies,
        score_hash,
        state_hash,
        scale,
        days,
        blocked,
    )


def assert_simulation_database_unchanged(
    paths: ExistingDbSimulationPaths, expected: tuple[int, int]
) -> None:
    stat = paths.allocation.daily_database.stat()
    if expected != (stat.st_size, stat.st_mtime_ns):
        raise DailyMarketRlContractError("HISTORICAL_SIMULATION_INPUT_CHANGED")


__all__ = [
    "ExistingDbSimulationInputs",
    "ExistingDbSimulationPaths",
    "RESEARCH_ID",
    "assert_simulation_database_unchanged",
    "load_existing_db_simulation_inputs",
]
