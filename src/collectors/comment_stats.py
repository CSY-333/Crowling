import logging
from typing import Any, Callable, Dict, Optional

from ..common.errors import AppError, ErrorKind, Severity
from ..config import CommentStatsConfig
from ..interfaces import IHttpClient
from ..ops.evidence import EvidenceCollector

logger = logging.getLogger(__name__)


class CommentStatsService:
    """
    Fetches demographic statistics (gender/age ratios) for Naver news articles.
    Uses the same objectId + ticket/template parameters discovered for comment fetching.
    """

    def __init__(
        self,
        http_client: IHttpClient,
        evidence: EvidenceCollector,
        config: CommentStatsConfig,
        parse_jsonp: Callable[[str], Dict[str, Any]],
    ):
        self.http_client = http_client
        self.evidence = evidence
        self.config = config
        self.parse_jsonp = parse_jsonp
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Referer": "https://n.news.naver.com/",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        self.url = config.stats_endpoint

    def fetch_stats(self, oid: str, aid: str, endpoint_params: Dict[str, str]) -> Optional[Dict[str, Any]]:
        if not self.config.enabled:
            return None

        query = self._build_query(oid, aid, endpoint_params)
        try:
            response = self.http_client.request(
                "GET",
                self.url,
                headers=self.headers,
                params=query,
                timeout=10,
            )
        except Exception as exc:  # broad to capture network failures without requests dependency
            self.evidence.log_failed_request(
                method="GET",
                url=self.url,
                status_code=0,
                error_type="REQUEST_EXCEPTION",
                headers=self.headers,
                context={"oid": oid, "aid": aid, "params": query, "scope": "comment_stats"},
                response_body=None,
            )
            raise AppError(str(exc), Severity.RETRY, ErrorKind.HTTP, original_exception=exc)

        if response.status_code >= 400:
            body = self._as_bytes(getattr(response, "content", None))
            self.evidence.log_failed_request(
                method="GET",
                url=self.url,
                status_code=response.status_code,
                error_type="HTTP_ERROR",
                headers=self.headers,
                context={"oid": oid, "aid": aid, "params": query, "scope": "comment_stats"},
                response_body=body,
            )
            raise AppError(f"Stats HTTP {response.status_code}", Severity.WARN, ErrorKind.HTTP)

        payload = self.parse_jsonp(response.text)
        try:
            return self._normalize(payload)
        except Exception as exc:
            raise AppError(f"Invalid stats payload: {exc}", Severity.WARN, ErrorKind.PARSE, original_exception=exc)

    def _build_query(self, oid: str, aid: str, params: Dict[str, str]) -> Dict[str, Any]:
        query = {
            "lang": "ko",
            "ticket": params.get("ticket", "news"),
            "templateId": params.get("templateId", "default_society"),
            "pool": params.get("pool", "cbox5"),
            "objectId": f"news{oid},{aid}",
        }
        for optional in ("cv", "template"):
            if optional in params:
                query[optional] = params[optional]
        return query

    def _normalize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = payload.get("result") or {}
        total = self._coerce_int(
            result.get("commentCount")
            or result.get("realCommentCount")
            or (result.get("count") or {}).get("comment")
            or (result.get("count") or {}).get("total")
            or 0
        )
        gender_map = {"male": 0.0, "female": 0.0}
        for entry in result.get("commentByGender", []):
            gender = (entry.get("gender") or "").upper()
            ratio = self._coerce_float(entry.get("ratio"))
            if gender == "M":
                gender_map["male"] = ratio
            elif gender == "F":
                gender_map["female"] = ratio

        age_map = {slot: 0.0 for slot in ("10", "20", "30", "40", "50", "60", "70")}
        for entry in result.get("commentByAge", []):
            age_key = str(entry.get("age"))
            if age_key in age_map:
                age_map[age_key] = self._coerce_float(entry.get("ratio"))

        return {
            "total_comments": total,
            "gender": gender_map,
            "age": age_map,
        }

    @staticmethod
    def _coerce_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _coerce_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _as_bytes(value: Any) -> Optional[bytes]:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode("utf-8", errors="ignore")
        return None
