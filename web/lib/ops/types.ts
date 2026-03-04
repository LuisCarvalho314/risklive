export type OpsStatus = "healthy" | "stale" | "degraded" | "missing" | "error";

export type OpsStage =
  | "ingestion"
  | "extraction"
  | "topic_modeling"
  | "report"
  | "dashboard_export"
  | "seca_light";

export type OpsLogEvent = {
  ts?: string;
  level?: string;
  logger?: string;
  event?: string;
  message?: string;
  correlation_id?: string;
  component?: string;
  operation?: string;
  route?: string;
  command?: string;
  job?: string;
  status?: number | string;
  duration_ms?: number;
  error_code?: string;
  retryable?: boolean;
  run_id?: string;
  stage?: string;
  stage_status?: string;
  run_status?: string;
  skip_reason?: string;
};

export type OpsArtifact = {
  id: string;
  path: string;
  required: boolean;
  exists: boolean;
  modifiedAt: string | null;
  sizeBytes: number;
  rowCount: number | null;
};

export type OpsStageStatus = {
  stage: OpsStage;
  status: OpsStatus;
  lastSuccessTs: string | null;
  lastRunDurationMs: number | null;
  evidence: string[];
};

export type OpsScheduleHealth = "healthy" | "overdue" | "missing" | "error";

export type OpsScheduleStatus = {
  job: string;
  status: OpsScheduleHealth;
  lastStartTs: string | null;
  lastCompleteTs: string | null;
  lastFailedTs: string | null;
  nextExpectedTs: string | null;
  graceMinutes: number;
  evidence: string[];
};

export type WindowCounts = {
  day: number;
  week: number;
  month: number;
};

export type OpsOverview = {
  generatedAt: string;
  overallStatus: "healthy" | "degraded" | "error";
  stages: OpsStageStatus[];
  schedule: OpsScheduleStatus[];
  errorCounts: WindowCounts;
  warningCounts: WindowCounts;
  parseErrors: number;
  costs: OpsCosts;
};

export type OpsCostWindow = {
  dayUsd: number;
  weekUsd: number;
  monthUsd: number;
  dayTokens: number;
  weekTokens: number;
  monthTokens: number;
};

export type OpsLlmCostQuality = {
  status: "available" | "partial" | "derived_only" | "unavailable";
  reason: string;
  rowsInWindow: number;
  rowsWithExplicitPrice: number;
  rowsWithDerivedPrice: number;
  rowsWithoutPrice: number;
  evidence?: string[];
};

export type OpsCostRun = {
  bucketStartTs: string;
  bucketEndTs: string;
  llmUsd: number;
  valyuUsd: number;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
};

export type OpsValyuCostStatus = {
  status: "available" | "partial" | "unavailable";
  dayUsd: number;
  weekUsd: number;
  monthUsd: number;
  reason: string;
  evidence?: string[];
};

export type OpsCosts = {
  llm: OpsCostWindow & {
    quality: OpsLlmCostQuality;
  };
  recentBuckets: OpsCostRun[];
  valyu: OpsValyuCostStatus;
};
