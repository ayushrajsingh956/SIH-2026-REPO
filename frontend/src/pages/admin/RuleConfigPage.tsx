import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Scale,
  Search,
  Filter,
  RefreshCw,
  CheckCircle2,
  AlertOctagon,
  SlidersHorizontal,
} from "lucide-react";
import { apiClient } from "@/services/api";
import { Badge, BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface RuleItem {
  id: string;
  title: string;
  citation: string;
  severity: string;
  effective_severity: string;
  applies_to: string[];
  check: string;
  params: Record<string, any>;
  description_plain: string;
  mandatory: boolean;
  is_enabled: boolean;
  severity_override: string | null;
  thresholds: Record<string, any> | null;
  trigger_count: number;
}

export const RuleConfigPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [modeFilter, setModeFilter] = useState<string>("");

  const { data: rules = [], isLoading, refetch, isFetching } = useQuery<RuleItem[]>({
    queryKey: ["admin-rules"],
    queryFn: async () => {
      const res = await apiClient.get("/api/v1/rules");
      return res.data;
    },
  });

  // Mutation to update rule config
  const updateRuleMutation = useMutation({
    mutationFn: async ({
      code,
      isEnabled,
      severityOverride,
    }: {
      code: string;
      isEnabled?: boolean;
      severityOverride?: string | null;
    }) => {
      const payload: Record<string, any> = {};
      if (isEnabled !== undefined) payload.is_enabled = isEnabled;
      if (severityOverride !== undefined) payload.severity_override = severityOverride;

      const res = await apiClient.put(`/api/v1/admin/rules/${code}`, payload);
      return res.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-rules"] });
      void queryClient.invalidateQueries({ queryKey: ["rules"] });
    },
  });

  const filteredRules = rules.filter((r) => {
    const matchesSearch =
      !searchQuery.trim() ||
      r.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.citation.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesSeverity = !severityFilter || r.effective_severity === severityFilter;
    const matchesMode = !modeFilter || r.applies_to.includes(modeFilter);

    return matchesSearch && matchesSeverity && matchesMode;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <SlidersHorizontal className="w-5 h-5 text-blue-600" />
            Statutory Rules Engine Configuration
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Enable or disable legal metrology checks and configure statutory severity overrides in real time without redeploying.
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
            Refresh Rules
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-3 flex-1 min-w-[280px]">
          <div className="relative flex-1 max-w-sm">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search rule code, title, or statutory citation..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg border border-slate-200 text-xs focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 outline-none"
            />
          </div>

          <div className="flex items-center gap-1.5 text-slate-600">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-xs text-slate-700 outline-none focus:border-blue-500"
            >
              <option value="">All Severities</option>
              <option value="critical">Critical</option>
              <option value="major">Major</option>
              <option value="minor">Minor</option>
              <option value="advisory">Advisory</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5 text-slate-600">
            <select
              value={modeFilter}
              onChange={(e) => setModeFilter(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-xs text-slate-700 outline-none focus:border-blue-500"
            >
              <option value="">All Package Modes</option>
              <option value="retail">Retail</option>
              <option value="wholesale">Wholesale</option>
              <option value="imported">Imported</option>
              <option value="ecommerce">E-Commerce</option>
            </select>
          </div>
        </div>

        <div className="text-xs font-semibold text-slate-500">
          Showing <span className="text-slate-900">{filteredRules.length}</span> of{" "}
          <span className="text-slate-900">{rules.length}</span> rules
        </div>
      </div>

      {/* Rules Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-slate-400 text-xs animate-pulse">
            Loading rules engine registry...
          </div>
        ) : filteredRules.length === 0 ? (
          <div className="p-12 text-center">
            <Scale className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <div className="text-sm font-semibold text-slate-700">No matching rules found</div>
            <p className="text-xs text-slate-400 mt-1">Adjust search terms or severity filter.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">Rule Code &amp; Title</th>
                  <th className="py-3 px-4">Statutory Citation</th>
                  <th className="py-3 px-4 text-center">Active Status</th>
                  <th className="py-3 px-4">Severity Configuration</th>
                  <th className="py-3 px-4 text-center">Triggers</th>
                  <th className="py-3 px-4 text-right">Switch Toggle</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredRules.map((rule) => (
                  <tr key={rule.id} className="hover:bg-slate-50 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-mono font-bold text-slate-900">{rule.id}</div>
                      <div className="text-slate-700 font-semibold text-[11px] mt-0.5">{rule.title}</div>
                      <div className="text-slate-500 text-[10px] mt-1 max-w-md line-clamp-2">
                        {rule.description_plain}
                      </div>
                    </td>

                    <td className="py-3 px-4">
                      <span className="font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded text-[11px] border border-blue-200">
                        {rule.citation}
                      </span>
                    </td>

                    <td className="py-3 px-4 text-center">
                      {rule.is_enabled ? (
                        <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full text-[10px] font-bold border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3" />
                          ENABLED
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full text-[10px] font-bold border border-rose-200">
                          <AlertOctagon className="w-3 h-3" />
                          DISABLED
                        </span>
                      )}
                    </td>

                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <Badge variant={rule.effective_severity as BadgeVariant} size="sm">
                          {rule.effective_severity.toUpperCase()}
                        </Badge>
                        <select
                          value={rule.severity_override || ""}
                          onChange={(e) =>
                            updateRuleMutation.mutate({
                              code: rule.id,
                              severityOverride: e.target.value || null,
                            })
                          }
                          disabled={updateRuleMutation.isPending}
                          className="text-[11px] border border-slate-200 rounded px-2 py-0.5 bg-white text-slate-700 focus:outline-none focus:border-blue-500"
                        >
                          <option value="">Default ({rule.severity})</option>
                          <option value="critical">Critical</option>
                          <option value="major">Major</option>
                          <option value="minor">Minor</option>
                          <option value="advisory">Advisory</option>
                        </select>
                      </div>
                    </td>

                    <td className="py-3 px-4 text-center font-mono font-bold text-slate-800">
                      {rule.trigger_count}
                    </td>

                    <td className="py-3 px-4 text-right">
                      <button
                        type="button"
                        onClick={() =>
                          updateRuleMutation.mutate({
                            code: rule.id,
                            isEnabled: !rule.is_enabled,
                          })
                        }
                        disabled={updateRuleMutation.isPending}
                        className={`text-xs font-semibold px-2.5 py-1 rounded transition-colors border ${
                          rule.is_enabled
                            ? "text-rose-600 hover:bg-rose-50 border-rose-200 bg-white"
                            : "text-emerald-700 hover:bg-emerald-50 border-emerald-300 bg-emerald-50/50"
                        }`}
                      >
                        {rule.is_enabled ? "Disable Rule" : "Enable Rule"}
                      </button>
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
