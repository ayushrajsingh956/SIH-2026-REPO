import React from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldAlert, CheckCircle2, Clock, Upload, ArrowUpRight, Activity } from "lucide-react";
import { apiClient } from "@/services/api";

export const DashboardPage: React.FC = () => {
  const { data: healthData, isLoading: isHealthLoading } = useQuery({
    queryKey: ["healthz"],
    queryFn: async () => {
      const res = await apiClient.get("/healthz");
      return res.data;
    },
    refetchInterval: 15000,
  });

  return (
    <div className="space-y-8">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Compliance Monitoring Overview</h1>
          <p className="text-sm text-slate-500 mt-1">
            Real-time compliance checks under Legal Metrology (Packaged Commodities) Rules, 2011
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold shadow-sm transition-colors">
            <Upload className="w-4 h-4" />
            New Label Scan
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Scans
            </span>
            <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
              <Activity className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">1,248</div>
          <div className="text-xs text-emerald-600 font-medium mt-1 flex items-center gap-1">
            <ArrowUpRight className="w-3.5 h-3.5" /> +12% from last week
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Compliance Rate
            </span>
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">86.4%</div>
          <div className="text-xs text-slate-500 mt-1">Target benchmark: ≥ 90%</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Violations Flagged
            </span>
            <div className="p-2 bg-amber-50 text-amber-600 rounded-lg">
              <ShieldAlert className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">172</div>
          <div className="text-xs text-amber-600 font-medium mt-1">34 high severity</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Pending Reviews
            </span>
            <div className="p-2 bg-purple-50 text-purple-600 rounded-lg">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">19</div>
          <div className="text-xs text-slate-500 mt-1">Awaiting inspector sign-off</div>
        </div>
      </div>

      {/* System Infrastructure Health Panel */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <h2 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-600" />
          Backend & Pipeline Health Status
        </h2>

        {isHealthLoading ? (
          <div className="text-sm text-slate-500 animate-pulse">Checking system dependencies...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg border border-slate-100 bg-slate-50">
              <div className="text-xs font-semibold text-slate-500 uppercase">Database (PostgreSQL)</div>
              <div className="mt-1 flex items-center gap-2">
                <span className={`inline-block w-2.5 h-2.5 rounded-full ${healthData?.dependencies?.database?.status === 'ok' ? 'bg-emerald-500' : 'bg-red-500'}`} />
                <span className="font-semibold text-sm capitalize">
                  {healthData?.dependencies?.database?.status || "Connecting..."}
                </span>
                {healthData?.dependencies?.database?.latency_ms && (
                  <span className="text-xs text-slate-400">({healthData.dependencies.database.latency_ms} ms)</span>
                )}
              </div>
            </div>

            <div className="p-4 rounded-lg border border-slate-100 bg-slate-50">
              <div className="text-xs font-semibold text-slate-500 uppercase">Broker (Redis)</div>
              <div className="mt-1 flex items-center gap-2">
                <span className={`inline-block w-2.5 h-2.5 rounded-full ${healthData?.dependencies?.redis?.status === 'ok' ? 'bg-emerald-500' : 'bg-red-500'}`} />
                <span className="font-semibold text-sm capitalize">
                  {healthData?.dependencies?.redis?.status || "Connecting..."}
                </span>
                {healthData?.dependencies?.redis?.latency_ms && (
                  <span className="text-xs text-slate-400">({healthData.dependencies.redis.latency_ms} ms)</span>
                )}
              </div>
            </div>

            <div className="p-4 rounded-lg border border-slate-100 bg-slate-50">
              <div className="text-xs font-semibold text-slate-500 uppercase">Storage (MinIO / S3)</div>
              <div className="mt-1 flex items-center gap-2">
                <span className={`inline-block w-2.5 h-2.5 rounded-full ${healthData?.dependencies?.storage?.status === 'ok' ? 'bg-emerald-500' : 'bg-red-500'}`} />
                <span className="font-semibold text-sm capitalize">
                  {healthData?.dependencies?.storage?.status || "Connecting..."}
                </span>
                {healthData?.dependencies?.storage?.bucket && (
                  <span className="text-xs text-slate-400">[{healthData.dependencies.storage.bucket}]</span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
