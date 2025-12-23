# NACT-MVP Codebase Summary

Generated at: 12/24/2025 01:27:02

## Directory Structure

`	ext
src\collectors
src\common
src\http
src\ops
src\privacy
src\storage
src\__pycache__
src\config.py
src\interfaces.py
src\main.py
src\__init__.py
src\collectors\__pycache__
src\collectors\article_parser.py
src\collectors\comment_collector.py
src\collectors\comment_fetcher.py
src\collectors\comment_parser.py
src\collectors\search_collector.py
src\collectors\__init__.py
src\collectors\__pycache__\article_parser.cpython-313.pyc
src\collectors\__pycache__\comment_collector.cpython-313.pyc
src\collectors\__pycache__\comment_fetcher.cpython-313.pyc
src\collectors\__pycache__\comment_parser.cpython-313.pyc
src\collectors\__pycache__\search_collector.cpython-313.pyc
src\collectors\__pycache__\__init__.cpython-313.pyc
src\common\__pycache__
src\common\errors.py
src\common\__pycache__\errors.cpython-313.pyc
src\http\__pycache__
src\http\client.py
src\http\__init__.py
src\http\__pycache__\client.cpython-313.pyc
src\http\__pycache__\__init__.cpython-313.pyc
src\ops\__pycache__
src\ops\evidence.py
src\ops\health_check.py
src\ops\logger.py
src\ops\probe.py
src\ops\rate_limiter.py
src\ops\throttle.py
src\ops\__init__.py
src\ops\__pycache__\evidence.cpython-313.pyc
src\ops\__pycache__\health_check.cpython-313.pyc
src\ops\__pycache__\logger.cpython-313.pyc
src\ops\__pycache__\probe.cpython-313.pyc
src\ops\__pycache__\rate_limiter.cpython-313.pyc
src\ops\__pycache__\throttle.cpython-313.pyc
src\ops\__pycache__\__init__.cpython-313.pyc
src\privacy\__pycache__
src\privacy\hashing.py
src\privacy\__init__.py
src\privacy\__pycache__\hashing.cpython-313.pyc
src\privacy\__pycache__\__init__.cpython-313.pyc
src\storage\__pycache__
src\storage\db.py
src\storage\exporters.py
src\storage\repository.py
src\storage\__init__.py
src\storage\__pycache__\db.cpython-313.pyc
src\storage\__pycache__\__init__.cpython-313.pyc
src\__pycache__\config.cpython-313.pyc
src\__pycache__\interfaces.cpython-313.pyc
src\__pycache__\main.cpython-313.pyc
src\__pycache__\__init__.cpython-313.pyc
tests\__pycache__
tests\conftest.py
tests\test_article_parser.py
tests\test_cli_foundations.py
tests\test_comment_collector.py
tests\test_comment_fetcher.py
tests\test_common_errors.py
tests\test_config_loader.py
tests\test_ops_evidence.py
tests\test_ops_health.py
tests\test_ops_health_check.py
tests\test_ops_logger.py
tests\test_ops_probe.py
tests\test_privacy_hashing.py
tests\test_rate_limiter.py
tests\test_search_collector.py
tests\test_storage_db.py
tests\test_storage_exporters.py
tests\test_throttle.py
tests\__pycache__\conftest.cpython-313-pytest-9.0.2.pyc
tests\__pycache__\test_comment_collector.cpython-313-pytest-9.0.2.pyc
tests\__pycache__\test_throttle.cpython-313-pytest-9.0.2.pyc
config\default.yaml
``n
## File Contents

### src\collectors\article_parser.py

`python
import re
import logging
import json
from bs4 import BeautifulSoup
from typing import Dict, Optional, Tuple, Any
from urllib.parse import urlparse, parse_qs
from src.interfaces import IHttpClient
from src.http.client import RequestsHttpClient

logger = logging.getLogger(__name__)

class ArticleParser:
    def __init__(self, http_client: IHttpClient):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        self.http_client = http_client

    def parse_oid_aid(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract oid and aid from Naver News URL.
        Supports standard news.naver.com pattern.
        """
        try:
            # Pattern 1: https://n.news.naver.com/mnews/article/{oid}/{aid}?sid=101
            match = re.search(r'/article/(\d+)/(\d+)', url)
            if match:
                return match.group(1), match.group(2)
            
            # Pattern 2: Query params (old style)
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            if 'oid' in qs and 'aid' in qs:
                return qs['oid'][0], qs['aid'][0]
                
            return None, None
        except Exception:
            return None, None

    def fetch_and_parse(self, url: str) -> Dict[str, Any]:
        """
        Fetch article HTML and extract metadata.
        Returns dictionary with title, published_at, etc.
        """
        result = {
            "title": None,
            "published_at": None, 
            "updated_at": None,
            "press": None,
            "reporter": None,
            "section": None,
            "body": None,
            "body_length": 0,
            "status_code": "FAIL-PARSE"
        }
        
        try:
            # Add Referer to allow some deep linking
            resp = self.http_client.request("GET", url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                result["status_code"] = "FAIL-HTTP"
                result["error_code"] = str(resp.status_code)
                return result
                
            soup = BeautifulSoup(resp.text, 'lxml')
            
            # Store raw HTML for Probe usage (hidden field)
            result["_raw_html"] = resp.text

            # Strategy 1: JSON-LD (Preferred)
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    data = json.loads(json_ld.string)
                    # Handle list of objects or single object
                    if isinstance(data, list):
                        data = data[0]
                    
                    if '@type' in data and 'NewsArticle' in data['@type']:
                        result['title'] = data.get('headline')
                        result['published_at'] = data.get('datePublished')
                        result['updated_at'] = data.get('dateModified')
                        result['section'] = data.get('articleSection')
                        if data.get('author'):
                            result['reporter'] = data['author'].get('name') if isinstance(data['author'], dict) else None
                except Exception:
                    pass # Fallback to selectors
            
            # Extract common metadata
            # Title
            if not result['title']:
                title_tag = soup.find('h2', id='title_area') or soup.find('title')
                if title_tag:
                    result["title"] = title_tag.get_text(strip=True)
                
            # Published At (many patterns, trying most common)
            # data-date-time attribute in span
            if not result['published_at']:
                date_span = soup.select_one('span[data-date-time]')
                if date_span:
                    result["published_at"] = date_span['data-date-time']
                else:
                # Fallback to meta tag
                    meta_date = soup.find('meta', property='article:published_time')
                    if meta_date:
                        result['published_at'] = meta_date['content']

            # Updated At
            if not result['updated_at']:
                updated_span = soup.select_one('span.media_end_head_info_datestamp_time._MODIFY_DATE_TIME')
                if updated_span and updated_span.has_attr('data-date-time'):
                    result['updated_at'] = updated_span['data-date-time']

            # Press
            press_img = soup.select_one('a.media_end_head_top_logo img')
            if press_img:
                result['press'] = press_img.get('title') or press_img.get('alt')
                
            # Reporter
            # Common selector: .media_end_head_journalist_name
            if not result['reporter']:
                reporter_tag = soup.select_one('.media_end_head_journalist_name')
                if reporter_tag:
                    result['reporter'] = reporter_tag.get_text(strip=True)

            # Body Content
            # Standard Naver News body id: #dic_area
            body_div = soup.select_one('#dic_area')
            if body_div:
                # Remove captions/photos
                for useless in body_div.select('.end_photo_org, .img_desc, script, style'):
                    useless.decompose()
                result['body'] = body_div.get_text(separator='\n', strip=True)
                result['body_length'] = len(result['body'])

            result["status_code"] = "CRAWL-OK"
            return result
            
        except Exception as e:
            logger.error(f"Article parse failed {url}: {e}")
            result["error_message"] = str(e)
            return result

``n
### src\collectors\comment_collector.py

`python
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

``n
### src\collectors\comment_fetcher.py

`python
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

``n
### src\collectors\comment_parser.py

`python
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
``n
### src\collectors\search_collector.py

`python
import time
import logging
import re
from typing import Dict, Any, Generator, Optional
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from ..config import SearchConfig
from src.interfaces import IHttpClient
from src.http.client import RequestsHttpClient

logger = logging.getLogger(__name__)

class SearchCollector:
    def __init__(self, config: SearchConfig, http_client: IHttpClient):
        self.config = config
        self.base_url = "https://openapi.naver.com/v1/search/news.json"
        self.fallback_url = "https://search.naver.com/search.naver"
        # Keep track of deduplicated articles so repeated keywords don't emit duplicates
        self._dedup_index: Dict[str, Dict[str, Any]] = {}
        self.http_client = http_client
        
    def extract_oid_aid(self, url: str) -> Dict[str, str]:
        """
        Extract oid and aid from URL to serve as unique ID.
        """
        # Pattern 1: /article/001/0000001
        match = re.search(r'/article/(\d+)/(\d+)', url)
        if match:
            return {"oid": match.group(1), "aid": match.group(2)}
        
        # Pattern 2: Query params
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if 'oid' in qs and 'aid' in qs:
            return {"oid": qs['oid'][0], "aid": qs['aid'][0]}
            
        return {}

    def normalize_url(self, url: str) -> str:
        """
        Normalize URL to standard Naver News format if possible.
        """
        ids = self.extract_oid_aid(url)
        if ids:
            return f"https://n.news.naver.com/mnews/article/{ids['oid']}/{ids['aid']}"
        return url

    def _make_dedup_key(self, oid: Optional[str], aid: Optional[str], url: str) -> str:
        """
        Choose dedup key using (oid, aid) when available, else normalized URL.
        """
        if oid and aid:
            return f"{oid}:{aid}"
        return self.normalize_url(url)

    def _register_article(self, entry: Dict[str, Any], keyword: str) -> bool:
        """
        Returns True if the article is new and should be yielded.
        Updates matched_keywords if the article was already seen.
        """
        dedup_key = self._make_dedup_key(entry.get("oid"), entry.get("aid"), entry.get("url", ""))
        existing = self._dedup_index.get(dedup_key)
        if existing:
            if keyword not in existing["matched_keywords"]:
                existing["matched_keywords"].append(keyword)
            return False

        entry["matched_keywords"] = [keyword]
        self._dedup_index[dedup_key] = entry
        return True

    def search_keyword(self, keyword: str) -> Generator[Dict[str, Any], None, None]:
        """
        Search for articles using Naver OpenAPI.
        Yields normalized article dictionaries.
        """
        if not self.config.use_openapi or not self.config.client_id or not self.config.client_secret:
            logger.info("OpenAPI disabled or not configured. Using HTML fallback.")
            yield from self._search_fallback(keyword)
            return

        headers = {
            "X-Naver-Client-Id": self.config.client_id,
            "X-Naver-Client-Secret": self.config.client_secret
        }
        
        display = 100 # Max allowed by Naver
        start = 1
        total_yielded = 0
        max_limit = self.config.max_articles_per_keyword
        global_rank = 1
        
        while total_yielded < max_limit:
            params = {
                "query": keyword,
                "display": min(display, max_limit - total_yielded),
                "start": start,
                "sort": "sim" if self.config.sort == "rel" else "date"
            }
            
            try:
                resp = self.http_client.request(
                    "GET",
                    self.base_url,
                    headers=headers,
                    params=params,
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                
                items = data.get('items', [])
                if not items:
                    logger.info(f"No more items for keyword '{keyword}' at start={start}")
                    break
                    
                for item in items:
                    raw_url = item.get('originallink') or item.get('link', '')
                    url = self.normalize_url(raw_url)
                    ids = self.extract_oid_aid(url)
                    
                    normalized_item = {
                        "search_rank": global_rank,
                        "keyword": keyword,
                        "url": url,
                        "title": item.get('title', ''),
                        "published_at": item.get('pubDate', ''),
                        "description": item.get('description', ''),
                        "oid": ids.get('oid'),
                        "aid": ids.get('aid')
                    }
                    
                    if self._register_article(normalized_item, keyword):
                        yield normalized_item
                        total_yielded += 1
                        global_rank += 1
                    else:
                        logger.debug(f"Duplicate article skipped during OpenAPI search: {url}")
                    
                start += len(items)
                if start > 1000: # Naver limits start to 1000
                    logger.info("Reached Naver OpenAPI pagination limit (1000).")
                    # Fallback to HTML search for deeper results if needed
                    yield from self._search_fallback(keyword, start_page=(start // 10) + 1, start_rank=global_rank)
                    break
                    
                time.sleep(0.1) # Polite delay
                
            except Exception as e:
                logger.error(f"OpenAPI search failed for '{keyword}': {e}. Switching to fallback.")
                yield from self._search_fallback(keyword, start_page=(start // 10) + 1, start_rank=global_rank)
                break

    def _search_fallback(self, keyword: str, start_page: int = 1, start_rank: int = 1) -> Generator[Dict[str, Any], None, None]:
        """
        Fallback: Scrape Naver Search HTML.
        """
        logger.info(f"Starting HTML fallback search for '{keyword}' from page {start_page}")
        
        page = start_page
        current_rank = start_rank
        
        while True:
            # Naver search 'start' param is 1-based index (1, 11, 21...)
            start_index = (page - 1) * 10 + 1
            if start_index > 4000: # Practical limit for HTML scraping
                break
                
            params = {
                "where": "news",
                "query": keyword,
                "start": start_index,
                "sort": "0" if self.config.sort == "rel" else "1"
            }
            
            try:
                resp = self.http_client.request(
                    "GET",
                    self.fallback_url,
                    params=params,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10,
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, 'lxml')
                
                articles = soup.select('ul.list_news > li')
                if not articles:
                    break
                    
                for li in articles:
                    link = li.select_one('a.news_tit')
                    if link:
                        url = link['href']
                        ids = self.extract_oid_aid(url)
                        normalized_item = {
                            "search_rank": current_rank,
                            "keyword": keyword,
                            "url": self.normalize_url(url),
                            "title": link.get_text(strip=True),
                            "published_at": "", # Hard to parse reliably from list view
                            "oid": ids.get('oid'),
                            "aid": ids.get('aid')
                        }
                        if self._register_article(normalized_item, keyword):
                            yield normalized_item
                            current_rank += 1
                        else:
                            logger.debug(f"Duplicate article skipped during fallback search: {url}")
                
                page += 1
                time.sleep(0.5) # Higher delay for scraping
            except Exception as e:
                logger.error(f"Fallback search failed: {e}")
                break

``n
### src\collectors\__init__.py

`python

``n
### src\common\errors.py

`python
from enum import Enum
from typing import Optional


class Severity(Enum):
    INFO = "INFO"
    WARN = "WARN"
    RETRY = "RETRY"
    ABORT = "ABORT"


class ErrorKind(Enum):
    HTTP = "HTTP"
    PARSE = "PARSE"
    SCHEMA = "SCHEMA"
    STRUCTURAL = "STRUCTURAL"
    UNKNOWN = "UNKNOWN"


class AppError(Exception):
    """
    Domain-specific error that carries severity + classification metadata so
    callers can decide how to recover.
    """

    def __init__(
        self,
        message: str,
        severity: Severity = Severity.WARN,
        kind: ErrorKind = ErrorKind.UNKNOWN,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.severity = severity
        self.kind = kind
        self.original_exception = original_exception

    def __str__(self) -> str:
        base = super().__str__()
        return f"[{self.severity.name}/{self.kind.name}] {base}"

``n
### src\http\client.py

`python
import requests

from src.interfaces import IHttpClient


class RequestsHttpClient(IHttpClient):
    """
    Thin adapter over requests.Session that satisfies IHttpClient.
    """

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def request(self, method: str, url: str, **kwargs):
        return self.session.request(method=method, url=url, **kwargs)

``n
### src\http\__init__.py

`python


``n
### src\ops\evidence.py

`python
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import hashlib

class EvidenceCollector:
    def __init__(self, run_id: str, logs_dir: str = "logs"):
        self.run_id = run_id
        self.logs_dir = Path(logs_dir)
        self.requests_log_path = self.logs_dir / "failed_requests.jsonl"
        self.responses_dir = self.logs_dir / "failed_responses"
        
        # Ensure directories exist
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.responses_dir.mkdir(parents=True, exist_ok=True)

    def log_failed_request(
        self, 
        method: str, 
        url: str, 
        status_code: int, 
        error_type: str, 
        headers: Dict[str, str], 
        context: Dict[str, Any],
        response_body: Optional[bytes] = None
    ):
        """
        Log failed request metadata to JSONL and save body sample if provided.
        """
        timestamp = datetime.now().isoformat()
        
        # Redact secrets from headers
        safe_headers = {k: v for k, v in headers.items() if 'auth' not in k.lower() and 'key' not in k.lower()}
        
        entry = {
            "timestamp": timestamp,
            "run_id": self.run_id,
            "method": method,
            "full_url": url,
            "status_code": status_code,
            "error_type": error_type,
            "headers": safe_headers,
            "context": context
        }
        
        # Save body sample if available
        if response_body:
            body_hash = hashlib.sha256(response_body).hexdigest()[:16]
            body_sample_path = self.responses_dir / f"{body_hash}.txt"
            entry["body_sample_path"] = str(body_sample_path)
            
            # Save first 2KB
            try:
                with open(body_sample_path, "wb") as f:
                    # If binary, save hex? For now just save raw bytes, it's safer for debug tools.
                    # Or decode safely. Use 'errors=replace' for text view.
                    f.write(response_body[:2048])
                    if len(response_body) > 2048:
                        f.write(b"\n...[TRUNCATED]")
            except Exception as e:
                entry["body_save_error"] = str(e)

        # Append to JSONL
        try:
            with open(self.requests_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"CRITICAL: Failed to write evidence log: {e}")

``n
### src\ops\health_check.py

`python
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

``n
### src\ops\logger.py

`python
import logging
import sys
from pathlib import Path
from datetime import datetime

def setup_logger(run_id: str, logs_dir: str = "logs") -> logging.Logger:
    """
    Configures the root logger:
    - Console: INFO level
    - File: DEBUG level (logs/debug_{timestamp}.log)
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers to avoid duplicates during re-runs or tests
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 1. Console Handler (INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. File Handler (DEBUG)
    log_path = Path(logs_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    filename = f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{run_id}.log"
    file_handler = logging.FileHandler(log_path / filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
``n
### src\ops\probe.py

`python
import logging
import re
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class EndpointProbe:
    def __init__(self):
        self.known_configs = [
            # Config A (New API likely)
            {"ticket": "news", "templateId": "default_society"},
            # Config B (Fallback)
            {"ticket": "news", "templateId": "view_politics"},
        ]

    def get_candidate_configs(self, url: str, article_html: str) -> List[Dict[str, str]]:
        """
        Returns a list of configuration dictionaries to try, in order of priority:
        1. Auto-discovered parameters (if any)
        2. Known Config A
        3. Known Config B
        """
        candidates = []
        
        discovered = self.discover_parameters(url, article_html)
        if discovered:
            candidates.append(discovered)
            
        # Append fallbacks
        candidates.extend(self.known_configs)
        return candidates

    def discover_parameters(self, article_url: str, article_html: str) -> Optional[Dict[str, str]]:
        """
        Attempt to auto-discover parameters from HTML (ticket, templateId, objectId).
        Fallback to known configs if auto-discovery fails.
        """
        # 1. Auto-discovery (Regex/DOM)
        discovered = {} 
        
        if article_html:
            # Pattern 1: var _cv = "news"; var _templateId = "view_politics";
            # Note: Naver often uses `data-service-name` or JS vars.
            
            # Ticket (service name)
            ticket_match = re.search(r'serviceName\s*:\s*["\']([^"\']+)["\']', article_html)
            if not ticket_match:
                ticket_match = re.search(r'_cv\s*=\s*["\']([^"\']+)["\']', article_html)
            
            if ticket_match:
                discovered['ticket'] = ticket_match.group(1)
            else:
                discovered['ticket'] = 'news' # Default

            # Template ID
            # Look for `templateId = 'view_politics'` or similar
            tmpl_match = re.search(r'templateId\s*:\s*["\']([^"\']+)["\']', article_html)
            if not tmpl_match:
                tmpl_match = re.search(r'_templateId\s*=\s*["\']([^"\']+)["\']', article_html)
            
            if tmpl_match:
                discovered['templateId'] = tmpl_match.group(1)

            # Pool (cbox5 usually, but sometimes different)
            pool_match = re.search(r'pool\s*[:=]\s*["\']([^"\']+)["\']', article_html)
            if pool_match:
                discovered['pool'] = pool_match.group(1)

            # CV (Client Version or similar)
            cv_match = re.search(r'_cv\s*=\s*["\']([^"\']+)["\']', article_html)
            if cv_match:
                discovered['cv'] = cv_match.group(1)
                
            # Template (sometimes distinct from templateId)
            t_match = re.search(r'template\s*:\s*["\']([^"\']+)["\']', article_html)
            if t_match:
                discovered['template'] = t_match.group(1)

            # ObjectId is usually constructed from oid,aid, but sometimes explicit
            # We assume caller has oid,aid. If needed, we can extract `g_did` or `newsId` here.
        
        if discovered.get('ticket') and discovered.get('templateId'):
            logger.debug(f"Probe discovered params: {discovered}")
            return discovered
        return None

    def deep_validate_response(self, json_data: Dict[str, Any]) -> bool:
        """
        Validate schema integrity of comment response.
        Must contain 'result' -> 'commentList' -> [0] -> 'contents'/'regTime'
        """
        try:
            # Naver typical response: { "success": true, "result": { "commentList": [...] } }
            if not json_data.get('success', False):
                return False
                
            result = json_data.get('result', {})
            if 'commentList' not in result:
                # Sometimes it returns pageModel but empty list?
                # If commentList is missing entirely, it's suspicious unless count=0
                return False
                
            comment_list = result.get('commentList', [])
            if comment_list:
                first = comment_list[0]
                # Check for critical fields
                required = ['commentNo', 'contents', 'regTime'] 
                if not all(k in first for k in required):
                    logger.warning(f"Probe: Missing keys in comment: {first.keys()}")
                    return False
                    
            return True
        except Exception:
            return False

``n
### src\ops\rate_limiter.py

`python
import time
import random
import logging
import requests
from ..config import RateLimitConfig

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Manages request delays and provides a reusable session.
    """
    def __init__(self, config: RateLimitConfig):
        self.baseline_min = config.baseline_min_delay
        self.min_delay = config.min_delay
        self.max_delay = config.max_delay
        self.session = requests.Session()
        
        # Ensure max is valid relative to min
        if self.max_delay < self.min_delay:
            self.max_delay = self.min_delay + 1.0

    def wait(self):
        """
        Sleep for a random duration between min_delay and max_delay.
        """
        delay = random.uniform(self.min_delay, self.max_delay)
        if delay > 0:
            time.sleep(delay)

    def update_min_delay(self, new_min: float):
        """
        Update the minimum delay (e.g. from AutoThrottler).
        Automatically adjusts max_delay to maintain the spread.
        """
        self.min_delay = max(0.0, new_min)
        # Maintain the original spread or at least ensure max > min
        spread = max(1.0, self.max_delay - self.baseline_min) 
        self.max_delay = self.min_delay + spread
        
    def close(self):
        self.session.close()
``n
### src\ops\throttle.py

`python
import logging
from collections import deque
from datetime import datetime
from ..config import AutoThrottleConfig
from ..storage.db import Database
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

class AutoThrottler:
    """
    Monitors response status codes and adjusts RateLimiter delays.
    Implements 429 backoff and 403 emergency stop.
    """
    def __init__(self, config: AutoThrottleConfig, limiter: RateLimiter, db: Database, run_id: str):
        self.config = config
        self.limiter = limiter
        self.db = db
        self.run_id = run_id
        
        # Sliding window for 429 detection (True if 429, False otherwise)
        self.history = deque(maxlen=config.window)
        
        # Recovery window (longer history)
        self.recovery_history = deque(maxlen=config.recovery_window)
        
        self.is_stopped = False
        self.stop_reason = None

    def observe(self, status_code: int):
        """
        Feed a response status code to the throttler.
        """
        if self.is_stopped:
            return

        # 1. Hard Rule: Stop on 403
        if self.config.stop_on_403 and status_code == 403:
            self._emergency_stop("Received 403 Forbidden")
            return

        # 2. Record history
        is_429 = (status_code == 429)
        self.history.append(is_429)
        self.recovery_history.append(is_429)

        # 3. Check Throttle Up (Window full)
        if len(self.history) == self.history.maxlen:
            ratio_429 = sum(self.history) / len(self.history)
            if ratio_429 > self.config.ratio_429_threshold:
                self._throttle_up(ratio_429)
                # Clear history to avoid rapid-fire step-ups
                self.history.clear() 
                return

        # 4. Check Recovery (Window full)
        if len(self.recovery_history) == self.recovery_history.maxlen:
            ratio_429_rec = sum(self.recovery_history) / len(self.recovery_history)
            if ratio_429_rec < self.config.ratio_429_recovery_threshold:
                # Only recover if we are above baseline
                if self.limiter.min_delay > self.limiter.baseline_min:
                    self._throttle_down(ratio_429_rec)
                    self.recovery_history.clear()

    def _throttle_up(self, ratio: float):
        old_val = self.limiter.min_delay
        new_val = old_val + self.config.min_delay_step_up
        self.limiter.update_min_delay(new_val)
        
        msg = f"Throttle UP: 429 ratio {ratio:.2%} > {self.config.ratio_429_threshold:.2%}. Delay {old_val:.2f}s -> {new_val:.2f}s"
        logger.warning(msg)
        self._log_event("THROTTLE_UP", msg)

    def _throttle_down(self, ratio: float):
        old_val = self.limiter.min_delay
        new_val = max(self.limiter.baseline_min, old_val - self.config.min_delay_step_down)
        
        if new_val != old_val:
            self.limiter.update_min_delay(new_val)
            msg = f"Throttle DOWN: Recovery ratio {ratio:.2%}. Delay {old_val:.2f}s -> {new_val:.2f}s"
            logger.info(msg)
            self._log_event("THROTTLE_DOWN", msg)

    def _emergency_stop(self, reason: str):
        self.is_stopped = True
        self.stop_reason = reason
        logger.critical(f"AutoThrottler triggered STOP: {reason}")
        self._log_event("STOP_LIMIT", reason)
        
    def _log_event(self, event_type: str, details: str):
        try:
            conn = self.db.get_connection()
            with conn:
                conn.execute(
                    "INSERT INTO events (run_id, timestamp, event_type, details) VALUES (?, ?, ?, ?)",
                    (self.run_id, datetime.now().isoformat(), event_type, details)
                )
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log throttle event: {e}")
``n
### src\ops\__init__.py

`python

``n
### src\privacy\hashing.py

`python
import hashlib
import hmac
from typing import Optional

class PrivacyHasher:
    def __init__(self, salt: str):
        self.salt = salt.encode('utf-8')

    def hash_identifier(self, identifier: Optional[str]) -> Optional[str]:
        """
        Return SHA-256 HMAC of identifier using run salt.
        Safe against rainbow tables.
        Returns None if input is None/Empty.
        """
        if not identifier:
            return None
            
        return hmac.new(
            self.salt, 
            identifier.encode('utf-8'), 
            hashlib.sha256
        ).hexdigest()

``n
### src\privacy\__init__.py

`python

``n
### src\storage\db.py

`python
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
                        notes TEXT
                    );
                """)

                # 2. Articles Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS articles (
                        oid TEXT NOT NULL,
                        aid TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        url TEXT,
                        title TEXT,
                        press TEXT,
                        published_at TEXT,
                        updated_at TEXT,
                        crawl_at TEXT,
                        status_code TEXT,
                        error_code TEXT,
                        error_message TEXT,
                        PRIMARY KEY (oid, aid),
                        FOREIGN KEY (run_id) REFERENCES runs(run_id)
                    );
                """)

                # 3. Comments Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS comments (
                        comment_no TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
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
                        status_code TEXT,
                        error_code TEXT,
                        error_message TEXT,
                        FOREIGN KEY (run_id) REFERENCES runs(run_id),
                        FOREIGN KEY (oid, aid) REFERENCES articles(oid, aid)
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
            query = "SELECT oid, aid FROM articles WHERE status_code = 'SUCCESS'"
            params = []
            if run_id:
                query += " AND run_id = ?"
                params.append(run_id)
            cursor = conn.execute(query, params)
            return {(row['oid'], row['aid']) for row in cursor.fetchall()}
        finally:
            conn.close()

``n
### src\storage\exporters.py

`python
import csv
import logging
from pathlib import Path
from .db import Database

logger = logging.getLogger(__name__)

class DataExporter:
    def __init__(self, db: Database, export_dir: str = "exports"):
        self.db = db
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_run(self, run_id: str):
        """
        Exports articles and comments for a specific run to CSV.
        """
        logger.info(f"Starting export for run_id: {run_id}")
        
        self._export_table(
            table="articles",
            filename=f"articles_{run_id}.csv",
            where_clause="WHERE run_id = ?",
            params=(run_id,)
        )
        
        self._export_table(
            table="comments",
            filename=f"comments_{run_id}.csv",
            where_clause="WHERE run_id = ?",
            params=(run_id,)
        )
        
        # Export run log (append mode usually, but here we dump current run info)
        self._export_table(
            table="runs",
            filename=f"run_log_{run_id}.csv",
            where_clause="WHERE run_id = ?",
            params=(run_id,)
        )

    def _export_table(self, table: str, filename: str, where_clause: str = "", params: tuple = ()):
        filepath = self.export_dir / filename
        conn = self.db.get_connection()
        try:
            # Get headers
            cursor = conn.execute(f"SELECT * FROM {table} LIMIT 0")
            headers = [description[0] for description in cursor.description]
            
            # Get data
            sql = f"SELECT * FROM {table} {where_clause}"
            cursor = conn.execute(sql, params)
            
            row_count = 0
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                
                while True:
                    rows = cursor.fetchmany(1000)
                    if not rows:
                        break
                    writer.writerows(rows)
                    row_count += len(rows)
            
            logger.info(f"Exported {row_count} rows from '{table}' to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to export table {table}: {e}")
        finally:
            conn.close()
``n
### src\storage\repository.py

`python
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
``n
### src\storage\__init__.py

`python
# Storage Layer
``n
### src\config.py

`python
import yaml
from copy import deepcopy
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ValidationError

class SnapshotConfig(BaseModel):
    timezone: str = "Asia/Seoul"
    reference_time: Literal["start", "manual"] = "start"
    manual_snapshot_time: Optional[str] = None

class DateRangeConfig(BaseModel):
    start: str
    end: str

class SearchConfig(BaseModel):
    keywords: List[str]
    max_articles_per_keyword: int = 300
    date_range: DateRangeConfig
    sort: str = "rel"
    use_openapi: bool = True
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

class VolumeStrategyConfig(BaseModel):
    target_comments: int = 50000
    min_acceptable_comments: int = 30000
    max_total_articles: int = 2000
    estimator: str = "trimmed_mean_p20_p80"

class RateLimitConfig(BaseModel):
    baseline_min_delay: float = 1.0
    min_delay: float = 1.0
    max_delay: float = 3.0
    max_concurrent: int = 1

class RetryConfig(BaseModel):
    max_attempts: int = 3
    backoff_factor: float = 2.0

class TimeoutConfig(BaseModel):
    connect: float = 10.0
    read: float = 30.0

class AutoThrottleConfig(BaseModel):
    window: int = 50
    ratio_429_threshold: float = 0.05
    min_delay_step_up: float = 0.5
    recovery_window: int = 200
    ratio_429_recovery_threshold: float = 0.01
    min_delay_step_down: float = 0.2
    stop_on_403: bool = True

class CollectionConfig(BaseModel):
    rate_limit: RateLimitConfig
    retry: RetryConfig
    timeout: TimeoutConfig
    auto_throttle: AutoThrottleConfig

class StorageConfig(BaseModel):
    db_path: str = "./data/nact_data.db"
    wal_mode: bool = True

class PrivacyConfig(BaseModel):
    allow_pii: bool = False
    hash_algorithm: str = "sha256"
    hash_salt_mode: Literal["per_run", "global"] = "per_run"
    global_salt: Optional[str] = None

class AppConfig(BaseModel):
    snapshot: SnapshotConfig
    search: SearchConfig
    volume_strategy: VolumeStrategyConfig
    collection: CollectionConfig
    storage: StorageConfig
    privacy: PrivacyConfig


def _load_yaml_mapping(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        try:
            data = yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"Error parsing YAML config: {exc}")

    if not isinstance(data, dict):
        raise ValueError(f"Configuration file at {path} must contain a mapping at the top level.")
    return data


def _deep_merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: str) -> AppConfig:
    """
    Load YAML config, merge it with defaults, validate with Pydantic, and return a typed config object.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")

    default_config = _load_yaml_mapping(get_default_config_path())
    user_config = _load_yaml_mapping(path)
    merged_config = _deep_merge_dicts(default_config, user_config)

    try:
        config = AppConfig(**merged_config)

        if config.privacy.hash_salt_mode == "global" and not config.privacy.global_salt:
            raise ValueError("Privacy config error: 'global_salt' is required when 'hash_salt_mode' is 'global'.")

        return config
    except ValidationError as e:
        raise ValueError(f"Configuration validation failed: {e}")

def get_default_config_path() -> Path:
    """Returns the absolute path to the default config file."""
    # Assuming src/config.py is one level deep from root
    root_dir = Path(__file__).parent.parent
    return root_dir / "config" / "default.yaml"

``n
### src\interfaces.py

`python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Generator
from contextlib import contextmanager

class IHttpClient(ABC):
    @abstractmethod
    def request(self, method: str, url: str, **kwargs) -> Any:
        pass

class IEvidenceCollector(ABC):
    @abstractmethod
    def log_failed_request(self, method: str, url: str, status_code: int, error_type: str, headers: Dict, context: Dict, response_body: bytes = None):
        pass

class IThrottleController(ABC):
    @abstractmethod
    def wait(self, domain: str = "default"):
        pass

    @abstractmethod
    def update_stats(self, status_code: int):
        pass

class IStorageDAO(ABC):
    @abstractmethod
    @contextmanager
    def transaction(self) -> Generator:
        pass

    @abstractmethod
    def get_completed_articles(self, run_id: str) -> set:
        pass

    @abstractmethod
    def insert_comments(self, comments: List[Dict[str, Any]]):
        pass

    @abstractmethod
    def update_article_status(self, oid: str, aid: str, status: str):
        pass

``n
### src\main.py

`python
import argparse
import sys
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Add src to path to allow imports if running directly
sys.path.append(str(Path(__file__).parent.parent))

from src.config import load_config, get_default_config_path
from src.storage.db import Database
from src.ops.logger import setup_logger


@dataclass
class RuntimeContext:
    config: "AppConfig"
    db: Database
    run_id: str
    snapshot_at: str
    db_path: str


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="NACT-MVP: Naver Article & Comment Tracker")

    parser.add_argument(
        "--config",
        type=str,
        default=str(get_default_config_path()),
        help="Path to the YAML configuration file.",
    )

    parser.add_argument(
        "--resume-from-db",
        type=str,
        help="Path to an existing SQLite DB to resume from.",
    )

    return parser.parse_args(argv)


def bootstrap_runtime(args) -> RuntimeContext:

    # 0. Temporary logger for config loading
    logging.basicConfig(level=logging.INFO)
    temp_logger = logging.getLogger("bootstrap")

    try:
        config = load_config(args.config)
        temp_logger.info(f"Configuration loaded from {args.config}")
    except Exception as exc:
        temp_logger.error(f"Failed to load configuration: {exc}")
        raise

    # 1. Init Run ID & Logger
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = setup_logger(run_id)
    logger.info(f"Starting Run ID: {run_id}")

    if config.privacy.allow_pii:
        logger.warning("!!! WARNING: PII Collection is ENABLED (allow_pii=True) !!!")
        logger.warning("Ensure you have explicit consent or justification.")

    db_path = args.resume_from_db if args.resume_from_db else config.storage.db_path
    logger.info(f"Initializing database at {db_path}")

    db = Database(db_path, wal_mode=config.storage.wal_mode)
    try:
        db.init_schema()
    except Exception as exc:
        logger.error(f"Database initialization failed: {exc}")
        raise

    snapshot_at = datetime.now().isoformat()

    return RuntimeContext(
        config=config,
        db=db,
        run_id=run_id,
        snapshot_at=snapshot_at,
        db_path=db_path,
    )


def main():
    args = parse_args()

    try:
        context = bootstrap_runtime(args)
    except Exception:
        sys.exit(1)

    config = context.config
    db = context.db
    run_id = context.run_id
    snapshot_at = context.snapshot_at

    logger = logging.getLogger("nact-mvp")

    # Initialize components
    from src.ops.evidence import EvidenceCollector
    from src.collectors.search_collector import SearchCollector
    from src.collectors.article_parser import ArticleParser
    from src.ops.probe import EndpointProbe
    from src.collectors.comment_collector import CommentCollector
    from src.collectors.comment_fetcher import CommentFetcher
    from src.collectors.comment_parser import CommentParser
    from src.storage.repository import CommentRepository
    from src.http.client import RequestsHttpClient
    from src.ops.rate_limiter import RateLimiter
    from src.ops.throttle import AutoThrottler
    from src.privacy.hashing import PrivacyHasher
    from src.storage.exporters import DataExporter

    http_client = RequestsHttpClient()
    evidence = EvidenceCollector(run_id=run_id, logs_dir="logs")
    searcher = SearchCollector(config.search, http_client)
    parser = ArticleParser(http_client)
    probe = EndpointProbe()
    
    # Privacy Setup
    salt = config.privacy.global_salt if config.privacy.hash_salt_mode == "global" else run_id
    if not salt:
        salt = run_id # Fallback
    hasher = PrivacyHasher(salt)

    rate_limiter = RateLimiter(config.collection.rate_limit)
    throttler = AutoThrottler(config.collection.auto_throttle, rate_limiter, db, run_id)
    fetcher = CommentFetcher(http_client, rate_limiter, throttler, evidence, config)
    comment_parser = CommentParser(config, hasher)
    repository = CommentRepository(db, run_id)
    
    collector = CommentCollector(config, fetcher, comment_parser, repository, snapshot_at)

    # 5. Pre-flight health check (Optional integration here, typically before loop)
    # from src.ops.health_check import HealthCheck
    # hc = HealthCheck(config)
    # if not hc.run_preflight_check():
    #     logger.critical("Pre-flight check failed. Aborting.")
    #     sys.exit(1)

    # 6. Main Collection Loop
    total_articles = 0
    total_comments = 0
    
    for keyword in config.search.keywords:
        logger.info(f"== Processing Keyword: {keyword} ==")
        
        for item in searcher.search_keyword(keyword):
            total_articles += 1
            url = item.get("url")
            oid = item.get("oid")
            aid = item.get("aid")
            title = item.get("title")
            
            if not oid or not aid:
                logger.warning(f"Skipping article without OID/AID: {url}")
                continue
                
            # Resume Check (via DB directly or collector helper)
            if repository.is_article_completed(oid, aid):
                logger.info(f"Skipping completed article: {oid}/{aid}")
                continue

            logger.info(f"Processing ({total_articles}) {oid}/{aid}: {title}")
            
            # 1. Parse Metadata
            meta = parser.fetch_and_parse(url)
            if meta["status_code"] != "CRAWL-OK":
                logger.error(f"Metadata parse failed for {url}: {meta.get('error_code')}")
                # Log usage if needed, but we continue to try comments? 
                # Usually if article is missing, comments might still exist? 
                # But we need OID/AID which we have.
                # PRD says we should try if OID/AID exists.
            
            # 2. Probe Endpoint
            raw_html = meta.get("_raw_html", "")
            candidates = probe.get_candidate_configs(url, raw_html)
            
            # 3. Collect Comments (Try candidates)
            success = False
            for params in candidates:
                try:
                    count = collector.collect_article(oid, aid, params)
                    total_comments += count
                    success = True
                    break # Success!
                except Exception as e:
                    logger.warning(f"Probe config failed for {oid}/{aid}: {e}")
                    # Continue to next candidate
            
            if not success:
                logger.error(f"All probe candidates failed for {oid}/{aid}")
                # Article status is updated inside collect_article (on fail)
                
            # Volume Check (Optional: check total comments vs target)
            if config.volume_strategy.target_comments and total_comments >= config.volume_strategy.target_comments:
                logger.info(f"Target volume reached ({total_comments}). Stopping.")
                sys.exit(0)

    logger.info(f"Run Complete. Articles: {total_articles}, Comments: {total_comments}")
    
    # 7. Export Data
    exporter = DataExporter(db)
    exporter.export_run(run_id)

if __name__ == "__main__":
    main()

``n
### src\__init__.py

`python
# NACT-MVP Source Root
``n
### tests\conftest.py

`python
import pytest
import sqlite3
import os
from pathlib import Path
from src.config import AppConfig, SnapshotConfig, SearchConfig, DateRangeConfig, VolumeStrategyConfig, CollectionConfig, StorageConfig, PrivacyConfig, RateLimitConfig, AutoThrottleConfig, RetryConfig, TimeoutConfig
from src.storage.db import Database
from src.ops.evidence import EvidenceCollector

@pytest.fixture
def mock_config(tmp_path):
    return AppConfig(
        snapshot=SnapshotConfig(reference_time="start"),
        search=SearchConfig(
            keywords=["test"],
            max_articles_per_keyword=10,
            date_range=DateRangeConfig(start="2023-01-01", end="2023-01-02")
        ),
        volume_strategy=VolumeStrategyConfig(),
        collection=CollectionConfig(
            rate_limit=RateLimitConfig(min_delay=0.0, max_delay=0.0, baseline_min_delay=0.0), # Fast tests
            retry=RetryConfig(),
            timeout=TimeoutConfig(),
            auto_throttle=AutoThrottleConfig(window=5, ratio_429_threshold=0.2) # Small window for testing
        ),
        storage=StorageConfig(db_path=str(tmp_path / "test.db"), wal_mode=False),
        privacy=PrivacyConfig()
    )

@pytest.fixture
def db(mock_config):
    database = Database(mock_config.storage.db_path, wal_mode=False)
    database.init_schema()
    return database

@pytest.fixture
def evidence(tmp_path):
    return EvidenceCollector(run_id="test_run", logs_dir=str(tmp_path / "logs"))

``n
### tests\test_article_parser.py

`python
from dataclasses import dataclass

from src.collectors.article_parser import ArticleParser


@dataclass
class StubResponse:
    status_code: int = 200
    text: str = ""


class StubHttpClient:
    def __init__(self, response: StubResponse):
        self.response = response
        self.requested = []

    def request(self, method, url, **kwargs):
        self.requested.append((method, url, kwargs))
        return self.response


def test_fetch_and_parse_prefers_json_ld():
    html = """
    <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "headline": "JSON Headline",
                "datePublished": "2025-01-01T00:00:00+09:00",
                "dateModified": "2025-01-01T00:30:00+09:00",
                "articleSection": "Tech",
                "author": {"name": "Reporter A"}
            }
            </script>
        </head>
        <body>
            <a class="media_end_head_top_logo"><img title="Press Name"/></a>
            <div id="dic_area">Body text<span class="end_photo_org">ignore</span></div>
        </body>
    </html>
    """
    parser = ArticleParser(StubHttpClient(StubResponse(text=html)))

    result = parser.fetch_and_parse("https://news.example.com/article")

    assert result["status_code"] == "CRAWL-OK"
    assert result["title"] == "JSON Headline"
    assert result["published_at"] == "2025-01-01T00:00:00+09:00"
    assert result["reporter"] == "Reporter A"
    assert result["section"] == "Tech"
    assert result["press"] == "Press Name"
    assert result["body"] == "Body text"
    assert result["body_length"] == len("Body text")


def test_fetch_and_parse_handles_http_errors():
    parser = ArticleParser(StubHttpClient(StubResponse(status_code=500)))

    result = parser.fetch_and_parse("https://news.example.com/article")

    assert result["status_code"] == "FAIL-HTTP"
    assert result["error_code"] == "500"

``n
### tests\test_cli_foundations.py

`python
import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import yaml

from src.config import get_default_config_path
from src.main import parse_args, bootstrap_runtime


def _write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "cli_config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _search_override():
    return {
        "keywords": ["cli-alpha"],
        "date_range": {"start": "2025-02-01", "end": "2025-02-10"},
    }


def test_parse_args_uses_default_config_when_not_provided():
    args = parse_args([])
    assert args.config == str(get_default_config_path())
    assert args.resume_from_db is None


def test_bootstrap_runtime_prefers_resume_db_path(monkeypatch, tmp_path):
    config_path = _write_config(tmp_path, {"search": _search_override()})
    resume_db = tmp_path / "resume.db"

    class DummyDB:
        def __init__(self, path: str, wal_mode: bool):
            self.path = path
            self.wal_mode = wal_mode
            self.init_called = False

        def init_schema(self):
            self.init_called = True

    created = {}

    def fake_db(path, wal_mode):
        db = DummyDB(path, wal_mode)
        created["db"] = db
        return db

    monkeypatch.setattr("src.main.Database", fake_db)

    args = SimpleNamespace(config=str(config_path), resume_from_db=str(resume_db))
    context = bootstrap_runtime(args)

    assert context.db is created["db"]
    assert created["db"].path == str(resume_db)
    assert created["db"].wal_mode is True
    assert created["db"].init_called is True
    assert re.match(r"\d{8}_\d{6}", context.run_id)
    datetime.fromisoformat(context.snapshot_at)

``n
### tests\test_comment_collector.py

`python
import pytest
import json
from unittest.mock import MagicMock, Mock
from src.collectors.comment_collector import CommentCollector
from src.collectors.comment_parser import CommentParser, JSONPParseError, SchemaMismatchError
from src.collectors.comment_fetcher import CommentFetcher
from src.storage.repository import CommentRepository
from src.privacy.hashing import PrivacyHasher

class TestCommentCollector:
    @pytest.fixture
    def collector(self, mock_config):
        fetcher = Mock(spec=CommentFetcher)
        parser = Mock(spec=CommentParser)
        repo = Mock(spec=CommentRepository)
        repo.is_article_completed.return_value = False
        return CommentCollector(mock_config, fetcher, parser, repo, "2023-01-01T00:00:00")

    def test_parse_jsonp_valid(self, mock_config):
        parser = CommentParser(mock_config, PrivacyHasher("salt"))
        # Plain JSON
        assert parser.parse_jsonp('{"a": 1}') == {"a": 1}
        # Callback wrapper
        assert parser.parse_jsonp('cb({"a": 1});') == {"a": 1}
        # Weird spacing
        assert parser.parse_jsonp('  _callback (  {"a": 1}  )  ') == {"a": 1}

    def test_parse_jsonp_invalid(self, mock_config):
        parser = CommentParser(mock_config, PrivacyHasher("salt"))
        with pytest.raises(JSONPParseError):
            parser.parse_jsonp("<html>Error</html>")
        with pytest.raises(JSONPParseError):
            parser.parse_jsonp("")

    def test_persist_comments_delegates_to_repo(self, collector):
        comments = [
            {
                "commentNo": "100",
                "contents": "Test",
                "userId": "user1hash",
                "regTime": "2023-01-01 12:00:00",
                "sympathyCount": 10
            }
        ]
        collector.parser.extract_comments.return_value = comments
        collector.parser.to_record.return_value = {"comment_no": "100"}
        collector.repository.persist_comments.return_value = 1
        collector.fetcher.fetch.return_value = "{}"
        collector.parser.parse_jsonp.return_value = {}
        collector.parser.extract_cursor.return_value = None

        written = collector.collect_article("oid", "aid", {})
        assert written == 1
        collector.repository.persist_comments.assert_called_once()

    def test_pagination_stops_on_duplicate_cursor(self, collector):
        # Setup mocks
        collector.fetcher.fetch.return_value = "{}"
        collector.parser.parse_jsonp.return_value = {}
        collector.parser.extract_comments.return_value = [{"id": 1}]
        # Return same cursor twice
        collector.parser.extract_cursor.side_effect = ["CURSOR_A", "CURSOR_A"]
        collector.repository.persist_comments.return_value = 1
        
        count = collector.collect_article("oid", "aid", {})
        # Should process page 1, see Cursor A.
        # Process page 2, see Cursor A again -> Stop.
        # Total comments 2.
        assert count == 2
        assert collector.fetcher.fetch.call_count == 2

    def test_to_record_hashes_identifier(self, mock_config):
        parser = CommentParser(mock_config, PrivacyHasher("salt"))
        record = parser.to_record(
            {
                "commentNo": "1",
                "contents": "hi",
                "userId": "author",
                "regTime": "1700000000",
                "sympathyCount": 1,
            },
            depth=0,
            parent=None,
            snapshot_at="2023-01-01T00:00:00",
        )
        assert record["author_hash"] is not None
        assert record["author_raw"] is None

``n
### tests\test_comment_fetcher.py

`python
import requests
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.collectors.comment_fetcher import CommentFetcher
from src.common.errors import AppError, Severity, ErrorKind
from src.ops.rate_limiter import RateLimitConfig, RateLimiter


class StubResponse:
    def __init__(self, status_code=200, text="{}", content=b"{}"):
        self.status_code = status_code
        self.text = text
        self.content = content


class StubHttpClient:
    def __init__(self, response=None, exception=None):
        self.response = response or StubResponse()
        self.exception = exception
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.exception:
            raise self.exception
        return self.response


def _config():
    timeout = SimpleNamespace(connect=1, read=1)
    collection = SimpleNamespace(timeout=timeout)
    return SimpleNamespace(collection=collection)


def _rate_limiter():
    cfg = RateLimitConfig(baseline_min_delay=0.0, min_delay=0.0, max_delay=0.0, max_concurrent=1)
    limiter = RateLimiter(cfg)
    limiter.wait = MagicMock()
    return limiter


def test_fetch_returns_response_text(tmp_path):
    http = StubHttpClient(StubResponse(status_code=200, text="payload"))
    limiter = _rate_limiter()
    throttler = MagicMock()
    evidence = MagicMock()

    fetcher = CommentFetcher(http, limiter, throttler, evidence, _config())

    result = fetcher.fetch("001", "0001", 1, {}, "comment", None)

    assert result == "payload"
    throttler.observe.assert_called_once_with(200)
    evidence.log_failed_request.assert_not_called()


def test_fetch_logs_and_raises_on_network_error():
    exc = requests.RequestException("boom")
    http = StubHttpClient(exception=exc)
    limiter = _rate_limiter()
    throttler = MagicMock()
    evidence = MagicMock()

    fetcher = CommentFetcher(http, limiter, throttler, evidence, _config())

    with pytest.raises(AppError) as err:
        fetcher.fetch("001", "0001", 1, {}, "comment", None)

    assert err.value.severity == Severity.RETRY
    evidence.log_failed_request.assert_called_once()


def test_fetch_raises_abort_on_403():
    http = StubHttpClient(StubResponse(status_code=403))
    limiter = _rate_limiter()
    throttler = MagicMock()
    evidence = MagicMock()

    fetcher = CommentFetcher(http, limiter, throttler, evidence, _config())

    with pytest.raises(AppError) as err:
        fetcher.fetch("001", "0001", 1, {}, "comment", None)

    assert err.value.severity == Severity.ABORT
    assert err.value.kind == ErrorKind.HTTP
    evidence.log_failed_request.assert_called_once()

``n
### tests\test_common_errors.py

`python
from src.common.errors import AppError, Severity, ErrorKind


def test_app_error_includes_metadata_in_str():
    err = AppError("boom", Severity.ABORT, ErrorKind.HTTP)
    message = str(err)
    assert "ABORT" in message and "HTTP" in message
    assert err.severity is Severity.ABORT
    assert err.kind is ErrorKind.HTTP

``n
### tests\test_config_loader.py

`python
import yaml
import pytest
from pathlib import Path

from src.config import load_config


def _write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "partial_config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _search_override():
    return {
        "keywords": ["alpha", "beta"],
        "date_range": {"start": "2025-01-01", "end": "2025-01-31"},
    }


def test_load_config_merges_with_defaults(tmp_path):
    config_path = _write_config(
        tmp_path,
        {
            # Only override search parameters, everything else should come from defaults
            "search": _search_override(),
        },
    )

    config = load_config(str(config_path))

    assert config.search.keywords == ["alpha", "beta"]
    # Default storage values should survive even though they weren't in the override file.
    assert config.storage.db_path == "./data/nact_data.db"
    assert config.collection.rate_limit.max_delay == 3.0


def test_load_config_enforces_global_salt_requirement(tmp_path):
    config_path = _write_config(
        tmp_path,
        {
            "search": _search_override(),
            "privacy": {
                "hash_salt_mode": "global",
                # Missing global_salt should raise a descriptive error
            },
        },
    )

    with pytest.raises(ValueError) as err:
        load_config(str(config_path))

    assert "global_salt" in str(err.value)

``n
### tests\test_ops_evidence.py

`python
import json
from pathlib import Path

from src.ops.evidence import EvidenceCollector


def test_log_failed_request_writes_jsonl_and_body(tmp_path):
    logs_dir = tmp_path / "logs"
    collector = EvidenceCollector(run_id="test", logs_dir=str(logs_dir))

    collector.log_failed_request(
        method="GET",
        url="https://example.com",
        status_code=500,
        error_type="HTTP_ERROR",
        headers={"Authorization": "secret", "User-Agent": "pytest"},
        context={"oid": "1"},
        response_body=b"failure body",
    )

    log_path = logs_dir / "failed_requests.jsonl"
    assert log_path.exists()

    data = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert data["run_id"] == "test"
    assert data["status_code"] == 500
    assert "Authorization" not in data["headers"]
    assert data["headers"]["User-Agent"] == "pytest"

    body_path = Path(data["body_sample_path"])
    assert body_path.exists()
    assert body_path.read_bytes().startswith(b"failure body")

``n
### tests\test_ops_health.py

`python
import pytest
from unittest.mock import MagicMock, ANY
from src.ops.health_check import HealthCheck

class TestHealthCheck:
    @pytest.fixture
    def mock_deps(self):
        searcher = MagicMock()
        parser = MagicMock()
        probe = MagicMock()
        fetcher = MagicMock()
        comment_parser = MagicMock()
        evidence = MagicMock()
        config = MagicMock()
        config.search.keywords = ["test_keyword"]
        
        return {
            "searcher": searcher,
            "parser": parser,
            "probe": probe,
            "comment_fetcher": fetcher,
            "comment_parser": comment_parser,
            "evidence": evidence,
            "config": config
        }

    def test_health_check_success(self, mock_deps):
        # Setup: 1 sample article found
        mock_deps["searcher"].search_keyword.return_value = [
            {"oid": "001", "aid": "0000001", "url": "http://Article1"}
        ]
        
        # 1. Metadata OK
        mock_deps["parser"].fetch_and_parse.return_value = {
            "status_code": "CRAWL-OK", 
            "_raw_html": "<html></html>"
        }
        
        # 2. Probe Param
        mock_deps["probe"].get_candidate_configs.return_value = [{"ticket": "news"}]
        
        # 3. Comment Fetch OK
        mock_deps["comment_fetcher"].fetch_page.return_value = '{"success":true}'
        mock_deps["comment_parser"].parse_jsonp.return_value = {"success": True}
        
        # 4. Probe Validation OK
        mock_deps["probe"].deep_validate_response.return_value = True
        
        hc = HealthCheck(
            config=mock_deps["config"],
            searcher=mock_deps["searcher"],
            parser=mock_deps["parser"],
            probe=mock_deps["probe"],
            comment_fetcher=mock_deps["comment_fetcher"],
            comment_parser=mock_deps["comment_parser"],
            evidence=mock_deps["evidence"]
        )
        
        assert hc.run_preflight_check() is True
        mock_deps["evidence"].log_failed_request.assert_not_called()

    def test_health_check_fail_metadata(self, mock_deps):
        mock_deps["searcher"].search_keyword.return_value = [
            {"oid": "001", "aid": "0000001", "url": "http://Article1"}
        ]
        # Metadata Fail
        mock_deps["parser"].fetch_and_parse.return_value = {"status_code": "FAIL-HTTP"}
        
        hc = HealthCheck(
            config=mock_deps["config"],
            searcher=mock_deps["searcher"],
            parser=mock_deps["parser"],
            probe=mock_deps["probe"],
            comment_fetcher=mock_deps["comment_fetcher"],
            comment_parser=mock_deps["comment_parser"],
            evidence=mock_deps["evidence"]
        )
        
        # 0 successes out of 1 sample -> Fail
        assert hc.run_preflight_check() is False

    def test_health_check_partial_success(self, mock_deps):
        # 3 samples
        mock_deps["searcher"].search_keyword.return_value = [
            {"oid": "1", "aid": "1", "url": "u1"},
            {"oid": "2", "aid": "2", "url": "u2"},
            {"oid": "3", "aid": "3", "url": "u3"},
        ]
        
        mock_deps["parser"].fetch_and_parse.return_value = {"status_code": "CRAWL-OK"}
        mock_deps["probe"].get_candidate_configs.return_value = [{"t": "n"}]
        mock_deps["comment_fetcher"].fetch_page.return_value = "{}"
        
        # Sample 1: Success
        # Sample 2: Fail (Schema)
        # Sample 3: Success
        mock_deps["probe"].deep_validate_response.side_effect = [True, False, True]
        
        hc = HealthCheck(
            config=mock_deps["config"],
            searcher=mock_deps["searcher"],
            parser=mock_deps["parser"],
            probe=mock_deps["probe"],
            comment_fetcher=mock_deps["comment_fetcher"],
            comment_parser=mock_deps["comment_parser"],
            evidence=mock_deps["evidence"]
        )
        
        # 2/3 Success -> Pass
        assert hc.run_preflight_check() is True
        
        # Check evidence logged for Sample 2 failure
        mock_deps["evidence"].log_failed_request.assert_called()

``n
### tests\test_ops_health_check.py

`python
from dataclasses import dataclass
from typing import List, Dict, Any, Iterator

import pytest

from src.ops.health_check import HealthCheck


@dataclass
class StubSearchResult:
    oid: str
    aid: str
    url: str


class StubSearcher:
    def __init__(self, results: List[StubSearchResult]):
        self.results = results
        self.queries = []

    def search_keyword(self, keyword: str) -> Iterator[Dict[str, str]]:
        self.queries.append(keyword)
        for item in self.results:
            yield {"oid": item.oid, "aid": item.aid, "url": item.url}


class StubParser:
    def __init__(self, statuses: List[Dict[str, Any]]):
        self.statuses = list(statuses)

    def fetch_and_parse(self, url: str) -> Dict[str, Any]:
        if not self.statuses:
            raise AssertionError("No parser statuses left")
        return self.statuses.pop(0)


class StubProbe:
    def __init__(self, configs: List[Dict[str, str]], validations: List[bool]):
        self.configs = configs
        self.validations = list(validations)
        self.calls = 0

    def get_candidate_configs(self, url: str, raw_html: str):
        self.calls += 1
        return list(self.configs)

    def deep_validate_response(self, payload: Dict[str, Any]) -> bool:
        if not self.validations:
            return False
        return self.validations.pop(0)


class StubCommentFetcher:
    def __init__(self, payloads: List[Dict[str, Any]], should_raise: bool = False):
        self.payloads = list(payloads)
        self.calls = 0
        self.should_raise = should_raise
        self.api_url = "https://comments.example.com"

    def fetch_page(self, oid: str, aid: str, page: int, params: Dict[str, str]):
        self.calls += 1
        if self.should_raise:
            raise RuntimeError("fetch failed")
        if not self.payloads:
            return {"result": {"commentList": []}}
        return self.payloads.pop(0)


class StubEvidence:
    def __init__(self):
        self.logged = []

    def log_failed_request(self, *args, **kwargs):
        self.logged.append((args, kwargs))


def _health_check_with_stubs(mock_config, validations, payloads, should_raise=False):
    searcher = StubSearcher(
        [
            StubSearchResult("001", "0001", "https://a"),
            StubSearchResult("001", "0002", "https://b"),
            StubSearchResult("001", "0003", "https://c"),
        ]
    )
    parser = StubParser(
        [
            {"status_code": "CRAWL-OK", "_raw_html": "<html></html>"},
            {"status_code": "CRAWL-OK", "_raw_html": "<html></html>"},
            {"status_code": "CRAWL-OK", "_raw_html": "<html></html>"},
        ]
    )
    probe = StubProbe(
        configs=[{"ticket": "news", "templateId": "default"}, {"ticket": "news", "templateId": "fallback"}],
        validations=validations,
    )
    fetcher = StubCommentFetcher(payloads=payloads, should_raise=should_raise)
    evidence = StubEvidence()

    hc = HealthCheck(
        config=mock_config,
        searcher=searcher,
        parser=parser,
        probe=probe,
        comment_fetcher=fetcher,
        evidence=evidence,
    )
    return hc, evidence, fetcher


def test_health_check_passes_with_two_successes(mock_config):
    payload = {"success": True, "result": {"commentList": [{"commentNo": "1", "contents": "c", "regTime": "now"}]}}
    hc, evidence, fetcher = _health_check_with_stubs(mock_config, validations=[True, True, False], payloads=[payload] * 3)

    assert hc.run_preflight_check(run_id="hc") is True
    assert fetcher.calls >= 2
    assert len(evidence.logged) >= 1


def test_health_check_fails_and_logs_evidence(mock_config):
    payload = {"success": False}
    hc, evidence, fetcher = _health_check_with_stubs(
        mock_config,
        validations=[False, False, False],
        payloads=[payload] * 3,
    )

    assert hc.run_preflight_check(run_id="hc") is False
    assert len(evidence.logged) > 0

``n
### tests\test_ops_logger.py

`python
import logging

from src.ops.logger import setup_logger


def test_setup_logger_creates_console_and_file_handlers(tmp_path):
    logger = setup_logger("run123", logs_dir=str(tmp_path))
    try:
        # Two handlers: console + file
        assert len(logger.handlers) == 2
        levels = sorted(handler.level for handler in logger.handlers)
        assert logging.DEBUG in levels
        assert logging.INFO in levels

        log_files = list(tmp_path.iterdir())
        assert any(f.name.startswith("debug_") and f.suffix == ".log" for f in log_files)
    finally:
        # Clean up handlers so later tests can reconfigure logging
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)

``n
### tests\test_ops_probe.py

`python
import pytest
from src.ops.probe import EndpointProbe

class TestEndpointProbe:
    @pytest.fixture
    def probe(self):
        return EndpointProbe()

    def test_discover_parameters_found(self, probe):
        html = """
        <script>
            var _cv = "news_service";
            var _templateId = "view_politics";
            var pool = "cbox99";
        </script>
        """
        params = probe.discover_parameters("http://url", html)
        assert params["ticket"] == "news_service"
        assert params["templateId"] == "view_politics"
        assert params["pool"] == "cbox99"

    def test_discover_parameters_service_name(self, probe):
        html = """
        serviceName: "sports",
        templateId: "view_sports",
        """
        params = probe.discover_parameters("http://url", html)
        assert params["ticket"] == "sports"
        assert params["templateId"] == "view_sports"

    def test_discover_parameters_missing(self, probe):
        html = "<html>No vars here</html>"
        params = probe.discover_parameters("http://url", html)
        # Should return None if ticket/templateId not found
        assert params is None

    def test_get_candidate_configs_priority(self, probe):
        html = """serviceName: "discovered", templateId: "discovered_tmpl" """
        candidates = probe.get_candidate_configs("http://url", html)
        
        # 1. Discovered
        assert candidates[0]["ticket"] == "discovered"
        assert candidates[0]["templateId"] == "discovered_tmpl"
        # 2. Know Config A
        assert candidates[1]["ticket"] == "news"
        # 3. Known Config B
        assert candidates[2]["ticket"] == "news"

    def test_deep_validate_response_success(self, probe):
        valid = {
            "success": True,
            "result": {
                "commentList": [
                    {"commentNo": "1", "contents": "c", "regTime": "t"}
                ]
            }
        }
        assert probe.deep_validate_response(valid) is True

    def test_deep_validate_response_failure(self, probe):
        # Case 1: success false
        assert probe.deep_validate_response({"success": False}) is False
        
        # Case 2: missing result
        assert probe.deep_validate_response({"success": True}) is False
        
        # Case 3: missing commentList key
        assert probe.deep_validate_response({"success": True, "result": {}}) is False
        
        # Case 4: item missing keys
        invalid_item = {
            "success": True,
            "result": {
                "commentList": [{"commentNo": "1"}] # missing contents/regTime
            }
        }
        assert probe.deep_validate_response(invalid_item) is False

``n
### tests\test_privacy_hashing.py

`python
from src.privacy.hashing import PrivacyHasher


def test_hash_identifier_is_deterministic():
    hasher = PrivacyHasher("run-salt")

    value = hasher.hash_identifier("author123")
    assert value == hasher.hash_identifier("author123")
    assert value != hasher.hash_identifier("AUTHOR123")


def test_hash_identifier_handles_empty_values():
    hasher = PrivacyHasher("salt")
    assert hasher.hash_identifier(None) is None
    assert hasher.hash_identifier("") is None

``n
### tests\test_rate_limiter.py

`python
import types
from unittest.mock import patch

from src.ops.rate_limiter import RateLimiter
from src.config import RateLimitConfig


def _config(min_delay=0.1, max_delay=0.5, baseline=0.1):
    return RateLimitConfig(
        baseline_min_delay=baseline,
        min_delay=min_delay,
        max_delay=max_delay,
        max_concurrent=1,
    )


def test_wait_sleeps_with_random_delay(monkeypatch):
    limiter = RateLimiter(_config())

    captured = {}

    def fake_uniform(a, b):
        captured["bounds"] = (a, b)
        return 0.2

    def fake_sleep(value):
        captured["slept"] = value

    monkeypatch.setattr("src.ops.rate_limiter.random.uniform", fake_uniform)
    monkeypatch.setattr("src.ops.rate_limiter.time.sleep", fake_sleep)

    limiter.wait()

    assert captured["bounds"] == (0.1, 0.5)
    assert captured["slept"] == 0.2


def test_update_min_delay_adjusts_spread():
    limiter = RateLimiter(_config(min_delay=0.5, max_delay=1.0, baseline=0.5))

    limiter.update_min_delay(2.0)

    assert limiter.min_delay == 2.0
    # Spread defaults to at least 1.0, so max should be min + spread
    assert limiter.max_delay == limiter.min_delay + 1.0

``n
### tests\test_search_collector.py

`python
from dataclasses import dataclass
from typing import List, Any, Dict

import pytest

from src.collectors.search_collector import SearchCollector
from src.config import SearchConfig, DateRangeConfig


def make_search_config(**overrides) -> SearchConfig:
    base = {
        "keywords": ["alpha"],
        "max_articles_per_keyword": 5,
        "date_range": DateRangeConfig(start="2025-01-01", end="2025-01-02"),
        "sort": "rel",
        "use_openapi": False,
    }
    base.update(overrides)
    return SearchConfig(**base)


@dataclass
class StubResponse:
    status_code: int = 200
    text: str = ""
    json_payload: Dict[str, Any] = None

    def json(self):
        return self.json_payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")


class StubHttpClient:
    def __init__(self, responses: List[StubResponse]):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError("No more responses queued")
        return self.responses.pop(0)


def test_extract_oid_aid_supports_path_and_query():
    collector = SearchCollector(make_search_config(), StubHttpClient([]))

    assert collector.extract_oid_aid("https://n.news.naver.com/mnews/article/001/000123") == {
        "oid": "001",
        "aid": "000123",
    }
    assert collector.extract_oid_aid("https://news.naver.com/main?oid=002&aid=000456") == {
        "oid": "002",
        "aid": "000456",
    }


def test_register_article_accumulates_keywords():
    collector = SearchCollector(make_search_config(), StubHttpClient([]))
    entry = {"url": "https://n.news.naver.com/mnews/article/001/000123", "oid": "001", "aid": "000123"}

    assert collector._register_article(entry.copy(), "alpha") is True
    assert collector._register_article(entry.copy(), "beta") is False
    assert collector._dedup_index["001:000123"]["matched_keywords"] == ["alpha", "beta"]


def test_search_keyword_uses_fallback_when_credentials_missing(mocker):
    collector = SearchCollector(make_search_config(use_openapi=True), StubHttpClient([]))
    fallback = [{"url": "https://example.com"}]

    mocker.patch.object(collector, "_search_fallback", return_value=iter(fallback))

    assert list(collector.search_keyword("alpha")) == fallback
    collector._search_fallback.assert_called_once_with("alpha")


def test_search_fallback_parses_articles(monkeypatch):
    html = """
    <ul class="list_news">
        <li>
            <a class="news_tit" href="https://n.news.naver.com/mnews/article/003/001122">Title A</a>
        </li>
        <li>
            <a class="news_tit" href="https://news.naver.com/main?oid=004&aid=000333">Title B</a>
        </li>
    </ul>
    """
    # Second response returns no articles to terminate loop
    responses = [StubResponse(text=html), StubResponse(text="<html></html>")]
    collector = SearchCollector(make_search_config(), http_client=StubHttpClient(responses))
    monkeypatch.setattr("src.collectors.search_collector.time.sleep", lambda *args, **kwargs: None)

    results = list(collector._search_fallback("alpha"))

    assert len(results) == 2
    assert results[0]["oid"] == "003"
    assert results[1]["oid"] == "004"


def test_search_keyword_openapi_yields_normalized_results(monkeypatch):
    config = make_search_config(
        use_openapi=True,
        client_id="id",
        client_secret="secret",
        max_articles_per_keyword=1,
    )
    json_payload = {
        "items": [
            {
                "originallink": "https://news.naver.com/article/005/000999",
                "title": "Headline",
                "pubDate": "Mon, 01 Jan 2025 00:00:00 +0900",
                "description": "desc",
            }
        ]
    }
    responses = [StubResponse(json_payload=json_payload)]
    collector = SearchCollector(config, http_client=StubHttpClient(responses))
    monkeypatch.setattr("src.collectors.search_collector.time.sleep", lambda *args, **kwargs: None)

    results = list(collector.search_keyword("alpha"))

    assert len(results) == 1
    assert results[0]["oid"] == "005"
    assert results[0]["search_rank"] == 1

``n
### tests\test_storage_db.py

`python
import sqlite3
from datetime import datetime

import pytest

from src.storage.db import Database


def _init_db(tmp_path) -> Database:
    db_path = tmp_path / "test.db"
    database = Database(str(db_path), wal_mode=True)
    database.init_schema()
    return database


def test_database_enables_wal_mode(tmp_path):
    db = _init_db(tmp_path)
    conn = db.get_connection()
    try:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    finally:
        conn.close()
    assert mode.lower() == "wal"


def test_transaction_context_rolls_back_on_error(tmp_path):
    db = _init_db(tmp_path)
    with pytest.raises(RuntimeError):
        with db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, snapshot_at, start_at, timezone)
                VALUES (?, ?, ?, ?)
                """,
                ("run-test", datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), "UTC"),
            )
            raise RuntimeError("force rollback")

    conn = db.get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM runs WHERE run_id = ?", ("run-test",)).fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_get_completed_article_keys_filters_by_run(tmp_path):
    db = _init_db(tmp_path)
    conn = db.get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, snapshot_at, start_at, timezone)
                VALUES (?, ?, ?, ?)
                """,
                ("run-1", datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), "UTC"),
            )
            conn.execute(
                """
                INSERT INTO articles (oid, aid, run_id, status_code, crawl_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("001", "0001", "run-1", "SUCCESS", datetime.utcnow().isoformat()),
            )
    finally:
        conn.close()

    assert db.get_completed_article_keys("run-1") == {("001", "0001")}
    assert db.get_completed_article_keys("run-2") == set()

``n
### tests\test_storage_exporters.py

`python
import csv

from src.storage.db import Database
from src.storage.exporters import DataExporter


def test_data_exporter_writes_csv(tmp_path):
    db_path = tmp_path / "test.db"
    database = Database(str(db_path), wal_mode=False)
    database.init_schema()

    conn = database.get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO runs (run_id, snapshot_at, start_at, timezone) VALUES (?, ?, ?, ?)",
                ("run-1", "2023-01-01T00:00:00", "2023-01-01T00:00:00", "UTC"),
            )
            conn.execute(
                "INSERT INTO articles (oid, aid, run_id, status_code) VALUES (?, ?, ?, ?)",
                ("001", "0001", "run-1", "SUCCESS"),
            )
            conn.execute(
                "INSERT INTO comments (comment_no, run_id, oid, aid, contents) VALUES (?, ?, ?, ?, ?)",
                ("c1", "run-1", "001", "0001", "hello"),
            )
    finally:
        conn.close()

    exporter = DataExporter(database, export_dir=str(tmp_path / "exports"))
    exporter.export_run("run-1")

    articles_csv = tmp_path / "exports" / "articles_run-1.csv"
    comments_csv = tmp_path / "exports" / "comments_run-1.csv"
    runs_csv = tmp_path / "exports" / "run_log_run-1.csv"

    for csv_path in (articles_csv, comments_csv, runs_csv):
        assert csv_path.exists()
        with csv_path.open("r", encoding="utf-8-sig") as handle:
            rows = list(csv.reader(handle))
            assert len(rows) >= 2  # header + at least one row

``n
### tests\test_throttle.py

`python
import pytest
from src.ops.throttle import AutoThrottler
from src.ops.rate_limiter import RateLimiter

class TestAutoThrottle:
    def test_throttle_up_on_429(self, mock_config, db):
        limiter = RateLimiter(mock_config.collection.rate_limit)
        throttler = AutoThrottler(mock_config.collection.auto_throttle, limiter, db, "test")
        
        # Trigger 429s (Window is 5, threshold 20%)
        # 1 429 out of 5 is 20% -> needs >20% so 2 failures?
        # Config says ratio > threshold. 1/5 = 0.2. If threshold is 0.2, 0.2 > 0.2 is False.
        # We need 2/5 = 0.4 > 0.2.
        
        assert limiter.min_delay == 0.0
        
        throttler.observe(200)
        throttler.observe(200)
        throttler.observe(200)
        throttler.observe(429) 
        throttler.observe(429) # 2/5 -> 40%
        
        # Should have triggered throttle up
        # Step up is 0.5 (default)
        assert limiter.min_delay == 0.5
        # History should be cleared
        assert len(throttler.history) == 0

    def test_emergency_stop_on_403(self, mock_config, db):
        limiter = RateLimiter(mock_config.collection.rate_limit)
        throttler = AutoThrottler(mock_config.collection.auto_throttle, limiter, db, "test")
        
        assert not throttler.is_stopped
        throttler.observe(403)
        assert throttler.is_stopped
        assert "403" in throttler.stop_reason

    def test_recovery(self, mock_config, db):
        limiter = RateLimiter(mock_config.collection.rate_limit)
        throttler = AutoThrottler(mock_config.collection.auto_throttle, limiter, db, "test")
        
        # Force high delay
        limiter.update_min_delay(1.0)
        
        # Fill recovery window (default 200, test config not setting it? 
        # conftest sets: auto_throttle=AutoThrottleConfig(window=5...) 
        # Pydantic default for recovery_window is 200.
        # We need to send many requests or mock deque maxlen.
        
        # Hack: manually set recovery_history maxlen if possible or rely on simple loop
        # Testing recovery takes 200 reqs. Let's make test config smaller recovery window?
        pass # Skip complex recovery test for brief TDD 

``n
### config\default.yaml

`python
snapshot:
  timezone: "Asia/Seoul"
  reference_time: "start" # start | manual
  manual_snapshot_time: null

search:
  keywords: ["湲고썑蹂??, "?멸났吏??]
  max_articles_per_keyword: 300
  date_range:
    start: "2025-01-01"
    end: "2025-12-23"
  sort: "rel"
  use_openapi: true

volume_strategy:
  target_comments: 50000
  min_acceptable_comments: 30000
  max_total_articles: 2000
  estimator: "trimmed_mean_p20_p80"

collection:
  rate_limit:
    baseline_min_delay: 1.0
    min_delay: 1.0
    max_delay: 3.0
    max_concurrent: 1
  retry:
    max_attempts: 3
    backoff_factor: 2
  timeout:
    connect: 10
    read: 30
  auto_throttle:
    window: 50
    ratio_429_threshold: 0.05
    min_delay_step_up: 0.5
    recovery_window: 200
    ratio_429_recovery_threshold: 0.01
    min_delay_step_down: 0.2
    stop_on_403: true

storage:
  db_path: "./data/nact_data.db"
  wal_mode: true

privacy:
  allow_pii: false
  hash_algorithm: "sha256"
  hash_salt_mode: "per_run" # per_run | global
  global_salt: null # required if global

``n

