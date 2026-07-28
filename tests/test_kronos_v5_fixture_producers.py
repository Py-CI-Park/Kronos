"""Contract coverage for isolated V5 synthetic fixture producers."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import socket
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "tests" / "data" / "kronos_v5_fixture_contract.json").read_text(encoding="utf-8"))
VECTORS = json.loads((ROOT / "tests" / "data" / "kronos_rl_api_v2_vectors.json").read_text(encoding="utf-8"))
SCHEMA = ROOT / "docs" / "schemas" / "kronos_v5_qa_producers.v1.schema.json"


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = _module("run_dashboard_v5_fixture")
manifests = _module("build_dashboard_v5_manifests")
baseline = _module("capture_dashboard_v5_baseline")
SHA = "a" * 64


def _tree(tmp_path: Path, name: str = "tree") -> Path:
    root = tmp_path / name
    root.mkdir(parents=True)
    (root / "app.js").write_text("console.log('fixture')\n", encoding="utf-8")
    return root


def _schema_validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _make_symlink(link: Path, target: Path, *, is_dir: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=is_dir)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    assert link.is_symlink()


def _baseline_inputs(tmp_path: Path, name: str = "tree") -> tuple[dict, dict, dict]:
    root = _tree(tmp_path, name)
    return manifests.build_source_manifest(root), manifests.build_bundle_manifest(root), manifests.build_dist_manifest(root)


def _manifest_with_entry_path(manifest: dict, path: str) -> dict:
    updated = json.loads(json.dumps(manifest))
    updated["entries"][0]["path"] = path
    content = {key: updated[key] for key in ("schema", "entries", "raw_byte_length", "gzip9_byte_length", "browser_transfer_byte_length")}
    updated["manifest_sha256"] = baseline._sha(baseline._canonical(content))
    return updated


def test_fixture_binds_loopback_nonce_readiness_and_cleanup(tmp_path: Path) -> None:
    descriptor = fixture.start_fixture(registry_root=tmp_path / "registry", artifact_root=tmp_path / "artifacts", job_intent_root=tmp_path / "intents", source_sha256=SHA)
    ready = descriptor
    try:
        ready = fixture.wait_ready(descriptor, timeout_seconds=2.0)
        assert ready["schema"] == CONTRACT["fixture_schema"]
        assert ready["host"] == "127.0.0.1"
        assert ready["port"] > 0 and ready["nonce"]
        assert ready["pid"] == descriptor["pid"]
        assert isinstance(ready["readiness_timestamp_utc"], str)
        assert ready["readiness_timestamp_utc"].endswith("Z")
        assert "readiness_timestamp_ms" not in ready
        assert "readiness_timestamp_ns" not in ready
        with socket.create_connection((ready["host"], ready["port"]), timeout=1):
            pass
    finally:
        stopped = fixture.stop_fixture(ready, grace_seconds=0.5, force_seconds=1.0)
    assert stopped["cleanup_status"] in {"GRACEFUL", "FORCED"}
    assert set(CONTRACT["required_fixture_fields"]) <= set(stopped)
    assert not fixture._pid_is_running(int(stopped["pid"]))


def test_fixture_readiness_timeout_is_bounded_and_cleanup_leaves_no_child(tmp_path: Path) -> None:
    descriptor = fixture.start_fixture(registry_root=tmp_path / "registry", artifact_root=tmp_path / "artifacts", job_intent_root=tmp_path / "intents", source_sha256=SHA)
    started_at = time.monotonic()
    try:
        broken = dict(descriptor)
        broken["readiness_path"] = str(tmp_path / "missing.ready.json")
        with pytest.raises(fixture.FixtureError, match="readiness timed out"):
            fixture.wait_ready(broken, timeout_seconds=0.1)
        assert time.monotonic() - started_at < 2.0
    finally:
        stopped = fixture.stop_fixture(descriptor, grace_seconds=0.5, force_seconds=1.0)
    assert not fixture._pid_is_running(int(stopped["pid"]))


def test_fixture_refuses_real_oos_database_and_tracked_dist_roots(tmp_path: Path) -> None:
    bad_roots = [ROOT / "webui" / "static" / "v2" / "dist", tmp_path / "OOS", tmp_path / "database", tmp_path / "db", tmp_path / "webui" / "static" / "v2" / "dist"]
    for index, bad_root in enumerate(bad_roots):
        with pytest.raises(fixture.FixtureError):
            fixture.start_fixture(registry_root=bad_root, artifact_root=tmp_path / f"artifacts-{index}", job_intent_root=tmp_path / f"intents-{index}", source_sha256=SHA)


def test_manifests_are_deterministic_hash_bound_and_include_gzip_transfer_metrics(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    first, second = manifests.build_bundle_manifest(root), manifests.build_bundle_manifest(root)
    assert first == second
    assert first["schema"] == "kronos_bundle_manifest.v1"
    assert first["entries"][0]["gzip9_byte_length"] > 0
    assert first["entries"][0]["browser_transfer_byte_length"] == first["entries"][0]["gzip9_byte_length"]
    assert first["raw_byte_length"] == sum(row["byte_length"] for row in first["entries"])
    assert first["gzip9_byte_length"] == sum(row["gzip9_byte_length"] for row in first["entries"])
    assert first["browser_transfer_byte_length"] == sum(row["browser_transfer_byte_length"] for row in first["entries"])
    hashed_content = {key: first[key] for key in ("schema", "entries", "raw_byte_length", "gzip9_byte_length", "browser_transfer_byte_length")}
    assert first["manifest_sha256"] == manifests._sha(manifests._canonical(hashed_content))


@pytest.mark.parametrize("name", ["../escape", "symlink", "collision"])
def test_manifest_rejects_traversal_symlink_and_collision(tmp_path: Path, name: str) -> None:
    root = _tree(tmp_path)
    if name == "../escape":
        with pytest.raises(manifests.ManifestError):
            manifests.build_bundle_manifest(root / ".." / "missing")
    elif name == "symlink":
        _make_symlink(root / "link.js", root / "app.js")
        with pytest.raises(manifests.ManifestError, match="symlink"):
            manifests.build_bundle_manifest(root)
    else:
        (root / "APP.js").write_text("x", encoding="utf-8")
        casefolded = [path.name.casefold() for path in root.iterdir() if path.is_file()]
        if casefolded.count("app.js") < 2:
            (root / "ß.js").write_text("x", encoding="utf-8")
            (root / "ss.js").write_text("y", encoding="utf-8")
        with pytest.raises(manifests.ManifestError, match="collision"):
            manifests.build_bundle_manifest(root)


@pytest.mark.parametrize("parts", [("webui", "static", "v2", "dist"), ("OOS",), ("database",), ("db",)])
def test_manifest_refuses_tracked_dist_oos_database_and_db_roots(tmp_path: Path, parts: tuple[str, ...]) -> None:
    bad_root = tmp_path.joinpath(*parts)
    bad_root.mkdir(parents=True)
    (bad_root / "app.js").write_text("x", encoding="utf-8")
    with pytest.raises(manifests.ManifestError):
        manifests.build_bundle_manifest(bad_root)


@pytest.mark.parametrize("parts", [
    ("nested", "OOS", "secret.js"),
    ("assets", "WEBUI", "static", "v2", "DIST", "bundle.js"),
    ("nested", "DataBase", "secret.js"),
    ("nested", "DB", "secret.js"),
])
def test_manifest_rejects_nested_forbidden_descendants_before_hashing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parts: tuple[str, ...]) -> None:
    root = _tree(tmp_path)
    forbidden_file = root.joinpath(*parts)
    forbidden_file.parent.mkdir(parents=True)
    forbidden_file.write_text("must not be read\n", encoding="utf-8")
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path == forbidden_file:
            raise AssertionError("forbidden descendant was read before rejection")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    with pytest.raises(manifests.ManifestError, match="forbidden"):
        manifests.build_bundle_manifest(root)


def test_manifest_rejects_symlinked_ancestor_when_supported(tmp_path: Path) -> None:
    real_parent = tmp_path / "real-parent"
    real_root = _tree(real_parent)
    link_parent = tmp_path / "linked-parent"
    _make_symlink(link_parent, real_parent, is_dir=True)
    with pytest.raises(manifests.ManifestError, match="symlinked"):
        manifests.build_bundle_manifest(link_parent / real_root.name)


def test_baseline_is_synthetic_refuses_tracked_dist_and_never_needs_oos(tmp_path: Path) -> None:
    source, bundle, dist = _baseline_inputs(tmp_path)
    receipt = baseline.capture_baseline(output_root=tmp_path / "evidence", producer_sha256=SHA, schema_sha256=SHA, instrument_sha256=SHA, fixture_sha256=SHA, source_manifest=source, bundle_manifest=bundle, dist_manifest=dist)
    assert receipt["schema"] == CONTRACT["baseline_schema"]
    assert receipt["status"] == CONTRACT["baseline_status"]
    assert CONTRACT["six_lock_keys"] == list(VECTORS["locks"])
    assert CONTRACT["six_locks_false"] == VECTORS["locks"]
    assert receipt["six_locks_false"] == CONTRACT["six_locks_false"]
    assert receipt["manifest_sha256"] == {"source": source["manifest_sha256"], "bundle": bundle["manifest_sha256"], "dist": dist["manifest_sha256"]}
    receipt_path = Path(receipt["receipt_location"])
    run_root = receipt_path.parents[1]
    screenshot_path = run_root / receipt["evidence_locations"]["screenshot"]
    metadata_path = run_root / receipt["evidence_locations"]["metadata"]
    assert receipt_path.name == f"{receipt['receipt_ref']['sha256']}.json"
    assert metadata_path.name == f"{receipt['evidence_refs'][0]['sha256']}.json"
    assert screenshot_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert receipt_path.read_bytes()
    assert metadata_path.read_bytes()
    with pytest.raises(baseline.BaselineError):
        baseline.capture_baseline(output_root=ROOT / "webui" / "static" / "v2" / "dist", producer_sha256=SHA, schema_sha256=SHA, instrument_sha256=SHA, fixture_sha256=SHA, source_manifest=source, bundle_manifest=bundle, dist_manifest=dist)


def test_baseline_recomputes_manifest_hashes_and_rejects_stale_manifests(tmp_path: Path) -> None:
    source, bundle, dist = _baseline_inputs(tmp_path)
    stale_hash = json.loads(json.dumps(source))
    stale_hash["manifest_sha256"] = "b" * 64
    with pytest.raises(baseline.BaselineError, match="hash mismatch"):
        baseline.capture_baseline(output_root=tmp_path / "bad-hash", producer_sha256=SHA, schema_sha256=SHA, instrument_sha256=SHA, fixture_sha256=SHA, source_manifest=stale_hash, bundle_manifest=bundle, dist_manifest=dist)
    stale_total = json.loads(json.dumps(source))
    stale_total["raw_byte_length"] += 1
    with pytest.raises(baseline.BaselineError, match="aggregate"):
        baseline.capture_baseline(output_root=tmp_path / "bad-total", producer_sha256=SHA, schema_sha256=SHA, instrument_sha256=SHA, fixture_sha256=SHA, source_manifest=stale_total, bundle_manifest=bundle, dist_manifest=dist)


@pytest.mark.parametrize(("manifest_key", "forbidden_path"), [
    ("source_manifest", "assets/WEBUI/static/v2/DIST/app.js"),
    ("bundle_manifest", "safe/DataBase/app.js"),
    ("dist_manifest", "safe/DB/app.js"),
])
def test_baseline_rejects_hash_consistent_forbidden_manifest_provenance(tmp_path: Path, manifest_key: str, forbidden_path: str) -> None:
    source, bundle, dist = _baseline_inputs(tmp_path)
    inputs = {"source_manifest": source, "bundle_manifest": bundle, "dist_manifest": dist}
    forbidden_manifest = _manifest_with_entry_path(inputs[manifest_key], forbidden_path)
    hashed_content = {key: forbidden_manifest[key] for key in ("schema", "entries", "raw_byte_length", "gzip9_byte_length", "browser_transfer_byte_length")}
    assert forbidden_manifest["manifest_sha256"] == baseline._sha(baseline._canonical(hashed_content))
    inputs[manifest_key] = forbidden_manifest
    with pytest.raises(baseline.BaselineError, match="forbidden provenance"):
        baseline.capture_baseline(output_root=tmp_path / "forbidden-provenance", producer_sha256=SHA, schema_sha256=SHA, instrument_sha256=SHA, fixture_sha256=SHA, **inputs)


def test_baseline_rejects_preexisting_and_portable_collision_output_roots(tmp_path: Path) -> None:
    source, bundle, dist = _baseline_inputs(tmp_path)
    preexisting = tmp_path / "preexisting"
    preexisting.mkdir()
    with pytest.raises(baseline.BaselineError):
        baseline.capture_baseline(output_root=preexisting, producer_sha256=SHA, schema_sha256=SHA, instrument_sha256=SHA, fixture_sha256=SHA, source_manifest=source, bundle_manifest=bundle, dist_manifest=dist)
    (tmp_path / "Evidence").mkdir()
    with pytest.raises(baseline.BaselineError):
        baseline.capture_baseline(output_root=tmp_path / "evidence", producer_sha256=SHA, schema_sha256=SHA, instrument_sha256=SHA, fixture_sha256=SHA, source_manifest=source, bundle_manifest=bundle, dist_manifest=dist)


def test_baseline_rejects_symlink_output_root_when_supported(tmp_path: Path) -> None:
    source, bundle, dist = _baseline_inputs(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    _make_symlink(link, target, is_dir=True)
    with pytest.raises(baseline.BaselineError, match="symlink"):
        baseline.capture_baseline(output_root=link, producer_sha256=SHA, schema_sha256=SHA, instrument_sha256=SHA, fixture_sha256=SHA, source_manifest=source, bundle_manifest=bundle, dist_manifest=dist)


def test_actual_producer_outputs_validate_against_schema(tmp_path: Path) -> None:
    validator = _schema_validator()
    descriptor = fixture.start_fixture(registry_root=tmp_path / "registry", artifact_root=tmp_path / "artifacts", job_intent_root=tmp_path / "intents", source_sha256=SHA)
    ready = descriptor
    try:
        ready = fixture.wait_ready(descriptor, timeout_seconds=2.0)
    finally:
        stopped = fixture.stop_fixture(ready, grace_seconds=0.5, force_seconds=1.0)
    validator.validate(stopped)
    source, bundle, dist = _baseline_inputs(tmp_path, "schema-tree")
    for payload in (source, bundle, dist):
        validator.validate(payload)
    receipt = baseline.capture_baseline(output_root=tmp_path / "schema-evidence", producer_sha256=SHA, schema_sha256=SHA, instrument_sha256=SHA, fixture_sha256=SHA, source_manifest=source, bundle_manifest=bundle, dist_manifest=dist)
    validator.validate(receipt)
