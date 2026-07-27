"""Durable, resumable evidence lifecycle for Type2 discovery runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict
from typing_extensions import override

from stom_rl.rl_discovery.gates import ArmOutcome, GateResult, RunProfile


class LifecycleState(BaseModel):
    """Strict boundary persisted before any expensive training starts."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos.rl-discovery.lifecycle.v1"]
    experiment_id: str
    profile: RunProfile
    prereg_sha256: str
    status: str
    expected_runs: tuple[str, ...]
    completed_runs: tuple[str, ...]


class OutcomePayload(BaseModel):
    """Typed JSON boundary for one persisted arm/seed result."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    arm: str
    seed: int
    training_timesteps: int
    oracle_reward_ratio: float
    exact_basket_accuracy: float
    invalid_action_count: int
    block_count: int
    no_fill_count: int
    dominant_action_rate: float
    shuffled_reward: bool


@dataclass(frozen=True, slots=True)
class ResumeMismatchError(ValueError):
    """Raised when resumption would cross an immutable experiment boundary."""

    field: str

    @override
    def __str__(self) -> str:
        return f"cannot resume: {self.field} does not match the persisted lifecycle"


def _atomic_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    _ = temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _ = temporary.replace(path)


def _outcome_payload(outcome: ArmOutcome) -> dict[str, object]:
    payload = asdict(outcome)
    payload["model"] = f"{outcome.arm}/seed-{outcome.seed}"
    payload["algorithm"] = outcome.arm
    return payload


class DiscoveryLifecycle:
    """Owns partial evidence, immutable identity checks, and terminalization."""

    def __init__(self, run_dir: Path, state: LifecycleState, outcomes: tuple[ArmOutcome, ...]) -> None:
        self.run_dir: Path = run_dir
        self._state: LifecycleState = state
        self._outcomes: tuple[ArmOutcome, ...] = outcomes

    @classmethod
    def start(
        cls,
        run_root: Path,
        *,
        run_id: str,
        experiment_id: str,
        profile: RunProfile | str,
        prereg_sha256: str,
        expected_runs: tuple[str, ...],
    ) -> DiscoveryLifecycle:
        if Path(run_id).name != run_id or run_id in {"", ".", ".."}:
            raise ValueError("run_id must be a direct child name")
        run_dir = run_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        state = LifecycleState(
            schema_version="kronos.rl-discovery.lifecycle.v1",
            experiment_id=experiment_id,
            profile=RunProfile(profile),
            prereg_sha256=prereg_sha256,
            status="RUNNING",
            expected_runs=expected_runs,
            completed_runs=(),
        )
        lifecycle = cls(run_dir, state, ())
        lifecycle._persist()
        return lifecycle

    @classmethod
    def resume(
        cls,
        run_dir: Path,
        *,
        experiment_id: str,
        profile: RunProfile | str,
        prereg_sha256: str,
    ) -> DiscoveryLifecycle:
        state = LifecycleState.model_validate_json(
            (run_dir / "lifecycle.json").read_text(encoding="utf-8")
        )
        expected = {
            "experiment_id": experiment_id,
            "profile": RunProfile(profile),
            "prereg_sha256": prereg_sha256,
        }
        for field, value in expected.items():
            if getattr(state, field) != value:
                raise ResumeMismatchError(field)
        outcomes = tuple(cls._read_outcome(run_dir, key) for key in state.completed_runs)
        return cls(run_dir, state, outcomes)

    @property
    def outcomes(self) -> tuple[ArmOutcome, ...]:
        return self._outcomes

    @property
    def completed_keys(self) -> frozenset[str]:
        return frozenset(self._state.completed_runs)

    def record(self, outcome: ArmOutcome) -> None:
        key = f"{outcome.arm}:{outcome.seed}"
        if key not in self._state.expected_runs:
            raise ValueError(f"unexpected discovery run: {key}")
        if key in self.completed_keys:
            raise ValueError(f"discovery run already recorded: {key}")
        outcome_path = self.run_dir / "outcomes" / outcome.arm / f"seed-{outcome.seed}.json"
        outcome_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(outcome_path, _outcome_payload(outcome))
        self._outcomes = (*self._outcomes, outcome)
        self._state = self._state.model_copy(
            update={"completed_runs": (*self._state.completed_runs, key)}
        )
        self._persist()

    def complete(self, gate: GateResult) -> None:
        self._state = self._state.model_copy(update={"status": gate.status})
        self._persist(gate)
        _atomic_json(
            self.run_dir / "terminal_receipt.json",
            {
                "experiment_id": self._state.experiment_id,
                "profile": self._state.profile.value,
                "status": gate.status,
                "verdict": gate.verdict,
                "promotion_allowed": gate.promotion_allowed,
                "profitability_claim_allowed": gate.profitability_claim_allowed,
                "fresh_oos": gate.fresh_oos,
                "prereg_sha256": self._state.prereg_sha256,
            },
        )

    @staticmethod
    def _read_outcome(run_dir: Path, key: str) -> ArmOutcome:
        arm, seed_text = key.rsplit(":", maxsplit=1)
        payload = OutcomePayload.model_validate_json(
            (run_dir / "outcomes" / arm / f"seed-{seed_text}.json").read_text(
                encoding="utf-8"
            )
        )
        return ArmOutcome(
            arm=payload.arm,
            seed=payload.seed,
            training_timesteps=payload.training_timesteps,
            oracle_reward_ratio=payload.oracle_reward_ratio,
            exact_basket_accuracy=payload.exact_basket_accuracy,
            invalid_action_count=payload.invalid_action_count,
            block_count=payload.block_count,
            no_fill_count=payload.no_fill_count,
            dominant_action_rate=payload.dominant_action_rate,
            shuffled_reward=payload.shuffled_reward,
        )

    def _persist(self, gate: GateResult | None = None) -> None:
        _atomic_json(self.run_dir / "lifecycle.json", self._state.model_dump(mode="json"))
        summary = {
            "research_lane": "rl_discovery",
            "experiment_id": self._state.experiment_id,
            "profile": self._state.profile.value,
            "status": self._state.status,
            "verdict": gate.verdict if gate else "RUNNING_NOT_EVALUATED",
            "reasons": list(gate.reasons) if gate else ["run is incomplete"],
            "fresh_oos": gate.fresh_oos if gate else "NOT_RUN_NO_READ",
            "type1_outcome": "COMPLETE_NO_GO",
            "promotion_allowed": gate.promotion_allowed if gate else False,
            "profitability_claim_allowed": gate.profitability_claim_allowed if gate else False,
            "prereg_sha256": self._state.prereg_sha256,
            "completed_run_count": len(self._state.completed_runs),
            "expected_run_count": len(self._state.expected_runs),
            "arm_count": len({outcome.arm for outcome in self._outcomes}),
            "seed_count": len({outcome.seed for outcome in self._outcomes}),
        }
        models = [_outcome_payload(outcome) for outcome in self._outcomes]
        _atomic_json(self.run_dir / "sb3_smoke_summary.json", {"summary": summary, "models": models})
        _atomic_json(self.run_dir / "outcomes.json", models)
