from src.storage.db import Database
from src.storage.repository import CommentRepository


def test_persist_comment_stats(tmp_path):
    db_path = tmp_path / "stats.db"
    database = Database(str(db_path), wal_mode=False)
    database.init_schema()

    conn = database.get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO runs (run_id, snapshot_at, start_at, timezone) VALUES (?, ?, ?, ?)",
                ("run-1", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "UTC"),
            )
    finally:
        conn.close()

    repo = CommentRepository(database, run_id="run-1")
    repo.set_article_status("001", "0001", status="SUCCESS")

    stats = {
        "total_comments": 240,
        "gender": {"male": 82.0, "female": 18.0},
        "age": {"10": 0.0, "20": 2.0, "30": 19.0, "40": 44.0, "50": 29.0, "60": 6.0, "70": 0.0},
    }

    repo.persist_comment_stats("001", "0001", stats, snapshot_at="2023-01-01T00:00:00Z")

    conn = database.get_connection()
    try:
        row = conn.execute(
            "SELECT total_comments, male_ratio, age_40s FROM comment_stats WHERE oid = '001' AND aid = '0001'"
        ).fetchone()
        assert row["total_comments"] == 240
        assert row["male_ratio"] == 82.0
        assert row["age_40s"] == 44.0
    finally:
        conn.close()


def test_set_article_status_is_scoped_by_run(tmp_path):
    db_path = tmp_path / "status.db"
    database = Database(str(db_path), wal_mode=False)
    database.init_schema()

    conn = database.get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO runs (run_id, snapshot_at, start_at, timezone) VALUES (?, ?, ?, ?)",
                ("run-1", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "UTC"),
            )
            conn.execute(
                "INSERT INTO runs (run_id, snapshot_at, start_at, timezone) VALUES (?, ?, ?, ?)",
                ("run-2", "2024-01-02T00:00:00Z", "2024-01-02T00:00:00Z", "UTC"),
            )
    finally:
        conn.close()

    repo1 = CommentRepository(database, run_id="run-1")
    repo2 = CommentRepository(database, run_id="run-2")

    repo1.set_article_status("001", "0001", status="SUCCESS")
    repo2.set_article_status("001", "0001", status="FAIL-HTTP", http_status=500)

    conn = database.get_connection()
    try:
        rows = conn.execute(
            "SELECT run_id, status, status_code FROM articles WHERE oid = ? AND aid = ? ORDER BY run_id",
            ("001", "0001"),
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["run_id"] == "run-1" and rows[0]["status"] == "SUCCESS"
        assert rows[1]["run_id"] == "run-2" and rows[1]["status_code"] == 500
    finally:
        conn.close()


def test_persist_comments_respects_privacy_flag(tmp_path):
    db_path = tmp_path / "comments.db"
    database = Database(str(db_path), wal_mode=False)
    database.init_schema()

    conn = database.get_connection()
    try:
        with conn:
            for run in ("run-1", "run-2"):
                conn.execute(
                    "INSERT INTO runs (run_id, snapshot_at, start_at, timezone) VALUES (?, ?, ?, ?)",
                    (run, "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "UTC"),
                )
    finally:
        conn.close()

    repo_no_pii = CommentRepository(database, run_id="run-1", store_author_raw=False)
    repo_with_pii = CommentRepository(database, run_id="run-2", store_author_raw=True)

    base_record = {
        "comment_no": "c1",
        "parent_comment_no": None,
        "depth": 0,
        "contents": "hello",
        "author_hash": "hash1",
        "author_raw": "raw-name",
        "reg_time": "2024-01-01T00:00:00Z",
        "crawl_at": "2024-01-01T00:00:00Z",
        "snapshot_at": "2024-01-01T00:00:00Z",
        "sympathy_count": 1,
        "antipathy_count": 0,
        "reply_count": 0,
        "is_deleted": 0,
        "is_blind": 0,
    }

    repo_no_pii.set_article_status("001", "0001", status="SUCCESS")
    repo_with_pii.set_article_status("001", "0001", status="SUCCESS")

    repo_no_pii.persist_comments([base_record], oid="001", aid="0001")
    repo_with_pii.persist_comments([base_record], oid="001", aid="0001")

    conn = database.get_connection()
    try:
        rows = conn.execute(
            "SELECT run_id, author_raw FROM comments WHERE comment_no = ? ORDER BY run_id",
            ("c1",),
        ).fetchall()
        assert rows[0]["run_id"] == "run-1" and rows[0]["author_raw"] is None
        assert rows[1]["run_id"] == "run-2" and rows[1]["author_raw"] == "raw-name"
    finally:
        conn.close()
