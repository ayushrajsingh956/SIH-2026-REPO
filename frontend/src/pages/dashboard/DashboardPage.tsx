import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  Clock,
  Upload,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  BarChart3,
  PieChart as PieIcon,
  TrendingUp,
  MapPin,
  Calendar,
} from "lucide-react";
import { apiClient } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";
import { ViolationsByRuleBarChart } from "@/components/charts/ViolationsByRuleBarChart";
import { SeverityDonutChart } from "@/components/charts/SeverityDonutChart";
import { ComplianceTrendLineChart } from "@/components/charts/ComplianceTrendLineChart";

export const DashboardPage: React.FC = () => {
  const { user } = useAuthStore();
  const [range, setRange] = useState<"7d" | "30d" | "90d">("30d");
  const [granularity, setGranularity] = useState<"day" | "week" | "month">("day");

  const canCreateScan = user?.role === "admin" || user?.role === "inspector";

  // 1. Dashboard Summary
  const { data: summary, isLoading: isSummaryLoading } = useQuery({
    queryKey: ["dashboard", "summary", range],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/dashboard/summary?range=${range}`);
      return res.data;
    },
  });

  // 2. Violations by Rule
  const { data: ruleViolations, isLoading: isRulesLoading } = useQuery({
    queryKey: ["dashboard", "violations-by-rule", range],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/dashboard/violations/by-rule?range=${range}&limit=8`);
      return res.data;
    },
  });

  // 3. Violations by Severity
  const { data: severityData, isLoading: isSeverityLoading } = useQuery({
    queryKey: ["dashboard", "violations-by-severity", range],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/dashboard/violations/by-severity?range=${range}`);
      return res.data;
    },
  });

  // 4. Compliance Trend
  const { data: trendData, isLoading: isTrendLoading } = useQuery({
    queryKey: ["dashboard", "compliance-trend", range, granularity],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/dashboard/compliance/trend?range=${range}&granularity=${granularity}`
      );
      return res.data;
    },
  });

  // 5. Districts Breakdown
  const { data: districtsData, isLoading: isDistrictsLoading } = useQuery({
    queryKey: ["dashboard", "districts", range],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/dashboard/districts?range=${range}`);
      return res.data;
    },
  });

  return (
    <div className="space-y-6">
      {/* Top Banner & Range Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900">Compliance Analytics Dashboard</h1>
            <span className="px-2 py-0.5 text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 rounded-md">
              LMPC Rules, 2011
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Real-time compliance surveillance metrics and statutory violations breakdown across jurisdictions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Range Selector */}
          <div className="inline-flex items-center rounded-lg border border-slate-200 p-1 bg-slate-50">
            <Calendar className="w-3.5 h-3.5 text-slate-400 ml-1.5 mr-1" />
            {(["7d", "30d", "90d"] as const).map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
                  range === r
                    ? "bg-white text-blue-700 shadow-xs font-semibold"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {r === "7d" ? "7 Days" : r === "30d" ? "30 Days" : "90 Days"}
              </button>
            ))}
          </div>

          {canCreateScan && (
            <Link to="/scans/new">
              <button className="flex items-center gap-2 px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer">
                <Upload className="w-3.5 h-3.5" />
                New Scan
              </button>
            </Link>
          )}
        </div>
      </div>

      {/* KPI Stat Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Scans */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Scans
            </span>
            <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
              <Activity className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-extrabold text-slate-900 mt-2">
            {isSummaryLoading ? "..." : summary?.total_scans?.toLocaleString() || "0"}
          </div>
          <div className="text-xs text-slate-500 font-medium mt-1 flex items-center gap-1">
            {summary?.scans_comparison_pct !== null && summary?.scans_comparison_pct !== undefined ? (
              summary.scans_comparison_pct >= 0 ? (
                <span className="text-emerald-600 flex items-center gap-0.5">
                  <ArrowUpRight className="w-3.5 h-3.5" /> +{summary.scans_comparison_pct}%
                </span>
              ) : (
                <span className="text-red-500 flex items-center gap-0.5">
                  <ArrowDownRight className="w-3.5 h-3.5" /> {summary.scans_comparison_pct}%
                </span>
              )
            ) : null}
            <span>vs previous {range}</span>
          </div>
        </div>

        {/* Compliance Rate */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Compliance Rate
            </span>
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-extrabold text-slate-900 mt-2">
            {isSummaryLoading ? "..." : `${summary?.compliance_rate || 0}%`}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            {summary?.compliance_rate && summary.compliance_rate >= 90 ? (
              <span className="text-emerald-600 font-semibold">Exceeds target benchmark (≥90%)</span>
            ) : (
              <span className="text-amber-600 font-medium">Below benchmark (≥90%)</span>
            )}
          </div>
        </div>

        {/* Average Compliance Score */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Average Score
            </span>
            <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-extrabold text-slate-900 mt-2">
            {isSummaryLoading ? "..." : `${summary?.avg_compliance_score || 0} / 100`}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            <span>{summary?.total_violations || 0} total violations recorded</span>
          </div>
        </div>

        {/* Pending Review */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Pending Reviews
            </span>
            <div className="p-2 bg-amber-50 text-amber-600 rounded-lg">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-extrabold text-slate-900 mt-2">
            {isSummaryLoading ? "..." : summary?.pending_reviews || 0}
          </div>
          <div className="text-xs text-amber-600 font-medium mt-1">
            <span>{summary?.critical_violations || 0} critical violations open</span>
          </div>
        </div>
      </div>

      {/* Primary Visualizations Grid: Trend + Severity Donut */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Compliance Trend Chart (2 cols) */}
        <div className="lg:col-span-2 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-600" />
              Compliance Surveillance Trend
            </h2>
          </div>
          {isTrendLoading ? (
            <div className="h-64 flex items-center justify-center text-slate-400 text-sm animate-pulse">
              Loading trend analytics...
            </div>
          ) : (
            <ComplianceTrendLineChart
              data={trendData || []}
              granularity={granularity}
              onGranularityChange={setGranularity}
            />
          )}
        </div>

        {/* Severity Donut Chart (1 col) */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <h2 className="text-sm font-bold text-slate-900 mb-2 flex items-center gap-2">
            <PieIcon className="w-4 h-4 text-blue-600" />
            Violations Severity Mix
          </h2>
          <p className="text-xs text-slate-400 mb-2">
            Statutory violations distribution across enforcement severities.
          </p>
          {isSeverityLoading ? (
            <div className="h-64 flex items-center justify-center text-slate-400 text-sm animate-pulse">
              Loading severity data...
            </div>
          ) : (
            <SeverityDonutChart data={severityData || []} />
          )}
        </div>
      </div>

      {/* Secondary Visualizations Grid: Violations by Rule + District Table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Violations by Rule Horizontal Bar Chart */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-indigo-600" />
                Most Frequent Rule Violations
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Top statutory rule codes cited during automated audits.
              </p>
            </div>
            <Link to="/violations" className="text-xs font-semibold text-blue-600 hover:underline">
              View All
            </Link>
          </div>
          {isRulesLoading ? (
            <div className="h-72 flex items-center justify-center text-slate-400 text-sm animate-pulse">
              Loading rule data...
            </div>
          ) : (
            <ViolationsByRuleBarChart data={ruleViolations || []} />
          )}
        </div>

        {/* District Compliance Table */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-amber-600" />
                Jurisdiction & District Compliance
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Enforcement field coverage and regional compliance rates.
              </p>
            </div>
          </div>

          {isDistrictsLoading ? (
            <div className="h-72 flex items-center justify-center text-slate-400 text-sm animate-pulse">
              Loading district data...
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-600">
                <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
                  <tr>
                    <th className="py-2.5 px-3">District</th>
                    <th className="py-2.5 px-3">State</th>
                    <th className="py-2.5 px-3 text-right">Scans</th>
                    <th className="py-2.5 px-3 text-right">Compliance</th>
                    <th className="py-2.5 px-3 text-right">Critical Viols</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {districtsData && districtsData.length > 0 ? (
                    districtsData.map((d: any) => (
                      <tr key={`${d.district}-${d.state}`} className="hover:bg-slate-50 transition-colors">
                        <td className="py-2.5 px-3 font-medium text-slate-900">{d.district}</td>
                        <td className="py-2.5 px-3 text-slate-500">{d.state}</td>
                        <td className="py-2.5 px-3 text-right font-semibold text-slate-900">
                          {d.total_scans}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <span
                            className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold ${
                              d.compliance_rate >= 90
                                ? "bg-emerald-50 text-emerald-700"
                                : d.compliance_rate >= 75
                                ? "bg-amber-50 text-amber-700"
                                : "bg-red-50 text-red-700"
                            }`}
                          >
                            {d.compliance_rate}%
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right font-bold text-red-600">
                          {d.critical_violations}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-slate-400">
                        No district activity recorded in this period.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
