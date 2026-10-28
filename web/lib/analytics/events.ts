export const routes = ["/topics", "/alerts", "/newsmap", "/newsmap-experimental"] as const;
export type AnalyticsEvent = "pageview" | "article_opened" | "topic_selected" | "topic_filter_used" |
  "alert_filter_changed" | "newsmap_node_selected" | "newsmap_view_changed";
export type FeatureEvent = Exclude<AnalyticsEvent, "pageview" | "article_opened">;
export type RiskLevel = "red" | "yellow" | "unknown";
export const riskLevel = (flag?: string): RiskLevel => flag?.toLowerCase() === "red" ? "red" : flag?.toLowerCase() === "yellow" ? "yellow" : "unknown";
export const viewModes = ["binary", "squarify", "30d", "7d", "3d", "timeline", "mappedSourceCount", "recency", "activeWindow", "wordMass", "hktSignificance", "triggerIntensity", "combinedError", "alphaError", "betaError", "wordImportanceError", "triggeredScore", "composite", "highToLarge", "highToSmall"];

// Reject unknown fields rather than letting SDK defaults or future callers add data.
export function eventProperties(name: AnalyticsEvent, path: string, values: Record<string, unknown> = {}): Record<string, string | number> | null {
  if (!(routes as readonly string[]).includes(path)) return null;
  const section = path.slice(1);
  const keys = Object.keys(values).sort().join(",");
  if (name === "pageview") return keys === "" ? {} : null;
  if (name === "article_opened") {
    if (path === "/topics" || keys !== "article_id,risk_level" || typeof values.article_id !== "string" ||
      !/^url-v1-[a-f0-9]{64}$/.test(values.article_id) || !["red", "yellow", "unknown"].includes(String(values.risk_level))) return null;
    return { article_id: values.article_id, section, risk_level: String(values.risk_level) };
  }
  if (name === "topic_selected" || name === "topic_filter_used") return path === "/topics" && keys === "" ? { section } : null;
  if (name === "alert_filter_changed") return path === "/alerts" && keys === "severity" && ["all", "red", "yellow"].includes(String(values.severity)) ? { section, severity: String(values.severity) } : null;
  if (!path.startsWith("/newsmap")) return null;
  if (name === "newsmap_view_changed") return keys === "mode" && viewModes.includes(String(values.mode)) ? { section, mode: String(values.mode) } : null;
  if (name === "newsmap_node_selected" && keys === "depth,node_type" && ["category", "topic", "article", "node"].includes(String(values.node_type)) &&
    typeof values.depth === "number" && Number.isInteger(values.depth) && values.depth >= 0 && values.depth <= 20) {
    return { section, node_type: String(values.node_type), depth: values.depth };
  }
  return null;
}
