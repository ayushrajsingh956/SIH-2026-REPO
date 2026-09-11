import React from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Barcode,
  ShieldAlert,
  History,
  Clock,
  User,
  ExternalLink,
} from "lucide-react";
import { apiClient } from "@/services/api";

export const ProductDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["product-scans", id],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/products/${id}/scans`);
      return res.data;
    },
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="p-12 text-center text-slate-400 text-xs animate-pulse">
        Loading commodity profile and audit history...
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-8 bg-white rounded-xl border border-red-200 text-center">
        <ShieldAlert className="w-10 h-10 text-red-500 mx-auto mb-2" />
        <div className="text-sm font-bold text-slate-900">Commodity Record Not Found</div>
        <p className="text-xs text-slate-500 mt-1">
          Unable to locate commodity with identifier: {id}
        </p>
        <button
          onClick={() => navigate("/products")}
          className="mt-4 px-4 py-1.5 text-xs font-semibold bg-blue-600 text-white rounded-lg"
        >
          Return to Products Catalog
        </button>
      </div>
    );
  }

  const { product, scans, is_repeat_offender, recurrent_violations } = data;

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <div>
        <Link
          to="/products"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Commodities Repository
        </Link>
      </div>

      {/* Product Overview Header Card */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-bold text-slate-900">{product.name}</h1>
              {is_repeat_offender && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-600 text-white animate-pulse">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  Repeat Offender
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500 flex-wrap">
              {product.brand && (
                <span>
                  Brand: <strong className="text-slate-700">{product.brand}</strong>
                </span>
              )}
              {product.category && (
                <span>
                  Category: <strong className="text-slate-700">{product.category}</strong>
                </span>
              )}
              {product.barcode && (
                <span className="flex items-center gap-1 font-mono">
                  <Barcode className="w-3.5 h-3.5 text-slate-400" />
                  {product.barcode}
                </span>
              )}
            </div>
            {product.manufacturer_name && (
              <div className="text-xs text-slate-500">
                Packer / Manufacturer: <span className="text-slate-700">{product.manufacturer_name}</span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-6 bg-slate-50 p-4 rounded-lg border border-slate-100 shrink-0">
            <div>
              <div className="text-[11px] font-semibold text-slate-400 uppercase">Total Scans</div>
              <div className="text-xl font-extrabold text-slate-900">{product.total_scans}</div>
            </div>
            <div className="w-px h-8 bg-slate-200" />
            <div>
              <div className="text-[11px] font-semibold text-slate-400 uppercase">Compliance Rate</div>
              <div
                className={`text-xl font-extrabold ${
                  product.compliance_rate >= 90
                    ? "text-emerald-600"
                    : product.compliance_rate >= 75
                    ? "text-amber-600"
                    : "text-red-600"
                }`}
              >
                {product.compliance_rate}%
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Repeat Offender & Violation Recurrence Panel */}
      {is_repeat_offender && (
        <div className="bg-red-50/60 border-2 border-red-200 rounded-xl p-5 shadow-xs">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-red-100 text-red-700 rounded-lg shrink-0">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div className="space-y-2 flex-1">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-red-900">
                  Statutory Violation Recurrence Alert (Repeat Offender)
                </h2>
                <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-red-200 text-red-900">
                  Multiple Infractions
                </span>
              </div>
              <p className="text-xs text-red-800">
                This packaged commodity has repeatedly failed automated LMPC compliance verification on the same statutory rules across multiple distinct inspection scans.
              </p>

              <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                {recurrent_violations.map((rv: any) => (
                  <div
                    key={rv.rule_code}
                    className="bg-white p-3.5 rounded-lg border border-red-200 shadow-2xs space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-red-700">{rv.rule_code}</span>
                      <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-red-100 text-red-800">
                        {rv.count} Repeat Citations
                      </span>
                    </div>
                    <div className="text-xs font-semibold text-slate-800">{rv.rule_title}</div>
                    <div className="text-[11px] text-slate-500">{rv.citation}</div>
                    <div className="text-[11px] text-slate-400 pt-1">
                      Detected across {rv.scan_ids.length} unique inspection scans.
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Vertical Scan Timeline */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
        <h2 className="text-sm font-bold text-slate-900 mb-6 flex items-center gap-2">
          <History className="w-4 h-4 text-blue-600" />
          Chronological Inspection & Scan Timeline
        </h2>

        {scans.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs">
            No inspection scans recorded yet for this commodity.
          </div>
        ) : (
          <div className="relative border-l-2 border-slate-200 ml-4 pl-6 space-y-8">
            {scans.map((s: any, idx: number) => {
              const isCompliant = s.verdict === "compliant";
              const isNonCompliant = s.verdict === "non_compliant";

              return (
                <div key={s.id} className="relative group">
                  {/* Timeline Node Icon */}
                  <span
                    className={`absolute -left-[31px] top-1 w-4 h-4 rounded-full border-2 border-white ring-2 ${
                      isCompliant
                        ? "bg-emerald-500 ring-emerald-200"
                        : isNonCompliant
                        ? "bg-red-500 ring-red-200"
                        : "bg-amber-500 ring-amber-200"
                    }`}
                  />

                  {/* Scan Event Card */}
                  <div className="bg-slate-50 hover:bg-slate-100/80 p-4 rounded-xl border border-slate-200 transition-colors">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-700">
                          Scan #{scans.length - idx}
                        </span>
                        <span className="capitalize px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-200 text-slate-700">
                          {s.mode}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                            isCompliant
                              ? "bg-emerald-100 text-emerald-800"
                              : isNonCompliant
                              ? "bg-red-100 text-red-800"
                              : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {s.verdict ? s.verdict.toUpperCase().replace("_", " ") : s.status.toUpperCase()}
                        </span>
                      </div>

                      <div className="flex items-center gap-3 text-xs">
                        {s.compliance_score !== null && (
                          <span className="font-bold text-slate-800">
                            Score: {s.compliance_score} / 100
                          </span>
                        )}
                        <Link
                          to={`/scans/${s.id}`}
                          className="inline-flex items-center gap-1 font-semibold text-blue-600 hover:underline"
                        >
                          Scan Details
                          <ExternalLink className="w-3 h-3" />
                        </Link>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 mt-2 text-[11px] text-slate-400">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        {new Date(s.scanned_at).toLocaleString("en-IN")}
                      </span>
                      {s.inspector_name && (
                        <span className="flex items-center gap-1">
                          <User className="w-3.5 h-3.5" />
                          {s.inspector_name}
                        </span>
                      )}
                    </div>

                    {/* Violations during this scan */}
                    {s.violations && s.violations.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-200 space-y-1.5">
                        <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                          Statutory Citations ({s.violations.length}):
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {s.violations.map((v: any) => (
                            <span
                              key={v.id}
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border ${
                                v.overridden
                                  ? "bg-slate-100 text-slate-500 line-through border-slate-200"
                                  : v.severity === "critical"
                                  ? "bg-red-50 text-red-700 border-red-200 font-semibold"
                                  : "bg-amber-50 text-amber-800 border-amber-200"
                              }`}
                            >
                              {v.rule_code} · {v.rule_title}
                              {v.overridden && " (Overridden)"}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
