import { beforeEach, describe, expect, it, vi } from "vitest";
import { buildSecaV2View } from "@/lib/seca-v2";
import { loadExperimentalNewsmap } from "@/lib/newsmap-experimental";
import type { TreemapNode } from "@/lib/dashboard";

const read = vi.hoisted(() => vi.fn());
vi.mock("@/lib/bounded-file", () => ({ readBoundedText: read }));

const report = () => ({ schema_version: 1, batch: 2, next_batch: 3, retained_source_count: 3,
  root: { nodes: [
    { words: ["nuclear", "reactor"], sources: ["https://a", "https://b"], child: { nodes: [
      { words: ["energy"], sources: ["https://a"], child: null },
      { words: [], sources: ["https://b"], child: null },
    ] } },
    { words: [], sources: ["article:stable"], child: null },
  ] }, decisions: [{ path: [0], errors: { alpha: .1, beta: .2, importance: .3 }, reconstructed: true }] });
const manifest = () => ({ schema_version: 1, batch: 2, day: "2026-10-28", file: "2026-10-28-batch-2.json" });
const missing = () => Object.assign(new Error("missing"), { code: "ENOENT" });

beforeEach(() => {
  read.mockReset();
  read.mockImplementation(async (name: string) => {
    if (name.endsWith("/seca-v2/manifest.json")) return JSON.stringify(manifest());
    if (name.endsWith("2026-10-28-batch-2.json")) return JSON.stringify(report());
    throw missing();
  });
});

describe("native V2 view", () => {
  it("preserves recursive scopes, refuge, source IDs and batch-local render positions", () => {
    const out = buildSecaV2View(report(), "2026-10-28", new Map([["https://a", "Reactor story"]]));
    expect(out.mode).toBe("v2");
    expect(out.tree.name).toBe("SECA Tree");
    const node = out.tree.children![0];
    expect(node.name).toBe("nuclear reactor");
    expect(node.children).toHaveLength(2);
    expect(node.children![1].name).toBe("Unassigned");
    expect(node.meta?.sourceRefs?.[0]).toMatchObject({ id: "https://a", url: "https://a", title: "Reactor story" });
    expect(out.tree.children![1].meta?.sourceRefs?.[0]).toMatchObject({ id: "article:stable", url: null });
    expect(node.id).toBe("v2:2:0");
    expect(node.children![0].id).toBe("v2:2:0/0");
    expect(node.meta?.experimentalMetrics).toBeUndefined(); // Pre-reconstruction decisions are separate.
    const mass = (n: TreemapNode): number => n.children?.length ? n.children.reduce((s,c) => s + mass(c), 0) : n.value ?? 0;
    expect(mass(out.tree)).toBeCloseTo(3);
    expect(out.decisions).toEqual(report().decisions);
  });

  it.each(["schema", "sequence", "sourceCount", "childScope", "metric", "path"])("rejects invalid %s", field => {
    const bad = report();
    if (field === "schema") bad.schema_version = 9;
    if (field === "sequence") bad.next_batch = 9;
    if (field === "sourceCount") bad.retained_source_count = 1;
    if (field === "childScope") bad.root.nodes[0].child!.nodes[0].sources = ["https://unrelated"];
    if (field === "metric") bad.decisions[0].errors.alpha = NaN;
    if (field === "path") bad.decisions[0].path = [-1];
    expect(() => buildSecaV2View(bad, "2026-10-28")).toThrow();
  });

  it("supports an empty retained model", () => {
    const out = buildSecaV2View({ ...report(), retained_source_count: 0, root: { nodes: [] }, decisions: [] }, "2026-10-28");
    expect(out.tree.children).toEqual([]);
    expect(out.retainedSourceCount).toBe(0);
  });

  it("bounds scientific tree depth", () => {
    let root: unknown = { nodes: [] };
    for (let i = 0; i < 70; i++) root = { nodes: [{ words: ["x"], sources: ["https://a"], child: root }] };
    expect(() => buildSecaV2View({ ...report(), root, retained_source_count: 1 }, "2026-10-28")).toThrow();
  });
});

describe("V2 experimental loader", () => {
  it("prefers the native V2 report over all legacy timelines", async () => {
    const out = await loadExperimentalNewsmap();
    expect(out).toMatchObject({ mode: "v2", day: "2026-10-28", batch: 2, retainedSourceCount: 3 });
    expect(read.mock.calls.some(([name]) => String(name).includes("seca-light"))).toBe(false);
  });

  it("loads native retained-but-unmapped evidence without falling back or fabricating nodes", async () => {
    read.mockImplementation(async (name: string) => {
      if (name.endsWith("manifest.json")) return JSON.stringify(manifest());
      if (name.endsWith("batch-2.json")) return JSON.stringify({ ...report(), retained_source_count: 4 });
      throw missing();
    });
    const out = await loadExperimentalNewsmap();
    expect(out.mode).toBe("v2");
    if (out.mode !== "v2") throw new Error("Expected V2");
    expect(out.retainedSourceCount).toBe(4);
    expect(out.tree.children).toHaveLength(2);
    expect(out.tree.value).toBe(1);
  });

  it("reloads a fresh report on the next request", async () => {
    const first = await loadExperimentalNewsmap();
    const reads = read.mock.calls.length;
    expect(await loadExperimentalNewsmap()).toEqual(first);
    expect(read.mock.calls.length).toBe(reads * 2);
  });

  it.each(["traversal", "date", "mismatch", "malformed", "oversized", "permission"])("fails visibly without displaying stale V1 data on %s", async field => {
    read.mockImplementation(async (name: string) => {
      if (name.endsWith("/seca-v2/manifest.json")) {
        if (field === "oversized") throw new Error("safe size limit");
        if (field === "permission") throw Object.assign(new Error("denied"), { code: "EACCES" });
        if (field === "traversal") return JSON.stringify({ ...manifest(), file: "../../state.json" });
        if (field === "date") return JSON.stringify({ ...manifest(), day: "2026-02-30" });
        return JSON.stringify(manifest());
      }
      if (field === "malformed") return "not JSON";
      if (field === "mismatch") return JSON.stringify({ ...report(), batch: 3, next_batch: 4 });
      throw missing();
    });
    const out = await loadExperimentalNewsmap();
    expect(out.mode).toBe("fallback");
    if (out.mode === "fallback") expect(out.reason).toContain("V2");
    expect(read.mock.calls.some(([name]) => String(name).includes("seca-light"))).toBe(false);
  });
});
