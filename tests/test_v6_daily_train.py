from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from stom_rl.daily_v6_dataset import CSV_FIELDS
from stom_rl.daily_v6_train import CAPITAL, compute_bucket_boundaries, load_dataset, run_training


def _write_dataset(root: Path, run_id: str, poison_val: bool = False) -> None:
    directory = root / run_id
    directory.mkdir(parents=True)
    rows = []
    for day in range(30):
        split = "train" if day < 20 else "val" if day < 25 else "test"
        for symbol_index, symbol in enumerate(("AAA", "BBB", "CCC")):
            ret5 = (-0.02, 0.01, 0.03)[symbol_index]
            if poison_val and split == "val":
                ret5 = 1_000_000.0 + symbol_index
            row = {field: "" for field in CSV_FIELDS}
            row.update({"symbol": symbol, "table": symbol, "session_yyyymmdd": str(20230101 + day), "split": split,
                        "ret_1d_prev": str(ret5 / 2), "ret_5d_prev": str(ret5), "ret_20d_prev": str(ret5 / 3),
                        "vol_z_20": str((-1.0, 0.0, 1.0)[symbol_index]), "foreign_ratio_prev": "0.1",
                        "foreign_ratio_delta_5": str((-1.0, 0.0, 1.0)[symbol_index]),
                        "inst_netbuy_norm_5": str((-2.0, 0.0, 2.0)[symbol_index]), "entry_close_1520": "100",
                        "future_return_h1_1520_proxy": str((-0.01, 0.005, 0.02)[symbol_index]),
                        "label_reason_h1": "", "label_reason_h3": "", "label_reason_h5": ""})
            rows.append(row)
    csv_path = directory / "dataset.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    (directory / "dataset_manifest.json").write_text(json.dumps({"schema_version": "kronos_v6_joined_dataset.v1", "dataset_sha256": digest}), encoding="utf-8")


def _without_timestamp(manifest: dict) -> dict:
    copy = dict(manifest)
    copy.pop("generated_utc")
    return copy


def test_v6_train_preregistered_accounting_and_determinism(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    _write_dataset(root, "clean")
    _write_dataset(root, "poisoned", poison_val=True)
    clean = load_dataset("clean", root)
    poisoned = load_dataset("poisoned", root)
    clean_train = [row for row in clean["rows"] if row["split"] == "train"]
    poisoned_train = [row for row in poisoned["rows"] if row["split"] == "train"]
    assert compute_bucket_boundaries(clean_train) == compute_bucket_boundaries(poisoned_train)

    first = run_training("clean", seeds=(0,), smoke=True, out_root=root, train_run_id="one")
    second = run_training("clean", seeds=(0,), smoke=True, out_root=root, train_run_id="two")
    one, two = first["manifest"], second["manifest"]
    assert _without_timestamp(one) == _without_timestamp(two)
    assert one["baselines"]["no_trade"]["nav"] == CAPITAL
    navs = one["per_seed"]["0"]["final_val_metrics"]["cost_scenario_navs"]
    assert navs["0.0000"] >= navs["0.0023"] >= navs["0.0046"]
    assert one["test"] == {"state": "NOT_RUN"}
    control = one["shuffled_label_control"]["0"]
    assert control["train_labels_changed"]
    assert control["train_labels_sha256"] != control["shuffled_train_labels_sha256"]
    metrics = one["per_seed"]["0"]["final_val_metrics"]
    assert metrics["max_positions_per_session"] <= 10
    assert metrics["max_invested_krw"] <= 50_000_000
    assert navs["0.0000"] >= CAPITAL
