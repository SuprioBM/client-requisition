import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/providers/query-provider";
import { ThemeProvider } from "@/providers/theme-provider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { AppShell } from "@/components/layout/app-shell";

export const metadata: Metadata = {
  title: "Client Requisition Agent",
  description: "AI lead-intelligence operations dashboard",
};

// System font stack (no build-time font download — keeps `next build` offline-safe).
// The --font-* CSS variables are defined in globals.css.

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <ThemeProvider>
          <QueryProvider>
            <TooltipProvider delayDuration={200}>
              <AppShell>{children}</AppShell>
              <Toaster />
            </TooltipProvider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
