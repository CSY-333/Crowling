import pytest
import sqlite3
import os
from pathlib import Path
from src.config import (
    AppConfig,
    SnapshotConfig,
    SearchConfig,
    DateRangeConfig,
    VolumeStrategyConfig,
    CollectionConfig,
    StorageConfig,
    PrivacyConfig,
    RateLimitConfig,
    AutoThrottleConfig,
    RetryConfig,
    TimeoutConfig,
    CommentStatsConfig,
)
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
            auto_throttle=AutoThrottleConfig(window=5, ratio_429_threshold=0.2), # Small window for testing
            comment_stats=CommentStatsConfig(),
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
