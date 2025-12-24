"use client";

import { FC } from "react";

type LogConsoleProps = {
  lines: string[];
};

export const LogConsole: FC<LogConsoleProps> = ({ lines }) => {
  return (
    <section className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Live Log</h3>
        <button className="rounded border px-3 py-1 text-xs">Copy</button>
      </div>
      <pre className="h-48 overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-200">
        {lines.map((line, idx) => (
          <div key={`${line}-${idx}`} className="font-mono">
            {line}
          </div>
        ))}
      </pre>
    </section>
  );
};
