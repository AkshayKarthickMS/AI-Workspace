import type { ReactNode } from "react";

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-line border-t-ink-muted ${className ?? ""}`}
    />
  );
}

export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm text-ink-muted">
      <Spinner />
      {label}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      {message}
    </p>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-md border border-dashed border-line px-4 py-6 text-center text-sm text-ink-muted">
      {children}
    </p>
  );
}
