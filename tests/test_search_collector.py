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
