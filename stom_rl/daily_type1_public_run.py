"""Frozen G002 public-only Type 1 MaskablePPO orchestration.

This module deliberately has no fresh-OOS reader and never imports a combined V6
CSV.  Market-data construction and fixed-notional replay are supplied by the
public market boundary in :mod:`stom_rl.daily_type1_market` or explicitly
injected for deterministic tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

import numpy as np

from stom_rl.daily_type1_contract import FEATURES, INITIAL_NAV_KRW, SEEDS, SLOT_NOTIONAL_KRW, STABLE_SLOTS, canonical_json_bytes, sha256_canonical

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "docs" / "kronos_type1_g002_public_protocol_2026-07-23.json"
PUBLIC_TRAIN_START = "2018-01-02"
PUBLIC_TRAIN_END = "2023-12-29"
REUSED_VALIDATION_START = "2024-01-02"
REUSED_VALIDATION_END = "2025-06-30"
TIMESTEPS_PER_SEED = 200_000
FINAL_MODEL_ONLY = "FINAL_MODEL_ONLY"
FALSE_RESEARCH_LOCKS = {
    "promotion_allowed": False,
    "model_build_allowed": False,
    "paper_forward_allowed": False,
    "live_broker_order_allowed": False,
    "profitability_claim_allowed": False,
    "go_summary_allowed": False,
}


class PublicRunOperations(Protocol):
    """Narrow, injectable boundary for materialization, PPO, and replay."""

    def build_pairs(self, rows: Sequence[Mapping[str, Any]], *, split: str, shuffled_seed: int | None = None) -> Sequence[Mapping[str, Any]]: ...
    def train(self, pairs: Sequence[Mapping[str, Any]], *, seed: int, timesteps: int) -> tuple[Any, Any]: ...
    def save_final(self, model: Any, normalizer: Any, path: Path) -> Mapping[str, str]: ...
    def evaluate(self, model: Any, pairs: Sequence[Mapping[str, Any]], *, seed: int) -> Mapping[str, Any]: ...
    def controls(self, train_rows: Sequence[Mapping[str, Any]], validation_rows: Sequence[Mapping[str, Any]], primary: Mapping[str, Any], shuffled: Mapping[str, Any]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class RunConfig:
    """Non-negotiable G002 training budget; no smoke or seed override exists."""

    seeds: tuple[int, ...] = SEEDS
    timesteps_per_seed: int = TIMESTEPS_PER_SEED
    device: str = "cpu"
    final_artifact: str = FINAL_MODEL_ONLY

    def __post_init__(self) -> None:
        if self.seeds != SEEDS or self.timesteps_per_seed != TIMESTEPS_PER_SEED:
            raise ValueError("G002 requires seeds 0..4 and exactly 200000 timesteps per member")
        if self.device != "cpu" or self.final_artifact != FINAL_MODEL_ONLY:
            raise ValueError("G002 requires CPU and final-model-only artifacts")


def _iso_date(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO-8601 date")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 date") from exc


def _row_date(row: Mapping[str, Any]) -> str:
    for key in ("decision_date", "session_date", "date", "session"):
        if key in row:
            return _iso_date(row[key], key)
    raise ValueError("public row is missing a session date")


def reject_nonpublic_path(path: str | Path) -> Path:
    """Reject paths whose identity signals a combined, test, sealed, or fresh input."""
    candidate = Path(path)
    lowered = "/".join(candidate.parts).lower()
    forbidden = ("fresh", "test", "oos", "sealed", "combined", "dataset_full")
    if any(token in lowered for token in forbidden):
        raise ValueError("fresh/test/combined dataset paths are forbidden for G002 public training")
    return candidate


def split_public_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    """Fail closed unless every row is exclusively train or reused validation."""
    train: list[Mapping[str, Any]] = []
    validation: list[Mapping[str, Any]] = []
    forbidden_fields = {"fresh_oos", "test", "test_metrics", "fresh_oos_metrics", "oos"}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("public rows must be mappings")
        lowered_keys = {str(key).lower() for key in row}
        if lowered_keys & forbidden_fields or any(
            token in key for key in lowered_keys for token in ("fresh", "test", "oos", "sealed")
        ):
            raise ValueError("fresh/test fields are forbidden in public rows")
        for key in ("split", "partition", "partition_label"):
            value = row.get(key)
            if value is not None and any(word in str(value).lower() for word in ("test", "fresh", "oos", "sealed")):
                raise ValueError("fresh/test partition is forbidden")
        session = _row_date(row)
        if PUBLIC_TRAIN_START <= session <= PUBLIC_TRAIN_END:
            train.append(row)
        elif REUSED_VALIDATION_START <= session <= REUSED_VALIDATION_END:
            validation.append(row)
        else:
            raise ValueError("row date is outside the G002 public train/reused-validation boundary")
    if not train or not validation:
        raise ValueError("public materialization requires non-empty train and reused-validation rows")
    return tuple(train), tuple(validation)


def materialize_public_rows(loader: Callable[..., Sequence[Mapping[str, Any]]], *, daily_db_path: str | Path, fivemin_db_path: str | Path) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    """Request exact-15:20 features only through the public bounded loader."""
    reject_nonpublic_path(daily_db_path)
    reject_nonpublic_path(fivemin_db_path)
    rows = loader(
        daily_db_path=Path(daily_db_path),
        fivemin_db_path=Path(fivemin_db_path),
        start_date=PUBLIC_TRAIN_START,
        end_date=REUSED_VALIDATION_END,
    )
    return split_public_rows(rows)


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _dataset_symbols(rows_path: Path, manifest_path: Path, universe_manifest_path: Path) -> tuple[str, ...]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise ValueError("dataset manifest must be a JSON object")
    if manifest.get("schema_version") != "kronos_type1_g002_public_data.v1":
        raise ValueError("dataset manifest schema is not the frozen G002 public schema")
    if manifest.get("dataset_id") != "type1-close-20260803-001":
        raise ValueError("dataset manifest identity is not the frozen Type1 identity")
    if manifest.get("output_sha256") != _file_hash(rows_path):
        raise ValueError("public rows hash differs from the dataset manifest")
    if manifest.get("fresh_oos") != {"state": "NOT_RUN", "read_performed": False}:
        raise ValueError("dataset manifest does not prove untouched fresh OOS")
    universe = manifest.get("universe")
    if not isinstance(universe, Mapping):
        raise ValueError("dataset manifest lacks its universe binding")
    symbols = universe.get("symbols")
    if symbols is None:
        if universe.get("manifest_sha256") != _file_hash(universe_manifest_path):
            raise ValueError("universe manifest hash differs from the dataset binding")
        universe_manifest = json.loads(universe_manifest_path.read_text(encoding="utf-8"))
        entries = universe_manifest.get("universe") if isinstance(universe_manifest, Mapping) else None
        if not isinstance(entries, list):
            raise ValueError("universe manifest is malformed")
        symbols = [entry.get("code") for entry in entries if isinstance(entry, Mapping)]
    if (
        not isinstance(symbols, list)
        or len(symbols) != STABLE_SLOTS
        or len(set(symbols)) != STABLE_SLOTS
        or any(not isinstance(symbol, str) or len(symbol) != 6 or not symbol.isdigit() for symbol in symbols)
    ):
        raise ValueError("dataset manifest must bind exactly 500 stable six-digit symbols")
    return tuple(symbols)



def _protocol() -> Mapping[str, Any]:
    value = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if value.get("protocol_id") != "KRONOS-TYPE1-G002-PUBLIC-2026-07-23":
        raise ValueError("unexpected G002 protocol")
    return value


def _member(operations: PublicRunOperations, pairs: Sequence[Mapping[str, Any]], validation_pairs: Sequence[Mapping[str, Any]], *, seed: int, root: Path, kind: str) -> dict[str, Any]:
    model, normalizer = operations.train(pairs, seed=seed, timesteps=TIMESTEPS_PER_SEED)
    destination = root / kind / f"seed_{seed}"
    destination.mkdir(parents=True, exist_ok=False)
    artifacts = dict(operations.save_final(model, normalizer, destination))
    if set(artifacts) != {"model_sha256", "normalizer_sha256"}:
        raise ValueError("final artifact receipt must contain model_sha256 and normalizer_sha256 only")
    metrics = dict(operations.evaluate(model, validation_pairs, seed=seed))
    actual_timesteps = getattr(model, "num_timesteps", TIMESTEPS_PER_SEED)
    return {
        "seed": seed,
        "timesteps": TIMESTEPS_PER_SEED,
        "actual_sb3_timesteps": actual_timesteps,
        "device": "cpu",
        "artifact": FINAL_MODEL_ONLY,
        "artifacts": artifacts,
        "validation": metrics,
    }


def _iqm(members: Mapping[str, Mapping[str, Any]]) -> Any:
    values = []
    for seed in SEEDS:
        metrics = members[str(seed)]["validation"]
        if "nav_krw" not in metrics:
            raise ValueError("deterministic validation metrics must include nav_krw")
        values.append(metrics["nav_krw"])
    ordered = sorted(values)
    if all(isinstance(value, Decimal) for value in ordered):
        return Decimal("0.3") * ordered[1] + Decimal("0.4") * ordered[2] + Decimal("0.3") * ordered[3]
    return 0.3 * ordered[1] + 0.4 * ordered[2] + 0.3 * ordered[3]


def run_public_experiment(rows: Sequence[Mapping[str, Any]], *, out_root: str | Path, run_id: str, operations: PublicRunOperations, config: RunConfig = RunConfig()) -> dict[str, Any]:
    """Run the mandatory five primary and five shuffled public-only members."""
    if not run_id or Path(run_id).name != run_id:
        raise ValueError("run_id must be one non-empty path component")
    train_rows, validation_rows = split_public_rows(rows)
    root = Path(out_root) / run_id
    root.mkdir(parents=True, exist_ok=False)
    protocol = _protocol()
    train_pairs = operations.build_pairs(train_rows, split="train")
    validation_pairs = operations.build_pairs(validation_rows, split="reused_validation")
    if not train_pairs or not validation_pairs:
        raise ValueError("public pair construction produced an empty split")
    primary: dict[str, dict[str, Any]] = {}
    shuffled: dict[str, dict[str, Any]] = {}
    for seed in config.seeds:
        primary[str(seed)] = _member(operations, train_pairs, validation_pairs, seed=seed, root=root, kind="primary")
        shuffled_pairs = operations.build_pairs(train_rows, split="train", shuffled_seed=seed)
        shuffled[str(seed)] = _member(operations, shuffled_pairs, validation_pairs, seed=seed, root=root, kind="shuffled_reward")
    controls = dict(operations.controls(train_rows, validation_rows, primary, shuffled))
    timestep_mismatches = [
        f"{kind}_seed_{seed}_timestep_mismatch"
        for kind, members in (("primary", primary), ("shuffled_reward", shuffled))
        for seed in config.seeds
        if members[str(seed)]["actual_sb3_timesteps"] != TIMESTEPS_PER_SEED
    ]
    if timestep_mismatches:
        controls["integrity_ok"] = False
        controls["integrity_reasons"] = list(controls.get("integrity_reasons", ())) + timestep_mismatches
    execution_status = "BLOCK" if controls.get("integrity_ok") is False else "COMPLETE"
    manifest = {
        "schema_version": "kronos_type1_g002_public_run.v1",
        "protocol": {"id": protocol["protocol_id"], "sha256": _file_hash(PROTOCOL_PATH)},
        "features": list(FEATURES),
        "public_splits": {
            "train": {
                "frozen_start": PUBLIC_TRAIN_START,
                "frozen_end": PUBLIC_TRAIN_END,
                "actual_start": min(_row_date(row) for row in train_rows),
                "actual_end": max(_row_date(row) for row in train_rows),
            },
            "reused_validation": {
                "frozen_start": REUSED_VALIDATION_START,
                "frozen_end": REUSED_VALIDATION_END,
                "actual_start": min(_row_date(row) for row in validation_rows),
                "actual_end": max(_row_date(row) for row in validation_rows),
            },
        },
        "training": {"seeds": list(config.seeds), "timesteps_per_seed": config.timesteps_per_seed, "device": "cpu", "validation_visible_to_training": False, "eval_callback": False, "early_stopping": False, "best_model_selection": False, "checkpoint_selection": False, "member_selection": False, "saved_artifact": FINAL_MODEL_ONLY, "synthetic_oracle_calibration": False},
        "members": {"primary": primary, "shuffled_reward": shuffled},
        "aggregation": {"metric": "FIVE_SEED_IQM", "primary_nav_krw": _iqm(primary), "shuffled_nav_krw": _iqm(shuffled)},
        "controls": controls,
        "fresh_oos": {"state": "NOT_RUN", "metrics": None},
        "false_research_locks": FALSE_RESEARCH_LOCKS,
        "execution_status": execution_status,
        "verdict": "NO_GO",
    }
    receipt = {"manifest_sha256": sha256_canonical(manifest), "execution_status": execution_status, "verdict": "NO_GO", "fresh_oos": {"state": "NOT_RUN", "metrics": None}}
    (root / "run_manifest.json").write_bytes(canonical_json_bytes(manifest))
    (root / "receipt.json").write_bytes(canonical_json_bytes(receipt))
    return {"output_dir": root, "manifest": manifest, "receipt": receipt}


class _ProductionOperations:
    """The sole production bridge from canonical public rows to Type1ClosingEnv."""

    def __init__(self, *, stable_symbols: Sequence[str] | None = None) -> None:
        self._normalizer: Any | None = None
        self._stable_symbols = tuple(stable_symbols) if stable_symbols is not None else None

    def build_pairs(self, rows: Sequence[Mapping[str, Any]], *, split: str, shuffled_seed: int | None = None) -> Sequence[Mapping[str, Any]]:
        from stom_rl.daily_type1_market import (
            TrainOnlyNormalizer,
            public_row_from_mapping,
            shuffled_returns,
            validate_public_rows,
        )

        parsed = validate_public_rows(
            tuple(
                public_row_from_mapping({
                    key: value
                    for key, value in row.items()
                    if key not in {"split", "partition", "partition_label"}
                })
                for row in rows
            ),
            split=split,
        )
        if split == "train":
            self._normalizer = TrainOnlyNormalizer.fit(parsed)
        if self._normalizer is None:
            raise ValueError("validation pairs require the train-only normalizer")
        symbols = self._stable_symbols or tuple(sorted({row.symbol for row in parsed}))
        if len(symbols) != STABLE_SLOTS or len(set(symbols)) != STABLE_SLOTS:
            raise ValueError("public Type1 rows must bind exactly 500 stable six-digit symbols")
        if any(not isinstance(symbol, str) or len(symbol) != 6 or not symbol.isdigit() for symbol in symbols):
            raise ValueError("stable symbols must be six-digit strings")
        by_date: dict[date, dict[str, Any]] = {}
        for row in parsed:
            by_date.setdefault(row.decision_date, {})[row.symbol] = row
        sessions = tuple(sorted(by_date))
        if len(sessions) < 2:
            raise ValueError("public split requires at least two sessions")
        pair_sessions = tuple(
            (sessions[index], sessions[index + 1])
            for index in range(0, len(sessions) - 1, 2)
        )
        pair_keys = tuple(
            (decision, settlement, symbol)
            for decision, settlement in pair_sessions
            for symbol in symbols
        )
        returns = [
            by_date[decision].get(symbol).gross_return
            if symbol in by_date[decision] and symbol in by_date[settlement]
            else None
            for decision, settlement, symbol in pair_keys
        ]
        if shuffled_seed is not None:
            returns = list(shuffled_returns(returns, seed=shuffled_seed))
        return_values = {
            (decision, symbol): value
            for (decision, _, symbol), value in zip(pair_keys, returns, strict=True)
        }
        pairs: list[dict[str, Any]] = []
        for decision, settlement in pair_sessions:
            selected = by_date[decision]
            values, missing, availability, gross = [], [], [], []
            for symbol in symbols:
                row = selected.get(symbol)
                if row is None:
                    values.append((0.0,) * len(FEATURES))
                    missing.append((1,) * len(FEATURES))
                    availability.append(0)
                    gross.append(None)
                    continue
                transformed, absent = self._normalizer.transform(row.features)
                values.append(transformed)
                missing.append(absent)
                availability.append(int(row.entry_available))
                gross.append(return_values[(decision, symbol)])
            pairs.append({
                "decision_date": decision.isoformat(),
                "settlement_date": settlement.isoformat(),
                "observation_cutoff_d1": (decision - timedelta(days=1)).isoformat(),
                "observation_cutoff_d2": (decision - timedelta(days=2)).isoformat(),
                "split_label": "RESEARCH_ONLY_HISTORICAL_SECONDARY",
                "partition_label": "historical_secondary_only",
                "fresh_oos_access_allowed": False,
                "execution_proxy": "15:20_bar_close_proxy",
                "proxy_time": "15:20:00",
                "proxy_timezone": "Asia/Seoul",
                "official_close": False,
                "missing_entry_policy": "NO_FILL",
                "candidate_values": np.asarray(values, dtype=np.float32),
                "candidate_missing": np.asarray(missing, dtype=np.int8),
                "availability_mask": np.asarray(availability, dtype=np.int8),
                "symbols": symbols,
                "gross_returns": tuple(gross),
                "entry_available": np.asarray(availability, dtype=np.int8),
                "post_decision_fill_available": np.asarray([int(value is not None) for value in gross], dtype=np.int8),
            })
        if not pairs:
            raise ValueError("odd public session tail is dropped and must leave at least one chronological pair")
        return tuple(pairs)

    def train(self, pairs: Sequence[Mapping[str, Any]], *, seed: int, timesteps: int) -> tuple[Any, Any]:
        from stom_rl.daily_type1_train import TrainingConfig, train_model
        return train_model(pairs, TrainingConfig(seed=seed), timesteps=timesteps)

    def save_final(self, model: Any, normalizer: Any, path: Path) -> Mapping[str, str]:
        model_path = path / "final_model"
        normalizer_path = path / "normalizer.pkl"
        model.save(str(model_path))
        normalizer.save(str(normalizer_path))
        saved_model = model_path.with_suffix(".zip")
        return {"model_sha256": _file_hash(saved_model), "normalizer_sha256": _file_hash(normalizer_path)}

    def evaluate(self, model: Any, pairs: Sequence[Mapping[str, Any]], *, seed: int) -> Mapping[str, Any]:
        from stom_rl.daily_type1_env import Type1ClosingEnv

        env = Type1ClosingEnv(pairs)
        observation, _ = env.reset(seed=seed)
        blocks, selections, outcomes = 0, [], []
        while True:
            action, _ = model.predict(observation, deterministic=True, action_masks=env.action_masks())
            observation, _, terminated, truncated, info = env.step(int(np.asarray(action).item()))
            blocks += int(info["status"] == "BLOCK")
            if info["status"] == "SETTLED":
                settled = info["settlement"].outcomes
                selections.append([item.symbol for item in settled])
                outcomes.append([{"symbol": item.symbol, "status": item.status, "gross_return": item.gross_return} for item in settled])
            if terminated or truncated:
                break
        nav = INITIAL_NAV_KRW + sum((self._pnl(pair) for pair in outcomes), Decimal(0))
        return {"nav_krw": nav, "deterministic": True, "block_count": blocks, "selections": selections, "outcomes": outcomes}

    @staticmethod
    def _outcomes(pair: Mapping[str, Any], selected: Sequence[str]) -> list[dict[str, Any]]:
        positions = {symbol: index for index, symbol in enumerate(pair["symbols"])}
        return [
            {"symbol": symbol, "status": "FILLED" if pair["post_decision_fill_available"][positions[symbol]] else "NO_FILL",
             "gross_return": pair["gross_returns"][positions[symbol]]}
            for symbol in selected
        ]

    @staticmethod
    def _pnl(outcomes: Sequence[Mapping[str, Any]]) -> Decimal:
        return sum((SLOT_NOTIONAL_KRW * (Decimal(item["gross_return"]) - Decimal("0.0023"))
                    for item in outcomes if item["status"] == "FILLED"), Decimal(0))

    def controls(self, train_rows: Sequence[Mapping[str, Any]], validation_rows: Sequence[Mapping[str, Any]], primary: Mapping[str, Any], shuffled: Mapping[str, Any]) -> Mapping[str, Any]:
        """Run all frozen controls; integrity defects BLOCK while science never promotes."""
        from stom_rl.daily_type1_market import (
            RidgeBaseline, bootstrap_confidence_interval, circular_moving_block_bootstrap,
            exposure_matched_random, five_seed_iqm, random_baseline, replay_fixed_notional,
            select_top_positive, stop_baseline,
        )
        from stom_rl.daily_type1_accounting import SlotOutcome

        train_pairs = self.build_pairs(train_rows, split="train")
        normalizer_before = self._normalizer.digest()
        validation_pairs = self.build_pairs(validation_rows, split="reused_validation")
        normalizer_after = self._normalizer.digest()
        samples = [
            (pair["candidate_values"][slot], pair["candidate_missing"][slot], pair["gross_returns"][slot])
            for pair in train_pairs for slot in range(len(pair["symbols"]))
            if pair["entry_available"][slot] and pair["gross_returns"][slot] is not None
        ]
        ridge = RidgeBaseline.fit(samples)
        available = [tuple(symbol for symbol, enabled in zip(pair["symbols"], pair["availability_mask"], strict=True) if enabled) for pair in validation_pairs]
        ridge_selection = [
            select_top_positive({symbol: ridge.predict(pair["candidate_values"][slot], pair["candidate_missing"][slot])
                                 for slot, symbol in enumerate(pair["symbols"]) if pair["availability_mask"][slot]})
            for pair in validation_pairs
        ]
        ridge_pnl = [self._pnl(self._outcomes(pair, selected)) for pair, selected in zip(validation_pairs, ridge_selection, strict=True)]
        random_members = random_baseline(available, replications=10_000, seed=0)
        random_pnl = [[self._pnl(self._outcomes(pair, selected)) for pair, selected in zip(validation_pairs, selection, strict=True)] for selection in random_members]
        random_expected = [sum((member[index] for member in random_pnl), Decimal(0)) / Decimal(10_000) for index in range(len(validation_pairs))]

        def matched(members: Mapping[str, Any], above: bool) -> dict[str, Any]:
            counts = [[len(members[str(seed)]["validation"]["selections"][index]) for index in range(len(validation_pairs))] for seed in SEEDS]
            draws = [exposure_matched_random(available, value, replications=10_000, seed=0) for value in counts]
            navs = []
            for replication in range(10_000):
                values = [
                    INITIAL_NAV_KRW + sum((self._pnl(self._outcomes(pair, selected)) for pair, selected in zip(validation_pairs, draws[offset][replication], strict=True)), Decimal(0))
                    for offset in range(len(SEEDS))
                ]
                navs.append(five_seed_iqm(values))
            actual = five_seed_iqm([Decimal(str(members[str(seed)]["validation"]["nav_krw"])) for seed in SEEDS])
            p95 = sorted(navs)[9499]
            return {"actual_iqm_nav_krw": actual, "matched_p95_nav_krw": p95, "gate_pass": actual > p95 if above else actual <= p95, "selected_counts_by_seed": counts}

        primary_match, shuffled_match = matched(primary, True), matched(shuffled, False)
        reasons = []
        if normalizer_before != normalizer_after:
            reasons.append("reused_validation_mutated_train_normalizer")
        for name, members in (("primary", primary), ("shuffled_reward", shuffled)):
            for seed in SEEDS:
                member = members.get(str(seed), {})
                if member.get("actual_sb3_timesteps") != TIMESTEPS_PER_SEED:
                    reasons.append(f"{name}_seed_{seed}_timestep_mismatch")
                if member.get("validation", {}).get("block_count", 0) != 0:
                    reasons.append(f"{name}_seed_{seed}_evaluation_block")
                try:
                    replay = replay_fixed_notional(tuple(
                        tuple(SlotOutcome(item["symbol"], item["status"], item["gross_return"]) if item["status"] == "FILLED" else SlotOutcome(item["symbol"], item["status"])
                              for item in pair)
                        for pair in member["validation"]["outcomes"]
                    ))
                    if replay[-1] != Decimal(str(member["validation"]["nav_krw"])):
                        reasons.append(f"{name}_seed_{seed}_decimal_accounting_mismatch")
                except Exception:
                    reasons.append(f"{name}_seed_{seed}_decimal_accounting_schema")
        primary_iqm_pnl = [five_seed_iqm([self._pnl(primary[str(seed)]["validation"]["outcomes"][index]) for seed in SEEDS]) for index in range(len(validation_pairs))]
        bootstrap = {
            name: {"kind": "CIRCULAR_MOVING_BLOCK", "block_length_pairs": 20, "replications": 10_000, "seed": 0,
                   "ci_95": bootstrap_confidence_interval(circular_moving_block_bootstrap(
                       [actual - expected for actual, expected in zip(primary_iqm_pnl, baseline, strict=True)],
                       replications=10_000, block_length_pairs=20, seed=0))}
            for name, baseline in (("ridge", ridge_pnl), ("random_expected", random_expected))
        }
        science = primary_match["gate_pass"] and shuffled_match["gate_pass"]
        return {
            "integrity_ok": not reasons, "integrity_reasons": reasons,
            "stop_baseline": {"definition": "Select no symbols for every pair", "selections": stop_baseline(len(validation_pairs)), "nav_krw": INITIAL_NAV_KRW},
            "ridge_baseline": {"alpha": "1", "inputs": 14, "intercept_penalized": False, "tuning": False, "selection": "positive_top_10", "per_pair_pnl_krw": ridge_pnl},
            "random_baseline": {"replications": 10_000, "seed": 0},
            "exposure_matched_random": {"replications": 10_000, "seed": 0, "primary": primary_match, "shuffled_reward": shuffled_match},
            "moving_block_bootstrap": bootstrap,
            "shuffle_retraining": {"seeds": list(SEEDS), "timesteps_per_seed": TIMESTEPS_PER_SEED, "all_members_recorded": True},
            "mutation_invariance": {"train_only_normalizer_unchanged": normalizer_before == normalizer_after,
                                     "model_and_normalizer_hashes": {name: {str(seed): members[str(seed)]["artifacts"] for seed in SEEDS} for name, members in (("primary", primary), ("shuffled_reward", shuffled))}},
            "scientific_gates_pass": science, "scientific_gate_reasons": [] if science else ["local_control_gate_miss"],
            "train_rows": len(train_rows), "reused_validation_rows": len(validation_rows),
        }
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run frozen G002 Type 1 public-only MaskablePPO research.")
    parser.add_argument("--rows-json", required=True, help="Public-only canonical JSON row array; fresh/test paths are rejected.")
    parser.add_argument("--dataset-manifest", required=True, help="Frozen public-only dataset manifest binding all 500 stable symbols.")
    parser.add_argument("--universe-manifest", required=True, help="Checked universe manifest whose SHA is bound by the dataset manifest.")
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--run-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows_path = reject_nonpublic_path(args.rows_json)
    manifest_path = reject_nonpublic_path(args.dataset_manifest)
    universe_manifest_path = reject_nonpublic_path(args.universe_manifest)
    rows = json.loads(rows_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("--rows-json must contain a JSON array")
    stable_symbols = _dataset_symbols(rows_path, manifest_path, universe_manifest_path)
    result = run_public_experiment(
        rows,
        out_root=args.out_root,
        run_id=args.run_id,
        operations=_ProductionOperations(stable_symbols=stable_symbols),
        config=RunConfig(),
    )
    print(json.dumps({"output_dir": str(result["output_dir"]), "execution_status": result["manifest"]["execution_status"], "verdict": "NO_GO"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
