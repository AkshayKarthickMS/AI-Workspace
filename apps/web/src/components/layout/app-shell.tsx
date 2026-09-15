"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { IdentityBadge } from "@/features/identity/identity-badge";
import { WorkspaceSwitcher } from "@/features/workspace/workspace-switcher";
import { cn } from "@/lib/utils";

import { DemoBanner } from "./demo-banner";

const NAV_LINKS = [
  { href: "/app", label: "Missions" },
  { href: "/app/knowledge", label: "Knowledge" },
  { href: "/app/audit", label: "Audit" },
];

function NavLinks({ pathname, className }: { pathname: string; className?: string }) {
  return (
    <>
      {NAV_LINKS.map((link) => {
        const active = link.href === "/app" ? pathname === "/app" : pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "rounded-md px-3 py-2 text-sm font-medium transition-colors",
              active ? "bg-paper text-ink" : "text-ink-muted hover:bg-paper hover:text-ink",
              className,
            )}
          >
            {link.label}
          </Link>
        );
      })}
    </>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-paper">
      <DemoBanner />
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-[1400px]">
        <aside className="hidden w-56 shrink-0 flex-col border-r border-line bg-white md:flex">
          <Link
            href="/"
            className="border-b border-line px-6 py-5 text-sm font-bold tracking-tight text-ink"
          >
            AEGISOS
          </Link>
          <nav className="flex flex-1 flex-col gap-0.5 px-3 py-4">
            <NavLinks pathname={pathname} />
          </nav>
          <div className="space-y-2 border-t border-line px-3 py-4">
            <WorkspaceSwitcher />
            <IdentityBadge />
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="flex flex-col gap-3 border-b border-line bg-white px-6 py-3 md:hidden">
            <div className="flex items-center justify-between">
              <Link href="/" className="text-sm font-bold tracking-tight text-ink">
                AEGISOS
              </Link>
              <IdentityBadge />
            </div>
            <div className="flex items-center gap-1 overflow-x-auto">
              <NavLinks pathname={pathname} />
            </div>
            <WorkspaceSwitcher />
          </header>
          <main className="mx-auto max-w-5xl px-6 py-10 sm:px-10">{children}</main>
        </div>
      </div>
    </div>
  );
}
