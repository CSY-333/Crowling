import logging
import requests
from typing import Dict, Any, Optional
from ..config import AppConfig
from ..ops.rate_limiter import RateLimiter
from ..ops.throttle import AutoThrottler
from ..ops.evidence import EvidenceCollector
from ..interfaces import IHttpClient
from ..common.errors import AppError, Severity, ErrorKind

logger = logging.getLogger(__name__)

class CommentFetcher:
    API_URL = "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json"

    def __init__(
        self,
        http_client: IHttpClient,
        rate_limiter: RateLimiter,
        throttler: AutoThrottler,
        evidence: EvidenceCollector,
        config: AppConfig
    ):
        self.http_client = http_client
        self.rate_limiter = rate_limiter
        self.throttler = throttler
        self.evidence = evidence
        self.config = config
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Referer": "https://n.news.naver.com/",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        self.api_url = self.API_URL

    def fetch(
        self,
        oid: str,
        aid: str,
        page: int,
        params: Dict[str, str],
        scope: str,
        parent_comment_no: Optional[str]
    ) -> str:
        query = self._build_query_params(oid, aid, page, params, scope, parent_comment_no)
        
        self.rate_limiter.wait()
        try:
            # Using http_client.request assuming it behaves like requests.Session.request
            response = self.http_client.request(
                "GET",
                self.API_URL,
                headers=self.headers,
                params=query,
                timeout=(
                    self.config.collection.timeout.connect,
                    self.config.collection.timeout.read,
                ),
            )
        except requests.RequestException as exc:
            self.evidence.log_failed_request(
                method="GET",
                url=self.API_URL,
                status_code=0,
                error_type="REQUEST_EXCEPTION",
                headers=self.headers,
                context={"scope": scope, "oid": oid, "aid": aid, "page": page, "params": query},
                response_body=None
            )
            raise AppError(f"Network request failed: {exc}", Severity.RETRY, ErrorKind.HTTP, original_exception=exc)

        self.throttler.observe(response.status_code)

        if response.status_code >= 400:
            self.evidence.log_failed_request(
                method="GET",
                url=self.API_URL,
                status_code=response.status_code,
                error_type="HTTP_ERROR",
                headers=self.headers,
                context={"scope": scope, "oid": oid, "aid": aid, "page": page, "params": query},
                response_body=response.content
            )
            if response.status_code == 403:
                raise AppError("403 Forbidden", Severity.ABORT, ErrorKind.HTTP)
            
            raise AppError(f"HTTP {response.status_code}", Severity.RETRY, ErrorKind.HTTP)

        return response.text

    def fetch_page(
        self,
        oid: str,
        aid: str,
        page: int,
        params: Dict[str, str],
        scope: str = "comment",
        parent_comment_no: Optional[str] = None,
    ) -> str:
        """
        Public helper so orchestration/health-check code can fetch a single
        comment or reply page without needing to know implementation details.
        """
        return self.fetch(
            oid=oid,
            aid=aid,
            page=page,
            params=params,
            scope=scope,
            parent_comment_no=parent_comment_no,
        )

    def _build_query_params(self, oid: str, aid: str, page: int, params: Dict[str, str], scope: str, parent_comment_no: Optional[str]) -> Dict[str, Any]:
        query = {
            "ticket": params.get("ticket", "news"),
            "templateId": params.get("templateId", "default_society"),
            "pool": params.get("pool", "cbox5"),
            "lang": "ko",
            "country": "KR",
            "objectId": f"news{oid},{aid}",
            "page": page,
            "pageSize": params.get("pageSize", 20),
            "indexSize": params.get("indexSize", 10),
            "pageType": "more",
            "listType": "OBJECT",
            "sort": params.get("sort", "FAVORITE"),
            "initialize": "true" if page == 1 else "false",
            "replyPageSize": params.get("replyPageSize", 20),
            "useAltSort": "true",
            "includeAllStatus": "true",
        }
        # ... (rest of logic same as original) ...
        optional_keys = ("cv", "template", "moreType")
        for key in optional_keys:
            if key in params:
                query[key] = params[key]

        if scope == "reply":
            query["moreType"] = "child"
            query["parentCommentNo"] = parent_comment_no
            query["pageSize"] = params.get("replyPageSize", 20)
            query["replyPageSize"] = params.get("replyPageSize", 20)
            query["page"] = page
        
        return query
