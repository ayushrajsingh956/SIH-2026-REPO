import React, { useState } from "react";
import { Edit2, Check, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { apiClient } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";
import { getFieldColor } from "./BboxOverlay";
import { cn } from "@/lib/utils";

interface ExtractedFieldsTableProps {
  scanId: string;
  fields: Record<string, any>;
  onUpdated?: () => void;
  selectedField?: string | null;
  onSelectField?: (field: string | null) => void;
}

interface EditableFieldState {
  raw: string;
  normalized: string;
}

export const ExtractedFieldsTable: React.FC<ExtractedFieldsTableProps> = ({
  scanId,
  fields,
  onUpdated,
  selectedField,
  onSelectField,
}) => {
  const { user } = useAuthStore();
  const canEdit = user?.role === "admin" || user?.role === "inspector";

  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<EditableFieldState>({ raw: "", normalized: "" });
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Field display list configuration
  const fieldKeys = Object.keys(fields || {});

  const handleStartEdit = (key: string, item: any) => {
    if (!canEdit) return;
    setEditingField(key);
    setEditValues({
      raw: item?.raw ?? (typeof item === "string" ? item : ""),
      normalized:
        item?.normalized ??
        (item?.value !== undefined
          ? `${item.value} ${item.unit || item.currency || ""}`.trim()
          : typeof item === "string"
          ? item
          : ""),
    });
    setError(null);
  };

  const handleCancelEdit = () => {
    setEditingField(null);
    setError(null);
  };

  const handleSaveEdit = async (key: string) => {
    setIsSaving(true);
    setError(null);

    try {
      // Structure patch payload
      const patchData: Record<string, any> = {};
      const current = fields[key] || {};

      patchData[key] = {
        ...current,
        raw: editValues.raw,
        normalized: editValues.normalized,
        // If it's a numeric field like net_quantity or mrp, preserve value if parseable
        ...(current.value !== undefined && {
          value: parseFloat(editValues.normalized) || current.value,
        }),
      };

      await apiClient.patch(`/api/v1/scans/${scanId}/extraction`, {
        fields: patchData,
      });

      setEditingField(null);
      onUpdated?.();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to update field extraction");
    } finally {
      setIsSaving(false);
    }
  };

  // Helper to format confidence
  const renderConfidenceBadge = (confidence?: number) => {
    if (confidence === undefined || confidence === null) return null;
    const pct = Math.round(confidence * 100);
    let variant: "compliant" | "needs_review" | "non_compliant" = "compliant";
    if (confidence < 0.6) variant = "non_compliant";
    else if (confidence < 0.8) variant = "needs_review";

    return (
      <Badge variant={variant} size="sm">
        {pct}%
      </Badge>
    );
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
      <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-slate-50/50">
        <div>
          <h3 className="text-sm font-bold text-slate-900">Extracted Declarations</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            LMPC mandatory declarations parsed via AI vision & verified by rules engine.
          </p>
        </div>
        {canEdit && (
          <span className="text-[11px] font-medium text-blue-600 bg-blue-50 px-2 py-1 rounded-md border border-blue-100 flex items-center gap-1">
            <Edit2 className="w-3 h-3" /> Inline Editing Enabled
          </span>
        )}
      </div>

      {error && (
        <div className="m-4 p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-lg">
          {error}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
              <th className="py-2.5 px-4">Field</th>
              <th className="py-2.5 px-4">Raw Text (OCR)</th>
              <th className="py-2.5 px-4">Normalized Value</th>
              <th className="py-2.5 px-3">Confidence</th>
              <th className="py-2.5 px-3">Source</th>
              {canEdit && <th className="py-2.5 px-3 text-right">Action</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {fieldKeys.map((key) => {
              const item = fields[key];
              const isEditing = editingField === key;
              const isSelected = selectedField === key;
              const color = getFieldColor(key);

              // Extract values
              const rawText = item?.raw ?? (typeof item === "string" ? item : "—");
              let normalizedText =
                item?.normalized ??
                (item?.value !== undefined
                  ? `${item.value} ${item.unit || item.currency || ""}`.trim()
                  : typeof item === "string"
                  ? item
                  : "—");

              if (key === "consumer_care" && item) {
                const parts: string[] = [];
                if (item.phone?.length) parts.push(`Tel: ${item.phone.join(", ")}`);
                if (item.email) parts.push(`Email: ${item.email}`);
                if (item.address) parts.push(`Addr: ${item.address}`);
                if (parts.length) normalizedText = parts.join(" | ");
              }

              return (
                <tr
                  key={key}
                  onClick={() => onSelectField?.(key)}
                  className={cn(
                    "hover:bg-slate-50/80 transition-colors cursor-pointer",
                    isSelected ? "bg-blue-50/50" : ""
                  )}
                >
                  {/* Field Name */}
                  <td className="py-3 px-4 font-semibold text-slate-800 align-top">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: color.stroke }}
                      />
                      <span className="capitalize">{key.replace(/_/g, " ")}</span>
                    </div>
                  </td>

                  {/* Raw Text */}
                  <td className="py-3 px-4 text-slate-600 align-top font-mono text-[11px] max-w-xs break-words">
                    {isEditing ? (
                      <textarea
                        value={editValues.raw}
                        onChange={(e) => setEditValues({ ...editValues, raw: e.target.value })}
                        rows={2}
                        className="w-full text-xs font-mono p-1.5 border border-blue-400 rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-blue-600"
                      />
                    ) : (
                      <span className={rawText === "—" ? "text-slate-400 italic" : ""}>
                        {rawText}
                      </span>
                    )}
                  </td>

                  {/* Normalized Value */}
                  <td className="py-3 px-4 text-slate-900 font-medium align-top max-w-xs break-words">
                    {isEditing ? (
                      <textarea
                        value={editValues.normalized}
                        onChange={(e) =>
                          setEditValues({ ...editValues, normalized: e.target.value })
                        }
                        rows={2}
                        className="w-full text-xs p-1.5 border border-blue-400 rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-blue-600"
                      />
                    ) : (
                      <span className={normalizedText === "—" ? "text-slate-400 italic" : ""}>
                        {normalizedText}
                      </span>
                    )}
                  </td>

                  {/* Confidence Badge */}
                  <td className="py-3 px-3 align-top whitespace-nowrap">
                    {renderConfidenceBadge(item?.confidence)}
                  </td>

                  {/* Source Badge */}
                  <td className="py-3 px-3 align-top whitespace-nowrap">
                    <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                      {item?.source || "ai"}
                    </span>
                  </td>

                  {/* Actions */}
                  {canEdit && (
                    <td className="py-3 px-3 align-top text-right whitespace-nowrap">
                      {isEditing ? (
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            size="sm"
                            variant="primary"
                            isLoading={isSaving}
                            onClick={(e) => {
                              e.stopPropagation();
                              void handleSaveEdit(key);
                            }}
                            title="Save & Re-evaluate"
                            className="h-7 px-2 text-xs"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isSaving}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCancelEdit();
                            }}
                            title="Cancel"
                            className="h-7 px-2 text-xs text-slate-500"
                          >
                            <X className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStartEdit(key, item);
                          }}
                          className="p-1 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                          title="Edit declaration"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
