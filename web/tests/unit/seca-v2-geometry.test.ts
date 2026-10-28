import { expect, it } from "vitest";
import { buildSecaV2View } from "@/lib/seca-v2";
import { computeLayout } from "@/lib/treemap/layout";
import { buildWeightedTree } from "@/lib/treemap/focus";
import { defaultTuning, type TileAlgorithm } from "@/lib/treemap/config";
import type { TreemapNode } from "@/lib/dashboard";

const node = (sources: string[], children?: ReturnType<typeof leaf>[]) => ({
  words: ["topic"], sources, child: children ? { nodes: children } : null,
});
const leaf = (sources: string[]) => ({ words: ["child"], sources, child: null });
const report = (nodes: ReturnType<typeof node>[], count: number) => ({
  schema_version: 1, batch: 2, next_batch: 3, retained_source_count: count,
  root: { nodes }, decisions: [],
});
const tuning = { ...defaultTuning, useLayoutLabelBand: false,
  groupBorderByDepth: { root: 0, category: 0, topic: 0, leaf: 0 },
  groupBorderInnerByDepth: { root: 0, category: 0, topic: 0, leaf: 0 } };
const algorithms: TileAlgorithm[] = ["binary", "squarify", "resquarify", "slice", "dice", "sliceDice"];
const layout = (tree: TreemapNode, algorithm: TileAlgorithm) => computeLayout(
  buildWeightedTree(tree, new Set(), tuning), 1000, 1000,
  { ...tuning, tileAlgorithmRoot: algorithm, tileAlgorithmCategory: algorithm,
    tileAlgorithmTopic: algorithm, tileAlgorithmLeaf: algorithm });
const area = (map: ReturnType<typeof layout>, id: string) => {
  const r = map.byId.get(id)!;
  expect([r.x0, r.y0, r.x1, r.y1].every(Number.isFinite)).toBe(true);
  return (r.x1 - r.x0) * (r.y1 - r.y0);
};

it.each(algorithms)("%s leaves genuinely unallocated child and root area", algorithm => {
  const tree = buildSecaV2View(report([node(["a", "b"], [leaf(["a"])])], 4), "2026-10-28").tree;
  const map = layout(tree, algorithm);
  expect(area(map, "v2:2:0")).toBeCloseTo(500000, 5);
  expect(area(map, "v2:2:0/0")).toBeCloseTo(250000, 5);
  expect(map.nodes).toHaveLength(3); // No synthetic remainder nodes.
  expect(map.byId.get("root::newsmap")!.value).toBe(4);
  const parent = map.byId.get("v2:2:0")!, child = map.byId.get("v2:2:0/0")!;
  expect(child.x1).toBeLessThan(parent.x1);
  expect(child.y1).toBeLessThanOrEqual(parent.y1);
});

it.each(algorithms)("%s splits overlapping source mass and carries fractions into children", algorithm => {
  const tree = buildSecaV2View(report([
    node(["a", "b"], [leaf(["a", "b"]), leaf(["b"])]), node(["b"]),
  ], 2), "2026-10-28").tree;
  const map = layout(tree, algorithm);
  expect(area(map, "v2:2:0")).toBeCloseTo(750000, 5); // a + half b
  expect(area(map, "v2:2:1")).toBeCloseTo(250000, 5);
  expect(area(map, "v2:2:0/0")).toBeCloseTo(625000, 5); // a + quarter b
  expect(area(map, "v2:2:0/1")).toBeCloseTo(125000, 5);
  expect(tree.children![0].meta!.sourceRefs!.map(s => s.id)).toEqual(["a", "b"]);
  expect(tree.children![0].meta!.sourceCount).toBe(2);
});

it("accepts entirely unmapped evidence and preserves zero-mass native topology", () => {
  const tree = buildSecaV2View(report([node([], [leaf([])])], 2), "2026-10-28").tree;
  expect(tree.children![0].children).toHaveLength(1);
  for (const algorithm of algorithms) {
    const map = layout(tree, algorithm);
    expect(area(map, "v2:2:0")).toBe(0);
    expect(area(map, "v2:2:0/0")).toBe(0);
  }
});

it("retains the existing fill behaviour for unmarked main and legacy trees", () => {
  const tree = { id: "parent", name: "parent", value: 2,
    children: [{ id: "child", name: "child", value: 1 }],
    meta: { experimentalLayoutWeights: true } };
  const map = computeLayout(tree, 1000, 1000, { ...tuning,
    tileAlgorithmRoot: "binary" });
  expect(area(map, "child")).toBe(1000000);
  expect(map.byId.get("parent")!.value).toBe(1);
  const main = computeLayout({ ...tree, meta: {} }, 1000, 1000,
    { ...tuning, tileAlgorithmRoot: "binary" });
  expect(area(main, "child")).toBe(1000000);
  expect(main.byId.get("parent")!.value).toBe(3);
});

it("handles a large native report without inventing or truncating source identities", () => {
  const sources = Array.from({ length: 50000 }, (_, i) => `https://source/${i}`);
  const out = buildSecaV2View(report([node(sources)], sources.length + 1), "2026-10-28");
  expect(out.tree.children![0].meta!.sourceRefs).toHaveLength(sources.length);
  expect(area(layout(out.tree, "binary"), "v2:2:0")).toBeCloseTo(1000000 * 50000 / 50001, 5);
});

it("keeps uncovered child area with the actual default borders and label bands", () => {
  const tree = buildSecaV2View(report([node(["a", "b"], [leaf(["a"])])], 2), "2026-10-28").tree;
  const map = computeLayout(tree, 1440, 800, defaultTuning);
  const parent = map.byId.get("v2:2:0")!, child = map.byId.get("v2:2:0/0")!;
  expect(child.x1).toBeLessThan(parent.x0 + (parent.x1 - parent.x0) * .6);
  expect(area(map, "v2:2:0/0")).toBeLessThan(area(map, "v2:2:0") * .6);
  expect(child.x0).toBeGreaterThanOrEqual(parent.x0);
  expect(child.y0).toBeGreaterThanOrEqual(parent.y0);
});
