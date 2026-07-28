"""Stage-aware synthetic runner state for the immutable daily Portfolio SB3 protocol.

The protocol module remains the authority for matrix identity and stop-code order.
This module only records deterministic runner state, resume decisions, and read
capability guardrails for synthetic verification.  It does not import SB3, train,
or read market/OOS data.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
import json
import math
import re
from typing import Any, Final, Protocol

from stom_rl import daily_portfolio_sb3_protocol as protocol_contract


RUNNER_STATE_SCHEMA: Final = "kronos_daily_sb3_runner_state.v1"
RUNNER_CELL_STATE_SCHEMA: Final = "kronos_daily_sb3_runner_cell_state.v1"
RUNNER_TERMINAL_ARTIFACT_SCHEMA: Final = "kronos_daily_sb3_runner_terminal_artifact.v1"
RESUME_SNAPSHOT_SCHEMA: Final = "kronos_daily_sb3_resume_snapshot.v1"
PARTITION_READ_RECEIPT_SCHEMA: Final = "kronos_daily_sb3_partition_read_receipt.v1"
CHECKPOINT_INTERVAL_STEPS: Final = 10_240
MAX_SYNTHETIC_STEPS_PER_CELL: Final = 16

SNAPSHOT_MAPPING_SECTIONS: Final = (
    "model",
    "optimizer",
    "scheduler",
    "python_rng",
    "numpy_rng",
    "torch_rng",
    "env",
    "normalization",
    "rollout",
    "callback",
    "eval",
    "deps",
    "device",
    "config",
    "protocol",
)
SNAPSHOT_REQUIRED_KEYS: Final = frozenset(("schema", "event_seq", *SNAPSHOT_MAPPING_SECTIONS))
STOP_PREDICATE_CODES: Final = tuple(str(rule["code"]) for rule in protocol_contract.STOP_RULES)
TERMINAL_STATUSES: Final = frozenset({"STOPPED", "FAILED", "COMPLETED"})
NON_EXACT_RESUME_REASON_CODES: Final = frozenset(
    {
        "CONFIG_MISMATCH",
        "CUDA_SNAPSHOT",
        "EVENT_SEQ_MISMATCH",
        "MIDROLLOUT_SNAPSHOT",
        "MISSING_RESUME_SECTION",
        "PROTOCOL_MISMATCH",
        "SNAPSHOT_MISMATCH",
    }
)
NEW_ATTEMPT_SOURCE_PHASES: Final = frozenset({"CELL_RUNNING", "CELL_CHECKPOINTED"})
SAFE_UNPROTECTED_PARTITIONS: Final = frozenset({"train", "validation"})
CAPABILITY_PROTECTED_PARTITIONS: Final = frozenset({"historical_secondary_only"})
_PARTITION_ALIAS_TOKENS: Final = frozenset({"test", "test_oos", "official", "official_test_oos", "oos"})
FRESH_OOS_PARTITIONS: Final = frozenset({"fresh_oos", "fresh_test_oos", "live_oos"})
_D1_AUTHORIZED: Final = frozenset({"VERIFIED", "OFFICIAL_OR_MANUAL_REVIEWED"})
_SHA_RE: Final = re.compile(r"^[0-9a-f]{64}$")


class DailyPortfolioSb3StateError(ValueError):
    """Raised when runner state would violate the frozen protocol contract."""


class ResumeSnapshotError(DailyPortfolioSb3StateError):
    """Raised for malformed exact-resume snapshots."""


class AuthorityGateError(DailyPortfolioSb3StateError):
    """Raised before any protected test/OOS read is allowed."""


class CapabilityConsumptionStore(Protocol):
    """Durable one-use capability store.  Production implementations must be atomic."""

    def consume_if_absent(self, capability_sha256: str, nonce_sha256: str) -> bool: ...


@dataclass(frozen=True)
class InMemoryCapabilityConsumptionStore:
    """Small deterministic store for tests; not a production durability boundary."""

    consumed: frozenset[tuple[str, str]] = frozenset()

    def consume_if_absent(self, capability_sha256: str, nonce_sha256: str) -> bool:
        key = (capability_sha256, nonce_sha256)
        if key in self.consumed:
            return False
        object.__setattr__(self, "consumed", self.consumed | {key})
        return True


@dataclass(frozen=True)
class ArtifactRecord:
    payload: Mapping[str, Any]
    raw: bytes
    ref: Mapping[str, Any]


@dataclass(frozen=True)
class ResumeDecision:
    exact: bool
    action: str
    reason_code: str
    previous_sha256: str | None
    candidate_sha256: str | None
    new_attempt_required: bool


@dataclass(frozen=True)
class ResumeSnapshot:
    model: Mapping[str, Any]
    optimizer: Mapping[str, Any]
    scheduler: Mapping[str, Any]
    python_rng: Mapping[str, Any]
    numpy_rng: Mapping[str, Any]
    torch_rng: Mapping[str, Any]
    env: Mapping[str, Any]
    normalization: Mapping[str, Any]
    rollout: Mapping[str, Any]
    callback: Mapping[str, Any]
    eval: Mapping[str, Any]
    deps: Mapping[str, Any]
    device: Mapping[str, Any]
    config: Mapping[str, Any]
    protocol: Mapping[str, Any]
    event_seq: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ResumeSnapshot":
        if not isinstance(value, Mapping):
            raise ResumeSnapshotError("resume snapshot must be a mapping")
        if set(value) != SNAPSHOT_REQUIRED_KEYS:
            missing = sorted(SNAPSHOT_REQUIRED_KEYS - set(value))
            extra = sorted(set(value) - SNAPSHOT_REQUIRED_KEYS)
            raise ResumeSnapshotError(f"resume snapshot sections mismatch missing={missing} extra={extra}")
        if value["schema"] != RESUME_SNAPSHOT_SCHEMA:
            raise ResumeSnapshotError("resume snapshot schema mismatch")
        event_seq = value["event_seq"]
        if not isinstance(event_seq, int) or isinstance(event_seq, bool) or event_seq < 0:
            raise ResumeSnapshotError("resume snapshot event_seq must be a non-negative integer")
        sections: dict[str, Mapping[str, Any]] = {}
        for name in SNAPSHOT_MAPPING_SECTIONS:
            section = value[name]
            if not isinstance(section, Mapping):
                raise ResumeSnapshotError(f"resume snapshot section {name} must be a mapping")
            sections[name] = _canonical_clone(section)
        _validate_resume_snapshot_semantics(sections)
        return cls(event_seq=event_seq, **sections)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": RESUME_SNAPSHOT_SCHEMA,
            "model": _canonical_clone(self.model),
            "optimizer": _canonical_clone(self.optimizer),
            "scheduler": _canonical_clone(self.scheduler),
            "python_rng": _canonical_clone(self.python_rng),
            "numpy_rng": _canonical_clone(self.numpy_rng),
            "torch_rng": _canonical_clone(self.torch_rng),
            "env": _canonical_clone(self.env),
            "normalization": _canonical_clone(self.normalization),
            "rollout": _canonical_clone(self.rollout),
            "callback": _canonical_clone(self.callback),
            "eval": _canonical_clone(self.eval),
            "deps": _canonical_clone(self.deps),
            "device": _canonical_clone(self.device),
            "config": _canonical_clone(self.config),
            "protocol": _canonical_clone(self.protocol),
            "event_seq": self.event_seq,
        }

    def fingerprint(self) -> str:
        return protocol_contract.sha256_hex(self.to_mapping())

    def protocol_sha256(self) -> str | None:
        if isinstance(self.protocol.get("protocol_sha256"), str):
            return str(self.protocol["protocol_sha256"])
        identity = self.protocol.get("identity")
        if isinstance(identity, Mapping) and isinstance(identity.get("protocol_sha256"), str):
            return str(identity["protocol_sha256"])
        return None

    def device_kind(self) -> str:
        for key in ("kind", "type", "device", "torch_device"):
            value = self.device.get(key)
            if isinstance(value, str) and value.strip():
                return value.lower()
        return ""

    def is_cpu_snapshot(self) -> bool:
        kind = self.device_kind()
        return kind == "cpu" or kind.startswith("cpu:")

    def is_midrollout(self) -> bool:
        if self.rollout.get("midrollout") is True:
            return True
        for key in ("buffer_position", "pending_steps", "partial_rollout_steps"):
            value = self.rollout.get(key, 0)
            if value not in (0, None, False):
                return True
        return False


@dataclass(frozen=True)
class DailySb3CellState:
    schema: str
    ordinal: int
    cell_uid: str
    attempt_uid: str
    attempt_number: int
    seed_id: str
    fold_id: str
    variant_id: str
    phase: str
    status: str
    step: int
    next_checkpoint_step: int
    event_seq: int
    checkpoint_refs: tuple[Mapping[str, Any], ...]
    terminal_artifact_ref: Mapping[str, Any] | None = None

    @classmethod
    def from_protocol_cell(cls, cell: Mapping[str, Any]) -> "DailySb3CellState":
        return cls(
            schema=RUNNER_CELL_STATE_SCHEMA,
            ordinal=_positive_int(cell.get("ordinal"), "cell ordinal"),
            cell_uid=_required_text(cell.get("cell_uid"), "cell_uid"),
            attempt_uid=_required_text(cell.get("attempt_uid"), "attempt_uid"),
            attempt_number=1,
            seed_id=_required_text(cell.get("seed_id"), "seed_id"),
            fold_id=_required_text(cell.get("fold_id"), "fold_id"),
            variant_id=_required_text(cell.get("variant_id"), "variant_id"),
            phase="PENDING",
            status="PENDING",
            step=0,
            next_checkpoint_step=CHECKPOINT_INTERVAL_STEPS,
            event_seq=0,
            checkpoint_refs=(),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "ordinal": self.ordinal,
            "cell_uid": self.cell_uid,
            "attempt_uid": self.attempt_uid,
            "attempt_number": self.attempt_number,
            "seed_id": self.seed_id,
            "fold_id": self.fold_id,
            "variant_id": self.variant_id,
            "phase": self.phase,
            "status": self.status,
            "step": self.step,
            "next_checkpoint_step": self.next_checkpoint_step,
            "event_seq": self.event_seq,
            "checkpoint_refs": [_canonical_clone(ref) for ref in self.checkpoint_refs],
            "terminal_artifact_ref": None if self.terminal_artifact_ref is None else _canonical_clone(self.terminal_artifact_ref),
        }


@dataclass(frozen=True)
class DailySb3RunState:
    schema: str
    run_uid: str
    protocol_uid: str
    protocol_sha256: str
    phase: str
    status: str
    event_seq: int
    cells: tuple[DailySb3CellState, ...]
    terminal_artifact_ref: Mapping[str, Any] | None = None
    terminal_status: str | None = None
    stop_codes: tuple[str, ...] = ()

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "run_uid": self.run_uid,
            "protocol_uid": self.protocol_uid,
            "protocol_sha256": self.protocol_sha256,
            "phase": self.phase,
            "status": self.status,
            "event_seq": self.event_seq,
            "cells": [cell.to_mapping() for cell in self.cells],
            "terminal_artifact_ref": None if self.terminal_artifact_ref is None else _canonical_clone(self.terminal_artifact_ref),
            "terminal_status": self.terminal_status,
            "stop_codes": list(self.stop_codes),
        }

    def matrix_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(cell.status for cell in self.cells).items()))

    def cell_by_uid(self, cell_uid: str) -> DailySb3CellState:
        for cell in self.cells:
            if cell.cell_uid == cell_uid:
                return cell
        raise DailyPortfolioSb3StateError(f"unknown cell_uid: {cell_uid}")


@dataclass(frozen=True)
class TerminalTransition:
    state: DailySb3RunState
    artifact: ArtifactRecord


def _canonical_clone(value: Any) -> Any:
    return json.loads(protocol_contract.canonical_bytes(value).decode("utf-8"))


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DailyPortfolioSb3StateError(f"{label} must be a non-empty string")
    return value


def _positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise DailyPortfolioSb3StateError(f"{label} must be a positive integer")
    return value


def _nonnegative_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DailyPortfolioSb3StateError(f"{label} must be a non-negative integer")
    return value


def _validate_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise DailyPortfolioSb3StateError(f"{label} must be a lower-case SHA-256 digest")
    return value


def _object_ref_for_payload(payload: Mapping[str, Any], *, uri: str, schema: str) -> ArtifactRecord:
    raw = protocol_contract.canonical_bytes(payload)
    ref = {"uri": uri, "sha256": protocol_contract.sha256_hex(raw), "byte_length": len(raw), "schema": schema}
    return ArtifactRecord(payload=_canonical_clone(payload), raw=raw, ref=ref)


def validate_object_ref(ref: Mapping[str, Any], label: str = "object ref") -> Mapping[str, Any]:
    if not isinstance(ref, Mapping) or set(ref) != {"uri", "sha256", "byte_length", "schema"}:
        raise DailyPortfolioSb3StateError(f"{label} has invalid shape")
    if not isinstance(ref["uri"], str) or not ref["uri"]:
        raise DailyPortfolioSb3StateError(f"{label}.uri must be a non-empty string")
    _validate_sha(ref["sha256"], f"{label}.sha256")
    if not isinstance(ref["byte_length"], int) or isinstance(ref["byte_length"], bool) or ref["byte_length"] < 0:
        raise DailyPortfolioSb3StateError(f"{label}.byte_length must be a non-negative integer")
    if not isinstance(ref["schema"], str) or not ref["schema"]:
        raise DailyPortfolioSb3StateError(f"{label}.schema must be a non-empty string")
    return _canonical_clone(ref)


def build_initial_state(protocol_value: Mapping[str, Any] | None = None) -> DailySb3RunState:
    value = protocol_contract.build_protocol() if protocol_value is None else _canonical_clone(protocol_value)
    protocol_contract.validate_protocol(value)
    identity = value["identity"]
    cells = tuple(DailySb3CellState.from_protocol_cell(cell) for cell in value["matrix"]["cells"])
    if len(cells) != 50:
        raise DailyPortfolioSb3StateError("runner state requires the authoritative 50-cell matrix")
    return DailySb3RunState(
        schema=RUNNER_STATE_SCHEMA,
        run_uid=derive_run_uid(identity["protocol_sha256"]),
        protocol_uid=identity["protocol_uid"],
        protocol_sha256=identity["protocol_sha256"],
        phase="MATRIX_READY",
        status="PENDING",
        event_seq=0,
        cells=cells,
    )


def derive_run_uid(protocol_sha256: str) -> str:
    digest = protocol_contract.sha256_hex(
        {
            "schema": "kronos_daily_sb3_runner_identity_basis.v1",
            "protocol_sha256": _validate_sha(protocol_sha256, "protocol_sha256"),
            "compute_mode": protocol_contract.SYNTHETIC_COMPUTE_MODE,
        }
    )
    return f"kdp1-run-{digest[:32]}"


def derive_attempt_uid(protocol_sha256: str, cell_uid: str, attempt_number: int) -> str:
    _validate_sha(protocol_sha256, "protocol_sha256")
    _required_text(cell_uid, "cell_uid")
    _positive_int(attempt_number, "attempt_number")
    canonical = protocol_contract.build_protocol()
    if canonical["identity"]["protocol_sha256"] == protocol_sha256:
        for cell in canonical["matrix"]["cells"]:
            if cell["cell_uid"] == cell_uid and attempt_number == 1:
                return str(cell["attempt_uid"])
    digest = protocol_contract.sha256_hex(
        {
            "schema": "kronos_daily_sb3_runner_attempt_identity_basis.v1",
            "protocol_sha256": protocol_sha256,
            "cell_uid": cell_uid,
            "attempt_number": attempt_number,
            "compute_mode": protocol_contract.SYNTHETIC_COMPUTE_MODE,
        }
    )
    return f"kdp1-attempt-{digest[:32]}"


def checkpoint_due(step: int) -> bool:
    _nonnegative_int(step, "step")
    return step > 0 and step % CHECKPOINT_INTERVAL_STEPS == 0


def snapshot_artifact(snapshot: ResumeSnapshot | Mapping[str, Any], *, uri: str) -> ArtifactRecord:
    value = snapshot if isinstance(snapshot, ResumeSnapshot) else ResumeSnapshot.from_mapping(snapshot)
    return _object_ref_for_payload(value.to_mapping(), uri=uri, schema=RESUME_SNAPSHOT_SCHEMA)


def decide_resume(
    previous: ResumeSnapshot | Mapping[str, Any] | None,
    candidate: ResumeSnapshot | Mapping[str, Any] | None,
    *,
    expected_protocol_sha256: str | None = None,
    expected_event_seq: int | None = None,
    expected_config: Mapping[str, Any] | None = None,
) -> ResumeDecision:
    previous_snapshot = _coerce_snapshot_or_none(previous)
    candidate_snapshot = _coerce_snapshot_or_none(candidate)
    previous_sha = previous_snapshot.fingerprint() if previous_snapshot is not None else None
    candidate_sha = candidate_snapshot.fingerprint() if candidate_snapshot is not None else None
    if previous_snapshot is None or candidate_snapshot is None:
        return _restart_decision("MISSING_RESUME_SECTION", previous_sha, candidate_sha)
    if not candidate_snapshot.is_cpu_snapshot():
        return _restart_decision("CUDA_SNAPSHOT", previous_sha, candidate_sha)
    if candidate_snapshot.is_midrollout():
        return _restart_decision("MIDROLLOUT_SNAPSHOT", previous_sha, candidate_sha)
    if expected_protocol_sha256 is not None and candidate_snapshot.protocol_sha256() != expected_protocol_sha256:
        return _restart_decision("PROTOCOL_MISMATCH", previous_sha, candidate_sha)
    if expected_event_seq is not None and candidate_snapshot.event_seq != expected_event_seq:
        return _restart_decision("EVENT_SEQ_MISMATCH", previous_sha, candidate_sha)
    if expected_config is not None and candidate_snapshot.config != _canonical_clone(expected_config):
        return _restart_decision("CONFIG_MISMATCH", previous_sha, candidate_sha)
    if previous_sha != candidate_sha:
        return _restart_decision("SNAPSHOT_MISMATCH", previous_sha, candidate_sha)
    return ResumeDecision(
        exact=True,
        action="RESUME_EXACT",
        reason_code="EXACT_CPU_SNAPSHOT",
        previous_sha256=previous_sha,
        candidate_sha256=candidate_sha,
        new_attempt_required=False,
    )


def _coerce_snapshot_or_none(value: ResumeSnapshot | Mapping[str, Any] | None) -> ResumeSnapshot | None:
    if value is None:
        return None
    if isinstance(value, ResumeSnapshot):
        return value
    try:
        return ResumeSnapshot.from_mapping(value)
    except (ResumeSnapshotError, protocol_contract.DailySb3ProtocolError, TypeError, ValueError):
        return None


def _restart_decision(reason_code: str, previous_sha: str | None, candidate_sha: str | None) -> ResumeDecision:
    return ResumeDecision(
        exact=False,
        action="RESTART_NEW_ATTEMPT",
        reason_code=reason_code,
        previous_sha256=previous_sha,
        candidate_sha256=candidate_sha,
        new_attempt_required=True,
    )


def start_cell(state: DailySb3RunState, cell_uid: str) -> DailySb3RunState:
    _assert_not_terminal(state)
    if any(cell.status == "RUNNING" for cell in state.cells):
        raise DailyPortfolioSb3StateError("another cell is already running")
    cell = state.cell_by_uid(cell_uid)
    if cell.status != "PENDING":
        raise DailyPortfolioSb3StateError("cell can only start from PENDING")
    updated = replace(cell, phase="CELL_RUNNING", status="RUNNING", event_seq=cell.event_seq + 1)
    return _replace_cell(state, updated, phase="CELL_RUNNING", status="RUNNING")


def record_checkpoint(state: DailySb3RunState, cell_uid: str, *, step: int, snapshot_ref: Mapping[str, Any]) -> DailySb3RunState:
    _assert_not_terminal(state)
    cell = state.cell_by_uid(cell_uid)
    if cell.status != "RUNNING":
        raise DailyPortfolioSb3StateError("checkpoint requires a running cell")
    if step != cell.next_checkpoint_step or not checkpoint_due(step):
        raise DailyPortfolioSb3StateError("checkpoint step must be the next 10240-step boundary")
    ref = validate_object_ref(snapshot_ref, "snapshot_ref")
    updated = replace(
        cell,
        phase="CELL_CHECKPOINTED",
        step=step,
        next_checkpoint_step=step + CHECKPOINT_INTERVAL_STEPS,
        event_seq=cell.event_seq + 1,
        checkpoint_refs=(*cell.checkpoint_refs, ref),
    )
    return _replace_cell(state, updated, phase="CELL_CHECKPOINTED", status="RUNNING")


def complete_cell(state: DailySb3RunState, cell_uid: str, *, step: int, artifact_ref: Mapping[str, Any] | None = None) -> DailySb3RunState:
    _assert_not_terminal(state)
    _nonnegative_int(step, "step")
    cell = state.cell_by_uid(cell_uid)
    if cell.status != "RUNNING":
        raise DailyPortfolioSb3StateError("cell completion requires a running cell")
    if step < cell.step:
        raise DailyPortfolioSb3StateError("cell step cannot move backwards")
    if step >= cell.next_checkpoint_step:
        raise DailyPortfolioSb3StateError("checkpoint due before cell completion")
    ref = None if artifact_ref is None else validate_object_ref(artifact_ref, "cell artifact_ref")
    updated = replace(
        cell,
        phase="CELL_COMPLETED",
        status="COMPLETED",
        step=step,
        event_seq=cell.event_seq + 1,
        terminal_artifact_ref=ref,
    )
    next_cells = _cells_with_replacement(state.cells, updated)
    phase = "MATRIX_COMPLETED" if all(item.status == "COMPLETED" for item in next_cells) else "CELL_COMPLETED"
    return replace(state, cells=next_cells, phase=phase, status="RUNNING", event_seq=state.event_seq + 1)


def start_new_attempt(
    state: DailySb3RunState,
    cell_uid: str,
    decision: ResumeDecision,
    *,
    config_overrides: Mapping[str, Any] | None = None,
) -> DailySb3RunState:
    _assert_not_terminal(state)
    _assert_restart_decision(decision)
    if config_overrides:
        raise DailyPortfolioSb3StateError("config retry is forbidden by the frozen protocol")
    cell = state.cell_by_uid(cell_uid)
    _assert_new_attempt_source(cell)
    attempt_number = cell.attempt_number + 1
    updated = replace(
        cell,
        attempt_uid=derive_attempt_uid(state.protocol_sha256, cell.cell_uid, attempt_number),
        attempt_number=attempt_number,
        phase="PENDING",
        status="PENDING",
        step=0,
        next_checkpoint_step=CHECKPOINT_INTERVAL_STEPS,
        event_seq=cell.event_seq + 1,
        checkpoint_refs=(),
        terminal_artifact_ref=None,
    )
    return _replace_cell(state, updated, phase="MATRIX_READY", status="RUNNING")


def request_config_retry(*_: Any, **__: Any) -> None:
    raise DailyPortfolioSb3StateError("config retry is forbidden by the frozen protocol")


def complete_run(state: DailySb3RunState, *, completed_at: str) -> TerminalTransition:
    if any(cell.status != "COMPLETED" for cell in state.cells):
        raise DailyPortfolioSb3StateError("run completion requires all 50 cells to be completed")
    return _terminal_transition(state, terminal_status="COMPLETED", reason_code="ALL_CELLS_COMPLETED", stop_codes=(), created_at=completed_at)


def stop_run(state: DailySb3RunState, *, stop_codes: Sequence[str], reason_code: str, stopped_at: str) -> TerminalTransition:
    codes = ordered_stop_codes(stop_codes)
    if not codes:
        raise DailyPortfolioSb3StateError("STOPPED artifact requires at least one stop code")
    return _terminal_transition(state, terminal_status="STOPPED", reason_code=reason_code, stop_codes=codes, created_at=stopped_at)


def fail_run(state: DailySb3RunState, *, reason_code: str, failed_at: str, stop_codes: Sequence[str] = ()) -> TerminalTransition:
    return _terminal_transition(state, terminal_status="FAILED", reason_code=reason_code, stop_codes=ordered_stop_codes(stop_codes), created_at=failed_at)


def ordered_stop_codes(stop_codes: Sequence[str]) -> tuple[str, ...]:
    observed = tuple(str(code) for code in stop_codes)
    if len(set(observed)) != len(observed):
        raise DailyPortfolioSb3StateError("stop codes must be unique")
    unknown = [code for code in observed if code not in STOP_PREDICATE_CODES]
    if unknown:
        raise DailyPortfolioSb3StateError(f"unknown stop codes: {unknown}")
    ordered = tuple(code for code in STOP_PREDICATE_CODES if code in set(observed))
    if observed != ordered:
        raise DailyPortfolioSb3StateError("stop codes must follow protocol STOP_RULES order")
    return ordered


def ordered_stop_codes_for_predicates(predicate_results: Mapping[str, bool]) -> tuple[str, ...]:
    if set(predicate_results) != set(STOP_PREDICATE_CODES):
        missing = sorted(set(STOP_PREDICATE_CODES) - set(predicate_results))
        extra = sorted(set(predicate_results) - set(STOP_PREDICATE_CODES))
        raise DailyPortfolioSb3StateError(f"stop predicate shape mismatch missing={missing} extra={extra}")
    if any(not isinstance(value, bool) for value in predicate_results.values()):
        raise DailyPortfolioSb3StateError("stop predicate values must be booleans")
    return tuple(code for code in STOP_PREDICATE_CODES if predicate_results[code])


def evaluate_stop_predicates(
    *,
    missing_session: bool = False,
    label_leakage_past_fit: bool = False,
    alias_variant: bool = False,
    protocol_drift: bool = False,
    noncanonical_code_or_hash: bool = False,
    fresh_oos_access_requested: bool = False,
    unsupported_compute: bool = False,
    d0_status: str = "VERIFIED",
    d1_status: str = "OFFICIAL_OR_MANUAL_REVIEWED",
    require_fresh_oos_for_claim: bool = False,
    fresh_oos_status: str = "FRESH_OOS_VERIFIED",
    metric_values: Sequence[float] = (),
    invalid_action_rate: float = 0.0,
) -> tuple[str, ...]:
    if not isinstance(invalid_action_rate, (int, float)) or isinstance(invalid_action_rate, bool):
        raise DailyPortfolioSb3StateError("invalid_action_rate must be numeric")
    predicates = {
        "MISSING_SESSION": bool(missing_session),
        "LABEL_LEAKAGE_PAST_FIT": bool(label_leakage_past_fit),
        "ALIAS_VARIANT": bool(alias_variant),
        "PROTOCOL_DRIFT": bool(protocol_drift),
        "NONCANONICAL_CODE_OR_HASH": bool(noncanonical_code_or_hash),
        "FRESH_OOS_ACCESS_REQUESTED": bool(fresh_oos_access_requested),
        "UNSUPPORTED_COMPUTE": bool(unsupported_compute),
        "D0_PRICE_BASIS_NOT_VERIFIED": d0_status != "VERIFIED",
        "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED": d1_status not in _D1_AUTHORIZED,
        "FRESH_OOS_NOT_RUN": bool(require_fresh_oos_for_claim and fresh_oos_status != "FRESH_OOS_VERIFIED"),
        "NAN_OR_INF_METRIC": any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) for value in metric_values),
        "INVALID_ACTION_RATE_ABOVE_0_05": float(invalid_action_rate) > 0.05,
    }
    return ordered_stop_codes_for_predicates(predicates)


def authorize_partition_read(
    partition: str,
    authority: Mapping[str, Any],
    store: CapabilityConsumptionStore,
    *,
    consumed_at: str,
    protocol_sha256: str | None = None,
) -> Mapping[str, Any]:
    partition_key = _normalize_partition_key(partition)
    if partition_key in SAFE_UNPROTECTED_PARTITIONS:
        return {
            "schema": PARTITION_READ_RECEIPT_SCHEMA,
            "partition": partition_key,
            "protected_read": False,
            "capability_consumed_before_read": False,
            "consumed_at": consumed_at,
        }
    if partition_key in FRESH_OOS_PARTITIONS or "fresh" in partition_key:
        raise AuthorityGateError("FRESH_OOS_ACCESS_REQUESTED")
    if partition_key != "historical_secondary_only":
        tokens = {token for token in partition_key.split("_") if token}
        if tokens & _PARTITION_ALIAS_TOKENS or "test_oos" in partition_key or "official" in partition_key or partition_key == "test":
            raise AuthorityGateError("TEST_OOS_ALIAS_DENIED")
        raise AuthorityGateError("PARTITION_READ_NOT_ALLOWLISTED")
    if partition_key not in CAPABILITY_PROTECTED_PARTITIONS:
        raise AuthorityGateError("PARTITION_READ_NOT_ALLOWLISTED")
    if not isinstance(authority, Mapping):
        raise AuthorityGateError("authority must be a mapping")
    d0_status = str(authority.get("d0_status") or "")
    d1_status = str(authority.get("d1_status") or "")
    custody_status = str(authority.get("custody_status") or "")
    if d0_status != "VERIFIED":
        raise AuthorityGateError("D0_PRICE_BASIS_NOT_VERIFIED")
    if d1_status not in _D1_AUTHORIZED:
        raise AuthorityGateError("D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED")
    if custody_status != "FRESH_OOS_NOT_RUN":
        raise AuthorityGateError("CUSTODY_STATUS_MISMATCH")
    if authority.get("historical_secondary_read_allowed") is not True:
        raise AuthorityGateError("TEST_OOS_READ_CAPABILITY_NOT_AUTHORIZED")
    capability_sha256 = _validate_sha(authority.get("capability_sha256"), "capability_sha256")
    nonce_sha256 = _validate_sha(authority.get("nonce_sha256"), "nonce_sha256")
    if not store.consume_if_absent(capability_sha256, nonce_sha256):
        raise AuthorityGateError("TEST_OOS_READ_CAPABILITY_ALREADY_CONSUMED")
    return {
        "schema": PARTITION_READ_RECEIPT_SCHEMA,
        "partition": partition_key,
        "protected_read": True,
        "d0_status": d0_status,
        "d1_status": d1_status,
        "custody_status": custody_status,
        "protocol_sha256": protocol_sha256,
        "capability_sha256": capability_sha256,
        "nonce_sha256": nonce_sha256,
        "capability_consumed_before_read": True,
        "consumed_at": consumed_at,
    }


def read_partition_after_authority(
    partition: str,
    authority: Mapping[str, Any],
    store: CapabilityConsumptionStore,
    reader: Callable[[Mapping[str, Any]], Any],
    *,
    consumed_at: str,
    protocol_sha256: str | None = None,
) -> Any:
    receipt = authorize_partition_read(partition, authority, store, consumed_at=consumed_at, protocol_sha256=protocol_sha256)
    return reader(receipt)


def _normalize_partition_key(partition: str) -> str:
    raw = _required_text(partition, "partition")
    normalized = re.sub(r"[^a-z0-9]+", "_", raw.strip().lower()).strip("_")
    if not normalized:
        raise AuthorityGateError("PARTITION_READ_NOT_ALLOWLISTED")
    return normalized


def _require_snapshot_shape(section: Mapping[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - set(section))
    if missing:
        raise ResumeSnapshotError(f"resume snapshot {label} missing required fields: {missing}")


def _require_snapshot_sha(section: Mapping[str, Any], key: str, label: str) -> None:
    try:
        _validate_sha(section.get(key), f"resume snapshot {label}.{key}")
    except DailyPortfolioSb3StateError as exc:
        raise ResumeSnapshotError(str(exc)) from exc


def _validate_resume_snapshot_semantics(sections: Mapping[str, Mapping[str, Any]]) -> None:
    _require_snapshot_shape(sections["model"], {"format", "weights_sha256"}, "model")
    _require_snapshot_sha(sections["model"], "weights_sha256", "model")
    for name in ("optimizer", "scheduler", "python_rng", "numpy_rng", "env", "normalization", "rollout", "callback", "eval", "deps"):
        _require_snapshot_shape(sections[name], {"state_sha256"}, name)
        _require_snapshot_sha(sections[name], "state_sha256", name)
    if not isinstance(sections["python_rng"].get("algorithm"), str) or not sections["python_rng"]["algorithm"]:
        raise ResumeSnapshotError("resume snapshot python_rng.algorithm must be a non-empty string")
    if not isinstance(sections["numpy_rng"].get("bit_generator"), str) or not sections["numpy_rng"]["bit_generator"]:
        raise ResumeSnapshotError("resume snapshot numpy_rng.bit_generator must be a non-empty string")
    torch_rng = sections["torch_rng"]
    if set(torch_rng) != {"cpu_state_sha256", "cuda_states"}:
        raise ResumeSnapshotError("resume snapshot torch_rng must contain only CPU state and empty CUDA states")
    _require_snapshot_sha(torch_rng, "cpu_state_sha256", "torch_rng")
    if torch_rng["cuda_states"] != []:
        raise ResumeSnapshotError("resume snapshot torch_rng cuda_states must be empty for exact CPU resume")
    deps = sections["deps"]
    if set(deps) != {"sb3_imported", "torch_version", "state_sha256"}:
        raise ResumeSnapshotError("resume snapshot deps shape is invalid")
    if deps["sb3_imported"] is not False or not isinstance(deps["torch_version"], str) or not deps["torch_version"]:
        raise ResumeSnapshotError("resume snapshot deps must prove no SB3 import and name the torch version")
    device = sections["device"]
    if set(device) != {"kind", "torch_device"} or not isinstance(device["kind"], str) or not isinstance(device["torch_device"], str):
        raise ResumeSnapshotError("resume snapshot device shape is invalid")
    config = sections["config"]
    if set(config) != {"synthetic_verification_only", "no_heavy_compute", "steps_per_cell"}:
        raise ResumeSnapshotError("resume snapshot config shape is invalid")
    if config["synthetic_verification_only"] is not True or config["no_heavy_compute"] is not True:
        raise ResumeSnapshotError("resume snapshot config must remain synthetic and no-heavy-compute")
    if not isinstance(config["steps_per_cell"], int) or isinstance(config["steps_per_cell"], bool) or not 0 <= config["steps_per_cell"] <= MAX_SYNTHETIC_STEPS_PER_CELL:
        raise ResumeSnapshotError("resume snapshot config steps_per_cell is outside the synthetic bound")
    protocol = sections["protocol"]
    if set(protocol) != {"schema", "protocol_sha256"}:
        raise ResumeSnapshotError("resume snapshot protocol shape is invalid")
    if protocol["schema"] != protocol_contract.PROTOCOL_SCHEMA:
        raise ResumeSnapshotError("resume snapshot protocol schema mismatch")
    _require_snapshot_sha(protocol, "protocol_sha256", "protocol")
    rollout = sections["rollout"]
    for key in ("midrollout", "buffer_position", "pending_steps"):
        if key not in rollout:
            raise ResumeSnapshotError(f"resume snapshot rollout.{key} is required")
    if not isinstance(rollout["midrollout"], bool):
        raise ResumeSnapshotError("resume snapshot rollout.midrollout must be a boolean")


def _assert_not_terminal(state: DailySb3RunState) -> None:
    if state.status in TERMINAL_STATUSES or state.terminal_status in TERMINAL_STATUSES:
        raise DailyPortfolioSb3StateError("terminal runner state is immutable")

def _assert_restart_decision(decision: ResumeDecision) -> None:
    if not isinstance(decision, ResumeDecision):
        raise DailyPortfolioSb3StateError("new attempt requires a validated non-exact resume decision")
    if (
        decision.exact is not False
        or decision.new_attempt_required is not True
        or decision.action != "RESTART_NEW_ATTEMPT"
    ):
        raise DailyPortfolioSb3StateError("new attempt requires a validated non-exact resume decision")
    reason_code = _required_text(decision.reason_code, "resume decision reason_code")
    if reason_code not in NON_EXACT_RESUME_REASON_CODES:
        raise DailyPortfolioSb3StateError("new attempt resume reason is not allowed")
    if decision.previous_sha256 is not None:
        _validate_sha(decision.previous_sha256, "resume decision previous_sha256")
    if decision.candidate_sha256 is not None:
        _validate_sha(decision.candidate_sha256, "resume decision candidate_sha256")


def _assert_new_attempt_source(cell: DailySb3CellState) -> None:
    if cell.status == "PENDING" or cell.phase == "PENDING":
        raise DailyPortfolioSb3StateError("pending cell state cannot start a new attempt")
    if cell.status == "COMPLETED" or cell.phase == "CELL_COMPLETED":
        raise DailyPortfolioSb3StateError("completed cell state cannot start a new attempt")
    if cell.status in TERMINAL_STATUSES or cell.phase in TERMINAL_STATUSES:
        raise DailyPortfolioSb3StateError("terminal cell state cannot start a new attempt")
    if cell.status != "RUNNING" or cell.phase not in NEW_ATTEMPT_SOURCE_PHASES:
        raise DailyPortfolioSb3StateError("new attempt requires an interrupted or checkpointed running cell")
    if cell.phase == "CELL_CHECKPOINTED" and not cell.checkpoint_refs:
        raise DailyPortfolioSb3StateError("checkpointed cell restart requires a checkpoint reference")



def _cells_with_replacement(cells: tuple[DailySb3CellState, ...], updated: DailySb3CellState) -> tuple[DailySb3CellState, ...]:
    answer = tuple(updated if cell.cell_uid == updated.cell_uid else cell for cell in cells)
    if answer == cells:
        raise DailyPortfolioSb3StateError(f"unknown cell_uid: {updated.cell_uid}")
    return answer


def _replace_cell(state: DailySb3RunState, updated: DailySb3CellState, *, phase: str, status: str) -> DailySb3RunState:
    return replace(state, cells=_cells_with_replacement(state.cells, updated), phase=phase, status=status, event_seq=state.event_seq + 1)


def _terminal_transition(
    state: DailySb3RunState,
    *,
    terminal_status: str,
    reason_code: str,
    stop_codes: tuple[str, ...],
    created_at: str,
) -> TerminalTransition:
    _assert_not_terminal(state)
    if terminal_status not in TERMINAL_STATUSES:
        raise DailyPortfolioSb3StateError("invalid terminal status")
    next_event_seq = state.event_seq + 1
    next_cells = _terminal_cells(state.cells, terminal_status)
    counts = dict(sorted(Counter(cell.status for cell in next_cells).items()))
    payload = {
        "schema": RUNNER_TERMINAL_ARTIFACT_SCHEMA,
        "protocol_schema": protocol_contract.PROTOCOL_SCHEMA,
        "protocol_sha256": state.protocol_sha256,
        "run_uid": state.run_uid,
        "terminal_status": terminal_status,
        "phase_before": state.phase,
        "status_before": state.status,
        "event_seq": next_event_seq,
        "reason_code": _required_text(reason_code, "reason_code"),
        "stop_codes": list(stop_codes),
        "stop_predicate_order": list(STOP_PREDICATE_CODES),
        "cell_counts": counts,
        "checkpoint_interval_steps": CHECKPOINT_INTERVAL_STEPS,
        "config_retry_allowed": False,
        "claims": {
            "research_only": True,
            "synthetic_verification_only": True,
            "training_allowed": False,
            "sb3_learn_allowed": False,
            "fresh_oos_consumed": False,
            "promotion_allowed": False,
            "model_build_allowed": False,
            "paper_forward_allowed": False,
            "live_broker_order_allowed": False,
            "profitability_claim_allowed": False,
            "go_summary_allowed": False,
        },
        "created_at": _required_text(created_at, "created_at"),
    }
    artifact = _object_ref_for_payload(
        payload,
        uri=f"kronos-run://{state.run_uid}/{terminal_status.lower()}-{next_event_seq}",
        schema=RUNNER_TERMINAL_ARTIFACT_SCHEMA,
    )
    next_state = replace(
        state,
        phase=terminal_status,
        status=terminal_status,
        event_seq=next_event_seq,
        cells=next_cells,
        terminal_artifact_ref=artifact.ref,
        terminal_status=terminal_status,
        stop_codes=stop_codes,
    )
    return TerminalTransition(state=next_state, artifact=artifact)


def _terminal_cells(cells: tuple[DailySb3CellState, ...], terminal_status: str) -> tuple[DailySb3CellState, ...]:
    if terminal_status == "COMPLETED":
        return cells
    return tuple(cell if cell.status == "COMPLETED" else replace(cell, phase=terminal_status, status=terminal_status) for cell in cells)


__all__ = [
    "ArtifactRecord",
    "AuthorityGateError",
    "CHECKPOINT_INTERVAL_STEPS",
    "CapabilityConsumptionStore",
    "DailyPortfolioSb3StateError",
    "DailySb3CellState",
    "DailySb3RunState",
    "InMemoryCapabilityConsumptionStore",
    "MAX_SYNTHETIC_STEPS_PER_CELL",
    "PARTITION_READ_RECEIPT_SCHEMA",
    "RESUME_SNAPSHOT_SCHEMA",
    "RUNNER_STATE_SCHEMA",
    "RUNNER_TERMINAL_ARTIFACT_SCHEMA",
    "ResumeDecision",
    "ResumeSnapshot",
    "ResumeSnapshotError",
    "STOP_PREDICATE_CODES",
    "TerminalTransition",
    "authorize_partition_read",
    "build_initial_state",
    "checkpoint_due",
    "complete_cell",
    "complete_run",
    "decide_resume",
    "derive_attempt_uid",
    "derive_run_uid",
    "evaluate_stop_predicates",
    "fail_run",
    "ordered_stop_codes",
    "ordered_stop_codes_for_predicates",
    "read_partition_after_authority",
    "record_checkpoint",
    "request_config_retry",
    "snapshot_artifact",
    "start_cell",
    "start_new_attempt",
    "stop_run",
    "validate_object_ref",
]
