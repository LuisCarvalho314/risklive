//© 2025 University of Aberdeen. All rights reserved

import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TreemapExperimentalClient } from "@/components/newsmap/treemap-experimental-client";

vi.mock("@/components/newsmap/treemap-client", () => ({
  TreemapClient: ({
    data,
    weightModeOverride,
    compactControls,
    controlHint,
  }: {
    data: { name?: string; value?: number; children?: Array<{ value?: number }> };
    weightModeOverride?: string;
    compactControls?: boolean;
    controlHint?: string;
  }) => (
    <div data-testid="mock-treemap">
      {data?.name ?? "unknown"}|{String(weightModeOverride ?? "")}|{String(data?.children?.[0]?.value ?? data?.value ?? "")}|{String(compactControls ?? false)}|{controlHint ?? ""}
    </div>
  ),
}));

afterEach(() => {
  cleanup();
});

describe("TreemapExperimentalClient", () => {
  it("renders timeline selector and switches between 30-day and 7-day views", async () => {
    const user = userEvent.setup();

    render(
      <TreemapExperimentalClient
        fallbackTree={{ id: "fallback", name: "Fallback Tree" }}
        timelineResult={{
          mode: "timeline",
          selectedKey: "30d",
          timelines: {
            "30d": {
              totalBatches: 3,
              selectedIndex: 2,
              batches: [
                {
                  index: 0,
                  day: "2026-02-25",
                  filename: "30d_batch.json",
                  tree: { id: "root-full-0", name: "Full Tree 0" },
                },
                {
                  index: 1,
                  day: "2026-02-26",
                  filename: "30d_batch_1.json",
                  tree: { id: "root-full-1", name: "Full Tree 1" },
                },
                {
                  index: 2,
                  day: "2026-02-27",
                  filename: "30d_batch_2.json",
                  tree: { id: "root-full-2", name: "Full Tree 2" },
                },
              ],
            },
            "7d": {
              totalBatches: 1,
              selectedIndex: 0,
              batches: [
                {
                  index: 0,
                  day: "2026-02-27",
                  filename: "7d_batch.json",
                  tree: { id: "root-7d", name: "7D Tree" },
                },
              ],
            },
            "3d": {
              totalBatches: 1,
              selectedIndex: 0,
              batches: [
                {
                  index: 0,
                  day: "2026-02-27",
                  filename: "3d_batch.json",
                  tree: { id: "root-3d", name: "3D Tree" },
                },
              ],
            },
          },
        }}
      />
    );

    expect(screen.getByRole("button", { name: "30 days" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "7 days" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "3 days" })).toBeInTheDocument();
    expect(screen.getByText("2026-02-27")).toBeInTheDocument();
    expect(screen.getByTestId("mock-treemap")).toHaveTextContent("Full Tree 2|value");
    expect(screen.getByTestId("mock-treemap")).toHaveTextContent("|true|Double click a tile to show sources.");
    expect(screen.getByText("0d")).toHaveAttribute("title", "2026-02-27");
    expect(screen.getByText("1d")).toHaveAttribute("title", "2026-02-26");
    expect(screen.getByText("2d")).toHaveAttribute("title", "2026-02-25");

    await user.click(screen.getByRole("button", { name: "7 days" }));
    expect(screen.getByText("2026-02-27")).toBeInTheDocument();
    expect(screen.getByTestId("mock-treemap")).toHaveTextContent("7D Tree|value");
  });

  it("allows selecting the experimental size metric", async () => {
    const user = userEvent.setup();
    render(
      <TreemapExperimentalClient
        fallbackTree={{ id: "fallback", name: "Fallback Tree" }}
        timelineResult={{
          mode: "timeline",
          selectedKey: "30d",
          timelines: {
            "30d": {
              totalBatches: 1,
              selectedIndex: 0,
              batches: [
                {
                  index: 0,
                  day: "2026-02-27",
                  filename: "30d_batch_0.json",
                  tree: {
                    id: "root-full-0",
                    name: "Full Tree 0",
                    children: [
                      {
                        id: "node-1",
                        name: "Node 1",
                        value: 1,
                        meta: {
                          experimentalMetrics: {
                            mappedSourceCount: 9,
                            alphaError: 3,
                            composite: 9,
                          },
                        },
                      },
                    ],
                  },
                },
              ],
            },
          },
        }}
      />
    );

    const currentTreemap = () => {
      const nodes = screen.getAllByTestId("mock-treemap");
      return nodes[nodes.length - 1];
    };

    expect(currentTreemap()).toHaveTextContent("|9");
    await user.click(screen.getByRole("button", { name: "Alpha Error" }));
    expect(currentTreemap()).toHaveTextContent("|3");
    await user.click(screen.getByRole("button", { name: "High -> Small" }));
    expect(currentTreemap()).toHaveTextContent("|3");
  });
});
