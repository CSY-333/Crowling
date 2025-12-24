"use client";

import { FC } from "react";

type Step = {
  title: string;
  description: string;
  items: string[];
};

const PRESETS = [
  { label: "FAST", detail: "Max concurrency, minimal retries" },
  { label: "SAFE", detail: "Slow & cautious for 429-heavy runs" },
  { label: "DEBUG", detail: "Short run with verbose logging" },
];

type ControlStepperProps = {
  steps: Step[];
};

export const ControlStepper: FC<ControlStepperProps> = ({ steps }) => {
  return (
    <aside className="card space-y-6">
      <div>
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">
          Presets
        </h2>
        <div className="mt-3 flex flex-col gap-2">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              className="rounded-lg border px-3 py-2 text-left hover:border-slate-400"
            >
              <div className="text-xs font-semibold">{preset.label}</div>
              <p className="text-[11px] text-slate-500">{preset.detail}</p>
            </button>
          ))}
        </div>
      </div>
      <div className="space-y-5">
        {steps.map((step, index) => (
          <div key={step.title} className="rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">
                {index + 1}
              </div>
              <div>
                <div className="text-sm font-semibold">{step.title}</div>
                <p className="text-xs text-slate-500">{step.description}</p>
              </div>
            </div>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-slate-600">
              {step.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </aside>
  );
};
