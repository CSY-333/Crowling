"use client";

import { FC } from "react";

type RunHeaderProps = {
  runId: string;
  configHash: string;
};

export const RunHeader: FC<RunHeaderProps> = ({ runId, configHash }) => {
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b bg-white/90 px-6 py-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="rounded-full bg-slate-900 px-3 py-1 text-sm font-semibold text-white">
          NACT-MVP
        </div>
        <span className="text-xs uppercase tracking-widest text-slate-500">
          Research Mode
        </span>
      </div>
      <div className="flex flex-col items-center">
        <span className="text-xs uppercase text-slate-400">Run ID</span>
        <span className="font-mono text-sm">{runId}</span>
        <span className="text-[11px] text-slate-400">Config {configHash}</span>
      </div>
      <div className="flex gap-2">
        <button className="rounded-full border px-3 py-1 text-xs font-semibold text-slate-600">
          Export CSV
        </button>
        <button className="rounded-full border px-3 py-1 text-xs font-semibold text-slate-600">
          Export Report
        </button>
        <button className="rounded-full border px-3 py-1 text-xs font-semibold text-slate-600">
          Logs
        </button>
      </div>
    </header>
  );
};
