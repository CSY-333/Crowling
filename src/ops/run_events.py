import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..storage.db import Database

logger = logging.getLogger(__name__)


class RunEventLogger:
    """
    Thin wrapper for persisting structured operational events into the events table.
    """

    def __init__(self, db: Database, run_id: str):
        self.db = db
        self.run_id = run_id

    def log(self, event_type: str, summary: str, payload: Optional[Dict[str, Any]] = None) -> None:
        """
        Persist the event. Payload is JSON-encoded into the details column alongside the summary.
        """
        record = {"summary": summary}
        if payload:
            record["payload"] = payload

        details = json.dumps(record, ensure_ascii=False)
        timestamp = datetime.now(timezone.utc).isoformat()

        conn = None
        try:
            conn = self.db.get_connection()
            with conn:
                conn.execute(
                    "INSERT INTO events (run_id, timestamp, event_type, details) VALUES (?, ?, ?, ?)",
                    (self.run_id, timestamp, event_type, details),
                )
        except Exception as exc:
            logger.error("Failed to log event %s: %s", event_type, exc)
        finally:
            if conn is not None:
                conn.close()
