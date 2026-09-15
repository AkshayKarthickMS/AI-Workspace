"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { IdentityBadge } from "@/features/identity/identity-badge";
import { WorkspaceSwitcher } from "@/features/workspace/workspace-switcher";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { href: "/", label: "Missions" },
  { href: "/knowledge", label: "Knowledge" },
  { href: "/audit", label: "Audit" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4 sm:px-10">
          <div className="flex items-center gap-8">
            <Link href="/" className="text-sm font-semibold uppercase tracking-[0.24em] text-cyan-300">
              AegisOS
            </Link>
            <nav className="flex items-center gap-1">
              {NAV_LINKS.map((link) => {
                const active =
                  link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={cn(
                      "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                      active
                        ? "bg-slate-800 text-white"
                        : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200",
                    )}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <WorkspaceSwitcher />
            <IdentityBadge />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-10 sm:px-10">{children}</main>
    </div>
  );
}
