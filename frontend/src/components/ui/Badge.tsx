import React from "react";
import { cn } from "@/lib/utils";

export type BadgeVariant =
  | "default"
  | "secondary"
  | "outline"
  | "compliant"
  | "non_compliant"
  | "needs_review"
  | "critical"
  | "major"
  | "minor"
  | "advisory"
  | "admin"
  | "inspector"
  | "viewer";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: "sm" | "md";
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = "default",
  size = "md",
  className,
  ...props
}) => {
  const variantStyles: Record<BadgeVariant, string> = {
    default: "bg-slate-100 text-slate-800 border-slate-200",
    secondary: "bg-slate-200 text-slate-900 border-slate-300",
    outline: "bg-transparent text-slate-700 border-slate-300",
    // Compliance status / verdicts
    compliant: "bg-emerald-50 text-emerald-700 border-emerald-200 font-semibold",
    non_compliant: "bg-rose-50 text-rose-700 border-rose-200 font-semibold",
    needs_review: "bg-amber-50 text-amber-700 border-amber-200 font-semibold",
    // Severities
    critical: "bg-rose-100 text-rose-800 border-rose-300 font-bold",
    major: "bg-orange-100 text-orange-800 border-orange-300 font-semibold",
    minor: "bg-amber-100 text-amber-800 border-amber-300 font-medium",
    advisory: "bg-blue-50 text-blue-700 border-blue-200 font-medium",
    // Roles
    admin: "bg-purple-100 text-purple-800 border-purple-200 font-bold tracking-wide",
    inspector: "bg-blue-100 text-blue-800 border-blue-200 font-bold tracking-wide",
    viewer: "bg-slate-100 text-slate-700 border-slate-300 font-medium",
  };

  const sizeStyles = {
    sm: "text-[10px] px-1.5 py-0.5 leading-none",
    md: "text-xs px-2.5 py-0.5 leading-normal",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border transition-colors",
        variantStyles[variant] || variantStyles.default,
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
};
