import type { AnalyticsConfig } from "./config";
import { eventProperties, type AnalyticsEvent } from "./events";

export function optedOut(): boolean {
  try { return Boolean(localStorage.getItem("disable-liwan")); }
  catch { return true; } // Unavailable preferences fail closed.
}

export function canTrack(config: AnalyticsConfig, automated = navigator.webdriver): boolean {
  return config.enabled && process.env.NODE_ENV === "production" && !automated && !optedOut();
}

export async function sendEvent(config: AnalyticsConfig, name: AnalyticsEvent, path: string, values: Record<string, unknown> = {}): Promise<void> {
  if (!canTrack(config) || !(name === "pageview" ? config.pageviews : name === "article_opened" ? config.articles : config.features)) return;
  const properties = eventProperties(name, path, values);
  if (!properties) return;
  try {
    const tracker = await import("@liwan.dev/tracker");
    // Recheck after loading: opt-out or navigation may have changed while awaiting JS.
    if (!canTrack(config) || window.location.pathname !== path) return;
    const payload = { name, entity_id: config.entity, url: new URL(path, window.location.origin).href, properties };
    // Official SDK hook rebuilds the payload, dropping global defaults, referrer,
    // attribution, screen and orientation. Never call automatic trackPageviews().
    globalThis.liwanTransformEvent = () => payload;
    await tracker.event(name, { endpoint: "/analytics/event", entity: config.entity, url: payload.url, properties, exit: false });
  } catch { /* Analytics must not interrupt product use; do not retry/double-count. */ }
}
