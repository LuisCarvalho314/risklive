import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { OpsOverviewCards } from "@/components/ops/ops-overview";

describe("ops overview cards", () => {
  it("renders cost and valyu status cards", () => {
    render(
      <OpsOverviewCards
        overview={{
          generatedAt: "2026-02-27T00:00:00.000Z",
          overallStatus: "healthy",
          stages: [],
          schedule: [],
          errorCounts: { day: 0, week: 0, month: 0 },
          warningCounts: { day: 1, week: 2, month: 3 },
          parseErrors: 0,
          costs: {
            llm: {
              dayUsd: 1.23,
              weekUsd: 2.34,
              monthUsd: 3.45,
              dayTokens: 100,
              weekTokens: 200,
              monthTokens: 300,
              quality: {
                status: "partial",
                reason: "mixed",
                rowsInWindow: 10,
                rowsWithExplicitPrice: 4,
                rowsWithDerivedPrice: 5,
                rowsWithoutPrice: 1
              }
            },
            recentBuckets: [],
            valyu: { status: "partial", dayUsd: 0.12, weekUsd: 0.34, monthUsd: 0.56, reason: "partial data" }
          }
        }}
      />
    );

    expect(screen.getByText("LLM Cost (24 hours)")).toBeInTheDocument();
    expect(screen.getByText("$1.2300")).toBeInTheDocument();
    expect(screen.getByText("Tokens (24 hours)")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText(/Quality:/)).toBeInTheDocument();
    expect(screen.getByText("Valyu Cost (24 hours)")).toBeInTheDocument();
    expect(screen.getByText("$0.1200")).toBeInTheDocument();
    expect(screen.getByText(/Status:/)).toBeInTheDocument();
  });
});
