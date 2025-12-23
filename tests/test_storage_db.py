import sqlite3
from datetime import datetime

import pytest

from src.storage.db import Database


def _init_db(tmp_path) -> Database:
    db_path = tmp_path / "test.db"
    database = Database(str(db_path), wal_mode=True)
    database.init_schema()
    return database


def test_database_enables_wal_mode(tmp_path):
    db = _init_db(tmp_path)
    conn = db.get_connection()
    try:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    finally:
        conn.close()
    assert mode.lower() == "wal"


def test_transaction_context_rolls_back_on_error(tmp_path):
    db = _init_db(tmp_path)
    with pytest.raises(RuntimeError):
        with db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, snapshot_at, start_at, timezone)
                VALUES (?, ?, ?, ?)
                """,
                ("run-test", datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), "UTC"),
            )
            raise RuntimeError("force rollback")

    conn = db.get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM runs WHERE run_id = ?", ("run-test",)).fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_get_completed_article_keys_filters_by_run(tmp_path):
    db = _init_db(tmp_path)
    conn = db.get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, snapshot_at, start_at, timezone)
                VALUES (?, ?, ?, ?)
                """,
                ("run-1", datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), "UTC"),
            )
            conn.execute(
                """
                INSERT INTO articles (oid, aid, run_id, status_code, crawl_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("001", "0001", "run-1", "SUCCESS", datetime.utcnow().isoformat()),
            )
    finally:
        conn.close()

    assert db.get_completed_article_keys("run-1") == {("001", "0001")}
    assert db.get_completed_article_keys("run-2") == set()
