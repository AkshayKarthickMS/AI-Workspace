import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import { IdentityProvider } from "@/features/identity/identity-context";
import { WorkspaceProvider } from "@/features/workspace/workspace-context";

import "./globals.css";

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AegisOS — Autonomous analysis for enterprise teams",
  description:
    "AegisOS plans, analyzes, and reports on your business data with a human approval gate before anything runs, and a full audit trail after.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body className="bg-paper font-sans text-ink antialiased">
        <IdentityProvider>
          <WorkspaceProvider>{children}</WorkspaceProvider>
        </IdentityProvider>
      </body>
    </html>
  );
}
