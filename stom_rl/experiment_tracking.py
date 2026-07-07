"""Opt-in, self-host MLflow experiment-tracking shim for Kronos RL research.

Design contract (read before wiring anything into training):

* OPT-IN ONLY. Tracking is disabled unless the environment variable
  ``KRONOS_MLFLOW_ENABLED`` is set to a truthy value (``1``/``true``/``yes``/``on``)
  AND ``mlflow`` is importable. If either is false, every public function here
  is a silent no-op that never raises.
* SELF-HOST, NO EGRESS. The tracking URI is always a local ``file:`` store
  resolved to ``<repo>/artifacts/mlruns``. This module never targets a remote
  or HTTP tracking server, and it makes no external network calls.
* NOT WIRED INTO TRAINING BY DEFAULT. This is a standalone scaffold that
  training/research code MAY call later. Nothing in the contract-bearing event
  path (``stom_rl/rl_events.py``, ``daily_rl_train.py``,
  ``daily_close_slot_train.py``, ...) imports or invokes it. Keep it that way
  unless a plan explicitly authorizes the wiring.
* GRACEFUL DEGRADATION. Importing this module has no side effects and never
  imports ``mlflow`` at module load. ``mlflow`` is imported lazily inside the
  functions that need it, guarded by try/except, so the module is safe to import
  in any environment (including ones without mlflow installed).

Usage (only ever runs when explicitly enabled)::

    from stom_rl import experiment_tracking as et

    et.log_run(
        "close_slot_smoke",
        params={"cost_bps": 23.0, "seed": 100},
        metrics={"final_equity_mult": 1.08},
        tags={"stage": "smoke", "research_only": "true"},
    )

    # or as a context manager
    with et.tracked_run("close_slot_smoke", params={"seed": 100}) as run:
        ...  # run is the active mlflow run, or None when disabled
"""

from __future__ import annotations

import math
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional

# Environment flag that gates all tracking. Off unless explicitly enabled.
ENABLED_ENV_VAR = "KRONOS_MLFLOW_ENABLED"
# Optional override for the local file store directory (still self-host only).
DIR_ENV_VAR = "KRONOS_MLFLOW_DIR"
# Default experiment name used when a caller does not supply one.
DEFAULT_EXPERIMENT = "kronos_rl_research"

_TRUTHY = {"1", "true", "yes", "on", "y", "t"}


def _repo_root() -> Path:
    """Return the repository root (parent of the ``stom_rl`` package)."""

    return Path(__file__).resolve().parents[1]


def _env_flag_on() -> bool:
    """Return True only when the opt-in env flag is set to a truthy value."""

    return os.environ.get(ENABLED_ENV_VAR, "").strip().lower() in _TRUTHY


def _mlflow_available() -> bool:
    """Return True when ``mlflow`` can be imported, False otherwise."""

    try:
        import mlflow  # noqa: F401
    except Exception:
        return False
    return True


def is_enabled() -> bool:
    """Return True only when tracking is both opted-in and importable.

    Never raises: any failure (missing env, missing/broken mlflow) yields False.
    """

    try:
        return _env_flag_on() and _mlflow_available()
    except Exception:
        return False


def tracking_dir(base_dir: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the local file-store directory (``<repo>/artifacts/mlruns``).

    ``base_dir`` (or the ``KRONOS_MLFLOW_DIR`` env var) overrides the location,
    which is still treated as a plain local directory — never a remote server.
    """

    if base_dir is None:
        base_dir = os.environ.get(DIR_ENV_VAR) or None
    if base_dir is not None:
        return Path(base_dir).expanduser().resolve()
    return (_repo_root() / "artifacts" / "mlruns").resolve()


def tracking_uri(base_dir: str | os.PathLike[str] | None = None) -> str:
    """Return a self-host ``file:`` tracking URI for the local store.

    The directory is created if missing so that ``Path.as_uri()`` produces a
    stable absolute file URI (e.g. ``file:///D:/.../artifacts/mlruns``).
    """

    path = tracking_dir(base_dir)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Directory creation is best-effort; still return a usable URI.
        pass
    return path.as_uri()


def _coerce_params(params: Optional[Mapping[str, Any]]) -> dict[str, str]:
    """Coerce params to str-valued dict (mlflow params are strings)."""

    if not params:
        return {}
    coerced: dict[str, str] = {}
    for key, value in params.items():
        coerced[str(key)] = str(value)
    return coerced


def _coerce_metrics(metrics: Optional[Mapping[str, Any]]) -> dict[str, float]:
    """Coerce metrics to finite float values, dropping non-numeric/NaN/inf."""

    if not metrics:
        return {}
    coerced: dict[str, float] = {}
    for key, value in metrics.items():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            coerced[str(key)] = number
    return coerced


def _coerce_tags(tags: Optional[Mapping[str, Any]]) -> dict[str, str]:
    """Coerce tags to str-valued dict."""

    if not tags:
        return {}
    return {str(key): str(value) for key, value in tags.items()}


@contextmanager
def tracked_run(
    run_name: str,
    *,
    params: Optional[Mapping[str, Any]] = None,
    tags: Optional[Mapping[str, Any]] = None,
    experiment: Optional[str] = None,
    base_dir: str | os.PathLike[str] | None = None,
) -> Iterator[Any]:
    """Context manager yielding an active mlflow run, or ``None`` when disabled.

    When disabled or on any failure, yields ``None`` and never raises, so call
    sites can use ``with tracked_run(...) as run:`` unconditionally.
    """

    if not is_enabled():
        yield None
        return

    try:
        import mlflow
    except Exception:
        yield None
        return

    try:
        mlflow.set_tracking_uri(tracking_uri(base_dir))
        mlflow.set_experiment(experiment or DEFAULT_EXPERIMENT)
    except Exception:
        yield None
        return

    run = None
    try:
        run = mlflow.start_run(run_name=run_name)
        run.__enter__()
        params_ = _coerce_params(params)
        if params_:
            mlflow.log_params(params_)
        tags_ = _coerce_tags(tags)
        if tags_:
            mlflow.set_tags(tags_)
        yield run
    except Exception:
        # Never propagate tracking failures to the caller.
        yield None
    finally:
        if run is not None:
            try:
                run.__exit__(None, None, None)
            except Exception:
                pass


def log_run(
    run_name: str,
    params: Optional[Mapping[str, Any]] = None,
    metrics: Optional[Mapping[str, Any]] = None,
    tags: Optional[Mapping[str, Any]] = None,
    *,
    experiment: Optional[str] = None,
    base_dir: str | os.PathLike[str] | None = None,
) -> Optional[str]:
    """Log a single run to the local file store; silent no-op when disabled.

    Returns the mlflow ``run_id`` on success, or ``None`` when tracking is
    disabled, mlflow is unavailable, or any error occurs. Never raises.
    """

    if not is_enabled():
        return None

    try:
        import mlflow
    except Exception:
        return None

    try:
        mlflow.set_tracking_uri(tracking_uri(base_dir))
        mlflow.set_experiment(experiment or DEFAULT_EXPERIMENT)
        with mlflow.start_run(run_name=run_name) as run:
            params_ = _coerce_params(params)
            if params_:
                mlflow.log_params(params_)
            metrics_ = _coerce_metrics(metrics)
            if metrics_:
                mlflow.log_metrics(metrics_)
            tags_ = _coerce_tags(tags)
            if tags_:
                mlflow.set_tags(tags_)
            return run.info.run_id
    except Exception:
        # Silent no-op on any failure, per the opt-in / graceful-degradation contract.
        return None


__all__ = [
    "ENABLED_ENV_VAR",
    "DIR_ENV_VAR",
    "DEFAULT_EXPERIMENT",
    "is_enabled",
    "tracking_dir",
    "tracking_uri",
    "tracked_run",
    "log_run",
]
