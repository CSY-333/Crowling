# NACT-MVP Technical Reference Manual

**Version**: 1.0.0
**Date**: 2025-12-24
**Status**: Milestones 1-4 Complete, Milestone 5 (UI) Partially Implemented (Frontend Mock)

---

## 1. System Overview

NACT-MVP (Naver Article & Comment Tracker) is a specialized robust crawler designed for legal resilience and data integrity. It collects news articles and comments from Naver News, enforcing strict schemas and operational safety limits.

### Core Capabilities

- **Transactional Collection**: SQLite WAL mode ensures atomic storage of articles and comments.
- **Structural Safety**: Circuit breaker pattern (`StructuralDetector`) aborts runs upon detecting site layout changes.
- **Dynamic Volume**: Strategy pattern (`VolumeStrategy`) supports adaptive stopping conditions (Fixed Target / Time-based).
- **Privacy First**: SHA-256 hashing of user identifiers by default.
- **Scale Ready**: CSV exporters include demographic stats (`comment_stats`) and health scores.

---

## 2. Directory Structure

```text
Crowling/
├── config/                 # YAML Configuration
│   └── default.yaml        # Source of Truth for defaults
├── docs/                   # Documentation & Specs
├── src/                    # Backend Source Code (Python)
│   ├── collectors/         # Fetching & Parsing Logic
│   ├── common/             # Errors & Shared Types
│   ├── ops/                # Operations (Throttling, Metrics, Evidence)
│   ├── storage/            # Database Repository & Schema
│   ├── config.py           # Configuration Loader
│   └── main.py             # Entry Point
├── webui/                  # Frontend Source Code (Next.js)
│   ├── app/                # App Router Pages
│   ├── components/         # React Components (Atoms/Molecules)
│   └── public/             # Static Assets
├── tests/                  # Pytest Suite
└── nact_data.db            # SQLite Database (Runtime)
```

---

## 3. Backend Architecture (`src/`)

### 3.1 Core Components

**1. Configuration (`src/config.py`)**

- Uses `Pydantic` for strict validation of YAML input.
- **Key Models**: `SearchConfig`, `PrivacyConfig`, `VolumeStrategyConfig`.

**2. Storage Layer (`src/storage/`)**

- **`Database`**: Wrapper around `sqlite3`. Enforces `WAL` mode and `foreign_keys=ON`.
- **Schema**:
  - `runs`: Execution metadata (status, health score).
  - `articles`: Article metadata (oid, aid, title).
  - `comments`: Comment content (hierarchy, hashed author).
  - `comment_stats`: Demographic aggregation (gender/age).
  - `events`: Operational logs (throttle changes).

**3. Collection Pipeline (`src/collectors/`)**

- **`SearchCollector`**: Fetches article list via Naver Search API or HTML Fallback.
- **`ArticleParser`**: Extracts metadata using `BeautifulSoup`.
- **`CommentCollector`**:
  - Orchestrates fetching (`CommentFetcher`) and parsing (`CommentParser`).
  - Handles pagination and reply traversal (depth=1).
  - **Integration**: Injects `StructuralDetector` to monitor parse/schema errors.
  - **Stats**: Delegated to `CommentStatsService` (Best-effort).

**4. Operational Safety (`src/ops/`)**

- **`AutoThrottler`**: Monitors 429 response ratio in sliding window (default 50 requests). Dynamically adjusts `min_delay`.
- **`StructuralDetector`**: Circuit breaker. Raises `StructuralError` (Fatal) if `threshold` (10) consecutive errors occur.
- **`VolumeStrategy`**: Implements Strategy Pattern (`FixedTargetStrategy`). Decides when to stop the crawler based on `config.volume_strategy`.
- **`EvidenceCollector`**: Writes failed requests to `logs/failed_requests.jsonl` for audit.

---

## 4. Frontend Architecture (`webui/`)

**Status**: Prototype / Mock Mode.
The frontend is built with **Next.js 14+ (App Router)** and **Tailwind CSS**. Currently, it displays mock data and does not communicate with a real Python backend API (as `src/api` is not yet implemented).

### 4.1 Key Components (`webui/components/`)

- **`RunHeader`**: Displays active Run ID and configuration hash.
- **`ControlStepper`**: Visualizes the 4-step configuration process.
- **`LogConsole`**: Simulates real-time log streaming (currently static list).
- **`MetricCard` / `FailureCard`**: KPI visualization components.

### 4.2 State Management

- Currently uses local component state.
- _Planned_: React Query for polling `src/api` endpoints.

---

## 5. Workflow & Data Flow

1.  **Initialization**: `main.py` loads `config.yaml`, initializes `Database` and `RuntimeContext`.
2.  **Search Phase**: `SearchCollector` gathers article URLs per keyword.
3.  **Collection Loop**:
    - Check `is_article_completed(oid, aid)` (Resume Capability).
    - **Probe**: `ArticleParser` extracts metadata.
    - **Fetch**: `CommentCollector` paginates comments.
    - **Safety**: `RateLimiter` enforces delays; `StructuralDetector` watches for layout breaks.
    - **Volume**: `VolumeTracker` updates counts; `FixedTargetStrategy` checks stop condition.
4.  **Finalization**:
    - `compute_health_score` calculates data quality.
    - `DataExporter` generates CSVs in `exports/`.

---

## 6. Testing Strategy

- **Framework**: `pytest`
- **Coverage**: 63 passing tests.
- **Key Suites**:
  - `test_comment_collector.py`: Verifies pagination, replies, and Stats integration.
  - `test_ops_structural.py`: Verifies circuit breaker logic.
  - `test_ops_volume.py`: Verifies dynamic stopping logic.
  - `test_storage_exporters.py`: Verifies CSV output formats including headers.

---

## 7. Known Limitations (v1.0.0)

1.  **No REST API**: The Backend API (`src/api`) is planned but not implemented. The Web UI runs in isolation.
2.  **Naver Search API Deprecation**: If Naver shuts down the Open API, `SearchCollector` assumes an HTML fallback (implemented but less robust).
3.  **Single Thread**: The crawler is single-threaded synchronous (using `requests`). Scale is achieved via efficiency, not concurrency.

---

---

## 8. Appendix: Implementation Details

### 8.1 Structural Failure Detection (Circuit Breaker)

**Source**: `src/ops/structural.py`

The `StructuralDetector` class implements a circuit breaker pattern. It monitors consecutive collection failures (Schema Mismatch, Parse Error). If the failure count exceeds the threshold (default 10), it raises a fatal `StructuralError` to abort the entire run, protecting the dataset from pollution.

```python
class StructuralError(AppError):
    """
    Fatal error raised when the site structure seems to have changed fundamentally,
    making further collection unsafe or useless.
    """
    def __init__(self, message: str):
        super().__init__(message, Severity.ABORT, ErrorKind.STRUCTURAL)


class StructuralDetector:
    """
    Circuit breaker for structural failures.
    If N consecutive parse/schema errors occur, we assume the site layout has changed
    and we should stop to prevent polluting the dataset with garbage/failures.
    """
    def __init__(self, threshold: int = 10):
        self.threshold = threshold
        self.failure_count = 0

    def record_failure(self, reason: str) -> None:
        self.failure_count += 1
        logger.warning(
            "Structural failure #%d/%d detected: %s",
            self.failure_count,
            self.threshold,
            reason
        )

        if self.failure_count >= self.threshold:
            msg = f"Structural integrity threshold exceeded ({self.failure_count} failures). Reason: {reason}"
            logger.critical(msg)
            raise StructuralError(msg)

    def record_success(self) -> None:
        if self.failure_count > 0:
            logger.info("Structural failure counter reset (was %d).", self.failure_count)
            self.failure_count = 0
```

### 8.2 Database Schema

**Source**: `src/storage/db.py`

The database schema is designed for collecting hierarchical comment data and stats. It uses SQLite with WAL mode enabled for concurrency.

```sql
-- 1. Runs Table
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    snapshot_at TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT,
    timezone TEXT NOT NULL,
    config_json TEXT,
    status TEXT CHECK(status IN ('SUCCESS', 'PARTIAL', 'STOPPED', 'FAILED', 'A', 'B', 'C')),
    notes TEXT,
    total_articles INTEGER DEFAULT 0,
    total_comments INTEGER DEFAULT 0,
    health_score INTEGER,
    health_flags TEXT
);

-- 2. Articles Table
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

-- 3. Comments Table
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

-- 4. Events Table (Log)
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    event_type TEXT,
    details TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

-- 5. Comment Stats Table (Demographics)
CREATE TABLE IF NOT EXISTS comment_stats (
    oid TEXT NOT NULL,
    aid TEXT NOT NULL,
    run_id TEXT NOT NULL,
    total_comments INTEGER,
    male_ratio REAL,
    female_ratio REAL,
    age_10s REAL,
    age_20s REAL,
    age_30s REAL,
    age_40s REAL,
    age_50s REAL,
    age_60s REAL,
    age_70s REAL,
    snapshot_at TEXT,
    collected_at TEXT,
    PRIMARY KEY (oid, aid, run_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    FOREIGN KEY (oid, aid) REFERENCES articles(oid, aid)
);
```

### 8.3 Execution Entry Point (`main.py`)

The application bootstraps via `bootstrap_runtime` (config loading, DB init, logging) and then enters the main loop. Strategies (Volume, Throttle) are injected dynamically.

```python
def main():
    args = parse_args()
    try:
        context = bootstrap_runtime(args)
    except Exception:
        sys.exit(1)

    # ... Component Initialization (omitted for brevity) ...

    # 6. Main Collection Loop
    total_articles = 0
    total_comments = 0

    for keyword in config.search.keywords:
        logger.info(f"== Processing Keyword: {keyword} ==")

        for item in searcher.search_keyword(keyword):
            # ... (Resume Check) ...

            # 1. Parse Metadata
            meta = parser.fetch_and_parse(url)

            # 2. Probe Endpoint (Find Ticket/Template ID)
            candidates = probe.get_candidate_configs(url, raw_html)

            # 3. Collect Comments (Try candidates)
            for params in candidates:
                try:
                    count = collector.collect_article(oid, aid, params)
                    total_comments += count
                    volume_tracker.add_count(count)
                    break # Success!
                except Exception:
                    continue # Try next params

            # 4. Volume Strategy Check
            if stop_strategy:
                decision = stop_strategy.decide(total_comments, 0.0)
                if decision.should_stop:
                    sys.exit(0)

    # 7. Finalization & Health Score
    run_repo.finalize_run(run_id, ...)
```

---

**Contact**: Engineering Team (Google Deepmind Agnetic Coding)
