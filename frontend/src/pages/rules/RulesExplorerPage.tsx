import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  AlertOctagon,
  AlertTriangle,
  Info,
  ChevronRight,
  X,
  ExternalLink,
  History,
} from "lucide-react";
import { apiClient } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

export const RulesExplorerPage: React.FC = () => {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const isAdmin = user?.role === "admin";

  const [selectedRuleCode, setSelectedRuleCode] = useState<string | null>(null);

  // 1. Fetch Rules
  const { data: rules, isLoading } = useQuery({
    queryKey: ["rules"],
    queryFn: async () => {
      const res = await apiClient.get("/api/v1/rules");
      return res.data;
    },
  });

  // 2. Fetch Selected Rule Recent Scans
  const { data: recentScans, isLoading: isRecentLoading } = useQuery({
    queryKey: ["rules", selectedRuleCode, "recent-scans"],
    queryFn: async () => {
      if (!selectedRuleCode) return [];
      const res = await apiClient.get(`/api/v1/rules/${selectedRuleCode}/recent-scans?limit=10`);
      return res.data;
    },
    enabled: !!selectedRuleCode,
  });

  // 3. Admin Rule Toggle Mutation
  const toggleMutation = useMutation({
    mutationFn: async ({ code, is_enabled }: { code: string; is_enabled: boolean }) => {
      const res = await apiClient.put(`/api/v1/admin/rules/${code}`, { is_enabled });
      return res.data;
    },
    onMutate: async ({ code, is_enabled }) => {
      await queryClient.cancelQueries({ queryKey: ["rules"] });
      const previousRules = queryClient.getQueryData(["rules"]);

      queryClient.setQueryData(["rules"], (old: any) => {
        if (!old) return [];
        return old.map((r: any) => (r.id === code ? { ...r, is_enabled } : r));
      });

      return { previousRules };
    },
    onError: (_err, _variables, context: any) => {
      if (context?.previousRules) {
        queryClient.setQueryData(["rules"], context.previousRules);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
    },
  });

  const selectedRule = rules?.find((r: any) => r.id === selectedRuleCode);

  const renderSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
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
    <div className="space-y-6 relative">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-600" />
            Legal Metrology (Packaged Commodities) Statutory Rules
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Encoded deterministic compliance rulebook under LMPC Rules, 2011 with live enforcement trigger metrics.
          </p>
        </div>

        <div className="text-xs text-slate-500 font-medium">
          Total Rules Encoded: <strong className="text-slate-900">{rules?.length || 0}</strong>
        </div>
      </div>

      {/* Rules Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-slate-400 text-xs animate-pulse">
            Loading statutory rules repository...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">Rule Code & Title</th>
                  <th className="py-3 px-4">Statutory Legal Citation</th>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4 hidden md:table-cell">Applies To</th>
                  <th className="py-3 px-4 text-right">Triggers</th>
                  <th className="py-3 px-4 text-center">Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rules?.map((r: any) => (
                  <tr
                    key={r.id}
                    onClick={() => setSelectedRuleCode(r.id)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-900">{r.id}</div>
                      <div className="text-xs text-slate-700 mt-0.5">{r.title}</div>
                      <div className="text-[11px] text-slate-400 mt-0.5 line-clamp-1 max-w-sm">
                        {r.description_plain}
                      </div>
                    </td>
                    <td className="py-3 px-4 font-serif text-[11px] text-slate-700 max-w-xs">
                      {r.citation}
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      {renderSeverityBadge(r.effective_severity)}
                    </td>
                    <td className="py-3 px-4 hidden md:table-cell">
                      <div className="flex flex-wrap gap-1">
                        {r.applies_to?.map((m: string) => (
                          <span
                            key={m}
                            className="capitalize text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600"
                          >
                            {m}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right font-extrabold text-slate-900">
                      {r.trigger_count?.toLocaleString() || 0}
                    </td>
                    <td className="py-3 px-4 text-center" onClick={(e) => e.stopPropagation()}>
                      {isAdmin ? (
                        <button
                          onClick={() =>
                            toggleMutation.mutate({ code: r.id, is_enabled: !r.is_enabled })
                          }
                          className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                            r.is_enabled ? "bg-blue-600" : "bg-slate-300"
                          }`}
                        >
                          <span
                            className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                              r.is_enabled ? "translate-x-4" : "translate-x-0"
                            }`}
                          />
                        </button>
                      ) : (
                        <span
                          className={`inline-flex items-center gap-1 text-[11px] font-semibold ${
                            r.is_enabled ? "text-emerald-700" : "text-slate-400"
                          }`}
                        >
                          {r.is_enabled ? "Enabled" : "Disabled"}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800">
                        Details
                        <ChevronRight className="w-3.5 h-3.5" />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Slide-over Rule Detail Drawer */}
      {selectedRule && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/40 backdrop-blur-xs flex justify-end">
          <div className="w-full max-w-lg bg-white h-full shadow-2xl flex flex-col overflow-y-auto animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-200 flex items-start justify-between bg-slate-50">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-extrabold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                    {selectedRule.id}
                  </span>
                  {renderSeverityBadge(selectedRule.effective_severity)}
                </div>
                <h2 className="text-base font-bold text-slate-900 mt-2">{selectedRule.title}</h2>
              </div>
              <button
                onClick={() => setSelectedRuleCode(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="p-6 space-y-6 flex-1 text-xs">
              {/* Statutory Legal Citation */}
              <div className="space-y-1.5 bg-amber-50/50 p-4 rounded-xl border border-amber-200">
                <div className="text-[11px] font-bold text-amber-800 uppercase tracking-wider">
                  Verbatim Statutory Citation
                </div>
                <div className="text-xs font-serif text-slate-800 italic">
                  "{selectedRule.citation}"
                </div>
              </div>

              {/* Plain Language Explanation */}
              <div className="space-y-1.5">
                <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                  Requirement Description
                </div>
                <p className="text-slate-700 leading-relaxed">{selectedRule.description_plain}</p>
              </div>

              {/* Check Type & Technical Metadata */}
              <div className="grid grid-cols-2 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-100">
                <div>
                  <div className="text-[10px] font-semibold text-slate-400 uppercase">Check Algorithm</div>
                  <div className="font-mono font-bold text-slate-800 mt-0.5">{selectedRule.check}</div>
                </div>
                <div>
                  <div className="text-[10px] font-semibold text-slate-400 uppercase">Total Violations</div>
                  <div className="font-bold text-slate-800 mt-0.5">{selectedRule.trigger_count}</div>
                </div>
                {selectedRule.thresholds && (
                  <div className="col-span-2 pt-2 border-t border-slate-200">
                    <div className="text-[10px] font-semibold text-slate-400 uppercase">Custom Thresholds</div>
                    <pre className="font-mono text-[10px] bg-slate-100 p-2 rounded mt-1 overflow-x-auto">
                      {JSON.stringify(selectedRule.thresholds, null, 2)}
                    </pre>
                  </div>
                )}
              </div>

              {/* Recent Scans Triggering This Rule */}
              <div className="space-y-3 pt-2">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-slate-900 flex items-center gap-1.5">
                    <History className="w-4 h-4 text-blue-600" />
                    Recent Non-Compliant Scans
                  </h3>
                  <span className="text-[11px] text-slate-400">Past 90 Days</span>
                </div>

                {isRecentLoading ? (
                  <div className="p-6 text-center text-slate-400 text-xs animate-pulse">
                    Retrieving recent infractions...
                  </div>
                ) : recentScans && recentScans.length > 0 ? (
                  <div className="space-y-2.5">
                    {recentScans.map((s: any) => (
                      <div
                        key={s.violation_id}
                        className="bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-900 truncate">
                            {s.product_name || "Label Inspection"}
                          </span>
                          <Link
                            to={`/scans/${s.scan_id}`}
                            className="inline-flex items-center gap-1 font-semibold text-blue-600 hover:underline"
                          >
                            Scan
                            <ExternalLink className="w-3 h-3" />
                          </Link>
                        </div>
                        {s.observed_value && (
                          <div className="text-[11px] text-red-700 truncate">
                            <strong>Observed:</strong> {s.observed_value}
                          </div>
                        )}
                        <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-200">
                          <span>{s.inspector_name || "Inspector"}</span>
                          <span>{new Date(s.scanned_at).toLocaleDateString("en-IN")}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-6 text-center text-slate-400 text-xs bg-slate-50 rounded-lg border border-dashed border-slate-200">
                    No recent scans have triggered this rule.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
