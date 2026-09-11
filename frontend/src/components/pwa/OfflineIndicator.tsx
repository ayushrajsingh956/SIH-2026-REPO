import React, { useEffect, useState } from "react";
import { Wifi, WifiOff, RefreshCw, UploadCloud } from "lucide-react";
import { subscribeOutboxChanges, syncOutbox } from "@/services/outbox";

export const OfflineIndicator: React.FC = () => {
  const [isOnline, setIsOnline] = useState(
    typeof navigator !== "undefined" ? navigator.onLine : true
  );
  const [outboxCount, setOutboxCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      void handleSync();
    };
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    const unsubscribe = subscribeOutboxChanges((count) => {
      setOutboxCount(count);
    });

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      unsubscribe();
    };
  }, []);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await syncOutbox();
    } finally {
      setIsSyncing(false);
    }
  };

  if (isOnline && outboxCount === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 px-3 py-1 rounded-lg text-xs font-semibold shadow-xs border transition-all">
      {!isOnline ? (
        <span className="inline-flex items-center gap-1.5 text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
          <WifiOff className="w-3.5 h-3.5 text-amber-600" />
          <span>Offline Mode</span>
        </span>
      ) : (
        <span className="inline-flex items-center gap-1.5 text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
          <Wifi className="w-3.5 h-3.5 text-emerald-600" />
          <span>Connected</span>
        </span>
      )}

      {outboxCount > 0 && (
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-slate-600">
            <strong>{outboxCount}</strong> scan{outboxCount > 1 ? "s" : ""} queued
          </span>
          {isOnline && (
            <button
              type="button"
              onClick={() => void handleSync()}
              disabled={isSyncing}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 text-[11px] transition-colors"
            >
              {isSyncing ? (
                <RefreshCw className="w-3 h-3 animate-spin" />
              ) : (
                <UploadCloud className="w-3 h-3" />
              )}
              <span>Sync</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
};
