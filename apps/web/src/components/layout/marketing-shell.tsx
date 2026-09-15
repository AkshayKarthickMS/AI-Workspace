import Link from "next/link";
import type { ReactNode } from "react";

const NAV_LINKS = [{ href: "/pricing", label: "Pricing" }];

export function MarketingShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4 sm:px-10">
          <Link href="/" className="text-sm font-bold tracking-tight text-ink">
            AEGISOS
          </Link>
          <nav className="hidden items-center gap-8 sm:flex">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm font-medium text-ink-muted hover:text-ink"
              >
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <Link
              href="/app"
              className="rounded-md border border-line px-3 py-1.5 text-sm font-medium text-ink hover:border-ink-faint"
            >
              Sign in
            </Link>
            <Link
              href="/app"
              className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover"
            >
              Open app
            </Link>
          </div>
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="border-t border-line bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-8 text-sm text-ink-muted sm:flex-row sm:items-center sm:justify-between sm:px-10">
          <p>© {new Date().getFullYear()} AegisOS. All rights reserved.</p>
          <div className="flex items-center gap-6">
            <Link href="/pricing" className="hover:text-ink">
              Pricing
            </Link>
            <Link href="/app" className="hover:text-ink">
              Open app
            </Link>
            <a href="mailto:sales@aegisos.app" className="hover:text-ink">
              Contact
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
