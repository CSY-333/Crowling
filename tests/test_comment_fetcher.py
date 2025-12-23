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
