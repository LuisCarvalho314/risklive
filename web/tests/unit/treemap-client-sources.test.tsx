//© 2025 University of Aberdeen. All rights reserved

import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "@testing-library/react";

import { TreemapClient } from "@/components/newsmap/treemap-client";

vi.mock("@visx/responsive", () => ({
  ParentSize: ({ children }: { children: (size: { width: number; height: number }) => React.ReactNode }) =>
    <>{children({ width: 900, height: 600 })}</>,
}));

vi.mock("@/components/newsmap/treemap-canvas", () => ({
  TreemapCanvas: ({
    setTooltip,
  }: {
    setTooltip: (value: { x: number; y: number; node: unknown } | null) => void;
  }) => (
    <button
      type="button"
      onClick={() =>
        setTooltip({
          x: 100,
          y: 120,
          node: {
            id: "node::1",
            name: "Node 1",
            meta: {
              title: "Node 1",
              sourceRefs: [
                {
                  id: "row_000001",
                  title: "Example headline",
                  url: "https://example.com/a",
                  isUrl: false,
                },
                { id: "opaque-id-9", url: null, isUrl: false },
              ],
            },
          },
        })
      }
    >
      show-tooltip
    </button>
  ),
}));

afterEach(() => cleanup());

describe("TreemapClient source routing popover", () => {
  it("shows URL and non-URL sources in tooltip popover", async () => {
    const user = userEvent.setup();
    render(
      <TreemapClient
        data={{
          id: "root::newsmap",
          name: "SECA Tree",
          children: [{ id: "node::1", name: "Node 1" }],
        }}
        preserveHierarchy
      />
    );

    await user.click(screen.getByRole("button", { name: "show-tooltip" }));
    await user.click(screen.getByRole("button", { name: "Sources (2)" }));

    const sourceLink = screen.getByRole("link", { name: /Example headline/i });
    expect(sourceLink).toHaveAttribute("href", "https://example.com/a");
    expect(screen.getByText("https://example.com/a")).toBeInTheDocument();
    expect(screen.getAllByText("opaque-id-9").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Copy" })).toBeInTheDocument();
  });
});
