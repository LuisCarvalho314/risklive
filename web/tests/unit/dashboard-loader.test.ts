//© 2025 University of Aberdeen. All rights reserved

import { beforeEach, describe, expect, it, vi } from "vitest";

import { getDefaultDashboard, loadDashboard, parseDashboardPayload } from "@/lib/dashboard";
import { sampleDashboard } from "@/tests/fixtures/dashboard";

vi.mock("fs/promises", () => ({
  readFile: vi.fn(),
  default: {
    readFile: vi.fn()
  }
}));

describe("dashboard loader", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("parses valid dashboard payload", () => {
    const parsed = parseDashboardPayload(sampleDashboard);
    expect(parsed.newsmap.name).toBe("All News");
    expect(parsed.topics[0].keyword).toBe("nuclear policy");
  });

  it("rejects malformed dashboard payload", () => {
    expect(() => parseDashboardPayload({ generated_at: "x" })).toThrowError(
      "Invalid dashboard payload"
    );
  });

  it("returns default dashboard when file is missing", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.default.readFile).mockRejectedValueOnce(
      Object.assign(new Error("missing"), { code: "ENOENT" })
    );
    const out = await loadDashboard();
    expect(out).toEqual(getDefaultDashboard());
  });

  it("throws when dashboard file contains invalid shape", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.default.readFile).mockResolvedValueOnce(
      JSON.stringify({ generated_at: "x", newsmap: { name: "Only" } })
    );
    await expect(loadDashboard()).rejects.toThrowError("Invalid dashboard payload");
  });
});
