import React, { useEffect, useState } from "react";
import { Download, X, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export const PwaInstallBanner: React.FC = () => {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
    };

    window.addEventListener("beforeinstallprompt", handler);

    return () => {
      window.removeEventListener("beforeinstallprompt", handler);
    };
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") {
      setDeferredPrompt(null);
    }
  };

  if (!deferredPrompt || dismissed) {
    return null;
  }

  return (
    <div className="bg-slate-900 text-white px-4 py-2.5 flex items-center justify-between gap-3 text-xs shadow-md border-b border-slate-800 z-50">
      <div className="flex items-center gap-2">
        <div className="bg-blue-600 p-1.5 rounded-md flex-shrink-0">
          <ShieldCheck className="w-4 h-4 text-white" />
        </div>
        <div>
          <span className="font-bold text-slate-100 block">Install LegalMetro Shield App</span>
          <span className="text-[11px] text-slate-400">
            For field officers: instant camera access, offline inspection queueing, and home screen launch.
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        <Button
          variant="primary"
          size="sm"
          onClick={() => void handleInstall()}
          className="gap-1 bg-blue-600 hover:bg-blue-500 text-xs py-1 h-7"
        >
          <Download className="w-3.5 h-3.5" />
          Install App
        </Button>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="p-1 text-slate-400 hover:text-white rounded"
          title="Dismiss banner"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
