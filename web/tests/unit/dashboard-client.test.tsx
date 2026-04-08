//© 2025 University of Aberdeen. All rights reserved

import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDashboardData } from "@/lib/dashboard-client";
import { sampleDashboard } from "@/tests/fixtures/dashboard";

function DashboardProbe({ intervalMs = 50 }: { intervalMs?: number }) {
  const { dashboard, error, isLoading, lastLoadedAt } = useDashboardData({ intervalMs });

  return (
    <div>
      <span data-testid="generated-at">{dashboard.generated_at}</span>
      <span data-testid="topic-keyword">{dashboard.topics[0]?.keyword ?? "none"}</span>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="error">{error ?? "none"}</span>
      <span data-testid="loaded-at">{lastLoadedAt ?? "none"}</span>
    </div>
  );
}

describe("useDashboardData", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads dashboard data from the API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => sampleDashboard,
      })
    );

    render(<DashboardProbe />);

    expect(screen.getByTestId("loading")).toHaveTextContent("true");

    await waitFor(() => {
      expect(screen.getByTestId("topic-keyword")).toHaveTextContent("nuclear policy");
    });
    expect(screen.getByTestId("loading")).toHaveTextContent("false");
    expect(screen.getByTestId("error")).toHaveTextContent("none");
    expect(screen.getByTestId("loaded-at")).not.toHaveTextContent("none");
  });

  it("refreshes on an interval and preserves the last good payload on failure", async () => {
    const refreshedDashboard = {
      ...sampleDashboard,
      generated_at: "2026-02-27T01:00:00+00:00",
      topics: [{ keyword: "fresh topic", response: "Updated" }],
    };

    let callCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async () => {
        callCount += 1;
        if (callCount === 1) {
          return {
            ok: true,
            json: async () => sampleDashboard,
          };
        }
        if (callCount === 2) {
          return {
            ok: true,
            json: async () => refreshedDashboard,
          };
        }
        throw new Error("network down");
      })
    );

    render(<DashboardProbe intervalMs={50} />);

    await waitFor(() => {
      expect(screen.getByTestId("topic-keyword")).toHaveTextContent("fresh topic");
    }, { timeout: 2000 });
    expect(callCount).toBeGreaterThanOrEqual(2);
    expect(screen.getByTestId("generated-at")).toHaveTextContent("2026-02-27T01:00:00+00:00");

    await waitFor(() => {
      expect(screen.getByTestId("error")).toHaveTextContent("network down");
    }, { timeout: 2000 });
    expect(screen.getByTestId("topic-keyword")).toHaveTextContent("fresh topic");
  }, 5000);
});
