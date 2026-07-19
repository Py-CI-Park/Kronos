"""Optional localhost-only Aim tracking for STOM RL research runs.

The adapter is default-off and imports Aim lazily only when ``KRONOS_USE_AIM`` is
truthy. It performs no network upload; it only writes to a local Aim repository
for inspection with ``scripts/aim_up.bat`` bound to ``127.0.0.1``.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

_TRUTHY = {"1", "true", "yes", "on"}
_DEFAULT_REPO = ".aim"


def aim_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether the optional Aim adapter should be active."""

    source = os.environ if env is None else env
    return str(source.get("KRONOS_USE_AIM", "")).strip().lower() in _TRUTHY


def stable_json(payload: Any) -> str:
    """Return deterministic JSON for hash/logging payloads."""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_payload(payload: Any) -> str:
    """Hash a config/metadata payload deterministically."""

    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Hash a local artifact file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lazy_run_class() -> Any:
    try:
        from aim import Run
    except Exception as exc:  # pragma: no cover - exact exception depends on install state.
        raise RuntimeError(
            "Aim tracking requested with KRONOS_USE_AIM=1, but the optional "
            "research dependency 'aim' is not importable. Install "
            "stom_rl/requirements-research.txt or disable KRONOS_USE_AIM."
        ) from exc
    return Run


class AimResearchTracker:
    """Small wrapper around Aim Run with disabled-mode no-op behavior."""

    def __init__(
        self,
        *,
        run_name: str,
        repo: str | Path | None = None,
        experiment: str = "kronos-stom-rl-research",
        config: Mapping[str, Any] | None = None,
        hashes: Mapping[str, Any] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.enabled = aim_enabled(env)
        self.run_name = str(run_name)
        self.repo = str(repo or (env or os.environ).get("KRONOS_AIM_REPO", _DEFAULT_REPO))
        self.experiment = experiment
        self._run: Any | None = None
        if not self.enabled:
            return

        Run = _lazy_run_class()
        self._run = Run(repo=self.repo, experiment=experiment)
        self._run.name = self.run_name
        self.log_config(config or {})
        self.log_hashes(hashes or {})

    @property
    def run(self) -> Any | None:
        return self._run

    def log_config(self, config: Mapping[str, Any]) -> None:
        if not self.enabled or self._run is None:
            return
        payload = dict(config)
        self._run["config"] = payload
        self._run["config_hash"] = sha256_payload(payload)

    def log_hashes(self, hashes: Mapping[str, Any]) -> None:
        if not self.enabled or self._run is None:
            return
        self._run["hashes"] = dict(hashes)

    def log_metrics(self, metrics: Mapping[str, Any], *, step: int | None = None, context: Mapping[str, Any] | None = None) -> None:
        if not self.enabled or self._run is None:
            return
        for name, value in sorted(metrics.items()):
            if isinstance(value, bool):
                numeric = int(value)
            elif isinstance(value, (int, float)):
                numeric = value
            else:
                continue
            self._run.track(numeric, name=str(name), step=step, context=dict(context or {}))

    def close(self) -> None:
        if self._run is not None and hasattr(self._run, "close"):
            self._run.close()

    def __enter__(self) -> "AimResearchTracker":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def maybe_create_tracker(
    *,
    run_name: str,
    repo: str | Path | None = None,
    experiment: str = "kronos-stom-rl-research",
    config: Mapping[str, Any] | None = None,
    hashes: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> AimResearchTracker:
    """Create a no-op tracker unless ``KRONOS_USE_AIM`` is enabled."""

    return AimResearchTracker(
        run_name=run_name,
        repo=repo,
        experiment=experiment,
        config=config,
        hashes=hashes,
        env=env,
    )
