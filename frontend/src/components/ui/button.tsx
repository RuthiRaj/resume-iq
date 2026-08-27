import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
  size?: "sm" | "md" | "lg" | "icon";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", children, disabled, ...props }, ref) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none rounded-btn select-none";

    const variants = {
      primary: "bg-accent text-white hover:bg-accent/90 shadow-subtle border border-accent",
      secondary: "bg-accent-soft text-accent hover:bg-accent-soft/80 border border-transparent",
      outline: "bg-surface text-primary border border-border hover:bg-page hover:text-primary",
      ghost: "text-secondary hover:text-primary hover:bg-page border border-transparent",
      danger: "bg-status-error text-white hover:bg-status-error/90 border border-status-error",
    };

    const sizes = {
      sm: "h-8 px-2.5 text-small gap-1.5",
      md: "h-9 px-3.5 text-body gap-2",
      lg: "h-10 px-4 text-body gap-2.5",
      icon: "h-9 w-9 p-0",
    };

    return (
      <button
        ref={ref}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
