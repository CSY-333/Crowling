import csv

from src.storage.db import Database
from src.storage.exporters import DataExporter


def test_data_exporter_writes_csv(tmp_path):
    db_path = tmp_path / "test.db"
    database = Database(str(db_path), wal_mode=False)
    database.init_schema()

    conn = database.get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO runs (run_id, snapshot_at, start_at, timezone) VALUES (?, ?, ?, ?)",
                ("run-1", "2023-01-01T00:00:00", "2023-01-01T00:00:00", "UTC"),
            )
            conn.execute(
                "INSERT INTO articles (oid, aid, run_id, status_code) VALUES (?, ?, ?, ?)",
                ("001", "0001", "run-1", "SUCCESS"),
            )
            conn.execute(
                "INSERT INTO comments (comment_no, run_id, oid, aid, contents) VALUES (?, ?, ?, ?, ?)",
                ("c1", "run-1", "001", "0001", "hello"),
            )
    finally:
        conn.close()

    exporter = DataExporter(database, export_dir=str(tmp_path / "exports"))
    exporter.export_run("run-1")

    articles_csv = tmp_path / "exports" / "articles.csv"
    comments_csv = tmp_path / "exports" / "comments.csv"
    runs_csv = tmp_path / "exports" / "run_log.csv"

    for csv_path in (articles_csv, comments_csv):
        assert csv_path.exists()
        with csv_path.open("r", encoding="utf-8-sig") as handle:
            rows = list(csv.reader(handle))
            assert rows[1][0] in {"001", "c1"}

    # run_log should include all runs (no filtering)
    with runs_csv.open("r", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
        assert len(rows) == 2
        assert rows[1][0] == "run-1"
