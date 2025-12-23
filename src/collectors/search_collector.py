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
