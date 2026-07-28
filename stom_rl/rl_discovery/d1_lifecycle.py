"""Resumable, digest-bound lifecycle for Type2-D1 arm/seed units."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from stom_rl.rl_discovery.d1_contract import D1ArmId
from stom_rl.rl_discovery.d1_gates import D1Outcome
from stom_rl.rl_discovery.gates import RunProfile
from stom_rl.rl_discovery.storage import (
    atomic_write_json,
    contained_path,
    create_run_directory,
    file_digest,
    validate_run_directory,
)


class D1LifecycleError(ValueError):
    """Raised when persisted D1 execution state cannot be trusted."""


class D1ArtifactStamp(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class D1UnitManifest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos.rl-discovery.d1-unit.v1"]
    run_key: str
    outcome: D1ArtifactStamp
    events: D1ArtifactStamp
    model: D1ArtifactStamp
    normalizer: D1ArtifactStamp


class D1UnitReference(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    run_key: str
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class D1LifecycleState(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos.rl-discovery.d1-lifecycle.v1"]
    experiment_id: Literal["TYPE2-D1-REWARD-ACTION"]
    profile: RunProfile
    prereg_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["RUNNING", "COMPLETE_PENDING_RECEIPT"]
    expected_runs: tuple[str, ...]
    completed_units: tuple[D1UnitReference, ...]


class D1OutcomePayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    arm: D1ArmId
    seed: int = Field(ge=0)
    training_timesteps: int = Field(ge=0)
    economic_reward_ratio: float
    initial_decision_accuracy: float = Field(ge=0, le=1)
    invalid_action_count: int = Field(ge=0)
    block_count: int = Field(ge=0)
    no_fill_count: int = Field(ge=0)
    dominant_initial_action_rate: float = Field(ge=0, le=1)

    def to_outcome(self) -> D1Outcome:
        return D1Outcome(**self.model_dump())


class D1Lifecycle:
    """Persist completion only after each outcome and model bundle is hashed."""

    def __init__(self, run_dir: Path, state: D1LifecycleState) -> None:
        self.run_dir = run_dir
        self._state = state

    @classmethod
    def open(
        cls,
        run_root: Path,
        *,
        run_id: str,
        experiment_id: Literal["TYPE2-D1-REWARD-ACTION"],
        profile: RunProfile,
        prereg_sha256: str,
        fixture_sha256: str,
        expected_runs: tuple[str, ...],
        resume: bool,
    ) -> D1Lifecycle:
        if resume:
            run_dir = validate_run_directory(run_root, run_root / run_id)
            if contained_path(run_dir, "terminal_receipt.json").exists():
                raise D1LifecycleError("terminal D1 run is immutable")
            state = D1LifecycleState.model_validate_json(
                contained_path(run_dir, "lifecycle.json").read_text(encoding="utf-8")
            )
            identity = (
                state.experiment_id == experiment_id
                and state.profile is profile
                and state.prereg_sha256 == prereg_sha256
                and state.fixture_sha256 == fixture_sha256
                and state.expected_runs == expected_runs
            )
            if not identity:
                raise D1LifecycleError("resume identity differs from persisted D1 lifecycle")
            lifecycle = cls(run_dir, state)
            lifecycle._verify_all()
            return lifecycle
        run_dir = create_run_directory(run_root, run_id)
        state = D1LifecycleState(
            schema_version="kronos.rl-discovery.d1-lifecycle.v1",
            experiment_id=experiment_id,
            profile=profile,
            prereg_sha256=prereg_sha256,
            fixture_sha256=fixture_sha256,
            status="RUNNING",
            expected_runs=expected_runs,
            completed_units=(),
        )
        lifecycle = cls(run_dir, state)
        lifecycle._persist()
        return lifecycle

    @property
    def completed_keys(self) -> frozenset[str]:
        return frozenset(unit.run_key for unit in self._state.completed_units)

    @property
    def outcomes(self) -> tuple[D1Outcome, ...]:
        values: list[D1Outcome] = []
        for reference in self._state.completed_units:
            arm, seed = self._parse_key(reference.run_key)
            payload = D1OutcomePayload.model_validate_json(
                contained_path(self.run_dir, "outcomes", arm.value, f"seed-{seed}.json").read_text(
                    encoding="utf-8"
                )
            )
            values.append(payload.to_outcome())
        return tuple(values)

    def record(self, outcome: D1Outcome) -> None:
        key = self.key(outcome.arm, outcome.seed)
        if self._state.status != "RUNNING" or key not in self._state.expected_runs:
            raise D1LifecycleError(f"unexpected or terminal D1 unit: {key}")
        if key in self.completed_keys:
            raise D1LifecycleError(f"duplicate D1 unit: {key}")
        manifest = D1UnitManifest(
            schema_version="kronos.rl-discovery.d1-unit.v1",
            run_key=key,
            outcome=self._stamp(contained_path(self.run_dir, "outcomes", outcome.arm.value, f"seed-{outcome.seed}.json")),
            events=self._stamp(contained_path(self.run_dir, "events", outcome.arm.value, f"seed-{outcome.seed}.json")),
            model=self._stamp(contained_path(self.run_dir, "models", outcome.arm.value, f"seed-{outcome.seed}", "model.zip")),
            normalizer=self._stamp(contained_path(self.run_dir, "models", outcome.arm.value, f"seed-{outcome.seed}", "normalizer.pkl")),
        )
        manifest_path = contained_path(
            self.run_dir, "unit_manifests", outcome.arm.value, f"seed-{outcome.seed}.json"
        )
        atomic_write_json(manifest_path, manifest.model_dump(mode="json"))
        reference = D1UnitReference(run_key=key, manifest_sha256=file_digest(manifest_path)[0])
        self._state = self._state.model_copy(
            update={"completed_units": (*self._state.completed_units, reference)}
        )
        self._persist()

    def mark_complete_pending_receipt(self) -> None:
        if self.completed_keys != frozenset(self._state.expected_runs):
            raise D1LifecycleError("every D1 unit must be complete before terminal publication")
        self._verify_all()
        self._state = self._state.model_copy(update={"status": "COMPLETE_PENDING_RECEIPT"})
        self._persist()

    def _verify_all(self) -> None:
        for reference in self._state.completed_units:
            arm, seed = self._parse_key(reference.run_key)
            manifest_path = contained_path(
                self.run_dir, "unit_manifests", arm.value, f"seed-{seed}.json"
            )
            if file_digest(manifest_path)[0] != reference.manifest_sha256:
                raise D1LifecycleError(f"unit manifest changed: {reference.run_key}")
            manifest = D1UnitManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
            checks = (
                (contained_path(self.run_dir, "outcomes", arm.value, f"seed-{seed}.json"), manifest.outcome),
                (contained_path(self.run_dir, "events", arm.value, f"seed-{seed}.json"), manifest.events),
                (contained_path(self.run_dir, "models", arm.value, f"seed-{seed}", "model.zip"), manifest.model),
                (contained_path(self.run_dir, "models", arm.value, f"seed-{seed}", "normalizer.pkl"), manifest.normalizer),
            )
            for path, stamp in checks:
                digest, size = file_digest(path)
                if digest != stamp.sha256 or size != stamp.size_bytes:
                    raise D1LifecycleError(f"unit artifact changed: {reference.run_key}")

    def _persist(self) -> None:
        atomic_write_json(
            contained_path(self.run_dir, "lifecycle.json"),
            self._state.model_dump(mode="json"),
        )

    @staticmethod
    def key(arm: D1ArmId, seed: int) -> str:
        return f"{arm.value}:{seed}"

    @staticmethod
    def _parse_key(value: str) -> tuple[D1ArmId, int]:
        arm_value, separator, seed_value = value.partition(":")
        if separator != ":" or not seed_value.isdigit():
            raise D1LifecycleError(f"invalid D1 run key: {value}")
        return D1ArmId(arm_value), int(seed_value)

    @staticmethod
    def _stamp(path: Path) -> D1ArtifactStamp:
        if not path.is_file():
            raise D1LifecycleError(f"missing D1 artifact: {path}")
        sha256, size_bytes = file_digest(path)
        return D1ArtifactStamp(size_bytes=size_bytes, sha256=sha256)
