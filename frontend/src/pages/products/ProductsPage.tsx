import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  Search,
  Package,
  Barcode,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  ChevronRight,
} from "lucide-react";
import { apiClient } from "@/services/api";

export const ProductsPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");

  // Debounce search input by 300ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchTerm);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const { data, isLoading } = useQuery({
    queryKey: ["products", debouncedQuery],
    queryFn: async () => {
      const url = debouncedQuery.trim()
        ? `/api/v1/products?q=${encodeURIComponent(debouncedQuery.trim())}&limit=250`
        : `/api/v1/products?limit=250`;
      const res = await apiClient.get(url);
      return res.data;
    },
  });

  const products = data?.items || [];
  const total = data?.total || 0;

  // Virtualization for large lists (> 200 items)
  const parentRef = useRef<HTMLDivElement>(null);
  const shouldVirtualize = products.length > 200;

  const rowVirtualizer = useVirtualizer({
    count: products.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 56,
    overscan: 10,
    enabled: shouldVirtualize,
  });

  const renderBadge = (badge: string) => {
    switch (badge) {
      case "compliant":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <ShieldCheck className="w-3 h-3" />
            Compliant
          </span>
        );
      case "non_compliant":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-50 text-red-700 border border-red-200">
            <ShieldAlert className="w-3 h-3" />
            Non-Compliant
          </span>
        );
      case "needs_review":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3 h-3" />
            Needs Review
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-600">
            Unscanned
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Package className="w-5 h-5 text-blue-600" />
            Packaged Commodities Repository
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Full-text search & trigram indexed database of scanned packaged goods with violation history.
          </p>
        </div>

        <div className="text-xs text-slate-500 font-medium">
          Total Indexed: <span className="font-bold text-slate-900">{total} commodities</span>
        </div>
      </div>

      {/* Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search by product name, brand, manufacturer, or barcode/GTIN..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        {searchTerm && (
          <button
            onClick={() => setSearchTerm("")}
            className="text-xs font-semibold text-slate-400 hover:text-slate-600 px-2"
          >
            Clear
          </button>
        )}
      </div>

      {/* Products Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-slate-400 text-xs animate-pulse">
            Searching commodities catalog...
          </div>
        ) : products.length === 0 ? (
          <div className="p-12 text-center">
            <Package className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <div className="text-sm font-semibold text-slate-700">No commodities match your query</div>
            <p className="text-xs text-slate-400 mt-1">
              Try searching with a broader brand name, category, or barcode.
            </p>
          </div>
        ) : shouldVirtualize ? (
          /* Virtualized view if > 200 items */
          <div
            ref={parentRef}
            className="h-[600px] overflow-auto divide-y divide-slate-100"
          >
            <div
              style={{
                height: `${rowVirtualizer.getTotalSize()}px`,
                width: "100%",
                position: "relative",
              }}
            >
              {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                const p = products[virtualRow.index];
                return (
                  <div
                    key={p.id}
                    onClick={() => navigate(`/products/${p.id}`)}
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
                    <div className="flex-1 min-w-0 pr-4">
                      <div className="font-semibold text-slate-900 truncate">{p.name}</div>
                      <div className="text-[11px] text-slate-400 truncate">
                        {p.brand} · {p.manufacturer_name}
                      </div>
                    </div>
                    <div className="w-36 hidden sm:block text-slate-500 font-mono text-[11px]">
                      {p.barcode || "—"}
                    </div>
                    <div className="w-28 text-center">{renderBadge(p.compliance_badge)}</div>
                    <div className="w-24 text-right font-medium text-slate-600">
                      {p.total_scans} scans
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-400 ml-2" />
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* Standard high-density table */
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">Commodity Name & Brand</th>
                  <th className="py-3 px-4 hidden sm:table-cell">Manufacturer</th>
                  <th className="py-3 px-4 hidden md:table-cell">Barcode / GTIN</th>
                  <th className="py-3 px-4 text-center">Status</th>
                  <th className="py-3 px-4 text-right">Scans</th>
                  <th className="py-3 px-4 hidden lg:table-cell text-right">Last Scanned</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {products.map((p: any) => (
                  <tr
                    key={p.id}
                    onClick={() => navigate(`/products/${p.id}`)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-900">{p.name}</div>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        {p.brand} {p.category ? `· ${p.category}` : ""}
                      </div>
                    </td>
                    <td className="py-3 px-4 hidden sm:table-cell text-slate-600">
                      {p.manufacturer_name || "—"}
                    </td>
                    <td className="py-3 px-4 hidden md:table-cell font-mono text-[11px] text-slate-500">
                      {p.barcode ? (
                        <span className="flex items-center gap-1">
                          <Barcode className="w-3.5 h-3.5 text-slate-400" />
                          {p.barcode}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-3 px-4 text-center">{renderBadge(p.compliance_badge)}</td>
                    <td className="py-3 px-4 text-right font-semibold text-slate-900">
                      {p.total_scans}
                    </td>
                    <td className="py-3 px-4 hidden lg:table-cell text-right text-slate-400 text-[11px]">
                      {p.last_scanned_at
                        ? new Date(p.last_scanned_at).toLocaleDateString("en-IN", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })
                        : "Never"}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800">
                        History
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
    </div>
  );
};
