"""Tests for the dashboard-v3 execution-boundary verifier (plan Todo 4).

The security-critical unit is the Gate-A allowlist diff-guard: any change to
webui/app.py outside the allowlisted function/line ranges must fail. These tests
also assert the integration base is a real ancestor of HEAD, that a non-ancestor
is rejected, that the frozen-file ownership (incl. rl_events.py schema-frozen)
is recorded, and that the route snapshot is deterministic.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "verify_dashboard_v3_execution_boundaries.py"

# Git empty-tree object: a valid object that is NOT an ancestor commit of HEAD.
_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _load():
    spec = importlib.util.spec_from_file_location("verify_boundaries_mod", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


vb = _load()


# --------------------------------------------------------------------------- #
# Diff hunk parsing
# --------------------------------------------------------------------------- #
def test_changed_line_ranges_parses_new_file_ranges():
    diff = (
        "diff --git a/webui/app.py b/webui/app.py\n"
        "--- a/webui/app.py\n+++ b/webui/app.py\n"
        "@@ -399,1 +399,3 @@\n+a\n+b\n+c\n"
        "@@ -1000,2 +1010,2 @@\n-x\n+y\n"
    )
    assert vb._changed_line_ranges(diff) == [(399, 401), (1010, 1011)]


def test_changed_line_ranges_single_line_hunk_without_count():
    diff = "@@ -10 +2521 @@\n+app.run(debug=False)\n"
    assert vb._changed_line_ranges(diff) == [(2521, 2521)]


# --------------------------------------------------------------------------- #
# Allowlist membership
# --------------------------------------------------------------------------- #
def test_within_allowlist_accepts_fully_contained_range():
    # cors_restriction is (399, 399); predict bounds (2133, 2352)
    assert vb._within_allowlist((399, 399), vb.GATE_A_ALLOWLIST) is True
    assert vb._within_allowlist((2140, 2145), vb.GATE_A_ALLOWLIST) is True


def test_within_allowlist_rejects_out_of_range_and_boundary_straddle():
    assert vb._within_allowlist((100, 100), vb.GATE_A_ALLOWLIST) is False
    # straddles the CORS line boundary -> not fully contained -> rejected
    assert vb._within_allowlist((398, 400), vb.GATE_A_ALLOWLIST) is False


# --------------------------------------------------------------------------- #
# Diff-guard end to end (git mocked to inject crafted app.py diffs)
# --------------------------------------------------------------------------- #
def _guard_with_diff(monkeypatch, diff_text: str):
    monkeypatch.setattr(vb, "_git", lambda repo, *args: (0, diff_text))
    return vb.check_app_py_diff_within_allowlist(_REPO_ROOT, base_ref="BASE")


def test_diff_guard_passes_for_allowlisted_cors_change(monkeypatch):
    report = _guard_with_diff(monkeypatch, "@@ -399,1 +399,1 @@\n-CORS(app)\n+CORS(app, origins=LOOPBACK)\n")
    assert report["ok"] is True
    assert report["violations"] == []


def test_diff_guard_fails_for_change_outside_allowlist(monkeypatch):
    # Line 950 (an /api/rl route) is NOT in the Gate-A allowlist.
    report = _guard_with_diff(monkeypatch, "@@ -950,1 +950,2 @@\n+injected\n+route\n")
    assert report["ok"] is False
    assert (950, 951) in report["violations"]


def test_diff_guard_fails_when_any_hunk_is_outside(monkeypatch):
    diff = (
        "@@ -399,1 +399,1 @@\n+CORS(app, origins=LOOPBACK)\n"       # allowed
        "@@ -3000,1 +3000,1 @@\n+sneaky = True\n"                    # NOT allowed
    )
    report = _guard_with_diff(monkeypatch, diff)
    assert report["ok"] is False
    assert (3000, 3000) in report["violations"]


def test_diff_guard_ok_when_no_diff(monkeypatch):
    report = _guard_with_diff(monkeypatch, "")
    assert report["ok"] is True
    assert report["changed_ranges"] == []


# --------------------------------------------------------------------------- #
# Ancestry (real git)
# --------------------------------------------------------------------------- #
def test_integration_base_is_ancestor_of_head():
    assert vb.is_ancestor(_REPO_ROOT, vb.INTEGRATION_BASE_SHA, "HEAD") is True


def test_empty_tree_is_not_an_ancestor():
    # The empty tree is a valid object but never an ancestor commit of HEAD.
    assert vb.is_ancestor(_REPO_ROOT, _EMPTY_TREE, "HEAD") is False


# --------------------------------------------------------------------------- #
# Frozen-file ownership + route snapshot
# --------------------------------------------------------------------------- #
def test_frozen_files_cover_the_four_protected_paths():
    keys = set(vb.FROZEN_FILES)
    assert keys == {
        "webui/app.py",
        "webui/rl_dashboard_tables.py",
        "webui/v2/__init__.py",
        "stom_rl/rl_events.py",
    }


def test_rl_events_is_schema_frozen_with_additive_info_permitted():
    note = vb.FROZEN_FILES["stom_rl/rl_events.py"]
    assert "SCHEMA_FROZEN" in note
    assert "additive info" in note.lower()


def test_app_py_is_gate_a_only():
    assert "GATE_A_ONLY" in vb.FROZEN_FILES["webui/app.py"]


def test_route_snapshot_is_deterministic_and_sorted():
    a = vb.app_py_route_snapshot(_REPO_ROOT)
    b = vb.app_py_route_snapshot(_REPO_ROOT)
    assert a == b  # deterministic
    assert a["routes"] == sorted(a["routes"])
    assert a["route_count"] == len(a["routes"]) >= 1
    assert len(a["file_sha256"]) == 64 and len(a["routes_sha256"]) == 64


def test_verify_boundaries_reports_expected_branch_and_base_ancestor():
    report = vb.verify_boundaries(_REPO_ROOT)
    assert report["gates"]["on_expected_branch"] is True
    assert report["gates"]["integration_base_is_ancestor"] is True
    assert report["gates"]["all_archival_are_ancestors"] is True
    assert report["diverged_branches"] == []
    # app.py must be unchanged from base during a non-Gate-A goal.
    assert report["app_py_allowlist_report"]["ok"] is True


# --------------------------------------------------------------------------- #
# Hardening fixes from architect review (G004 rev)
# --------------------------------------------------------------------------- #
def test_diff_guard_invokes_git_with_zero_context(monkeypatch):
    captured = {}

    def fake_git(repo, *args):
        captured["args"] = args
        return (0, "")

    monkeypatch.setattr(vb, "_git", fake_git)
    vb.check_app_py_diff_within_allowlist(_REPO_ROOT, base_ref="BASE")
    # -U0 keeps hunk headers to changed lines only, so a real ±context edit at an
    # allowlist boundary is not falsely rejected.
    assert "-U0" in captured["args"], captured["args"]


def test_diff_guard_fails_closed_on_git_error(monkeypatch):
    monkeypatch.setattr(vb, "_git", lambda repo, *a: (128, "fatal: bad revision 'nope'"))
    report = vb.check_app_py_diff_within_allowlist(_REPO_ROOT, base_ref="nope")
    assert report["ok"] is False  # fail CLOSED, not vacuously True
    assert report["error"]


def test_missing_declared_archival_branch_fails_the_gate():
    report = vb.verify_boundaries(_REPO_ROOT, archival_branches=("definitely/not/a/real/branch",))
    assert "definitely/not/a/real/branch" in report["missing_archival_branches"]
    assert report["gates"]["all_archival_are_ancestors"] is False


def test_git_output_is_decoded_as_utf8_on_non_utf8_windows_locale(monkeypatch):
    captured = {}

    class Completed:
        returncode = 0
        stdout = "한글 diff"
        stderr = ""

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return Completed()

    monkeypatch.setattr(vb.subprocess, "run", fake_run)
    code, output = vb._git(_REPO_ROOT, "diff")

    assert code == 0
    assert output == "한글 diff"
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
