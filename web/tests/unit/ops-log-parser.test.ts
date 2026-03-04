//© 2025 University of Aberdeen. All rights reserved

import { beforeEach, describe, expect, it, vi } from "vitest";

import { filterLogEvents, parseLogLine, readLogEvents } from "@/lib/ops/log-parser";

vi.mock("fs/promises", () => ({
  readFile: vi.fn(),
  default: {
    readFile: vi.fn()
  }
}));

describe("ops log parser", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("parses json lines and tracks parse errors", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.default.readFile).mockResolvedValueOnce(
      [
        '{"ts":"2026-02-27T00:00:00Z","level":"INFO","component":"app.server","operation":"fetch"}',
        "not-json",
        '{"ts":"2026-02-27T00:00:05Z","level":"ERROR","component":"app.server","operation":"report"}'
      ].join("\n")
    );

    const out = await readLogEvents();
    expect(out.events).toHaveLength(2);
    expect(out.parseErrors).toBe(1);
    expect(out.events[0].level).toBe("ERROR");
  });

  it("sorts recent-first for python-style timestamps", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.default.readFile).mockResolvedValueOnce(
      [
        '{"ts":"2026-02-27 02:16:31,064","level":"INFO","component":"services.pipeline","event":"pipeline_stage_end"}',
        '{"ts":"2026-02-27 02:16:58,018","level":"INFO","component":"app.cli","event":"pipeline_run_end"}'
      ].join("\n")
    );

    const out = await readLogEvents();
    expect(out.events[0].event).toBe("pipeline_run_end");
    expect(out.events[1].event).toBe("pipeline_stage_end");
  });

  it("returns empty logs when file is missing", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.default.readFile).mockRejectedValueOnce(
      Object.assign(new Error("missing"), { code: "ENOENT" })
    );

    const out = await readLogEvents();
    expect(out).toEqual({ events: [], parseErrors: 0 });
  });

  it("supports filter by level/component/search", () => {
    const events = [
      { level: "INFO", component: "app.server", operation: "fetch", message: "ok" },
      { level: "ERROR", component: "services.pipeline", operation: "report", message: "failed report" }
    ];
    const filtered = filterLogEvents(events, {
      level: "error",
      component: "pipeline",
      query: "failed"
    });
    expect(filtered).toHaveLength(1);
    expect(filtered[0].operation).toBe("report");
  });

  it("returns null for invalid log line", () => {
    expect(parseLogLine("x")).toBeNull();
  });
});
