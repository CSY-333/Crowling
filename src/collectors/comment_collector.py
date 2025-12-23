import logging
from typing import Any, Dict, List, Optional, Set

from ..config import AppConfig
from .comment_fetcher import CommentFetcher
from .comment_parser import CommentParser, JSONPParseError, SchemaMismatchError
from ..storage.repository import CommentRepository
from ..common.errors import AppError, Severity, ErrorKind

logger = logging.getLogger(__name__)

class StructuralStop(AppError):
    def __init__(self, message: str):
        super().__init__(message, Severity.ABORT, ErrorKind.STRUCTURAL)


class CommentCollector:
    MAX_COMMENT_PAGES = 400
    MAX_REPLY_PAGES = 200
    STRUCTURAL_THRESHOLD = 10

    def __init__(
        self,
        config: AppConfig,
        fetcher: CommentFetcher,
        parser: CommentParser,
        repository: CommentRepository,
        snapshot_at: str,
    ):
        self.config = config
        self.fetcher = fetcher
        self.parser = parser
        self.repository = repository
        self.snapshot_at = snapshot_at
        self._structural_failures = 0

    # Public API -----------------------------------------------------------------
    def collect_article(self, oid: str, aid: str, endpoint_params: Dict[str, str]) -> int:
        """
        Collects comments + replies for an article and persists them to SQLite.
        Returns number of (top-level + reply) comments stored.
        """
        logger.info("Collecting comments for %s/%s", oid, aid)
        if self.repository.is_article_completed(oid, aid):
            logger.info("Article %s/%s already SUCCESS, skipping.", oid, aid)
            return 0

        self._reset_structural_failure()
        total_written = 0
        try:
            page = 1
            seen_cursors: Set[str] = set()
            while page <= self.MAX_COMMENT_PAGES:
                try:
                    raw_body = self.fetcher.fetch(
                        oid=oid,
                        aid=aid,
                        page=page,
                        params=endpoint_params,
                        scope="comment",
                        parent_comment_no=None,
                    )
                    payload = self.parser.parse_jsonp(raw_body)
                    self.parser.validate_schema(payload)
                except (JSONPParseError, SchemaMismatchError) as err:
                    self._record_structural_failure(str(err))
                    raise

                self._reset_structural_failure()
                comments = self.parser.extract_comments(payload)

                if not comments:
                    break

                records = [self.parser.to_record(c, 0, None, self.snapshot_at) for c in comments]
                written = self.repository.persist_comments(records, oid, aid)
                total_written += written

                for comment in comments:
                    reply_total = comment.get("replyCount", comment.get("childCount", 0))
                    if reply_total and int(reply_total) > 0:
                        total_written += self._collect_replies(oid, aid, comment, endpoint_params)

                cursor = self.parser.extract_cursor(payload)
                if cursor:
                    if cursor in seen_cursors:
                        logger.warning("Cursor repeat detected for %s/%s. Stopping pagination.", oid, aid)
                        break
                    seen_cursors.add(cursor)

                if not cursor:
                    break
                page += 1

            self.repository.set_article_status(oid, aid, status="SUCCESS")
            return total_written

        except AppError as err:
            # Map AppError to DB status
            status = "FAIL-UNKNOWN"
            if err.kind.name == "HTTP":
                status = "FAIL-HTTP"
            elif err.kind.name in ("PARSE", "SCHEMA", "STRUCTURAL"):
                status = "FAIL-PROBE"
            
            self.repository.set_article_status(oid, aid, status=status, error_message=str(err))
            raise
        except Exception as err:
            # Catch-all for unexpected errors
            self.repository.set_article_status(oid, aid, status="FAIL-HTTP", error_message=f"Unexpected: {err}")
            raise

    # Internal helpers -----------------------------------------------------------
    def _collect_replies(
        self,
        oid: str,
        aid: str,
        parent_comment: Dict[str, Any],
        endpoint_params: Dict[str, str],
    ) -> int:
        parent_no = str(parent_comment.get("commentNo"))
        if not parent_no:
            return 0

        total_written = 0
        page = 1
        seen_cursors: Set[str] = set()

        while page <= self.MAX_REPLY_PAGES:
            try:
                raw_body = self.fetcher.fetch(
                    oid=oid,
                    aid=aid,
                    page=page,
                    params=endpoint_params,
                    scope="reply",
                    parent_comment_no=parent_no,
                )
                payload = self.parser.parse_jsonp(raw_body)
                self.parser.validate_schema(payload)
            except (JSONPParseError, SchemaMismatchError) as err:
                self._record_structural_failure(str(err))
                raise

            self._reset_structural_failure()
            comments = self.parser.extract_comments(payload)
            if not comments:
                break

            records = [self.parser.to_record(c, 1, parent_no, self.snapshot_at) for c in comments]
            total_written += self.repository.persist_comments(records, oid, aid)

            cursor = self.parser.extract_cursor(payload)
            if cursor:
                if cursor in seen_cursors:
                    logger.warning("Reply cursor repeat for parent %s. Stopping reply pagination.", parent_no)
                    break
                seen_cursors.add(cursor)

            if not cursor:
                break
            page += 1

        return total_written

    def _record_structural_failure(self, reason: str) -> None:
        self._structural_failures += 1
        logger.warning(
            "Structural failure #%s detected (threshold %s): %s",
            self._structural_failures,
            self.STRUCTURAL_THRESHOLD,
            reason,
        )
        if self._structural_failures >= self.STRUCTURAL_THRESHOLD:
            raise StructuralStop(f"Structural failure threshold exceeded: {reason}")

    def _reset_structural_failure(self) -> None:
        self._structural_failures = 0
