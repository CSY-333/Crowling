import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .db import Database


class RunRepository:
    def __init__(self, db: Database):
        self.db = db

    def start_run(
        self,
        run_id: str,
        snapshot_at: str,
        tz_name: str,
        config_payload: Dict[str, Any],
    ) -> None:
        payload = json.dumps(config_payload, ensure_ascii=False)
        conn = self.db.get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO runs (
                        run_id, snapshot_at, start_at, timezone, config_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_id, snapshot_at, datetime.now(timezone.utc).isoformat(), tz_name, payload),
                )
        finally:
            conn.close()

    def finalize_run(
        self,
        run_id: str,
        status: str,
        notes: str,
        total_articles: int,
        total_comments: int,
        health_score: int,
        health_flags: str,
    ) -> None:
        conn = self.db.get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE runs
                    SET
                        end_at = ?,
                        status = ?,
                        notes = ?,
                        total_articles = ?,
                        total_comments = ?,
                        health_score = ?,
                        health_flags = ?
                    WHERE run_id = ?
                    """,
                    (
                        datetime.now(timezone.utc).isoformat(),
                        status,
                        notes,
                        total_articles,
                        total_comments,
                        health_score,
                        health_flags,
                        run_id,
                    ),
                )
        finally:
            conn.close()
