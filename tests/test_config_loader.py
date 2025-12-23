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
