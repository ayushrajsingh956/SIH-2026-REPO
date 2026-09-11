import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Package,
  PlusCircle,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  Clock,
  CheckCircle2,
  Calendar,
  Layers,
} from "lucide-react";
import { Badge, BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiClient } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 15;

export const ScansListPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const canScan = user?.role === "admin" || user?.role === "inspector";

  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [verdictFilter, setVerdictFilter] = useState<string>("all");
  const [modeFilter, setModeFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["scans", page, statusFilter, verdictFilter, modeFilter, searchQuery],
    queryFn: async () => {
      const params: Record<string, any> = {
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      };
      if (statusFilter !== "all") params.status = statusFilter;
      if (verdictFilter !== "all") params.verdict = verdictFilter;
      if (modeFilter !== "all") params.mode = modeFilter;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const res = await apiClient.get("/api/v1/scans", { params });
      return res.data;
    },
  });

  const scans = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / PAGE_SIZE) || 1;
  const filteredScans = scans;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Packaged Commodities Scans</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Repository of all ingested commodity label scans, verification verdicts, and compliance audit records.
          </p>
        </div>
        {canScan && (
          <Link to="/scans/new">
            <Button variant="primary" size="md" className="gap-2 shadow-xs">
              <PlusCircle className="w-4 h-4" />
              New Label Scan
            </Button>
          </Link>
        )}
      </div>

      {/* Filter & Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3">
        {/* Search */}
        <div className="relative min-w-[240px] flex-1 max-w-sm">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search by scan ID or mode..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full text-xs pl-9 pr-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600 bg-slate-50/50"
          />
        </div>

        {/* Dropdown Filters */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Filter */}
          <div className="flex items-center gap-1.5 text-xs text-slate-600">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(0);
              }}
              className="text-xs py-1.5 px-2.5 border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-blue-600 text-slate-700"
            >
              <option value="all">Status: All</option>
              <option value="completed">Completed</option>
              <option value="processing">Processing</option>
              <option value="needs_review">Needs Review</option>
              <option value="queued">Queued</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          {/* Verdict Filter */}
          <select
            value={verdictFilter}
            onChange={(e) => {
              setVerdictFilter(e.target.value);
              setPage(0);
            }}
            className="text-xs py-1.5 px-2.5 border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-blue-600 text-slate-700"
          >
            <option value="all">Verdict: All</option>
            <option value="compliant">Compliant</option>
            <option value="non_compliant">Non-Compliant</option>
            <option value="needs_review">Needs Review</option>
          </select>

          {/* Mode Filter */}
          <select
            value={modeFilter}
            onChange={(e) => {
              setModeFilter(e.target.value);
              setPage(0);
            }}
            className="text-xs py-1.5 px-2.5 border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-blue-600 text-slate-700"
          >
            <option value="all">Mode: All</option>
            <option value="retail">Retail</option>
            <option value="wholesale">Wholesale</option>
            <option value="imported">Imported</option>
            <option value="ecommerce">E-Commerce</option>
          </select>
        </div>
      </div>

      {/* Scans Data Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
        {isLoading ? (
          <div className="p-6 space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : filteredScans.length === 0 ? (
          <div className="p-12">
            <EmptyState
              icon={<Package className="w-8 h-8 text-slate-400" />}
              title="No Scans Found"
              description={
                statusFilter !== "all" || verdictFilter !== "all" || modeFilter !== "all" || searchQuery
                  ? "No scan records match the current filter criteria."
                  : "No commodity scans recorded yet. Initiate your first compliance scan to begin statutory verification."
              }
              action={
                canScan ? (
                  <Link to="/scans/new">
                    <Button variant="primary" size="sm" className="gap-1.5">
                      <PlusCircle className="w-4 h-4" />
                      Create New Scan
                    </Button>
                  </Link>
                ) : undefined
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-4">Scan ID</th>
                  <th className="py-3 px-4">Mode</th>
                  <th className="py-3 px-4">Scanned Date</th>
                  <th className="py-3 px-4">Pipeline Status</th>
                  <th className="py-3 px-4">Statutory Verdict</th>
                  <th className="py-3 px-4 text-center">Score</th>
                  <th className="py-3 px-4 text-center">Violations</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredScans.map((scan: any) => {
                  const verdict = scan.verdict || "needs_review";
                  const verdictVariant: BadgeVariant =
                    verdict === "compliant"
                      ? "compliant"
                      : verdict === "non_compliant"
                      ? "non_compliant"
                      : "needs_review";

                  const score =
                    scan.compliance_score !== null && scan.compliance_score !== undefined
                      ? Math.round(scan.compliance_score)
                      : null;

                  const violationsCount = scan.violations?.length || 0;

                  return (
                    <tr
                      key={scan.id}
                      onClick={() => navigate(`/scans/${scan.id}`)}
                      className="hover:bg-blue-50/40 transition-colors cursor-pointer group"
                    >
                      {/* Scan ID & Photo count */}
                      <td className="py-3 px-4 align-middle">
                        <div className="font-mono font-bold text-slate-900 group-hover:text-blue-600 transition-colors flex items-center gap-2">
                          <span>#{scan.id.slice(0, 8)}</span>
                          {scan.image_urls?.length > 1 && (
                            <span className="text-[10px] text-slate-400 font-normal flex items-center gap-0.5">
                              <Layers className="w-3 h-3" />
                              {scan.image_urls.length}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Mode */}
                      <td className="py-3 px-4 align-middle">
                        <span className="font-medium text-slate-700 capitalize">
                          {scan.mode}
                        </span>
                      </td>

                      {/* Scanned Date */}
                      <td className="py-3 px-4 align-middle text-slate-500 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <Calendar className="w-3.5 h-3.5 text-slate-400" />
                          <span>{new Date(scan.scanned_at).toLocaleDateString()}</span>
                          <span className="text-[10px] text-slate-400">
                            {new Date(scan.scanned_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </span>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="py-3 px-4 align-middle">
                        {scan.status === "processing" ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200 animate-pulse">
                            <Clock className="w-3 h-3 animate-spin text-blue-600" />
                            Processing
                          </span>
                        ) : scan.status === "failed" ? (
                          <Badge variant="critical" size="sm">
                            FAILED
                          </Badge>
                        ) : (
                          <span className="font-mono text-[11px] text-slate-600 uppercase">
                            {scan.status}
                          </span>
                        )}
                      </td>

                      {/* Verdict */}
                      <td className="py-3 px-4 align-middle">
                        {scan.status === "completed" || scan.status === "needs_review" ? (
                          <Badge variant={verdictVariant} size="sm">
                            {verdict.toUpperCase().replace(/_/g, " ")}
                          </Badge>
                        ) : (
                          <span className="text-slate-400 italic text-[11px]">Evaluating...</span>
                        )}
                      </td>

                      {/* Score */}
                      <td className="py-3 px-4 align-middle text-center">
                        {score !== null ? (
                          <span
                            className={cn(
                              "font-mono font-bold text-xs px-2 py-0.5 rounded",
                              score >= 90
                                ? "text-emerald-700 bg-emerald-50"
                                : score >= 60
                                ? "text-amber-700 bg-amber-50"
                                : "text-rose-700 bg-rose-50"
                            )}
                          >
                            {score}%
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>

                      {/* Violations Count */}
                      <td className="py-3 px-4 align-middle text-center">
                        {violationsCount > 0 ? (
                          <span className="inline-flex items-center gap-1 text-rose-700 font-semibold bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200">
                            <AlertTriangle className="w-3 h-3" />
                            {violationsCount}
                          </span>
                        ) : scan.status === "completed" ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3" /> 0
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>

                      {/* Detail action */}
                      <td className="py-3 px-4 align-middle text-right">
                        <Link
                          to={`/scans/${scan.id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="text-xs font-semibold text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          View &rarr;
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 bg-slate-50/50 text-xs text-slate-500">
            <div>
              Showing {page * PAGE_SIZE + 1} to {Math.min((page + 1) * PAGE_SIZE, total)} of {total} scans
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="gap-1 h-8"
              >
                <ChevronLeft className="w-3.5 h-3.5" /> Previous
              </Button>
              <span className="px-2 font-semibold text-slate-700">
                Page {page + 1} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="gap-1 h-8"
              >
                Next <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
