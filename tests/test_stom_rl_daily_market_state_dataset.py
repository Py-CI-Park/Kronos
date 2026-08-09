from __future__ import annotations

import csv
import json
from pathlib import Path

from stom_rl.daily_market_score_dataset import load_market_score_dataset
from stom_rl.daily_market_state_dataset import CAUSAL_FEATURE_COLUMNS, build_market_state_dataset


def _manifest(path: Path) -> Path:
    _ = path.write_text(
        json.dumps(
            {
                "fill_mode": "close_to_next_close_research_label",
                "price_basis": "unknown",
                "decision_grade_return_status": "BLOCKED_UNTIL_PRICE_BASIS_VERIFIED",
                "promotion_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    return path


def _scores(path: Path) -> Path:
    fields = ["date", "table", "code", "score", "split", "eligible_for_selection"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for date_value, split in (("20260102", "train"), ("20260105", "test")):
            for index in range(10):
                code = f"{index + 1:06d}"
                writer.writerow(
                    {
                        "date": date_value,
                        "table": f"A{code}",
                        "code": code,
                        "score": str(100 - index),
                        "split": split,
                        "eligible_for_selection": "True",
                    }
                )
    return path


def _panel(
    path: Path,
    *,
    future_label: str,
    test_multiplier: float = 100.0,
) -> Path:
    fields = ["date", "table", "code", "split", *CAUSAL_FEATURE_COLUMNS, "future_return_1d"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for date_value, split, multiplier in (
            ("20260102", "train", 1.0),
            ("20260105", "test", test_multiplier),
        ):
            for index in range(10):
                code = f"{index + 1:06d}"
                value = (index + 1) * multiplier
                row = {
                    "date": date_value,
                    "table": f"A{code}",
                    "code": code,
                    "split": split,
                    "future_return_1d": future_label,
                    **{feature: str(value) for feature in CAUSAL_FEATURE_COLUMNS},
                }
                if split == "train" and index == 0:
                    row["foreign_holding_ratio"] = ""
                writer.writerow(row)
    return path


def _score_dataset(root: Path):
    return load_market_score_dataset(
        _scores(root / "scores.csv"),
        source_manifest_path=_manifest(root / "manifest.json"),
    )


def test_state_dataset_fits_imputation_and_scaling_on_train_only(tmp_path: Path) -> None:
    score_dataset = _score_dataset(tmp_path)
    state_dataset = build_market_state_dataset(
        score_dataset,
        panel_csv_path=_panel(tmp_path / "panel.csv", future_label="0.9"),
    )

    assert state_dataset.day_count == 2
    assert state_dataset.feature_vector_size == 160
    assert state_dataset.training_selected_rows == 10
    assert state_dataset.statistics[0].feature == "return_1d"
    assert state_dataset.statistics[0].mean == 5.5
    foreign = next(row for row in state_dataset.statistics if row.feature == "foreign_holding_ratio")
    assert foreign.mean == 6.0
    assert foreign.observed_count == 9
    first_vector = state_dataset.days[0].feature_vector
    assert first_vector[12] == 0.0
    assert first_vector[13] == 1.0
    assert state_dataset.promotion_allowed is False
    assert "MODEL_TRAINING_NOT_RUN" in state_dataset.blockers


def test_future_label_is_excluded_but_test_features_use_frozen_train_statistics(tmp_path: Path) -> None:
    score_dataset = _score_dataset(tmp_path)
    first = build_market_state_dataset(
        score_dataset,
        panel_csv_path=_panel(tmp_path / "first.csv", future_label="-0.9"),
    )
    second = build_market_state_dataset(
        score_dataset,
        panel_csv_path=_panel(tmp_path / "second.csv", future_label="0.9"),
    )
    shifted = build_market_state_dataset(
        score_dataset,
        panel_csv_path=_panel(
            tmp_path / "shifted.csv",
            future_label="0.9",
            test_multiplier=1000.0,
        ),
    )

    assert first.state_dataset_hash == second.state_dataset_hash
    assert first.source_panel_sha256 != second.source_panel_sha256
    assert first.statistics == shifted.statistics
    assert first.state_dataset_hash != shifted.state_dataset_hash
