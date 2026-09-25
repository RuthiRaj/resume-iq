"use client";

import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  maxWidth?: "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl";
}

export function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  maxWidth = "lg",
}: ModalProps) {
  const dialogRef = React.useRef<HTMLDivElement>(null);
  const previousActiveElement = React.useRef<HTMLElement | null>(null);
  const titleId = React.useId();
  const descId = React.useId();

  // Focus trap, Escape key handling, and focus restoration
  React.useEffect(() => {
    if (!isOpen) return;

    previousActiveElement.current = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";

    // Initial focus on dialog
    const focusTimer = setTimeout(() => {
      if (dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length > 0) {
          focusable[0].focus();
        } else {
          dialogRef.current.focus();
        }
      }
    }, 50);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;

        const firstElement = focusable[0];
        const lastElement = focusable[focusable.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      clearTimeout(focusTimer);
      document.body.style.overflow = "unset";
      window.removeEventListener("keydown", handleKeyDown);
      if (previousActiveElement.current) {
        previousActiveElement.current.focus();
      }
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const maxWidths = {
    sm: "max-w-sm",
    md: "max-w-md",
    lg: "max-w-lg",
    xl: "max-w-xl",
    "2xl": "max-w-2xl",
    "3xl": "max-w-3xl",
    "4xl": "max-w-4xl",
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6"
      role="presentation"
    >
      {/* Accessible Backdrop */}
      <div
        className="fixed inset-0 bg-primary/40 backdrop-blur-none transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Accessible Modal Dialog Container */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        className={cn(
          "relative z-50 w-full rounded-modal border border-border bg-surface shadow-dropdown transition-all max-h-[92vh] sm:max-h-[90vh] flex flex-col focus:outline-none",
          maxWidths[maxWidth]
        )}
      >
        <div className="flex items-start justify-between border-b border-border/80 p-4 sm:p-5">
          <div className="space-y-1 pr-2">
            <h2 id={titleId} className="text-h2 font-semibold text-primary">
              {title}
            </h2>
            {description && (
              <p id={descId} className="text-small text-secondary">
                {description}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="flex h-11 w-11 sm:h-8 sm:w-8 items-center justify-center rounded-[4px] text-muted hover:bg-page hover:text-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
          >
            <X className="h-5 w-5 sm:h-4 sm:w-4" />
            <span className="sr-only">Close</span>
          </button>
        </div>

        <div className="overflow-y-auto overscroll-contain p-4 sm:p-5 flex-1">
          {children}
        </div>
      </div>
    </div>
  );
}
