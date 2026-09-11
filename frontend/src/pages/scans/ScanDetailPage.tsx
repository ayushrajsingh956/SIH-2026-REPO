import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  ArrowLeft,
  Calendar,
  ShieldAlert,
  RefreshCw,
  Camera,
  Layers,
  FileText,
  Loader2,
  Check,
} from "lucide-react";
import { Badge, BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { BboxOverlay, BboxItem } from "@/components/scan/BboxOverlay";
import { PipelineStatusBanner } from "@/components/scan/PipelineStatusBanner";
import { ExtractedFieldsTable } from "@/components/scan/ExtractedFieldsTable";
import { ViolationsAccordion } from "@/components/scan/ViolationsAccordion";
import { apiClient } from "@/services/api";
import { cn } from "@/lib/utils";

export const ScanDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const [selectedImageIndex, setSelectedImageIndex] = useState(0);
  const [selectedField, setSelectedField] = useState<string | null>(null);

  const {
    data: scan,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["scan", id],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/scans/${id}`);
      return res.data;
    },
    enabled: !!id,
    refetchInterval: (query) => {
      // If scan is still processing, poll every 2.5s as fallback
      const status = query.state.data?.status;
      return status === "queued" || status === "processing" ? 2500 : false;
    },
  });

  const [reportSuccessMsg, setReportSuccessMsg] = useState<string | null>(null);

  const generateReportMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post("/api/v1/reports", { scan_id: id });
      return res.data;
    },
    onSuccess: () => {
      setReportSuccessMsg("Report successfully generated!");
      setTimeout(() => setReportSuccessMsg(null), 5000);
      void refetch();
    },
  });

  const handleStatusChange = (newStatus: string) => {
    if (["completed", "needs_review", "failed"].includes(newStatus)) {
      void refetch();
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <Skeleton className="h-9 w-9 rounded-lg" />
          <div className="space-y-2">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-6 space-y-4">
            <Skeleton className="h-[480px] w-full rounded-xl" />
          </div>
          <div className="lg:col-span-6 space-y-4">
            <Skeleton className="h-48 w-full rounded-xl" />
            <Skeleton className="h-64 w-full rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !scan) {
    return (
      <div className="max-w-2xl mx-auto my-12 bg-white rounded-xl border border-slate-200 p-8 text-center shadow-xs">
        <EmptyState
          icon={<ShieldAlert className="w-8 h-8 text-rose-600" />}
          title="Scan Record Not Found"
          description="The requested inspection scan identifier does not exist or you do not have permission to view it."
          action={
            <Link to="/scans">
              <Button variant="outline" size="sm" className="gap-2">
                <ArrowLeft className="w-4 h-4" />
                Back to Scans Repository
              </Button>
            </Link>
          }
        />
      </div>
    );
  }

  // Image list (prefer presigned urls, fallback to raw urls)
  const images = scan.presigned_image_urls?.length
    ? scan.presigned_image_urls
    : scan.image_urls || [];
  const currentImageUrl = images[selectedImageIndex] || "";

  // Prepare BboxItems from extracted fields
  const fields = scan.extraction?.fields || {};
  const bboxItems: BboxItem[] = [];

  Object.entries(fields).forEach(([fieldName, val]: [string, any]) => {
    if (val && Array.isArray(val.bbox) && val.bbox.length === 4) {
      bboxItems.push({
        id: `${fieldName}-bbox`,
        fieldName,
        label: fieldName.replace(/_/g, " "),
        coords: val.bbox,
        confidence: val.confidence,
        rawValue: val.raw,
      });
    }
  });

  // Verdict style mapping
  const verdict = scan.verdict || "needs_review";
  const verdictVariant: BadgeVariant =
    verdict === "compliant"
      ? "compliant"
      : verdict === "non_compliant"
      ? "non_compliant"
      : "needs_review";

  const score = scan.compliance_score !== null && scan.compliance_score !== undefined
    ? Math.round(scan.compliance_score)
    : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-4 sm:p-5 rounded-xl border border-slate-200 shadow-xs">
        <div className="flex items-center gap-3">
          <Link
            to="/scans"
            className="p-2 text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
            title="Back to Scans"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-base sm:text-lg font-bold text-slate-900 font-mono">
                Scan #{scan.id.slice(0, 8)}
              </h1>
              <Badge variant={verdictVariant} size="md">
                {verdict.toUpperCase().replace(/_/g, " ")}
              </Badge>
              <Badge variant="outline" size="sm" className="font-mono uppercase text-slate-600">
                Mode: {scan.mode}
              </Badge>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5" />
                {new Date(scan.scanned_at).toLocaleString()}
              </span>
              <span>&bull;</span>
              <span>Font Check: <span className="font-semibold text-slate-700 capitalize">{scan.font_check_mode.replace(/_/g, " ")}</span></span>
              {scan.surface_area_cm2 && (
                <span>({scan.surface_area_cm2} cm²)</span>
              )}
            </div>
          </div>
        </div>

        {/* Score Card / Actions */}
        <div className="flex items-center gap-3 self-end sm:self-center">
          {score !== null && (
            <div className="flex items-center gap-3 px-4 py-2 bg-slate-50 rounded-xl border border-slate-200">
              <div className="text-right">
                <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                  Compliance Score
                </div>
                <div
                  className={cn(
                    "text-xl font-extrabold font-mono",
                    score >= 90
                      ? "text-emerald-600"
                      : score >= 60
                      ? "text-amber-600"
                      : "text-rose-600"
                  )}
                >
                  {score}/100
                </div>
              </div>
              <div
                className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center text-white text-xs font-bold",
                  score >= 90
                    ? "bg-emerald-600"
                    : score >= 60
                    ? "bg-amber-500"
                    : "bg-rose-600"
                )}
              >
                {score}%
              </div>
            </div>
          )}

          {reportSuccessMsg ? (
            <Link
              to="/reports"
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-lg border border-emerald-300"
            >
              <Check className="w-4 h-4 text-emerald-600" />
              View Generated Reports
            </Link>
          ) : (
            <Button
              variant="primary"
              size="sm"
              onClick={() => generateReportMutation.mutate()}
              disabled={
                generateReportMutation.isPending ||
                (scan.status !== "completed" && scan.status !== "needs_review")
              }
              className="gap-1.5 h-10"
              title="Generate statutory PDF & DOCX inspection notice"
            >
              {generateReportMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <FileText className="w-4 h-4" />
              )}
              <span>{generateReportMutation.isPending ? "Generating..." : "Generate Report"}</span>
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={() => void refetch()}
            title="Refresh scan data"
            className="h-10"
          >
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Live Processing Banner if Queued or Processing */}
      <PipelineStatusBanner
        scanId={scan.id}
        initialStatus={scan.status}
        initialStage={scan.pipeline_meta?.stage || "preprocessing"}
        onStatusChange={handleStatusChange}
      />

      {/* Main 2-Column Split Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT COLUMN: Annotated Image Viewer */}
        <div className="lg:col-span-6 space-y-3">
          {/* Multi-image thumbnail selector */}
          {images.length > 1 && (
            <div className="flex items-center gap-2 p-2 bg-white rounded-xl border border-slate-200 overflow-x-auto shadow-xs">
              <span className="text-[11px] font-semibold text-slate-500 px-2 flex items-center gap-1">
                <Layers className="w-3.5 h-3.5" /> Images:
              </span>
              {images.map((imgUrl: string, idx: number) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setSelectedImageIndex(idx)}
                  className={cn(
                    "relative w-14 h-14 rounded-lg overflow-hidden border-2 flex-shrink-0 transition-all",
                    selectedImageIndex === idx
                      ? "border-blue-600 ring-2 ring-blue-100"
                      : "border-slate-200 opacity-70 hover:opacity-100"
                  )}
                >
                  <img
                    src={imgUrl}
                    alt={`Thumbnail ${idx + 1}`}
                    className="w-full h-full object-cover"
                  />
                  <span className="absolute bottom-0 right-0 bg-slate-900/80 text-white text-[9px] font-mono px-1 rounded-tl">
                    #{idx + 1}
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* Bbox Overlay Component */}
          {currentImageUrl ? (
            <BboxOverlay
              imageUrl={currentImageUrl}
              items={bboxItems}
              selectedField={selectedField}
              onSelectField={setSelectedField}
            />
          ) : (
            <div className="bg-white p-12 text-center rounded-xl border border-slate-200">
              <Camera className="w-8 h-8 text-slate-300 mx-auto mb-2" />
              <p className="text-xs text-slate-500">No packaging image available for this scan.</p>
            </div>
          )}

          {/* Pipeline Metadata Note */}
          {scan.pipeline_meta && (
            <div className="p-3 bg-white rounded-xl border border-slate-200 text-[11px] text-slate-500 flex items-center justify-between shadow-xs">
              <span>
                Model: <span className="font-mono text-slate-700">{scan.pipeline_meta.model || "qwen/qwen3.8-27b"}</span>
              </span>
              {scan.pipeline_meta.durations?.total_ms && (
                <span>
                  Pipeline time: <span className="font-mono text-slate-700">{(scan.pipeline_meta.durations.total_ms / 1000).toFixed(2)}s</span>
                </span>
              )}
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: Extracted Fields & Violations Accordion */}
        <div className="lg:col-span-6 space-y-6">
          {/* Violations Accordion */}
          <ViolationsAccordion
            scanId={scan.id}
            violations={scan.violations || []}
            imageUrl={currentImageUrl}
            onOverrideSuccess={() => void refetch()}
            onSelectField={setSelectedField}
          />

          {/* Extracted Fields Table with Inline Editing */}
          <ExtractedFieldsTable
            scanId={scan.id}
            fields={fields}
            onUpdated={() => void refetch()}
            selectedField={selectedField}
            onSelectField={setSelectedField}
          />
        </div>
      </div>
    </div>
  );
};
