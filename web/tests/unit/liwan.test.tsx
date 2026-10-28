import { StrictMode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AnalyticsProvider, AnalyticsPreference, useAnalytics } from "@/components/analytics/provider";
import { AlertList } from "@/components/alerts/alert-list";
import { analyticsConfig } from "@/lib/analytics/config";
import { articleId, normaliseArticleUrl } from "@/lib/analytics/article-id.mjs";
import { eventProperties, routes } from "@/lib/analytics/events";
import { sendEvent } from "@/lib/analytics/send";

let path = "/topics";
const sent = vi.hoisted(() => [] as Array<{ name: string; url: string; properties: Record<string, string | number> }>);
vi.mock("next/navigation", () => ({ usePathname: () => path }));
vi.mock("@liwan.dev/tracker", () => ({ event: vi.fn(async (name, options) => {
  sent.push(globalThis.liwanTransformEvent!({ name, url: options.url, properties: { secret: "drop me" },
    referrer: "https://private/?search=secret", screen_width: "xl", orientation: "landscape" }) as typeof sent[number]);
}) }));
const config = { enabled: true, entity: "risklive", pageviews: true, articles: true, features: true };
function move(next: string) { path = next; window.history.replaceState({}, "", next); }
function ArticleAction() {
  const { openArticle } = useAnalytics();
  return <button onClick={() => openArticle("https://example.com/story?utm_source=alerts#section", "Red")}>Open source</button>;
}
beforeEach(() => {
  vi.stubEnv("NODE_ENV", "production");
  Object.defineProperty(navigator, "webdriver", { configurable: true, value: false });
  localStorage.clear(); sent.length = 0; move("/topics");
});
afterEach(() => { cleanup(); vi.unstubAllEnvs(); vi.restoreAllMocks(); });

describe("article identity", () => {
  it("shares SHA-256 identity across sections and attribution variants", () => {
    expect(articleId("https://EXAMPLE.com:443/story?id=42&utm_source=alerts#top")).toBe(articleId("https://example.com/story?id=42&utm_source=newsmap"));
    expect(articleId("https://example.com/story?id=42")).toMatch(/^url-v1-[a-f0-9]{64}$/);
    expect(articleId("https://example.com/story?id=42")).not.toBe(articleId("https://example.com/story?id=43"));
    expect(articleId("https://example.com/Story")).not.toBe(articleId("https://example.com/story"));
    expect(normaliseArticleUrl("https://example.com/a?z=2&a=1&gclid=private#x")).toBe("https://example.com/a?a=1&z=2");
  });
  it.each(["not a url", "javascript:alert(1)", "https://user:password@example.com/a"])("rejects %s", (url) => expect(articleId(url)).toBeNull());
});
describe("event privacy schema", () => {
  it.each(routes)("permits approved pageview %s", (route) => expect(eventProperties("pageview", route)).toEqual({}));
  it.each(["/ops", "/ops/logs", "/api/dashboard", "/privacy", "/", "/alerts/private", "/topics?search=secret"])("rejects %s", (route) => expect(eventProperties("pageview", route)).toBeNull());
  it("rejects extra fields, unsafe IDs, unknown events and mismatched sections", () => {
    expect(eventProperties("pageview", "/topics", { query: "private" })).toBeNull();
    expect(eventProperties("topic_selected", "/alerts")).toBeNull();
    expect(eventProperties("article_opened", "/alerts", { article_id: "headline", risk_level: "red" })).toBeNull();
    expect(eventProperties("article_opened", "/alerts", { article_id: articleId("https://example.com"), risk_level: "red", url: "secret" })).toBeNull();
    expect(eventProperties("unknown" as never, "/newsmap")).toBeNull();
  });
  it("validates all feature events and fixed values", () => {
    expect(eventProperties("topic_selected", "/topics")).toEqual({ section: "topics" });
    expect(eventProperties("topic_filter_used", "/topics")).toEqual({ section: "topics" });
    expect(eventProperties("alert_filter_changed", "/alerts", { severity: "yellow" })).toEqual({ section: "alerts", severity: "yellow" });
    expect(eventProperties("newsmap_node_selected", "/newsmap", { node_type: "article", depth: 3 })).toEqual({ section: "newsmap", node_type: "article", depth: 3 });
    expect(eventProperties("newsmap_view_changed", "/newsmap-experimental", { mode: "binary" })).toEqual({ section: "newsmap-experimental", mode: "binary" });
    expect(eventProperties("newsmap_view_changed", "/newsmap", { mode: "private title" })).toBeNull();
    expect(eventProperties("newsmap_node_selected", "/newsmap", { node_type: "node", depth: -1 })).toBeNull();
  });
});
describe("collection controls and navigation", () => {
  it("defaults off and rejects development/automated production servers", () => {
    expect(analyticsConfig({ NODE_ENV: "production" }).enabled).toBe(false);
    expect(analyticsConfig({ NODE_ENV: "production", LIWAN_ENABLED: "true", ANALYTICS_TEST_MODE: "true" }).enabled).toBe(false);
    expect(analyticsConfig({ NODE_ENV: "development", LIWAN_ENABLED: "true" }).enabled).toBe(false);
  });
  it("counts Strict Mode once, transitions and returns from excluded pages", async () => {
    const view = render(<StrictMode><AnalyticsProvider config={config}>Content</AnalyticsProvider></StrictMode>);
    await waitFor(() => expect(sent).toHaveLength(1));
    view.rerender(<StrictMode><AnalyticsProvider config={config}>Rerender</AnalyticsProvider></StrictMode>);
    await Promise.resolve(); expect(sent).toHaveLength(1);
    for (const [index, next] of ["/alerts", "/topics", "/ops", "/topics"].entries()) {
      move(next); view.rerender(<StrictMode><AnalyticsProvider config={config}>Content</AnalyticsProvider></StrictMode>);
      if (next !== "/ops") await waitFor(() => expect(sent).toHaveLength(index === 3 ? 4 : index + 2));
    }
    expect(sent).toHaveLength(4);
  });
  it("does not count or transmit query/hash changes", async () => {
    window.history.replaceState({}, "", "/topics?utm_term=private#article");
    const view = render(<AnalyticsProvider config={config}>Content</AnalyticsProvider>);
    await waitFor(() => expect(sent).toHaveLength(1));
    view.rerender(<AnalyticsProvider config={config}>Changed</AnalyticsProvider>);
    expect(sent[0]).toEqual({ name: "pageview", entity_id: "risklive", url: `${location.origin}/topics`, properties: {} });
    expect(sent).toHaveLength(1);
  });
  it("emits the same article ID and shared event from all three sections", async () => {
    move("/alerts"); const enabled = { ...config, pageviews: false };
    const view = render(<AnalyticsProvider config={enabled}><ArticleAction /></AnalyticsProvider>);
    for (const [index, next] of ["/alerts", "/newsmap", "/newsmap-experimental"].entries()) {
      move(next); view.rerender(<AnalyticsProvider config={enabled}><ArticleAction /></AnalyticsProvider>);
      fireEvent.click(screen.getByText("Open source"));
      await waitFor(() => expect(sent).toHaveLength(index + 1));
    }
    expect(new Set(sent.map(e => e.properties.article_id)).size).toBe(1);
    expect(sent.map(e => e.properties.section)).toEqual(["alerts", "newsmap", "newsmap-experimental"]);
    expect(sent.every(e => e.name === "article_opened" && e.properties.risk_level === "red")).toBe(true);
    expect(JSON.stringify(sent)).not.toMatch(/example.com|utm_|headline|secret|screen|referrer/);
  });
  it("records middle-click but ignores right-click on Alert links", async () => {
    move("/alerts");
    render(<AnalyticsProvider config={{ ...config, pageviews: false }}><AlertList items={[{ title: "Private title", url: "https://example.com/a", alert_flag: "Yellow" }]} /></AnalyticsProvider>);
    fireEvent(screen.getByRole("link"), new MouseEvent("auxclick", { bubbles: true, button: 2 })); await Promise.resolve(); expect(sent).toHaveLength(0);
    fireEvent(screen.getByRole("link"), new MouseEvent("auxclick", { bubbles: true, button: 1 }));
    await waitFor(() => expect(sent).toHaveLength(1)); expect(sent[0].properties.risk_level).toBe("yellow");
  });
  it.each(["development", "test"])("never sends in %s", async (env) => {
    vi.stubEnv("NODE_ENV", env); await sendEvent(config, "pageview", "/topics"); expect(sent).toHaveLength(0);
  });
  it("blocks disabled categories, automation and opt-out", async () => {
    await sendEvent({ ...config, enabled: false }, "pageview", "/topics");
    await sendEvent({ ...config, pageviews: false }, "pageview", "/topics");
    await sendEvent({ ...config, features: false }, "topic_selected", "/topics");
    move("/alerts"); await sendEvent({ ...config, articles: false }, "article_opened", "/alerts", { article_id: articleId("https://example.com/a"), risk_level: "red" });
    Object.defineProperty(navigator, "webdriver", { configurable: true, value: true }); await sendEvent(config, "pageview", "/alerts");
    Object.defineProperty(navigator, "webdriver", { configurable: true, value: false }); localStorage.setItem("disable-liwan", "true");
    await sendEvent(config, "pageview", "/alerts"); expect(sent).toHaveLength(0);
  });
  it("persists opt-out and stops future transmissions", async () => {
    render(<AnalyticsPreference />); fireEvent.click(await screen.findByText("Opt out of usage analytics"));
    expect(localStorage.getItem("disable-liwan")).toBe("true");
    await sendEvent(config, "pageview", "/topics"); expect(sent).toHaveLength(0);
    fireEvent.click(screen.getByText("Allow usage analytics on this browser")); expect(localStorage.getItem("disable-liwan")).toBeNull();
  });
  it("fails closed if preference storage is unavailable", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    await sendEvent(config, "pageview", "/topics"); expect(sent).toHaveLength(0);
  });
});
