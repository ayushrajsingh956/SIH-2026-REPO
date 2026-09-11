import React, { useEffect, useState, useRef } from "react";
import { CheckCircle2, Loader2, AlertCircle } from "lucide-react";
import { apiClient } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";
import { cn } from "@/lib/utils";

interface PipelineStatusBannerProps {
  scanId: string;
  initialStatus: string;
  initialStage?: string;
  onStatusChange?: (status: string, payload?: any) => void;
}

interface Step {
  id: string;
  label: string;
  description: string;
}

const PIPELINE_STEPS: Step[] = [
  { id: "preprocessing", label: "Preprocess", description: "Deskew, denoise & contrast normalization" },
  { id: "extracting", label: "Extract", description: "Multi-tier Vision AI & Statutory OCR" },
  { id: "validating", label: "Validate", description: "LMPC Rules 2011 deterministic checks" },
  { id: "scoring", label: "Score", description: "Compliance rating & verdict calculation" },
];

export const PipelineStatusBanner: React.FC<PipelineStatusBannerProps> = ({
  scanId,
  initialStatus,
  initialStage = "preprocessing",
  onStatusChange,
}) => {
  const [currentStatus, setCurrentStatus] = useState<string>(initialStatus);
  const [currentStage, setCurrentStage] = useState<string>(initialStage);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollingTimerRef = useRef<any>(null);

  // Derive step index (0-3)
  const getActiveStepIndex = () => {
    if (currentStatus === "completed" || currentStatus === "needs_review") return 4;
    if (currentStatus === "failed") return -1;
    if (currentStage === "extracting") return 1;
    if (currentStage === "validating") return 2;
    if (currentStage === "scoring") return 3;
    return 0; // preprocessing or queued
  };

  const activeStepIdx = getActiveStepIndex();

  useEffect(() => {
    setCurrentStatus(initialStatus);
  }, [initialStatus]);

  useEffect(() => {
    if (currentStatus === "completed" || currentStatus === "needs_review" || currentStatus === "failed") {
      return;
    }

    let isSubscribed = true;

    // Build WebSocket URL with auth token
    const token = useAuthStore.getState().accessToken;
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : "";
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    // If running with Vite dev server proxy or standalone API url:
    const apiBase = import.meta.env.VITE_API_BASE_URL || "";
    let wsUrl: string;
    if (apiBase.startsWith("http")) {
      const parsed = new URL(apiBase);
      const wsProto = parsed.protocol === "https:" ? "wss:" : "ws:";
      wsUrl = `${wsProto}//${parsed.host}/api/v1/scans/${scanId}/events${tokenParam}`;
    } else {
      wsUrl = `${protocol}//${host}/api/v1/scans/${scanId}/events${tokenParam}`;
    }

    const startPolling = () => {
      if (pollingTimerRef.current) return;
      pollingTimerRef.current = setInterval(async () => {
        try {
          const res = await apiClient.get(`/api/v1/scans/${scanId}`);
          if (!isSubscribed) return;
          const scan = res.data;
          if (scan.status !== currentStatus) {
            setCurrentStatus(scan.status);
            if (scan.pipeline_meta?.stage) {
              setCurrentStage(scan.pipeline_meta.stage);
            }
            onStatusChange?.(scan.status, scan);
          }
          if (["completed", "needs_review", "failed"].includes(scan.status)) {
            clearInterval(pollingTimerRef.current);
            pollingTimerRef.current = null;
          }
        } catch {
          // ignore transient poll error
        }
      }, 2000);
    };

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data);
          if (payload.status) {
            setCurrentStatus(payload.status);
          }
          if (payload.stage) {
            setCurrentStage(payload.stage);
          }
          if (payload.error) {
            setErrorMessage(payload.error);
          }
          onStatusChange?.(payload.status, payload);

          if (["completed", "needs_review", "failed"].includes(payload.status)) {
            ws.close();
          }
        } catch {
          // payload parsing error
        }
      };

      ws.onerror = () => {
        startPolling();
      };

      ws.onclose = () => {
        if (["queued", "processing"].includes(currentStatus)) {
          startPolling();
        }
      };
    } catch {
      startPolling();
    }

    return () => {
      isSubscribed = false;
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
      }
    };
  }, [scanId, currentStatus, onStatusChange]);

  if (currentStatus === "completed" || currentStatus === "needs_review") {
    return null;
  }

  if (currentStatus === "failed") {
    return (
      <div className="bg-rose-50 border border-rose-200 p-4 rounded-xl flex items-start gap-3 shadow-sm">
        <AlertCircle className="w-5 h-5 text-rose-600 mt-0.5 flex-shrink-0" />
        <div>
          <h4 className="text-sm font-bold text-rose-900">Pipeline Execution Failed</h4>
          <p className="text-xs text-rose-700 mt-1">
            {errorMessage || "The compliance pipeline encountered an unrecoverable error during processing."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="pipeline-status-banner"
      className="bg-white border border-blue-200 rounded-xl p-5 shadow-sm space-y-4"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-blue-50 text-blue-600 rounded-lg animate-spin">
            <Loader2 className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              Compliance Analysis In Progress
              <span className="inline-block w-2 h-2 rounded-full bg-blue-600 animate-ping" />
            </h3>
            <p className="text-xs text-slate-500">
              Processing packaged commodity label through LMPC 2011 inspection pipeline.
            </p>
          </div>
        </div>
        <div className="text-xs font-mono font-semibold text-blue-700 bg-blue-50 px-3 py-1 rounded-full border border-blue-100 self-start sm:self-center">
          Status: {currentStatus.toUpperCase()}
        </div>
      </div>

      {/* Step Indicator */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2">
        {PIPELINE_STEPS.map((step, idx) => {
          const isDone = activeStepIdx > idx;
          const isActive = activeStepIdx === idx;

          return (
            <div
              key={step.id}
              className={cn(
                "p-3 rounded-lg border text-left transition-all",
                isDone
                  ? "bg-emerald-50/60 border-emerald-200 text-slate-800"
                  : isActive
                  ? "bg-blue-50 border-blue-300 ring-1 ring-blue-400 text-blue-900 shadow-sm"
                  : "bg-slate-50 border-slate-200 text-slate-400 opacity-60"
              )}
            >
              <div className="flex items-center gap-2">
                {isDone ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                ) : isActive ? (
                  <Loader2 className="w-4 h-4 text-blue-600 animate-spin flex-shrink-0" />
                ) : (
                  <div className="w-4 h-4 rounded-full border border-slate-300 flex items-center justify-center text-[10px] font-mono text-slate-400 flex-shrink-0">
                    {idx + 1}
                  </div>
                )}
                <span className="text-xs font-bold">{step.label}</span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1 leading-snug line-clamp-2">
                {step.description}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
