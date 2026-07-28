"""Synthetic-only executor for the immutable daily Portfolio SB3 runner state.

This runner advances the authoritative 50-cell matrix through deterministic tiny
state transitions.  It deliberately refuses heavy compute, SB3 learning, config
retry, and fresh-OOS access; real training must not be wired through this module.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Final, Mapping, Sequence

from stom_rl import daily_portfolio_sb3_protocol as protocol_contract
from stom_rl import daily_portfolio_sb3_events as event_contract
from stom_rl.daily_portfolio_sb3_state import (
    MAX_SYNTHETIC_STEPS_PER_CELL,
    ArtifactRecord,
    DailyPortfolioSb3StateError,
    DailySb3RunState,
    ResumeDecision,
    TerminalTransition,
    build_initial_state,
    complete_cell,
    complete_run,
    start_cell,
    start_new_attempt,
)


SYNTHETIC_RUNNER_RESULT_SCHEMA: Final = "kronos_daily_sb3_synthetic_runner_result.v1"


class SyntheticRunnerError(DailyPortfolioSb3StateError):
    """Raised when a caller asks the synthetic runner to do non-synthetic work."""


@dataclass(frozen=True)
class SyntheticRunnerConfig:
    max_cells: int = 50
    steps_per_cell: int = 3
    synthetic_verification_only: bool = True
    no_heavy_compute: bool = True
    resume_mode: str = "none"


@dataclass(frozen=True)
class SyntheticRunResult:
    state: DailySb3RunState
    event_stream: Mapping[str, Any]
    terminal_artifact: ArtifactRecord | None

    @property
    def events(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.event_stream["events"])

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": SYNTHETIC_RUNNER_RESULT_SCHEMA,
            "state": self.state.to_mapping(),
            "event_stream": dict(self.event_stream),
            "terminal_artifact_ref": None if self.terminal_artifact is None else dict(self.terminal_artifact.ref),
        }


class SyntheticDailyPortfolioSb3Runner:
    """Deterministic matrix executor for tests and dashboard plumbing only."""

    def __init__(self, protocol_value: Mapping[str, Any] | None = None) -> None:
        value = protocol_contract.build_protocol() if protocol_value is None else dict(protocol_value)
        protocol_contract.validate_protocol(value)
        self._protocol = value

    @property
    def protocol(self) -> Mapping[str, Any]:
        return self._protocol

    def initial_state(self) -> DailySb3RunState:
        return build_initial_state(self._protocol)

    def run(self, config: SyntheticRunnerConfig | None = None, *, completed_at: str = "2026-07-15T00:00:00Z") -> SyntheticRunResult:
        cfg = SyntheticRunnerConfig() if config is None else config
        _validate_synthetic_config(cfg)
        state = self.initial_state()
        selected_cells = state.cells[: cfg.max_cells]
        stream = event_contract.start_event_stream(created_at=completed_at, protocol=self._protocol)
        first_cell = selected_cells[0]
        stream = event_contract.append_event(
            stream,
            run_uid=state.run_uid,
            cell_uid=first_cell.cell_uid,
            occurred_at=completed_at,
            event_kind="RUN_CREATED",
            phase="PREREGISTERED",
            lifecycle_state="NOT_RUN",
            step=0,
            total_steps=cfg.steps_per_cell,
            protocol=self._protocol,
        )
        terminal_artifact = None
        for cell in selected_cells:
            state = start_cell(state, cell.cell_uid)
            if cfg.resume_mode == "none" or cell.cell_uid != first_cell.cell_uid:
                state = complete_cell(state, cell.cell_uid, step=cfg.steps_per_cell)
                stream = event_contract.append_event(
                    stream,
                    run_uid=state.run_uid,
                    cell_uid=cell.cell_uid,
                    occurred_at=completed_at,
                    event_kind="PROGRESS",
                    phase="SYNTHETIC_TRAIN",
                    lifecycle_state="ADVANCING",
                    step=cfg.steps_per_cell,
                    total_steps=cfg.steps_per_cell,
                    protocol=self._protocol,
                )
                continue
            checkpoint_step = 1
            checkpoint = event_contract.artifact_ref(
                f"agent://kronos-v5/checkpoints/{state.run_uid}/{cell.cell_uid}/attempt-1-step-1",
                "kronos_daily_sb3_checkpoint_ref.v1",
                "synthetic_checkpoint",
                {"schema": "kronos_daily_sb3_checkpoint_ref.v1", "run_uid": state.run_uid, "cell_uid": cell.cell_uid, "attempt_number": 1, "step": checkpoint_step},
            )
            stream = event_contract.append_event(
                stream,
                run_uid=state.run_uid,
                cell_uid=cell.cell_uid,
                occurred_at=completed_at,
                event_kind="PROGRESS",
                phase="SYNTHETIC_TRAIN",
                lifecycle_state="ADVANCING",
                step=checkpoint_step,
                total_steps=cfg.steps_per_cell,
                protocol=self._protocol,
            )
            stream = event_contract.append_event(
                stream,
                run_uid=state.run_uid,
                cell_uid=cell.cell_uid,
                occurred_at=completed_at,
                event_kind="CHECKPOINT",
                phase="CHECKPOINT",
                lifecycle_state="STALLED",
                step=checkpoint_step,
                total_steps=cfg.steps_per_cell,
                artifact_refs=[checkpoint],
                checkpoint_ref=checkpoint,
                protocol=self._protocol,
            )
            resume_exact = cfg.resume_mode == "exact"
            if not resume_exact:
                decision = ResumeDecision(
                    exact=False,
                    action="RESTART_NEW_ATTEMPT",
                    reason_code="SNAPSHOT_MISMATCH",
                    previous_sha256=None,
                    candidate_sha256=None,
                    new_attempt_required=True,
                )
                state = start_new_attempt(state, cell.cell_uid, decision)
            stream = event_contract.append_event(
                stream,
                run_uid=state.run_uid,
                cell_uid=cell.cell_uid,
                occurred_at=completed_at,
                event_kind="RESUME",
                phase="RESUME",
                lifecycle_state="RESUMED" if resume_exact else "RESTARTED_NON_EXACT",
                step=checkpoint_step if resume_exact else 0,
                total_steps=cfg.steps_per_cell,
                resume_from_checkpoint_ref=checkpoint,
                resume_exact=resume_exact,
                protocol=self._protocol,
            )
            if not resume_exact:
                state = start_cell(state, cell.cell_uid)
            state = complete_cell(state, cell.cell_uid, step=cfg.steps_per_cell)
            stream = event_contract.append_event(
                stream,
                run_uid=state.run_uid,
                cell_uid=cell.cell_uid,
                occurred_at=completed_at,
                event_kind="PROGRESS",
                phase="SYNTHETIC_TRAIN",
                lifecycle_state="ADVANCING",
                step=cfg.steps_per_cell,
                total_steps=cfg.steps_per_cell,
                protocol=self._protocol,
            )
        if cfg.max_cells == len(state.cells):
            transition: TerminalTransition = complete_run(state, completed_at=completed_at)
            state = transition.state
            terminal_artifact = transition.artifact
            stop_report = event_contract.artifact_ref(
                f"agent://kronos-v5/stop-reports/{state.run_uid}",
                "kronos_daily_sb3_stop_report.v1",
                "synthetic_stop_report",
                {"schema": "kronos_daily_sb3_stop_report.v1", "run_uid": state.run_uid, "terminal_status": "COMPLETED", "event_seq": state.event_seq},
            )
            stream = event_contract.append_event(
                stream,
                run_uid=state.run_uid,
                cell_uid=selected_cells[-1].cell_uid,
                occurred_at=completed_at,
                event_kind="STOP",
                phase="TERMINAL",
                lifecycle_state="COMPLETED",
                step=cfg.steps_per_cell,
                total_steps=cfg.steps_per_cell,
                artifact_refs=[stop_report],
                stop_reason_code="SYNTHETIC_COMPLETE",
                protocol=self._protocol,
            )
        return SyntheticRunResult(state=state, event_stream=stream, terminal_artifact=terminal_artifact)


def _validate_synthetic_config(config: SyntheticRunnerConfig) -> None:
    if config.synthetic_verification_only is not True or config.no_heavy_compute is not True:
        raise SyntheticRunnerError("synthetic runner requires synthetic_verification_only and no_heavy_compute")
    if not isinstance(config.max_cells, int) or isinstance(config.max_cells, bool) or not 1 <= config.max_cells <= 50:
        raise SyntheticRunnerError("synthetic runner max_cells must be between 1 and 50")
    if not isinstance(config.steps_per_cell, int) or isinstance(config.steps_per_cell, bool):
        raise SyntheticRunnerError("synthetic runner steps_per_cell must be an integer")
    if not 0 <= config.steps_per_cell <= MAX_SYNTHETIC_STEPS_PER_CELL:
        raise SyntheticRunnerError("synthetic runner rejects heavy timestep requests")
    if config.resume_mode not in {"none", "exact", "non_exact"}:
        raise SyntheticRunnerError("synthetic runner resume_mode must be none, exact, or non_exact")
    if config.resume_mode != "none" and config.steps_per_cell < 1:
        raise SyntheticRunnerError("synthetic runner resume requires at least one synthetic step")


def run_synthetic(config: SyntheticRunnerConfig | None = None) -> SyntheticRunResult:
    return SyntheticDailyPortfolioSb3Runner().run(config)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the tiny synthetic daily SB3 matrix executor; no training or OOS reads.")
    parser.add_argument("--synthetic-verification-only", action="store_true")
    parser.add_argument("--no-heavy-compute", action="store_true")
    parser.add_argument("--max-cells", type=int, default=1)
    parser.add_argument("--steps-per-cell", type=int, default=3)
    parser.add_argument("--resume-mode", choices=("none", "exact", "non_exact"), default="none")
    args = parser.parse_args(argv)
    config = SyntheticRunnerConfig(
        max_cells=args.max_cells,
        steps_per_cell=args.steps_per_cell,
        synthetic_verification_only=args.synthetic_verification_only,
        no_heavy_compute=args.no_heavy_compute,
        resume_mode=args.resume_mode,
    )
    result = SyntheticDailyPortfolioSb3Runner().run(config)
    print(protocol_contract.canonical_bytes(result.to_mapping()).decode("utf-8"))
    return 0


__all__ = [
    "SYNTHETIC_RUNNER_RESULT_SCHEMA",
    "SyntheticDailyPortfolioSb3Runner",
    "SyntheticRunResult",
    "SyntheticRunnerConfig",
    "SyntheticRunnerError",
    "main",
    "run_synthetic",
]


if __name__ == "__main__":
    raise SystemExit(main())
