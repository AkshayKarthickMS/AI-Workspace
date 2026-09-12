import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AegisOS",
  description: "Autonomous Enterprise AI Workforce",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
