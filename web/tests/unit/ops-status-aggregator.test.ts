import { beforeEach, describe, expect, it, vi } from "vitest";

import { buildOpsOverview } from "@/lib/ops/status-aggregator";

vi.mock("@/lib/ops/log-parser", () => ({
  readLogEvents: vi.fn()
}));

describe("ops status aggregator", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("derives healthy stage/run status from pipeline lifecycle logs", async () => {
    const { readLogEvents } = await import("@/lib/ops/log-parser");
    const now = new Date("2026-02-27T00:00:00.000Z");

    vi.mocked(readLogEvents).mockResolvedValue({
      parseErrors: 0,
      events: [
        {
          ts: "2026-02-26T23:59:59.000Z",
          event: "pipeline_run_end",
          run_id: "run-1",
          run_status: "succeeded",
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:59:00.000Z",
          event: "pipeline_stage_end",
          run_id: "run-1",
          stage: "ingestion",
          stage_status: "succeeded",
          duration_ms: 1100,
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:59:05.000Z",
          event: "pipeline_stage_end",
          run_id: "run-1",
          stage: "extraction",
          stage_status: "succeeded",
          duration_ms: 2200,
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:59:10.000Z",
          event: "pipeline_stage_end",
          run_id: "run-1",
          stage: "topic",
          stage_status: "succeeded",
          duration_ms: 3300,
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:59:15.000Z",
          event: "pipeline_stage_end",
          run_id: "run-1",
          stage: "report",
          stage_status: "skipped",
          skip_reason: "no_reportable_red_topics",
          duration_ms: 440,
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:59:20.000Z",
          event: "pipeline_stage_end",
          run_id: "run-1",
          stage: "dashboard",
          stage_status: "succeeded",
          duration_ms: 550,
          level: "INFO"
        }
      ]
    });

    const overview = await buildOpsOverview(now);
    expect(overview.overallStatus).toBe("healthy");
    expect(overview.stages.every((stage) => stage.status === "healthy")).toBe(true);
    expect(overview.stages.find((stage) => stage.stage === "report")?.lastSuccessTs).toBeNull();
    expect(overview.stages.find((stage) => stage.stage === "report")?.evidence.join(" ")).toContain(
      "skip:no_reportable_red_topics"
    );
  });

  it("uses run+stage failure logs for error status and counts windows", async () => {
    const { readLogEvents } = await import("@/lib/ops/log-parser");
    const now = new Date("2026-02-27T00:00:00.000Z");

    vi.mocked(readLogEvents).mockResolvedValue({
      parseErrors: 2,
      events: [
        {
          ts: "2026-02-26T23:58:30.000Z",
          event: "pipeline_run_end",
          run_id: "run-2",
          run_status: "failed",
          level: "ERROR"
        },
        {
          ts: "2026-02-26T23:58:20.000Z",
          event: "pipeline_stage_end",
          run_id: "run-2",
          stage: "extraction",
          stage_status: "failed",
          duration_ms: 900,
          level: "ERROR"
        },
        { ts: "2026-02-26T23:55:00.000Z", level: "WARNING", component: "app.server", operation: "report" }
      ]
    });

    const overview = await buildOpsOverview(now);
    expect(overview.overallStatus).toBe("error");
    expect(overview.stages.find((stage) => stage.stage === "extraction")?.status).toBe("error");
    expect(overview.errorCounts.day).toBe(2);
    expect(overview.warningCounts.week).toBe(1);
    expect(overview.parseErrors).toBe(2);
  });

  it("is degraded with missing stages when no pipeline_run_end exists", async () => {
    const { readLogEvents } = await import("@/lib/ops/log-parser");
    const now = new Date("2026-02-27T00:00:00.000Z");

    vi.mocked(readLogEvents).mockResolvedValue({
      parseErrors: 0,
      events: [
        {
          ts: "2026-02-26T23:59:00.000Z",
          event: "pipeline_stage_end",
          run_id: "run-orphan",
          stage: "ingestion",
          stage_status: "succeeded",
          duration_ms: 1100,
          level: "INFO"
        }
      ]
    });

    const overview = await buildOpsOverview(now);
    expect(overview.overallStatus).toBe("degraded");
    expect(overview.stages.every((stage) => stage.status === "missing")).toBe(true);
    expect(overview.stages[0]?.evidence.join(" ")).toContain("no pipeline_run_end logs");
  });

  it("does not backfill missing stages from older runs", async () => {
    const { readLogEvents } = await import("@/lib/ops/log-parser");
    const now = new Date("2026-02-27T00:00:00.000Z");

    vi.mocked(readLogEvents).mockResolvedValue({
      parseErrors: 0,
      events: [
        {
          ts: "2026-02-26T23:59:59.000Z",
          event: "pipeline_run_end",
          run_id: "run-2",
          run_status: "succeeded",
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:49:59.000Z",
          event: "pipeline_run_end",
          run_id: "run-1",
          run_status: "succeeded",
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:49:20.000Z",
          event: "pipeline_stage_end",
          run_id: "run-1",
          stage: "report",
          stage_status: "succeeded",
          duration_ms: 500,
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:59:20.000Z",
          event: "pipeline_stage_end",
          run_id: "run-2",
          stage: "ingestion",
          stage_status: "succeeded",
          duration_ms: 500,
          level: "INFO"
        }
      ]
    });

    const overview = await buildOpsOverview(now);
    expect(overview.overallStatus).toBe("degraded");
    expect(overview.stages.find((stage) => stage.stage === "report")?.status).toBe("missing");
    expect(overview.stages.find((stage) => stage.stage === "report")?.evidence.join(" ")).toContain(
      "latest run"
    );
  });

  it("maps cli stage aliases (fetch/save/extract) to ops stages", async () => {
    const { readLogEvents } = await import("@/lib/ops/log-parser");
    const now = new Date("2026-02-27T00:00:00.000Z");

    vi.mocked(readLogEvents).mockResolvedValue({
      parseErrors: 0,
      events: [
        {
          ts: "2026-02-26T23:59:59.000Z",
          event: "pipeline_run_end",
          run_id: "run-cli",
          run_status: "succeeded",
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:59:00.000Z",
          event: "pipeline_stage_end",
          run_id: "run-cli",
          stage: "fetch",
          stage_status: "succeeded",
          duration_ms: 100,
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:59:01.000Z",
          event: "pipeline_stage_end",
          run_id: "run-cli",
          stage: "save",
          stage_status: "succeeded",
          duration_ms: 50,
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:59:05.000Z",
          event: "pipeline_stage_end",
          run_id: "run-cli",
          stage: "extract",
          stage_status: "succeeded",
          duration_ms: 200,
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:59:10.000Z",
          event: "pipeline_stage_end",
          run_id: "run-cli",
          stage: "topic",
          stage_status: "succeeded",
          duration_ms: 300,
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:59:15.000Z",
          event: "pipeline_stage_end",
          run_id: "run-cli",
          stage: "report",
          stage_status: "succeeded",
          duration_ms: 400,
          level: "INFO"
        },
        {
          ts: "2026-02-26T23:59:20.000Z",
          event: "pipeline_stage_end",
          run_id: "run-cli",
          stage: "dashboard_export",
          stage_status: "succeeded",
          duration_ms: 500,
          level: "INFO"
        }
      ]
    });

    const overview = await buildOpsOverview(now);
    expect(overview.overallStatus).toBe("healthy");
    expect(overview.stages.every((stage) => stage.status === "healthy")).toBe(true);
    expect(overview.stages.find((stage) => stage.stage === "ingestion")?.lastRunDurationMs).toBe(150);
  });

  it("parses python-style timestamps and still computes healthy status", async () => {
    const { readLogEvents } = await import("@/lib/ops/log-parser");
    const now = new Date("2026-02-27T02:20:00.000Z");

    vi.mocked(readLogEvents).mockResolvedValue({
      parseErrors: 0,
      events: [
        {
          ts: "2026-02-27 02:16:58,018",
          event: "pipeline_run_end",
          run_id: "run-py",
          run_status: "succeeded",
          level: "INFO"
        },
        {
          ts: "2026-02-27 02:16:31,064",
          event: "pipeline_stage_end",
          run_id: "run-py",
          stage: "extract",
          stage_status: "succeeded",
          duration_ms: 311486,
          level: "INFO"
        },
        {
          ts: "2026-02-27 02:16:38,723",
          event: "pipeline_stage_end",
          run_id: "run-py",
          stage: "topic",
          stage_status: "succeeded",
          duration_ms: 7655,
          level: "INFO"
        },
        {
          ts: "2026-02-27 02:16:57,990",
          event: "pipeline_stage_end",
          run_id: "run-py",
          stage: "report",
          stage_status: "succeeded",
          duration_ms: 19265,
          level: "INFO"
        },
        {
          ts: "2026-02-27 02:16:58,018",
          event: "pipeline_stage_end",
          run_id: "run-py",
          stage: "dashboard_export",
          stage_status: "succeeded",
          duration_ms: 27,
          level: "INFO"
        },
        {
          ts: "2026-02-27 02:16:20,000",
          event: "pipeline_stage_end",
          run_id: "run-py",
          stage: "fetch",
          stage_status: "succeeded",
          duration_ms: 10,
          level: "INFO"
        },
        {
          ts: "2026-02-27 02:16:25,000",
          event: "pipeline_stage_end",
          run_id: "run-py",
          stage: "save",
          stage_status: "succeeded",
          duration_ms: 8,
          level: "INFO"
        }
      ]
    });

    const overview = await buildOpsOverview(now);
    expect(overview.overallStatus).toBe("healthy");
    expect(overview.stages.every((stage) => stage.status === "healthy")).toBe(true);
  });

  it("degrades overall when scheduler job is overdue", async () => {
    const { readLogEvents } = await import("@/lib/ops/log-parser");
    const now = new Date("2026-02-27T12:00:00.000Z");

    vi.mocked(readLogEvents).mockResolvedValue({
      parseErrors: 0,
      events: [
        { ts: "2026-02-27T11:59:59.000Z", event: "pipeline_run_end", run_id: "run-1", run_status: "succeeded", level: "INFO" },
        { ts: "2026-02-27T11:50:00.000Z", event: "pipeline_stage_end", run_id: "run-1", stage: "fetch", stage_status: "succeeded", duration_ms: 100, level: "INFO" },
        { ts: "2026-02-27T11:50:01.000Z", event: "pipeline_stage_end", run_id: "run-1", stage: "extract", stage_status: "succeeded", duration_ms: 100, level: "INFO" },
        { ts: "2026-02-27T11:50:02.000Z", event: "pipeline_stage_end", run_id: "run-1", stage: "topic", stage_status: "succeeded", duration_ms: 100, level: "INFO" },
        { ts: "2026-02-27T11:50:03.000Z", event: "pipeline_stage_end", run_id: "run-1", stage: "report", stage_status: "succeeded", duration_ms: 100, level: "INFO" },
        { ts: "2026-02-27T11:50:04.000Z", event: "pipeline_stage_end", run_id: "run-1", stage: "dashboard_export", stage_status: "succeeded", duration_ms: 100, level: "INFO" },
        { ts: "2026-02-26T07:05:00.000Z", event: "job_complete", component: "scheduler", job: "fetch_and_process", level: "INFO" },
        { ts: "2026-02-27T06:35:00.000Z", event: "job_complete", component: "scheduler", job: "cleanup_old_data", level: "INFO" }
      ]
    });

    const overview = await buildOpsOverview(now);
    expect(overview.overallStatus).toBe("degraded");
    const fetchJob = overview.schedule.find((item) => item.job === "fetch_and_process");
    expect(fetchJob?.status).toBe("overdue");
    expect(fetchJob?.graceMinutes).toBe(144);
  });

  it("escalates to error when scheduler latest outcome is job_failed", async () => {
    const { readLogEvents } = await import("@/lib/ops/log-parser");
    const now = new Date("2026-02-27T08:00:00.000Z");

    vi.mocked(readLogEvents).mockResolvedValue({
      parseErrors: 0,
      events: [
        { ts: "2026-02-27T07:59:59.000Z", event: "pipeline_run_end", run_id: "run-1", run_status: "succeeded", level: "INFO" },
        { ts: "2026-02-27T07:59:50.000Z", event: "pipeline_stage_end", run_id: "run-1", stage: "fetch", stage_status: "succeeded", duration_ms: 100, level: "INFO" },
        { ts: "2026-02-27T07:59:51.000Z", event: "pipeline_stage_end", run_id: "run-1", stage: "extract", stage_status: "succeeded", duration_ms: 100, level: "INFO" },
        { ts: "2026-02-27T07:59:52.000Z", event: "pipeline_stage_end", run_id: "run-1", stage: "topic", stage_status: "succeeded", duration_ms: 100, level: "INFO" },
        { ts: "2026-02-27T07:59:53.000Z", event: "pipeline_stage_end", run_id: "run-1", stage: "report", stage_status: "succeeded", duration_ms: 100, level: "INFO" },
        { ts: "2026-02-27T07:59:54.000Z", event: "pipeline_stage_end", run_id: "run-1", stage: "dashboard_export", stage_status: "succeeded", duration_ms: 100, level: "INFO" },
        { ts: "2026-02-27T07:10:00.000Z", event: "job_failed", component: "scheduler", job: "fetch_and_process", level: "ERROR" }
      ]
    });

    const overview = await buildOpsOverview(now);
    expect(overview.overallStatus).toBe("error");
    expect(overview.schedule.find((item) => item.job === "fetch_and_process")?.status).toBe("error");
  });
});
