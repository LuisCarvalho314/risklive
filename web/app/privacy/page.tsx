import { analyticsConfig } from "@/lib/analytics/config";
import { AnalyticsPreference } from "@/components/analytics/provider";

export default function PrivacyPage() {
  const enabled = analyticsConfig(process.env).enabled;
  return <div className="h-full overflow-y-auto p-6"><article className="mx-auto max-w-2xl space-y-4">
    <h1 className="text-2xl font-semibold">Usage analytics privacy</h1>
    <p>{enabled ? "RiskLive hosts its usage analytics on its own infrastructure." : "Usage analytics is currently disabled on this deployment. When enabled, RiskLive hosts it on its own infrastructure."}</p>
    <p>We measure page views on Topics, Alerts and Newsmap, feature use, and outbound article clicks. An article click means a source link was opened; it does not confirm that the article was read.</p>
    <p>Analytics uses opaque article identifiers and fixed section and risk labels. It excludes article URLs, titles, content, search text and administrative pages. It does not use analytics cookies, session replay or individual-user profiles.</p>
    <p>The analytics service processes network metadata to estimate visitor groups using a network-prefix hash and a daily rotating salt. It does not store raw IP addresses or raw browser User-Agent strings in event records. These groups are approximate, not counts of identified people.</p>
    <p>The proposed retention is approximately 24 months for event records and 30 days for backups, subject to University policy. Operational logs are governed separately. Publication of the responsible team’s contact and the final approved policy is required before collection is enabled.</p>
    <p>This browser preference stops future analytics requests from RiskLive. It does not delete records already collected and does not enable collection while the service is disabled.</p>
    <div className="rounded border border-border p-3"><AnalyticsPreference /></div>
  </article></div>;
}
