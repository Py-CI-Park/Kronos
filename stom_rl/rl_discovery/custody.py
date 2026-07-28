"""Portable custody manifest for ignored discovery model bundles."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from stom_rl.rl_discovery.storage import JsonValue, atomic_write_json


class ArtifactDigest(BaseModel):
    """Content identity for one file in a local evidence bundle."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    path: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReceiptBoundary(BaseModel):
    """Terminal claims copied into custody without trusting untyped JSON."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    status: str
    verdict: str
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    promotion_allowed: Literal[False]
    profitability_claim_allowed: Literal[False]
    prereg_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixture_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class CustodyManifest(BaseModel):
    """Reviewable identity for a large run whose binaries remain ignored."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["kronos.rl-discovery.custody.v1"]
    run_name: str
    producer_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    producer_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prereg_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixture_binding: Literal["RECEIPT_BOUND", "PRODUCER_DECLARED_LEGACY_UNVERIFIED"]
    terminal_status: str
    terminal_verdict: str
    fresh_oos: Literal["NOT_RUN_NO_READ"]
    artifact_count: int = Field(ge=0)
    artifact_bytes: int = Field(ge=0)
    artifacts: tuple[ArtifactDigest, ...]
    evidence_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_digests(run_dir: Path) -> tuple[ArtifactDigest, ...]:
    root = run_dir.resolve()
    entries: list[ArtifactDigest] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        resolved = path.resolve()
        if not path.is_file() or not resolved.is_relative_to(root):
            continue
        entries.append(
            ArtifactDigest(
                path=path.relative_to(root).as_posix(),
                size_bytes=path.stat().st_size,
                sha256=_sha256_file(path),
            )
        )
    return tuple(entries)


def _manifest_digest(artifacts: tuple[ArtifactDigest, ...]) -> str:
    payload = [
        {"path": item.path, "size_bytes": item.size_bytes, "sha256": item.sha256}
        for item in artifacts
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def build_custody_manifest(
    run_dir: Path,
    *,
    producer_commit: str,
    producer_tree: str,
    fixture_path: Path,
    prereg_path: Path,
) -> CustodyManifest:
    """Hash a complete terminal run and bind it to source/input revisions."""

    root = run_dir.resolve()
    receipt = ReceiptBoundary.model_validate_json(
        (root / "terminal_receipt.json").read_text(encoding="utf-8")
    )
    fixture_sha256 = _sha256_file(fixture_path)
    prereg_sha256 = _sha256_file(prereg_path)
    if not hmac.compare_digest(receipt.prereg_sha256, prereg_sha256):
        raise ValueError("preregistration hash does not match terminal receipt")
    if receipt.fixture_sha256 is not None and not hmac.compare_digest(
        receipt.fixture_sha256, fixture_sha256
    ):
        raise ValueError("fixture hash does not match terminal receipt")
    fixture_binding = (
        "RECEIPT_BOUND"
        if receipt.fixture_sha256 is not None
        else "PRODUCER_DECLARED_LEGACY_UNVERIFIED"
    )
    artifacts = _artifact_digests(root)
    return CustodyManifest(
        schema_version="kronos.rl-discovery.custody.v1",
        run_name=root.name,
        producer_commit=producer_commit,
        producer_tree=producer_tree,
        fixture_sha256=fixture_sha256,
        prereg_sha256=prereg_sha256,
        fixture_binding=fixture_binding,
        terminal_status=receipt.status,
        terminal_verdict=receipt.verdict,
        fresh_oos=receipt.fresh_oos,
        artifact_count=len(artifacts),
        artifact_bytes=sum(item.size_bytes for item in artifacts),
        artifacts=artifacts,
        evidence_manifest_sha256=_manifest_digest(artifacts),
    )


def write_custody_manifest(path: Path, manifest: CustodyManifest) -> None:
    """Atomically publish a small committed manifest, never the model binaries."""

    artifacts: list[JsonValue] = [
        {"path": item.path, "size_bytes": item.size_bytes, "sha256": item.sha256}
        for item in manifest.artifacts
    ]
    payload: dict[str, JsonValue] = {
        "schema_version": manifest.schema_version,
        "run_name": manifest.run_name,
        "producer_commit": manifest.producer_commit,
        "producer_tree": manifest.producer_tree,
        "fixture_sha256": manifest.fixture_sha256,
        "prereg_sha256": manifest.prereg_sha256,
        "fixture_binding": manifest.fixture_binding,
        "terminal_status": manifest.terminal_status,
        "terminal_verdict": manifest.terminal_verdict,
        "fresh_oos": manifest.fresh_oos,
        "artifact_count": manifest.artifact_count,
        "artifact_bytes": manifest.artifact_bytes,
        "artifacts": artifacts,
        "evidence_manifest_sha256": manifest.evidence_manifest_sha256,
    }
    atomic_write_json(path, payload)
