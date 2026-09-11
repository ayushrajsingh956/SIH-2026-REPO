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
    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 h-72">
      <div className="relative w-full sm:w-1/2 h-56">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const d = payload[0].payload as SeverityData;
                  return (
                    <div style={DATAVIZ_THEME.tooltipStyle} className="p-2.5">
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
              innerRadius={55}
              outerRadius={80}
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
          <span className="text-2xl font-extrabold text-slate-900">{total}</span>
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Violations
          </span>
        </div>
      </div>

      {/* Legend list */}
      <div className="w-full sm:w-1/2 space-y-2.5 pr-2">
        {data.map((item) => {
          const color = getSeverityColor(item.severity);
          return (
            <div key={item.severity} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full inline-block"
                  style={{ backgroundColor: color }}
                />
                <span className="capitalize font-medium text-slate-700">{item.severity}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-900">{item.count}</span>
                <span className="text-slate-400 w-10 text-right">({item.percentage}%)</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
