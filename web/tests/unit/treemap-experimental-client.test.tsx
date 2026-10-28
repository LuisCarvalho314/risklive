//© 2025 University of Aberdeen. All rights reserved

import React from "react";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRoot, type Root } from "react-dom/client";
import { flushSync } from "react-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TreemapExperimentalClient } from "@/components/newsmap/treemap-experimental-client";

const mounts = vi.hoisted(() => ({ count: 0 }));

vi.mock("@/components/newsmap/treemap-client", () => ({
  TreemapClient: ({
    data,
    weightModeOverride,
    compactControls,
    singleHierarchyColor,
    controlHint,
  }: {
    data: { name?: string; value?: number; children?: Array<{ value?: number }> };
    weightModeOverride?: string;
    compactControls?: boolean;
    singleHierarchyColor?: boolean;
    controlHint?: string;
  }) => {
    const [mount] = React.useState(() => ++mounts.count);
    return (
    <div data-mount={mount} data-testid="mock-treemap" data-single-color={String(singleHierarchyColor ?? false)}>
      {data?.name ?? "unknown"}|{String(weightModeOverride ?? "")}|{String(data?.children?.[0]?.value ?? data?.value ?? "")}|{String(compactControls ?? false)}|{controlHint ?? ""}
    </div>
  );
  },
}));

const mountedRoots: Array<{ root: Root; container: HTMLDivElement }> = [];

function renderIntoDom(node: React.ReactNode) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  flushSync(() => {
    root.render(node);
  });
  mountedRoots.push({ root, container });
  return root;
}

afterEach(() => {
  while (mountedRoots.length) {
    const mounted = mountedRoots.pop();
    if (!mounted) continue;
    flushSync(() => {
      mounted.root.unmount();
    });
    mounted.container.remove();
  }
});

describe("TreemapExperimentalClient", () => {
  it("renders timeline selector and switches between 30-day and 7-day views", async () => {
    const user = userEvent.setup();

    renderIntoDom(
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
    renderIntoDom(
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

    expect(currentTreemap()).toHaveTextContent("|1");
    await user.click(screen.getByRole("button", { name: "Alpha Error" }));
    expect(currentTreemap()).toHaveTextContent("|1");
    await user.click(screen.getByRole("button", { name: "Beta Error" }));
    expect(screen.getByRole("status")).toHaveTextContent("scopes available");
    await user.click(screen.getByRole("button", { name: "High -> Small" }));
    expect(currentTreemap()).toHaveTextContent("|1");
  });
});

it("restores the original V2 shell and single colour treemap without replacement controls", () => {
  renderIntoDom(<TreemapExperimentalClient fallbackTree={{ name: "Old dashboard" }} timelineResult={{
    mode: "v2", batch: 2, day: "2026-10-28", retainedSourceCount: 148,
    tree: { id: "root::newsmap", name: "SECALight V2", children: [{ name: "reactor", value: 148 }] },
    decisions: [{ path: [], errors: { alpha: .1, beta: .2, importance: .3 }, reconstructed: true }],
  }} />);
  expect(screen.getByText("Experimental")).toBeInTheDocument();
  expect(screen.queryByText("SECALight V2 · Experimental")).not.toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByText(/retained sources/)).not.toBeInTheDocument();
  expect(screen.queryByText(/fallback data/)).not.toBeInTheDocument();
  expect(screen.getByTestId("mock-treemap")).toHaveAttribute("data-single-color", "true");
  expect(screen.getByTestId("mock-treemap").parentElement).toHaveClass("pt-2", "overflow-hidden");
  expect(screen.getByTestId("mock-treemap")).toHaveTextContent("SECALight V2|value");
  expect(screen.queryByRole("button", { name: "30 days" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Alpha Error" })).not.toBeInTheDocument();
});

it("shows an empty V2 model without a stale fallback tree", () => {
  renderIntoDom(<TreemapExperimentalClient fallbackTree={{ name: "Old dashboard" }} timelineResult={{
    mode: "v2", batch: 4, day: "2026-10-30", retainedSourceCount: 0,
    tree: { id: "root::newsmap", name: "SECALight V2", children: [] }, decisions: [],
  }} />);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByTestId("mock-treemap")).toHaveTextContent("SECALight V2");
  expect(screen.queryByText("Old dashboard")).not.toBeInTheDocument();
});

it("keeps the treemap mounted across V2 batches and mode transitions", () => {
  const fallbackTree = { name: "Fallback" };
  const v2 = { mode: "v2" as const, batch: 2, day: "2026-10-28", retainedSourceCount: 1,
    tree: { id: "root::newsmap", name: "V2", children: [{ name: "topic", value: 1 }] }, decisions: [] };
  const root = renderIntoDom(<TreemapExperimentalClient fallbackTree={fallbackTree} timelineResult={v2} />);
  const initialMount = screen.getByTestId("mock-treemap").getAttribute("data-mount");
  for (const result of [
    { ...v2, batch: 3 },
    { mode: "fallback" as const, reason: "invalid" },
    { mode: "timeline" as const, selectedKey: "30d" as const, timelines: {} },
    v2,
  ]) {
    flushSync(() => root.render(<TreemapExperimentalClient fallbackTree={fallbackTree} timelineResult={result} />));
    expect(screen.getByTestId("mock-treemap")).toHaveAttribute("data-mount", initialMount);
  }
});
