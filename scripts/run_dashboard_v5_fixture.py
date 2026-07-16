"""Isolated synthetic fixture lifecycle for dashboard V5 QA.

This module never starts a product backend.  It starts a tiny loopback-only child
whose only contract is a nonce-bound readiness record.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from typing import Any

import rfc8785


class FixtureError(RuntimeError):
    pass

_LOOPBACK_HOST = "127.0.0.1"
_START_READY_TIMEOUT_SECONDS = 5.0
_CHILDREN: dict[int, subprocess.Popen] = {}


def _bounded_seconds(value: float, label: str) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError) as exc:
        raise FixtureError(f"{label} must be a finite positive timeout") from exc
    if not math.isfinite(seconds) or seconds <= 0:
        raise FixtureError(f"{label} must be a finite positive timeout")
    return seconds


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    process = _CHILDREN.get(pid)
    if process is None:
        return False
    if process.pid != pid:
        return False
    running = process.poll() is None
    if not running:
        _CHILDREN.pop(pid, None)
    return running


def _stop_pid(pid: int, *, grace_seconds: float, force_seconds: float) -> str:
    process = _CHILDREN.get(pid)
    if process is None or process.pid != pid:
        _CHILDREN.pop(pid, None)
        return "GRACEFUL"
    if process.poll() is not None:
        _CHILDREN.pop(pid, None)
        return "GRACEFUL"
    try:
        process.terminate()
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=force_seconds)
        except subprocess.TimeoutExpired as exc:
            raise FixtureError("fixture child did not exit after forced termination") from exc
        finally:
            _CHILDREN.pop(pid, None)
        return "FORCED"
    finally:
        if process.poll() is not None:
            _CHILDREN.pop(pid, None)
    return "GRACEFUL"


def _canonical(value: Any) -> bytes:
    return rfc8785.dumps(value)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _is_rfc3339_utc(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    offset = parsed.utcoffset()
    return offset is not None and offset.total_seconds() == 0.0


def _reject_symlinked_ancestors(path: Path, label: str) -> None:
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise FixtureError(f"{label} must not be a symlink or have symlinked ancestors")


def _temp_root(value: str | Path, label: str) -> Path:
    path = Path(value)
    if ".." in path.parts:
        raise FixtureError(f"{label} path traversal is forbidden")
    candidate = path if path.is_absolute() else Path.cwd() / path
    _reject_symlinked_ancestors(candidate, label)
    root = candidate.resolve(strict=False)
    temp = Path(tempfile.gettempdir()).resolve()
    root_parts = [part.lower() for part in root.parts]
    try:
        root.relative_to(temp)
    except ValueError as exc:
        raise FixtureError(f"{label} must be below the OS temporary directory") from exc
    if root_parts[-4:] == ["webui", "static", "v2", "dist"]:
        raise FixtureError(f"{label} must not target tracked dist")
    if root.name.lower() in {"oos", "database", "db"} or any(part in {"oos", "database", "db", "registry"} for part in root_parts[:-1]):
        raise FixtureError(f"{label} resembles a real OOS/database root")
    root.mkdir(parents=True, exist_ok=True)
    _reject_symlinked_ancestors(candidate, label)
    return root


def _write_canonical(path: Path, value: Any) -> bytes:
    raw = _canonical(value)
    path.write_bytes(raw)
    return raw


def _read_ready_record(descriptor: dict[str, Any]) -> tuple[int, str]:
    ready = Path(str(descriptor["readiness_path"]))
    value = json.loads(ready.read_text(encoding="utf-8"))
    pid = int(descriptor["pid"])
    descriptor_port = int(descriptor.get("port", 0))
    actual = (value.get("nonce"), value.get("pid"), value.get("host"))
    if actual != (descriptor["nonce"], pid, _LOOPBACK_HOST):
        raise FixtureError("readiness record does not bind fixture identity")
    actual_port = value.get("port")
    if not isinstance(actual_port, int) or isinstance(actual_port, bool) or actual_port < 1 or actual_port > 65535:
        raise FixtureError("readiness record missing safe loopback port")
    if descriptor_port not in (0, actual_port):
        raise FixtureError("readiness record does not bind fixture identity")
    timestamp = value.get("readiness_timestamp_utc")
    if not _is_rfc3339_utc(timestamp):
        raise FixtureError("readiness record missing RFC3339 UTC timestamp")
    return actual_port, timestamp


def start_fixture(*, registry_root: str | Path, artifact_root: str | Path, job_intent_root: str | Path,
                  source_sha256: str, fixture: dict[str, Any] | None = None) -> dict[str, Any]:
    """Start an ephemeral loopback fixture and return a closed descriptor."""
    if not isinstance(source_sha256, str) or len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise FixtureError("source_sha256 must be lowercase SHA-256")
    registry = _temp_root(registry_root, "registry_root")
    artifacts = _temp_root(artifact_root, "artifact_root")
    intents = _temp_root(job_intent_root, "job_intent_root")
    fixture_value = fixture or {"schema": "kronos_fixture.v2", "kind": "synthetic-loopback"}
    if fixture_value.get("schema") != "kronos_fixture.v2":
        raise FixtureError("fixture schema must be kronos_fixture.v2")
    fixture_sha = _sha(fixture_value)
    nonce = secrets.token_hex(32)
    readiness = registry / f"fixture-{nonce}.ready.json"
    child = (
        "import datetime,json,os,socket,sys; host,nonce,ready=sys.argv[1:]; "
        "s=socket.socket(socket.AF_INET,socket.SOCK_STREAM); "
        "opt=getattr(socket,'SO_EXCLUSIVEADDRUSE',None); "
        "s.setsockopt(socket.SOL_SOCKET,opt,1) if opt is not None else None; "
        "s.bind((host,0)); port=int(s.getsockname()[1]); s.listen(1); "
        "ready_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z'); "
        "ready_value={'nonce':nonce,'pid':os.getpid(),'host':host,'port':port,'readiness_timestamp_utc':ready_at}; "
        "f=open(ready,'w',encoding='utf-8'); f.write(json.dumps(ready_value,sort_keys=True,separators=(',',':'))); f.close(); "
        "s.settimeout(.2); "
        "\nwhile True:\n try:\n  conn,_=s.accept(); conn.close()\n except socket.timeout:\n  pass\n"
    )
    process = subprocess.Popen([sys.executable, "-c", child, _LOOPBACK_HOST, nonce, str(readiness)],
                               cwd=str(registry), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, close_fds=True)
    _CHILDREN[process.pid] = process
    descriptor = {
        "schema": "kronos_fixture.v2", "nonce": nonce, "pid": process.pid, "host": _LOOPBACK_HOST, "port": 0,
        "source_sha256": source_sha256, "fixture_sha256": fixture_sha,
        "registry_root": str(registry), "artifact_root": str(artifacts), "job_intent_root": str(intents),
        "readiness_path": str(readiness), "readiness_timestamp_utc": None, "cleanup_status": "RUNNING",
    }
    try:
        deadline = time.monotonic() + _START_READY_TIMEOUT_SECONDS
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if readiness.exists():
                try:
                    port, timestamp = _read_ready_record(descriptor)
                except (OSError, json.JSONDecodeError) as exc:
                    last_error = exc
                else:
                    descriptor["port"] = port
                    descriptor["readiness_timestamp_utc"] = timestamp
                    _write_canonical(registry / f"fixture-{nonce}.json", descriptor)
                    return descriptor
            if not _pid_is_running(process.pid):
                raise FixtureError("fixture child exited before readiness")
            time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
        detail = f"; last readiness read error: {last_error}" if last_error else ""
        raise FixtureError(f"fixture readiness timed out{detail}")
    except Exception:
        _stop_pid(process.pid, grace_seconds=0.5, force_seconds=1.0)
        raise


def wait_ready(descriptor: dict[str, Any], *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    """Verify nonce/PID/loopback readiness before returning an updated descriptor."""
    timeout = _bounded_seconds(timeout_seconds, "timeout_seconds")
    deadline = time.monotonic() + timeout
    ready = Path(str(descriptor["readiness_path"]))
    pid = int(descriptor["pid"])
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if ready.exists():
            try:
                port, timestamp = _read_ready_record(descriptor)
            except (OSError, json.JSONDecodeError) as exc:
                last_error = exc
            else:
                updated = dict(descriptor)
                updated["port"] = port
                updated["readiness_timestamp_utc"] = timestamp
                registry = Path(str(updated["registry_root"]))
                _write_canonical(registry / f"fixture-{updated['nonce']}.json", updated)
                return updated
        if not _pid_is_running(pid):
            _CHILDREN.pop(pid, None)
            raise FixtureError("fixture child exited before readiness")
        time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
    detail = f"; last readiness read error: {last_error}" if last_error else ""
    raise FixtureError(f"fixture readiness timed out{detail}")


def stop_fixture(descriptor: dict[str, Any], *, grace_seconds: float = 2.0,
                 force_seconds: float = 2.0) -> dict[str, Any]:
    """Gracefully terminate, then forcibly kill, only the recorded child PID."""
    result = dict(descriptor)
    pid = int(result["pid"])
    grace = _bounded_seconds(grace_seconds, "grace_seconds")
    force = _bounded_seconds(force_seconds, "force_seconds")
    result["cleanup_status"] = _stop_pid(pid, grace_seconds=grace, force_seconds=force)
    registry = Path(result["registry_root"])
    _write_canonical(registry / f"fixture-{result['nonce']}.json", result)
    return result
