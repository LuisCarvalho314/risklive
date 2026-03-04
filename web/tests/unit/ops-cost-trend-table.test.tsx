//© 2025 University of Aberdeen. All rights reserved

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { CostTrendTable } from "@/components/ops/cost-trend-table";

describe("ops cost trend table", () => {
  it("renders cost buckets", () => {
    render(
      <CostTrendTable
        buckets={[
          {
            bucketStartTs: "2026-02-27T10:00:00.000Z",
            bucketEndTs: "2026-02-27T16:00:00.000Z",
            llmUsd: 0.1234,
            valyuUsd: 0.0234,
            promptTokens: 10,
            completionTokens: 20,
            totalTokens: 30
          }
        ]}
      />
    );

    expect(screen.getByText("LLM Cost Trends")).toBeInTheDocument();
    expect(screen.getByText("$0.1234")).toBeInTheDocument();
    expect(screen.getByText("$0.0234")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(<CostTrendTable buckets={[]} />);
    expect(screen.getByText("No cost buckets available.")).toBeInTheDocument();
  });
});
