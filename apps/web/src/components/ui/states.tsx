import type { ReactNode } from "react";

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-500 border-t-cyan-400 ${className ?? ""}`}
    />
  );
}

export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm text-slate-400">
      <Spinner />
      {label}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <p className="rounded-lg border border-rose-400/30 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
      {message}
    </p>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-slate-700 px-4 py-6 text-center text-sm text-slate-400">
      {children}
    </p>
  );
}
