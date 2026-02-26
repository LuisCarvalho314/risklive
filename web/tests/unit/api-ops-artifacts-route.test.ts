import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/ops/artifact-inspector", () => ({
  inspectArtifacts: vi.fn()
}));

describe("api ops artifacts route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it("returns artifact payload", async () => {
    const { inspectArtifacts } = await import("@/lib/ops/artifact-inspector");
    vi.mocked(inspectArtifacts).mockResolvedValueOnce([
      {
        id: "report",
        path: "results/data/df_report.csv",
        required: true,
        exists: true,
        modifiedAt: "2026-02-27T00:00:00.000Z",
        sizeBytes: 42,
        rowCount: 2
      }
    ]);

    const { GET } = await import("@/app/api/ops/artifacts/route");
    const response = await GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      artifacts: [
        {
          id: "report",
          path: "results/data/df_report.csv",
          required: true,
          exists: true,
          modifiedAt: "2026-02-27T00:00:00.000Z",
          sizeBytes: 42,
          rowCount: 2
        }
      ]
    });
  });
});

