from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pydantic import TypeAdapter

PAYLOAD_ADAPTER = TypeAdapter(dict[str, object])


def test_direct_app_import_keeps_research_telemetry_and_governance_routes() -> None:
    # Given: the same top-level import context used by `py webui/app.py`.
    repository_root = Path(__file__).resolve().parents[1]
    script = (
        "import json, app; "
        "diagnostics=app.app.config['KRONOS_SUBSYSTEM_DIAGNOSTICS']; "
        "routes=sorted(str(rule) for rule in app.app.url_map.iter_rules()); "
        "print(json.dumps({'diagnostics':diagnostics,'routes':routes}))"
    )

    # When: the dashboard application is constructed from the webui directory.
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repository_root / "webui",
        capture_output=True,
        check=True,
        text=True,
    )
    payload = PAYLOAD_ADAPTER.validate_json(completed.stdout)
    diagnostics = PAYLOAD_ADAPTER.validate_python(payload["diagnostics"])
    routes = TypeAdapter(tuple[str, ...]).validate_python(payload["routes"])

    # Then: the UI cannot start successfully while omitting its read-only APIs.
    for subsystem in (
        "v6_platform",
        "v6_insight",
        "v6_research",
        "v6_telemetry",
        "v6_governance",
    ):
        state = PAYLOAD_ADAPTER.validate_python(diagnostics[subsystem])
        assert state["available"] is True
    assert "/api/v6/summary" in routes
    assert "/api/v6/telemetry-runs" in routes
    assert "/api/v6/governance-summary" in routes
    assert "/api/v6/status" in routes
    assert "/api/v6/insight/regime" in routes
