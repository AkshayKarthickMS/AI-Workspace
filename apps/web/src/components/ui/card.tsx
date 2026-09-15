import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-slate-700 bg-slate-900/70 p-6 shadow-2xl shadow-slate-950/30",
        className ?? null,
      )}
      {...props}
    />
  );
}

export function CardHeading({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("text-xl font-semibold text-white", className ?? null)} {...props} />;
}

export function CardSubtext({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("mt-2 text-sm text-slate-400", className ?? null)} {...props} />;
}
