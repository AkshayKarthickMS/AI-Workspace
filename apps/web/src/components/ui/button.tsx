import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const variantClasses: Record<Variant, string> = {
  primary: "bg-accent text-white hover:bg-accent-hover disabled:bg-ink-faint",
  secondary:
    "border border-line bg-white text-ink hover:border-ink-faint hover:bg-paper disabled:opacity-50",
  danger:
    "border border-red-200 bg-red-50 text-red-800 hover:bg-red-100 disabled:opacity-50",
  ghost: "text-ink-muted hover:bg-paper disabled:opacity-50",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({ className, variant = "primary", disabled, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed",
        variantClasses[variant],
        className ?? null,
      )}
      disabled={disabled}
      {...props}
    />
  );
}
