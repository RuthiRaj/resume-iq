import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "outline" | "success" | "warning" | "error" | "accent";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variants = {
    default: "bg-page text-primary border-border",
    secondary: "bg-surface text-secondary border-border",
    outline: "bg-transparent text-primary border-border",
    accent: "bg-accent-soft text-accent border-accent/20",
    success: "bg-status-success-soft text-status-success border-status-success/20",
    warning: "bg-status-warning-soft text-status-warning border-status-warning/20",
    error: "bg-status-error-soft text-status-error border-status-error/20",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-[4px] border px-2 py-0.5 text-caption font-semibold tracking-[0.4px] transition-colors",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}
