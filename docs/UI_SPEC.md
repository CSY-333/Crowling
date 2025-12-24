# NACT-MVP Web UI Specifications (Research-Grade)

**Goal**: Create a "Research-First" Web UI that prioritizes determinism, reproducibility, and failure visibility over visual flair.
**Stack**: Next.js (React) + Tailwind CSS + shadcn/ui (Frontend), FastAPI (Backend).
**Theme**: Clean, White Background, Minimalist (Inter font).

## 1. Design & UX Principles

1.  **3-Stage Flow**: Input → Execute → Result (Strict isolation).
2.  **Config First**: "Settings" are shown as a Review Card, not just a form. (Eye-check before execution).
3.  **Process Visibility**: During execution, show "Current Step" + "Last 20 Log Lines" rather than a generic progress bar.
4.  **KPI First**: Results start with summary stats (Success Rate, Miss Rate, Dup Rate) before the raw table.
5.  **Failure Gallery**: Do not hide failures. Separate them into a clear gallery for review.
6.  **Reproducibility**: `Run ID`, `Config Hash`, `Timestamp` must be pinned at the top.

## 2. Layout Structure

### A. Global Header (Fixed)

- **Left**: Project Logo + Mode Toggle (Research / Demo).
- **Center**: Current `Run ID` / `Config Hash`.
- **Right**: Export Dropdown (CSV, Report.md, JSON Logs).

### B. Main Two-Column Layout

- **Left Column (Control Stepper)**:
  1.  **Data Source**: URL List / Keywords / Date Range.
  2.  **Collection Policy**: Rate Limit, Retry logic, Concurrency.
  3.  **Schema & Validation**: Required columns, Unique Keys.
  4.  **Output**: Naming convention, Storage path.
- **Right Column (Live Preview & Guardrails)**:
  - **Config Card**: "Execution Summary" preview.
  - **Warnings**: Rule-based alerts (e.g., "High concurrency may trigger 429").
  - **Estimates**: Expected request count & time.

## 3. Key Screens

### C. Execution Screen

- **Status Badges**: `Collecting` → `Parsing` → `Validating` → `Reporting`.
- **Timeline**: Visual progress of the current item.
- **Live Log**: Monospace, auto-scroll, search supports, "Copy" button.

### D. Results Screen

- **KPI Cards (6)**: Success%, Miss%, Dup%, 429 Count, 403 Count, Duration.
- **Tabs**:
  1.  **Summary**: Graphs (Response Time, Domain Miss Rate).
  2.  **Table**: Sample 100 rows + Filters.
  3.  **Failures**: Gallery of failed URLs with error reasons.
  4.  **Compare**: Diff view (Run A vs Run B).

## 4. Components (Atomic Design)

- **MetricCard**: Big Number + Delta + Label.
- **RunBadge**: Unique ID display.
- **ConfigPanel**: Key-Value table for strict review.
- **Stepper**: Validated step navigation.
- **LogConsole**: Searchable, line-wrapping, monospace.
- **FailureCard**: URL, Status, Error Type, Evidence Link.
- **DiffView**: Comparative stats between runs.

## 5. User-Friendly Features (The "Wow" Factor)

1.  **Presets**: Buttons for `FAST`, `SAFE`, `DEBUG` (Auto-fills complex settings).
2.  **Pre-flight Validation**: "Test Schema (5 samples)" button before full run.
3.  **Warning Banners**: "This config increases miss rate risk."
4.  **Undo/History**: Restore recent configs.
5.  **Global Search**: Search across logs, tables, and errors simultaneously.
6.  **One-Click Reproduction**: "Re-run this ID".
7.  **Smart Explain**: Tooltips explaining errors (e.g., "429: Slow down").

## 6. Visual Style (Tailwind)

- **Font**: `font-sans` (Inter).
- **Background**: White (`bg-white`).
- **Cards**: `rounded-xl border bg-white shadow-sm p-6`.
- **Text**: Headers `text-xl font-semibold`, Body `text-sm text-slate-600`.
- **Badges**: `rounded-full px-2 py-1 text-xs`.
