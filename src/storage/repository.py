import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from .db import Database

logger = logging.getLogger(__name__)

class CommentRepository:
    def __init__(self, db: Database, run_id: str):
        self.db = db
        self.run_id = run_id
        self.tz = ZoneInfo("Asia/Seoul")

    def is_article_completed(self, oid: str, aid: str) -> bool:
        conn = self.db.get_connection()
        try:
            row = conn.execute(
                "SELECT status_code FROM articles WHERE oid = ? AND aid = ? AND run_id = ?",
                (oid, aid, self.run_id),
            ).fetchone()
            return bool(row and row["status_code"] == "SUCCESS")
        finally:
            conn.close()

    def set_article_status(self, oid: str, aid: str, status: str, error_code: Optional[str] = None, error_message: Optional[str] = None) -> None:
        crawl_at = datetime.now(self.tz).isoformat()
        conn = self.db.get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO articles (oid, aid, run_id, status_code, error_code, error_message, crawl_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(oid, aid) DO UPDATE SET
                        run_id = excluded.run_id,
                        status_code = excluded.status_code,
                        error_code = excluded.error_code,
                        error_message = excluded.error_message,
                        crawl_at = excluded.crawl_at
                    ;
                    """,
                    (oid, aid, self.run_id, status, error_code, error_message, crawl_at),
                )
        finally:
            conn.close()

    def persist_comments(self, records: List[Dict[str, Any]], oid: str, aid: str) -> int:
        if not records:
            return 0
        
        written = 0
        with self.db.transaction() as conn:
            for r in records:
                conn.execute(
                    """
                    INSERT INTO comments (
                        comment_no, run_id, oid, aid, parent_comment_no, depth, contents,
                        author_hash, author_raw, reg_time, crawl_at, snapshot_at,
                        sympathy_count, antipathy_count, reply_count, is_deleted, is_blind
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(comment_no) DO UPDATE SET
                        contents = excluded.contents,
                        reply_count = excluded.reply_count,
                        sympathy_count = excluded.sympathy_count,
                        antipathy_count = excluded.antipathy_count,
                        is_deleted = excluded.is_deleted,
                        is_blind = excluded.is_blind
                    ;
                    """,
                    (
                        r['comment_no'], self.run_id, oid, aid, r['parent_comment_no'], r['depth'], r['contents'],
                        r['author_hash'], r['author_raw'], r['reg_time'], r['crawl_at'], r['snapshot_at'],
                        r['sympathy_count'], r['antipathy_count'], r['reply_count'], r['is_deleted'], r['is_blind']
                    )
                )
                written += 1
        return written