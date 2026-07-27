"""Durable, resumable evidence lifecycle for Type2 discovery runs."""

from __future__ import annotations

import hmac
from pathlib import Path

from stom_rl.rl_discovery.gates import ArmOutcome, GateResult, RunProfile, evaluate_discovery_gate
from stom_rl.rl_discovery.lifecycle_evidence import receipt_payload, state_payload, write_dashboard
from stom_rl.rl_discovery.lifecycle_schema import (
    LifecycleIntegrityError,
    LifecycleState,
    LifecycleStatus,
    ArtifactStamp,
    OutcomePayload,
    ResumeMismatchError,
    RunKey,
    TerminalRunError,
    UnitManifest,
    UnitManifestRef,
    outcome_payload,
)
from stom_rl.rl_discovery.storage import (
    atomic_write_json,
    contained_path,
    create_run_directory,
    file_digest,
    validate_run_directory,
)

__all__ = [
    "DiscoveryLifecycle",
    "LifecycleIntegrityError",
    "ResumeMismatchError",
    "TerminalRunError",
]


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
        fixture_sha256: str,
        expected_runs: tuple[str, ...],
    ) -> DiscoveryLifecycle:
        run_dir = create_run_directory(run_root, run_id)
        state = LifecycleState(
            schema_version="kronos.rl-discovery.lifecycle.v2",
            experiment_id=experiment_id,
            profile=RunProfile(profile),
            prereg_sha256=prereg_sha256,
            fixture_sha256=fixture_sha256,
            status=LifecycleStatus.RUNNING,
            expected_runs=expected_runs,
            completed_runs=(),
            unit_manifests=(),
        )
        lifecycle = cls(run_dir, state, ())
        lifecycle._persist_running()
        return lifecycle

    @classmethod
    def resume(
        cls,
        run_dir: Path,
        *,
        run_root: Path,
        experiment_id: str,
        profile: RunProfile | str,
        prereg_sha256: str,
        fixture_sha256: str,
        expected_runs: tuple[str, ...],
    ) -> DiscoveryLifecycle:
        safe_dir = validate_run_directory(run_root, run_dir)
        receipt = contained_path(safe_dir, "terminal_receipt.json")
        if receipt.exists():
            raise TerminalRunError(safe_dir)
        state = LifecycleState.model_validate_json(
            contained_path(safe_dir, "lifecycle.json").read_text(encoding="utf-8")
        )
        expected_identity = {
            "experiment_id": experiment_id,
            "profile": RunProfile(profile),
            "prereg_sha256": prereg_sha256,
            "fixture_sha256": fixture_sha256,
            "expected_runs": expected_runs,
        }
        for field, value in expected_identity.items():
            if getattr(state, field) != value:
                raise ResumeMismatchError(field)
        for reference in state.unit_manifests:
            cls._verify_unit(safe_dir, reference)
        outcomes = tuple(cls._read_outcome(safe_dir, RunKey.parse(key)) for key in state.completed_runs)
        return cls(safe_dir, state, outcomes)

    @property
    def outcomes(self) -> tuple[ArmOutcome, ...]:
        return self._outcomes

    @property
    def completed_keys(self) -> frozenset[str]:
        return frozenset(self._state.completed_runs)

    def record(self, outcome: ArmOutcome) -> None:
        if self._state.status is not LifecycleStatus.RUNNING:
            raise TerminalRunError(self.run_dir)
        key = RunKey.parse(f"{outcome.arm}:{outcome.seed}")
        if key.value not in self._state.expected_runs:
            raise LifecycleIntegrityError("outcome", f"unexpected run {key.value}")
        if key.value in self.completed_keys:
            raise LifecycleIntegrityError("outcome", f"duplicate run {key.value}")
        outcome_path = contained_path(
            self.run_dir, "outcomes", key.arm.value, f"seed-{key.seed}.json"
        )
        outcome_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(outcome_path, outcome_payload(outcome))
        reference = self._write_unit_manifest(key, outcome_path)
        self._outcomes = (*self._outcomes, outcome)
        self._state = self._state.model_copy(
            update={
                "completed_runs": (*self._state.completed_runs, key.value),
                "unit_manifests": (*self._state.unit_manifests, reference),
            }
        )
        self._persist_running()

    def complete(self, gate: GateResult) -> None:
        if self._state.completed_runs != self._state.expected_runs:
            raise LifecycleIntegrityError("complete", "every expected arm/seed must be recorded")
        expected_status = (
            LifecycleStatus.SMOKE_COMPLETE
            if self._state.profile is RunProfile.SMOKE
            else LifecycleStatus.PRIMARY_COMPLETE
        )
        if gate.status != expected_status.value:
            raise LifecycleIntegrityError("gate_status", "must match lifecycle profile")
        computed_gate = evaluate_discovery_gate(self._outcomes, profile=self._state.profile)
        if gate != computed_gate:
            raise LifecycleIntegrityError("gate", "must equal the gate recomputed from recorded outcomes")
        receipt_path = contained_path(self.run_dir, "terminal_receipt.json")
        if receipt_path.exists():
            raise TerminalRunError(self.run_dir)
        terminal_state = self._state.model_copy(update={"status": LifecycleStatus(gate.status)})
        write_dashboard(self.run_dir, terminal_state, self._outcomes, gate)
        atomic_write_json(contained_path(self.run_dir, "lifecycle.json"), state_payload(terminal_state))
        atomic_write_json(receipt_path, receipt_payload(terminal_state, gate))
        self._state = terminal_state

    @staticmethod
    def _read_outcome(run_dir: Path, key: RunKey) -> ArmOutcome:
        path = contained_path(run_dir, "outcomes", key.arm.value, f"seed-{key.seed}.json")
        payload = OutcomePayload.model_validate_json(path.read_text(encoding="utf-8"))
        if payload.arm is not key.arm or payload.seed != key.seed or payload.algorithm is not key.arm:
            raise LifecycleIntegrityError("outcome_identity", key.value)
        return ArmOutcome(
            arm=payload.arm.value,
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

    def _write_unit_manifest(self, key: RunKey, outcome_path: Path) -> UnitManifestRef:
        model_dir = contained_path(self.run_dir, "models", key.arm.value, f"seed-{key.seed}")
        manifest = UnitManifest(
            schema_version="kronos.rl-discovery.unit-manifest.v1",
            run_key=key.value,
            outcome=self._stamp(outcome_path),
            model=self._stamp(model_dir / "model.zip"),
            normalizer=self._stamp(model_dir / "normalizer.pkl"),
        )
        path = contained_path(
            self.run_dir, "unit_manifests", key.arm.value, f"seed-{key.seed}.json"
        )
        atomic_write_json(path, manifest.model_dump(mode="json"))
        return UnitManifestRef(run_key=key.value, sha256=file_digest(path)[0])

    @staticmethod
    def _stamp(path: Path) -> ArtifactStamp:
        sha256, size_bytes = file_digest(path)
        return ArtifactStamp(size_bytes=size_bytes, sha256=sha256)

    @classmethod
    def _verify_unit(cls, run_dir: Path, reference: UnitManifestRef) -> None:
        key = RunKey.parse(reference.run_key)
        manifest_path = contained_path(
            run_dir, "unit_manifests", key.arm.value, f"seed-{key.seed}.json"
        )
        if not manifest_path.is_file():
            raise LifecycleIntegrityError("unit_manifest", f"missing {key.value}")
        actual_manifest_sha = file_digest(manifest_path)[0]
        if not hmac.compare_digest(actual_manifest_sha, reference.sha256):
            raise LifecycleIntegrityError("unit_manifest", key.value)
        manifest = UnitManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        if manifest.run_key != key.value:
            raise LifecycleIntegrityError("unit_manifest_identity", key.value)
        checks = (
            (
                "outcome",
                contained_path(run_dir, "outcomes", key.arm.value, f"seed-{key.seed}.json"),
                manifest.outcome,
            ),
            (
                "model",
                contained_path(run_dir, "models", key.arm.value, f"seed-{key.seed}", "model.zip"),
                manifest.model,
            ),
            (
                "normalizer",
                contained_path(
                    run_dir, "models", key.arm.value, f"seed-{key.seed}", "normalizer.pkl"
                ),
                manifest.normalizer,
            ),
        )
        for field, path, expected in checks:
            if not path.is_file():
                raise LifecycleIntegrityError("unit_artifact", f"missing {key.value}:{field}")
            actual_sha, actual_size = file_digest(path)
            if actual_size != expected.size_bytes or not hmac.compare_digest(
                actual_sha, expected.sha256
            ):
                raise LifecycleIntegrityError("unit_artifact", f"{key.value}:{field}")

    def _persist_running(self) -> None:
        write_dashboard(self.run_dir, self._state, self._outcomes, None)
        atomic_write_json(
            contained_path(self.run_dir, "lifecycle.json"), state_payload(self._state)
        )
