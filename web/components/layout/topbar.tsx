"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useTopbarContent } from "@/components/layout/topbar-context";

export function Topbar() {
  const { rightContent } = useTopbarContent();
  const themes = useMemo(
    () => [
      { id: "github-light", label: "Studio Light", dark: false },
      { id: "catppuccin-latte", label: "Latte Light", dark: false },
      { id: "dracula", label: "Midnight Purple", dark: true },
      { id: "github-dark", label: "Studio Dark", dark: true },
      { id: "catppuccin-mocha", label: "Mocha Dark", dark: true },
      { id: "oled-modern", label: "OLED Modern", dark: true },
    ],
    []
  );
  const [theme, setTheme] = useState<string>("github-dark");

  useEffect(() => {
    const root = document.documentElement;
    const stored = localStorage.getItem("theme");
    const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches;
    const fallback = prefersDark ? "github-dark" : "github-light";
    const next = themes.some((item) => item.id === stored) ? stored! : fallback;
    const nextTheme = themes.find((item) => item.id === next) ?? themes[0];
    root.classList.toggle("dark", nextTheme.dark);
    root.dataset.theme = nextTheme.id;
    setTheme(nextTheme.id);
  }, []);

  const updateTheme = (next: string) => {
    const target = themes.find((item) => item.id === next) ?? themes[0];
    document.documentElement.classList.toggle("dark", target.dark);
    document.documentElement.dataset.theme = target.id;
    localStorage.setItem("theme", target.id);
    setTheme(target.id);
  };

  const cycleTheme = () => {
    const currentIndex = themes.findIndex((item) => item.id === theme);
    const nextIndex = currentIndex >= 0 ? (currentIndex + 1) % themes.length : 0;
    updateTheme(themes[nextIndex].id);
  };

  return (
    <header className="border-b border-border bg-background px-4 py-2">
      <div className="flex min-w-0 items-center gap-3">
        <Link
          href="/"
          className="leading-tight transition hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
          aria-label="Go to Dashboard"
        >
          <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Risklive Ops
          </p>
          <h1 className="font-display text-xl sm:text-2xl">
            Dashboard
          </h1>
        </Link>

        <nav className="ml-auto flex min-w-0 items-center gap-2 overflow-x-auto whitespace-nowrap">
          <Link
            href="/topics"
            className="rounded-full border border-border px-3 py-1 text-[11px] font-semibold text-foreground transition hover:bg-accent hover:text-accent-foreground"
          >
            Daily Report
          </Link>
          <Link
            href="/newsmap"
            className="rounded-full border border-border px-3 py-1 text-[11px] font-semibold text-foreground transition hover:bg-accent hover:text-accent-foreground"
          >
            Newsmap
          </Link>
          <Link
            href="/newsmap-experimental"
            className="rounded-full border border-border px-3 py-1 text-[11px] font-semibold text-foreground transition hover:bg-accent hover:text-accent-foreground"
          >
            Newsmap Experimental
          </Link>
          <Link
            href="/alerts"
            className="rounded-full border border-border px-3 py-1 text-[11px] font-semibold text-foreground transition hover:bg-accent hover:text-accent-foreground"
          >
            Alerts
          </Link>
          <button
            type="button"
            onClick={cycleTheme}
            className="flex items-center justify-center rounded-full border border-border p-2 text-foreground transition hover:bg-accent hover:text-accent-foreground"
            aria-label="Cycle theme"
            title={`Theme: ${themes.find((item) => item.id === theme)?.label ?? theme}`}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="8" />
              <path d="M12 4a8 8 0 0 0 0 16z" fill="currentColor" />
            </svg>
          </button>
          {rightContent}
        </nav>
      </div>
    </header>
  );
}
