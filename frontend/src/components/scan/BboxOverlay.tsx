import React, { useState, useRef, useEffect, useCallback } from "react";
import { ZoomIn, ZoomOut, RotateCcw, Eye, EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";

export interface BboxItem {
  id: string;
  fieldName: string;
  label?: string;
  coords: number[]; // [ymin, xmin, ymax, xmax] in 0-1000 scale or [x1, y1, x2, y2]
  confidence?: number;
  rawValue?: string;
  color?: string;
}

interface BboxOverlayProps {
  imageUrl: string;
  altText?: string;
  items: BboxItem[];
  selectedField?: string | null;
  onSelectField?: (field: string | null) => void;
  className?: string;
}

// Canonical field color assignments
// eslint-disable-next-line react-refresh/only-export-components
export const FIELD_COLORS: Record<string, { stroke: string; fill: string; badge: string }> = {
  mrp: { stroke: "#10b981", fill: "rgba(16, 185, 129, 0.2)", badge: "bg-emerald-100 text-emerald-800 border-emerald-300" },
  net_quantity: { stroke: "#3b82f6", fill: "rgba(59, 130, 246, 0.2)", badge: "bg-blue-100 text-blue-800 border-blue-300" },
  mfg_date: { stroke: "#f59e0b", fill: "rgba(245, 158, 11, 0.2)", badge: "bg-amber-100 text-amber-800 border-amber-300" },
  expiry_date: { stroke: "#d97706", fill: "rgba(217, 119, 6, 0.2)", badge: "bg-amber-200 text-amber-900 border-amber-400" },
  manufacturer_name: { stroke: "#8b5cf6", fill: "rgba(139, 92, 246, 0.2)", badge: "bg-purple-100 text-purple-800 border-purple-300" },
  manufacturer_address: { stroke: "#a855f7", fill: "rgba(168, 85, 247, 0.2)", badge: "bg-purple-50 text-purple-700 border-purple-200" },
  importer_name: { stroke: "#ec4899", fill: "rgba(236, 72, 153, 0.2)", badge: "bg-pink-100 text-pink-800 border-pink-300" },
  importer_address: { stroke: "#f43f5e", fill: "rgba(244, 63, 94, 0.2)", badge: "bg-rose-100 text-rose-800 border-rose-300" },
  country_of_origin: { stroke: "#14b8a6", fill: "rgba(20, 184, 166, 0.2)", badge: "bg-teal-100 text-teal-800 border-teal-300" },
  consumer_care: { stroke: "#06b6d4", fill: "rgba(6, 182, 212, 0.2)", badge: "bg-cyan-100 text-cyan-800 border-cyan-300" },
  generic_name: { stroke: "#6366f1", fill: "rgba(99, 102, 241, 0.2)", badge: "bg-indigo-100 text-indigo-800 border-indigo-300" },
  default: { stroke: "#64748b", fill: "rgba(100, 116, 139, 0.2)", badge: "bg-slate-100 text-slate-800 border-slate-300" },
};

// eslint-disable-next-line react-refresh/only-export-components
export const getFieldColor = (fieldName: string) => {
  return FIELD_COLORS[fieldName] || FIELD_COLORS.default;
};

export const BboxOverlay: React.FC<BboxOverlayProps> = ({
  imageUrl,
  altText = "Packaged commodity label",
  items,
  selectedField,
  onSelectField,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  // Layout & image render metrics
  const [imageRect, setImageRect] = useState<{ width: number; height: number; top: number; left: number }>({
    width: 0,
    height: 0,
    top: 0,
    left: 0,
  });

  // Zoom & Pan State
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // Field visibility toggles
  const [visibleFields, setVisibleFields] = useState<Record<string, boolean>>({});
  const [hoveredBox, setHoveredBox] = useState<BboxItem | null>(null);

  // Initialize all fields to visible when items change
  useEffect(() => {
    const initial: Record<string, boolean> = {};
    items.forEach((item) => {
      if (item.coords && item.coords.length === 4) {
        initial[item.fieldName] = true;
      }
    });
    setVisibleFields(initial);
  }, [items]);

  // Compute rendered image geometry within container using ResizeObserver
  const updateImageRect = useCallback(() => {
    if (!imageRef.current || !containerRef.current) return;
    const img = imageRef.current;
    const container = containerRef.current;

    const cWidth = container.clientWidth;
    const cHeight = container.clientHeight;
    const naturalWidth = img.naturalWidth || 1;
    const naturalHeight = img.naturalHeight || 1;

    // Calculate 'contain' fit rect
    const containerAspect = cWidth / (cHeight || 1);
    const imageAspect = naturalWidth / naturalHeight;

    let renderedWidth: number;
    let renderedHeight: number;
    let offsetX = 0;
    let offsetY = 0;

    if (imageAspect > containerAspect) {
      renderedWidth = cWidth;
      renderedHeight = cWidth / imageAspect;
      offsetY = (cHeight - renderedHeight) / 2;
    } else {
      renderedHeight = cHeight;
      renderedWidth = cHeight * imageAspect;
      offsetX = (cWidth - renderedWidth) / 2;
    }

    setImageRect({
      width: renderedWidth,
      height: renderedHeight,
      left: offsetX,
      top: offsetY,
    });
  }, []);

  useEffect(() => {
    updateImageRect();
    const handleResize = () => updateImageRect();
    window.addEventListener("resize", handleResize);

    const ro = new ResizeObserver(() => updateImageRect());
    if (containerRef.current) {
      ro.observe(containerRef.current);
    }

    return () => {
      window.removeEventListener("resize", handleResize);
      ro.disconnect();
    };
  }, [updateImageRect]);

  // Zoom controls
  const handleZoomIn = () => setZoom((z) => Math.min(3, +(z + 0.25).toFixed(2)));
  const handleZoomOut = () =>
    setZoom((z) => {
      const next = Math.max(1, +(z - 0.25).toFixed(2));
      if (next === 1) setPan({ x: 0, y: 0 });
      return next;
    });
  const handleResetZoom = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // Pan controls
  const handleMouseDown = (e: React.MouseEvent) => {
    if (zoom <= 1) return;
    setIsPanning(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning || zoom <= 1) return;
    setPan({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => setIsPanning(false);

  // Per-field toggle
  const toggleField = (fieldName: string) => {
    setVisibleFields((prev) => ({
      ...prev,
      [fieldName]: !prev[fieldName],
    }));
  };

  const toggleAll = (show: boolean) => {
    const updated: Record<string, boolean> = {};
    items.forEach((item) => {
      updated[item.fieldName] = show;
    });
    setVisibleFields(updated);
  };

  // Convert coords to percentage-based box [ymin, xmin, ymax, xmax]
  const normalizeCoords = (coords: number[]) => {
    if (!coords || coords.length !== 4) return null;
    let [ymin, xmin, ymax, xmax] = coords;

    // Check if coords are in 0-1000 scale vs 0-1 scale
    const isScale1000 = Math.max(ymin, xmin, ymax, xmax) > 1.0;
    if (isScale1000) {
      ymin = ymin / 1000;
      xmin = xmin / 1000;
      ymax = ymax / 1000;
      xmax = xmax / 1000;
    }

    const top = Math.max(0, ymin);
    const left = Math.max(0, xmin);
    const width = Math.min(1 - left, xmax - xmin);
    const height = Math.min(1 - top, ymax - ymin);

    return { top, left, width, height };
  };

  // Unique fields with valid bboxes for toggle bar
  const validItems = items.filter(
    (item) => item.coords && item.coords.length === 4 && (item.coords[2] > item.coords[0] || item.coords[3] > item.coords[1])
  );
  const uniqueFields = Array.from(new Set(validItems.map((i) => i.fieldName)));

  return (
    <div className={cn("flex flex-col bg-slate-900 rounded-xl overflow-hidden border border-slate-700 shadow-md", className)}>
      {/* Viewer Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 bg-slate-950/80 border-b border-slate-800 text-xs text-slate-300">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-200">Bounding Box Overlays</span>
          <span className="text-slate-500">|</span>
          <span className="text-[11px] text-slate-400">
            {validItems.filter((i) => visibleFields[i.fieldName]).length} of {validItems.length} active
          </span>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1 bg-slate-900 rounded-lg p-1 border border-slate-800">
          <button
            type="button"
            onClick={handleZoomOut}
            disabled={zoom <= 1}
            title="Zoom Out"
            className="p-1 hover:bg-slate-800 rounded disabled:opacity-40 transition-colors text-slate-300"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <span className="px-1.5 text-[11px] font-mono min-w-[3rem] text-center text-slate-300">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            onClick={handleZoomIn}
            disabled={zoom >= 3}
            title="Zoom In"
            className="p-1 hover:bg-slate-800 rounded disabled:opacity-40 transition-colors text-slate-300"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleResetZoom}
            disabled={zoom === 1 && pan.x === 0 && pan.y === 0}
            title="Reset Zoom"
            className="p-1 hover:bg-slate-800 rounded disabled:opacity-40 transition-colors text-slate-300 ml-1 border-l border-slate-800 pl-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Visualizer Container */}
      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        className={cn(
          "relative flex-1 min-h-[380px] max-h-[560px] w-full flex items-center justify-center overflow-hidden bg-slate-950 select-none",
          zoom > 1 ? (isPanning ? "cursor-grabbing" : "cursor-grab") : "cursor-default"
        )}
      >
        <div
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "center center",
            transition: isPanning ? "none" : "transform 0.15s ease-out",
          }}
          className="relative w-full h-full flex items-center justify-center"
        >
          {/* Base Image */}
          <img
            ref={imageRef}
            src={imageUrl}
            alt={altText}
            onLoad={updateImageRect}
            className="max-h-[540px] max-w-full object-contain pointer-events-none"
          />

          {/* SVG Overlay scaled perfectly to rendered image */}
          {imageRect.width > 0 && imageRect.height > 0 && (
            <svg
              data-testid="bbox-svg-overlay"
              style={{
                position: "absolute",
                top: `${imageRect.top}px`,
                left: `${imageRect.left}px`,
                width: `${imageRect.width}px`,
                height: `${imageRect.height}px`,
                pointerEvents: "auto",
              }}
              viewBox="0 0 1000 1000"
              preserveAspectRatio="none"
              className="z-10"
            >
              {items.map((item) => {
                if (!visibleFields[item.fieldName]) return null;
                const norm = normalizeCoords(item.coords);
                if (!norm) return null;

                const color = getFieldColor(item.fieldName);
                const isSelected = selectedField === item.fieldName;
                const isHovered = hoveredBox?.id === item.id;

                const x = norm.left * 1000;
                const y = norm.top * 1000;
                const width = norm.width * 1000;
                const height = norm.height * 1000;

                return (
                  <g
                    key={item.id}
                    className="cursor-pointer transition-opacity"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectField?.(item.fieldName);
                    }}
                    onMouseEnter={() => setHoveredBox(item)}
                    onMouseLeave={() => setHoveredBox(null)}
                  >
                    {/* Bounding Box Rect */}
                    <rect
                      x={x}
                      y={y}
                      width={width}
                      height={height}
                      fill={isSelected || isHovered ? color.fill.replace("0.2", "0.4") : color.fill}
                      stroke={color.stroke}
                      strokeWidth={isSelected ? 4 : isHovered ? 3 : 2}
                      strokeDasharray={isSelected ? "6 3" : undefined}
                      rx={4}
                      className="transition-all"
                    />

                    {/* Field label tag */}
                    <g transform={`translate(${x}, ${Math.max(20, y - 6)})`}>
                      <rect
                        x={0}
                        y={-18}
                        width={Math.min(180, (item.label || item.fieldName).length * 8 + 36)}
                        height={18}
                        fill={color.stroke}
                        rx={2}
                      />
                      <text
                        x={4}
                        y={-5}
                        fill="#ffffff"
                        fontSize={10}
                        fontWeight="bold"
                        fontFamily="ui-sans-serif, system-ui, sans-serif"
                      >
                        {item.label || item.fieldName}
                        {item.confidence ? ` (${Math.round(item.confidence * 100)}%)` : ""}
                      </text>
                    </g>
                  </g>
                );
              })}
            </svg>
          )}
        </div>

        {/* Hovered Tooltip Card */}
        {hoveredBox && (
          <div className="absolute bottom-4 left-4 z-20 max-w-sm bg-slate-900/95 backdrop-blur-sm border border-slate-700 text-slate-200 text-xs p-3 rounded-lg shadow-xl pointer-events-none">
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="font-bold text-white uppercase tracking-wider text-[10px]">
                {hoveredBox.label || hoveredBox.fieldName.replace(/_/g, " ")}
              </span>
              {hoveredBox.confidence !== undefined && (
                <span className="font-mono text-[10px] text-emerald-400 font-semibold">
                  {Math.round(hoveredBox.confidence * 100)}% confidence
                </span>
              )}
            </div>
            {hoveredBox.rawValue && (
              <div className="font-mono text-[11px] text-slate-300 bg-slate-950 p-1.5 rounded border border-slate-800 break-words line-clamp-3">
                "{hoveredBox.rawValue}"
              </div>
            )}
          </div>
        )}
      </div>

      {/* Field Visibility Toggles Bar */}
      <div className="p-3 bg-slate-950 border-t border-slate-800">
        <div className="flex items-center justify-between gap-2 mb-2">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Toggle Overlays:
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => toggleAll(true)}
              className="text-[11px] text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium"
            >
              <Eye className="w-3 h-3" /> Show All
            </button>
            <span className="text-slate-600">|</span>
            <button
              type="button"
              onClick={() => toggleAll(false)}
              className="text-[11px] text-slate-400 hover:text-slate-300 flex items-center gap-1 font-medium"
            >
              <EyeOff className="w-3 h-3" /> Hide All
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-1">
          {uniqueFields.map((field) => {
            const isVisible = !!visibleFields[field];
            const color = getFieldColor(field);
            const isSelected = selectedField === field;

            return (
              <button
                key={field}
                type="button"
                onClick={() => toggleField(field)}
                className={cn(
                  "inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium transition-colors border",
                  isVisible
                    ? isSelected
                      ? "bg-blue-900/60 border-blue-400 text-blue-200 ring-1 ring-blue-400"
                      : "bg-slate-900 border-slate-700 text-slate-200 hover:border-slate-600"
                    : "bg-slate-950 border-slate-800/80 text-slate-500 opacity-60 line-through"
                )}
              >
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: color.stroke }}
                />
                <span className="capitalize">{field.replace(/_/g, " ")}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
