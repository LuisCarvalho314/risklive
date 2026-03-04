//© 2025 University of Aberdeen. All rights reserved

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/ops/log-parser", () => ({
  readLogEvents: vi.fn(),
  filterLogEvents: vi.fn()
}));

describe("api ops logs route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it("returns filtered events", async () => {
    const { readLogEvents, filterLogEvents } = await import("@/lib/ops/log-parser");
    vi.mocked(readLogEvents).mockResolvedValueOnce({
      events: [{ level: "ERROR", component: "app.server" }],
      parseErrors: 1
    });
    vi.mocked(filterLogEvents).mockReturnValueOnce([{ level: "ERROR", component: "app.server" }]);

    const { GET } = await import("@/app/api/ops/logs/route");
    const request = new Request("http://localhost/api/ops/logs?level=error&component=app&limit=10");
    const response = await GET(request);

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.count).toBe(1);
    expect(body.parseErrors).toBe(1);
    expect(vi.mocked(filterLogEvents)).toHaveBeenCalledWith(
      [{ level: "ERROR", component: "app.server" }],
      expect.objectContaining({
        level: "error",
        component: "app",
        limit: 10
      })
    );
  });
});

