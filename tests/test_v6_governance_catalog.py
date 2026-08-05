"""Behavior coverage for the lightweight governance document ledger."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from webui.v6_governance_catalog import build_governance_catalog


def test_governance_catalog_hashes_preregistration_and_result_docs_without_run_scan(tmp_path: Path) -> None:
    # Given
    prereg = tmp_path / "kronos_v9_prereg_daily.json"
    prereg.write_text(
        json.dumps(
            {
                "prereg_id": "daily-v9-001",
                "status": "FROZEN",
                "frozen_utc": "2026-08-05T00:00:00Z",
                "algorithm": {"family": "CQL"},
            }
        ),
        encoding="utf-8",
    )
    result = tmp_path / "kronos_v9_result.md"
    result.write_text("# NO-GO\n", encoding="utf-8")

    # When
    catalog = build_governance_catalog(tmp_path)

    # Then
    assert catalog.preregistrations[0].prereg_id == "daily-v9-001"
    assert catalog.preregistrations[0].status == "FROZEN"
    assert catalog.preregistrations[0].linkage_state == "DETAIL_DEFERRED"
    assert catalog.result_docs[0].sha256 == hashlib.sha256(result.read_bytes()).hexdigest()


def test_governance_catalog_keeps_invalid_preregistration_visible(tmp_path: Path) -> None:
    # Given
    (tmp_path / "kronos_v9_prereg_broken.json").write_text("{broken", encoding="utf-8")

    # When
    catalog = build_governance_catalog(tmp_path)

    # Then
    assert catalog.preregistrations[0].status == "INVALID"
    assert catalog.preregistrations[0].prereg_id == "MISSING"
