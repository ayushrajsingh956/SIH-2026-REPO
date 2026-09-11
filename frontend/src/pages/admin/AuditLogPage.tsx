import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Filter,
  RefreshCw,
  Clock,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { apiClient } from "@/services/api";
import { Button } from "@/components/ui/Button";

interface AuditLogItem {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  detail: Record<string, any> | null;
  created_at: string;
}

export const AuditLogPage: React.FC = () => {
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState<string>("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin-audit-log", page, actionFilter],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: "25",
      });
      if (actionFilter) params.append("action", actionFilter);

      const res = await apiClient.get(`/api/v1/admin/audit-log?${params.toString()}`);
      return res.data;
    },
  });

  const logs: AuditLogItem[] = data?.items || [];
  const total = data?.total || 0;

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const getActionBadgeClass = (action: string) => {
    if (action.includes("CREATE")) return "bg-emerald-50 text-emerald-700 border-emerald-200";
    if (action.includes("UPDATE") || action.includes("OVERRIDE")) return "bg-blue-50 text-blue-700 border-blue-200";
    if (action.includes("DELETE") || action.includes("FAIL")) return "bg-rose-50 text-rose-700 border-rose-200";
    return "bg-slate-100 text-slate-700 border-slate-200";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-blue-600" />
            Statutory Audit Trail &amp; System Event Log
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Tamper-evident chronological log of all compliance decisions, overrides, and administrative actions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void refetch()}
            disabled={isFetching}
            className="gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh Trail
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-slate-600">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setPage(1);
              }}
              className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs text-slate-700 outline-none focus:border-blue-500"
            >
              <option value="">All Enforcement Actions</option>
              <option value="ADMIN_UPDATE_USER">ADMIN_UPDATE_USER</option>
              <option value="ADMIN_CREATE_USER">ADMIN_CREATE_USER</option>
              <option value="ADMIN_UPDATE_RULE">ADMIN_UPDATE_RULE</option>
              <option value="VIOLATION_OVERRIDE">VIOLATION_OVERRIDE</option>
              <option value="EXTRACTION_EDIT">EXTRACTION_EDIT</option>
              <option value="SCAN_CREATED">SCAN_CREATED</option>
              <option value="REPORT_GENERATED">REPORT_GENERATED</option>
            </select>
          </div>
        </div>

        <div className="text-xs font-semibold text-slate-500">
          Total Logged Events: <span className="text-slate-900">{total}</span>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-slate-400 text-xs animate-pulse">
            Loading audit events trail...
          </div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center">
            <Clock className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <div className="text-sm font-semibold text-slate-700">No audit records found</div>
            <p className="text-xs text-slate-400 mt-1">Actions taken by officers will appear here in real time.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Action Type</th>
                  <th className="py-3 px-4">Acting Officer / User ID</th>
                  <th className="py-3 px-4">Entity Type &amp; Reference</th>
                  <th className="py-3 px-4 text-right">Details Payload</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                {logs.map((log) => {
                  const isExpanded = expandedId === log.id;
                  return (
                    <React.Fragment key={log.id}>
                      <tr className="hover:bg-slate-50 transition-colors">
                        <td className="py-3 px-4 whitespace-nowrap text-slate-700 font-sans">
                          {new Date(log.created_at).toLocaleString("en-IN", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                          })}
                        </td>

                        <td className="py-3 px-4 whitespace-nowrap">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold border ${getActionBadgeClass(
                              log.action
                            )}`}
                          >
                            {log.action}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-slate-700">
                          {log.user_id ? log.user_id.slice(0, 13) + "..." : "System Automation"}
                        </td>

                        <td className="py-3 px-4 text-slate-600 font-sans">
                          <span className="font-semibold text-slate-800 uppercase text-[10px]">
                            {log.entity_type || "General"}
                          </span>
                          {log.entity_id && (
                            <span className="text-slate-400 font-mono text-[10px] ml-1">
                              ({log.entity_id.slice(0, 8)})
                            </span>
                          )}
                        </td>

                        <td className="py-3 px-4 text-right font-sans">
                          {log.detail ? (
                            <button
                              type="button"
                              onClick={() => toggleExpand(log.id)}
                              className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-700 font-semibold text-xs"
                            >
                              {isExpanded ? (
                                <>
                                  Hide <ChevronUp className="w-3.5 h-3.5" />
                                </>
                              ) : (
                                <>
                                  Inspect <ChevronDown className="w-3.5 h-3.5" />
                                </>
                              )}
                            </button>
                          ) : (
                            <span className="text-slate-400 text-xs">—</span>
                          )}
                        </td>
                      </tr>

                      {/* Expanded JSON details */}
                      {isExpanded && log.detail && (
                        <tr className="bg-slate-50/80">
                          <td colSpan={5} className="py-3 px-6">
                            <div className="bg-slate-900 text-slate-100 p-3 rounded-lg text-[11px] overflow-x-auto shadow-inner">
                              <div className="text-[10px] text-slate-400 font-sans uppercase mb-1 font-bold">
                                Event Payload &amp; Mutation State:
                              </div>
                              <pre className="font-mono">{JSON.stringify(log.detail, null, 2)}</pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
