import { readLogEvents } from "@/lib/ops/log-parser";
import { buildOpsCosts } from "@/lib/ops/cost-aggregator";
import type {
  OpsLogEvent,
  OpsOverview,
  OpsScheduleStatus,
  OpsStage,
  OpsStageStatus,
  OpsStatus,
  WindowCounts
} from "@/lib/ops/types";

const LOG_STAGE_TO_OPS_STAGE: Record<string, OpsStage> = {
  ingestion: "ingestion",
  fetch: "ingestion",
  save: "ingestion",
  extraction: "extraction",
  extract: "extraction",
  topic: "topic_modeling",
  topic_modeling: "topic_modeling",
  report: "report",
  dashboard: "dashboard_export",
  dashboard_export: "dashboard_export",
  seca: "seca_light",
  seca_light: "seca_light"
};

const OPS_STAGES: OpsStage[] = [
  "ingestion",
  "extraction",
  "topic_modeling",
  "report",
  "dashboard_export",
  "seca_light",
];
const CORE_STAGES: OpsStage[] = ["ingestion", "extraction", "topic_modeling", "report", "dashboard_export"];
const SCHEDULE_CONFIG = [
  { job: "fetch_and_process", hour: 7, minute: 0, intervalMs: 24 * 60 * 60 * 1000 },
  { job: "cleanup_old_data", hour: 6, minute: 30, intervalMs: 24 * 60 * 60 * 1000 }
] as const;

function asDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const direct = new Date(value);
  if (!Number.isNaN(direct.getTime())) return direct;

  // Python logging default format: "YYYY-MM-DD HH:MM:SS,mmm"
  const normalized = value.replace(",", ".").replace(" ", "T");
  const fallback = new Date(normalized);
  if (!Number.isNaN(fallback.getTime())) return fallback;
  return null;
}

function stageFromEvent(event: OpsLogEvent): OpsStage | null {
  const raw = (event.stage ?? "").trim().toLowerCase();
  return LOG_STAGE_TO_OPS_STAGE[raw] ?? null;
}

function stageEventsFor(stage: OpsStage, events: OpsLogEvent[], runId?: string): OpsLogEvent[] {
  return events.filter((event) => {
    if (event.event !== "pipeline_stage_end") return false;
    if (runId && event.run_id !== runId) return false;
    return stageFromEvent(event) === stage;
  });
}

function stageStatusFromEvent(event: OpsLogEvent): OpsStatus {
  const status = (event.stage_status ?? "").toLowerCase();
  if (status === "failed") return "error";
  if (status === "succeeded" || status === "skipped") return "healthy";
  return "degraded";
}

function latestByTs(events: OpsLogEvent[]): OpsLogEvent | null {
  const withTs = events
    .map((event) => ({ event, ts: asDate(event.ts) }))
    .filter((entry): entry is { event: OpsLogEvent; ts: Date } => entry.ts !== null)
    .sort((a, b) => b.ts.getTime() - a.ts.getTime());
  return withTs[0]?.event ?? null;
}

function latestSuccessTs(events: OpsLogEvent[]): string | null {
  const successEvents = events.filter((event) => (event.stage_status ?? "").toLowerCase() === "succeeded");
  const latest = latestByTs(successEvents);
  return latest?.ts ?? null;
}

function buildStageStatus(stage: OpsStage, events: OpsLogEvent[], runId: string | undefined, hasRunEnd: boolean): OpsStageStatus {
  if (!hasRunEnd) {
    return {
      stage,
      status: "missing",
      lastSuccessTs: null,
      lastRunDurationMs: null,
      evidence: ["no pipeline_run_end logs"]
    };
  }

  const stageEvents = stageEventsFor(stage, events, runId);
  const latest = latestByTs(stageEvents);

  if (!latest) {
    if (stage === "seca_light") {
      return {
        stage,
        status: "healthy",
        lastSuccessTs: null,
        lastRunDurationMs: null,
        evidence: ["optional stage absent in latest run"]
      };
    }
    return {
      stage,
      status: "missing",
      lastSuccessTs: null,
      lastRunDurationMs: null,
      evidence: ["no pipeline_stage_end logs for latest run"]
    };
  }

  const evidence = [`log:stage_end:${latest.stage_status ?? "unknown"}`];
  if (latest.operation) evidence.push(`operation:${latest.operation}`);
  if (latest.skip_reason) evidence.push(`skip:${latest.skip_reason}`);
  if (latest.run_id) evidence.push(`run_id:${latest.run_id}`);
  const durations = stageEvents
    .map((event) => event.duration_ms)
    .filter((value): value is number => typeof value === "number");
  const stageDurationMs = durations.length ? durations.reduce((sum, value) => sum + value, 0) : null;

  return {
    stage,
    status: stageStatusFromEvent(latest),
    lastSuccessTs: latestSuccessTs(stageEvents),
    lastRunDurationMs: stageDurationMs,
    evidence
  };
}

function countByWindow(events: OpsLogEvent[], level: string, now: Date): WindowCounts {
  const filtered = events.filter((event) => (event.level ?? "").toUpperCase() === level);
  const countWith = (ms: number) =>
    filtered.filter((event) => {
      const ts = asDate(event.ts);
      return ts ? now.getTime() - ts.getTime() <= ms : false;
    }).length;
  return {
    day: countWith(24 * 60 * 60 * 1000),
    week: countWith(7 * 24 * 60 * 60 * 1000),
    month: countWith(30 * 24 * 60 * 60 * 1000)
  };
}

function previousScheduledInstant(now: Date, hour: number, minute: number): Date {
  const expected = new Date(now);
  expected.setHours(hour, minute, 0, 0);
  if (expected.getTime() > now.getTime()) {
    expected.setDate(expected.getDate() - 1);
  }
  return expected;
}

function buildScheduleStatus(events: OpsLogEvent[], now: Date): OpsScheduleStatus[] {
  const schedulerEvents = events.filter((event) => normalizeString(event.component) === "scheduler");
  return SCHEDULE_CONFIG.map((cfg) => {
    const jobEvents = schedulerEvents.filter((event) => normalizeString(event.job) === cfg.job);
    const starts = jobEvents.filter((event) => event.event === "job_start");
    const completes = jobEvents.filter((event) => event.event === "job_complete");
    const failures = jobEvents.filter((event) => event.event === "job_failed");
    const lastStart = latestByTs(starts);
    const lastComplete = latestByTs(completes);
    const lastFailed = latestByTs(failures);
    const prevExpected = previousScheduledInstant(now, cfg.hour, cfg.minute);
    const nextExpected = new Date(prevExpected.getTime() + cfg.intervalMs);
    const graceMs = Math.max(5 * 60 * 1000, Math.floor(cfg.intervalMs * 0.1));
    const dueBy = new Date(prevExpected.getTime() + graceMs);
    const evidence: string[] = [];

    if (!jobEvents.length) {
      return {
        job: cfg.job,
        status: "missing",
        lastStartTs: null,
        lastCompleteTs: null,
        lastFailedTs: null,
        nextExpectedTs: nextExpected.toISOString(),
        graceMinutes: Math.round(graceMs / 60000),
        evidence: ["no scheduler events for job"]
      };
    }

    const lastFailedAt = asDate(lastFailed?.ts)?.getTime() ?? 0;
    const lastCompleteAt = asDate(lastComplete?.ts)?.getTime() ?? 0;
    const hasRecentFailure = lastFailedAt >= prevExpected.getTime() && lastFailedAt > lastCompleteAt;
    if (hasRecentFailure) {
      evidence.push("latest scheduler outcome is job_failed");
      return {
        job: cfg.job,
        status: "error",
        lastStartTs: lastStart?.ts ?? null,
        lastCompleteTs: lastComplete?.ts ?? null,
        lastFailedTs: lastFailed?.ts ?? null,
        nextExpectedTs: nextExpected.toISOString(),
        graceMinutes: Math.round(graceMs / 60000),
        evidence
      };
    }

    const completedOnTime =
      lastCompleteAt >= prevExpected.getTime() && lastCompleteAt <= dueBy.getTime();
    const startedOnTime = (() => {
      const lastStartAt = asDate(lastStart?.ts)?.getTime() ?? 0;
      return lastStartAt >= prevExpected.getTime() && lastStartAt <= dueBy.getTime();
    })();
    if (completedOnTime || startedOnTime || now.getTime() <= dueBy.getTime()) {
      evidence.push("within schedule SLA window");
      return {
        job: cfg.job,
        status: "healthy",
        lastStartTs: lastStart?.ts ?? null,
        lastCompleteTs: lastComplete?.ts ?? null,
        lastFailedTs: lastFailed?.ts ?? null,
        nextExpectedTs: nextExpected.toISOString(),
        graceMinutes: Math.round(graceMs / 60000),
        evidence
      };
    }

    evidence.push("past expected run time + grace");
    return {
      job: cfg.job,
      status: "overdue",
      lastStartTs: lastStart?.ts ?? null,
      lastCompleteTs: lastComplete?.ts ?? null,
      lastFailedTs: lastFailed?.ts ?? null,
      nextExpectedTs: nextExpected.toISOString(),
      graceMinutes: Math.round(graceMs / 60000),
      evidence
    };
  });
}

function normalizeString(value: string | undefined): string {
  return (value ?? "").trim().toLowerCase();
}

function overallFromRunAndStages(
  runEnd: OpsLogEvent | null,
  stages: OpsStageStatus[],
  schedule: OpsScheduleStatus[],
  hasSchedulerTelemetry: boolean
): OpsOverview["overallStatus"] {
  if (hasSchedulerTelemetry && schedule.some((item) => item.status === "error")) return "error";
  if (!runEnd) return "degraded";
  const runStatus = (runEnd?.run_status ?? "").toLowerCase();
  if (runStatus === "failed") return "error";
  if (hasSchedulerTelemetry && schedule.some((item) => item.status === "overdue" || item.status === "missing")) {
    return "degraded";
  }
  const byStage = new Map(stages.map((stage) => [stage.stage, stage]));
  const coreStatuses = CORE_STAGES.map((stage) => byStage.get(stage)?.status ?? "missing");
  if (coreStatuses.some((status) => status === "error")) return "error";
  const coreAllHealthy = coreStatuses.every((status) => status === "healthy");
  if (runStatus === "succeeded" && coreAllHealthy) {
    const secaStatus = byStage.get("seca_light")?.status ?? "missing";
    return secaStatus === "error" || secaStatus === "degraded" ? "degraded" : "healthy";
  }
  if (coreStatuses.some((status) => status === "missing")) return "degraded";
  if (coreStatuses.some((status) => status !== "healthy")) return "degraded";
  return "healthy";
}

export async function buildOpsOverview(now = new Date()): Promise<OpsOverview> {
  const [{ events, parseErrors }, costs] = await Promise.all([readLogEvents(), buildOpsCosts(now)]);
  const runEnd = latestByTs(events.filter((event) => event.event === "pipeline_run_end"));
  const runId = runEnd?.run_id;
  const stages: OpsStageStatus[] = OPS_STAGES.map((stage) => buildStageStatus(stage, events, runId, Boolean(runEnd)));
  const schedule = buildScheduleStatus(events, now);
  const hasSchedulerTelemetry = events.some((event) => normalizeString(event.component) === "scheduler");

  return {
    generatedAt: now.toISOString(),
    overallStatus: overallFromRunAndStages(runEnd, stages, schedule, hasSchedulerTelemetry),
    stages,
    schedule,
    errorCounts: countByWindow(events, "ERROR", now),
    warningCounts: countByWindow(events, "WARNING", now),
    parseErrors,
    costs
  };
}
