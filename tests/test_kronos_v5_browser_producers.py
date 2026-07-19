from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "scripts" / "capture_dashboard_v5_browser_matrix.mjs"
PERFORMANCE = ROOT / "scripts" / "measure_dashboard_v5_performance.mjs"
SECURITY = ROOT / "scripts" / "probe_dashboard_v5_security.py"
FIXTURE = ROOT / "tests" / "data" / "kronos_v5_browser_fixture.json"
MATRIX = ROOT / "docs" / "kronos_dashboard_v5_browser_matrix_v1.json"
NONCE = "0123456789abcdef" * 4
BROWSER_SHA = hashlib.sha256(b"synthetic-browser-v5").hexdigest()
DIST_MANIFEST_SHA = hashlib.sha256(b"synthetic-dist-manifest-v5").hexdigest()
EXPECTED_ISOLATED_POST_PROBE = {"method": "POST", "path": "/api/v5/jobs", "payload": "create-job", "status": 405, "accepted": False, "side_effects": False}
LIFECYCLE = ["ADVANCING", "STALLED", "RESUMED", "RESTARTED_NON_EXACT", "STOPPED", "FAILED", "COMPLETED", "CONFLICT_BLOCKED", "NOT_RUN"]
GOVERNANCE = ["D0_BLOCKED", "D1_BLOCKED", "FRESH_OOS_SEALED", "FRESH_OOS_NOT_AVAILABLE", "MISSING_CELL"]
ASYNC_SECURITY = ["ISOLATED_TIMEOUT_RETRY", "LATE_LIST_DETAIL_RACE", "ALLOWED_DOWNLOAD", "DENIED_DOWNLOAD"]
KEYBOARD_TABS = ["mission-control", "rl", "daily-ohlcv", "live-training"]
DENIAL_PROBES = [
    {"id": "SEC-DENY-TRAVERSAL", "kind": "traversal", "method": "GET", "path": "/api/v5/download", "payload": "../../outside/registry.json", "status": 400, "accepted": False},
    {"id": "SEC-DENY-REPARSE", "kind": "reparse", "method": "GET", "path": "/api/v5/download", "payload": "reparse:../artifact-junction/fixture.json", "status": 400, "accepted": False},
    {"id": "SEC-DENY-OOS", "kind": "oos", "method": "GET", "path": "/api/v5/fresh-oos", "payload": "unsealed_fresh_oos_profile", "status": 403, "accepted": False},
]
MUTATION_PROBES = [
    {"id": f"SEC-MUTATION-{method}", "kind": "mutation", "method": method, "path": "/api/v5/jobs", "payload": payload, "status": 405, "accepted": False}
    for method, payload in [("DELETE", "delete-job"), ("PATCH", "patch-job"), ("POST", "create-job"), ("PUT", "replace-job")]
]


def _load_matrix() -> dict[str, object]:
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def _matrix_ids() -> list[str]:
    return list(_load_matrix()["scenarios"])


def _ref(root: Path, rel: str, media_type: str) -> dict[str, object]:
    data = (root / rel).read_bytes()
    return {"relative_path": rel, "sha256": hashlib.sha256(data).hexdigest(), "byte_length": len(data), "media_type": media_type}


def _png(width: int = 2, height: int = 1, seed: int = 1, uniform: bool = False) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            if uniform:
                raw.extend([seed % 256, seed % 256, seed % 256])
            else:
                raw.extend([(seed + x) % 256, (seed * 3 + y) % 256, (seed * 7 + x + y) % 256])
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b"")


def _run(command: list[str], expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False, timeout=30)
    assert result.returncode == expected, result.stderr
    return result


def _scenario_metadata(scenario_id: str) -> dict[str, object]:
    matrix = _load_matrix()
    for tab in matrix["base_tabs"]:
        for theme in matrix["themes"]:
            for width in matrix["widths"]:
                if scenario_id == f"S-BASE-{tab}-{theme}-{width}":
                    return {"group": "BASE", "tab": tab, "theme": theme, "width": width}
    for state in LIFECYCLE:
        for theme in matrix["themes"]:
            if scenario_id == f"S-LIFE-{state}-{theme}":
                return {"group": "LIFE", "state": state, "theme": theme}
    for state in GOVERNANCE:
        for theme in matrix["themes"]:
            if scenario_id == f"S-GOV-{state}-{theme}":
                return {"group": "GOV", "state": state, "theme": theme}
    for state in ASYNC_SECURITY:
        for theme in matrix["themes"]:
            if scenario_id == f"S-ASYNC-{state}-{theme}":
                return {"group": "ASYNC", "state": state, "theme": theme}
    for tab in KEYBOARD_TABS:
        if scenario_id == f"S-KBD-{tab}":
            return {"group": "KBD", "tab": tab, "keyboard_only": True, "width": 375}
    raise AssertionError(scenario_id)


def _browser_input(tmp_path: Path) -> tuple[Path, Path]:
    ids = _matrix_ids()
    root = tmp_path / "evidence"
    (root / "screens").mkdir(parents=True)
    (root / "traces").mkdir(parents=True)
    (root / "fixture.json").write_text("{}", encoding="utf-8")
    (root / "source.mjs").write_text("export {};", encoding="utf-8")
    fixture_ref = _ref(root, "fixture.json", "application/json")
    source_ref = _ref(root, "source.mjs", "application/javascript")
    scenarios = []
    for sequence, item in enumerate(ids, start=1):
        meta = _scenario_metadata(item)
        width = int(meta.get("width", 768))
        height = 2
        screen_rel = f"screens/{sequence:03d}.png"
        trace_rel = f"traces/{sequence:03d}.json"
        (root / screen_rel).write_bytes(_png(width=width, height=height, seed=sequence))
        screenshot = _ref(root, screen_rel, "image/png")
        url = f"http://127.0.0.1:4101/v5?scenario_id={quote(item, safe='')}"
        transcript = {
            "schema": "kronos_v5_browser_transcript.v1",
            "capture_kind": "synthetic_fixture_evidence",
            "live_browser_execution": False,
            "scenario_id": item,
            "sequence": sequence,
            "scenario": meta,
            "fixture_sha256": fixture_ref["sha256"],
            "source_sha256": source_ref["sha256"],
            "browser_sha256": BROWSER_SHA,
            "dist_manifest_sha256": DIST_MANIFEST_SHA,
            "url": url,
            "dom": {"scenario_id": item, "root": "#app", "landmarks": ["main"]},
            "screenshot": {"sha256": screenshot["sha256"], "media_type": "image/png", "width": width, "height": height},
            "get_ledger": [{"method": "GET", "url": url, "status": 200, "response_sha256": hashlib.sha256(f"GET {item}".encode()).hexdigest()}],
            "expected_isolated_post_probe": dict(EXPECTED_ISOLATED_POST_PROBE),
            "console_errors": [],
            "page_errors": [],
            "network_errors": [],
            "overflow": False,
            "wcag_a_aa": "passed",
            "focus_trace": "passed",
            "chart_table_semantics": "passed",
            "timing": {"navigation_start_ms": 0, "dom_content_loaded_ms": sequence, "hydrated_ms": sequence + 1},
        }
        (root / trace_rel).write_text(json.dumps(transcript, separators=(",", ":"), sort_keys=True), encoding="utf-8")
        scenarios.append({"scenario_id": item, "status": "passed", "screenshot_ref": screenshot, "transcript_ref": _ref(root, trace_rel, "application/json"), "console_errors": [], "page_errors": [], "network_errors": [], "overflow": False, "focus": "passed", "keyboard": "passed", "a11y": "passed", "chart_table_semantics": "passed"})
    raw = {"schema": "kronos_v5_browser_input.v1", "capture_kind": "synthetic_fixture_evidence", "live_browser_execution": False, "nonce": NONCE, "browser_pid": 7, "browser_sha256": BROWSER_SHA, "dist_manifest_sha256": DIST_MANIFEST_SHA, "fixture_ref": fixture_ref, "source_ref": source_ref, "scenarios": scenarios}
    source = tmp_path / "input.json"
    source.write_text(json.dumps(raw), encoding="utf-8")
    return source, root


def _replace_first_screenshot(source: Path, root: Path, image: bytes) -> None:
    raw = json.loads(source.read_text(encoding="utf-8"))
    rel = raw["scenarios"][0]["screenshot_ref"]["relative_path"]
    (root / rel).write_bytes(image)
    raw["scenarios"][0]["screenshot_ref"] = _ref(root, rel, "image/png")
    source.write_text(json.dumps(raw), encoding="utf-8")


def _mutate_transcript(source: Path, root: Path, index: int, mutator) -> None:
    raw = json.loads(source.read_text(encoding="utf-8"))
    rel = raw["scenarios"][index]["transcript_ref"]["relative_path"]
    transcript = json.loads((root / rel).read_text(encoding="utf-8"))
    mutator(transcript)
    (root / rel).write_text(json.dumps(transcript, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    raw["scenarios"][index]["transcript_ref"] = _ref(root, rel, "application/json")
    source.write_text(json.dumps(raw), encoding="utf-8")


def _assert_capture_fails(source: Path, root: Path, out: Path) -> None:
    result = _run(["node", str(CAPTURE), "--input", str(source), "--evidence-root", str(root), "--out", str(out)], expected=1)
    assert "capture failed closed:" in result.stderr
    assert not out.exists()


def test_fixture_freezes_the_exact_112_matrix_and_budget_contract() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    docs_matrix = _load_matrix()
    matrix = fixture["matrix"]
    assert matrix["base"] == {"tabs": docs_matrix["base_tabs"], "themes": docs_matrix["themes"], "widths": docs_matrix["widths"], "count": 72}
    assert matrix["lifecycle"] == {"states": LIFECYCLE, "themes": docs_matrix["themes"], "count": 18}
    assert matrix["governance"] == {"states": GOVERNANCE, "themes": docs_matrix["themes"], "count": 10}
    assert matrix["async_security"] == {"states": ASYNC_SECURITY, "themes": docs_matrix["themes"], "count": 8}
    assert matrix["keyboard"] == {"tabs": KEYBOARD_TABS, "count": 4}
    assert sum(section["count"] for key, section in matrix.items() if key != "count") == matrix["count"] == docs_matrix["scenario_count"] == 112
    expected_transcript_fields = ["schema", "capture_kind", "live_browser_execution", "scenario_id", "sequence", "scenario", *docs_matrix["capture_requirements"]]
    assert fixture["capture_requirements"] == docs_matrix["capture_requirements"]
    assert fixture["transcript_required_fields"] == expected_transcript_fields
    assert fixture["prohibited_claims"] == docs_matrix["prohibited_claims"] == ["OOS_CONSUMED", "LIVE_READY", "PROFIT_READY", "GO_READY"]
    assert fixture["expected_isolated_post_probe"] == EXPECTED_ISOLATED_POST_PROBE
    assert "network_errors" in docs_matrix["capture_requirements"]
    assert "request_errors" not in docs_matrix["capture_requirements"]
    assert fixture["performance"]["budgets_ms"] == {"first_critical_cold_ms": 3000, "first_critical_warm_ms": 1500, "full_hydration_cold_ms": 10000, "full_hydration_warm_ms": 6000, "api_cold_ms": 5000, "api_warm_ms": 2000, "isolated_timeout_ms": 20500, "palette_ms": 100, "filter_1000_ms": 150}
    assert fixture["capture_kind"] == "synthetic_fixture_evidence" and fixture["live_browser_execution"] is False
    assert all(value is False for value in fixture["false_locks"].values())


def test_browser_capture_is_deterministic_and_hash_bound(tmp_path: Path) -> None:
    source, root = _browser_input(tmp_path)
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    command = ["node", str(CAPTURE), "--input", str(source), "--evidence-root", str(root), "--out"]
    _run(command + [str(first)])
    _run(command + [str(second)])
    assert first.exists() and second.exists()
    assert first.read_bytes() == second.read_bytes()
    result = json.loads(first.read_text(encoding="utf-8"))
    ids = _matrix_ids()
    assert result["scenario_ids"] == ids
    assert [row["scenario_id"] for row in result["scenarios"]] == ids
    assert result["scenario_count"] == 112
    assert result["capture_kind"] == "synthetic_fixture_evidence"
    assert result["live_browser_execution"] is False
    assert all(row["network_errors"] == [] for row in result["scenarios"])
    assert len({row["screenshot_ref"]["sha256"] for row in result["scenarios"]}) == 112
    assert len({row["transcript_ref"]["sha256"] for row in result["scenarios"]}) == 112
    assert result["scenarios"][0]["screenshot"]["width"] == 375
    assert result["scenarios"][1]["screenshot"]["width"] == 768
    assert result["scenarios"][2]["screenshot"]["width"] == 1280


def test_browser_capture_rejects_tampered_png_and_incomplete_matrix(tmp_path: Path) -> None:
    source, root = _browser_input(tmp_path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw["scenarios"].pop()
    source.write_text(json.dumps(raw), encoding="utf-8")
    bad_matrix = tmp_path / "bad.json"
    result = _run(["node", str(CAPTURE), "--input", str(source), "--evidence-root", str(root), "--out", str(bad_matrix)], expected=1)
    assert "capture failed closed:" in result.stderr
    assert not bad_matrix.exists()

    source, root = _browser_input(tmp_path / "tamper")
    _replace_first_screenshot(source, root, b"not-a-png")
    bad_png = tmp_path / "bad-png.json"
    result = _run(["node", str(CAPTURE), "--input", str(source), "--evidence-root", str(root), "--out", str(bad_png)], expected=1)
    assert "capture failed closed:" in result.stderr
    assert not bad_png.exists()

    source, root = _browser_input(tmp_path / "uniform")
    _replace_first_screenshot(source, root, _png(width=375, height=2, seed=1, uniform=True))
    uniform_png = tmp_path / "uniform-png.json"
    result = _run(["node", str(CAPTURE), "--input", str(source), "--evidence-root", str(root), "--out", str(uniform_png)], expected=1)
    assert "capture failed closed:" in result.stderr
    assert not uniform_png.exists()


def test_browser_capture_rejects_order_duplicates_mislabeled_and_reused_evidence(tmp_path: Path) -> None:
    source, root = _browser_input(tmp_path / "order")
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw["scenarios"][0], raw["scenarios"][1] = raw["scenarios"][1], raw["scenarios"][0]
    source.write_text(json.dumps(raw), encoding="utf-8")
    assert "capture failed closed:" in _run(["node", str(CAPTURE), "--input", str(source), "--evidence-root", str(root), "--out", str(tmp_path / "order.json")], expected=1).stderr

    source, root = _browser_input(tmp_path / "duplicate")
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw["scenarios"][1]["scenario_id"] = raw["scenarios"][0]["scenario_id"]
    source.write_text(json.dumps(raw), encoding="utf-8")
    assert "capture failed closed:" in _run(["node", str(CAPTURE), "--input", str(source), "--evidence-root", str(root), "--out", str(tmp_path / "duplicate.json")], expected=1).stderr

    source, root = _browser_input(tmp_path / "mislabeled")
    second_id = _matrix_ids()[1]
    _mutate_transcript(source, root, 0, lambda transcript: transcript.update({"scenario_id": second_id}))
    assert "capture failed closed:" in _run(["node", str(CAPTURE), "--input", str(source), "--evidence-root", str(root), "--out", str(tmp_path / "mislabeled.json")], expected=1).stderr

    source, root = _browser_input(tmp_path / "binding")
    _mutate_transcript(source, root, 0, lambda transcript: transcript["screenshot"].update({"sha256": "f" * 64}))
    assert "capture failed closed:" in _run(["node", str(CAPTURE), "--input", str(source), "--evidence-root", str(root), "--out", str(tmp_path / "binding.json")], expected=1).stderr

    source, root = _browser_input(tmp_path / "reuse")
    raw = json.loads(source.read_text(encoding="utf-8"))
    for row in raw["scenarios"][1:]:
        row["screenshot_ref"] = raw["scenarios"][0]["screenshot_ref"]
        row["transcript_ref"] = raw["scenarios"][0]["transcript_ref"]
    source.write_text(json.dumps(raw), encoding="utf-8")
    assert "capture failed closed:" in _run(["node", str(CAPTURE), "--input", str(source), "--evidence-root", str(root), "--out", str(tmp_path / "reuse.json")], expected=1).stderr


def test_browser_capture_rejects_live_flags_missing_transcript_fields_claims_and_unknowns(tmp_path: Path) -> None:
    source, root = _browser_input(tmp_path / "input-missing-live")
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw.pop("live_browser_execution")
    source.write_text(json.dumps(raw), encoding="utf-8")
    _assert_capture_fails(source, root, tmp_path / "input-missing-live.json")

    source, root = _browser_input(tmp_path / "input-true-live")
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw["live_browser_execution"] = True
    source.write_text(json.dumps(raw), encoding="utf-8")
    _assert_capture_fails(source, root, tmp_path / "input-true-live.json")

    source, root = _browser_input(tmp_path / "transcript-missing-live")
    _mutate_transcript(source, root, 0, lambda transcript: transcript.pop("live_browser_execution"))
    _assert_capture_fails(source, root, tmp_path / "transcript-missing-live.json")

    source, root = _browser_input(tmp_path / "transcript-true-live")
    _mutate_transcript(source, root, 0, lambda transcript: transcript.update({"live_browser_execution": True}))
    _assert_capture_fails(source, root, tmp_path / "transcript-true-live.json")

    for field in ("dist_manifest_sha256", "expected_isolated_post_probe"):
        source, root = _browser_input(tmp_path / f"missing-{field}")
        _mutate_transcript(source, root, 0, lambda transcript, field=field: transcript.pop(field))
        _assert_capture_fails(source, root, tmp_path / f"missing-{field}.json")

    source, root = _browser_input(tmp_path / "claim")
    _mutate_transcript(source, root, 0, lambda transcript: transcript["dom"].update({"root": "LIVE_READY"}))
    _assert_capture_fails(source, root, tmp_path / "claim.json")

    source, root = _browser_input(tmp_path / "unknown")
    _mutate_transcript(source, root, 0, lambda transcript: transcript.update({"unexpected_field": "synthetic"}))
    _assert_capture_fails(source, root, tmp_path / "unknown.json")


def _series(count: int, value: int) -> dict[str, list[int]]:
    return {"discarded_warmup": [value], "samples": [value] * count}


def test_performance_nearest_rank_and_budget_denial(tmp_path: Path) -> None:
    measurements = {"first_critical_cold": _series(5, 3000), "first_critical_warm": _series(10, 1500), "full_hydration_cold": _series(5, 10000), "full_hydration_warm": _series(10, 6000), "api_cold": _series(10, 5000), "api_warm": _series(10, 2000), "isolated_timeout": _series(10, 20500), "palette": _series(10, 100), "filter_1000": _series(10, 150), "retry_visible": True}
    raw = {"schema": "kronos_v5_performance_input.v1", "capture_kind": "synthetic_fixture_evidence", "live_browser_execution": False, "nonce": NONCE, "fixture_sha256": NONCE, "source_sha256": NONCE, "measurements": measurements}
    source, first, second = tmp_path / "performance.json", tmp_path / "result.json", tmp_path / "result-second.json"
    source.write_text(json.dumps(raw), encoding="utf-8")
    command = ["node", str(PERFORMANCE), "--input", str(source), "--out"]
    _run(command + [str(first)])
    _run(command + [str(second)])
    assert first.exists() and second.exists()
    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text(encoding="utf-8"))["p95_ms"]["palette_ms"] == 100
    raw["measurements"]["palette"]["samples"][-1] = 101
    source.write_text(json.dumps(raw), encoding="utf-8")
    bad_out = tmp_path / "over-budget.json"
    result = _run(command + [str(bad_out)], expected=1)
    assert "performance failed closed:" in result.stderr
    assert not bad_out.exists()


def _security_input(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    root = tmp_path / "evidence"
    root.mkdir(parents=True)
    (root / "fixture.json").write_text("{}", encoding="utf-8")
    (root / "source.py").write_text("", encoding="utf-8")
    raw = {"schema": "kronos_v5_security_input.v1", "capture_kind": "synthetic_fixture_evidence", "live_browser_execution": False, "nonce": NONCE, "fixture_ref": _ref(root, "fixture.json", "application/json"), "source_ref": _ref(root, "source.py", "text/x-python"), "downloads": [{"id": "download-allowed-export", "disposition": "allowed", "status": 200, "relative_path": "export.json"}, {"id": "download-denied-traversal", "disposition": "denied", "status": 403, "relative_path": None}], "probes": [dict(item) for item in [*DENIAL_PROBES, *MUTATION_PROBES]]}
    source = tmp_path / "security.json"
    source.write_text(json.dumps(raw), encoding="utf-8")
    return source, root, raw


def _assert_security_fails(source: Path, root: Path, out: Path) -> None:
    result = _run([sys.executable, str(SECURITY), "--input", str(source), "--evidence-root", str(root), "--out", str(out)], expected=1)
    assert "security failed closed:" in result.stderr
    assert not out.exists()


def test_security_validates_exact_denial_matrix_and_rejects_generic_or_accepted_probes(tmp_path: Path) -> None:
    source, root, raw = _security_input(tmp_path)
    out = tmp_path / "security-result.json"
    _run([sys.executable, str(SECURITY), "--input", str(source), "--evidence-root", str(root), "--out", str(out)])
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["denied_probe_kinds"] == ["oos", "reparse", "traversal"]
    assert result["v5_mutation_methods_rejected"] == ["DELETE", "PATCH", "POST", "PUT"]
    assert result["capture_kind"] == "synthetic_fixture_evidence" and result["live_browser_execution"] is False
    assert result["allowed_downloads"] == 1 and result["denied_downloads"] == 1

    raw["probes"][0]["path"] = "/api/v5/generic-denied"
    raw["probes"][0]["payload"] = "denied"
    source.write_text(json.dumps(raw), encoding="utf-8")
    assert "security failed closed:" in _run([sys.executable, str(SECURITY), "--input", str(source), "--evidence-root", str(root), "--out", str(tmp_path / "generic.json")], expected=1).stderr

    source, root, raw = _security_input(tmp_path / "status")
    raw["probes"][1]["status"] = 403
    source.write_text(json.dumps(raw), encoding="utf-8")
    assert "security failed closed:" in _run([sys.executable, str(SECURITY), "--input", str(source), "--evidence-root", str(root), "--out", str(tmp_path / "status.json")], expected=1).stderr

    source, root, raw = _security_input(tmp_path / "duplicate")
    raw["probes"][1]["id"] = raw["probes"][0]["id"]
    source.write_text(json.dumps(raw), encoding="utf-8")
    assert "security failed closed:" in _run([sys.executable, str(SECURITY), "--input", str(source), "--evidence-root", str(root), "--out", str(tmp_path / "duplicate-probe.json")], expected=1).stderr

    source, root, raw = _security_input(tmp_path / "accepted")
    raw["probes"][-1]["accepted"] = True
    source.write_text(json.dumps(raw), encoding="utf-8")
    assert "security failed closed:" in _run([sys.executable, str(SECURITY), "--input", str(source), "--evidence-root", str(root), "--out", str(tmp_path / "accepted.json")], expected=1).stderr


def test_security_rejects_live_flags_unknown_fields_and_one_sided_downloads(tmp_path: Path) -> None:
    source, root, raw = _security_input(tmp_path / "missing-live")
    raw.pop("live_browser_execution")
    source.write_text(json.dumps(raw), encoding="utf-8")
    _assert_security_fails(source, root, tmp_path / "missing-live-security.json")

    source, root, raw = _security_input(tmp_path / "true-live")
    raw["live_browser_execution"] = True
    source.write_text(json.dumps(raw), encoding="utf-8")
    _assert_security_fails(source, root, tmp_path / "true-live-security.json")

    source, root, raw = _security_input(tmp_path / "unknown")
    raw["unexpected_field"] = "synthetic"
    source.write_text(json.dumps(raw), encoding="utf-8")
    _assert_security_fails(source, root, tmp_path / "unknown-security.json")

    source, root, raw = _security_input(tmp_path / "missing-allowed")
    raw["downloads"] = [raw["downloads"][1]]
    source.write_text(json.dumps(raw), encoding="utf-8")
    _assert_security_fails(source, root, tmp_path / "missing-allowed.json")

    source, root, raw = _security_input(tmp_path / "missing-denied")
    raw["downloads"] = [raw["downloads"][0]]
    source.write_text(json.dumps(raw), encoding="utf-8")
    _assert_security_fails(source, root, tmp_path / "missing-denied.json")
