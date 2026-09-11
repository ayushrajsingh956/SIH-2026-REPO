import React, { useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ShieldCheck,
  FileCheck,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import { Badge, BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiClient } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";
import { cn } from "@/lib/utils";

export interface ViolationItem {
  id: string;
  scan_id: string;
  rule_code: string;
  rule_title: string;
  citation: string;
  severity: "critical" | "major" | "minor" | "advisory";
  field_name: string;
  observed_value?: string | null;
  expected_value?: string | null;
  bbox?: number[] | Record<string, any> | null;
  overridden?: boolean;
  override_reason?: string | null;
}

interface ViolationsAccordionProps {
  scanId: string;
  violations: ViolationItem[];
  imageUrl?: string;
  onOverrideSuccess?: () => void;
  onSelectField?: (field: string) => void;
}

export const ViolationsAccordion: React.FC<ViolationsAccordionProps> = ({
  scanId,
  violations,
  imageUrl,
  onOverrideSuccess,
  onSelectField,
}) => {
  const { user } = useAuthStore();
  const canOverride = user?.role === "admin" || user?.role === "inspector";

  const [expandedId, setExpandedId] = useState<string | null>(violations[0]?.id || null);
  const [overrideModalViolation, setOverrideModalViolation] = useState<ViolationItem | null>(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [isSubmittingOverride, setIsSubmittingOverride] = useState(false);
  const [overrideError, setOverrideError] = useState<string | null>(null);

  const toggleItem = (id: string) => {
    setExpandedId((curr) => (curr === id ? null : id));
  };

  const handleOpenOverride = (violation: ViolationItem) => {
    setOverrideModalViolation(violation);
    setOverrideReason("");
    setOverrideError(null);
  };

  const handleConfirmOverride = async () => {
    if (!overrideModalViolation) return;
    if (overrideReason.trim().length < 5) {
      setOverrideError("Please provide a written justification of at least 5 characters.");
      return;
    }

    setIsSubmittingOverride(true);
    setOverrideError(null);

    try {
      await apiClient.post(
        `/api/v1/scans/${scanId}/violations/${overrideModalViolation.id}/override`,
        { reason: overrideReason.trim() }
      );
      setOverrideModalViolation(null);
      onOverrideSuccess?.();
    } catch (err: any) {
      setOverrideError(err?.response?.data?.detail || "Failed to record inspector override.");
    } finally {
      setIsSubmittingOverride(false);
    }
  };

  if (!violations || violations.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        <EmptyState
          icon={<ShieldCheck className="w-8 h-8 text-emerald-600" />}
          title="Full Statutory Compliance"
          description="No rule violations detected. All declarations satisfy the Legal Metrology (Packaged Commodities) Rules, 2011."
        />
      </div>
    );
  }

  // Count summary
  const activeCount = violations.filter((v) => !v.overridden).length;
  const overriddenCount = violations.filter((v) => v.overridden).length;

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm space-y-0">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-slate-50/50">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-600" />
          <h3 className="text-sm font-bold text-slate-900">
            Identified Violations ({activeCount})
          </h3>
          {overriddenCount > 0 && (
            <span className="text-xs text-slate-500 font-medium">
              ({overriddenCount} overridden)
            </span>
          )}
        </div>
        <span className="text-[11px] text-slate-500 font-mono">
          Deterministic Rules Engine
        </span>
      </div>

      {/* Violations List */}
      <div className="divide-y divide-slate-100">
        {violations.map((violation) => {
          const isExpanded = expandedId === violation.id;
          const isOverridden = !!violation.overridden;

          // Severity variant mapping
          const severityVariant: BadgeVariant =
            violation.severity === "critical"
              ? "critical"
              : violation.severity === "major"
              ? "major"
              : violation.severity === "minor"
              ? "minor"
              : "advisory";

          return (
            <div
              key={violation.id}
              className={cn(
                "transition-colors",
                isOverridden ? "bg-slate-50/60 opacity-80" : isExpanded ? "bg-slate-50/30" : "bg-white"
              )}
            >
              {/* Accordion Trigger Header */}
              <button
                type="button"
                onClick={() => toggleItem(violation.id)}
                className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-50 transition-colors focus:outline-none focus-visible:bg-slate-50"
                aria-expanded={isExpanded}
              >
                <div className="flex items-start sm:items-center gap-3">
                  <Badge variant={severityVariant} size="sm">
                    {violation.severity.toUpperCase()}
                  </Badge>
                  <div>
                    <span className="text-xs font-bold text-slate-900 block sm:inline mr-2">
                      {violation.rule_title}
                    </span>
                    <span className="text-[11px] text-slate-500 font-mono">
                      {violation.citation}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-3 flex-shrink-0 ml-2">
                  {isOverridden ? (
                    <Badge variant="outline" size="sm" className="bg-slate-100 text-slate-600 font-medium">
                      Overridden
                    </Badge>
                  ) : null}
                  <ChevronDown
                    className={cn(
                      "w-4 h-4 text-slate-400 transition-transform duration-200",
                      isExpanded ? "rotate-180 text-slate-700" : ""
                    )}
                  />
                </div>
              </button>

              {/* Accordion Body Content */}
              {isExpanded && (
                <div className="px-4 pb-4 pt-1 space-y-4 text-xs border-t border-slate-100 bg-white/50">
                  {/* Field & Citation metadata */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <div>
                      <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                        Impacted Declaration Field
                      </span>
                      <button
                        type="button"
                        onClick={() => onSelectField?.(violation.field_name)}
                        className="text-xs font-bold text-blue-600 hover:underline capitalize flex items-center gap-1 mt-0.5"
                      >
                        {violation.field_name.replace(/_/g, " ")}
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    </div>
                    <div>
                      <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                        Statutory Reference
                      </span>
                      <span className="text-xs font-medium text-slate-800 font-serif">
                        {violation.citation}
                      </span>
                    </div>
                  </div>

                  {/* Observed vs Expected Comparison Card */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="p-3 bg-rose-50/60 border border-rose-200 rounded-lg">
                      <span className="text-[10px] font-bold text-rose-700 uppercase tracking-wider block">
                        Observed On Package
                      </span>
                      <p className="text-xs font-mono text-rose-900 mt-1 font-semibold break-words">
                        {violation.observed_value || "Declaration absent / Not found"}
                      </p>
                    </div>

                    <div className="p-3 bg-emerald-50/60 border border-emerald-200 rounded-lg">
                      <span className="text-[10px] font-bold text-emerald-700 uppercase tracking-wider block">
                        Statutory Mandate
                      </span>
                      <p className="text-xs font-medium text-emerald-900 mt-1 break-words">
                        {violation.expected_value || "Valid declaration compliant with Rule specifications"}
                      </p>
                    </div>
                  </div>

                  {/* Evidence Thumbnail if Image is present */}
                  {imageUrl && (
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center gap-3">
                      <div className="relative w-14 h-14 rounded border border-slate-300 overflow-hidden bg-slate-900 flex-shrink-0">
                        <img
                          src={imageUrl}
                          alt="Evidence region"
                          className="w-full h-full object-cover"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                          Evidence Region
                        </span>
                        <button
                          type="button"
                          onClick={() => onSelectField?.(violation.field_name)}
                          className="text-xs text-blue-600 hover:underline font-semibold flex items-center gap-1 mt-0.5"
                        >
                          Focus in Bounding Box Viewer &rarr;
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Overridden state note or override button */}
                  {isOverridden ? (
                    <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900 text-xs">
                      <div className="font-bold flex items-center gap-1.5 mb-1">
                        <CheckCircle2 className="w-4 h-4 text-amber-600" />
                        Officer Override Applied
                      </div>
                      <p className="text-[11px] text-amber-800 italic">
                        "{violation.override_reason}"
                      </p>
                    </div>
                  ) : (
                    canOverride && (
                      <div className="flex justify-end pt-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleOpenOverride(violation)}
                          className="text-xs text-slate-700 hover:text-slate-900 border-slate-300"
                        >
                          <FileCheck className="w-3.5 h-3.5 mr-1.5 text-blue-600" />
                          Apply Inspector Override
                        </Button>
                      </div>
                    )
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Override Dialog Modal */}
      <Dialog
        open={!!overrideModalViolation}
        onClose={() => setOverrideModalViolation(null)}
        title="Inspector Violation Override"
        description="Provide a formal written regulatory justification for overriding this violation. This action is permanently recorded in the audit trail."
      >
        <div className="space-y-4">
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1">
            <div className="font-bold text-slate-800">
              {overrideModalViolation?.rule_title}
            </div>
            <div className="text-slate-500 font-mono">
              {overrideModalViolation?.citation}
            </div>
          </div>

          {overrideError && (
            <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-lg">
              {overrideError}
            </div>
          )}

          <div className="space-y-1.5">
            <label
              htmlFor="override-reason"
              className="text-xs font-semibold text-slate-700 block"
            >
              Justification / Exemption Reference <span className="text-rose-500">*</span>
            </label>
            <textarea
              id="override-reason"
              rows={4}
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="e.g. Manufacturer possesses certified exemption under Rule 26 for export surplus, verified with DoCA order ref #..."
              className="w-full text-xs p-3 border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 placeholder:text-slate-400"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOverrideModalViolation(null)}
              disabled={isSubmittingOverride}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              isLoading={isSubmittingOverride}
              onClick={() => void handleConfirmOverride()}
            >
              Confirm Override & Recalculate
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
};
