"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import type { AnalyticsConfig } from "@/lib/analytics/config";
import { articleId } from "@/lib/analytics/article-id.mjs";
import { riskLevel, routes, type FeatureEvent } from "@/lib/analytics/events";
import { canTrack, optedOut, sendEvent } from "@/lib/analytics/send";

const Context = createContext({
  track: (_name: FeatureEvent, _values: Record<string, unknown> = {}) => {},
  openArticle: (_url: string, _risk?: string) => {},
});
export const useAnalytics = () => useContext(Context);

export function AnalyticsProvider({ config, children }: { config: AnalyticsConfig; children: ReactNode }) {
  const path = usePathname();
  const lastPath = useRef<string | null>(null);
  const track = useCallback((name: FeatureEvent, values: Record<string, unknown> = {}) => {
    if (path) void sendEvent(config, name, path, values);
  }, [config, path]);
  const openArticle = useCallback((url: string, risk?: string) => {
    // Only emit opaque identifiers, never the URL being opened.
    const id = articleId(url);
    if (path && id) void sendEvent(config, "article_opened", path, { article_id: id, risk_level: riskLevel(risk) });
  }, [config, path]);
  useEffect(() => {
    if (!path || !(routes as readonly string[]).includes(path)) { lastPath.current = null; return; }
    if (!canTrack(config) || !config.pageviews || lastPath.current === path) return;
    lastPath.current = path;
    void sendEvent(config, "pageview", path);
  }, [config, path]);
  return <Context.Provider value={{ track, openArticle }}>{children}</Context.Provider>;
}

export function AnalyticsPreference() {
  const [disabled, setDisabled] = useState(true);
  useEffect(() => {
    const update = () => setDisabled(optedOut());
    update();
    window.addEventListener("storage", update);
    return () => window.removeEventListener("storage", update);
  }, []);
  return <button type="button" onClick={() => {
    try {
      if (disabled) localStorage.removeItem("disable-liwan");
      else localStorage.setItem("disable-liwan", "true");
      setDisabled(!disabled);
    } catch { setDisabled(true); }
  }}>{disabled ? "Allow usage analytics on this browser" : "Opt out of usage analytics"}</button>;
}

export function AnalyticsPrivacyLink() {
  return <Link href="/privacy" className="text-[11px] text-muted-foreground hover:underline">Privacy</Link>;
}
