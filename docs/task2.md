# NACT-MVP — Task Breakdown (task.md)

> Source of truth: **NACT-MVP PRD v1.1 (Unified & Authoritative)**
>
> Output expectation: This task list is **implementation-ready** (engineer can start coding immediately).

---

## 0) Definition of Done (Global)

A run is considered **Done** when all of the following are true:

* [ ] `nact_data.db` is created/updated in **SQLite WAL mode** and contains `runs`, `articles`, `comments` tables (and any supporting tables).
* [ ] CLI supports:

  * [ ] `--config <path>`
  * [ ] `--resume-from-db <db_path>`
  * [ ] a deterministic `run_id` (timestamp-based acceptable)
* [ ] Pre-flight health check executes and gates the run (≥2/3 sample articles succeed with deep schema validation).
* [ ] Collection is **transactional** (article+comments inserted via transactions; no partial-line CSV risk).
* [ ] Exporters generate:

  * [ ] `exports/articles.csv`
  * [ ] `exports/comments.csv`
  * [ ] `exports/run_log.csv` (1 row per run)
* [ ] Evidence artifacts exist for failures:

  * [ ] `logs/failed_requests.jsonl`
  * [ ] `logs/failed_responses/{hash}.txt`
* [ ] Auto-throttle behavior:

  * [ ] windowed 429 ratio logic
  * [ ] stop-on-403 (immediate)
  * [ ] recovery/cooldown step-down logic
  * [ ] all throttle changes logged as events
* [ ] Privacy defaults:

  * [ ] author identifiers are **SHA-256 hashed** by default
  * [ ] `hash_salt_mode=per_run` is default
  * [ ] `allow_pii=true` requires explicit config + console warning + run log flag
* [ ] Tier outcome (A/B/C) computed and stored in `runs.status` + `runs.notes`.

---

## 1) Repo & Project Scaffolding

### 1.1 Create folder structure

* [ ] Create repository root with:

  * [ ] `src/collectors/`
  * [ ] `src/storage/`
  * [ ] `src/ops/`
  * [ ] `src/privacy/`
  * [ ] `config/`
  * [ ] `data/`
  * [ ] `exports/`
  * [ ] `logs/failed_responses/`

### 1.2 Add packaging / entry points

* [ ] Add `pyproject.toml` or `setup.cfg` (choose one) to enable:

  * [ ] `python -m nact_mvp` execution
* [ ] Add `requirements.txt` (or `pyproject` deps) for core libs:

  * [ ] requests/httpx (choose one)
  * [ ] beautifulsoup4 + lxml
  * [ ] pyyaml
  * [ ] tenacity (optional) or custom retry

### 1.3 Add default config

* [ ] Create `config/default.yaml` matching PRD v1.1 fields:

  * snapshot, search, volume_strategy, collection, storage, privacy

---

## 2) Configuration Loader & Runtime Context

### 2.1 Implement config parsing

* [ ] Implement `src/config.py`:

  * [ ] load YAML
  * [ ] validate required keys
  * [ ] apply defaults
  * [ ] produce a typed config object (dataclass or pydantic)

### 2.2 Run context initialization

* [ ] Implement:

  * [ ] `run_id` generation
  * [ ] `snapshot_at` semantics (start/manual)
  * [ ] `start_at` timestamp
  * [ ] timezone handling (store ISO 8601 + offset)

### 2.3 Print startup banner

* [ ] Print config summary (redact secrets) and privacy mode:

  * [ ] if `allow_pii=true`: print WARNING and require explicit confirmation flag (optional) or proceed with warning per PRD.

---

## 3) SQLite Storage Layer (Mandatory Runtime SOR)

### 3.1 Database init

* [ ] Implement `src/storage/db.py`:

  * [ ] open connection
  * [ ] set `PRAGMA journal_mode=WAL;`
  * [ ] set `PRAGMA foreign_keys=ON;`
  * [ ] set reasonable `busy_timeout`

### 3.2 Schema migration / creation

* [ ] Implement table creation:

  * [ ] `runs`
  * [ ] `articles` (PK: oid+aid)
  * [ ] `comments` (PK: comment_id)
  * [ ] optional: `events` (throttle changes, structural failure signals)

### 3.3 Transaction utilities

* [ ] Provide helpers:

  * [ ] `with db.transaction():` context manager
  * [ ] `upsert_article(...)`
  * [ ] `insert_comments_bulk(...)` (executemany)

### 3.4 Resume queries

* [ ] Implement:

  * [ ] `get_completed_article_keys(run_id?)` OR `get_completed_article_keys_any_run` depending on intended resume semantics
  * [ ] default: resume by checking article existence with SUCCESS/PARTIAL status

---

## 4) Logging & Evidence Capture

### 4.1 Structured logger

* [ ] Implement `src/ops/logger.py`:

  * [ ] console INFO+
  * [ ] file DEBUG+ (`logs/debug_YYYYMMDD_HHMMSS.log`)

### 4.2 Failed request capture (mandatory)

* [ ] Implement `src/ops/evidence.py` (or inside logger):

  * [ ] append JSONL entry to `logs/failed_requests.jsonl` including:

    * method, full_url, headers (redact secrets), timestamp, status_code, error_type, context (oid,aid,page)

### 4.3 Failed response capture (mandatory)

* [ ] Store `failed_responses/{hash}.txt` with:

  * [ ] first 2KB of body
  * [ ] content-type
  * [ ] note if binary / include safe hex snippet if needed

---

## 5) Privacy Layer (Hashing Policy)

### 5.1 Hashing utility

* [ ] Implement `src/privacy/hashing.py`:

  * [ ] SHA-256 hashing for identifiers
  * [ ] salt selection:

    * [ ] `per_run` default (salt derived from run_id)
    * [ ] `global` optional (requires config global_salt)
  * [ ] deterministic output for same (salt, input)

### 5.2 PII gates

* [ ] Ensure:

  * [ ] `author_hash` always stored if identifier exists
  * [ ] `author_raw` stored only if `allow_pii=true`
  * [ ] run log flags when PII enabled

---

## 6) SearchCollector (Keyword → Articles)

### 6.1 OpenAPI client (primary)

* [ ] Implement `src/collectors/search_collector.py`:

  * [ ] request signing with client_id/client_secret
  * [ ] pagination up to `max_articles_per_keyword`
  * [ ] normalize OpenAPI + HTML fallback items into `ArticleSearchResult` (url/oid/aid/title/published_at/description/matched_keywords)
  * [ ] record `search_rank` (1-indexed within keyword)

### 6.2 Fallback HTML search (secondary)

* [ ] Implement HTML parsing fallback:

  * [ ] parse Naver search result pages for article links
  * [ ] handle paging conservatively
  * [ ] higher delays to reduce block risk

### 6.3 Deduplication

* [ ] Implement:

  * [ ] `extract_oid_aid(url)`
  * [ ] `normalize_url(url)`
  * [ ] in-collector dedup suppression using key priority: (oid,aid) else normalized url
  * [ ] `matched_keywords` accumulation (list per unique article)

---

## 7) ArticleParser (Metadata)

### 7.1 Fetch and parse article HTML

* [ ] Implement `src/collectors/article_parser.py`:

  * [ ] fetch article HTML
  * [ ] parse title/press/published_at/updated_at
  * [ ] extract section if available
  * [ ] compute `body_length` if feasible

### 7.2 Robustness

* [ ] Multi-strategy parse:

  * [ ] meta tags / JSON-LD first
  * [ ] fallback selectors
* [ ] On parse failure:

  * [ ] store partial fields
  * [ ] mark `articles.status_code=FAIL-PARSE` (or SUCCESS with warnings if minimal fields ok)

---

## 8) Comment Endpoint Probe & Health Check

### 8.1 Endpoint parameter discovery

* [ ] Implement `src/ops/probe.py` (or inside comment collector):

  * [ ] Auto-discovery from article HTML (ticket/templateId/pool/cv/template)
  * [ ] `get_candidate_configs()` helper to return [auto, Config A, Config B]
  * [ ] Ensure callers iterate Config A/B when discovery fails

### 8.2 Deep schema validation

* [ ] Implement `deep_validate_response(json_data)` per protocol:

  * [ ] verify comment list key exists
  * [ ] verify required keys exist on first comment if present

### 8.3 Pre-flight health check

* [ ] Implement `src/ops/health_check.py`:

  * [ ] get 3 sample articles from first keyword
  * [ ] fetch first comment page
  * [ ] require ≥2 successes
  * [ ] on failure: log evidence + stop run with clear error

---

## 9) CommentCollector (Pagination + Replies)

### 9.1 JSONP parsing

* [ ] Implement robust JSONP parser:

  * [ ] strip callback wrapper safely
  * [ ] guard against HTML error pages
  * [ ] raise typed errors: PARSE_ERROR, SCHEMA_MISMATCH

### 9.2 Page fetcher

* [ ] Implement `_fetch_comment_page(oid, aid, page, endpoint_params)`:

  * [ ] request headers include Referer and UA
  * [ ] timeouts
  * [ ] evidence capture on failure

### 9.3 Pagination loop

* [ ] Collect until:

  * [ ] empty comment list
  * [ ] cursor/next indicator exhausted
  * [ ] structural failure detector triggers stop threshold

### 9.4 Replies

* [ ] For each comment with `reply_count > 0`:

  * [ ] fetch replies via reply endpoint
  * [ ] ensure `parent_id` set and `depth=1` (or deeper if returned)

### 9.5 Deleted/blind handling

* [ ] Preserve rows with flags:

  * [ ] `is_deleted`, `is_blind`
  * [ ] content may be empty/placeholder

---

## 10) Rate Limiting, Retry, Auto-Throttle

### 10.1 Rate limiter

* [ ] Implement `src/ops/rate_limiter.py`:

  * [ ] random sleep between min/max
  * [ ] session reuse

### 10.2 Retry policy

* [ ] Implement exponential backoff:

  * [ ] retry 429/5xx/timeouts up to max_attempts
  * [ ] log attempts

### 10.3 Auto-throttle (hard rules)

* [ ] Implement `src/ops/throttle.py`:

  * [ ] window=50
  * [ ] if 429 ratio > 5%: min_delay += 0.5s
  * [ ] if any 403: immediate stop + mark run STOPPED
  * [ ] recovery: if 429 ratio < 1% for 200 requests: min_delay -= 0.2s down to baseline
  * [ ] every adjustment emits an event row (db.events) + file log

---

## 11) Structural Failure Detection

### 11.1 Detector

* [ ] Implement consecutive structural failure counter:

  * [ ] increments on: JSONP_PARSE_ERROR, SCHEMA_MISMATCH, ENDPOINT_404
  * [ ] threshold=10 triggers stop

### 11.2 Stop protocol

* [ ] On structural stop:

  * [ ] finalize run
  * [ ] write run status + stop reason
  * [ ] keep evidence artifacts

---

## 12) Dynamic Volume Strategy (Trimmed Mean)

### 12.1 Volume tracker

* [ ] Maintain `history_counts` (comments per article)
* [ ] After 20 articles:

  * [ ] compute P20–P80 trimmed mean
  * [ ] estimate remaining required articles

### 12.2 Expansion logic

* [ ] If projected yield insufficient and remaining articles exhausted:

  * [ ] increase `max_articles_per_keyword` (bounded)
  * [ ] optionally expand date range (if configured)
  * [ ] stop if `max_total_articles` would be exceeded

### 12.3 Bias disclosure flag

* [ ] If prioritization by comment count is enabled or early stop occurs:

  * [ ] set run notes: `comment_volume_bias=true`

---

## 13) System Health Score (Monitoring Only)

### 13.1 Compute metrics

* [ ] duplicate_rate
* [ ] timestamp anomalies
* [ ] total mismatch (only if API provides trustworthy total)

### 13.2 Scoring and alerts

* [ ] Score starts 100; apply penalties
* [ ] If score < 70:

  * [ ] run flag: `technical_review_needed=true`
  * [ ] do not drop data

---

## 14) Orchestration (main.py)

### 14.1 End-to-end flow

* [ ] Load config
* [ ] init run context
* [ ] init DB
* [ ] pre-flight health check
* [ ] for each keyword:

  * [ ] search articles
  * [ ] dedup
  * [ ] for each article:

    * [ ] skip if already completed (resume)
    * [ ] parse article metadata
    * [ ] probe endpoint if needed
    * [ ] collect comments+replies
    * [ ] transaction: upsert article + insert comments
    * [ ] update volume tracker
    * [ ] checkpoint via DB state
  * [ ] periodic progress logging every 10 articles

### 14.2 Finalization

* [ ] compute totals + rates
* [ ] determine Tier A/B/C
* [ ] write `runs` summary
* [ ] export CSVs

---

## 15) CSV Exporters

### 15.1 Export implementation

* [ ] Implement `src/storage/exporters.py`:

  * [ ] export `articles.csv` and `comments.csv` with required columns
  * [ ] export `run_log.csv` (one row per run)

### 15.2 Column requirements

* [ ] Ensure every export row includes:

  * [ ] `run_id`
  * [ ] `snapshot_at`
  * [ ] ISO 8601 timestamps with timezone

---

## 16) Test Plan (Minimum)

### 16.1 Unit tests

* [ ] JSONP parser tests:

  * valid JSONP
  * malformed JSONP
  * HTML error page
* [ ] oid/aid extraction tests
* [ ] hashing tests (per_run vs global)
* [ ] trimmed mean estimator tests

### 16.2 Integration tests

* [ ] Health check gate test (mock endpoints)
* [ ] Resume behavior test (run twice; second run skips)
* [ ] Evidence artifact generation test

---

## 17) Operational Runbook (Quick)

* [ ] Start with 1 keyword small run (max 30 articles) to validate endpoints
* [ ] Watch 429 ratio; confirm auto-throttle adjustments log correctly
* [ ] If any 403 occurs: stop and change network/IP later
* [ ] Validate exports with pandas:

  * `pd.read_csv(exports/comments.csv)`

---

## 18) Milestone Checklist

### Milestone 1 — Foundations

* [ ] Config loader + DB WAL + schema + CLI

### Milestone 2 — Core Collection

* [ ] SearchCollector + ArticleParser + CommentCollector (pagination + replies)

### Milestone 3 — Operations

* [ ] Auto-throttle + structural failure detector + evidence artifacts

### Milestone 4 — Scale Readiness

* [ ] Volume strategy + tiering + exporters + health score

---

## 19) Open Decisions (Track Explicitly)

* [ ] Choose HTTP client: requests vs httpx
* [ ] Choose retry lib: tenacity vs custom
* [ ] Decide resume scope: within-run only vs cross-run reuse of articles
* [ ] Confirm reply endpoint behavior (depends on current Naver schema)
