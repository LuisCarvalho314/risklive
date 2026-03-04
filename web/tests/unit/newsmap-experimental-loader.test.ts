import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildDailyBatches,
  buildTreemapFromRows,
  clampBatchIndex,
  loadExperimentalNewsmap,
  parseNewsDataCsv,
} from "@/lib/newsmap-experimental";
import { applyExperimentalSizeMetric } from "@/lib/newsmap-experimental-shared";

vi.mock("fs/promises", () => ({
  readFile: vi.fn(),
  default: {
    readFile: vi.fn(),
  },
}));

describe("newsmap experimental loader", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("parses required news_data.csv columns", () => {
    const rows = parseNewsDataCsv(
      [
        "Title,URL,Description,Timestamp,Query,Source_Price",
        "\"A title\",https://example.com,\"desc\",2026-02-27T00:00:00Z,Business,0.0015",
      ].join("\n")
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].query).toBe("Business");
    expect(rows[0].sourcePrice).toBe(0.0015);
  });

  it("rejects invalid csv headers", () => {
    expect(() => parseNewsDataCsv("Title,Timestamp\nx,2026-02-27")).toThrowError(
      "missing required columns"
    );
  });

  it("groups rows by day into ordered batches", () => {
    const batches = buildDailyBatches([
      {
        title: "Older",
        timestamp: "2026-02-26T10:00:00Z",
        query: "Politics",
      },
      {
        title: "Newer",
        timestamp: "2026-02-27T10:00:00Z",
        query: "Business",
      },
    ]);
    expect(batches).toHaveLength(2);
    expect(batches[0].day).toBe("2026-02-26");
    expect(batches[1].day).toBe("2026-02-27");
  });

  it("builds explicit HKT-like hierarchy with category, topic, and leaf ids", () => {
    const tree = buildTreemapFromRows(
      [
        {
          title: "Central bank risk policy changes",
          timestamp: "2026-02-27T10:00:00Z",
          query: "Politics",
          description: "central bank risk policy changes announced",
        },
      ],
      "2026-02-27"
    );
    const category = tree.children?.[0];
    const topic = category?.children?.[0];
    const leaf = topic?.children?.[0];
    expect(category?.id?.startsWith("cat::")).toBe(true);
    expect(topic?.id?.startsWith("topic::")).toBe(true);
    expect(leaf?.id?.startsWith("leaf::")).toBe(true);
  });

  it("clamps timeline batch index", () => {
    expect(clampBatchIndex(-10, 5)).toBe(0);
    expect(clampBatchIndex(99, 5)).toBe(4);
    expect(clampBatchIndex(1.9, 5)).toBe(1);
  });

  it("falls back when source csv files are missing", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.default.readFile).mockRejectedValue(
      Object.assign(new Error("missing"), { code: "ENOENT" })
    );
    const out = await loadExperimentalNewsmap();
    expect(out.mode).toBe("fallback");
  });

  it("prefers 30-day SECA timeline files when available", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.default.readFile).mockImplementation(async (filePathLike) => {
      const filePath = String(filePathLike);
      if (filePath.includes("seca-light-7d") || filePath.includes("seca-light-3d")) {
        throw Object.assign(new Error(`missing ${filePath}`), { code: "ENOENT" });
      }
      if (filePath.endsWith("manifest.json")) {
        return JSON.stringify({
          total_batches: 1,
          files: ["tree_batch_0000.json"],
        });
      }
      if (filePath.endsWith("tree_batch_0000.json")) {
        return JSON.stringify({
          hkts: [
            {
              hkt_id: 1,
              parent_node_id: 0,
              expected_words: [{ word_id: 11, token: "energy" }],
              all_node_words_union: [{ word_id: 11, token: "energy" }],
              node_ids: [101],
            },
          ],
          nodes: [
            {
              node_id: 101,
              hkt_id: 1,
              words: [{ word_id: 11, token: "energy" }],
              top_words: [{ word_id: 11, token: "energy" }],
              sources: [{ internal_source_id: 1, external_source_id: "https://example.com/source/1" }],
              is_refuge_node: false,
            },
          ],
          word_legend: [],
          source_legend: [{ internal_source_id: 1, external_source_id: "https://example.com/source/1" }],
        });
      }
      throw Object.assign(new Error(`missing ${filePath}`), { code: "ENOENT" });
    });

    const out = await loadExperimentalNewsmap();
    expect(out.mode).toBe("timeline");
    if (out.mode !== "timeline") return;
    expect(out.selectedKey).toBe("30d");
    expect(out.timelines["30d"]?.totalBatches).toBe(1);
    expect(out.timelines["7d"]).toBeUndefined();
    expect(out.timelines["3d"]).toBeUndefined();
    expect(out.timelines["30d"]?.batches[0].filename).toBe("tree_batch_0000.json");
    const firstNode = out.timelines["30d"]?.batches[0].tree.children?.[0];
    expect(firstNode?.id).toBe("node::101");
    expect(firstNode?.children?.length ?? 0).toBe(0);
    expect(firstNode?.meta?.sourceRefs?.[0]).toEqual({
      id: "https://example.com/source/1",
      url: "https://example.com/source/1",
      isUrl: true,
    });
  });

  it("renders refuge nodes with <> label in SECA hierarchy", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.default.readFile).mockImplementation(async (filePathLike) => {
      const filePath = String(filePathLike);
      if (filePath.endsWith("manifest.json")) {
        return JSON.stringify({
          total_batches: 1,
          files: ["tree_batch_0000.json"],
        });
      }
      if (filePath.endsWith("tree_batch_0000.json")) {
        return JSON.stringify({
          hkts: [
            {
              hkt_id: 1,
              parent_node_id: 0,
              expected_words: [],
              all_node_words_union: [],
              node_ids: [201],
            },
          ],
          nodes: [
            {
              node_id: 201,
              hkt_id: 1,
              words: [],
              top_words: [],
              sources: [],
              is_refuge_node: true,
            },
          ],
        });
      }
      throw Object.assign(new Error(`missing ${filePath}`), { code: "ENOENT" });
    });

    const out = await loadExperimentalNewsmap();
    expect(out.mode).toBe("timeline");
    if (out.mode !== "timeline") return;
    expect(out.timelines["30d"]?.batches[0].tree.children?.[0]?.name).toBe("<>");
  });

  it("loads 30-day, 7-day, and 3-day SECA timelines when available", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.default.readFile).mockImplementation(async (filePathLike) => {
      const filePath = String(filePathLike);
      if (filePath.endsWith("manifest.json")) {
        return JSON.stringify({
          total_batches: 1,
          files: ["tree_batch_0000.json"],
        });
      }
      if (filePath.endsWith("tree_batch_0000.json")) {
        return JSON.stringify({
          hkts: [{ hkt_id: 1, parent_node_id: 0, expected_words: [], all_node_words_union: [], node_ids: [11] }],
          nodes: [{ node_id: 11, hkt_id: 1, words: [], top_words: [], sources: [], is_refuge_node: false }],
        });
      }
      throw Object.assign(new Error(`missing ${filePath}`), { code: "ENOENT" });
    });

    const out = await loadExperimentalNewsmap();
    expect(out.mode).toBe("timeline");
    if (out.mode !== "timeline") return;
    expect(out.selectedKey).toBe("30d");
    expect(out.timelines["30d"]?.totalBatches).toBe(1);
    expect(out.timelines["7d"]?.totalBatches).toBe(1);
    expect(out.timelines["3d"]?.totalBatches).toBe(1);
  });

  it("marks non-url external source ids as non-clickable source refs", async () => {
    const fs = await import("fs/promises");
    vi.mocked(fs.default.readFile).mockImplementation(async (filePathLike) => {
      const filePath = String(filePathLike);
      if (filePath.includes("seca-light-7d") || filePath.includes("seca-light-3d")) {
        throw Object.assign(new Error(`missing ${filePath}`), { code: "ENOENT" });
      }
      if (filePath.endsWith("manifest.json")) {
        return JSON.stringify({
          total_batches: 1,
          files: ["tree_batch_0000.json"],
        });
      }
      if (filePath.endsWith("tree_batch_0000.json")) {
        return JSON.stringify({
          hkts: [{ hkt_id: 1, parent_node_id: 0, expected_words: [], all_node_words_union: [], node_ids: [9] }],
          nodes: [
            {
              node_id: 9,
              hkt_id: 1,
              words: [],
              top_words: [],
              sources: [{ internal_source_id: 1, external_source_id: "doc-12345" }],
              is_refuge_node: false,
            },
          ],
        });
      }
      throw Object.assign(new Error(`missing ${filePath}`), { code: "ENOENT" });
    });

    const out = await loadExperimentalNewsmap();
    expect(out.mode).toBe("timeline");
    if (out.mode !== "timeline") return;
    const node = out.timelines["30d"]?.batches[0].tree.children?.[0];
    expect(node?.meta?.sourceRefs?.[0]).toEqual({
      id: "doc-12345",
      url: null,
      isUrl: false,
    });
  });

  it("applies selected experimental metric to node values", () => {
    const root = {
      id: "root::newsmap",
      name: "SECA Tree",
      children: [
        {
          id: "node::1",
          name: "Node",
          value: 10,
          meta: {
            experimentalMetrics: {
              composite: 10,
              mappedSourceCount: 4,
              wordImportanceError: 7,
            },
          },
        },
      ],
    };
    const mappedTree = applyExperimentalSizeMetric(root, "mappedSourceCount");
    const wiTree = applyExperimentalSizeMetric(root, "wordImportanceError");
    expect(mappedTree.children?.[0]?.value).toBe(4);
    expect(wiTree.children?.[0]?.value).toBe(7);
  });

  it("re-sorts siblings when experimental metric changes", () => {
    const root = {
      id: "root::newsmap",
      name: "SECA Tree",
      children: [
        {
          id: "node::a",
          name: "A",
          meta: {
            experimentalMetrics: {
              mappedSourceCount: 20,
              combinedError: 2,
            },
          },
        },
        {
          id: "node::b",
          name: "B",
          meta: {
            experimentalMetrics: {
              mappedSourceCount: 10,
              combinedError: 9,
            },
          },
        },
      ],
    };

    const byMapped = applyExperimentalSizeMetric(root, "mappedSourceCount");
    const byError = applyExperimentalSizeMetric(root, "combinedError");

    expect(byMapped.children?.map((node) => node.id)).toEqual(["node::a", "node::b"]);
    expect(byError.children?.map((node) => node.id)).toEqual(["node::b", "node::a"]);
  });

  it("inverts metric sizing when direction is high-to-small", () => {
    const root = {
      id: "root::newsmap",
      name: "SECA Tree",
      children: [
        {
          id: "node::a",
          name: "A",
          meta: { experimentalMetrics: { mappedSourceCount: 20 } },
        },
        {
          id: "node::b",
          name: "B",
          meta: { experimentalMetrics: { mappedSourceCount: 10 } },
        },
      ],
    };
    const highToLarge = applyExperimentalSizeMetric(root, "mappedSourceCount", "highToLarge");
    const highToSmall = applyExperimentalSizeMetric(root, "mappedSourceCount", "highToSmall");

    expect(highToLarge.children?.map((node) => node.id)).toEqual(["node::a", "node::b"]);
    expect(highToSmall.children?.map((node) => node.id)).toEqual(["node::b", "node::a"]);
  });
});
