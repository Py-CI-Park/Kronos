"""Lightweight, read-only governance ledger built only from direct documents."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

PREREG_GLOBS: Final = ("kronos_v*_prereg_*.json", "kronos_v6_prereg_*.json")
RESULT_DOC_RE: Final = re.compile(r"^kronos_v[0-9][0-9a-z_\-]*\.md$")
MAX_PREREG_BYTES: Final = 2 * 1024 * 1024
MAX_PREREGISTRATIONS: Final = 120
MAX_RESULT_DOCS: Final = 240


@dataclass(frozen=True, slots=True)
class GovernancePreregistration:
    prereg_id: str
    doc: str
    status: str
    frozen_utc: str
    family: str
    sha256: str
    linkage_state: str


@dataclass(frozen=True, slots=True)
class GovernanceResultDoc:
    doc: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class GovernanceCatalog:
    preregistrations: tuple[GovernancePreregistration, ...]
    result_docs: tuple[GovernanceResultDoc, ...]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(128 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _family(mapping) -> str:
    algorithm = mapping.get("algorithm")
    if type(algorithm) is dict:
        family = algorithm.get("family")
        if type(family) is str and family.strip():
            return family.strip()
    return "MISSING"


def _preregistration(path: Path) -> GovernancePreregistration:
    sha256 = _sha256_file(path)
    try:
        if path.stat().st_size > MAX_PREREG_BYTES:
            raise json.JSONDecodeError("preregistration too large", "", 0)
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return GovernancePreregistration("MISSING", path.name, "INVALID", "MISSING", "MISSING", sha256, "DETAIL_DEFERRED")
    if type(raw) is not dict:
        return GovernancePreregistration("MISSING", path.name, "INVALID", "MISSING", "MISSING", sha256, "DETAIL_DEFERRED")
    prereg_id = raw.get("prereg_id")
    status = raw.get("status")
    frozen_utc = raw.get("frozen_utc")
    return GovernancePreregistration(
        prereg_id.strip() if type(prereg_id) is str and prereg_id.strip() else "MISSING",
        path.name,
        status.strip() if type(status) is str and status.strip() else "MISSING",
        frozen_utc.strip() if type(frozen_utc) is str and frozen_utc.strip() else "MISSING",
        _family(raw),
        sha256,
        "DETAIL_DEFERRED",
    )


def _prereg_paths(root: Path) -> tuple[Path, ...]:
    seen: set[Path] = set()
    paths: list[Path] = []
    for pattern in PREREG_GLOBS:
        try:
            for path in root.glob(pattern):
                if path.is_file() and not path.is_symlink() and path not in seen:
                    seen.add(path)
                    paths.append(path)
        except OSError:
            continue
    return tuple(sorted(paths)[:MAX_PREREGISTRATIONS])


def _result_docs(root: Path) -> tuple[GovernanceResultDoc, ...]:
    try:
        paths = tuple(
            path
            for path in sorted(root.glob("kronos_v*_*.md"), reverse=True)
            if path.is_file() and not path.is_symlink() and RESULT_DOC_RE.fullmatch(path.name) is not None
        )[:MAX_RESULT_DOCS]
    except OSError:
        return ()
    docs: list[GovernanceResultDoc] = []
    for path in paths:
        try:
            docs.append(GovernanceResultDoc(path.name, path.stat().st_size, _sha256_file(path)))
        except OSError:
            continue
    return tuple(docs)


def build_governance_catalog(root: Path) -> GovernanceCatalog:
    preregistrations = tuple(
        sorted(
            (_preregistration(path) for path in _prereg_paths(root)),
            key=lambda item: (item.frozen_utc, item.doc),
            reverse=True,
        )
    )
    return GovernanceCatalog(preregistrations, _result_docs(root))
