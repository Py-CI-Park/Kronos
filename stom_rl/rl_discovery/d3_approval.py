"""Operator authentication for the D3 Smoke-to-Primary transition."""

from __future__ import annotations

import hashlib
import hmac

from stom_rl.daily_type1_contract import canonical_json_bytes


def smoke_approval_signature(
    key: bytes,
    *,
    run_name: str,
    prereg_sha: str,
    episode_sha: str,
    manifest_sha: str,
) -> str:
    """Authenticate the immutable Smoke identity with an operator-held key."""

    message = canonical_json_bytes({
        "episode_snapshot_sha256": episode_sha,
        "artifact_manifest_sha256": manifest_sha,
        "prereg_sha256": prereg_sha,
        "run_name": run_name,
    })
    return hmac.new(key, message, hashlib.sha256).hexdigest()
