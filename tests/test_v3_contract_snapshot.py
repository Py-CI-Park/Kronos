# -*- coding: utf-8 -*-
"""F6 source-substring contract harness -- pytest gate.

This test proves the harness in ``tests/_v3_contract.py`` captures every
source-substring assertion in the two Gate-T dashboard test files with no
silent drop, agrees with the current source at baseline, and stays in lockstep
with the committed ``tests/_v3_contract_snapshot.json`` baseline.

It adds only this new file; it never touches app source or an existing test.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _v3_contract as contract  # noqa: E402


def test_reconciliation_holds():
    """No assert may be silently dropped: both the node-level and the expanded
    equations must balance."""
    snapshot = contract.build_snapshot()
    counts = snapshot["counts"]

    # Node-level: every physical ``ast.Assert`` is accounted for exactly once.
    node_sum = (
        counts["present"]
        + counts["absent"]
        + counts["loop_nodes"]
        + counts["e1"]
        + counts["e2"]
    )
    assert node_sum == counts["physical_assert_nodes"], (
        node_sum,
        counts["physical_assert_nodes"],
    )

    # Expanded (loop-list elements counted individually), per the F6 contract:
    # classified == total_asserts - |E1| - |E2|.
    assert counts["classified"] == counts["total_asserts"] - counts["e1"] - counts["e2"]
    assert counts["classified"] == (
        counts["present"]
        + counts["absent"]
        + counts["loop_present_expanded"]
        + counts["loop_absent_expanded"]
    )

    # The two Gate-T files must both have contributed.
    assert set(counts["per_file"]) == {
        "tests/test_daily_ohlcv_dashboard_tab.py",
        "tests/test_stom_rl_dashboard_tab.py",
    }
    assert counts["present"] > 0 and counts["absent"] > 0


def test_verify_snapshot_passes_against_current_source():
    """Baseline green: re-reading the current source reproduces every PRESENT
    / ABSENT assertion the Gate-T tests make."""
    contract.verify_snapshot(contract.build_snapshot())


def test_fresh_snapshot_matches_committed_baseline():
    """Drift guard: a freshly built snapshot must equal the committed JSON.

    A mismatch means a Gate-T source-substring assertion was added, removed, or
    changed without regenerating ``tests/_v3_contract_snapshot.json`` via
    ``py -3.11 tests/_gen_v3_contract_snapshot.py``.
    """
    fresh = contract.build_snapshot()
    committed = json.loads(contract.SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert fresh == committed


def test_edge_literals_are_captured_intact():
    """The four ast-only edge cases survive parsing without corruption."""
    snapshot = contract.build_snapshot()
    present = contract.all_present_literals(snapshot)
    absent = contract.all_absent_literals(snapshot)

    # 1. Mixed single/double quotes: '"name": "kronos-dashboard"' -> PRESENT.
    assert '"name": "kronos-dashboard"' in present

    # 2. Loop-list ABSENT label expanded from a `for ... in [...]:` block.
    assert "KRONOS_V2_DIST" in absent

    # 3. `#` inside a string literal is NOT a comment (would be truncated by a
    #    naive regex) -> ABSENT, captured whole.
    assert "`<strong>#${row" in absent
    assert "`<strong>${row" in absent

    # 4. Unicode escapes decode to real Hangul -> PRESENT.
    assert "Kronos 대시보드" in present


def test_e1_e2_classification_is_stable():
    """Structural (E1) vs build-conditional (E2) exclusions match the known
    baseline: zero E1, and exactly the five dist-bundle asserts as E2."""
    snapshot = contract.build_snapshot()
    assert snapshot["counts"]["e1"] == 0
    assert snapshot["counts"]["e2"] == 5
    e2_lines = {(r["file"], r["lineno"]) for r in snapshot["e2"]}
    assert e2_lines == {
        ("tests/test_stom_rl_dashboard_tab.py", n) for n in (184, 185, 186, 187, 188)
    }
