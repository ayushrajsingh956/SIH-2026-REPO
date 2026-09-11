export const DATAVIZ_THEME = {
  colors: {
    compliant: "#10b981", // Emerald
    nonCompliant: "#ef4444", // Crimson
    needsReview: "#f59e0b", // Amber
    critical: "#ef4444",
    major: "#f59e0b",
    minor: "#3b82f6",
    advisory: "#64748b",
  },
  palette: [
    "#0d9488", // Teal
    "#6366f1", // Indigo
    "#f59e0b", // Amber
    "#ec4899", // Pink
    "#06b6d4", // Cyan
    "#8b5cf6", // Purple
  ],
  grid: {
    stroke: "#e2e8f0",
    strokeDasharray: "3 3",
  },
  tooltipStyle: {
    backgroundColor: "rgba(15, 23, 42, 0.92)",
    color: "#ffffff",
    borderRadius: "8px",
    border: "none",
    boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
    fontSize: "12px",
    padding: "8px 12px",
  },
};

export const getSeverityColor = (severity: string): string => {
  const s = severity.toLowerCase();
  if (s === "critical") return DATAVIZ_THEME.colors.critical;
  if (s === "major") return DATAVIZ_THEME.colors.major;
  if (s === "minor") return DATAVIZ_THEME.colors.minor;
  return DATAVIZ_THEME.colors.advisory;
};
