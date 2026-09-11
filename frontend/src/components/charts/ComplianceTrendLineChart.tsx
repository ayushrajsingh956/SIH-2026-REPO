import React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import { DATAVIZ_THEME } from "./theme";

export interface TrendDataPoint {
  date: string;
  total_scans: number;
  compliant_scans: number;
  non_compliant_scans: number;
  compliance_rate: number;
  avg_score: number;
}

interface Props {
  data: TrendDataPoint[];
  granularity: "day" | "week" | "month";
  onGranularityChange: (g: "day" | "week" | "month") => void;
}

export const ComplianceTrendLineChart: React.FC<Props> = ({
  data,
  granularity,
  onGranularityChange,
}) => {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Target Benchmark
          </span>
          <span className="ml-2 text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">
            ≥ 90% Statutory Target
          </span>
        </div>
        <div className="inline-flex rounded-lg border border-slate-200 p-0.5 bg-slate-50">
          {(["day", "week", "month"] as const).map((g) => (
            <button
              key={g}
              onClick={() => onGranularityChange(g)}
              className={`px-2.5 py-1 text-xs font-medium rounded-md capitalize transition-colors ${
                granularity === g
                  ? "bg-white text-slate-900 shadow-xs font-semibold"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {g}
            </button>
          ))}
        </div>
      </div>

      <div className="w-full h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
            <defs>
              <linearGradient id="complianceGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={DATAVIZ_THEME.grid.stroke} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "#64748b" }}
              tickLine={false}
              axisLine={{ stroke: "#cbd5e1" }}
            />
            <YAxis
              domain={[0, 100]}
              width={45}
              tick={{ fontSize: 11, fill: "#64748b" }}
              tickLine={false}
              axisLine={{ stroke: "#cbd5e1" }}
              unit="%"
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  const d = payload[0].payload as TrendDataPoint;
                  return (
                    <div style={DATAVIZ_THEME.tooltipStyle} className="p-3">
                      <div className="font-semibold text-xs text-white border-b border-slate-700 pb-1">
                        {label}
                      </div>
                      <div className="mt-2 space-y-1 text-xs">
                        <div className="flex justify-between gap-4 text-emerald-400">
                          <span>Compliance Rate:</span>
                          <span className="font-bold">{d.compliance_rate}%</span>
                        </div>
                        <div className="flex justify-between gap-4 text-slate-300">
                          <span>Total Scans:</span>
                          <span className="font-bold text-white">{d.total_scans}</span>
                        </div>
                        <div className="flex justify-between gap-4 text-slate-300">
                          <span>Compliant:</span>
                          <span className="font-semibold text-emerald-300">{d.compliant_scans}</span>
                        </div>
                        <div className="flex justify-between gap-4 text-slate-300">
                          <span>Non-compliant:</span>
                          <span className="font-semibold text-red-400">{d.non_compliant_scans}</span>
                        </div>
                        <div className="flex justify-between gap-4 text-slate-400 pt-1 border-t border-slate-800">
                          <span>Average Score:</span>
                          <span className="font-semibold text-white">{d.avg_score} / 100</span>
                        </div>
                      </div>
                    </div>
                  );
                }
                return null;
              }}
            />
            <ReferenceLine
              y={90}
              stroke="#10b981"
              strokeDasharray="4 4"
              strokeWidth={1.5}
            />
            <Area
              type="monotone"
              dataKey="compliance_rate"
              stroke="#10b981"
              strokeWidth={2.5}
              fillOpacity={1}
              fill="url(#complianceGradient)"
              dot={{ r: 3, fill: "#10b981" }}
              activeDot={{ r: 5 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
