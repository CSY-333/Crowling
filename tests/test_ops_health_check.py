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
            {"status": "CRAWL-OK", "_raw_html": "<html></html>"},
            {"status": "CRAWL-OK", "_raw_html": "<html></html>"},
            {"status": "CRAWL-OK", "_raw_html": "<html></html>"},
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
