import React from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  CartesianGrid,
} from "recharts";
import { DATAVIZ_THEME, getSeverityColor } from "./theme";

export interface RuleViolationData {
  rule_code: string;
  rule_title: string;
  citation: string;
  severity: string;
  count: number;
}

interface Props {
  data: RuleViolationData[];
}

export const ViolationsByRuleBarChart: React.FC<Props> = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-slate-400 text-sm">
        No rule violations recorded in this period.
      </div>
    );
  }

  // Ensure sorted by count ascending for horizontal bar chart so highest is on top
  const sortedData = [...data].sort((a, b) => a.count - b.count);

  return (
    <div className="w-full h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          layout="vertical"
          data={sortedData}
          margin={{ top: 10, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke={DATAVIZ_THEME.grid.stroke} />
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "#64748b" }} />
          <YAxis
            type="category"
            dataKey="rule_code"
            tick={{ fontSize: 11, fill: "#1e293b", fontWeight: 500 }}
            width={115}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const d = payload[0].payload as RuleViolationData;
                return (
                  <div
                    style={DATAVIZ_THEME.tooltipStyle}
                    className="p-3 shadow-lg border border-slate-700 max-w-xs"
                  >
                    <div className="font-semibold text-xs text-white">{d.rule_code}: {d.rule_title}</div>
                    <div className="text-[11px] text-slate-300 mt-0.5">{d.citation}</div>
                    <div className="flex items-center justify-between mt-2 pt-1 border-t border-slate-700 text-xs">
                      <span className="capitalize font-medium text-amber-400">
                        {d.severity}
                      </span>
                      <span className="font-bold text-white">{d.count} occurrences</span>
                    </div>
                  </div>
                );
              }
              return null;
            }}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={22}>
            {sortedData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getSeverityColor(entry.severity)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
