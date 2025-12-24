"use client";

import { FC } from "react";

type ConfigSummaryProps = {
  entries: { label: string; value: string }[];
};

export const ConfigSummary: FC<ConfigSummaryProps> = ({ entries }) => {
  return (
    <section className="card space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Execution Summary</h3>
        <button className="rounded-full border px-3 py-1 text-xs font-semibold text-slate-600">
          Edit Config
        </button>
      </div>
      <dl className="grid grid-cols-2 gap-4 text-sm text-slate-600">
        {entries.map((entry) => (
          <div key={entry.label}>
            <dt className="text-xs uppercase text-slate-400">{entry.label}</dt>
            <dd className="font-medium text-slate-800">{entry.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
};
