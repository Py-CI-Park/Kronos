import json
from pathlib import Path

import pytest

from stom_rl.daily_v8_custody import write_partitioned_dataset
from stom_rl.daily_v8_m3e_run import (
    M3ERunError,
    PROTOCOL,
    build_validation_manifest,
    protocol_sha256,
    run_validation,
    trainer_sha256,
)


class Sink:
    def __init__(self):
        self.data = bytearray()
        self.closed = False

    def write(self, data):
        self.data.extend(data)

    def close(self):
        self.closed = True


def row(symbol, session, split, label):
    return {
        "symbol": symbol,
        "table": symbol,
        "session_yyyymmdd": session,
        "split": split,
        "ret_1d_prev": 0.01,
        "ret_5d_prev": 0.02,
        "ret_20d_prev": 0.03,
        "vol_z_20": 0.1,
        "foreign_ratio_prev": 0.2,
        "foreign_ratio_delta_5": 0.01,
        "inst_netbuy_norm_5": 0.02,
        "entry_close_1520": 1000.0,
        "future_return_h1_1520_proxy": label,
        "label_reason_h1": "",
    }


def frozen_prereg(custody):
    return {
        "prereg_id": "KRONOS-V8-PREREG-M3E-TEST",
        "status": "FROZEN",
        "source_contract": {
            "trainer_sha256": trainer_sha256(),
            "protocol_sha256": protocol_sha256(),
        },
        "dataset": {
            "custody_uid": custody["custody_uid"],
            "public_artifact_sha256": custody["public_artifact"]["sha256"],
            "sealed_test_sha256": custody["sealed_test_commitment"]["sha256"],
        },
    }


def create_custody(tmp_path):
    sink = Sink()
    rows = [
        row("000001", 20230102, "train", 0.02),
        row("000002", 20230103, "train", -0.01),
        row("000001", 20240102, "val", 0.01),
        row("000002", 20240102, "val", -0.02),
        row("000001", 20250701, "test", 99.0),
    ]
    result = write_partitioned_dataset(
        rows,
        public_root=tmp_path / "public",
        sealed_test_sink=sink,
        source_db_sha256="a" * 64,
        source_fivemin_db_sha256="b" * 64,
        custody_uid="m3e-test-custody",
        prereg_id="KRONOS-V8-PREREG-M3E-TEST",
    )
    prereg = tmp_path / "prereg.json"
    prereg.write_text(json.dumps(frozen_prereg(result["manifest"])), encoding="utf-8")
    return result, prereg, sink


def test_runner_loads_only_public_custody_and_keeps_test_not_run(tmp_path):
    custody, prereg, sink = create_custody(tmp_path)
    output = run_validation(
        custody["manifest_path"].parent,
        out_root=tmp_path / "runs",
        run_id="fixed",
        prereg_path=prereg,
    )
    manifest = output["manifest"]
    assert manifest["seeds"] == [0, 1, 2, 3, 4]
    assert manifest["policy"]["primary_cost_rate"] == 0.0023
    assert manifest["test"] == {"state": "NOT_RUN"}
    assert manifest["public_rows_loaded"] == 4
    assert b"99.0" in bytes(sink.data)
    assert "99.0" not in (output["output_dir"] / "run_manifest.json").read_text(encoding="utf-8")
    assert (output["output_dir"] / "events.jsonl").read_text(encoding="utf-8").count("NOT_RUN") == 1


def test_runner_rejects_unfrozen_or_changed_protocol_before_public_load(tmp_path):
    custody, prereg, _ = create_custody(tmp_path)
    payload = json.loads(prereg.read_text(encoding="utf-8"))
    payload["status"] = "DRAFT_NOT_FROZEN"
    prereg.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(M3ERunError, match="not frozen"):
        run_validation(custody["manifest_path"].parent, out_root=tmp_path / "runs", prereg_path=prereg)

    payload["status"] = "FROZEN"
    payload["source_contract"]["protocol_sha256"] = "0" * 64
    prereg.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(M3ERunError, match="trainer or protocol"):
        run_validation(custody["manifest_path"].parent, out_root=tmp_path / "runs", prereg_path=prereg)


def test_protocol_is_fixed_and_has_no_test_execution_switch():
    assert PROTOCOL["seeds"] == [0, 1, 2, 3, 4]
    assert PROTOCOL["aggregation"] == "unweighted_raw_member_score_mean_before_ranking_score_gt_0"
    assert PROTOCOL["test_state"] == "NOT_RUN"
    source = Path("stom_rl/daily_v8_m3e_run.py").read_text(encoding="utf-8")
    assert "--final-test" not in source
    assert "--dataset" not in source
