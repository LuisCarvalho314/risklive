import Ajv from "ajv";
import type { ErrorObject } from "ajv";

import dashboardSchema from "@/schema/dashboard.schema.json";

export type AlertItem = {
  title: string;
  url?: string | null;
  description?: string;
  timestamp?: string | null;
  alert_flag?: string;
  alert_reason?: string;
  news_category?: string;
  short_summary?: string;
  relevance?: string;
};

export type AlertsSection = {
  nuclear: AlertItem[];
  non_nuclear: Record<string, AlertItem[]>;
};

export type RecentAlerts = {
  red: AlertItem[];
  yellow: AlertItem[];
  green: AlertItem[];
};

export type FlaggedAlerts = {
  red: AlertItem[];
  yellow: AlertItem[];
};

export type TreemapNode = {
  name: string;
  id?: string;
  value?: number | null;
  children?: TreemapNode[];
  itemStyle?: {
    color?: string;
  };
  meta?: {
    title?: string;
    url?: string | null;
    category?: string;
    alertFlag?: string;
    alertReason?: string;
    timestamp?: string | null;
    shortSummary?: string;
    description?: string;
    topic?: string;
    topicLabel?: string;
    sourceCount?: number;
    sourceRefs?: Array<{
      id: string;
      title?: string;
      url?: string | null;
      isUrl?: boolean;
    }>;
    experimentalMetrics?: {
      mappedSourceCount?: number;
      combinedError?: number;
      alphaError?: number;
      betaError?: number;
      wordImportanceError?: number;
      triggeredScore?: number;
      composite?: number;
      recency?: number;
      wordMass?: number;
      hktSignificance?: number;
      triggerIntensity?: number;
      activeWindow?: number;
    };
  };
};

export type TopicEntry = {
  keyword: string;
  response: string;
};

export type DashboardData = {
  generated_at: string;
  alerts: AlertsSection;
  recent_alerts: RecentAlerts;
  flagged_alerts: FlaggedAlerts;
  newsmap: TreemapNode;
  topics: TopicEntry[];
  topic_tree: string;
};

export class DashboardValidationError extends Error {
  details: string[];

  constructor(message: string, details: string[]) {
    super(message);
    this.name = "DashboardValidationError";
    this.details = details;
  }
}

const defaultDashboard: DashboardData = {
  generated_at: new Date(0).toISOString(),
  alerts: { nuclear: [], non_nuclear: {} },
  recent_alerts: { red: [], yellow: [], green: [] },
  flagged_alerts: { red: [], yellow: [] },
  newsmap: { name: "All News", children: [] },
  topics: [],
  topic_tree: ""
};

const ajv = new Ajv({
  allErrors: true,
  strict: false,
  formats: {
    "date-time": true,
    uri: true
  }
});
const validateDashboard = ajv.compile(dashboardSchema as object);

function formatValidationErrors(): string[] {
  return (validateDashboard.errors ?? []).map((error: ErrorObject) => {
    const location = error.instancePath || "/";
    return `${location} ${error.message ?? "invalid value"}`.trim();
  });
}

export function parseDashboardPayload(payload: unknown): DashboardData {
  if (!validateDashboard(payload)) {
    throw new DashboardValidationError("Invalid dashboard payload", formatValidationErrors());
  }
  return payload as DashboardData;
}

export function parseDashboardString(raw: string): DashboardData {
  const parsed = JSON.parse(raw);
  return parseDashboardPayload(parsed);
}

export function getDefaultDashboard(): DashboardData {
  return defaultDashboard;
}
