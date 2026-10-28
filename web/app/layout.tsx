//© 2025 University of Aberdeen. All rights reserved


import type { Metadata } from "next";
import { Sora, Manrope } from "next/font/google";

import "./globals.css";
import { AnalyticsProvider } from "@/components/analytics/provider";
import { analyticsConfig } from "@/lib/analytics/config";
import { headers } from "next/headers";

import { Shell } from "@/components/layout/shell";

const sora = Sora({
  subsets: ["latin"],
  variable: "--font-display",
});

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "RiskLive Dashboard",
  referrer: "no-referrer",
  description: "Operations dashboard for alerts, topics, and newsmap insights.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Request-time rendering keeps activation runtime-only, including standalone images.
  headers();
  return (
    <html lang="en" className="dark h-full">
      <body className={`${sora.variable} ${manrope.variable} font-body antialiased h-full overflow-hidden`}>
        <AnalyticsProvider config={analyticsConfig(process.env)}>
          <Shell>{children}</Shell>
        </AnalyticsProvider>
      </body>
    </html>
  );
}
