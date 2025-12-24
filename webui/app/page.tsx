"use client";

import { RunHeader } from "@/components/run-header";
import { ControlStepper } from "@/components/control-stepper";
import { ConfigSummary } from "@/components/config-summary";
import { LogConsole } from "@/components/log-console";
import { MetricCard } from "@/components/metric-card";
import { FailureCard } from "@/components/failure-card";

const steps = [
  {
    title: "Data Sources",
    description: "Keywords & target endpoints",
    items: ["Keywords: ['기후변화','AI']", "Date Range: 2025-01-01 ~ 2025-01-31"],
  },
  {
    title: "Collection Policy",
    description: "Traffic shape & resilience",
    items: [
      "Rate limit: 1 req/sec",
      "Retry: Exponential 3 attempts",
      "Throttle: Auto cool-down",
    ],
  },
  {
    title: "Schema & Validation",
    description: "Contract-first parsing",
    items: ["Required: oid, aid, body", "Unique key: comment_no"],
  },
  {
    title: "Output & Storage",
    description: "Reproducible exports",
    items: ["DB: data/nact_data.db", "Exports: exports/*.csv"],
  },
];

const configEntries = [
  { label: "Keywords", value: "기후변화, AI, 경제" },
  { label: "Snapshot", value: "2025-01-01T09:00:00+09:00" },
  { label: "Rate Limit", value: "min 1s / max 3s" },
  { label: "Retry", value: "429/5xx x3 exponential" },
  { label: "Auto-Throttle", value: "Window 50, 5% threshold" },
  { label: "PII", value: "Hashed (allow_pii=false)" },
];

const logLines = [
  "[09:00:01] ▶ Starting Run run_20250101_0900",
  "[09:00:02] ▶ Keyword '기후변화' page 1",
  "[09:00:04] ✔ Article 001/000123 metadata ok",
  "[09:00:05] ↺ Probe fallback template applied",
  "[09:00:06] ✔ Comments persisted (52 rows)",
  "[09:00:08] ⚠ 429 detected -> throttle up",
  "[09:00:12] ▶ Keyword 'AI' page 1",
  "[09:00:15] ✖ Failed URL logged to evidence",
];

const failureSamples = [
  {
    url: "https://news.naver.com/article/001/000789",
    status: "403",
    error: "Forbidden",
    evidence: "/logs/failed_responses/a1b2.txt",
  },
  {
    url: "https://n.news.naver.com/article/009/000222",
    status: "schema",
    error: "Missing commentList",
    evidence: "/logs/failed_responses/f9e8.txt",
  },
];

export default function Page() {
  return (
    <div className="min-h-screen bg-slate-50">
      <RunHeader runId="run_20250101_0900" configHash="cf7d29" />
      <main className="mx-auto max-w-6xl space-y-8 px-6 py-8">
        <section className="grid gap-6 md:grid-cols-[320px_minmax(0,1fr)]">
          <ControlStepper steps={steps} />
          <div className="space-y-6">
            <ConfigSummary entries={configEntries} />
            <div className="grid gap-4 md:grid-cols-3">
              {[
                { label: "Expected Duration", value: "38m", trend: "±4m" },
                { label: "Expected Requests", value: "1,240", trend: "per 3 keywords" },
                { label: "Risk", value: "Moderate", trend: "High 429 probability" },
              ].map((metric) => (
                <MetricCard key={metric.label} {...metric} />
              ))}
            </div>
            <div className="card space-y-4">
              <div className="flex flex-wrap gap-2 text-xs">
                {["Collecting", "Parsing", "Validating", "Reporting"].map((stage, idx) => (
                  <span
                    key={stage}
                    className={`rounded-full px-3 py-1 ${idx === 1 ? "bg-slate-900 text-white" : "bg-slate-200 text-slate-700"}`}
                  >
                    {stage}
                  </span>
                ))}
              </div>
              <div className="space-y-2">
                {[
                  { label: "Article 12", progress: 80 },
                  { label: "Article 13", progress: 32 },
                  { label: "Article 14", progress: 4 },
                ].map((item) => (
                  <div key={item.label}>
                    <div className="flex justify-between text-xs text-slate-500">
                      <span>{item.label}</span>
                      <span>{item.progress}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-slate-200">
                      <div
                        className="h-full rounded-full bg-slate-900"
                        style={{ width: `${item.progress}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <LogConsole lines={logLines} />
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex flex-wrap gap-3">
            {[
              "Summary",
              "Table",
              "Failures",
              "Compare",
            ].map((tab, idx) => (
              <button
                key={tab}
                className={`rounded-full px-4 py-1 text-sm ${idx === 0 ? "bg-slate-900 text-white" : "bg-white text-slate-600"}`}
              >
                {tab}
              </button>
            ))}
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {[
              { label: "Success Rate", value: "92%" },
              { label: "Miss Rate", value: "5%" },
              { label: "Dup Rate", value: "3%" },
              { label: "429 Count", value: "12" },
              { label: "403 Count", value: "2" },
              { label: "Duration", value: "00:34:11" },
            ].map((metric) => (
              <MetricCard key={metric.label} label={metric.label} value={metric.value} />
            ))}
          </div>
          <div className="card">
            <h3 className="text-lg font-semibold">Failure Gallery</h3>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              {failureSamples.map((failure) => (
                <FailureCard key={failure.url} {...failure} />
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
