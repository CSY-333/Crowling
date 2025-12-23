import json
import logging
import time
from typing import Any, Dict, Optional

from ..collectors.search_collector import SearchCollector
from ..collectors.article_parser import ArticleParser
from ..collectors.comment_parser import CommentParser, JSONPParseError, SchemaMismatchError
from ..ops.probe import EndpointProbe
from ..ops.evidence import EvidenceCollector
from ..common.errors import AppError, ErrorKind, Severity

logger = logging.getLogger(__name__)


class HealthCheck:
    def __init__(
        self,
        config,
        searcher: Optional[SearchCollector] = None,
        parser: Optional[ArticleParser] = None,
        probe: Optional[EndpointProbe] = None,
        comment_fetcher=None,
        comment_parser: Optional[CommentParser] = None,
        evidence: Optional[EvidenceCollector] = None,
    ):
        self.config = config
        self.searcher = searcher or SearchCollector(config.search)
        self.parser = parser or ArticleParser()
        self.probe = probe or EndpointProbe()
        self.comment_fetcher = comment_fetcher
        self.comment_parser = comment_parser
        self.evidence = evidence or EvidenceCollector(run_id="health_check")

    def run_preflight_check(self, run_id: str = "preflight") -> bool:
        """
        Execute 3-sample article check from first keyword.
        Must succeed in at least 2/3 cases.
        """
        if not self.comment_fetcher:
            raise RuntimeError("HealthCheck requires a comment_fetcher dependency.")

        logger.info("Executing Pre-flight Health Check...")

        if not self.config.search.keywords:
            logger.error("Health Check: No keywords configured.")
            return False

        self.evidence.run_id = run_id
        keyword = self.config.search.keywords[0]
        samples = []

        for item in self.searcher.search_keyword(keyword):
            url = item.get("url")
            oid = item.get("oid")
            aid = item.get("aid")
            if oid and aid:
                samples.append((oid, aid, url))
            if len(samples) >= 3:
                break

        if len(samples) < 3:
            logger.warning("Health Check: Only %s sample(s) available.", len(samples))

        success_count = 0
        tried = 0

        for oid, aid, url in samples:
            tried += 1
            logger.info("Health Check Sample %s: %s/%s", tried, oid, aid)

            metadata = self.parser.fetch_and_parse(url)
            if metadata.get("status_code") != "CRAWL-OK":
                logger.error("Sample %s Failed: Metadata parse error", tried)
                continue

            raw_html = metadata.get("_raw_html", "")
            candidate_params = self.probe.get_candidate_configs(url, raw_html)
            sample_success = False

            for attempt, params in enumerate(candidate_params, start=1):
                logger.info("Sample %s Attempt %s using params %s", tried, attempt, params)

                try:
                    raw_payload = self._fetch_comment_payload(oid, aid, params)
                except AppError as exc:
                    self._log_evidence(
                        error_type=f"FETCH_{exc.kind.name}",
                        oid=oid,
                        aid=aid,
                        attempt=attempt,
                        status_code=0,
                        response_body=str(exc).encode("utf-8"),
                    )
                    time.sleep(0.5)
                    continue

                try:
                    payload = self._parse_payload(raw_payload)
                except (AppError, JSONPParseError, SchemaMismatchError) as exc:
                    error_kind = exc.kind.name if isinstance(exc, AppError) else "PARSER"
                    self._log_evidence(
                        error_type=f"PARSER_{error_kind}",
                        oid=oid,
                        aid=aid,
                        attempt=attempt,
                        status_code=200,
                        response_body=self._encode_payload(raw_payload),
                    )
                    time.sleep(0.5)
                    continue

                if self.probe.deep_validate_response(payload):
                    logger.info("Sample %s Success on attempt %s", tried, attempt)
                    success_count += 1
                    sample_success = True
                    break

                logger.error("Sample %s Failed schema validation on attempt %s", tried, attempt)
                self._log_evidence(
                    error_type="SCHEMA_MISMATCH",
                    oid=oid,
                    aid=aid,
                    attempt=attempt,
                    status_code=200,
                    response_body=self._encode_payload(payload),
                )
                time.sleep(0.5)

            if not sample_success:
                logger.error("Sample %s exhausted all probe attempts without success.", tried)

        pass_threshold = 2 if len(samples) >= 3 else len(samples)
        if success_count >= pass_threshold and len(samples) > 0:
            logger.info("Pre-flight Health Check PASSED (%s/%s)", success_count, tried)
            return True

        logger.critical("Pre-flight Health Check FAILED (%s/%s)", success_count, tried)
        return False

    def _fetch_comment_payload(self, oid: str, aid: str, params: Dict[str, str]) -> Any:
        fetch_page_attr = getattr(self.comment_fetcher, "fetch_page", None)
        if callable(fetch_page_attr):
            return fetch_page_attr(oid, aid, 1, params)

        fetch_attr = getattr(self.comment_fetcher, "fetch", None)
        if callable(fetch_attr):
            return fetch_attr(oid, aid, 1, params, "comment", None)
        raise AppError("Comment fetcher missing fetch_page/fetch.", Severity.ABORT, ErrorKind.UNKNOWN)

    def _parse_payload(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            parsed = payload
        else:
            body_text = payload if isinstance(payload, str) else str(payload)
            if not self.comment_parser:
                return json.loads(body_text)
            parsed = self.comment_parser.parse_jsonp(body_text)

        if self.comment_parser:
            self.comment_parser.validate_schema(parsed)
        return parsed

    def _encode_payload(self, payload: Any) -> bytes:
        if isinstance(payload, bytes):
            return payload
        try:
            return json.dumps(payload, ensure_ascii=False).encode("utf-8")
        except Exception:
            return str(payload).encode("utf-8", errors="ignore")

    def _log_evidence(
        self,
        error_type: str,
        oid: str,
        aid: str,
        attempt: int,
        status_code: int,
        response_body: Optional[bytes],
    ) -> None:
        self.evidence.log_failed_request(
            method="GET",
            url=self._comment_api_url(),
            status_code=status_code,
            error_type=error_type,
            headers={},
            context={"oid": oid, "aid": aid, "stage": "health_check", "attempt": attempt},
            response_body=response_body,
        )

    def _comment_api_url(self) -> str:
        if self.comment_fetcher and hasattr(self.comment_fetcher, "api_url"):
            return getattr(self.comment_fetcher, "api_url")
        return "comment_endpoint"
