"""Exact C2 source-identity tests using Git object bytes, never worktree bytes."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
from webui.v5_api_contract import V5ApiContractError, validate_source_identity

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("v5_score", ROOT / "scripts" / "score_kronos_dashboard_v5.py")
assert SPEC and SPEC.loader
v5_score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v5_score)
SCOPE = json.loads((ROOT / "docs" / "kronos_dashboard_v5_source_scope_v1.json").read_text(encoding="utf-8"))
ERROR_OWNER = "webui/v2_src/src/lib/v5SchemaValidationError.ts"
GENERATOR = "scripts/generate_kronos_v5_api_types.mjs"
HTTP = "webui/v2_src/src/lib/http.ts"

SOURCE_IDENTITY_SCHEMA = json.loads((ROOT / "docs" / "schemas" / "kronos_v5_source_identity.v1.schema.json").read_text(encoding="utf-8"))

def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def candidate_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "candidate"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "v5@example.invalid")
    _git(repo, "config", "user.name", "V5 Test")
    generator = repo / GENERATOR
    generator.parent.mkdir(parents=True)
    generator.write_text("export const generated = true;\n", encoding="utf-8")
    http = repo / HTTP
    http.parent.mkdir(parents=True)
    http.write_text("export async function fetchJson() {}\n", encoding="utf-8")
    error_owner = repo / ERROR_OWNER
    error_owner.write_text("export class V5SchemaValidationError extends Error {}\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "kronos_dashboard_v5_scorecard_v1.json").write_text("{}\n", encoding="utf-8")
    _commit(repo, "initial candidate")
    return repo


def _identity(repo: Path, candidate: str = "HEAD") -> dict:
    return v5_score.build_source_identity(candidate, SCOPE, repo)


def _member(identity: dict, path: str) -> dict:
    return next(entry for entry in identity["files"] if entry["path"] == path)


def test_scope_is_exact_closed_six_field_contract_and_selected_owners_are_in_scope():
    assert set(SCOPE) == {"schema", "include", "exclude", "forbid_modes", "path_policy", "blob_basis"}
    assert SCOPE["schema"] == "kronos_source_scope.v1"
    assert SCOPE["path_policy"] == "UTF8-NFC-POSIX-CASE-COLLISION-FORBIDDEN"
    assert SCOPE["blob_basis"] == "GIT_BLOB_CONTENT_BYTES"
    for path in (ERROR_OWNER, GENERATOR, HTTP):
        assert any(v5_score.restricted_posix_glob_matches(pattern, path) for pattern in SCOPE["include"])
        assert v5_score._selected(path, SCOPE)
        assert not any(v5_score.restricted_posix_glob_matches(pattern, path) for pattern in SCOPE["exclude"])
    assert not v5_score._selected("docs/kronos_dashboard_v5_source_scope_v1.json", SCOPE)
    assert "docs/kronos_dashboard_v5_source_scope_v1.json" in SCOPE["exclude"]
    assert "docs/kronos_dashboard_v5_source_identity_v1.json" in SCOPE["exclude"]


def test_literal_error_owner_member_uses_approved_tree_raw_blob_path_mode_hash_and_length(candidate_repo: Path):
    commit = _git(candidate_repo, "rev-parse", "HEAD")
    identity = _identity(candidate_repo, commit)
    raw_blob = subprocess.run(["git", "show", f"{commit}:{ERROR_OWNER}"], cwd=candidate_repo, check=True, stdout=subprocess.PIPE).stdout
    member = _member(identity, ERROR_OWNER)
    assert identity["schema"] == "kronos_source_identity.v1"
    assert identity["source_commit"] == commit
    assert identity["source_tree"] == _git(candidate_repo, "rev-parse", f"{commit}^{{tree}}")
    assert identity["scope_manifest_sha256"] == v5_score._CANONICAL_SCOPE_DIGEST
    assert member == {"path": ERROR_OWNER, "git_mode": "100644", "sha256": hashlib.sha256(raw_blob).hexdigest(), "byte_length": len(raw_blob)}
    assert identity["files"] == sorted(identity["files"], key=lambda entry: entry["path"].encode("utf-8"))


def test_source_identity_schema_digest_is_bound_to_scorer_and_contract_runs_schema_then_semantic_validation(candidate_repo: Path):
    identity = _identity(candidate_repo)
    assert SOURCE_IDENTITY_SCHEMA["properties"]["scope_manifest_sha256"]["const"] == v5_score._CANONICAL_SCOPE_DIGEST
    validate_source_identity(identity)
    unordered = json.loads(json.dumps(identity))
    unordered["files"].reverse()
    with pytest.raises(V5ApiContractError, match="authoritative C2 source identity"):
        validate_source_identity(unordered)


def test_error_owner_http_and_generator_content_delete_and_mode_mutations_change_c2_source_sha(candidate_repo: Path):
    initial = _identity(candidate_repo)
    error_owner = candidate_repo / ERROR_OWNER
    error_owner.write_text("export class V5SchemaValidationError extends Error { readonly code = 'C2'; }\n", encoding="utf-8")
    error_content = _identity(candidate_repo, _commit(candidate_repo, "error owner content"))
    _git(candidate_repo, "update-index", "--chmod=+x", ERROR_OWNER)
    error_mode = _identity(candidate_repo, _commit(candidate_repo, "error owner mode"))
    http = candidate_repo / HTTP
    http.write_text("export async function fetchJson() { return null; }\n", encoding="utf-8")
    http_content = _identity(candidate_repo, _commit(candidate_repo, "http content"))
    generator = candidate_repo / GENERATOR
    generator.write_text("export const generated = false;\n", encoding="utf-8")
    generator_content = _identity(candidate_repo, _commit(candidate_repo, "generator content"))
    error_owner.unlink()
    deleted = _identity(candidate_repo, _commit(candidate_repo, "delete error owner"))
    hashes = [v5_score.source_identity_sha256(value) for value in (initial, error_content, error_mode, http_content, generator_content, deleted)]
    assert len(set(hashes)) == len(hashes)
    assert _member(error_content, ERROR_OWNER)["sha256"] != _member(initial, ERROR_OWNER)["sha256"]
    assert _member(error_mode, ERROR_OWNER)["git_mode"] == "100755"
    assert _member(http_content, HTTP)["sha256"] != _member(error_mode, HTTP)["sha256"]
    assert _member(generator_content, GENERATOR)["sha256"] != _member(http_content, GENERATOR)["sha256"]
    assert ERROR_OWNER not in {entry["path"] for entry in deleted["files"]}


def test_dirty_worktree_is_not_a_c2_input(candidate_repo: Path):
    before = _identity(candidate_repo)
    (candidate_repo / ERROR_OWNER).write_text("uncommitted worktree mutation\n", encoding="utf-8")
    (candidate_repo / "generated.txt").write_text("also ignored\n", encoding="utf-8")
    assert _identity(candidate_repo) == before


def test_source_identity_sha256_rejects_boolean_byte_length(candidate_repo: Path):
    identity = _identity(candidate_repo)
    identity["files"][0]["byte_length"] = True
    with pytest.raises(v5_score.ScorecardError, match="byte_length"):
        v5_score.source_identity_sha256(identity)

def test_supplied_identity_rejects_out_of_scope_and_casefold_collision(candidate_repo: Path):
    identity = _identity(candidate_repo)
    out_of_scope = json.loads(json.dumps(identity))
    out_of_scope["files"][0]["path"] = "unselected.txt"
    with pytest.raises(v5_score.ScorecardError, match="out-of-scope"):
        v5_score.source_identity_sha256(out_of_scope)
    collision = json.loads(json.dumps(identity))
    member = dict(_member(collision, HTTP))
    member["path"] = "webui/v2_src/src/lib/HTTP.ts"
    collision["files"].append(member)
    collision["files"].sort(key=lambda entry: entry["path"].encode("utf-8"))
    with pytest.raises(v5_score.ScorecardError, match="case-fold"):
        v5_score.source_identity_sha256(collision)


def test_empty_selection_sha256_object_format_and_symlink_fail_closed(candidate_repo: Path):
    empty = candidate_repo / "empty"
    empty.mkdir()
    _git(empty, "init")
    _git(empty, "config", "user.email", "v5@example.invalid")
    _git(empty, "config", "user.name", "V5 Test")
    (empty / "unselected.txt").write_text("x\n", encoding="utf-8")
    _commit(empty, "empty selection")
    with pytest.raises(v5_score.SourceIdentityError, match="must not be empty"):
        _identity(empty)
    created = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=candidate_repo, input=b"target", stdout=subprocess.PIPE, check=True).stdout.decode().strip()
    index = candidate_repo / "index"
    env = {**__import__("os").environ, "GIT_INDEX_FILE": str(index)}
    subprocess.run(["git", "read-tree", "HEAD"], cwd=candidate_repo, env=env, check=True)
    subprocess.run(["git", "update-index", "--add", "--cacheinfo", f"120000,{created},webui/v2_src/src/link.ts"], cwd=candidate_repo, env=env, check=True)
    tree = subprocess.run(["git", "write-tree"], cwd=candidate_repo, env=env, stdout=subprocess.PIPE, check=True).stdout.decode().strip()
    commit = _git(candidate_repo, "commit-tree", tree, "-p", "HEAD", "-m", "symlink")
    with pytest.raises(v5_score.SourceIdentityError, match="forbidden"):
        _identity(candidate_repo, commit)
    sha256_repo = candidate_repo.parent / "sha256"
    initialized = subprocess.run(["git", "init", "--object-format=sha256", str(sha256_repo)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if initialized.returncode != 0:
        pytest.skip("Git does not support SHA-256 object-format repositories")
    _git(sha256_repo, "config", "user.email", "v5@example.invalid")
    _git(sha256_repo, "config", "user.name", "V5 Test")
    owner = sha256_repo / ERROR_OWNER
    owner.parent.mkdir(parents=True)
    owner.write_text("export const v5 = true;\n", encoding="utf-8")
    _commit(sha256_repo, "sha256")
    with pytest.raises(v5_score.SourceIdentityError, match="SHA-1"):
        _identity(sha256_repo)
