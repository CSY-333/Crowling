import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from .db import Database

logger = logging.getLogger(__name__)

class CommentRepository:
    def __init__(self, db: Database, run_id: str, store_author_raw: bool = False):
        self.db = db
        self.run_id = run_id
        self.tz = ZoneInfo("Asia/Seoul")
        self.store_author_raw = store_author_raw

    def is_article_completed(self, oid: str, aid: str) -> bool:
        conn = self.db.get_connection()
        try:
            row = conn.execute(
                "SELECT status FROM articles WHERE run_id = ? AND oid = ? AND aid = ?",
                (self.run_id, oid, aid),
            ).fetchone()
            return bool(row and row["status"] == "SUCCESS")
        finally:
            conn.close()

    def set_article_status(
        self,
        oid: str,
        aid: str,
        status: str,
        http_status: Optional[int] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        crawl_at = datetime.now(self.tz).isoformat()
        conn = self.db.get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO articles (run_id, oid, aid, status, status_code, error_code, error_message, crawl_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id, oid, aid) DO UPDATE SET
                        status = excluded.status,
                        status_code = excluded.status_code,
                        error_code = excluded.error_code,
                        error_message = excluded.error_message,
                        crawl_at = excluded.crawl_at
                    ;
                    """,
                    (self.run_id, oid, aid, status, http_status, error_code, error_message, crawl_at),
                )
        finally:
            conn.close()

    def persist_comments(self, records: List[Dict[str, Any]], oid: str, aid: str) -> int:
        if not records:
            return 0
        
        written = 0
        with self.db.transaction() as conn:
            for r in records:
                author_raw_value = r["author_raw"] if self.store_author_raw else None
                conn.execute(
                    """
                    INSERT INTO comments (
                        run_id, comment_no, oid, aid, parent_comment_no, depth, contents,
                        author_hash, author_raw, reg_time, crawl_at, snapshot_at,
                        sympathy_count, antipathy_count, reply_count, is_deleted, is_blind
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id, comment_no) DO UPDATE SET
                        contents = excluded.contents,
                        reply_count = excluded.reply_count,
                        sympathy_count = excluded.sympathy_count,
                        antipathy_count = excluded.antipathy_count,
                        is_deleted = excluded.is_deleted,
                        is_blind = excluded.is_blind
                    ;
                    """,
                    (
                        self.run_id,
                        r["comment_no"],
                        oid,
                        aid,
                        r["parent_comment_no"],
                        r["depth"],
                        r["contents"],
                        r["author_hash"],
                        author_raw_value,
                        r["reg_time"],
                        r["crawl_at"],
                        r["snapshot_at"],
                        r["sympathy_count"],
                        r["antipathy_count"],
                        r["reply_count"],
                        r["is_deleted"],
                        r["is_blind"],
                    ),
                )
                written += 1
        return written

    def persist_comment_stats(
        self,
        oid: str,
        aid: str,
        stats: Dict[str, Any],
        snapshot_at: Optional[str] = None,
    ) -> None:
        gender = stats.get("gender", {}) if stats else {}
        age = stats.get("age", {}) if stats else {}
        collected_at = datetime.now(self.tz).isoformat()
        conn = self.db.get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO comment_stats (
                        run_id, oid, aid, total_comments,
                        male_ratio, female_ratio,
                        age_10s, age_20s, age_30s, age_40s, age_50s, age_60s, age_70s,
                        snapshot_at, collected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id, oid, aid) DO UPDATE SET
                        total_comments = excluded.total_comments,
                        male_ratio = excluded.male_ratio,
                        female_ratio = excluded.female_ratio,
                        age_10s = excluded.age_10s,
                        age_20s = excluded.age_20s,
                        age_30s = excluded.age_30s,
                        age_40s = excluded.age_40s,
                        age_50s = excluded.age_50s,
                        age_60s = excluded.age_60s,
                        age_70s = excluded.age_70s,
                        snapshot_at = excluded.snapshot_at,
                        collected_at = excluded.collected_at
                    ;
                    """,
                    (
                        self.run_id,
                        oid,
                        aid,
                        stats.get("total_comments", 0) if stats else 0,
                        gender.get("male"),
                        gender.get("female"),
                        age.get("10"),
                        age.get("20"),
                        age.get("30"),
                        age.get("40"),
                        age.get("50"),
                        age.get("60"),
                        age.get("70"),
                        snapshot_at,
                        collected_at,
                    ),
                )
        finally:
            conn.close()
