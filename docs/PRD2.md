NACT-MVP PRD v1.1 (Unified & Authoritative)
Naver Article & Comment Tracker — Research Dataset Snapshot Generator

Status: Authoritative, unified PRD (supersedes prior drafts)
Version: 1.1
Last Updated: 2025-12-23 (KST, Asia/Seoul)
Primary Deliverables: nact_data.db (SQLite, WAL), CSV exports, debug/audit logs
Target Scale: ≥50,000 comments across multiple Naver News articles
Audience: Research team members running batch collection for non-commercial research

0) Authority & Precedence

This document is the single source of truth for NACT-MVP.
Where conflicts exist between earlier drafts (including any “main PRD” sections), this v1.1 PRD takes precedence—especially for:

Runtime storage (SQLite-first)

Dynamic volume strategy

Logging & audit evidence

Anti-blocking / auto-throttle rules

Privacy defaults (hashed identifiers)

1) Background & Problem Definition
1.1 Context

Naver News is a major aggregation platform in South Korea with high user engagement through comments and replies. Researchers often require keyword-driven article discovery and full comment thread collection to analyze discourse dynamics, engagement patterns, and diffusion.

1.2 Core Problem

No pre-existing URL list — articles must be discovered via keyword search.

Comments are dynamically loaded through unofficial endpoints — HTML-only scraping is incomplete.

The dataset must represent a point-in-time snapshot with clear time semantics.

The target volume (50k+ comments) must be achieved under rate limits and anti-scraping controls.

1.3 Key Constraints

No authentication (public data only).

Batch snapshot only (not continuous monitoring).

Execution on Windows is supported; file locking must be considered.

Data must be reproducible, auditable, and operationally resilient.

2) Goals & Non-Goals
2.1 Goals (In Scope)

P0 — Must Have

Discover Naver News articles from keyword search (≥100 articles per keyword target).

Collect all comments and replies available via public endpoints (pagination-complete).

Store collected data reliably with atomic operations (SQLite transactions).

Generate mandatory audit/debug logs for every run.

P1 — Should Have

Record temporal metadata: snapshot_at (run-level), crawl_at (record-level), published_at/updated_at (article-level when available), created_at (comment-level when available).

Checkpoint/resume without re-collecting completed articles (DB-backed).

Robust failure isolation (one article failure does not kill the run unless policy demands it).

P2 — Nice to Have

Adaptive volume expansion with realistic yield estimation (Trimmed Mean).

System health scoring (technical monitoring, not selective filtering).

2.2 Non-Goals (Out of Scope)

Continuous tracking/monitoring over time.

Login-based or personalized data collection.

Sentiment analysis/NLP processing (post-processing phase).

Forcing comment sort order (accept Naver defaults).

Bypassing authentication, restrictions, paywalls, or access controls.

3) Research Governance & Data Viability

Dataset volume below 50,000 comments is not “failed.” It is status-changed.
Research validity depends on tiered interpretation.

3.1 Viability Tiers
Tier	Volume	Research Status	Allowed Analysis
Tier A (Target)	≥ 50,000	Confirmatory	Hypothesis testing, structural modeling
Tier B (Acceptable)	30,000–49,999	Exploratory	Descriptive + correlational only; claims must be “sample-specific”
Tier C (Insufficient)	< 30,000	Pilot / Debug	Tool verification only; no inferential claims
3.2 Comment Volume Bias Declaration (Mandatory in Paper)

If collection stops early or prioritizes high-volume articles, the dataset may exhibit Comment Volume Bias.

Mandatory disclosure statement:

“This dataset represents a conditional snapshot biased toward higher-engagement articles and is not a random sample of all news coverage.”

Suggested corrective analysis options (not required, but recommended):

Article fixed effects

Weighting articles by 1 / log(1 + comment_count) (or comparable)

4) Scope & Assumptions
4.1 Assumptions

Reasonably stable network; intermittent failures are expected.

Naver comment endpoint remains stable enough during a run (hours).

Public availability without authentication remains true for the accessed content.

Long-running batch execution is acceptable.

4.2 Operational Limits

Hard cap: max_total_articles = 2000
Rationale: bounded run time and reduced IP-ban risk.

5) Snapshot Time Semantics (Unambiguous)
5.1 Time Fields
Field	Meaning	Scope
snapshot_at	Official run reference time (constant across the run)	Run-level
crawl_at	Actual collection timestamp	Record-level
published_at	Article publication time	Article-level
updated_at	Article last update time (if available)	Article-level
created_at	Comment creation time (if available)	Comment-level
5.2 Interpretation

“The dataset represents Naver News as of snapshot_at. Individual records were collected between start_at and end_at, with precise collection times recorded as crawl_at.”

5.3 Timezone Policy

Store timestamps in ISO 8601 with timezone offset (KST +09:00).

Default timezone: Asia/Seoul.

Internal calculations may use UTC; storage remains explicit with timezone.

6) Data Discovery & Collection Requirements
6.1 Keyword → Article Discovery
Preferred Method: Naver Search OpenAPI

Stable and documented; requires API credentials.

Output must include canonical article URLs when possible.

Fallback: HTML Parsing

Only used if OpenAPI unavailable or blocked.

Higher fragility and blocking risk.

Article Key & Deduplication

Primary key: (oid, aid) extracted from canonical Naver article URL pattern.

Fallback key: normalized URL (domain normalize, remove query, trim slash).

6.2 Article Metadata Parsing

For each discovered article, extract:

title, press, published_at (required when available)

updated_at, section, body_length (optional)

If oid/aid cannot be extracted reliably, the article is marked failed and skipped.

6.3 Comment & Reply Collection (Core Requirement)
Definition of “ALL Comments”

“All comments” means:

Pagination-complete collection of all comments returned by the endpoint.

Deleted/blind comments are recorded with flags (do not silently drop).

Replies must be collected when indicated (commonly depth 1; handle deeper if returned).

Partial success is allowed per article, but must be logged and status-coded.

Primary Strategy: Unofficial JSON/JSONP Endpoint Replication

Handle JSONP parsing robustly.

Validate response schema; do not assume status 200 equals valid data.

Reply Strategy

For comments with replyCount > 0, fetch replies via reply endpoint or thread endpoint (depending on API behavior).

Store parent_id and depth to allow reconstruction.

7) Dynamic Volume Strategy (Trimmed Mean)
7.1 Why Trimmed Mean

Mean is distorted by viral outliers in heavy-tail distributions.

Median is overly conservative and wastes effort.

Trimmed Mean (P20–P80) is a pragmatic estimator for expected yield.

7.2 Remaining Articles Estimation (Reference Logic)

Maintain history_counts (comments collected per processed article).

After at least 20 articles, estimate yield using P20–P80 trimmed mean.

Expand article discovery if projected yield is insufficient, subject to max_total_articles.

7.3 Stop Conditions

Success: total comments ≥ 50,000 (Tier A)

Acceptable stop: 30,000–49,999 (Tier B) when no additional articles remain or limit reached

Insufficient: < 30,000 (Tier C), treated as pilot/debug outcome

8) Storage Architecture (Mandatory): SQLite-First

CSV is an export format. SQLite is the runtime system of record.

8.1 Database

File: nact_data.db

WAL mode enabled

Foreign keys enabled

8.2 Core Tables (Reference Schema)
runs

run_id (PK)

snapshot_at, start_at, end_at

timezone

config_json

status (SUCCESS / PARTIAL / STOPPED / FAILED)

aggregated metrics (counts, rates, notes)

articles

Primary key: (oid, aid)

run_id (FK → runs)

oid, aid

url, title, press

published_at, updated_at

crawl_at

status_code (see Section 10.2)

error_code, error_message

comments

Primary key: comment_id (or a deterministic surrogate if missing)

run_id (FK → runs)

oid, aid (FK → articles)

comment_id, parent_id, depth

content

author_hash (default) and optional author_raw (if explicitly enabled)

created_at, crawl_at

likes, dislikes, reply_count

is_deleted, is_blind

status_code, error_code, error_message

8.3 Resume Logic

Resume is DB-native: query existing (oid, aid) with success status.

A rerun with --resume-from-db must skip completed articles deterministically.

8.4 Export Workflow

End of run: export CSVs from SQLite.

CSVs must include run_id and snapshot_at for reproducibility.

9) Robust Endpoint Probe & Health Check
9.1 Endpoint Probe (Multi-step)

Fallback priority:

Auto-discovery (HTML parse)

Known Config A (new)

Known Config B (old)

Failure → mark article FAIL-PROBE, skip

9.2 Deep Validity Check (Schema Integrity)

A response is valid only if it contains expected comment structures (e.g., result.commentList or equivalent) and minimum expected fields in comment objects.

9.3 Pre-flight Health Check

Before full run:

Fetch 3 sample articles for the first keyword.

Attempt to fetch first page of comments for each.

Proceed if ≥2/3 succeed with deep validation.

Otherwise fail fast with a clear message and store evidence.

10) Operational Policy: Anti-Blocking & Auto-Throttle
10.1 Responsible Harvesting (Non-circumvention)

Rate limiting + backoff + session reuse

No bypassing authentication or restricted content

Identify tool via User-Agent string

Stop on forbidden indicators to reduce ban risk

10.2 Status Codes (Standardized)

Article status_code

SUCCESS

FAIL-PROBE

FAIL-HTTP

FAIL-PARSE

PARTIAL-COMMENTS

SKIP-NO-OIDAID

STOP-403

Comment status_code

SUCCESS

FAIL-HTTP

FAIL-PARSE

FAIL-SCHEMA

FAIL-REPLY

10.3 Auto-Throttle Rules

Maintain a rolling window of last 50 requests.

If 429_ratio > 5%, increase min_delay by 0.5s (bounded by a max).

If any 403 occurs: immediate STOP and mark run STOPPED with reason STOP-403.

10.4 Recovery / Cooldown Policy (Added Enhancement)

To avoid permanently “ratcheting” delays upward:

If 429 ratio stays below 1% for a sustained window (e.g., 200 requests), decrease min_delay by 0.2s down to baseline.

Log all throttle adjustments as explicit events in run logs.

11) Privacy & Compliance
11.1 Legal Posture

Intended for non-commercial research use.

Respect server load and avoid abusive patterns.

11.2 Privacy Defaults (Mandatory)

nickname, userId, or any stable user identifier must be hashed (SHA-256) by default.

11.3 Hash Linkability Policy (Added Enhancement)

Config must explicitly decide whether hashes are linkable across runs:

Default: hash_salt_mode = per_run
Meaning: same user will not be linkable across separate dataset snapshots.

Optional: hash_salt_mode = global (requires explicit justification and warning).

11.4 Raw PII Collection Gate

Raw identifiers may be stored only if:

allow_pii = True

Console warning printed at startup

Run log notes this setting was enabled

12) Logging, Audit Evidence, and Debug Artifacts
12.1 Mandatory Evidence

failed_requests.jsonl
Includes method, full URL (including query), headers, timestamps, status code, error labels.

failed_responses/{hash}.txt
First 2KB of body + safe binary/hex note if needed.

Main run log (structured): progress, retries, throttle changes, stop reasons.

12.2 Run Summary Metrics (Minimum)

Article: found, processed, success/fail counts, failure types

Comment: total saved, replies saved, error counts, per-article yield distribution summary

HTTP: 429 count, 403 count, avg response time

Tier outcome: A/B/C with explicit rationale

13) Technical Health Score (Monitoring Only)

Renamed explicitly to avoid implying sampling completeness.

Rules

Never drop data based on this score.

If score < 70, flag the run as “Technical Review Needed.”

Components (reference):

High duplicate rate penalty

Timestamp anomalies penalty

Total mismatch penalty (when API provides a reliable total count)

14) System Design (MVP Architecture)
nact-mvp/
├── src/
│   ├── collectors/
│   │   ├── search_collector.py
│   │   ├── article_parser.py
│   │   └── comment_collector.py
│   ├── storage/
│   │   ├── db.py               # SQLite WAL, schema migration, transactions
│   │   └── exporters.py         # CSV export from DB
│   ├── ops/
│   │   ├── logger.py
│   │   ├── rate_limiter.py
│   │   ├── throttle.py          # auto-throttle + recovery policy
│   │   └── health_check.py
│   ├── privacy/
│   │   └── hashing.py           # salted hashing policy
│   ├── config.py
│   └── main.py
├── config/default.yaml
├── data/nact_data.db
├── exports/
│   ├── articles.csv
│   ├── comments.csv
│   └── run_log.csv
└── logs/
    ├── debug_*.log
    ├── failed_requests.jsonl
    └── failed_responses/

15) Execution Interface (CLI)
python -m nact_mvp --config config.yaml --resume-from-db data/nact_data.db


Required behaviors

Print configuration summary at start (including privacy mode).

Run pre-flight health check.

Create or reuse run_id deterministically (timestamp-based is acceptable).

Commit article+comment batches transactionally.

16) Configuration (Reference)
snapshot:
  timezone: "Asia/Seoul"
  reference_time: "start"        # start | manual
  manual_snapshot_time: null

search:
  keywords: ["기후변화", "인공지능"]
  max_articles_per_keyword: 300
  date_range:
    start: "2025-01-01"
    end: "2025-12-23"
  sort: "rel"
  use_openapi: true

volume_strategy:
  target_comments: 50000
  min_acceptable_comments: 30000
  max_total_articles: 2000
  estimator: "trimmed_mean_p20_p80"

collection:
  rate_limit:
    baseline_min_delay: 1.0
    min_delay: 1.0
    max_delay: 3.0
    max_concurrent: 1
  retry:
    max_attempts: 3
    backoff_factor: 2
  timeout:
    connect: 10
    read: 30
  auto_throttle:
    window: 50
    ratio_429_threshold: 0.05
    min_delay_step_up: 0.5
    recovery_window: 200
    ratio_429_recovery_threshold: 0.01
    min_delay_step_down: 0.2
    stop_on_403: true

storage:
  db_path: "./data/nact_data.db"
  wal_mode: true

privacy:
  allow_pii: false
  hash_algorithm: "sha256"
  hash_salt_mode: "per_run"      # per_run | global
  global_salt: null              # required if global

17) Success Criteria (Acceptance)
17.1 Primary Acceptance

Runtime storage is SQLite (WAL) and run is resumable from DB.

Exports parse cleanly in pandas/R.

Logs include failures and evidence artifacts.

17.2 Tier Outcome

Tier A (≥50k): confirmatory-ready

Tier B (30k–49,999): exploratory-only with mandatory bias disclosure

Tier C (<30k): pilot/debug-only

18) Milestones (Pragmatic)

Week 1

OpenAPI search + article parser + DB schema + exporter

Pre-flight health check

Week 2

Comment collector with pagination + reply collection + deep schema validation

Retry + backoff + evidence logs

Week 3

Auto-throttle with recovery + health score + full run summary tiering

Scale test to Tier A target

19) Known Risks & Mitigations (Reality-Based)

Endpoint volatility: mitigate with probe fallback chain + schema validation + evidence capture.

Rate limiting/IP ban risk: mitigate with strict delays, auto-throttle, stop-on-403.

Selection bias: mandatory disclosure + recommended FE/weights.

Partial data corruption risk: mitigated by SQLite transactions; CSV is export-only.

End of Document — NACT-MVP PRD v1.1