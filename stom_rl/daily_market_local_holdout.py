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
from typing import cast

from .daily_market_authority_contract import AuthorityFileIdentity
from .daily_market_authority_file_custody import read_stable_file_bytes
from .daily_market_local_db_audit import LocalDbCustodyReceipt
from .daily_market_local_db_evaluation import LocalDbEconomicGateReceipt
from .daily_market_local_holdout_contract import (
    LOCAL_HOLDOUT_ACTIONS,
    LOCAL_HOLDOUT_SEEDS,
    LocalDbHoldoutDescriptor,
    LocalDbHoldoutRegistration,
    LocalHoldoutPolicy,
)
from .daily_market_path_custody import has_reparse_component
from .daily_market_rl_contract import DailyMarketRlContractError


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
            allocation_receipt=root
            / "webui"
            / "rl_runs"
            / "daily_market_allocation"
            / "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002"
            / "validation_receipt.json",
            output_directory=local / "DAILY_MARKET_LOCAL_DB_HOLDOUT_2026_08_14_001",
        )


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


def _control_policies() -> tuple[LocalHoldoutPolicy, ...]:
    return (
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
            for seed in LOCAL_HOLDOUT_SEEDS
        ),
        *(
            LocalHoldoutPolicy(
                kind="SHUFFLE",
                policy_id=f"SHUFFLE_SEED_{seed}",
                seed=seed,
                paired_cql_seed=seed,
                implementation_sha256=_implementation_hash("PAIRED_ACTION_SHUFFLE_V1"),
            )
            for seed in LOCAL_HOLDOUT_SEEDS
        ),
    )


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
    action_space = allocation.get("action_space")
    model_runs = allocation.get("model_runs")
    if (
        allocation.get("research_id") != "DAILY_MARKET_ALLOCATION_SCREEN_2026_08_10_002"
        or allocation.get("verdict") != "REPRODUCTION_ONLY_VALIDATION_CONSUMED"
        or not isinstance(action_space, list)
        or allocation.get("daily_database_sha256") != custody.daily_database.sha256
        or not isinstance(model_runs, list)
    ):
        raise DailyMarketRlContractError("LOCAL_HOLDOUT_ALLOCATION_IDENTITY_INVALID")
    action_values = cast(Sequence[object], action_space)
    model_values = cast(Sequence[object], model_runs)
    if tuple(str(value) for value in action_values) != LOCAL_HOLDOUT_ACTIONS:
        raise DailyMarketRlContractError("LOCAL_HOLDOUT_ALLOCATION_IDENTITY_INVALID")
    cql: list[LocalHoldoutPolicy] = []
    for value in model_values:
        run = _mapping(value, "model_run")
        seed, checkpoint = run.get("seed"), run.get("checkpoint_sha256")
        if (
            run.get("algorithm") == "CQL"
            and type(seed) is int
            and isinstance(checkpoint, str)
        ):
            cql.append(
                LocalHoldoutPolicy(
                    kind="CQL",
                    policy_id=f"CQL_SEED_{seed}",
                    seed=seed,
                    implementation_sha256=allocation_identity.sha256,
                    checkpoint_sha256=checkpoint,
                )
            )
    cql.sort(key=lambda item: item.seed if item.seed is not None else -1)
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
        actions=LOCAL_HOLDOUT_ACTIONS,
        base_cost_bps=23,
        stress_cost_bps=46,
        policies=(*cql, *_control_policies()),
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
    files = (
        ("local_holdout_descriptor.json", payload),
        (
            "local_holdout_registration.json",
            f"{registration.model_dump_json(indent=2)}\n".encode("utf-8"),
        ),
    )
    for name, content in files:
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


if __name__ == "__main__":
    raise SystemExit(main())
