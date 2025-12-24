from datetime import datetime

from src.storage.db import Database
from src.storage.run_repository import RunRepository


def test_run_repository_start_and_finalize(tmp_path):
    db_path = tmp_path / "runs.db"
    database = Database(str(db_path), wal_mode=False)
    database.init_schema()

    repo = RunRepository(database)

    config_payload = {"search": {"keywords": ["foo"]}}
    repo.start_run(
        run_id="run-1",
        snapshot_at="2025-01-01T00:00:00",
        tz_name="UTC",
        config_payload=config_payload,
    )

    conn = database.get_connection()
    try:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", ("run-1",)).fetchone()
        assert row["config_json"].startswith("{")
        assert row["status"] is None
    finally:
        conn.close()

    repo.finalize_run(
        run_id="run-1",
        status="A",
        notes="target met",
        total_articles=30,
        total_comments=5000,
        health_score=95,
        health_flags="",
    )

    conn = database.get_connection()
    try:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", ("run-1",)).fetchone()
        assert row["status"] == "A"
        assert row["notes"] == "target met"
        assert row["total_articles"] == 30
        assert row["total_comments"] == 5000
        assert row["health_score"] == 95
    finally:
        conn.close()
