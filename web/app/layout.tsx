import type { Metadata } from "next";
import { Sora, Manrope } from "next/font/google";

import "./globals.css";
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
  description: "Operations dashboard for alerts, topics, and newsmap insights.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark h-full">
      <body className={`${sora.variable} ${manrope.variable} font-body antialiased h-full overflow-hidden`}>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
