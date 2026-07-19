"""Tests for the G008 dashboard-v4 browser matrix verifier.

The verifier is a stdlib-only, read-only checker for a browser-automation
transcript claiming full coverage of the 12 canonical tabs x 2 themes x
{375,768,1280} widths = 72 scenario matrix, including independently
re-decoded PNG artifact evidence (SHA-256/bytes/dimensions/non-uniform).

These tests synthesize one complete, valid fixture (real, non-uniform PNGs
encoded from scratch with stdlib zlib/struct, no Pillow, no browser, no
network) and then independently corrupt every major contract dimension to
prove the verifier fails closed: missing tuple, duplicate tuple, bad hash,
path traversal, non-GET request, runtime/console error, overflow, a11y
violation, keyboard/chart-semantic failure, and a missing performance
timing link. A last group proves the valid fixture itself passes.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import struct
import zlib
from pathlib import Path
from typing import Any, Dict, List, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "verify_dashboard_v4_browser_matrix.py"


def _load():
    spec = importlib.util.spec_from_file_location("verify_v4_matrix_mod", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


vm = _load()


# --------------------------------------------------------------------------- #
# PNG synthesis helpers (stdlib only)
# --------------------------------------------------------------------------- #


def _png_chunk(ctype: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)


def _make_png(width: int, height: int, seed: int, uniform: bool = False) -> bytes:
    """Encode a real, stdlib-decodable RGB PNG (color type 2, 8-bit, unfiltered)."""
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter type: None
        for x in range(width):
            if uniform:
                r, g, b = 10, 20, 30
            else:
                r = (x * 3 + seed) % 256
                g = (y * 5 + seed * 2) % 256
                b = (x + y + seed) % 256
            rows.extend((r, g, b))
    compressed = zlib.compress(bytes(rows), 6)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


def _write_artifact(artifacts_dir: Path, name: str, width: int, height: int, seed: int, uniform: bool = False) -> Dict[str, Any]:
    data = _make_png(width, height, seed, uniform=uniform)
    path = artifacts_dir / name
    path.write_bytes(data)
    return {
        "path": name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "width": width,
        "height": height,
        "non_uniform": not uniform,
    }


_ARTIFACT_HEIGHT = 60  # > MIN_ARTIFACT_HEIGHT (50)


def _make_scenario(tab: str, theme: str, width: int, artifacts_dir: Path, seed: int) -> Dict[str, Any]:
    name = f"{tab}_{theme}_{width}.png"
    artifact = _write_artifact(artifacts_dir, name, width, _ARTIFACT_HEIGHT, seed)
    return {
        "tab": tab,
        "theme": theme,
        "width": width,
        "status": "passed",
        "console_errors": [],
        "page_errors": [],
        "request_failures": [],
        "api_requests": [{"method": "GET", "url": "/api/mission-control/summary"}],
        "overflow_px": 0,
        "wcag_violations": {"A": 0, "AA": 0},
        "keyboard_check": "passed",
        "focus_check": "passed",
        "chart_semantic_check": "passed",
        "timings_ms": {"first_card": 900.0, "full_hydration": 2100.0, "api": 400.0, "palette": 60.0},
        "artifact": artifact,
    }


def _make_full_transcript(artifacts_dir: Path) -> Dict[str, Any]:
    scenarios: List[Dict[str, Any]] = []
    seed = 1
    for tab in vm.CANONICAL_TABS:
        for theme in vm.THEMES:
            for width in vm.WIDTHS:
                scenarios.append(_make_scenario(tab, theme, width, artifacts_dir, seed))
                seed += 7
    return {"scenarios": scenarios}


def _run(transcript: Dict[str, Any], tmp_path: Path, artifacts_dir: Path) -> Tuple[int, Dict[str, Any]]:
    input_path = tmp_path / "transcript.json"
    out_path = tmp_path / "report.json"
    input_path.write_text(json.dumps(transcript), encoding="utf-8")
    code = vm.main(["--input", str(input_path), "--out", str(out_path), "--artifacts-root", str(artifacts_dir)])
    report = json.loads(out_path.read_text(encoding="utf-8"))
    return code, report


def _errors_flat(report: Dict[str, Any]) -> List[str]:
    flat = list(report["top_level_errors"])
    for r in report["scenario_results"]:
        flat.extend(r["errors"])
    return flat


# --------------------------------------------------------------------------- #
# Valid fixture: full 72-scenario matrix passes cleanly.
# --------------------------------------------------------------------------- #


def test_valid_full_matrix_passes(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 0, _errors_flat(report)
    assert report["ok"] is True
    assert report["expected_scenario_count"] == 72
    assert report["observed_scenario_count"] == 72
    assert report["passed_scenario_count"] == 72
    assert report["top_level_errors"] == []
    assert all(r["ok"] for r in report["scenario_results"])


def test_valid_matrix_covers_exactly_12x2x3(tmp_path: Path):
    assert len(vm.CANONICAL_TABS) == 12
    assert len(vm.THEMES) == 2
    assert len(vm.WIDTHS) == 3
    assert vm.EXPECTED_SCENARIO_COUNT == 72

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    tuples = {(s["tab"], s["theme"], s["width"]) for s in transcript["scenarios"]}
    assert len(tuples) == 72


# --------------------------------------------------------------------------- #
# Missing / duplicate tuple
# --------------------------------------------------------------------------- #


def test_missing_scenario_tuple_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    transcript["scenarios"].pop()  # drop last -> one required tuple missing

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert report["ok"] is False
    assert any("missing required scenario" in e for e in report["top_level_errors"])


def test_duplicate_scenario_tuple_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    dup = copy.deepcopy(transcript["scenarios"][0])
    transcript["scenarios"].append(dup)

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert report["ok"] is False
    assert any("duplicate scenario" in e for e in _errors_flat(report))


# --------------------------------------------------------------------------- #
# Artifact evidence corruption
# --------------------------------------------------------------------------- #


def test_bad_artifact_hash_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    transcript["scenarios"][0]["artifact"]["sha256"] = "0" * 64

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("sha256" in e for e in _errors_flat(report))


def test_artifact_path_traversal_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)

    # Plant a real file just outside artifacts_dir that the traversal would hit.
    escape_target = tmp_path / "escaped.png"
    escape_target.write_bytes(_make_png(375, _ARTIFACT_HEIGHT, seed=99))
    transcript["scenarios"][0]["artifact"]["path"] = "../escaped.png"

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("escapes artifacts root" in e for e in _errors_flat(report))


def test_artifact_absolute_path_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    transcript["scenarios"][0]["artifact"]["path"] = "/etc/passwd"

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("absolute" in e for e in _errors_flat(report))


def test_artifact_missing_file_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    transcript["scenarios"][0]["artifact"]["path"] = "does_not_exist.png"

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("not found" in e for e in _errors_flat(report))


def test_artifact_tiny_placeholder_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)

    tiny = _make_png(1, 1, seed=1)
    assert len(tiny) < vm.MIN_ARTIFACT_BYTES
    name = "tiny.png"
    (artifacts_dir / name).write_bytes(tiny)
    scenario = transcript["scenarios"][0]
    scenario["artifact"] = {
        "path": name,
        "sha256": hashlib.sha256(tiny).hexdigest(),
        "bytes": len(tiny),
        "width": 1,
        "height": 1,
        "non_uniform": False,
    }

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    flat = _errors_flat(report)
    assert any("too small" in e for e in flat)


def test_artifact_blank_uniform_image_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)

    scenario = transcript["scenarios"][0]
    width = scenario["width"]
    blank = _make_png(width, _ARTIFACT_HEIGHT, seed=1, uniform=True)
    name = "blank.png"
    (artifacts_dir / name).write_bytes(blank)
    scenario["artifact"] = {
        "path": name,
        "sha256": hashlib.sha256(blank).hexdigest(),
        "bytes": len(blank),
        "width": width,
        "height": _ARTIFACT_HEIGHT,
        "non_uniform": True,  # transcript falsely claims non-uniform
    }

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("uniform" in e for e in _errors_flat(report))


def test_artifact_dimension_mismatch_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    transcript["scenarios"][0]["artifact"]["width"] = 999

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("does not match decoded PNG width" in e for e in _errors_flat(report))


# --------------------------------------------------------------------------- #
# Behavioral contract corruption
# --------------------------------------------------------------------------- #


def test_non_get_api_request_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    transcript["scenarios"][0]["api_requests"].append({"method": "POST", "url": "/api/x"})

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("method must be GET" in e for e in _errors_flat(report))


def test_console_error_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    transcript["scenarios"][0]["console_errors"] = ["TypeError: boom"]

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("console_errors must be empty" in e for e in _errors_flat(report))


def test_runtime_status_failure_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    transcript["scenarios"][0]["status"] = "failed"

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("status must be 'passed'" in e for e in _errors_flat(report))


def test_overflow_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    transcript["scenarios"][0]["overflow_px"] = 12

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("overflow_px must be 0" in e for e in _errors_flat(report))


def test_wcag_violation_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    transcript["scenarios"][0]["wcag_violations"]["AA"] = 2

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("wcag_violations.AA must be 0" in e for e in _errors_flat(report))


def test_keyboard_check_failure_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    transcript["scenarios"][0]["keyboard_check"] = "failed"

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("keyboard_check must be 'passed'" in e for e in _errors_flat(report))


def test_chart_semantic_failure_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    transcript["scenarios"][0]["chart_semantic_check"] = "failed"

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("chart_semantic_check must be 'passed'" in e for e in _errors_flat(report))


def test_missing_performance_timing_link_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    del transcript["scenarios"][0]["timings_ms"]["full_hydration"]

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("timings_ms.full_hydration" in e for e in _errors_flat(report))


def test_unknown_tab_fails_closed(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    transcript = _make_full_transcript(artifacts_dir)
    transcript["scenarios"][0]["tab"] = "not-a-real-tab"

    code, report = _run(transcript, tmp_path, artifacts_dir)

    assert code == 1
    assert any("unknown tab id" in e for e in _errors_flat(report))
    # The canonical tuple this scenario should have covered is now unfulfilled.
    assert any("missing required scenario" in e for e in report["top_level_errors"])


# --------------------------------------------------------------------------- #
# PNG decoder unit checks (independent of the transcript orchestration)
# --------------------------------------------------------------------------- #


def test_decode_png_roundtrip_matches_synthesis_dimensions():
    data = _make_png(16, 12, seed=5)
    width, height, channels, pixels = vm.decode_png(data)
    assert (width, height, channels) == (16, 12, 3)
    assert len(pixels) == 16 * 12 * 3
    assert vm.pixels_are_non_uniform(pixels, channels) is True


def test_decode_png_rejects_bad_signature():
    try:
        vm.decode_png(b"not a png at all")
        assert False, "expected VerifyError"
    except vm.VerifyError:
        pass


def test_pixels_are_non_uniform_detects_flat_image():
    data = _make_png(8, 8, seed=1, uniform=True)
    _, _, channels, pixels = vm.decode_png(data)
    assert vm.pixels_are_non_uniform(pixels, channels) is False
