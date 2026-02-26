import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/ops/status-aggregator", () => ({
  buildOpsOverview: vi.fn()
}));

describe("api ops overview route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it("returns overview payload", async () => {
    const { buildOpsOverview } = await import("@/lib/ops/status-aggregator");
    vi.mocked(buildOpsOverview).mockResolvedValueOnce({
      generatedAt: "2026-02-27T00:00:00.000Z",
      overallStatus: "healthy",
      stages: [],
      schedule: [],
      errorCounts: { day: 0, week: 0, month: 0 },
      warningCounts: { day: 0, week: 0, month: 0 },
      parseErrors: 0
    });

    const { GET } = await import("@/app/api/ops/overview/route");
    const response = await GET();
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toContain("no-store");
    await expect(response.json()).resolves.toMatchObject({ overallStatus: "healthy" });
  });
});
