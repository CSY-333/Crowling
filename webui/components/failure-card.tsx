"use client";

import { FC } from "react";

type FailureCardProps = {
  url: string;
  status: string;
  error: string;
  evidence: string;
};

export const FailureCard: FC<FailureCardProps> = ({
  url,
  status,
  error,
  evidence,
}) => {
  return (
    <div className="rounded-xl border p-4 shadow-sm">
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span className="font-mono">{status}</span>
        <span className="rounded-full bg-red-100 px-2 py-0.5 text-[11px] text-red-600">
          {error}
        </span>
      </div>
      <p className="mt-2 text-sm font-medium text-slate-800">{url}</p>
      <a href={evidence} className="mt-2 inline-block text-xs text-slate-500">
        Evidence →
      </a>
    </div>
  );
};
