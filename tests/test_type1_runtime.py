"""Focused replay, custody, and CLI tests for the Type 1 evidence runtime."""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "type1_runtime.py"
SPEC = importlib.util.spec_from_file_location("type1_runtime", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def _file(root: Path, name: str, contents: str = "evidence") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    return path


def _inputs(root: Path, phase_id: str) -> tuple[Path, Path, Path, Path]:
    return (_file(root, "prereg.json", '{"status":"BLOCKED","rfc3161":"ABSENT"}'),
            _file(root, f"source/{phase_id}.py"), _file(root, "runtime-type1.json", '{"attestation":"LOCAL_ONLY"}'),
            _file(root, f"outputs/{phase_id}.txt"))


def _phase(root: Path, phase_id: str, priors: list[tuple[Path, Path]] | None = None) -> tuple[Path, Path, Path, Path]:
    prereg, source, runtime_input, owned = _inputs(root, phase_id)
    prior_paths = [item[0] for item in priors or []]
    prior_manifests = [item[1] for item in priors or []]
    instance = runtime.build_phase_instance(phase_id, root, prior_paths=prior_paths, prior_manifest_paths=prior_manifests,
                                            prereg_inputs=[prereg], source_inputs=[source], runtime_inputs=[runtime_input], owned_outputs=[owned])
    instance_path = root / f"{phase_id}-instance.json"
    runtime.write_new_json(instance_path, instance)
    capture = runtime.capture_test(instance, root, [sys.executable, "-c", "pass"])
    capture_path = root / f"{phase_id}-capture.json"
    runtime.write_new_json(capture_path, capture)
    receipt = runtime.build_test_receipt(instance, root, capture_path)
    receipt_path = root / f"{phase_id}-receipt.json"
    runtime.write_new_json(receipt_path, receipt)
    manifest_path = root / "manifests" / f"{phase_id}.json"
    runtime.write_new_json(manifest_path, runtime.build_manifest(instance, receipt, root, instance_path, receipt_path, manifest_path))
    runtime.verify_manifest(runtime.read_json(manifest_path), manifest_path)
    return instance_path, capture_path, receipt_path, manifest_path


def test_canonicalization_is_key_order_independent_and_rejects_nan() -> None:
    assert runtime.canonical_json_bytes({"b": "한글", "a": 1}) == b'{"a":1,"b":"\xed\x95\x9c\xea\xb8\x80"}'
    with pytest.raises(runtime.ValidationError, match="canonical JSON"):
        runtime.canonical_json_bytes(float("nan"))


def test_complete_frozen_matrix_rejects_every_custody_mutation() -> None:
    matrix_path = Path(__file__).parents[1] / "docs" / "kronos_type1_phase_matrix_v1.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    assert matrix == runtime.approved_phase_matrix()
    runtime.validate_phase_matrix(matrix)
    for field, value in (
        ("schema_version", "future"),
        ("protocol_id", "other"),
        ("ordering_rule", "weakened"),
    ):
        changed = copy.deepcopy(matrix)
        changed[field] = value
        with pytest.raises(runtime.ValidationError, match="complete frozen"):
            runtime.validate_phase_matrix(changed)
    for field, value in (
        ("freeze_start", "2026-08-04"),
        ("freeze_end", "2027-08-01"),
        ("status", "RUN"),
        ("access", "ALLOWED"),
    ):
        changed = copy.deepcopy(matrix)
        changed["fresh_oos"][field] = value
        with pytest.raises(runtime.ValidationError, match="complete frozen"):
            runtime.validate_phase_matrix(changed)
    for field, value in (("id", "P99"), ("purpose", "changed"), ("depends_on", [])):
        changed = copy.deepcopy(matrix)
        changed["phases"][1][field] = value
        with pytest.raises(runtime.ValidationError, match="complete frozen"):
            runtime.validate_phase_matrix(changed)
    changed = copy.deepcopy(matrix)
    changed["phases"][0]["future_output_sha256"] = "0" * 64
    with pytest.raises(runtime.ValidationError, match="complete frozen"):
        runtime.validate_phase_matrix(changed)


def test_capture_and_receipt_exact_schema_and_custody_fields_fail_closed(tmp_path: Path) -> None:
    instance_path, capture_path, receipt_path, _ = _phase(tmp_path, "P0a")
    instance, capture, receipt = map(runtime.read_json, (instance_path, capture_path, receipt_path))
    for field, value in (("schema_version", "future"), ("phase_id", "P1"), ("phase_instance_sha256", "0" * 64),
                         ("exit_code", 1), ("status", "FAIL"), ("stdout", 1), ("stderr", 1),
                         ("source_inputs", []), ("runtime_inputs", []), ("owned_outputs", [])):
        changed = copy.deepcopy(capture); changed[field] = value
        with pytest.raises(runtime.ValidationError):
            runtime.validate_test_capture(changed, instance, tmp_path)
    for changed in ({**capture, "future": True}, {key: value for key, value in capture.items() if key != "stderr"}):
        with pytest.raises(runtime.ValidationError):
            runtime.validate_test_capture(changed, instance, tmp_path)
    for argv in ([], ["",], [1], "not-a-list"):
        changed = copy.deepcopy(capture); changed["argv"] = argv
        with pytest.raises(runtime.ValidationError, match="argv"):
            runtime.validate_test_capture(changed, instance, tmp_path)
    forged = {key: value for key, value in receipt.items() if key not in {"test_capture_path", "test_capture_sha256"}}
    with pytest.raises(runtime.ValidationError):
        runtime.validate_test_receipt(forged, instance, tmp_path)
    for changed in ({**receipt, "future": True}, {key: value for key, value in receipt.items() if key != "status"}):
        with pytest.raises(runtime.ValidationError):
            runtime.validate_test_receipt(changed, instance, tmp_path)
    for field, value in (("schema_version", "future"), ("phase_id", "P1"), ("phase_instance_sha256", "0" * 64),
                         ("argv", ["forged"]), ("exit_code", 1), ("status", "FAIL"), ("test_capture_sha256", "0" * 64),
                         ("source_inputs", []), ("runtime_inputs", []), ("owned_outputs", [])):
        changed = copy.deepcopy(receipt); changed[field] = value
        with pytest.raises(runtime.ValidationError):
            runtime.validate_test_receipt(changed, instance, tmp_path)
    for path in (str(capture_path), "../capture.json"):
        changed = copy.deepcopy(receipt); changed["test_capture_path"] = path
        with pytest.raises(runtime.ValidationError):
            runtime.validate_test_receipt(changed, instance, tmp_path)
    changed = copy.deepcopy(capture); changed["argv"] = ["forged"]
    capture_path.write_text(runtime.canonical_json_bytes(changed).decode("utf-8"), encoding="utf-8")
    with pytest.raises(runtime.ValidationError, match="stale test capture bytes"):
        runtime.validate_test_receipt(receipt, instance, tmp_path)
    _file(tmp_path, "outputs/P0a.txt", "changed")
    with pytest.raises(runtime.ValidationError, match="stale"):
        runtime.validate_test_receipt(receipt, instance, tmp_path)


def test_downstream_requires_verified_exact_direct_prior_manifest(tmp_path: Path) -> None:
    p0a_instance, _, _, p0a_manifest = _phase(tmp_path, "P0a")
    prereg, source, runtime_input, owned = _inputs(tmp_path, "P0")
    with pytest.raises(runtime.ValidationError, match="instances and manifests"):
        runtime.build_phase_instance("P0", tmp_path, prior_paths=[p0a_instance], prior_manifest_paths=[], prereg_inputs=[prereg], source_inputs=[source], runtime_inputs=[runtime_input], owned_outputs=[owned])
    stale = runtime.read_json(p0a_manifest); stale["phase_instance_sha256"] = "0" * 64
    bad_manifest = tmp_path / "bad-manifest.json"; runtime.write_new_json(bad_manifest, stale)
    with pytest.raises(runtime.ValidationError):
        runtime.build_phase_instance("P0", tmp_path, prior_paths=[p0a_instance], prior_manifest_paths=[bad_manifest], prereg_inputs=[prereg], source_inputs=[source], runtime_inputs=[runtime_input], owned_outputs=[owned])
    p0_instance, _, _, p0_manifest = _phase(tmp_path, "P0", [(p0a_instance, p0a_manifest)])
    assert runtime.read_json(p0_manifest)["phase_instance_path"] == p0_instance.name


def test_path_tamper_and_self_reference_fail_closed(tmp_path: Path) -> None:
    instance_path, capture_path, receipt_path, manifest_path = _phase(tmp_path, "P0a")
    instance = runtime.read_json(instance_path); instance["test_capture_path"] = capture_path.name
    with pytest.raises(runtime.ValidationError, match="own/future"):
        runtime.validate_phase_instance(instance, tmp_path)
    manifest = runtime.read_json(manifest_path); manifest["phase_instance_path"] = "../escaped.json"
    with pytest.raises(runtime.ValidationError, match="escapes"):
        runtime.verify_manifest(manifest, manifest_path)
    manifest = runtime.read_json(manifest_path); manifest["test_receipt_path"] = "manifests/P0a.json"
    with pytest.raises(runtime.ValidationError, match="self reference"):
        runtime.verify_manifest(manifest, manifest_path)
    receipt = runtime.read_json(receipt_path); receipt["test_capture_path"] = receipt_path.name
    with pytest.raises(runtime.ValidationError):
        runtime.validate_test_receipt(receipt, runtime.read_json(instance_path), tmp_path)


def test_cli_e2e_instance_capture_receipt_manifest_and_downstream_gate(tmp_path: Path) -> None:
    script = str(MODULE_PATH)
    prereg, source, runtime_input, owned = _inputs(tmp_path, "P0a")
    base = [sys.executable, script, "create-phase-instance", "--root", str(tmp_path), "--phase", "P0a", "--prereg-input", str(prereg), "--source-input", str(source), "--runtime-input", str(runtime_input), "--owned-output", str(owned), "--output", "P0a.json"]
    assert subprocess.run(base, capture_output=True, text=True).returncode == 0
    capture = [sys.executable, script, "capture-test", "--root", str(tmp_path), "--phase-instance", str(tmp_path / "P0a.json"), "--argv", sys.executable, "--argv=-c", "--argv", "pass", "--output", "capture.json"]
    assert subprocess.run(capture, capture_output=True, text=True).returncode == 0
    receipt = [sys.executable, script, "create-test-receipt", "--root", str(tmp_path), "--phase-instance", str(tmp_path / "P0a.json"), "--test-capture", str(tmp_path / "capture.json"), "--output", "receipt.json"]
    assert subprocess.run(receipt, capture_output=True, text=True).returncode == 0
    manifest = [sys.executable, script, "create-manifest", "--root", str(tmp_path), "--phase-instance", str(tmp_path / "P0a.json"), "--test-receipt", str(tmp_path / "receipt.json"), "--output", "manifest.json"]
    assert subprocess.run(manifest, capture_output=True, text=True).returncode == 0
    assert subprocess.run([sys.executable, script, "verify-manifest", "--manifest", str(tmp_path / "manifest.json")], capture_output=True, text=True).returncode == 0
    prereg, source, runtime_input, owned = _inputs(tmp_path, "P0")
    gated = [sys.executable, script, "create-phase-instance", "--root", str(tmp_path), "--phase", "P0", "--prior-instance", str(tmp_path / "P0a.json"), "--prereg-input", str(prereg), "--source-input", str(source), "--runtime-input", str(runtime_input), "--owned-output", str(owned), "--output", "P0.json"]
    assert subprocess.run(gated, capture_output=True, text=True).returncode == 2
    gated.extend(["--prior-manifest", str(tmp_path / "manifest.json")])
    assert subprocess.run(gated, capture_output=True, text=True).returncode == 0


def test_create_new_runtime_lock_and_m3e_inventory_receipt_fail_closed(tmp_path: Path) -> None:
    output = tmp_path / "new.json"; runtime.write_new_json(output, {"first": True})
    with pytest.raises(runtime.ValidationError, match="refusing to overwrite"):
        runtime.write_new_json(output, {"second": True})
    lock = json.loads((Path(__file__).parents[1] / "runtime-type1.json").read_text(encoding="utf-8"))
    requirements = Path(__file__).parents[1] / "requirements-type1.lock"
    runtime.validate_runtime_lock(lock, requirements)
    for field, value in (("schema_version", "future"), ("attestation", "external"), ("implementation", "PyPy"),
                         ("python_version", "0"), ("platform", "linux"), ("executable_name", "other.exe"),
                         ("executable_sha256", "0" * 64), ("dependency_lock", "other.lock"),
                         ("dependency_lock_sha256", "0" * 64), ("dependencies", [])):
        changed = copy.deepcopy(lock); changed[field] = value
        with pytest.raises(runtime.ValidationError):
            runtime.validate_runtime_lock(changed, requirements)
    for changed in ({**lock, "future": True}, {key: value for key, value in lock.items() if key != "platform"}):
        with pytest.raises(runtime.ValidationError):
            runtime.validate_runtime_lock(changed, requirements)
    aliases = tmp_path / "aliases.lock"
    aliases.write_text("foo-bar==1\nfoo_bar==1\nfoo.bar==1\n", encoding="utf-8")
    with pytest.raises(runtime.ValidationError, match="duplicates"):
        runtime._requirements(aliases)
    inventory = _file(tmp_path, "m3e-inventory.json", "existing hash inventory only")
    receipt = runtime.build_m3e_inventory_receipt(inventory, tmp_path)
    assert receipt == {
        "schema_version": runtime.M3E_INVENTORY_RECEIPT_SCHEMA,
        "status": "NO_TOUCH_INVENTORY_ONLY",
        "fresh_oos_status": "NOT_RUN",
        "inventory_path": "m3e-inventory.json",
        "inventory_sha256": runtime.sha256_file(inventory),
        "statement": "This receipt binds an existing local M3E inventory only; it does not open, read, evaluate, or attest fresh OOS.",
    }
    runtime.validate_m3e_inventory_receipt(receipt, inventory, tmp_path)
    for field, value in (("schema_version", "future"), ("status", "TOUCHED"), ("fresh_oos_status", "RUN"),
                         ("inventory_path", "../inventory.json"), ("inventory_sha256", "0" * 64), ("statement", "changed")):
        changed = copy.deepcopy(receipt); changed[field] = value
        with pytest.raises(runtime.ValidationError):
            runtime.validate_m3e_inventory_receipt(changed, inventory, tmp_path)
    for changed in ({**receipt, "future": True}, {key: value for key, value in receipt.items() if key != "statement"}):
        with pytest.raises(runtime.ValidationError):
            runtime.validate_m3e_inventory_receipt(changed, inventory, tmp_path)
    _file(tmp_path, "m3e-inventory.json", "changed")
    with pytest.raises(runtime.ValidationError):
        runtime.validate_m3e_inventory_receipt(receipt, inventory, tmp_path)
    missing = tmp_path / "missing-inventory.json"
    with pytest.raises(runtime.ValidationError):
        runtime.build_m3e_inventory_receipt(missing, tmp_path)
    outside = _file(tmp_path.parent, f"{tmp_path.name}-outside-inventory.json")
    with pytest.raises(runtime.ValidationError, match="escapes"):
        runtime.build_m3e_inventory_receipt(outside, tmp_path)
def test_capture_streams_bounded_multibyte_and_invalid_byte_diagnostics(tmp_path: Path) -> None:
    instance_path, _, _, _ = _phase(tmp_path, "P0a")
    instance = runtime.read_json(instance_path)
    argv = [sys.executable, "-c", (
        "import sys; "
        "sys.stdout.buffer.write(b'a' * 4095 + '€'.encode() + b'tail'); "
        "sys.stderr.buffer.write(b'\\xff' + b'b' * 5000)"
    )]
    capture = runtime.capture_test(instance, tmp_path, argv)
    assert capture["status"] == "PASS"
    assert capture["stdout"] == "a" * 4095
    assert capture["stderr"] == "�" + "b" * (runtime.MAX_DIAGNOSTIC_BYTES - 3)
    assert len(capture["stdout"].encode("utf-8")) <= runtime.MAX_DIAGNOSTIC_BYTES
    assert len(capture["stderr"].encode("utf-8")) == runtime.MAX_DIAGNOSTIC_BYTES
    changed = copy.deepcopy(capture); changed["stdout"] = "€" * (runtime.MAX_DIAGNOSTIC_BYTES // 3 + 1)
    with pytest.raises(runtime.ValidationError, match="bounded"):
        runtime.validate_test_capture(changed, instance, tmp_path)
    runtime.validate_test_capture(capture, instance, tmp_path)


def test_capture_drains_large_outputs_without_retaining_unbounded_diagnostics(tmp_path: Path) -> None:
    instance_path, _, _, _ = _phase(tmp_path, "P0a")
    instance = runtime.read_json(instance_path)
    capture = runtime.capture_test(instance, tmp_path, [sys.executable, "-c", (
        "import sys; "
        "sys.stdout.buffer.write(b'x' * (2 * 1024 * 1024)); "
        "sys.stderr.buffer.write(b'y' * (2 * 1024 * 1024))"
    )])
    assert capture["stdout"] == "x" * runtime.MAX_DIAGNOSTIC_BYTES
    assert capture["stderr"] == "y" * runtime.MAX_DIAGNOSTIC_BYTES
    assert len(capture["stdout"].encode("utf-8")) == runtime.MAX_DIAGNOSTIC_BYTES
    assert len(capture["stderr"].encode("utf-8")) == runtime.MAX_DIAGNOSTIC_BYTES

def test_failing_capture_is_persisted_with_bounded_diagnostics_and_rejects_receipt(tmp_path: Path) -> None:
    instance_path, _, _, _ = _phase(tmp_path, "P0a")
    capture_path = tmp_path / "failed-capture.json"
    command = [sys.executable, str(MODULE_PATH), "capture-test", "--root", str(tmp_path),
               "--phase-instance", str(instance_path), "--argv", sys.executable, "--argv=-c",
               "--argv", "import sys; print('stdout diagnostic'); print('stderr diagnostic', file=sys.stderr); raise SystemExit(7)",
               "--output", capture_path.name]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert "stdout diagnostic" in result.stdout
    assert "stderr diagnostic" in result.stdout
    capture = runtime.read_json(capture_path)
    assert capture["status"] == "FAIL"
    assert capture["exit_code"] == 7
    assert capture["stdout"] == "stdout diagnostic\n"
    assert capture["stderr"] == "stderr diagnostic\n"
    assert len(capture["stdout"]) <= runtime.MAX_DIAGNOSTIC_BYTES
    assert len(capture["stderr"]) <= runtime.MAX_DIAGNOSTIC_BYTES
    receipt_path = tmp_path / "failed-receipt.json"
    receipt = [sys.executable, str(MODULE_PATH), "create-test-receipt", "--root", str(tmp_path),
               "--phase-instance", str(instance_path), "--test-capture", str(capture_path),
               "--output", receipt_path.name]
    assert subprocess.run(receipt, capture_output=True, text=True).returncode == 2
    assert not receipt_path.exists()


def test_every_root_scoped_create_command_rejects_output_escapes_before_write(tmp_path: Path) -> None:
    instance_path, capture_path, receipt_path, _ = _phase(tmp_path, "P0a")
    prereg, source, runtime_input, owned = _inputs(tmp_path, "P0a")
    inventory = _file(tmp_path, "inventory.json")
    commands = [
        ["create-m3e-inventory-receipt", "--root", str(tmp_path), "--inventory", str(inventory)],
        ["create-phase-instance", "--root", str(tmp_path), "--phase", "P0a", "--prereg-input", str(prereg),
         "--source-input", str(source), "--runtime-input", str(runtime_input), "--owned-output", str(owned)],
        ["capture-test", "--root", str(tmp_path), "--phase-instance", str(instance_path), "--argv", sys.executable,
         "--argv=-c", "--argv", "pass"],
        ["create-test-receipt", "--root", str(tmp_path), "--phase-instance", str(instance_path),
         "--test-capture", str(capture_path)],
        ["create-manifest", "--root", str(tmp_path), "--phase-instance", str(instance_path),
         "--test-receipt", str(receipt_path)],
    ]
    escaped_name = f"{tmp_path.name}-escaped.json"
    for command in commands:
        assert runtime.main([*command, "--output", f"../{escaped_name}"]) == 2
    assert not (tmp_path.parent / escaped_name).exists()
    with pytest.raises(runtime.ValidationError, match="relative"):
        runtime._root_output(tmp_path, tmp_path.parent / f"{tmp_path.name}-absolute.json")
    outside = tmp_path.parent / f"{tmp_path.name}-symlink-target"
    outside.mkdir()
    escape = tmp_path / "escape-link"
    escape.symlink_to(outside, target_is_directory=True)
    with pytest.raises(runtime.ValidationError, match="escapes"):
        runtime._root_output(tmp_path, Path("escape-link") / "record.json")
    assert not (outside / "record.json").exists()
