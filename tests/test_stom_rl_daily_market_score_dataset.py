from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from stom_rl.daily_market_score_dataset import load_market_score_dataset


def _manifest(path: Path, *, fill_mode: str = "close_to_next_close_research_label") -> Path:
    _ = path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "fill_mode": fill_mode,
                "price_basis": "unknown",
                "decision_grade_return_status": "BLOCKED_UNTIL_PRICE_BASIS_VERIFIED",
                "promotion_allowed": False,
                "upstream_gate_blockers": [
                    "D0_PRICE_BASIS_NOT_VERIFIED",
                    "D1_UNIVERSE_NOT_OFFICIAL_OR_MANUAL_REVIEWED",
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _csv(path: Path, *, future_value: str = "0.1", split: str = "train") -> Path:
    fieldnames = [
        "date",
        "table",
        "code",
        "score",
        "split",
        "eligible_for_selection",
        "future_return_1d",
    ]
    rows: list[dict[str, str]] = []
    for index in range(12):
        code = f"{index + 1:06d}"
        rows.append(
            {
                "date": "20260102",
                "table": f"A{code}",
                "code": code,
                "score": "1.0" if index in {0, 10} else str(100 - index),
                "split": split,
                "eligible_for_selection": "True",
                "future_return_1d": future_value,
            }
        )
    rows.append(
        {
            "date": "20260102",
            "table": "A000099",
            "code": "000099",
            "score": "",
            "split": split,
            "eligible_for_selection": "True",
            "future_return_1d": future_value,
        }
    )
    rows.append(
        {
            "date": "20260103",
            "table": "A000100",
            "code": "000100",
            "score": "3.0",
            "split": split,
            "eligible_for_selection": "False",
            "future_return_1d": future_value,
        }
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_score_dataset_freezes_causal_top10_and_preserves_leading_zero_codes(tmp_path: Path) -> None:
    dataset = load_market_score_dataset(
        _csv(tmp_path / "scores.csv"),
        source_manifest_path=_manifest(tmp_path / "manifest.json"),
        artifact_root=tmp_path,
    )

    assert dataset.schema_version == "kronos_daily_market_score_dataset.v1"
    assert dataset.day_count == 1
    assert dataset.scored_row_count == 12
    assert dataset.excluded_missing_score_rows == 1
    assert dataset.excluded_ineligible_rows == 1
    assert dataset.days[0].split == "TRAIN"
    assert len(dataset.days[0].scores) == 10
    assert dataset.days[0].scores[0].code == "000002"
    assert dataset.days[0].scores[-1].code == "000012"
    assert dataset.source_fill_mode == "close_to_next_close_research_label"
    assert dataset.target_fill_mode == "D_CLOSE_DECISION_D1_OPEN_ENTRY_D2_OPEN_EXIT"
    assert dataset.promotion_allowed is False
    assert dataset.fresh_oos_read is False
    assert "STATE_FEATURE_VECTOR_NOT_BUILT" in dataset.blockers


def test_future_label_change_does_not_change_causal_dataset_hash(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "manifest.json")
    first = load_market_score_dataset(
        _csv(tmp_path / "first.csv", future_value="-0.9"),
        source_manifest_path=manifest,
        artifact_root=tmp_path,
    )
    second = load_market_score_dataset(
        _csv(tmp_path / "second.csv", future_value="0.9"),
        source_manifest_path=manifest,
        artifact_root=tmp_path,
    )

    assert first.dataset_hash == second.dataset_hash
    assert first.source_candidate_csv_sha256 != second.source_candidate_csv_sha256


def test_score_dataset_rejects_unreviewed_fill_mode_and_fresh_oos(tmp_path: Path) -> None:
    scores = _csv(tmp_path / "scores.csv")
    with pytest.raises(ValueError, match="SOURCE_FILL_MODE_UNEXPECTED"):
        _ = load_market_score_dataset(
            scores,
            source_manifest_path=_manifest(tmp_path / "bad.json", fill_mode="next_open"),
            artifact_root=tmp_path,
        )

    fresh_scores = _csv(tmp_path / "fresh.csv", split="fresh_oos")
    with pytest.raises(ValueError, match="FRESH_OOS"):
        _ = load_market_score_dataset(
            fresh_scores,
            source_manifest_path=_manifest(tmp_path / "fresh-manifest.json"),
            artifact_root=tmp_path,
        )


def test_score_dataset_rejects_sources_outside_the_explicit_trusted_root(tmp_path: Path) -> None:
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    scores = _csv(trusted / "scores.csv")
    outside_manifest = _manifest(tmp_path / "outside.json")

    with pytest.raises(ValueError, match="OUTSIDE_TRUSTED_ARTIFACT_ROOT"):
        _ = load_market_score_dataset(
            scores,
            source_manifest_path=outside_manifest,
            artifact_root=trusted,
        )
