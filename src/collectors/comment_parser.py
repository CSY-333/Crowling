import json
import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ValidationError
from ..config import AppConfig
from ..common.errors import AppError, Severity, ErrorKind
from ..privacy.hashing import PrivacyHasher

logger = logging.getLogger(__name__)

# --- Pydantic Models for Design by Contract ---
class NaverComment(BaseModel):
    commentNo: str
    contents: str
    regTime: str
    # Allow other fields to pass through without validation overhead
    class Config:
        extra = "ignore"

class NaverCommentListResult(BaseModel):
    commentList: List[NaverComment]

class NaverCommentResponse(BaseModel):
    result: NaverCommentListResult
# ----------------------------------------------

class JSONPParseError(AppError):
    def __init__(self, message: str):
        super().__init__(message, Severity.WARN, ErrorKind.PARSE)

class SchemaMismatchError(AppError):
    def __init__(self, message: str, original_exception: Exception = None):
        super().__init__(message, Severity.WARN, ErrorKind.SCHEMA, original_exception)

class CommentParser:
    def __init__(self, config: AppConfig, hasher: PrivacyHasher):
        self.config = config
        self.hasher = hasher
        self.tz = ZoneInfo("Asia/Seoul")

    def parse_jsonp(self, body: str) -> Dict[str, Any]:
        text = body.strip()
        if not text:
            raise JSONPParseError("Empty response body")
        if text.startswith("<"):
            raise JSONPParseError("HTML response detected")

        if text.startswith("{"):
            return json.loads(text)

        match = re.match(r"^[^(]*\((.*)\)\s*;?\s*$", text, re.DOTALL)
        if not match:
            raise JSONPParseError("Unable to strip callback wrapper")

        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise JSONPParseError(f"JSON decode failed: {exc}")

    def validate_schema(self, payload: Dict[str, Any]) -> None:
        """
        Enforce contract using Pydantic.
        """
        try:
            NaverCommentResponse(**payload)
        except ValidationError as exc:
            raise SchemaMismatchError(f"Schema validation failed: {exc}", original_exception=exc)

    def extract_comments(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        return payload.get("result", {}).get("commentList", []) or []

    def extract_cursor(self, payload: Dict[str, Any]) -> Optional[str]:
        page_model = payload.get("result", {}).get("pageModel", {})
        return page_model.get("next")

    def extract_total_count(self, payload: Dict[str, Any]) -> int:
        result = payload.get("result", {}) or {}
        count_block = result.get("count") or {}
        candidates = [
            result.get("commentCount"),
            result.get("realCommentCount"),
            count_block.get("comment"),
            count_block.get("total"),
        ]
        for value in candidates:
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        return 0

    def to_record(self, comment: Dict[str, Any], depth: int, parent: Optional[str], snapshot_at: str) -> Dict[str, Any]:
        # Returns a dict suitable for DB insertion (CommentRecord equivalent)
        comment_no = str(comment.get("commentNo"))
        contents = comment.get("contents")
        
        raw_id = comment.get("userId") or comment.get("profileUserId")
        author_hash = self.hasher.hash_identifier(raw_id)
        author_raw = comment.get("userName") if self.config.privacy.allow_pii else None
        
        reg_time = self._normalize_time(comment.get("regTime"))
        crawl_at = datetime.now(self.tz).isoformat()

        return {
            "comment_no": comment_no,
            "parent_comment_no": parent,
            "depth": depth,
            "contents": contents,
            "author_hash": author_hash,
            "author_raw": author_raw,
            "reg_time": reg_time,
            "crawl_at": crawl_at,
            "snapshot_at": snapshot_at,
            "sympathy_count": int(comment.get("sympathyCount", 0) or 0),
            "antipathy_count": int(comment.get("antipathyCount", 0) or 0),
            "reply_count": int(comment.get("replyCount", comment.get("childCount", 0)) or 0),
            "is_deleted": 1 if comment.get("isDeleted") else 0,
            "is_blind": 1 if comment.get("isBlind") else 0,
        }

    def _normalize_time(self, value: Optional[str]) -> Optional[str]:
        if not value: return None
        try:
            if value.isdigit():
                timestamp = int(value)
                if len(value) > 10: timestamp = timestamp / 1000
                dt = datetime.fromtimestamp(timestamp, tz=self.tz)
                return dt.isoformat()
        except Exception:
            pass
        # Simplified for brevity, assume ISO or similar if not epoch
        return value
