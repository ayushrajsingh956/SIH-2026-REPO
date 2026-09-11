import React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "destructive" | "outline" | "ghost" | "link";
  size?: "sm" | "md" | "lg" | "icon";
  isLoading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      children,
      variant = "primary",
      size = "md",
      isLoading = false,
      disabled,
      type = "button",
      ...props
    },
    ref
  ) => {
    const variantStyles = {
      primary: "bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 shadow-sm disabled:bg-blue-300",
      secondary: "bg-slate-100 text-slate-900 hover:bg-slate-200 active:bg-slate-300 border border-slate-200 disabled:bg-slate-50 disabled:text-slate-400",
      destructive: "bg-rose-600 text-white hover:bg-rose-700 active:bg-rose-800 shadow-sm disabled:bg-rose-300",
      outline: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 active:bg-slate-100 disabled:opacity-50",
      ghost: "text-slate-700 hover:bg-slate-100 active:bg-slate-200 disabled:opacity-50",
      link: "text-blue-600 underline-offset-4 hover:underline p-0 h-auto font-medium",
    };

    const sizeStyles = {
      sm: "h-8 px-3 text-xs rounded-md",
      md: "h-9 px-4 text-sm rounded-md",
      lg: "h-11 px-6 text-base rounded-lg",
      icon: "h-9 w-9 p-0 rounded-md flex items-center justify-center",
    };

    return (
      <button
        ref={ref}
        type={type}
        className={cn(
          "inline-flex items-center justify-center font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-1 disabled:pointer-events-none select-none cursor-pointer",
          variantStyles[variant],
          size !== "icon" && variant !== "link" ? sizeStyles[size] : "",
          size === "icon" ? sizeStyles.icon : "",
          className
        )}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading && <Loader2 className="w-4 h-4 mr-2 animate-spin text-current" />}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
