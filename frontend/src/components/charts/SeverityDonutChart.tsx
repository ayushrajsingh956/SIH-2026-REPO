import React from "react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
} from "recharts";
import { DATAVIZ_THEME, getSeverityColor } from "./theme";

export interface SeverityData {
  severity: string;
  count: number;
  percentage: number;
}

interface Props {
  data: SeverityData[];
}

export const SeverityDonutChart: React.FC<Props> = ({ data }) => {
  const total = data.reduce((acc, curr) => acc + curr.count, 0);

  if (!data || total === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-slate-400 text-sm">
        No violations recorded in this period.
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-between gap-3 w-full">
      {/* Donut Chart with centered summary */}
      <div className="relative w-full h-48 flex items-center justify-center">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const d = payload[0].payload as SeverityData;
                  return (
                    <div style={DATAVIZ_THEME.tooltipStyle} className="p-2.5 shadow-lg">
                      <div className="font-semibold capitalize text-xs text-white">
                        {d.severity} Severity
                      </div>
                      <div className="mt-1 text-slate-200 text-xs">
                        {d.count} violations ({d.percentage}%)
                      </div>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Pie
              data={data}
              dataKey="count"
              nameKey="severity"
              cx="50%"
              cy="50%"
              innerRadius={46}
              outerRadius={68}
              paddingAngle={3}
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getSeverityColor(entry.severity)} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-2xl font-black text-slate-900 tracking-tight">{total}</span>
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
            Violations
          </span>
        </div>
      </div>

      {/* Legend Rows - clean, spacious, completely legible and never cut off */}
      <div className="w-full space-y-2 pt-3 border-t border-slate-100">
        {data
          .filter((item) => item.count > 0)
          .map((item) => {
            const color = getSeverityColor(item.severity);
            return (
              <div
                key={item.severity}
                className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-100"
              >
                <div className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: color }}
                  />
                  <span className="capitalize font-semibold text-slate-700 text-xs">
                    {item.severity} Severity
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-slate-900 text-xs">{item.count}</span>
                  <span className="text-slate-500 font-medium text-xs">({item.percentage}%)</span>
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
};
