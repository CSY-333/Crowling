import json
import logging
from typing import Any, Dict, List, Optional, Set

from ..config import AppConfig
from .comment_fetcher import CommentFetcher
from .comment_parser import CommentParser, JSONPParseError, SchemaMismatchError
from .comment_stats import CommentStatsService
from ..storage.repository import CommentRepository
from ..common.errors import AppError, Severity, ErrorKind
from ..ops.structural import StructuralDetector, StructuralError, FailureKind
from ..ops.run_events import RunEventLogger

logger = logging.getLogger(__name__)

class CommentCollector:
    MAX_COMMENT_PAGES = 400
    MAX_REPLY_PAGES = 200

    def __init__(
        self,
        config: AppConfig,
        fetcher: CommentFetcher,
        parser: CommentParser,
        repository: CommentRepository,
        snapshot_at: str,
        structural_detector: Optional[StructuralDetector] = None,
        event_logger: Optional[RunEventLogger] = None,
        stats_service: Optional[CommentStatsService] = None,
    ):
        self.config = config
        self.fetcher = fetcher
        self.parser = parser
        self.repository = repository
        self.snapshot_at = snapshot_at
        self.structural_detector = structural_detector or StructuralDetector(threshold=10)
        self.stats_service = stats_service
        self.event_logger = event_logger

    # Public API -----------------------------------------------------------------
    def collect_article(
        self,
        oid: str,
        aid: str,
        endpoint_params: Dict[str, str],
        source_url: Optional[str] = None,
    ) -> int:
        """
        Collects comments + replies for an article and persists them to SQLite.
        Returns number of (top-level + reply) comments stored.
        """
        logger.info("Collecting comments for %s/%s", oid, aid)
        if self.repository.is_article_completed(oid, aid):
            logger.info("Article %s/%s already SUCCESS, skipping.", oid, aid)
            return 0

        self.structural_detector.record_success()
        total_written = 0
        max_reported_total = 0
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
                except JSONPParseError as err:
                    context = self._structural_context(
                        oid, aid, endpoint_params, source_url, "comment", page
                    )
                    self._record_monitor_failure(str(err), FailureKind.PARSE, context)
                    raise
                except SchemaMismatchError as err:
                    context = self._structural_context(
                        oid, aid, endpoint_params, source_url, "comment", page
                    )
                    self._record_monitor_failure(str(err), FailureKind.SCHEMA, context)
                    raise

                self.structural_detector.record_success()
                comments = self.parser.extract_comments(payload)
                self._validate_comment_payload(
                    comments,
                    payload,
                    oid,
                    aid,
                    endpoint_params,
                    source_url,
                    scope="comment",
                    page=page,
                )
                reported_total = self.parser.extract_total_count(payload)
                if reported_total:
                    max_reported_total = max(max_reported_total, reported_total)

                if not comments:
                    break

                records = [self.parser.to_record(c, 0, None, self.snapshot_at) for c in comments]
                written = self.repository.persist_comments(records, oid, aid)
                total_written += written

                for comment in comments:
                    reply_total = comment.get("replyCount", comment.get("childCount", 0))
                    if reply_total and int(reply_total) > 0:
                        total_written += self._collect_replies(
                            oid, aid, comment, endpoint_params, source_url
                        )

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
            total_comments = max(total_written, max_reported_total)
            self._maybe_collect_stats(oid, aid, endpoint_params, total_comments)
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
        source_url: Optional[str],
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
            except JSONPParseError as err:
                context = self._structural_context(
                    oid, aid, endpoint_params, source_url, "reply", page, parent_no
                )
                self._record_monitor_failure(str(err), FailureKind.PARSE, context)
                raise
            except SchemaMismatchError as err:
                context = self._structural_context(
                    oid, aid, endpoint_params, source_url, "reply", page, parent_no
                )
                self._record_monitor_failure(str(err), FailureKind.SCHEMA, context)
                raise

            self.structural_detector.record_success()
            comments = self.parser.extract_comments(payload)
            self._validate_comment_payload(
                comments,
                payload,
                oid,
                aid,
                endpoint_params,
                source_url,
                scope="reply",
                page=page,
                parent_no=parent_no,
            )
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

    def _maybe_collect_stats(
        self,
        oid: str,
        aid: str,
        endpoint_params: Dict[str, str],
        total_comments: int,
    ) -> None:
        stats_cfg = getattr(self.config.collection, "comment_stats", None)
        if not stats_cfg or not stats_cfg.enabled:
            return
        if not self.stats_service:
            return
        if total_comments < stats_cfg.min_comments:
            return

        try:
            stats = self.stats_service.fetch_stats(oid, aid, endpoint_params)
        except AppError as err:
            logger.warning("Failed to fetch stats for %s/%s: %s", oid, aid, err)
            return

        if stats:
            self.repository.persist_comment_stats(oid, aid, stats, snapshot_at=self.snapshot_at)

    # Monitoring helpers ---------------------------------------------------------
    def _record_monitor_failure(
        self,
        reason: str,
        kind: FailureKind,
        context: Dict[str, str],
    ) -> None:
        self.structural_detector.record_failure(reason, kind=kind, context=context)
        if self.event_logger:
            payload = dict(context)
            payload["failure_kind"] = kind.value
            self.event_logger.log("STRUCTURE_MONITOR", reason, payload)

    def _structural_context(
        self,
        oid: str,
        aid: str,
        params: Dict[str, str],
        source_url: Optional[str],
        scope: str,
        page: int,
        parent_no: Optional[str] = None,
    ) -> Dict[str, str]:
        context: Dict[str, str] = {
            "oid": oid,
            "aid": aid,
            "scope": scope,
            "page": str(page),
        }
        if source_url:
            context["url"] = source_url
        if parent_no:
            context["parent_comment_no"] = parent_no
        if params:
            context["params"] = json.dumps(params, ensure_ascii=False)
        return context

    def _validate_comment_payload(
        self,
        comments: List[Dict[str, Any]],
        payload: Dict[str, Any],
        oid: str,
        aid: str,
        params: Dict[str, str],
        source_url: Optional[str],
        scope: str,
        page: int,
        parent_no: Optional[str] = None,
    ) -> None:
        result_block = payload.get("result")
        if not isinstance(result_block, dict):
            context = self._structural_context(oid, aid, params, source_url, scope, page, parent_no)
            reason = "Result block missing in comment payload"
            self._raise_structural(reason, context)

        for idx, comment in enumerate(comments):
            required = ["commentNo", "contents", "regTime"]
            missing = [field for field in required if not comment.get(field)]
            if missing:
                context = self._structural_context(oid, aid, params, source_url, scope, page, parent_no)
                context["comment_index"] = str(idx)
                reason = f"Missing fields on comment: {','.join(missing)}"
                self._raise_structural(reason, context)

    def _raise_structural(self, reason: str, context: Dict[str, str]) -> None:
        try:
            self.structural_detector.record_failure(reason, kind=FailureKind.STRUCTURAL, context=context)
        finally:
            if self.event_logger:
                self.event_logger.log("STRUCTURAL_HEURISTIC", reason, context)
        raise StructuralError(reason)
