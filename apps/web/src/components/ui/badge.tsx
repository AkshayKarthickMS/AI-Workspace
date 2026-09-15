import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const toneClasses: Record<Tone, string> = {
  neutral: "border-line bg-paper text-ink-muted",
  info: "border-blue-200 bg-blue-50 text-blue-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  danger: "border-red-200 bg-red-50 text-red-800",
};

const STATUS_TONE: Record<string, Tone> = {
  draft: "neutral",
  planned: "info",
  pending: "warning",
  running: "info",
  awaiting_approval: "warning",
  awaiting_escalation: "warning",
  approved: "success",
  rejected: "danger",
  completed: "success",
  failed: "danger",
  cancelled: "neutral",
  ok: "success",
  pass: "success",
  fail: "danger",
  pending_review: "warning",
  ingested: "success",
  ingesting: "info",
  error: "danger",
};

export function toneForStatus(status: string): Tone {
  return STATUS_TONE[status.toLowerCase()] ?? "neutral";
}

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium capitalize",
        toneClasses[tone],
        className ?? null,
      )}
      {...props}
    />
  );
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={toneForStatus(status)}>{status.replace(/_/g, " ")}</Badge>;
}
