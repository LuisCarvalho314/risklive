//© 2025 University of Aberdeen. All rights reserved

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("fs/promises", () => ({
  default: {
    stat: vi.fn(),
    readFile: vi.fn(),
  },
  stat: vi.fn(),
  readFile: vi.fn(),
}));

describe("ops artifact inspector seca discovery", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it("discovers seca manifest batch artifacts", async () => {
    const fs = await import("fs/promises");
    const readFile = vi.mocked(fs.default.readFile);
    const stat = vi.mocked(fs.default.stat);

    stat.mockImplementation(async (filePath) => {
      const p = String(filePath);
      if (
        p.endsWith("results/web/newsmap/seca-light-30d/timeline_manifest.json") ||
        p.endsWith("results/web/newsmap/seca-light-30d/tree_batch_0000.json") ||
        p.endsWith("results/web/newsmap/seca-light-30d/tree_batch_0001.json")
      ) {
        return { mtime: new Date("2026-02-27T00:00:00.000Z"), size: 123 } as never;
      }
      const error = new Error("missing") as NodeJS.ErrnoException;
      error.code = "ENOENT";
      throw error;
    });

    readFile.mockImplementation(async (filePath) => {
      const p = String(filePath);
      if (p.endsWith("results/web/newsmap/seca-light-30d/timeline_manifest.json")) {
        return JSON.stringify({
          files: ["tree_batch_0000.json", "tree_batch_0001.json"],
        }) as never;
      }
      return "a,b\n1,2\n" as never;
    });

    const { inspectArtifacts } = await import("@/lib/ops/artifact-inspector");
    const artifacts = await inspectArtifacts();
    expect(artifacts.find((item) => item.id === "seca_manifest_30d")?.exists).toBe(true);
    expect(artifacts.find((item) => item.id === "seca_30d_batch_0")?.path).toBe(
      "results/web/newsmap/seca-light-30d/tree_batch_0000.json"
    );
    expect(artifacts.find((item) => item.id === "seca_30d_batch_1")?.exists).toBe(true);
  });

  it("discovers seca 3d manifest batch artifacts", async () => {
    const fs = await import("fs/promises");
    const readFile = vi.mocked(fs.default.readFile);
    const stat = vi.mocked(fs.default.stat);

    stat.mockImplementation(async (filePath) => {
      const p = String(filePath);
      if (
        p.endsWith("results/web/newsmap/seca-light-3d/timeline_manifest.json") ||
        p.endsWith("results/web/newsmap/seca-light-3d/tree_batch_0000.json")
      ) {
        return { mtime: new Date("2026-02-27T00:00:00.000Z"), size: 123 } as never;
      }
      const error = new Error("missing") as NodeJS.ErrnoException;
      error.code = "ENOENT";
      throw error;
    });

    readFile.mockImplementation(async (filePath) => {
      const p = String(filePath);
      if (p.endsWith("results/web/newsmap/seca-light-3d/timeline_manifest.json")) {
        return JSON.stringify({ files: ["tree_batch_0000.json"] }) as never;
      }
      return "" as never;
    });

    const { inspectArtifacts } = await import("@/lib/ops/artifact-inspector");
    const artifacts = await inspectArtifacts();
    expect(artifacts.find((item) => item.id === "seca_manifest_3d")?.exists).toBe(true);
    expect(artifacts.find((item) => item.id === "seca_3d_batch_0")?.path).toBe(
      "results/web/newsmap/seca-light-3d/tree_batch_0000.json"
    );
  });

  it("does not throw when seca manifest is malformed", async () => {
    const fs = await import("fs/promises");
    const readFile = vi.mocked(fs.default.readFile);
    const stat = vi.mocked(fs.default.stat);

    stat.mockImplementation(async (filePath) => {
      const p = String(filePath);
      if (p.endsWith("results/web/newsmap/seca-light-30d/timeline_manifest.json")) {
        return { mtime: new Date("2026-02-27T00:00:00.000Z"), size: 123 } as never;
      }
      const error = new Error("missing") as NodeJS.ErrnoException;
      error.code = "ENOENT";
      throw error;
    });
    readFile.mockImplementation(async (filePath) => {
      const p = String(filePath);
      if (p.endsWith("results/web/newsmap/seca-light-30d/timeline_manifest.json")) {
        return "{not-json" as never;
      }
      return "" as never;
    });

    const { inspectArtifacts } = await import("@/lib/ops/artifact-inspector");
    const artifacts = await inspectArtifacts();
    expect(artifacts.find((item) => item.id === "seca_manifest_30d")?.exists).toBe(true);
    expect(artifacts.some((item) => item.id.startsWith("seca_30d_batch_"))).toBe(false);
  });
});
