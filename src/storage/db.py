import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Generator

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str, wal_mode: bool = True):
        self.db_path = Path(db_path)
        self.wal_mode = wal_mode
        self._ensure_db_dir()

    def _ensure_db_dir(self):
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        
        # Enforce foreign keys
        conn.execute("PRAGMA foreign_keys = ON;")
        
        if self.wal_mode:
            conn.execute("PRAGMA journal_mode = WAL;")
            
        return conn

    def init_schema(self):
        """Creates the necessary tables if they don't exist."""
        conn = self.get_connection()
        try:
            with conn:
                # 1. Runs Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS runs (
                        run_id TEXT PRIMARY KEY,
                        snapshot_at TEXT NOT NULL,
                        start_at TEXT NOT NULL,
                        end_at TEXT,
                        timezone TEXT NOT NULL,
                        config_json TEXT,
                        status TEXT CHECK(status IN ('SUCCESS', 'PARTIAL', 'STOPPED', 'FAILED')),
                        notes TEXT,
                        total_articles INTEGER DEFAULT 0,
                        total_comments INTEGER DEFAULT 0,
                        health_score INTEGER,
                        health_flags TEXT
                    );
                """)

                # 2. Articles Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS articles (
                        run_id TEXT NOT NULL,
                        oid TEXT NOT NULL,
                        aid TEXT NOT NULL,
                        url TEXT,
                        title TEXT,
                        press TEXT,
                        published_at TEXT,
                        updated_at TEXT,
                        crawl_at TEXT,
                        status TEXT NOT NULL DEFAULT 'PENDING',
                        status_code INTEGER,
                        error_code TEXT,
                        error_message TEXT,
                        PRIMARY KEY (run_id, oid, aid),
                        FOREIGN KEY (run_id) REFERENCES runs(run_id)
                    );
                """)

                # 3. Comments Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS comments (
                        run_id TEXT NOT NULL,
                        comment_no TEXT NOT NULL,
                        oid TEXT NOT NULL,
                        aid TEXT NOT NULL,
                        parent_comment_no TEXT,
                        depth INTEGER NOT NULL DEFAULT 0,
                        contents TEXT,
                        author_hash TEXT,
                        author_raw TEXT,
                        reg_time TEXT,
                        crawl_at TEXT,
                        snapshot_at TEXT,
                        sympathy_count INTEGER,
                        antipathy_count INTEGER,
                        reply_count INTEGER,
                        is_deleted BOOLEAN,
                        is_blind BOOLEAN,
                        status_code INTEGER,
                        error_code TEXT,
                        error_message TEXT,
                        PRIMARY KEY (run_id, comment_no),
                        FOREIGN KEY (run_id, oid, aid) REFERENCES articles(run_id, oid, aid)
                    );
                """)

                # 4. Events Table (Optional but recommended for throttling logs)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        event_type TEXT,
                        details TEXT,
                        FOREIGN KEY (run_id) REFERENCES runs(run_id)
                    );
                """)

                # 5. Comment Stats Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS comment_stats (
                        run_id TEXT NOT NULL,
                        oid TEXT NOT NULL,
                        aid TEXT NOT NULL,
                        total_comments INTEGER,
                        male_ratio REAL,
                        female_ratio REAL,
                        age_10s REAL,
                        age_20s REAL,
                        age_30s REAL,
                        age_40s REAL,
                        age_50s REAL,
                        age_60s REAL,
                        age_70s REAL,
                        snapshot_at TEXT,
                        collected_at TEXT,
                        PRIMARY KEY (run_id, oid, aid),
                        FOREIGN KEY (run_id, oid, aid) REFERENCES articles(run_id, oid, aid)
                    );
                """)
                
            logger.info(f"Database schema initialized at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize schema: {e}")
            raise
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for atomic transactions.
        Commits on success, rolls back on exception.
        """
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_completed_article_keys(self, run_id: Optional[str] = None):
        """
        Returns a set of (oid, aid) tuples for successfully collected articles.
        Used for resume logic.
        """
        conn = self.get_connection()
        try:
            query = "SELECT oid, aid FROM articles WHERE status = 'SUCCESS'"
            params = []
            if run_id:
                query += " AND run_id = ?"
                params.append(run_id)
            cursor = conn.execute(query, params)
            return {(row['oid'], row['aid']) for row in cursor.fetchall()}
        finally:
            conn.close()
