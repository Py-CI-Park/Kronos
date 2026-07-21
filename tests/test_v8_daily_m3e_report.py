import json
from pathlib import Path

import pytest

from stom_rl.daily_v8_custody import write_partitioned_dataset
from stom_rl.daily_v8_m3e_report import M3EReportError, build_report
from stom_rl.daily_v8_m3e_run import protocol_sha256, run_validation, trainer_sha256
from stom_rl.v5_oos_custody import canonical_bytes


class Sink:
    def __init__(self):
        self.data = bytearray()

    def write(self, data):
        self.data.extend(data)

    def close(self):
        pass


def _row(symbol, session, split, label):
    return {"symbol": symbol, "table": symbol, "session_yyyymmdd": session, "split": split,
            "ret_1d_prev": 0.01, "ret_5d_prev": 0.02, "ret_20d_prev": 0.03, "vol_z_20": 0.1,
            "foreign_ratio_prev": 0.2, "foreign_ratio_delta_5": 0.01, "inst_netbuy_norm_5": 0.02,
            "entry_close_1520": 1000.0, "future_return_h1_1520_proxy": label, "label_reason_h1": ""}


def _evidence(tmp_path: Path):
    custody = write_partitioned_dataset(
        [_row("000001", 20230102, "train", .02), _row("000002", 20230103, "train", -.01),
         _row("000001", 20240102, "val", .01), _row("000002", 20240102, "val", -.02),
         _row("000001", 20250701, "test", 99.0)],
        public_root=tmp_path / "public", sealed_test_sink=Sink(), source_db_sha256="a" * 64,
        source_fivemin_db_sha256="b" * 64, custody_uid="m3e-report-custody", prereg_id="M3E-REPORT",
    )
    manifest = custody["manifest"]
    prereg = {"prereg_id": "M3E-REPORT", "status": "FROZEN", "source_contract": {
        "trainer_sha256": trainer_sha256(), "protocol_sha256": protocol_sha256()}, "dataset": {
        "custody_uid": manifest["custody_uid"], "public_artifact_sha256": manifest["public_artifact"]["sha256"],
        "sealed_test_sha256": manifest["sealed_test_commitment"]["sha256"]}}
    prereg_path = tmp_path / "prereg.json"
    prereg_path.write_bytes(canonical_bytes(prereg))
    output = run_validation(custody["manifest_path"].parent, out_root=tmp_path / "runs", run_id="fixed", prereg_path=prereg_path)
    return output["output_dir"], prereg_path, custody["manifest_path"]


def test_builds_truthful_self_contained_evidence(tmp_path):
    run_dir, prereg, custody = _evidence(tmp_path)
    receipt = build_report(run_dir, prereg, custody)
    report = (run_dir / "report.html").read_text(encoding="utf-8")
    assert receipt["test_state"] == "NOT_RUN"
    assert receipt["report_sha256"]
    assert (run_dir / "report_manifest.json").read_bytes() == canonical_bytes(receipt)
    for label in ("Overview", "Policy &amp; Environment", "Ensemble/Jackknives", "Baselines &amp; Controls", "Custody", "Appendix"):
        assert label in report
    for text in ("NO_GO", "NOT_RUN", "0 / 23 / 46 bp", "0.23%", "60M fixed-notional", "0–10 optional slots", "M1 INCONCLUSIVE", "M2 NO_GO", "M3 INCONCLUSIVE", "reused validation"):
        assert text in report
    assert "<svg" in report and "<script" not in report and "https://" not in report
    (run_dir / "report.html").write_text("tampered", encoding="utf-8")
    with pytest.raises(M3EReportError, match="immutable"):
        build_report(run_dir, prereg, custody)


@pytest.mark.parametrize("change", ["run", "prereg", "custody", "test", "lock", "verdict"])
def test_rejects_tampered_public_evidence(tmp_path, change):
    run_dir, prereg_path, custody_path = _evidence(tmp_path)
    if change == "run":
        payload = json.loads((run_dir / "run_manifest.json").read_text())
        payload["ensemble"]["metrics"]["nav"] += 1
        (run_dir / "run_manifest.json").write_bytes(canonical_bytes(payload))
    elif change == "prereg":
        payload = json.loads(prereg_path.read_text())
        payload["prereg_id"] = "OTHER"
        prereg_path.write_bytes(canonical_bytes(payload))
    elif change == "custody":
        payload = json.loads(custody_path.read_text())
        payload["public_artifact"]["sha256"] = "f" * 64
        custody_path.write_text(json.dumps(payload), encoding="utf-8")
    elif change == "test":
        payload = json.loads((run_dir / "run_manifest.json").read_text())
        payload["test"] = {"state": "RUN"}
        (run_dir / "run_manifest.json").write_bytes(canonical_bytes(payload))
    elif change == "lock":
        payload = json.loads((run_dir / "run_manifest.json").read_text())
        payload["false_research_locks"]["promotion_allowed"] = True
        (run_dir / "run_manifest.json").write_bytes(canonical_bytes(payload))
    else:
        payload = json.loads((run_dir / "run_manifest.json").read_text())
        payload["verdict"]["value"] = "GO"
        (run_dir / "run_manifest.json").write_bytes(canonical_bytes(payload))
    with pytest.raises(M3EReportError):
        build_report(run_dir, prereg_path, custody_path)
