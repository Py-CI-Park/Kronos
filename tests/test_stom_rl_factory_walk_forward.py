"""Tests for stom_rl.factory.walk_forward fold generation and guardrails."""

from __future__ import annotations

import random

import pytest

from stom_rl.factory import walk_forward
from stom_rl.factory.walk_forward import (
    Fold,
    WalkForwardError,
    chronological_folds,
    enforce_sample_power,
    fold_manifest,
    synthesize_fold_verdicts,
)


def _sessions(count: int) -> list[str]:
    """Deterministic ascending 'YYYYMMDD' session dates (weekday-agnostic)."""
    out: list[str] = []
    year, month, day = 2025, 1, 1
    for _ in range(count):
        out.append(f"{year:04d}{month:02d}{day:02d}")
        day += 1
        if day > 28:
            day = 1
            month += 1
            if month > 12:
                month = 1
                year += 1
    return out


def test_no_leakage_and_disjoint_roles():
    folds = chronological_folds(_sessions(30), n_folds=5)
    assert len(folds) == 5
    for fold in folds:
        assert isinstance(fold, Fold)
        train_val = fold.train_sessions + fold.validation_sessions
        assert train_val, "train+validation must be non-empty"
        assert fold.oos_sessions, "oos must be non-empty"
        assert max(train_val) < min(fold.oos_sessions)
        roles = (
            set(fold.train_sessions),
            set(fold.validation_sessions),
            set(fold.oos_sessions),
        )
        assert roles[0].isdisjoint(roles[1])
        assert roles[0].isdisjoint(roles[2])
        assert roles[1].isdisjoint(roles[2])


def test_determinism_under_shuffled_input():
    sessions = _sessions(30)
    shuffled_a = list(sessions)
    shuffled_b = list(sessions)
    random.Random(7).shuffle(shuffled_a)
    random.Random(99).shuffle(shuffled_b)
    folds_a = chronological_folds(shuffled_a, n_folds=5)
    folds_b = chronological_folds(shuffled_b, n_folds=5)
    assert folds_a == folds_b
    assert folds_a == chronological_folds(sessions, n_folds=5)


def test_few_folds_requires_explicit_override():
    sessions = _sessions(20)
    with pytest.raises(WalkForwardError):
        chronological_folds(sessions, n_folds=3)
    folds = chronological_folds(sessions, n_folds=3, allow_few_folds=True)
    assert len(folds) == 3
    for fold in folds:
        assert max(fold.train_sessions + fold.validation_sessions) < min(fold.oos_sessions)


def test_too_few_sessions_raises():
    with pytest.raises(WalkForwardError):
        chronological_folds(_sessions(6), n_folds=5)


def test_manifest_split_hash_stable_and_session_sensitive():
    folds = chronological_folds(_sessions(30), n_folds=5)
    manifest_a = fold_manifest(folds)
    manifest_b = fold_manifest(folds)
    assert manifest_a["split_hash"] == manifest_b["split_hash"]
    assert len(manifest_a["split_hash"]) == 16
    assert manifest_a["n_folds"] == 5
    assert manifest_a["guardrail"] == "OOS sessions must never be used for tuning"

    other = fold_manifest(chronological_folds(_sessions(31), n_folds=5))
    assert other["split_hash"] != manifest_a["split_hash"]

    for row, fold in zip(manifest_a["folds"], folds):
        assert row["train_count"] == len(fold.train_sessions)
        assert row["oos_start"] == fold.oos_sessions[0]
        assert row["oos_end"] == fold.oos_sessions[-1]


def test_enforce_sample_power_forces_inconclusive_below_minimum():
    weak = enforce_sample_power(6)
    assert weak == {
        "oos_trades": 6,
        "min_required": 100,
        "sufficient": False,
        "forced_verdict": "INCONCLUSIVE",
    }
    strong = enforce_sample_power(150)
    assert strong["sufficient"] is True
    assert strong["forced_verdict"] == ""


def test_synthesize_fold_verdicts_rules():
    assert synthesize_fold_verdicts(["GO_CANDIDATE"] * 5) == "GO_CANDIDATE"
    assert (
        synthesize_fold_verdicts(["GO_CANDIDATE", "NO-GO_CONTROL", "GO_CANDIDATE"])
        == "NO-GO_FOLDS"
    )
    assert (
        synthesize_fold_verdicts(["GO_CANDIDATE", "INCONCLUSIVE", "GO_CANDIDATE"])
        == "INCONCLUSIVE"
    )
    assert synthesize_fold_verdicts([]) == "INCONCLUSIVE"
    # NO-GO outranks INCONCLUSIVE.
    assert synthesize_fold_verdicts(["INCONCLUSIVE", "NO-GO"]) == "NO-GO_FOLDS"


def test_session_validation_rejects_non_strings_and_bad_shapes():
    with pytest.raises(WalkForwardError):
        chronological_folds([20250101] * 10, n_folds=5)  # type: ignore[list-item]
    with pytest.raises(WalkForwardError):
        chronological_folds(["2025-01-01"] + _sessions(10), n_folds=5)


def test_module_importable_via_package():
    assert hasattr(walk_forward, "chronological_folds")
