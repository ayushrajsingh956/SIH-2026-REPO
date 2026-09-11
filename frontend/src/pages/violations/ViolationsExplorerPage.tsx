import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  ShieldAlert,
  Filter,
  ExternalLink,
  MapPin,
  AlertOctagon,
  AlertTriangle,
  Info,
  CheckCircle,
} from "lucide-react";
import { apiClient } from "@/services/api";

export const ViolationsExplorerPage: React.FC = () => {
  const navigate = useNavigate();
  const [ruleCode, setRuleCode] = useState<string>("");
  const [severity, setSeverity] = useState<string>("");
  const [district, setDistrict] = useState<string>("");
  const [overridden, setOverridden] = useState<string>("");

  const [debouncedDistrict, setDebouncedDistrict] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedDistrict(district);
    }, 300);
    return () => clearTimeout(timer);
  }, [district]);

  // Fetch Violations
  const { data, isLoading } = useQuery({
    queryKey: ["violations", ruleCode, severity, debouncedDistrict, overridden],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (ruleCode) params.append("rule_code", ruleCode);
      if (severity) params.append("severity", severity);
      if (debouncedDistrict) params.append("district", debouncedDistrict);
      if (overridden) params.append("overridden", overridden);
      params.append("limit", "250");

      const res = await apiClient.get(`/api/v1/violations?${params.toString()}`);
      return res.data;
    },
  });

  const violations = data?.items || [];
  const total = data?.total || 0;
  const severitySummary = data?.severity_summary || {};

  // Virtualization for large lists (> 200 rows)
  const parentRef = useRef<HTMLDivElement>(null);
  const shouldVirtualize = violations.length > 200;

  const rowVirtualizer = useVirtualizer({
    count: violations.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 72,
    overscan: 10,
    enabled: shouldVirtualize,
  });

  const renderSeverityBadge = (sev: string, isOverridden: boolean) => {
    if (isOverridden) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-500 border border-slate-200 line-through">
          Overridden
        </span>
      );
    }
    switch (sev.toLowerCase()) {
      case "critical":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-red-100 text-red-800 border border-red-200">
            <AlertOctagon className="w-3 h-3" />
            CRITICAL
          </span>
        );
      case "major":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
            <AlertTriangle className="w-3 h-3" />
            MAJOR
          </span>
        );
      case "minor":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-100 text-blue-800 border border-blue-200">
            <Info className="w-3 h-3" />
            MINOR
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700">
            ADVISORY
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-red-600" />
            Statutory Violations Explorer
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Surveillance registry of non-compliant packaged commodity declarations across all inspections.
          </p>
        </div>

        <div className="text-xs font-medium text-slate-500">
          Showing: <strong className="text-slate-900">{total} infractions</strong>
        </div>
      </div>

      {/* Severity Distribution Mini-Chart Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-red-50/70 border border-red-200 rounded-xl p-3 flex items-center justify-between">
          <div>
            <div className="text-[11px] font-bold text-red-800 uppercase">Critical</div>
            <div className="text-xl font-extrabold text-red-900 mt-0.5">
              {severitySummary.critical || 0}
            </div>
          </div>
          <AlertOctagon className="w-6 h-6 text-red-400" />
        </div>

        <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-3 flex items-center justify-between">
          <div>
            <div className="text-[11px] font-bold text-amber-800 uppercase">Major</div>
            <div className="text-xl font-extrabold text-amber-900 mt-0.5">
              {severitySummary.major || 0}
            </div>
          </div>
          <AlertTriangle className="w-6 h-6 text-amber-400" />
        </div>

        <div className="bg-blue-50/70 border border-blue-200 rounded-xl p-3 flex items-center justify-between">
          <div>
            <div className="text-[11px] font-bold text-blue-800 uppercase">Minor</div>
            <div className="text-xl font-extrabold text-blue-900 mt-0.5">
              {severitySummary.minor || 0}
            </div>
          </div>
          <Info className="w-6 h-6 text-blue-400" />
        </div>

        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center justify-between">
          <div>
            <div className="text-[11px] font-bold text-slate-600 uppercase">Advisory</div>
            <div className="text-xl font-extrabold text-slate-800 mt-0.5">
              {severitySummary.advisory || 0}
            </div>
          </div>
          <CheckCircle className="w-6 h-6 text-slate-400" />
        </div>
      </div>

      {/* Multi-Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 mr-2">
          <Filter className="w-3.5 h-3.5" />
          Filter By:
        </div>

        {/* Severity */}
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          className="text-xs rounded-lg border border-slate-200 px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium text-slate-700 bg-white"
        >
          <option value="">All Severities</option>
          <option value="critical">Critical</option>
          <option value="major">Major</option>
          <option value="minor">Minor</option>
          <option value="advisory">Advisory</option>
        </select>

        {/* Rule Code */}
        <select
          value={ruleCode}
          onChange={(e) => setRuleCode(e.target.value)}
          className="text-xs rounded-lg border border-slate-200 px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium text-slate-700 bg-white"
        >
          <option value="">All Statutory Rules</option>
          <option value="LMPC-R6-1a">Rule 6(1)(a) Name & Address</option>
          <option value="LMPC-R6-1b">Rule 6(1)(b) Net Quantity</option>
          <option value="LMPC-R6-1c">Rule 6(1)(c) Month / Year</option>
          <option value="LMPC-R6-1d">Rule 6(1)(d) Consumer Care</option>
          <option value="LMPC-R9-1">Rule 9(1) MRP Format</option>
          <option value="LMPC-R9-5">Rule 9(5) Font Size</option>
          <option value="LMPC-R10-1">Rule 10 Metric Units</option>
          <option value="LMPC-R11-1">Rule 11 Future Dating</option>
        </select>

        {/* Override status */}
        <select
          value={overridden}
          onChange={(e) => setOverridden(e.target.value)}
          className="text-xs rounded-lg border border-slate-200 px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium text-slate-700 bg-white"
        >
          <option value="">All Statuses</option>
          <option value="false">Active Citations</option>
          <option value="true">Inspector Overridden</option>
        </select>

        {/* District input */}
        <div className="relative">
          <MapPin className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2" />
          <input
            type="text"
            placeholder="Filter district..."
            value={district}
            onChange={(e) => setDistrict(e.target.value)}
            className="pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 w-36"
          />
        </div>

        {/* Reset button */}
        {(ruleCode || severity || district || overridden) && (
          <button
            onClick={() => {
              setRuleCode("");
              setSeverity("");
              setDistrict("");
              setOverridden("");
            }}
            className="text-xs font-semibold text-blue-600 hover:text-blue-800 ml-auto"
          >
            Reset Filters
          </button>
        )}
      </div>

      {/* Violations Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-slate-400 text-xs animate-pulse">
            Querying statutory violations registry...
          </div>
        ) : violations.length === 0 ? (
          <div className="p-12 text-center">
            <CheckCircle className="w-10 h-10 text-emerald-400 mx-auto mb-2" />
            <div className="text-sm font-semibold text-slate-700">No violations match the selected criteria</div>
            <p className="text-xs text-slate-400 mt-1">Try relaxing one or more filter parameters.</p>
          </div>
        ) : shouldVirtualize ? (
          /* Virtualized view if > 200 items */
          <div ref={parentRef} className="h-[600px] overflow-auto divide-y divide-slate-100">
            <div
              style={{
                height: `${rowVirtualizer.getTotalSize()}px`,
                width: "100%",
                position: "relative",
              }}
            >
              {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                const v = violations[virtualRow.index];
                return (
                  <div
                    key={v.id}
                    onClick={() => navigate(`/scans/${v.scan_id}`)}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      height: `${virtualRow.size}px`,
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                    className="flex items-center justify-between px-4 py-2 hover:bg-slate-50 cursor-pointer transition-colors text-xs"
                  >
                    <div className="w-28 shrink-0">
                      {renderSeverityBadge(v.severity, v.overridden)}
                    </div>
                    <div className="flex-1 min-w-0 pr-4">
                      <div className="font-bold text-slate-900 truncate">
                        {v.rule_code} · {v.rule_title}
                      </div>
                      <div className="text-[11px] text-slate-400 truncate">
                        {v.citation} · {v.product_name || "Unlinked Commodity"}
                      </div>
                    </div>
                    <div className="w-32 hidden md:block text-slate-500 truncate">
                      {v.district || "Central"}
                    </div>
                    <div className="w-24 text-right text-slate-400 text-[11px]">
                      {new Date(v.scanned_at).toLocaleDateString("en-IN")}
                    </div>
                    <ExternalLink className="w-4 h-4 text-slate-400 ml-2" />
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* Standard table */
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Statutory Citation</th>
                  <th className="py-3 px-4 hidden md:table-cell">Observed vs Expected</th>
                  <th className="py-3 px-4">Commodity / Mode</th>
                  <th className="py-3 px-4 hidden lg:table-cell">District</th>
                  <th className="py-3 px-4 text-right">Date</th>
                  <th className="py-3 px-4 text-right">Source Scan</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {violations.map((v: any) => (
                  <tr
                    key={v.id}
                    onClick={() => navigate(`/scans/${v.scan_id}`)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4 whitespace-nowrap">
                      {renderSeverityBadge(v.severity, v.overridden)}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-900">{v.rule_code}</div>
                      <div className="text-xs text-slate-600 mt-0.5">{v.rule_title}</div>
                      <div className="text-[11px] text-slate-400">{v.citation}</div>
                    </td>
                    <td className="py-3 px-4 hidden md:table-cell max-w-xs">
                      {v.observed_value && (
                        <div className="text-[11px] truncate">
                          <span className="text-red-600 font-semibold">Obs:</span> {v.observed_value}
                        </div>
                      )}
                      {v.expected_value && (
                        <div className="text-[11px] text-slate-400 truncate mt-0.5">
                          <span className="text-emerald-600 font-semibold">Exp:</span> {v.expected_value}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-900 truncate max-w-[150px]">
                        {v.product_name || "Label Inspection"}
                      </div>
                      <span className="capitalize text-[11px] text-slate-400">{v.mode}</span>
                    </td>
                    <td className="py-3 px-4 hidden lg:table-cell text-slate-500 whitespace-nowrap">
                      {v.district ? (
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-slate-400" />
                          {v.district}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-3 px-4 text-right text-slate-400 text-[11px] whitespace-nowrap">
                      {new Date(v.scanned_at).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </td>
                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      <Link
                        to={`/scans/${v.scan_id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:underline"
                      >
                        Inspect
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
