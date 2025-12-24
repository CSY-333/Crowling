"use client";

import { FC } from "react";

type MetricCardProps = {
  label: string;
  value: string;
  trend?: string;
};

export const MetricCard: FC<MetricCardProps> = ({ label, value, trend }) => {
  return (
    <div className="card flex flex-col gap-1">
      <span className="text-xs uppercase text-slate-400">{label}</span>
      <span className="text-2xl font-semibold">{value}</span>
      {trend && <span className="text-xs text-slate-500">{trend}</span>}
    </div>
  );
};
