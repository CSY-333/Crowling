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
