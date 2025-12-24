import yaml
from copy import deepcopy
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ValidationError, root_validator

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

class CommentStatsConfig(BaseModel):
    enabled: bool = True
    min_comments: int = 100
    stats_endpoint: str = "https://apis.naver.com/commentBox/cbox/web_naver_statistics_jsonp.json"

class CollectionConfig(BaseModel):
    rate_limit: RateLimitConfig
    retry: RetryConfig
    timeout: TimeoutConfig
    auto_throttle: AutoThrottleConfig
    comment_stats: CommentStatsConfig = CommentStatsConfig()

class StorageConfig(BaseModel):
    db_path: str = "./data/nact_data.db"
    wal_mode: bool = True

class PrivacyConfig(BaseModel):
    allow_pii: bool = False
    hash_algorithm: str = "sha256"
    mode: Literal["ephemeral", "longitudinal"] = "ephemeral"
    fixed_salt: Optional[str] = None

    @root_validator(pre=True)
    def _migrate_legacy_fields(cls, values):
        hash_salt_mode = values.pop("hash_salt_mode", None)
        if "mode" not in values and hash_salt_mode:
            values["mode"] = "longitudinal" if hash_salt_mode == "global" else "ephemeral"

        global_salt = values.pop("global_salt", None)
        if "fixed_salt" not in values and global_salt:
            values["fixed_salt"] = global_salt
        return values

    @root_validator
    def _validate_longitudinal_mode(cls, values):
        mode = values.get("mode", "ephemeral")
        if mode == "longitudinal" and not values.get("fixed_salt"):
            raise ValueError("privacy.fixed_salt is required when privacy.mode='longitudinal'.")
        return values

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
        return config
    except ValidationError as e:
        raise ValueError(f"Configuration validation failed: {e}")

def get_default_config_path() -> Path:
    """Returns the absolute path to the default config file."""
    # Assuming src/config.py is one level deep from root
    root_dir = Path(__file__).parent.parent
    return root_dir / "config" / "default.yaml"
