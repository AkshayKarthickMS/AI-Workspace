import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-lg border border-line bg-white p-6 shadow-card", className ?? null)}
      {...props}
    />
  );
}

export function CardHeading({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2 className={cn("text-base font-semibold text-ink", className ?? null)} {...props} />
  );
}

export function CardSubtext({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("mt-1.5 text-sm text-ink-muted", className ?? null)} {...props} />;
}
