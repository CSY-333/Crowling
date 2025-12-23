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
