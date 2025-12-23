# NACT-MVP Project Governance Rules

**ALL AGENTS MUST FOLLOW THESE RULES WITHOUT EXCEPTION.**
These rules supersede any implicit preferences.

## 1. Zero-Trust TDD (Test-Driven Development) Protocol

> "No implementation code exists without a failing test."

- **Process**:
  1.  **Red**: Write a test case that fails.
  2.  **Green**: Write the _minimum_ code to pass the test.
  3.  **Refactor**: Improve code quality without changing behavior.
- **Verification**:
  - Never commit code unless `pytest tests/` returns `Exit Code 0`.
  - Do not write "placeholder" tests that always pass.

## 2. SOLID Architecture Mandate

> "Dependencies point inwards; High-level modules own the interfaces."

- **SRP (Single Responsibility)**: Split `Collector`, `Parser`, `Probe`, `Evidence` into separate modules.

  - **Enforcement**: A class/module must have exactly one reason to change. HTTP request logic, parsing, schema validation, pagination control, and persistence MUST NOT coexist in the same class.

- **OCP (Open/Closed)**: New strategies (e.g., volume algorithms) must simpler implement an interface, not modify core loop logic.

  - **Enforcement**: Core pagination loops and collector orchestration logic are CLOSED for modification. Any new behavior must be injected via strategy objects or callbacks.

- **LSP (Liskov Substitution)**:

  - **Enforcement**: Any implementation of an interface must preserve behavioral contracts:
    - same input types
    - same error semantics (typed exceptions)
    - no additional side effects

- **ISP (Interface Segregation)**:

  - **Enforcement**: Interfaces must not force implementers to depend on methods they do not use. Prefer multiple role-specific interfaces over a single multipurpose interface.

- **DIP (Dependency Inversion)**:
  - **Enforcement**: No concrete implementation may be instantiated inside domain or collector logic. All wiring must occur at a single composition root (`main.py`).

## 3. Operations & Safety

- **Evidence First**: Failures must be logged to `failed_requests.jsonl` _before_ raising exceptions.
- **SQLite-First**: Usage of transactional writes (WAL mode) is mandatory. RAM buffering is prohibited.
- **Privacy-First**: PII (User ID/Name) must be hashed (SHA-256) unless `config.privacy.allow_pii` is explicitly True.

## 4. No Silent Failures (Operational Integrity)

- **Fail Fast**: 403 Forbidden, Structural Threshold Reached.
- **Warn Only**: Health Score < 70, Single Parsing Error (unless structural).
- **Never Drop Data**: Even "failed" rows should be logged or tracked in `failed_requests` evidentiary logs.

## 5. Error Taxonomy & Handling

> "Classify errors by recovery strategy, not by source."

- **Rule**: All exceptions raised from domain modules MUST be `AppError`. External exceptions MUST be caught and wrapped at the boundary.
- **Enforcement**: `AppError` MUST define `severity` (WARN/RETRY/ABORT) and `kind` (HTTP/PARSE/SCHEMA/STRUCTURAL).
  - _Transient_: Retryable (Network, 429).
  - _Permanent_: Non-retryable (404, Bad Params).
  - _Fatal_: Immediate Stop (403, Repeated Schema Mismatch, Probe Failure).

## 6. Determinism & Idempotency

> "Replayability is non-negotiable."

- **Rule**: Run logic must be safe to replay. Re-processing a completed CLI command must produce zero side effects on domain records.
- **Enforcement**: CLI commands MUST be replay-safe: re-running the same command with the same config and `snapshot_at` MUST NOT create duplicate domain records (idempotent writes via PK/unique constraints). Evidence logs may append but MUST be content-addressed (hash-based) to avoid uncontrolled growth.

## 7. Design by Contract

> "Trust but Verify at Boundaries."

- **Rule**: Public interfaces must validate inputs (Pre-condition) and guarantee output schema (Post-condition).
- **Enforcement**: All boundary interfaces (HTTP parse result, DAO writes, CLI inputs) MUST enforce contracts: preconditions validated (caller errors abort), postconditions guaranteed via DTO/schema validation (data errors classified as `SchemaMismatchError`). Use Pydantic models for external JSON/JSONP-derived payloads; internal functions rely on typed DTOs only.
