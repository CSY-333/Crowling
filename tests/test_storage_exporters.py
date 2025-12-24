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
                "INSERT INTO articles (run_id, oid, aid, status) VALUES (?, ?, ?, ?)",
                ("run-1", "001", "0001", "SUCCESS"),
            )
            conn.execute(
                "INSERT INTO comments (run_id, comment_no, oid, aid, contents) VALUES (?, ?, ?, ?, ?)",
                ("run-1", "c1", "001", "0001", "hello"),
            )
            conn.execute(
                """
                INSERT INTO comment_stats (
                    run_id, oid, aid, total_comments, male_ratio, female_ratio,
                    age_10s, age_20s, age_30s, age_40s, age_50s, age_60s, age_70s
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("run-1", "001", "0001", 240, 82.0, 18.0, 0.0, 2.0, 19.0, 44.0, 29.0, 6.0, 0.0),
            )
    finally:
        conn.close()

    exporter = DataExporter(database, export_dir=str(tmp_path / "exports"))
    exporter.export_run("run-1")

    articles_csv = tmp_path / "exports" / "articles.csv"
    comments_csv = tmp_path / "exports" / "comments.csv"
    runs_csv = tmp_path / "exports" / "run_log.csv"
    stats_csv = tmp_path / "exports" / "comment_stats.csv"

    for csv_path in (articles_csv, comments_csv, stats_csv):
        assert csv_path.exists()
        with csv_path.open("r", encoding="utf-8-sig") as handle:
            rows = list(csv.reader(handle))
            assert rows[1][0] == "run-1"

    # run_log should include all runs (no filtering)
    with runs_csv.open("r", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
        assert len(rows) == 2
        assert rows[1][0] == "run-1"
