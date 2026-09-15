import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const toneClasses: Record<Tone, string> = {
  neutral: "border-slate-600 bg-slate-800 text-slate-200",
  info: "border-cyan-400/30 bg-cyan-400/10 text-cyan-100",
  success: "border-emerald-400/30 bg-emerald-400/10 text-emerald-100",
  warning: "border-amber-400/30 bg-amber-400/10 text-amber-100",
  danger: "border-rose-400/30 bg-rose-400/10 text-rose-100",
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
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize",
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
