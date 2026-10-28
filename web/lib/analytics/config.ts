export type AnalyticsConfig = {
  enabled: boolean;
  entity: string;
  pageviews: boolean;
  articles: boolean;
  features: boolean;
};

export function analyticsConfig(env: Record<string, string | undefined>): AnalyticsConfig {
  return {
    enabled: env.NODE_ENV === "production" && env.LIWAN_ENABLED === "true" && env.ANALYTICS_TEST_MODE !== "true",
    entity: env.LIWAN_ENTITY_ID || "risklive",
    pageviews: env.LIWAN_PAGEVIEWS !== "false",
    articles: env.LIWAN_ARTICLES !== "false",
    features: env.LIWAN_FEATURES !== "false",
  };
}
