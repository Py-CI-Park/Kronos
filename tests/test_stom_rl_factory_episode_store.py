import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from stom_rl.factory import episode_store
from stom_rl.factory.episode_store import (
    DEFAULT_EPISODE_CACHE_DIR,
    EpisodeRef,
    connect_readonly,
    list_sessions,
    list_stock_tables,
    load_episode,
    sample_episode_refs,
    store_manifest,
)

_TABLES = ("000010", "000250")
_SESSIONS = ("20250103", "20250106")
_IN_WINDOW_TIMES = ("090000", "090001", "091500", "092959", "093000")


def _make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        for table in _TABLES:
            conn.execute(
                f'CREATE TABLE "{table}" ('
                '"index" INTEGER, "현재가" REAL, "매수호가1" REAL, "매도호가1" REAL, "종목코드" TEXT)'
            )
            for session in _SESSIONS:
                times = ("085959", *_IN_WINDOW_TIMES, "093001")
                for i, hhmmss in enumerate(times):
                    conn.execute(
                        f'INSERT INTO "{table}" VALUES (?, ?, ?, ?, ?)',
                        (int(f"{session}{hhmmss}"), 100.0 + i, 99.0 + i, 101.0 + i, table),
                    )
        conn.execute('CREATE TABLE "ABC001" ("index" INTEGER)')
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "tick.db"
    _make_db(path)
    return path


def test_connect_readonly_blocks_writes(db_path):
    conn = connect_readonly(db_path)
    try:
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute('INSERT INTO "000010" VALUES (20250103090000, 1.0, 1.0, 1.0, \'000010\')')
    finally:
        conn.close()


def test_table_and_session_enumeration(db_path):
    assert list_stock_tables(db_path) == ["000010", "000250"]
    assert list_stock_tables(db_path, max_tables=1) == ["000010"]
    assert list_sessions(db_path, "000250") == ["20250103", "20250106"]
    assert list_sessions(db_path, "000250", max_sessions=1) == ["20250103"]


def test_load_episode_respects_time_window_and_max_rows(db_path):
    ref = EpisodeRef(table="000250", session="20250103")
    frame = load_episode(db_path, ref)
    assert len(frame) == len(_IN_WINDOW_TIMES)
    hhmmss = frame["index"].astype(str).str[8:14]
    assert (hhmmss >= "090000").all() and (hhmmss <= "093000").all()
    assert frame["index"].astype(str).str[:8].eq("20250103").all()

    capped = load_episode(db_path, ref, max_rows=3)
    assert len(capped) == 3
    pd.testing.assert_frame_equal(capped, frame.iloc[:3].reset_index(drop=True))


def test_cache_hit_survives_db_deletion(db_path, tmp_path):
    cache_dir = tmp_path / "episode_cache"
    ref = EpisodeRef(table="000250", session="20250106")
    first = load_episode(db_path, ref, cache_dir=cache_dir)
    assert list(cache_dir.glob("*.parquet"))

    db_path.rename(tmp_path / "gone.db")
    assert not db_path.exists()
    second = load_episode(db_path, ref, cache_dir=cache_dir)
    pd.testing.assert_frame_equal(first, second)

    # without a cache the missing DB raises
    with pytest.raises(FileNotFoundError):
        load_episode(db_path, ref)


def test_leading_zero_symbol_preserved_through_cache(db_path, tmp_path):
    cache_dir = tmp_path / "episode_cache"
    ref = EpisodeRef(table="000010", session="20250103")
    first = load_episode(db_path, ref, cache_dir=cache_dir)
    second = load_episode(db_path, ref, cache_dir=cache_dir)

    for frame in (first, second):
        assert frame["종목코드"].dtype == object
        assert frame["종목코드"].tolist() == ["000010"] * len(frame)
    pd.testing.assert_frame_equal(first, second)


def test_sample_episode_refs_deterministic_per_seed(db_path):
    refs_a = sample_episode_refs(db_path, n=3, seed=7)
    refs_b = sample_episode_refs(db_path, n=3, seed=7)
    assert refs_a == refs_b
    assert len(refs_a) == 3
    assert all(isinstance(ref, EpisodeRef) for ref in refs_a)
    assert len(set(refs_a)) == 3  # without replacement

    refs_c = sample_episode_refs(db_path, n=3, seed=8)
    assert refs_c != refs_a

    # n larger than candidate pool returns every candidate exactly once
    refs_all = sample_episode_refs(db_path, n=99, seed=7)
    assert len(refs_all) == len(_TABLES) * len(_SESSIONS)
    assert len(set(refs_all)) == len(refs_all)


def test_store_manifest_is_json_safe(db_path, tmp_path):
    refs = sample_episode_refs(db_path, n=4, seed=7)
    manifest = store_manifest(refs, db_path=db_path, cache_dir=tmp_path / "cache")
    assert manifest["read_only"] is True
    assert manifest["ref_count"] == 4
    assert manifest["tables"] == ["000010", "000250"]
    assert manifest["sessions"] == ["20250103", "20250106"]
    assert manifest["time_windows"] == ["090000-093000"]
    assert "research-only" in manifest["guardrail"]
    json.dumps(manifest, ensure_ascii=False)  # JSON-safe


def test_default_cache_dir_constant():
    assert DEFAULT_EPISODE_CACHE_DIR == Path(".omx") / "artifacts" / "factory_episode_cache"
    assert episode_store.DEFAULT_TIME_START == "090000"
    assert episode_store.DEFAULT_TIME_END == "093000"
