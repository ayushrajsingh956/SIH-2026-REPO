import React, { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useDropzone } from "react-dropzone";
import {
  Upload,
  Globe,
  Camera,
  X,
  AlertCircle,
  HelpCircle,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { apiClient } from "@/services/api";
import { cn } from "@/lib/utils";
import { enqueuePendingScan, fileToOutboxFile } from "@/services/outbox";

interface PreviewFile {
  file: File;
  previewUrl: string;
  id: string;
}

export const NewScanPage: React.FC = () => {
  const navigate = useNavigate();

  // Tab State: "upload" | "url"
  const [activeTab, setActiveTab] = useState<"upload" | "url">("upload");

  // Form State
  const [files, setFiles] = useState<PreviewFile[]>([]);
  const [listingUrl, setListingUrl] = useState("");
  const [scanMode, setScanMode] = useState<"retail" | "wholesale" | "imported" | "ecommerce">("retail");
  const [fontCheckMode, setFontCheckMode] = useState<"relative" | "surface_area" | "reference_object">("relative");
  const [surfaceArea, setSurfaceArea] = useState<string>("");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [offlineQueued, setOfflineQueued] = useState(false);

  const cameraInputRef = useRef<HTMLInputElement>(null);

  // react-dropzone configuration
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      "image/jpeg": [".jpg", ".jpeg"],
      "image/png": [".png"],
      "image/webp": [".webp"],
    },
    maxFiles: 6,
    maxSize: 10 * 1024 * 1024, // 10MB
    onDrop: (acceptedFiles, rejectedFiles) => {
      setFormError(null);

      if (rejectedFiles.length > 0) {
        const firstRejection = rejectedFiles[0];
        if (firstRejection.errors.some((e) => e.code === "file-too-large")) {
          setFormError("One or more images exceed the 10MB size limit.");
          return;
        }
        if (firstRejection.errors.some((e) => e.code === "file-invalid-type")) {
          setFormError("Only JPEG, PNG, or WebP images are permitted.");
          return;
        }
      }

      const availableSlots = 6 - files.length;
      if (acceptedFiles.length > availableSlots) {
        setFormError(`You can attach at most 6 photos per scan. Only adding first ${availableSlots}.`);
      }

      const newPreviewItems: PreviewFile[] = acceptedFiles
        .slice(0, availableSlots)
        .map((f) => ({
          file: f,
          previewUrl: URL.createObjectURL(f),
          id: `${f.name}-${Date.now()}-${Math.random()}`,
        }));

      setFiles((prev) => [...prev, ...newPreviewItems]);
    },
  });

  const handleRemoveFile = (id: string, previewUrl: string) => {
    URL.revokeObjectURL(previewUrl);
    setFiles((prev) => prev.filter((item) => item.id !== id));
  };

  const handleCameraCapture = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const capturedFile = e.target.files[0];
      if (files.length >= 6) {
        setFormError("Maximum 6 images reached.");
        return;
      }
      const newPreview: PreviewFile = {
        file: capturedFile,
        previewUrl: URL.createObjectURL(capturedFile),
        id: `${capturedFile.name}-${Date.now()}`,
      };
      setFiles((prev) => [...prev, newPreview]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    // Validation
    if (activeTab === "upload") {
      if (files.length === 0) {
        setFormError("Please upload at least one photograph of the packaged commodity label.");
        return;
      }
    } else {
      if (!listingUrl.trim()) {
        setFormError("Please enter a valid e-commerce product URL.");
        return;
      }
      try {
        const parsed = new URL(listingUrl.trim());
        if (!["http:", "https:"].includes(parsed.protocol)) {
          throw new Error();
        }
      } catch {
        setFormError("Invalid URL. Must begin with http:// or https://");
        return;
      }
    }

    // Validate conditional surface area
    let parsedSurfaceArea: number | null = null;
    if (fontCheckMode === "surface_area") {
      if (!surfaceArea.trim()) {
        setFormError("Surface area is required when Font Check Mode is set to 'Package Surface Area'.");
        return;
      }
      parsedSurfaceArea = parseFloat(surfaceArea);
      if (isNaN(parsedSurfaceArea) || parsedSurfaceArea < 5 || parsedSurfaceArea > 50000) {
        setFormError("Package surface area must be a valid number between 5 cm² and 50,000 cm².");
        return;
      }
    }

    // Offline outbox queue for field officers in areas with low or no connectivity
    if (activeTab === "upload" && typeof navigator !== "undefined" && !navigator.onLine) {
      try {
        setIsSubmitting(true);
        const outboxFiles = await Promise.all(files.map((f) => fileToOutboxFile(f.file)));
        await enqueuePendingScan({
          files: outboxFiles,
          mode: scanMode,
          fontCheckMode,
          surfaceAreaCm2: parsedSurfaceArea,
        });
        setOfflineQueued(true);
        setFiles([]);
        return;
      } catch (queueErr: any) {
        setFormError("Failed to save scan to offline queue: " + (queueErr.message || queueErr));
        return;
      } finally {
        setIsSubmitting(false);
      }
    }

    setIsSubmitting(true);

    try {
      let scanId: string;

      if (activeTab === "upload") {
        const formData = new FormData();
        files.forEach((f) => {
          formData.append("images", f.file);
        });
        formData.append("mode", scanMode);
        formData.append("font_check_mode", fontCheckMode);
        if (parsedSurfaceArea !== null) {
          formData.append("surface_area_cm2", parsedSurfaceArea.toString());
        }

        const response = await apiClient.post("/api/v1/scans", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        scanId = response.data.scan_id;
      } else {
        const response = await apiClient.post("/api/v1/scans/url", {
          url: listingUrl.trim(),
          font_check_mode: fontCheckMode,
          surface_area_cm2: parsedSurfaceArea,
        });
        scanId = response.data.scan_id;
      }

      // Optimistic navigation to scan detail view with live progress
      navigate(`/scans/${scanId}`);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setFormError(
        typeof detail === "string"
          ? detail
          : "Failed to initiate compliance scan. Please verify inputs."
      );
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-900">Initiate Compliance Scan</h1>
        <p className="text-xs text-slate-500 mt-1">
          Upload physical packaging photos or provide an e-commerce URL for automated LMPC Rule 2011 verification.
        </p>
      </div>

      {offlineQueued && (
        <div className="p-4 bg-emerald-50 border border-emerald-300 rounded-xl flex items-start justify-between gap-3 shadow-xs">
          <div className="flex items-start gap-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
            <div>
              <div className="text-sm font-bold text-emerald-900">Scan Saved to Offline Outbox</div>
              <p className="text-xs text-emerald-700 mt-0.5">
                Your packaging photos and configuration were safely recorded locally in IndexedDB. As soon as connectivity restores, the system will automatically upload and process this scan through the AI rules pipeline.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOfflineQueued(false)}
            className="text-emerald-800 border-emerald-300 hover:bg-emerald-100 text-xs"
          >
            Scan Another
          </Button>
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-slate-200 p-1 shadow-xs flex max-w-md">
        <button
          type="button"
          onClick={() => {
            setActiveTab("upload");
            setFormError(null);
          }}
          className={cn(
            "flex-1 flex items-center justify-center gap-2 py-2 text-xs font-bold rounded-lg transition-colors",
            activeTab === "upload"
              ? "bg-blue-600 text-white shadow-xs"
              : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
          )}
        >
          <Upload className="w-4 h-4" />
          Physical Photo Upload
        </button>
        <button
          type="button"
          onClick={() => {
            setActiveTab("url");
            setScanMode("ecommerce");
            setFormError(null);
          }}
          className={cn(
            "flex-1 flex items-center justify-center gap-2 py-2 text-xs font-bold rounded-lg transition-colors",
            activeTab === "url"
              ? "bg-blue-600 text-white shadow-xs"
              : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
          )}
        >
          <Globe className="w-4 h-4" />
          E-Commerce Listing URL
        </button>
      </div>

      {formError && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 text-rose-600 mt-0.5 flex-shrink-0" />
          <span>{formError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate className="space-y-6">
        {/* Upload Mode Area */}
        {activeTab === "upload" ? (
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-slate-900">Commodity Label Photographs</h2>
                <p className="text-xs text-slate-500">
                  Attach up to 6 clear photographs capturing all declared packaging panels (MRP, Net Qty, Mfg).
                </p>
              </div>

              {/* Mobile Camera Button */}
              <div className="flex items-center gap-2">
                <input
                  ref={cameraInputRef}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={handleCameraCapture}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => cameraInputRef.current?.click()}
                  className="gap-1.5 text-xs text-blue-600 border-blue-200 hover:bg-blue-50"
                >
                  <Camera className="w-4 h-4" />
                  Take Photo (Mobile)
                </Button>
              </div>
            </div>

            {/* Drag & Drop Zone */}
            <div
              {...getRootProps()}
              className={cn(
                "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors flex flex-col items-center justify-center",
                isDragActive
                  ? "border-blue-500 bg-blue-50/50"
                  : "border-slate-300 hover:border-blue-400 bg-slate-50/50"
              )}
            >
              <input {...getInputProps()} />
              <div className="p-3 bg-white text-blue-600 rounded-full shadow-xs border border-slate-200 mb-3">
                <Upload className="w-6 h-6" />
              </div>
              <p className="text-xs font-semibold text-slate-800">
                Drag and drop label photographs here, or <span className="text-blue-600 underline">browse files</span>
              </p>
              <p className="text-[11px] text-slate-400 mt-1">
                JPEG, PNG, WebP up to 10MB each &bull; Max 6 photos per scan
              </p>
            </div>

            {/* Thumbnail Previews Grid */}
            {files.length > 0 && (
              <div className="space-y-2 pt-2">
                <div className="text-xs font-semibold text-slate-700">
                  Selected Images ({files.length} of 6):
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
                  {files.map((item, idx) => (
                    <div
                      key={item.id}
                      className="group relative rounded-lg overflow-hidden border border-slate-200 bg-slate-100 aspect-square flex items-center justify-center"
                    >
                      <img
                        src={item.previewUrl}
                        alt={`Upload #${idx + 1}`}
                        className="w-full h-full object-cover"
                      />
                      <span className="absolute top-1 left-1 bg-slate-900/80 text-white text-[9px] font-mono px-1.5 py-0.5 rounded">
                        #{idx + 1}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleRemoveFile(item.id, item.previewUrl)}
                        className="absolute top-1 right-1 bg-rose-600 hover:bg-rose-700 text-white p-1 rounded-full shadow-sm transition-opacity opacity-90 hover:opacity-100"
                        title="Remove photo"
                      >
                        <X className="w-3 h-3" />
                      </button>
                      <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/70 to-transparent p-1">
                        <p className="text-[9px] text-white truncate px-1">
                          {(item.file.size / (1024 * 1024)).toFixed(1)} MB
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Listing URL Mode Area */
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900">E-Commerce Product Listing URL</h2>
              <p className="text-xs text-slate-500">
                Provide public e-commerce URL (e.g. Amazon, Flipkart, Blinkit, Zepto, BigBasket). Images are securely retrieved with SSRF protection.
              </p>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="listing-url" className="text-xs font-semibold text-slate-700 block">
                Product URL <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <Globe className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  id="listing-url"
                  type="url"
                  value={listingUrl}
                  onChange={(e) => setListingUrl(e.target.value)}
                  placeholder="https://www.amazon.in/dp/B08N5WRWNW..."
                  className="w-full text-xs pl-9 pr-3 py-2.5 border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 placeholder:text-slate-400"
                />
              </div>
              <p className="text-[11px] text-slate-400">
                Rule 6 amendment requires online marketplaces to display all mandatory declarations on digital listings.
              </p>
            </div>
          </div>
        )}

        {/* Scan Parameters & Font Check Configuration */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-5">
          <h2 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-3">
            Inspection Parameters & Verification Mode
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Packaging / Distribution Mode */}
            <div className="space-y-1.5">
              <label htmlFor="scan-mode" className="text-xs font-semibold text-slate-700 block">
                Commodity Category Mode
              </label>
              <select
                id="scan-mode"
                value={scanMode}
                onChange={(e) => setScanMode(e.target.value as any)}
                className="w-full text-xs p-2.5 border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                <option value="retail">Retail Packaged Commodity (Rule 6 general)</option>
                <option value="wholesale">Wholesale Package (Rule 24 exemptions)</option>
                <option value="imported">Imported Commodity (Importer + Country of Origin)</option>
                <option value="ecommerce">E-Commerce Marketplace Listing</option>
              </select>
              <p className="text-[11px] text-slate-400">
                Controls statutory rule applicability matrices under LMPC 2011.
              </p>
            </div>

            {/* Font-Check Mode */}
            <div className="space-y-1.5">
              <label htmlFor="font-check-mode" className="text-xs font-semibold text-slate-700 block">
                Font Size Verification Strategy
              </label>
              <select
                id="font-check-mode"
                value={fontCheckMode}
                onChange={(e) => setFontCheckMode(e.target.value as any)}
                className="w-full text-xs p-2.5 border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                <option value="relative">Relative Mode — Rule 9(5) size-class comparison (Recommended)</option>
                <option value="surface_area">Package Surface Area — Exact cm² calculation</option>
                <option value="reference_object">In-Frame Reference Object (Card/Coin scale)</option>
              </select>
              <p className="text-[11px] text-slate-400">
                Rule 9(5) prescribes minimum numeral heights (1mm to 6mm) relative to package area.
              </p>
            </div>
          </div>

          {/* Conditional Surface Area Input */}
          {fontCheckMode === "surface_area" && (
            <div className="p-4 bg-blue-50/60 border border-blue-200 rounded-xl space-y-2 animate-in fade-in-0 duration-200">
              <div className="flex items-center gap-1.5 text-xs font-bold text-blue-900">
                <HelpCircle className="w-4 h-4 text-blue-600" />
                <span>Package Principal Display Surface Area</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="relative max-w-xs">
                  <input
                    id="surface-area"
                    type="number"
                    step="0.1"
                    min="5"
                    max="50000"
                    value={surfaceArea}
                    onChange={(e) => setSurfaceArea(e.target.value)}
                    placeholder="e.g. 150.0"
                    className="w-full text-xs p-2.5 border border-blue-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 pr-12 font-mono"
                  />
                  <span className="absolute right-3 top-2.5 text-xs text-slate-400 font-semibold">
                    cm²
                  </span>
                </div>
                <span className="text-[11px] text-slate-500">
                  Acceptable range: 5 cm² to 50,000 cm²
                </span>
              </div>
              <p className="text-[11px] text-slate-600">
                Formula: Height &times; Width for rectangular surfaces, or 40% &times; Height &times; Circumference for cylindrical containers.
              </p>
            </div>
          )}
        </div>

        {/* Submit Actions */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate("/scans")}
            disabled={isSubmitting}
          >
            Cancel
          </Button>

          <Button
            type="submit"
            variant="primary"
            size="lg"
            isLoading={isSubmitting}
            className="px-8 shadow-sm"
          >
            Submit for Statutory Verification
          </Button>
        </div>
      </form>
    </div>
  );
};
