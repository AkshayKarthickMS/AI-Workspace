import type { Metadata } from "next";

import { AppShell } from "@/components/layout/app-shell";
import { IdentityProvider } from "@/features/identity/identity-context";
import { WorkspaceProvider } from "@/features/workspace/workspace-context";

import "./globals.css";

export const metadata: Metadata = {
  title: "AegisOS",
  description: "Autonomous Enterprise AI Workforce",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <IdentityProvider>
          <WorkspaceProvider>
            <AppShell>{children}</AppShell>
          </WorkspaceProvider>
        </IdentityProvider>
      </body>
    </html>
  );
}
