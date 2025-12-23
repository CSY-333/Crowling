# NACT-MVP Operations Protocol & Critical Enhancements

> [!CRITICAL] > **Protocol Authority**
> This document defines the **Operations Protocol v1**.
> **"A run is considered valid ONLY if `run_log` contains (run_id, snapshot_at, endpoint_config_json, schema_version) and the DB passes integrity_check."**
> This document supersedes main PRD sections regarding Storage, Scheduling, and Data Governance.

---

## 0. Operations Protocol v1

### 0.1 Run Lifecycle

- **Run ID**: Format `run_YYYYMMDD_HHMMSS` (KST). Unique identifier for every execution context.
- **Snapshot Time**: `snapshot_at` is fixed at **Run Start Time**. All records effectively inherit this timestamp as their "reference time".
- **Database**: Per-run isolation default: `nact_data_{run_id}.db`.
- **Resume**: Must provide `--resume-from-db {path}`. Run ID and Salt are read from the existing DB (state continuity).

### 0.2 Article State Machine

Every article MUST reach a **Terminal State**.

| State              | Description                                      |
| ------------------ | ------------------------------------------------ |
| `FOUND`            | Initial state from Search API.                   |
| `SKIP-NO_OID_AID`  | Parse error, cannot extract ID. (Terminal)       |
| `PROBE-OK`         | Endpoint parameters discovered/verified.         |
| `FAIL-PROBE`       | Could not determine comment endpoint. (Terminal) |
| `CRAWL-OK`         | Article metadata collected.                      |
| `FAIL-HTTP`        | Article page/API HTTP error. (Terminal)          |
| `COMMENTS-OK`      | All comments collected successfully. (Terminal)  |
| `COMMENTS-PARTIAL` | Collection interrupted/incomplete. (Terminal\*)  |
| `FAIL-STRUCTURAL`  | Schema mismatch/Parse failure. (Terminal)        |
| `STOP-403`         | Forced stop due to Forbidden. (Terminal)         |
| `STOP-RATE-LIMIT`  | Forced stop due to excessive 429s. (Terminal)    |

### 0.3 Auto-Throttle Rules

- **Window**: Sliding window of last 50 requests.
- **Scale Up**: If 429 Ratio > 5% → `min_delay += 0.5s` (Max 10.0s).
- **Recovery**: If 429 Ratio < 1% for 3 windows → `min_delay -= 0.5s` (Min 1.0s).
- **Hard Stop**:
  - **403 Forbidden**: Immediate Stop (Count >= 1).
  - **Rate Limit**: 429 Ratio > 20% for 2 windows → `STOP-RATE-LIMIT`.

### 0.4 Privacy & Hashing (Run-Level)

- **Salt Policy**: Generated **Per-Run** (stored in `run_state` table) by default.
  - _Result_: `hash(user_id + run_salt)`. Safe from rainbow tables, prevents cross-run tracking (Privacy-First).
  - _Config_: User can supply fixed `project_salt` for longitudinal tracking if approved.

---

## 1. Research Governance & Data Viability

### 1.1 Viability Tiers

| Tier       | Volume   | Research Status  | Allowed Analysis                               |
| ---------- | -------- | ---------------- | ---------------------------------------------- |
| **Tier A** | ≥ 50,000 | **Confirmatory** | Full hypothesis testing.                       |
| **Tier B** | 30k-50k  | **Exploratory**  | Descriptive stats only. Limits must be stated. |
| **Tier C** | < 30,000 | **Pilot**        | Tool verification only. No inferential claims. |

### 1.2 Bias Declaration

If stopping volume < 50k or utilizing "High Volume Priority":

> "Data represents a _conditional snapshot_ of high-engagement articles. Analysis must apply article-level weighting or fixed effects."

---

## 2. Dynamic Volume Strategy (Trimmed Mean)

**Logic**: Use **Winsorized Mean (P20-P80)** to estimate yield.

- Outliers (top 20% viral, bottom 20% empty) are excluded from yield estimation to prevent optimistic/pessimistic skew.
- **Max Articles**: Hard limit `2000` to prevent infinite crawl loops on low-yield keywords.

---

## 3. Storage Architecture (SQLite)

### 3.1 Metadata & Config Tables

```sql
CREATE TABLE run_config (
    key TEXT PRIMARY KEY,
    value TEXT
);
-- Stores: run_id, snapshot_at, author_salt, endpoint_config_json, schema_version
```

### 3.2 Articles Table

```sql
CREATE TABLE articles (
    oid TEXT NOT NULL,
    aid TEXT NOT NULL,
    run_id TEXT NOT NULL,
    snapshot_at TEXT NOT NULL, -- Run start time
    crawl_at TEXT NOT NULL, -- Actual collection time
    source_keyword TEXT,
    matched_keywords TEXT,
    search_rank INTEGER,
    terminal_state TEXT NOT NULL, -- See State Machine
    error_code TEXT,
    error_message TEXT,
    url TEXT,
    title TEXT,
    meta_json TEXT,
    PRIMARY KEY (oid, aid)
);
```

### 3.3 Comments Table

```sql
CREATE TABLE comments (
    comment_id TEXT PRIMARY KEY,
    oid TEXT NOT NULL,
    aid TEXT NOT NULL,
    run_id TEXT NOT NULL,
    snapshot_at TEXT NOT NULL,
    crawl_at TEXT NOT NULL, -- Record-level time
    parent_id TEXT,
    depth INTEGER,
    content TEXT,
    created_at TEXT,
    author_hash TEXT, -- SHA256(uid + salt)
    author_raw TEXT, -- NULL unless configured
    reply_count INTEGER,
    is_deleted BOOLEAN,
    is_blind BOOLEAN,
    status TEXT, -- OK/DELETED/BLIND/FAIL
    FOREIGN KEY (oid, aid) REFERENCES articles(oid, aid)
);
```

---

## 4. Robust Endpoint Probe

**Deep Validity Check**:

- Probe must verify JSON structure contains critical keys (`contents`, `regTime`) and not just a "success" wrapper.
- **Failure Handling**: If probe fails, article state = `FAIL-PROBE`. Do NOT attempt to crawl comments.

---

## 5. Export Policy (Python-Based)

> [!CAUTION] > **Do not use `sqlite3` CLI for CSV export.**
> Naver comments contain newlines, emojis, and special characters that break standard CLI CSV tools.

**Implementation**:

```python
def export_safe_csv(db_path, output_dir):
    conn = sqlite3.connect(db_path)

    # Articles
    df = pd.read_sql("SELECT * FROM articles", conn)
    df.to_csv(output_dir / "articles.csv", index=False, encoding="utf-8-sig")

    # Comments
    df = pd.read_sql("SELECT * FROM comments", conn)
    # Ensure correct escaping of newlines/quotes
    df.to_csv(
        output_dir / "comments.csv",
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_ALL, # Force quotes for safety
        escapechar='\\'
    )

    # Manifest
    manifest = {
        "export_at": datetime.now().isoformat(),
        "source_db": str(db_path),
        "records": len(df)
    }
    with open(output_dir / "export_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
```

---

## 6. Execution Interface

```bash
# Start new run
python -m nact_mvp start --keywords "AI,Climate" --target 50000

# Resume
python -m nact_mvp resume --db nact_data_run_20251223.db

# Export
python -m nact_mvp export --db nact_data_run_20251223.db --format csv
```
