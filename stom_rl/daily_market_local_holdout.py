"""Register a future local-DB holdout without reading any future market row."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .daily_market_allocation_contract import AllocationAction, allocation_action_name
from .daily_market_authority_contract import AuthorityFileIdentity
from .daily_market_authority_file_custody import read_stable_file_bytes
from .daily_market_local_db_audit import LocalDbCustodyReceipt
from .daily_market_local_db_evaluation import LocalDbEconomicGateReceipt
from .daily_market_path_custody import has_reparse_component
from .daily_market_rl_contract import DailyMarketRlContractError

_SEEDS = (0, 1, 2, 3, 4)
_ACTIONS = tuple(allocation_action_name(action) for action in AllocationAction)


@dataclass(frozen=True, slots=True)
class LocalDbHoldoutPaths:
    custody_receipt: Path
    economic_gate_receipt: Path
    allocation_receipt: Path
    output_directory: Path

    @classmethod
    def registered(cls, repository_root: Path) -> "LocalDbHoldoutPaths":
        root = repository_root.resolve()
        local = root / "webui" / "rl_runs" / "daily_market_local_db"
        return cls(
            custody_receipt=local
            / "DAILY_MARKET_LOCAL_DB_CUSTODY_2026_08_14_001"
            / "local_db_custody_receipt.json",
            economic_gate_receipt=local
            / "DAILY_MARKET_LOCAL_DB_BASELINE_2026_08_14_001"
            / "local_db_economic_gate.json",
            allocation_receipt=(
                root
                / "webui"
                / "rl_runs"
                / "daily_market_allocation"
                / "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002"
                / "validation_receipt.json"
            ),
            output_directory=local / "DAILY_MARKET_LOCAL_DB_HOLDOUT_2026_08_14_001",
        )


class LocalHoldoutPolicy(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["CQL", "NO_TRADE", "RULE", "RANDOM", "SHUFFLE"]
    policy_id: str = Field(pattern=r"^[A-Z0-9_]+$")
    seed: int | None
    implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    paired_cql_seed: int | None = None

    @model_validator(mode="after")
    def _kind_contract(self) -> Self:
        if self.kind in {"CQL", "RANDOM", "SHUFFLE"}:
            if self.seed not in _SEEDS:
                raise ValueError("seeded local holdout policy requires seed 0..4")
        elif self.seed is not None:
            raise ValueError("seedless local holdout control declared a seed")
        if (self.kind == "CQL") != (self.checkpoint_sha256 is not None):
            raise ValueError("only CQL policies bind checkpoints")
        if self.kind == "SHUFFLE":
            if self.paired_cql_seed != self.seed:
                raise ValueError("shuffle control must pair with the same CQL seed")
        elif self.paired_cql_seed is not None:
            raise ValueError("only shuffle controls declare paired CQL seeds")
        return self


class LocalDbHoldoutDescriptor(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_local_db_holdout.v1"]
    research_id: Literal["DAILY_MARKET_LOCAL_DB_HOLDOUT_2026_08_14_001"]
    state: Literal["REGISTERED_SEALED_NO_READ"]
    registered_at_utc: str
    source_git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    custody_receipt: AuthorityFileIdentity
    economic_gate_receipt: AuthorityFileIdentity
    allocation_receipt: AuthorityFileIdentity
    cutoff_date: Literal["20260814"]
    first_session_rule: Literal["FIRST_LOCAL_DB_SESSION_STRICTLY_AFTER_CUTOFF"]
    required_trading_days: Literal[60]
    price_basis: Literal["UNKNOWN_LOCAL_DB_BASIS"]
    universe_basis: Literal["CURRENT_SNAPSHOT_NOT_PIT"]
    actions: tuple[str, ...]
    base_cost_bps: Literal[23]
    stress_cost_bps: Literal[46]
    policies: tuple[LocalHoldoutPolicy, ...]
    historical_test_state: Literal["CONTAMINATED_FORBIDDEN"]
    local_holdout_features_read: Literal[False]
    local_holdout_actions_read: Literal[False]
    local_holdout_rewards_read: Literal[False]
    retuning_allowed: Literal[False]
    retry_allowed: Literal[False]
    independent_oos_claim_allowed: Literal[False]
    promotion_allowed: Literal[False]
    paper_live_allowed: Literal[False]

    @model_validator(mode="after")
    def _matrix_is_exact(self) -> Self:
        if self.actions != _ACTIONS:
            raise ValueError("local holdout action space drifted")
        by_kind: dict[str, list[LocalHoldoutPolicy]] = {}
        for policy in self.policies:
            by_kind.setdefault(policy.kind, []).append(policy)
        if {key: len(value) for key, value in by_kind.items()} != {
            "CQL": 5,
            "NO_TRADE": 1,
            "RULE": 1,
            "RANDOM": 5,
            "SHUFFLE": 5,
        }:
            raise ValueError("local holdout policy matrix is incomplete")
        for kind in ("CQL", "RANDOM", "SHUFFLE"):
            seeds = tuple(
                sorted(
                    policy.seed for policy in by_kind[kind] if policy.seed is not None
                )
            )
            if seeds != _SEEDS:
                raise ValueError(f"local holdout {kind} seed matrix drifted")
        return self


class LocalDbHoldoutRegistration(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos_daily_market_local_db_holdout_registration.v1"]
    descriptor_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    descriptor_size_bytes: int = Field(gt=0)
    state: Literal["REGISTERED_SEALED_NO_READ"]
    blockers: tuple[str, ...]
    accumulated_trading_days: Literal[0]
    required_trading_days: Literal[60]
    local_holdout_read: Literal[False]
    one_read_authorized: Literal[False]
    promotion_allowed: Literal[False]
    paper_live_allowed: Literal[False]


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise DailyMarketRlContractError("LOCAL_HOLDOUT_SOURCE_INVALID", label)
    return cast(Mapping[str, object], value)


def _stable_json(
    path: Path, limit: int
) -> tuple[Mapping[str, object], AuthorityFileIdentity]:
    if has_reparse_component(path) or not path.is_file():
        raise DailyMarketRlContractError("LOCAL_HOLDOUT_SOURCE_UNTRUSTED", str(path))
    raw, identity = read_stable_file_bytes(path, max_bytes=limit)
    try:
        return _mapping(cast(object, json.loads(raw)), path.name), identity
    except json.JSONDecodeError as error:
        raise DailyMarketRlContractError(
            "LOCAL_HOLDOUT_SOURCE_INVALID", path.name
        ) from error


def _implementation_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_local_holdout_descriptor(
    paths: LocalDbHoldoutPaths,
    *,
    source_git_sha: str,
    registered_at_utc: str,
) -> LocalDbHoldoutDescriptor:
    custody_raw, custody_identity = _stable_json(paths.custody_receipt, 256 * 1024)
    gate_raw, gate_identity = _stable_json(paths.economic_gate_receipt, 256 * 1024)
    allocation, allocation_identity = _stable_json(
        paths.allocation_receipt, 2 * 1024 * 1024
    )
    custody = LocalDbCustodyReceipt.model_validate(custody_raw)
    gate = LocalDbEconomicGateReceipt.model_validate(gate_raw)
    if not custody.local_research_allowed or gate.verdict != "NO_GO_LOCAL_DB_BASELINE":
        raise DailyMarketRlContractError("LOCAL_HOLDOUT_PREREQUISITE_BLOCKED")
    if (
        allocation.get("research_id") != "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002"
        or allocation.get("verdict") != "REPRODUCTION_ONLY_VALIDATION_CONSUMED"
        or tuple(cast(Sequence[str], allocation.get("action_space"))) != _ACTIONS
        or allocation.get("daily_database_sha256") != custody.daily_database.sha256
    ):
        raise DailyMarketRlContractError("LOCAL_HOLDOUT_ALLOCATION_IDENTITY_INVALID")
    cql: list[LocalHoldoutPolicy] = []
    for value in cast(Sequence[object], allocation.get("model_runs")):
        run = _mapping(value, "model_run")
        if run.get("algorithm") == "CQL":
            cql.append(
                LocalHoldoutPolicy(
                    kind="CQL",
                    policy_id=f"CQL_SEED_{run['seed']}",
                    seed=int(cast(int, run["seed"])),
                    implementation_sha256=allocation_identity.sha256,
                    checkpoint_sha256=str(run["checkpoint_sha256"]),
                )
            )
    cql.sort(key=lambda item: item.seed if item.seed is not None else -1)
    policies = (
        *cql,
        LocalHoldoutPolicy(
            kind="NO_TRADE",
            policy_id="NO_TRADE_CASH",
            seed=None,
            implementation_sha256=_implementation_hash("NO_TRADE_CASH_V1"),
        ),
        LocalHoldoutPolicy(
            kind="RULE",
            policy_id="RULE_ALWAYS_TOP5",
            seed=None,
            implementation_sha256=_implementation_hash("RULE_ALWAYS_TOP5_V1"),
        ),
        *(
            LocalHoldoutPolicy(
                kind="RANDOM",
                policy_id=f"RANDOM_SEED_{seed}",
                seed=seed,
                implementation_sha256=_implementation_hash(
                    "UNIFORM_RANDOM_FOUR_ACTIONS_V1"
                ),
            )
            for seed in _SEEDS
        ),
        *(
            LocalHoldoutPolicy(
                kind="SHUFFLE",
                policy_id=f"SHUFFLE_SEED_{seed}",
                seed=seed,
                paired_cql_seed=seed,
                implementation_sha256=_implementation_hash("PAIRED_ACTION_SHUFFLE_V1"),
            )
            for seed in _SEEDS
        ),
    )
    return LocalDbHoldoutDescriptor(
        schema_version="kronos_daily_market_local_db_holdout.v1",
        research_id="DAILY_MARKET_LOCAL_DB_HOLDOUT_2026_08_14_001",
        state="REGISTERED_SEALED_NO_READ",
        registered_at_utc=registered_at_utc,
        source_git_sha=source_git_sha,
        custody_receipt=custody_identity,
        economic_gate_receipt=gate_identity,
        allocation_receipt=allocation_identity,
        cutoff_date="20260814",
        first_session_rule="FIRST_LOCAL_DB_SESSION_STRICTLY_AFTER_CUTOFF",
        required_trading_days=60,
        price_basis="UNKNOWN_LOCAL_DB_BASIS",
        universe_basis="CURRENT_SNAPSHOT_NOT_PIT",
        actions=_ACTIONS,
        base_cost_bps=23,
        stress_cost_bps=46,
        policies=policies,
        historical_test_state="CONTAMINATED_FORBIDDEN",
        local_holdout_features_read=False,
        local_holdout_actions_read=False,
        local_holdout_rewards_read=False,
        retuning_allowed=False,
        retry_allowed=False,
        independent_oos_claim_allowed=False,
        promotion_allowed=False,
        paper_live_allowed=False,
    )


def register_local_holdout(
    descriptor: LocalDbHoldoutDescriptor, output: Path
) -> LocalDbHoldoutRegistration:
    if has_reparse_component(output) or output.exists():
        raise DailyMarketRlContractError("LOCAL_HOLDOUT_OUTPUT_UNTRUSTED")
    payload = json.dumps(
        descriptor.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    registration = LocalDbHoldoutRegistration(
        schema_version="kronos_daily_market_local_db_holdout_registration.v1",
        descriptor_sha256=hashlib.sha256(payload).hexdigest(),
        descriptor_size_bytes=len(payload),
        state="REGISTERED_SEALED_NO_READ",
        blockers=(
            "FUTURE_60_TRADING_DAY_WINDOW_NOT_ACCUMULATED",
            "RANDOM_CONTROL_NOT_EVALUATED",
            "HUMAN_ONE_READ_APPROVAL_MISSING",
            "LOCAL_DB_NOT_OFFICIAL_PIT_AUTHORITY",
        ),
        accumulated_trading_days=0,
        required_trading_days=60,
        local_holdout_read=False,
        one_read_authorized=False,
        promotion_allowed=False,
        paper_live_allowed=False,
    )
    output.mkdir(parents=True, exist_ok=False)
    for name, content in (
        ("local_holdout_descriptor.json", payload),
        (
            "local_holdout_registration.json",
            f"{registration.model_dump_json(indent=2)}\n".encode("utf-8"),
        ),
    ):
        with (output / name).open("xb") as handle:
            _ = handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    return registration


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        raise DailyMarketRlContractError("LOCAL_HOLDOUT_REQUIRES_REPOSITORY_ROOT")
    root = Path(arguments[0]).resolve()
    paths = LocalDbHoldoutPaths.registered(root)
    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    now = (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    descriptor = build_local_holdout_descriptor(
        paths, source_git_sha=git_sha, registered_at_utc=now
    )
    result = register_local_holdout(descriptor, paths.output_directory)
    print(result.model_dump_json())
    return 0


__all__ = [
    "LocalDbHoldoutDescriptor",
    "LocalDbHoldoutPaths",
    "LocalDbHoldoutRegistration",
    "LocalHoldoutPolicy",
    "build_local_holdout_descriptor",
    "register_local_holdout",
]
