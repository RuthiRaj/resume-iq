import * as React from "react";
import { AlertCircle, FileQuestion, Loader2, CheckCircle2, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  description,
  actionLabel,
  onAction,
  icon: Icon = FileQuestion,
  className,
}: {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  icon?: React.ComponentType<{ className?: string }>;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-card border border-dashed border-border bg-surface p-8 text-center",
        className
      )}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-page text-muted">
        <Icon className="h-5 w-5" />
      </div>
      <h4 className="mt-3 text-h2 font-medium text-primary">{title}</h4>
      <p className="mt-1 max-w-sm text-small text-secondary">{description}</p>
      {actionLabel && onAction && (
        <Button onClick={onAction} variant="outline" size="sm" className="mt-4">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

export function LoadingState({
  text = "Loading workspace data...",
  className,
}: {
  text?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-card border border-border bg-surface p-12 text-center",
        className
      )}
    >
      <Loader2 className="h-6 w-6 animate-spin text-accent" />
      <p className="mt-3 text-small text-secondary">{text}</p>
    </div>
  );
}

export function ErrorAlert({
  title = "An error occurred",
  message,
  onRetry,
  className,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-start justify-between rounded-btn border border-status-error/30 bg-status-error-soft p-4 text-status-error",
        className
      )}
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
        <div>
          <h5 className="text-body font-semibold">{title}</h5>
          <p className="mt-0.5 text-small opacity-90">{message}</p>
        </div>
      </div>
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="border-status-error/40 text-status-error hover:bg-status-error/10 bg-transparent"
        >
          Try Again
        </Button>
      )}
    </div>
  );
}

export function ToastBanner({
  message,
  type = "success",
  className,
}: {
  message: string;
  type?: "success" | "error" | "info";
  className?: string;
}) {
  const isError = type === "error";
  const isInfo = type === "info";
  return (
    <div
      role={isError ? "alert" : "status"}
      aria-live={isError ? "assertive" : "polite"}
      className={cn(
        "flex items-center gap-2 rounded-btn px-4 py-2.5 text-small font-medium border animate-in fade-in duration-200",
        isError
          ? "bg-status-error-soft text-status-error border-status-error/20"
          : isInfo
          ? "bg-accent-soft text-accent border-accent/20"
          : "bg-status-success-soft text-status-success border-status-success/20",
        className
      )}
    >
      {isError ? (
        <AlertCircle className="h-4 w-4 shrink-0" />
      ) : isInfo ? (
        <Info className="h-4 w-4 shrink-0" />
      ) : (
        <CheckCircle2 className="h-4 w-4 shrink-0" />
      )}
      <span>{message}</span>
    </div>
  );
}
