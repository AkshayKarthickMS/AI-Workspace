import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const variantClasses: Record<Variant, string> = {
  primary: "bg-cyan-500 text-slate-950 hover:bg-cyan-400 disabled:bg-cyan-500/40",
  secondary:
    "border border-slate-600 bg-slate-800 text-slate-100 hover:bg-slate-700 disabled:opacity-50",
  danger: "bg-rose-500 text-white hover:bg-rose-400 disabled:bg-rose-500/40",
  ghost: "text-slate-300 hover:bg-slate-800 disabled:opacity-50",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({ className, variant = "primary", disabled, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed",
        variantClasses[variant],
        className ?? null,
      )}
      disabled={disabled}
      {...props}
    />
  );
}
