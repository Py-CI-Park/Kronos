import hashlib
import json
import threading

import pytest

from stom_rl.daily_v8_custody import (
    H1_FIELDS,
    MANIFEST_FILENAME,
    CustodyAccessLedger,
    CustodyError,
    VerifiedEligibleGateReceipt,
    load_train_validation,
    open_test_once,
    write_partitioned_dataset,
)


class FakeSink:
    def __init__(self):
        self.parts = []
        self.closed = False

    def write(self, data):
        self.parts.append(data)

    def close(self):
        self.closed = True

    @property
    def data(self):
        return b"".join(self.parts)


def row(symbol, session, split, label=0.1):
    return {
        "symbol": symbol, "table": "T" + symbol, "session_yyyymmdd": session, "split": split,
        "ret_1d_prev": 0.0, "ret_5d_prev": 0.0, "ret_20d_prev": 0.0, "vol_z_20": 0.0,
        "foreign_ratio_prev": 0.0, "foreign_ratio_delta_5": 0.0, "inst_netbuy_norm_5": 0.0,
        "entry_close_1520": 10.0, "future_return_h1_1520_proxy": label, "label_reason_h1": None,
    }


def write_fixture(tmp_path, rows=None):
    sink = FakeSink()
    result = write_partitioned_dataset(
        rows or [row("000001", 20231229, "train"), row("000002", 20240102, "val"),
                 row("000003", 20250701, "test", 999.0), row("000004", 20250630, "embargo_dropped")],
        public_root=tmp_path, sealed_test_sink=sink, source_db_sha256="a" * 64,
        source_fivemin_db_sha256="b" * 64,
        custody_uid="custody-1", prereg_id="M3E-PREREG",
    )
    return result, sink


def resign_public_manifest(result):
    public_path = result["public_path"]
    manifest_path = result["manifest_path"]
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["public_artifact"]["sha256"] = hashlib.sha256(public_path.read_bytes()).hexdigest()
    payload["public_artifact"]["byte_length"] = public_path.stat().st_size
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")


def test_partitioning_occurs_before_public_serialization_and_hides_test_diagnostics(tmp_path):
    result, sink = write_fixture(tmp_path)
    public = result["public_path"].read_text(encoding="utf-8")
    manifest_text = result["manifest_path"].read_text(encoding="utf-8")
    assert "000003" not in public and "999.0" not in public and "000004" not in public
    assert "000003" in sink.data.decode("utf-8") and "999.0" in sink.data.decode("utf-8")
    assert "000003" not in manifest_text and "999.0" not in manifest_text
    assert "path" not in result["manifest"]["sealed_test_commitment"]
    assert load_train_validation(result["manifest_path"], tmp_path)[0]["symbol"] == "000001"


@pytest.mark.parametrize("mutator", ["traversal", "sha", "truncate", "duplicate", "boundary"])
def test_loader_rejects_public_artifact_tampering(tmp_path, mutator):
    result, _ = write_fixture(tmp_path)
    manifest_path = result["manifest_path"]
    public_path = result["public_path"]
    if mutator == "traversal":
        with pytest.raises(CustodyError):
            load_train_validation(tmp_path / "elsewhere" / MANIFEST_FILENAME, tmp_path)
        return
    if mutator == "sha":
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["public_artifact"]["sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    elif mutator == "truncate":
        public_path.write_bytes(public_path.read_bytes()[:-1])
    elif mutator == "duplicate":
        lines = public_path.read_text(encoding="utf-8").splitlines()
        public_path.write_text("\n".join([*lines, lines[1]]) + "\n", encoding="utf-8")
        resign_public_manifest(result)
    else:
        lines = public_path.read_text(encoding="utf-8").splitlines()
        parts = lines[1].split(",")
        parts[2] = "20250701"
        public_path.write_text("\n".join([lines[0], ",".join(parts), *lines[2:]]) + "\n", encoding="utf-8")
        resign_public_manifest(result)
    with pytest.raises(CustodyError):
        load_train_validation(manifest_path, tmp_path)


def test_loader_rejects_legacy_combined_and_symlink(tmp_path):
    result, _ = write_fixture(tmp_path)
    (tmp_path / "dataset.csv").write_text("do not open", encoding="utf-8")
    with pytest.raises(CustodyError, match="legacy"):
        load_train_validation(result["manifest_path"], tmp_path)
    (tmp_path / "dataset.csv").unlink()
    symlink_root = tmp_path / "symlink-root"
    symlink_root.mkdir()
    link = symlink_root / MANIFEST_FILENAME
    try:
        link.symlink_to(result["manifest_path"])
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(CustodyError):
        load_train_validation(link, symlink_root)


class Vault:
    def __init__(self, data, fail=False):
        self.data, self.fail, self.reads = data, fail, 0

    def read(self):
        self.reads += 1
        if self.fail:
            raise RuntimeError("vault unavailable")
        return self.data


def receipt():
    return VerifiedEligibleGateReceipt("b" * 64)


def test_open_test_burns_before_read_and_failure_cannot_retry(tmp_path):
    ledger = CustodyAccessLedger(tmp_path / "access.sqlite")
    data = b"sealed test bytes"
    digest = hashlib.sha256(data).hexdigest()
    failing = Vault(data, fail=True)
    with pytest.raises(RuntimeError):
        open_test_once(ledger=ledger, custody_uid="u", test_sha256=digest, receipt=receipt(), vault=failing)
    assert failing.reads == 1
    retry = Vault(data)
    with pytest.raises(Exception):
        open_test_once(ledger=ledger, custody_uid="u", test_sha256=digest, receipt=receipt(), vault=retry)
    assert retry.reads == 0


def test_open_test_concurrency_restart_and_replay_are_single_use(tmp_path):
    path = tmp_path / "access.sqlite"
    data = b"sealed test bytes"
    digest = hashlib.sha256(data).hexdigest()
    outcomes = []

    def attempt():
        try:
            open_test_once(ledger=CustodyAccessLedger(path), custody_uid="u", test_sha256=digest,
                           receipt=receipt(), vault=Vault(data))
            outcomes.append("opened")
        except CustodyError:
            outcomes.append("burned")

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["burned", "opened"]
    with pytest.raises(CustodyError):
        open_test_once(ledger=CustodyAccessLedger(path), custody_uid="new", test_sha256=digest,
                       receipt=receipt(), vault=Vault(data))


def test_writer_rejects_duplicate_and_wrong_boundary_without_public_output(tmp_path):
    with pytest.raises(CustodyError):
        write_fixture(tmp_path, [row("000001", 20231229, "train"), row("000001", 20231229, "train")])
    assert not (tmp_path / "train_validation.csv").exists()
    with pytest.raises(CustodyError):
        write_fixture(tmp_path, [row("000001", 20250701, "val")])
