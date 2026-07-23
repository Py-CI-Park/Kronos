"""Create-new, replay-safe local evidence records for Type 1 research phases."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Mapping, Sequence

PHASE_INSTANCE_SCHEMA = "kronos_type1_phase_instance.v2"
TEST_CAPTURE_SCHEMA = "kronos_type1_test_capture.v2"
TEST_RECEIPT_SCHEMA = "kronos_type1_test_receipt.v2"
MANIFEST_SCHEMA = "kronos_type1_manifest.v2"
RUNTIME_LOCK_SCHEMA = "kronos_type1_runtime.v2"
M3E_INVENTORY_RECEIPT_SCHEMA = "kronos_type1_m3e_inventory_receipt.v1"
MAX_DIAGNOSTIC_BYTES = 4096
PHASE_PRIORS = {
    "P0a": (), "P0": ("P0a",), "P1": ("P0a",), "P2": ("P0a", "P0"),
    "P3": ("P0a", "P0"), "P4": ("P0a", "P0", "P2", "P3"),
    "P5": ("P0a", "P0", "P1", "P2", "P3", "P4"),
    "P6": ("P0a", "P0", "P1", "P2", "P3", "P4", "P5"),
    "P7": ("P0a", "P0", "P2", "P3", "P4", "P5", "P6"),
    "P8": ("P0a", "P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"),
    "P9": ("P0a", "P1", "P6", "P8"), "P10": ("P0a", "P1", "P6", "P8", "P9"),
    "P11": ("P0a", "P1", "P6", "P8", "P10"), "P12": ("P0a", "P1", "P6", "P8", "P11"),
    "P13": ("P0a", "P1", "P6", "P8", "P12"), "P14": ("P0a", "P1", "P6", "P8", "P13"),
    "P15": ("P0a", "P1", "P6", "P8", "P14"),
    "P16": ("P0a", "P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11", "P12", "P13", "P14", "P15"),
}
PHASE_MATRIX_SCHEMA = "kronos_type1_phase_matrix.v1"
PHASE_MATRIX_PROTOCOL = "KRONOS-TYPE1-CLOSING-2026-07-23"
PHASE_MATRIX_ORDERING_RULE = (
    "A phase may begin only after every listed dependency has a PASS test receipt and a verified manifest. "
    "Dependencies point only to earlier phases. This matrix intentionally contains no output hashes, receipts, "
    "manifests, or predicted artifact digests."
)
PHASE_MATRIX_FRESH_OOS = {
    "freeze_start": "2026-08-03",
    "freeze_end": "2027-07-30",
    "status": "NOT_RUN",
    "access": "FORBIDDEN",
}
PHASE_PURPOSES = {
    "P0a": "Freeze this preregistration and phase graph.",
    "P0": "Validate canonical JSON, receipt, and manifest runtime wiring.",
    "P1": "Verify exact 15:20 source custody and leading-zero symbols.",
    "P2": "Build chronological causal training and validation partitions without fresh OOS.",
    "P3": "Validate fixed-notional ten-slot accounting at 23bp and 0/46bp controls.",
    "P4": "Define and validate action masks for cash, slot, duplicate, and missing-bar constraints.",
    "P5": "Exercise environment wiring on synthetic fixtures only.",
    "P6": "Specify frozen baselines and shuffled-label control contracts.",
    "P7": "Run bounded historical plumbing smoke only after separate approval.",
    "P8": "Review smoke integrity, not model quality or promotion.",
    "P9": "Run preregistered validation experiments with identical configuration seeds.",
    "P10": "Evaluate frozen validation comparisons and controls.",
    "P11": "Record a validation stop, NO_GO, or separate eligibility decision.",
    "P12": "Prepare an independently approved fresh-OOS custody gate; do not access OOS.",
    "P13": "One-time fresh-OOS evaluation only under a separate approved gate.",
    "P14": "Reconcile OOS results, controls, uncertainty, and manifests.",
    "P15": "Record research verdict; failure remains NO_GO or INCONCLUSIVE.",
    "P16": "Archive immutable research evidence; this is not a live-trading authorization.",
}
FORBIDDEN_INSTANCE_TERMS = ("receipt", "manifest", "capture", "self")


class ValidationError(ValueError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"value is not canonical JSON: {exc}") from exc


def sha256_canonical(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError as exc:
        raise ValidationError(f"cannot hash {path}: {exc}") from exc


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read JSON {path}: {exc}") from exc


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be a JSON object")
    return value


def _string(record: Mapping[str, Any], field: str, label: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label}.{field} must be a non-empty string")
    return value


def _exact_keys(record: Mapping[str, Any], keys: set[str], label: str) -> None:
    if set(record) != keys:
        raise ValidationError(f"{label} has unknown, missing, or future keys")


def _safe_path(root: Path, value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise ValidationError(f"{label} must be a relative path")
    resolved_root, resolved = root.resolve(), (root / path).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValidationError(f"{label} escapes evidence root") from exc
    return resolved
def _root_output(root: Path, output: Path) -> Path:
    if output.is_absolute():
        raise ValidationError("output must be a relative path beneath evidence root")
    if ".." in output.parts:
        raise ValidationError("output must not contain traversal")
    return _safe_path(root, str(output), "output")



def _file_binding(path: Path, root: Path) -> dict[str, str]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationError(f"input path escapes evidence root: {path}") from exc
    if not resolved.is_file():
        raise ValidationError(f"bound file does not exist: {path}")
    return {"path": relative.as_posix(), "sha256": sha256_file(resolved)}


def _validate_bindings(value: Any, root: Path, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValidationError(f"{label} must be a non-empty list")
    result, seen = [], set()
    for item in value:
        record = _mapping(item, label)
        _exact_keys(record, {"path", "sha256"}, label)
        path_text, expected = _string(record, "path", label), _string(record, "sha256", label)
        if path_text in seen:
            raise ValidationError(f"{label} contains duplicate path: {path_text}")
        seen.add(path_text)
        path = _safe_path(root, path_text, label)
        if not path.is_file() or sha256_file(path) != expected:
            raise ValidationError(f"{label} has stale bytes: {path_text}")
        result.append(record)
    return result


def approved_phase_matrix() -> dict[str, Any]:
    return {
        "schema_version": PHASE_MATRIX_SCHEMA,
        "protocol_id": PHASE_MATRIX_PROTOCOL,
        "ordering_rule": PHASE_MATRIX_ORDERING_RULE,
        "fresh_oos": PHASE_MATRIX_FRESH_OOS,
        "phases": [
            {"id": phase, "depends_on": list(priors), "purpose": PHASE_PURPOSES[phase]}
            for phase, priors in PHASE_PRIORS.items()
        ],
    }


def validate_phase_matrix(matrix: Any) -> None:
    record = _mapping(matrix, "phase matrix")
    frozen = approved_phase_matrix()
    if record != frozen:
        raise ValidationError("phase matrix differs from the complete frozen schema, protocol, order, purposes, allowed keys, or fresh-OOS status")


def _forbid_instance_future_references(record: Mapping[str, Any]) -> None:
    forbidden_directories = {"test-receipts", "phase-manifests", "test-captures"}
    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if not isinstance(key, str):
                    raise ValidationError("phase instance keys must be strings")
                if key not in {"path", "manifest_path", "manifest_sha256"} and any(term in key.lower() for term in FORBIDDEN_INSTANCE_TERMS):
                    raise ValidationError("phase instance must not reference own/future receipt, manifest, capture, or self")
                if key == "path" and isinstance(nested, str) and {part.lower() for part in Path(nested).parts}.intersection(forbidden_directories):
                    raise ValidationError("phase instance must not consume test receipts, phase manifests, or test captures")
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)
    walk(record)


def _verify_prior_manifest(prior: Mapping[str, Any], root: Path, expected_id: str) -> None:
    _exact_keys(prior, {"phase_id", "path", "sha256", "manifest_path", "manifest_sha256"}, "prior instance")
    if prior.get("phase_id") != expected_id:
        raise ValidationError("phase instance prior order is not approved")
    instance_path = _safe_path(root, _string(prior, "path", "prior instance"), "prior instance.path")
    instance = read_json(instance_path)
    if sha256_canonical(instance) != _string(prior, "sha256", "prior instance"):
        raise ValidationError("phase instance prior has stale bytes")
    manifest_path = _safe_path(root, _string(prior, "manifest_path", "prior instance"), "prior instance.manifest_path")
    manifest = read_json(manifest_path)
    if sha256_canonical(manifest) != _string(prior, "manifest_sha256", "prior instance"):
        raise ValidationError("phase instance prior manifest has stale bytes")
    verify_manifest(manifest, manifest_path)
    if (manifest.get("phase_id") != expected_id or manifest.get("phase_instance_path") != prior["path"]
            or manifest.get("phase_instance_sha256") != prior["sha256"]):
        raise ValidationError("phase instance prior manifest has wrong producer or instance binding")


def validate_phase_instance(instance: Any, root: Path | None = None) -> Mapping[str, Any]:
    record = _mapping(instance, "phase instance")
    _forbid_instance_future_references(record)
    _exact_keys(record, {"schema_version", "phase_id", "prior_instances", "prereg_inputs", "source_inputs", "runtime_inputs", "owned_outputs"}, "phase instance")
    if record.get("schema_version") != PHASE_INSTANCE_SCHEMA:
        raise ValidationError("phase instance has an unsupported schema_version")
    phase_id = _string(record, "phase_id", "phase instance")
    if phase_id not in PHASE_PRIORS:
        raise ValidationError(f"unknown phase id: {phase_id}")
    priors = record["prior_instances"]
    if not isinstance(priors, list) or tuple(item.get("phase_id") if isinstance(item, dict) else None for item in priors) != PHASE_PRIORS[phase_id]:
        raise ValidationError(f"phase instance {phase_id} has wrong, reordered, or extra direct priors")
    if root is not None:
        for field in ("prereg_inputs", "source_inputs", "runtime_inputs", "owned_outputs"):
            _validate_bindings(record[field], root, f"phase instance.{field}")
        for expected_id, prior in zip(PHASE_PRIORS[phase_id], priors):
            _verify_prior_manifest(_mapping(prior, "prior instance"), root, expected_id)
    return record


def build_phase_instance(phase_id: str, root: Path, *, prior_paths: Sequence[Path], prior_manifest_paths: Sequence[Path], prereg_inputs: Sequence[Path], source_inputs: Sequence[Path], runtime_inputs: Sequence[Path], owned_outputs: Sequence[Path]) -> dict[str, Any]:
    if phase_id not in PHASE_PRIORS or len(prior_paths) != len(PHASE_PRIORS[phase_id]) or len(prior_manifest_paths) != len(prior_paths):
        raise ValidationError(f"phase {phase_id} requires exactly its approved direct prior instances and manifests")
    priors = []
    for expected_id, path, manifest_path in zip(PHASE_PRIORS[phase_id], prior_paths, prior_manifest_paths):
        prior, manifest = read_json(path), read_json(manifest_path)
        binding = _file_binding(path, root)
        binding["sha256"] = sha256_canonical(prior)
        binding["phase_id"] = expected_id
        binding["manifest_path"] = _file_binding(manifest_path, root)["path"]
        binding["manifest_sha256"] = sha256_canonical(manifest)
        _verify_prior_manifest(binding, root, expected_id)
        priors.append(binding)
    def bindings(paths: Sequence[Path], label: str) -> list[dict[str, str]]:
        if not paths:
            raise ValidationError(f"{label} must not be empty")
        return [_file_binding(path, root) for path in paths]
    instance = {"schema_version": PHASE_INSTANCE_SCHEMA, "phase_id": phase_id, "prior_instances": priors,
                "prereg_inputs": bindings(prereg_inputs, "prereg_inputs"), "source_inputs": bindings(source_inputs, "source_inputs"),
                "runtime_inputs": bindings(runtime_inputs, "runtime_inputs"), "owned_outputs": bindings(owned_outputs, "owned_outputs")}
    validate_phase_instance(instance, root)
    return instance


def validate_test_capture(capture: Any, phase_instance: Any, root: Path) -> Mapping[str, Any]:
    instance, record = validate_phase_instance(phase_instance, root), _mapping(capture, "test capture")
    _exact_keys(record, {"schema_version", "phase_id", "phase_instance_sha256", "argv", "exit_code", "status", "stdout", "stderr", "source_inputs", "runtime_inputs", "owned_outputs"}, "test capture")
    if record.get("schema_version") != TEST_CAPTURE_SCHEMA or record.get("phase_id") != instance["phase_id"]:
        raise ValidationError("test capture has unsupported schema or wrong phase")
    if record.get("status") != "PASS" or record.get("exit_code") != 0:
        raise ValidationError("test capture must be an observed PASS with exit_code 0")
    if record.get("phase_instance_sha256") != sha256_canonical(instance):
        raise ValidationError("test capture has stale phase_instance_sha256")
    argv = record.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and arg for arg in argv):
        raise ValidationError("test capture.argv must be a non-empty exact argv list")
    for field in ("stdout", "stderr"):
        if not isinstance(record.get(field), str) or len(record[field].encode("utf-8")) > MAX_DIAGNOSTIC_BYTES:
            raise ValidationError(f"test capture.{field} must be a bounded string")
    for field in ("source_inputs", "runtime_inputs", "owned_outputs"):
        _validate_bindings(record[field], root, f"test capture.{field}")
        if record[field] != instance[field]:
            raise ValidationError(f"test capture.{field} does not match the tested phase instance")
    return record


def _bounded_diagnostic(value: bytes) -> str:
    text = value[:MAX_DIAGNOSTIC_BYTES].decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    result, size = [], 0
    for character in text:
        character_size = len(character.encode("utf-8"))
        if size + character_size > MAX_DIAGNOSTIC_BYTES:
            break
        result.append(character)
        size += character_size
    return "".join(result)


def _drain_diagnostic(handle: Any, destination: bytearray) -> None:
    while block := handle.read(64 * 1024):
        remaining = MAX_DIAGNOSTIC_BYTES - len(destination)
        if remaining > 0:
            destination.extend(block[:remaining])



def capture_test(instance: Any, root: Path, argv: Sequence[str]) -> dict[str, Any]:
    validated = validate_phase_instance(instance, root)
    if not argv or not all(isinstance(arg, str) and arg for arg in argv):
        raise ValidationError("argv must be a non-empty exact argv list")
    stdout_bytes, stderr_bytes = bytearray(), bytearray()
    with subprocess.Popen(list(argv), cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        assert process.stdout is not None and process.stderr is not None
        stdout_thread = threading.Thread(target=_drain_diagnostic, args=(process.stdout, stdout_bytes))
        stderr_thread = threading.Thread(target=_drain_diagnostic, args=(process.stderr, stderr_bytes))
        stdout_thread.start()
        stderr_thread.start()
        exit_code = process.wait()
        stdout_thread.join()
        stderr_thread.join()
    stdout_text, stderr_text = _bounded_diagnostic(bytes(stdout_bytes)), _bounded_diagnostic(bytes(stderr_bytes))
    return {"schema_version": TEST_CAPTURE_SCHEMA, "phase_id": validated["phase_id"], "phase_instance_sha256": sha256_canonical(validated),
            "argv": list(argv), "exit_code": exit_code, "status": "PASS" if exit_code == 0 else "FAIL",
            "stdout": stdout_text, "stderr": stderr_text,
            "source_inputs": validated["source_inputs"], "runtime_inputs": validated["runtime_inputs"], "owned_outputs": validated["owned_outputs"]}


def validate_test_receipt(receipt: Any, phase_instance: Any, root: Path) -> Mapping[str, Any]:
    instance, record = validate_phase_instance(phase_instance, root), _mapping(receipt, "test receipt")
    _exact_keys(record, {"schema_version", "phase_id", "phase_instance_sha256", "argv", "exit_code", "status", "test_capture_path", "test_capture_sha256", "source_inputs", "runtime_inputs", "owned_outputs"}, "test receipt")
    if record.get("schema_version") != TEST_RECEIPT_SCHEMA or record.get("phase_id") != instance["phase_id"] or record.get("status") != "PASS" or record.get("exit_code") != 0:
        raise ValidationError("test receipt must bind phase, PASS status, and exit_code 0")
    if record.get("phase_instance_sha256") != sha256_canonical(instance):
        raise ValidationError("test receipt has a stale phase_instance_sha256")
    capture_path = _safe_path(root, _string(record, "test_capture_path", "test receipt"), "test receipt.test_capture_path")
    capture = read_json(capture_path)
    if sha256_canonical(capture) != _string(record, "test_capture_sha256", "test receipt"):
        raise ValidationError("test receipt has stale test capture bytes")
    validate_test_capture(capture, instance, root)
    for field in ("argv", "source_inputs", "runtime_inputs", "owned_outputs"):
        if record[field] != capture[field]:
            raise ValidationError(f"test receipt.{field} does not match observed test capture")
    return record


def build_test_receipt(instance: Any, root: Path, capture_path: Path) -> dict[str, Any]:
    validated = validate_phase_instance(instance, root)
    capture = read_json(capture_path)
    validate_test_capture(capture, validated, root)
    receipt = {"schema_version": TEST_RECEIPT_SCHEMA, "phase_id": validated["phase_id"], "phase_instance_sha256": sha256_canonical(validated),
               "argv": capture["argv"], "exit_code": capture["exit_code"], "status": capture["status"],
               "test_capture_path": _file_binding(capture_path, root)["path"], "test_capture_sha256": sha256_canonical(capture),
               "source_inputs": capture["source_inputs"], "runtime_inputs": capture["runtime_inputs"], "owned_outputs": capture["owned_outputs"]}
    validate_test_receipt(receipt, validated, root)
    return receipt


def build_manifest(phase_instance: Any, test_receipt: Any, root: Path, phase_path: Path, receipt_path: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    instance, receipt = validate_phase_instance(phase_instance, root), validate_test_receipt(test_receipt, phase_instance, root)
    if read_json(phase_path) != instance or read_json(receipt_path) != receipt:
        raise ValidationError("manifest inputs must be the exact persisted phase instance and receipt")
    parent = root if manifest_path is None else manifest_path.parent
    return {"schema_version": MANIFEST_SCHEMA, "phase_id": instance["phase_id"], "evidence_root_path": os.path.relpath(root.resolve(), parent.resolve()).replace(os.sep, "/"),
            "phase_instance_path": _file_binding(phase_path, root)["path"], "phase_instance_sha256": sha256_canonical(instance),
            "test_receipt_path": _file_binding(receipt_path, root)["path"], "test_receipt_sha256": sha256_canonical(receipt), "owned_outputs": instance["owned_outputs"]}


def write_new_json(path: Path, value: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json_bytes(value).decode("utf-8") + "\n")
    except FileExistsError as exc:
        raise ValidationError(f"refusing to overwrite existing file: {path}") from exc


def verify_manifest(manifest: Any, manifest_path: Path) -> None:
    record = _mapping(manifest, "manifest")
    _exact_keys(record, {"schema_version", "phase_id", "evidence_root_path", "phase_instance_path", "phase_instance_sha256", "test_receipt_path", "test_receipt_sha256", "owned_outputs"}, "manifest")
    if record.get("schema_version") != MANIFEST_SCHEMA:
        raise ValidationError("manifest has an unsupported schema_version")
    root_text = _string(record, "evidence_root_path", "manifest")
    if Path(root_text).is_absolute(): raise ValidationError("manifest.evidence_root_path must be relative")
    root = (manifest_path.parent / root_text).resolve()
    try: manifest_path.resolve().relative_to(root)
    except ValueError as exc: raise ValidationError("manifest evidence root escapes manifest location") from exc
    instance_path = _safe_path(root, _string(record, "phase_instance_path", "manifest"), "manifest.phase_instance_path")
    receipt_path = _safe_path(root, _string(record, "test_receipt_path", "manifest"), "manifest.test_receipt_path")
    if manifest_path.resolve() in (instance_path, receipt_path): raise ValidationError("manifest path self reference")
    instance, receipt = read_json(instance_path), read_json(receipt_path)
    validate_phase_instance(instance, root)
    validate_test_receipt(receipt, instance, root)
    if record.get("phase_id") != instance["phase_id"] or record.get("phase_instance_sha256") != sha256_canonical(instance) or record.get("test_receipt_sha256") != sha256_canonical(receipt):
        raise ValidationError("manifest has stale or mismatched phase evidence")
    if record.get("owned_outputs") != instance["owned_outputs"]: raise ValidationError("manifest owned outputs do not match phase instance")
    _validate_bindings(record["owned_outputs"], root, "manifest.owned_outputs")


def _distribution_key(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _requirements(requirements_lock: Path) -> list[dict[str, str]]:
    if not requirements_lock.is_file(): raise ValidationError("dependency lock is required")
    result = []
    for raw in requirements_lock.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"): continue
        if line.count("==") != 1: raise ValidationError("dependency lock must use exact name==version entries")
        name, version = line.split("==")
        if not name or not version: raise ValidationError("dependency lock has an empty name or version")
        result.append({"name": name, "version": version})
    if not result or len({_distribution_key(item["name"]) for item in result}) != len(result): raise ValidationError("dependency lock is empty or duplicates a distribution")
    return sorted(result, key=lambda item: _distribution_key(item["name"]))


def build_runtime_lock(requirements_lock: Path) -> dict[str, Any]:
    dependencies = _requirements(requirements_lock)
    installed = {
        _distribution_key(dist.metadata["Name"]): dist.version
        for dist in importlib.metadata.distributions()
        if dist.metadata.get("Name")
    }
    mismatches = [
        f"{item['name']}=={item['version']}"
        for item in dependencies
        if installed.get(_distribution_key(item["name"])) != item["version"]
    ]
    if mismatches: raise ValidationError("installed distributions differ from dependency lock: " + ", ".join(mismatches))
    if sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 11) or sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise ValidationError("runtime must be CPython 3.11 on win_amd64")
    executable = Path(sys.executable)
    return {"schema_version": RUNTIME_LOCK_SCHEMA, "attestation": "LOCAL_RUNTIME_IDENTITY_ONLY_NOT_EXTERNAL_ATTESTATION", "implementation": "CPython", "python_version": platform.python_version(), "platform": "win_amd64", "executable_name": executable.name, "executable_sha256": sha256_file(executable), "dependency_lock": requirements_lock.name, "dependency_lock_sha256": sha256_file(requirements_lock), "dependencies": dependencies}


def validate_runtime_lock(lock: Any, requirements_lock: Path) -> None:
    record = _mapping(lock, "runtime lock")
    _exact_keys(record, {"schema_version", "attestation", "implementation", "python_version", "platform", "executable_name", "executable_sha256", "dependency_lock", "dependency_lock_sha256", "dependencies"}, "runtime lock")
    if record.get("schema_version") != RUNTIME_LOCK_SCHEMA or record.get("attestation") != "LOCAL_RUNTIME_IDENTITY_ONLY_NOT_EXTERNAL_ATTESTATION" or record.get("dependency_lock") != requirements_lock.name or record.get("dependency_lock_sha256") != sha256_file(requirements_lock) or record.get("dependencies") != _requirements(requirements_lock):
        raise ValidationError("runtime lock does not match the canonical dependency lock schema")
    expected = build_runtime_lock(requirements_lock)
    if record != expected: raise ValidationError("runtime lock does not match the installed local runtime")


def build_m3e_inventory_receipt(inventory_path: Path, root: Path) -> dict[str, str]:
    binding = _file_binding(inventory_path, root)
    return {"schema_version": M3E_INVENTORY_RECEIPT_SCHEMA, "status": "NO_TOUCH_INVENTORY_ONLY", "fresh_oos_status": "NOT_RUN", "inventory_path": binding["path"], "inventory_sha256": binding["sha256"], "statement": "This receipt binds an existing local M3E inventory only; it does not open, read, evaluate, or attest fresh OOS."}


def validate_m3e_inventory_receipt(receipt: Any, inventory_path: Path, root: Path) -> None:
    record = _mapping(receipt, "M3E inventory receipt")
    _exact_keys(record, {"schema_version", "status", "fresh_oos_status", "inventory_path", "inventory_sha256", "statement"}, "M3E inventory receipt")
    if record != build_m3e_inventory_receipt(inventory_path, root):
        raise ValidationError("M3E inventory receipt does not bind the exact existing no-touch inventory")


def _print_json(value: Any) -> None: print(canonical_json_bytes(value).decode("utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__); commands = parser.add_subparsers(dest="command", required=True)
    matrix = commands.add_parser("validate-phase-matrix"); matrix.add_argument("--matrix", required=True, type=Path)
    runtime = commands.add_parser("create-runtime-lock"); runtime.add_argument("--requirements-lock", required=True, type=Path); runtime.add_argument("--output", required=True, type=Path)
    verify_runtime = commands.add_parser("verify-runtime-lock"); verify_runtime.add_argument("--requirements-lock", required=True, type=Path); verify_runtime.add_argument("--runtime-lock", required=True, type=Path)
    inventory = commands.add_parser("create-m3e-inventory-receipt"); inventory.add_argument("--root", required=True, type=Path); inventory.add_argument("--inventory", required=True, type=Path); inventory.add_argument("--output", required=True, type=Path)
    instance = commands.add_parser("create-phase-instance"); instance.add_argument("--root", required=True, type=Path); instance.add_argument("--phase", required=True); instance.add_argument("--prior-instance", action="append", default=[], type=Path); instance.add_argument("--prior-manifest", action="append", default=[], type=Path); instance.add_argument("--prereg-input", action="append", required=True, type=Path); instance.add_argument("--source-input", action="append", required=True, type=Path); instance.add_argument("--runtime-input", action="append", required=True, type=Path); instance.add_argument("--owned-output", action="append", required=True, type=Path); instance.add_argument("--output", required=True, type=Path)
    capture = commands.add_parser("capture-test"); capture.add_argument("--root", required=True, type=Path); capture.add_argument("--phase-instance", required=True, type=Path); capture.add_argument("--argv", action="append", required=True); capture.add_argument("--output", required=True, type=Path)
    receipt = commands.add_parser("create-test-receipt"); receipt.add_argument("--root", required=True, type=Path); receipt.add_argument("--phase-instance", required=True, type=Path); receipt.add_argument("--test-capture", required=True, type=Path); receipt.add_argument("--output", required=True, type=Path)
    manifest = commands.add_parser("create-manifest"); manifest.add_argument("--root", required=True, type=Path); manifest.add_argument("--phase-instance", required=True, type=Path); manifest.add_argument("--test-receipt", required=True, type=Path); manifest.add_argument("--output", required=True, type=Path)
    verify = commands.add_parser("verify-manifest"); verify.add_argument("--manifest", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-phase-matrix": validate_phase_matrix(read_json(args.matrix)); _print_json({"status": "PASS"})
        elif args.command == "create-runtime-lock": value = build_runtime_lock(args.requirements_lock); write_new_json(args.output, value); _print_json(value)
        elif args.command == "verify-runtime-lock": validate_runtime_lock(read_json(args.runtime_lock), args.requirements_lock); _print_json({"status": "PASS"})
        elif args.command == "create-m3e-inventory-receipt":
            output = _root_output(args.root, args.output); value = build_m3e_inventory_receipt(args.inventory, args.root); write_new_json(output, value); _print_json(value)
        elif args.command == "create-phase-instance":
            output = _root_output(args.root, args.output); value = build_phase_instance(args.phase, args.root, prior_paths=args.prior_instance, prior_manifest_paths=args.prior_manifest, prereg_inputs=args.prereg_input, source_inputs=args.source_input, runtime_inputs=args.runtime_input, owned_outputs=args.owned_output); write_new_json(output, value); _print_json(value)
        elif args.command == "capture-test":
            output = _root_output(args.root, args.output); value = capture_test(read_json(args.phase_instance), args.root, args.argv); write_new_json(output, value); _print_json(value)
            if value["status"] != "PASS": return 1
        elif args.command == "create-test-receipt":
            output = _root_output(args.root, args.output); value = build_test_receipt(read_json(args.phase_instance), args.root, args.test_capture); write_new_json(output, value); _print_json(value)
        elif args.command == "create-manifest":
            output = _root_output(args.root, args.output); value = build_manifest(read_json(args.phase_instance), read_json(args.test_receipt), args.root, args.phase_instance, args.test_receipt, output); write_new_json(output, value); _print_json(value)
        elif args.command == "verify-manifest": verify_manifest(read_json(args.manifest), args.manifest); _print_json({"status": "PASS"})
    except ValidationError as exc:
        print(f"ERROR: {exc}"); return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
