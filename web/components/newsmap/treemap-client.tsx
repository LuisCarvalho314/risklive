"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";

import { TreemapNode } from "@/lib/dashboard";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

type Meta = {
  title?: string;
  url?: string | null;
  category?: string;
  alertFlag?: string; // "Red" | "Yellow" | ...
  alertReason?: string;
  timestamp?: string | null;
  shortSummary?: string;
  description?: string;
  topic?: string;
  topicLabel?: string;
};

type FlagFilter = "All" | "Red" | "Yellow";

const mutedPalette = [
  "#d47a5a",
  "#c58a5a",
  "#b8894a",
  "#8ea65a",
  "#6ea87a",
  "#5aa28f",
  "#5a8ab0",
  "#6f7ac6",
  "#8b6cc7",
  "#b06aa8",
  "#c76878",
  "#b07c5f",
];

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const clean = hex.replace("#", "");
  const num = parseInt(clean, 16);
  return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
}

function mixWithWhite(hex: string, amount: number): string {
  const { r, g, b } = hexToRgb(hex);
  const mix = (channel: number) => Math.round(channel + (255 - channel) * amount);
  return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`;
}

function slugify(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function djb2Hash(input: string): string {
  let hash = 5381;
  for (let index = 0; index < input.length; index += 1) {
    hash = (hash * 33) ^ input.charCodeAt(index);
  }
  return (hash >>> 0).toString(16);
}

function formatTimestamp(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(date);
}

function isGroupNode(node: TreemapNode): boolean {
  return Array.isArray(node.children) && node.children.length > 0;
}

/**
 * Font sizing helpers (auto-fit label to treemap tile).
 * NOTE: Do NOT return fontSize: 0 in labelLayout with treemap animations enabled.
 * That can trigger ECharts treemap animation bugs (null graphic elements during diff).
 */
function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function estimateFontSizeToFitSingleLine(params: {
  text: string;
  rectWidth: number;
  rectHeight: number;
  paddingX?: number;
  paddingY?: number;
  minFontSize?: number;
  maxFontSize?: number;
}): number {
  const {
    text,
    rectWidth,
    rectHeight,
    paddingX = 8,
    paddingY = 6,
    minFontSize = 8,
    maxFontSize = 28,
  } = params;

  const safeWidth = Math.max(0, rectWidth - paddingX * 2);
  const safeHeight = Math.max(0, rectHeight - paddingY * 2);

  if (!text || safeWidth <= 2 || safeHeight <= 2) return minFontSize;

  // Approx average glyph width for Latin sans fonts.
  const avgGlyphWidthFactor = 0.58;

  const byWidth = safeWidth / (Math.max(1, text.length) * avgGlyphWidthFactor);
  const byHeight = safeHeight * 0.72;

  const raw = Math.min(byWidth, byHeight);
  return clamp(Math.floor(raw), minFontSize, maxFontSize);
}

/**
 * Collect leaf nodes from an arbitrary incoming tree.
 */
function collectLeaves(root: TreemapNode): TreemapNode[] {
  const leaves: TreemapNode[] = [];

  const stack: TreemapNode[] = [root];
  while (stack.length) {
    const node = stack.pop()!;
    const children = node.children ?? [];
    if (!children.length) {
      leaves.push(node);
      continue;
    }
    for (const child of children) stack.push(child);
  }
  return leaves;
}

/**
 * Normalize to Category → Topic → Leaf, and assign stable IDs and deterministic colors.
 */
function normalizeToNewsmapTree(input: TreemapNode): TreemapNode {
  const leaves = collectLeaves(input);

  type LeafRecord = { leaf: TreemapNode; meta: Meta };
  const records: LeafRecord[] = leaves.map((leaf) => ({
    leaf,
    meta: (leaf.meta ?? {}) as Meta,
  }));

  const categoryNameFor = (rec: LeafRecord) =>
    (rec.meta.category?.trim() || rec.leaf.name?.trim() || "Uncategorized").trim();

  const topicNameFor = (rec: LeafRecord) =>
    (rec.meta.topicLabel?.trim() || rec.meta.topic?.trim() || "Unknown Topic").trim();

  const categoryNames = Array.from(new Set(records.map(categoryNameFor))).sort((a, b) =>
    a.localeCompare(b)
  );
  const categoryIndexByName = new Map<string, number>(categoryNames.map((name, index) => [name, index]));

  const baseColorForCategory = (categoryName: string) => {
    const index = categoryIndexByName.get(categoryName) ?? 0;
    return mutedPalette[index % mutedPalette.length];
  };

  const byCategory = new Map<string, Map<string, LeafRecord[]>>();
  for (const rec of records) {
    const category = categoryNameFor(rec);
    const topic = topicNameFor(rec);

    let byTopic = byCategory.get(category);
    if (!byTopic) {
      byTopic = new Map();
      byCategory.set(category, byTopic);
    }
    const bucket = byTopic.get(topic);
    if (bucket) bucket.push(rec);
    else byTopic.set(topic, [rec]);
  }

  const categoryNodes: TreemapNode[] = categoryNames.map((categoryName) => {
    const byTopic = byCategory.get(categoryName) ?? new Map<string, LeafRecord[]>();
    const topicNames = Array.from(byTopic.keys()).sort((a, b) => a.localeCompare(b));

    const baseColor = baseColorForCategory(categoryName);
    const categoryId = `cat::${slugify(categoryName)}`;

    const topicNodes: TreemapNode[] = topicNames.map((topicName) => {
      const topicId = `topic::${slugify(categoryName)}::${slugify(topicName)}`;
      const topicColor = mixWithWhite(baseColor, 0.38);

      const topicLeaves = (byTopic.get(topicName) ?? [])
        .slice()
        .sort((a, b) => {
          const at = a.meta.timestamp ?? "";
          const bt = b.meta.timestamp ?? "";
          const ad = Date.parse(at);
          const bd = Date.parse(bt);
          if (!Number.isNaN(ad) && !Number.isNaN(bd) && ad !== bd) return bd - ad;
          const an = (a.meta.title || a.leaf.name || "").toString();
          const bn = (b.meta.title || b.leaf.name || "").toString();
          return an.localeCompare(bn);
        });

      const leafNodes: TreemapNode[] = topicLeaves.map(({ leaf, meta }) => {
        const stableKey = `${meta.url ?? ""}|${meta.title ?? ""}|${leaf.name ?? ""}`;
        const leafId = `leaf::${slugify(categoryName)}::${slugify(topicName)}::${djb2Hash(stableKey)}`;

        const baseValue = Math.max(1, typeof leaf.value === "number" ? leaf.value : 1);

        return {
          name: meta.title || leaf.name || "Untitled",
          id: leafId,
          value: baseValue,
          meta: {
            ...meta,
            category: meta.category ?? categoryName,
            topicLabel: meta.topicLabel ?? meta.topic ?? topicName,
          },
          itemStyle: { color: baseColor },
        };
      });

      return {
        name: topicName,
        id: topicId,
        value: leafNodes.reduce((sum, n) => sum + (typeof n.value === "number" ? n.value : 0), 0),
        children: leafNodes,
        itemStyle: { color: topicColor },
      };
    });

    return {
      name: categoryName,
      id: categoryId,
      value: topicNodes.reduce((sum, n) => sum + (typeof n.value === "number" ? n.value : 0), 0),
      children: topicNodes,
      itemStyle: { color: mixWithWhite(baseColor, 0.22) },
    };
  });

  return {
    name: "All",
    id: "root::newsmap",
    children: categoryNodes,
    itemStyle: { color: "transparent" },
  };
}

type NodeIndex = {
  byId: Map<string, TreemapNode>;
  parentById: Map<string, string | null>;
  childrenById: Map<string, string[]>;
  leafIds: Set<string>;
};

function indexTree(root: TreemapNode): NodeIndex {
  const byId = new Map<string, TreemapNode>();
  const parentById = new Map<string, string | null>();
  const childrenById = new Map<string, string[]>();
  const leafIds = new Set<string>();

  const stack: Array<{ node: TreemapNode; parentId: string | null }> = [{ node: root, parentId: null }];

  while (stack.length) {
    const { node, parentId } = stack.pop()!;
    if (!node.id) continue;

    byId.set(node.id, node);
    parentById.set(node.id, parentId);

    const children = node.children ?? [];
    if (!children.length) {
      leafIds.add(node.id);
      childrenById.set(node.id, []);
      continue;
    }

    const childIds: string[] = [];
    for (const child of children) {
      if (child.id) childIds.push(child.id);
      stack.push({ node: child, parentId: node.id });
    }
    childrenById.set(node.id, childIds);
  }

  return { byId, parentById, childrenById, leafIds };
}

function ancestorsOf(nodeId: string, parentById: Map<string, string | null>): string[] {
  const path: string[] = [];
  let current: string | null | undefined = nodeId;
  while (current) {
    path.push(current);
    current = parentById.get(current) ?? null;
  }
  return path.reverse();
}

function descendantsOf(nodeId: string, childrenById: Map<string, string[]>): Set<string> {
  const out = new Set<string>();
  const stack = [nodeId];
  while (stack.length) {
    const current = stack.pop()!;
    out.add(current);
    const kids = childrenById.get(current) ?? [];
    for (const k of kids) stack.push(k);
  }
  return out;
}

function unionInto(target: Set<string>, items: Iterable<string>) {
  for (const item of items) target.add(item);
}

function buildReweightedTree(params: {
  root: TreemapNode;
  index: NodeIndex;
  keepIds: Set<string>;
  epsilon: number;
}): TreemapNode {
  const { root, keepIds, epsilon } = params;

  const clone = (node: TreemapNode): TreemapNode => {
    const children = node.children ?? [];
    const hasChildren = children.length > 0;

    if (!node.id) return { ...node };

    const keep = keepIds.has(node.id);
    const weight = keep ? 1 : epsilon;

    if (!hasChildren) {
      const baseValue = Math.max(1, typeof node.value === "number" ? node.value : 1);
      return {
        ...node,
        value: baseValue * weight,
      };
    }

    const clonedChildren = children.map(clone);
    const summedValue = clonedChildren.reduce(
      (sum, c) => sum + (typeof c.value === "number" ? c.value : 0),
      0
    );

    return {
      ...node,
      children: clonedChildren,
      value: summedValue,
    };
  };

  return clone(root);
}

function tooltipHtml(node: TreemapNode): string {
  const meta = (node.meta ?? {}) as Meta;
  const title = meta.title || node.name || "";
  const category = meta.category || "";
  const topic = meta.topicLabel || meta.topic || "";
  const flag = meta.alertFlag || "";
  const time = formatTimestamp(meta.timestamp);
  const summary = meta.shortSummary || meta.description || "";

  const esc = (v: string) =>
    v
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");

  return `
    <div style="max-width:320px; white-space:normal; word-break:break-word;">
      <div style="font-weight:700; margin-bottom:6px;">${esc(title)}</div>
      <div style="opacity:0.9">${esc(category)}</div>
      <div style="opacity:0.9">${esc(topic)}</div>
      ${
        flag
          ? `<div style="margin-top:6px;"><strong>${esc(flag)}</strong>${
              meta.alertReason ? ` — ${esc(meta.alertReason)}` : ""
            }</div>`
          : ""
      }
      ${time ? `<div style="opacity:0.8; margin-top:4px;">${esc(time)}</div>` : ""}
      ${summary ? `<div style="margin-top:8px; opacity:0.95">${esc(summary)}</div>` : ""}
    </div>
  `;
}

export function TreemapClient({ data }: { data: TreemapNode }) {
  const chartRef = useRef<any>(null);

  const [flagFilter, setFlagFilter] = useState<FlagFilter>("All");
  const [focusId, setFocusId] = useState<string>("root::newsmap");

  const normalizedRoot = useMemo(() => normalizeToNewsmapTree(data), [data]);
  const treeIndex = useMemo(() => indexTree(normalizedRoot), [normalizedRoot]);

  const focusPath = useMemo(() => {
    if (!treeIndex.byId.has(focusId)) return ancestorsOf("root::newsmap", treeIndex.parentById);
    return ancestorsOf(focusId, treeIndex.parentById);
  }, [focusId, treeIndex]);

  const keepIds = useMemo(() => {
    const keep = new Set<string>();

    const rootId = "root::newsmap";
    const validFocusId = treeIndex.byId.has(focusId) ? focusId : rootId;

    const focusDesc = descendantsOf(validFocusId, treeIndex.childrenById);
    unionInto(keep, focusDesc);
    unionInto(keep, ancestorsOf(validFocusId, treeIndex.parentById));

    if (flagFilter !== "All") {
      const flaggedLeaves = new Set<string>();

      for (const leafId of treeIndex.leafIds) {
        const leaf = treeIndex.byId.get(leafId);
        const meta = (leaf?.meta ?? {}) as Meta;
        if (meta.alertFlag === flagFilter) flaggedLeaves.add(leafId);
      }

      const filterKeep = new Set<string>();
      for (const leafId of flaggedLeaves) {
        unionInto(filterKeep, ancestorsOf(leafId, treeIndex.parentById));
        filterKeep.add(leafId);
      }

      const finalKeep = new Set<string>();
      finalKeep.add(rootId);

      for (const id of keep) {
        if (filterKeep.has(id)) finalKeep.add(id);
      }

      const toAddAncestors: string[] = [];
      for (const id of finalKeep) {
        for (const a of ancestorsOf(id, treeIndex.parentById)) toAddAncestors.push(a);
      }
      unionInto(finalKeep, toAddAncestors);

      return finalKeep;
    }

    keep.add(rootId);
    return keep;
  }, [flagFilter, focusId, treeIndex]);

  const displayTree = useMemo(() => {
    const epsilon = 1e-6;
    return buildReweightedTree({
      root: normalizedRoot,
      index: treeIndex,
      keepIds,
      epsilon,
    });
  }, [normalizedRoot, treeIndex, keepIds]);

  const option = useMemo(() => {
    return {
      tooltip: {
        confine: true,
        className: "treemap-tooltip",
        extraCssText: "max-width:340px; white-space:normal; word-break:break-word;",
        formatter: (params: { data?: TreemapNode }) => {
          const node = params.data;
          if (!node) return "";
          if (isGroupNode(node)) return `<div style="font-weight:700;">${node.name}</div>`;
          return tooltipHtml(node);
        },
      },
      series: [
        {
          name: "newsmap",
          type: "treemap",
          data: [displayTree],

          top: 0,
          left: 0,
          right: 0,
          bottom: 0,

          roam: false,
          nodeClick: false,
          breadcrumb: { show: false },

          visibleMin: 0.9,
          childrenVisibleMin: 0.9,

          animation: true,
          animationDuration: 600,
          animationEasing: "cubicOut",
          animationDurationUpdate: 2400,
          animationEasingUpdate: "cubicInOut",
          animationDelayUpdate: (index: number) => Math.min(index * 2, 250),

          universalTransition: {
            enabled: true,
            seriesKey: "newsmap",
          },

          label: {
            show: true,
            overflow: "truncate",
            color: "#ffffff",
          },
          upperLabel: {
            show: true,
            height: 26,
            color: "#ffffff",
          },

          // Auto-fit font sizes based on tile rect.
          // IMPORTANT: avoid returning fontSize: 0 with treemap animations (can crash ECharts).
          labelLayout: (layoutParams: any) => {
            const rect = layoutParams?.rect;
            const node: TreemapNode | undefined = layoutParams?.data;
            if (!rect || !node) return;

            const text = (layoutParams?.text ?? node.name ?? "").toString();

            // Let ECharts handle hiding via overlap rules; do not force fontSize=0.
            // For very small tiles, just ask ECharts to hide overlaps.
            if (rect.width < 18 || rect.height < 14) {
              return { hideOverlap: true };
            }

            const isLeaf = !isGroupNode(node);

            const fontSize = estimateFontSizeToFitSingleLine({
              text,
              rectWidth: rect.width,
              rectHeight: rect.height,
              paddingX: 6,
              paddingY: 4,
              minFontSize: isLeaf ? 8 : 9,
              maxFontSize: isLeaf ? 22 : 26,
            });

            return {
              fontSize,
              hideOverlap: true,
            };
          },

          itemStyle: {
            borderColor: "transparent",
            borderWidth: 0,
            gapWidth: 0,
          },

          levels: [
            {
              itemStyle: { gapWidth: 2 },
              label: { show: false },
              upperLabel: { show: false },
            },
            {
              itemStyle: { gapWidth: 8 },
              label: { show: false },
              upperLabel: { show: true, color: "#ffffff" },
            },
            {
              itemStyle: { gapWidth: 5 },
              label: { show: true, color: "#ffffff" },
              upperLabel: { show: true },
            },
            {
              itemStyle: { gapWidth: 2 },
              label: { show: true, color: "#ffffff" },
              upperLabel: { show: true },
            },
          ],
        },
      ],
    };
  }, [displayTree]);

  const onEvents = useMemo(() => {
    return {
      click: (params: any) => {
        const node: TreemapNode | undefined = params?.data;
        if (!node?.id) return;

        if (isGroupNode(node)) {
          setFocusId(node.id);
          return;
        }

        const meta = (node.meta ?? {}) as Meta;
        if (meta.url) window.open(meta.url, "_blank", "noreferrer");
      },
    };
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      chartRef.current?.getEchartsInstance?.().resize?.();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [flagFilter, focusId]);

  const buttonClass = (active: boolean) =>
    [
      "rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-wide transition-colors",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
      active
        ? "bg-accent text-foreground"
        : "bg-muted/60 text-muted-foreground hover:bg-accent/40 hover:text-foreground",
    ].join(" ");

  const breadcrumbNodes = useMemo(() => {
    const ids = focusPath.length ? focusPath : ["root::newsmap"];
    return ids.map((id) => treeIndex.byId.get(id)).filter(Boolean) as TreemapNode[];
  }, [focusPath, treeIndex]);

  return (
    <div className="relative h-full w-full overflow-hidden">
      <div className="pointer-events-none absolute left-4 right-4 top-3 z-10 flex items-center gap-3">
        <div className="pointer-events-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => setFlagFilter("All")}
            className={buttonClass(flagFilter === "All")}
          >
            All
          </button>
          <button
            type="button"
            onClick={() => setFlagFilter("Red")}
            className={buttonClass(flagFilter === "Red")}
          >
            Red
          </button>
          <button
            type="button"
            onClick={() => setFlagFilter("Yellow")}
            className={buttonClass(flagFilter === "Yellow")}
          >
            Yellow
          </button>
        </div>

        <div className="ml-auto pointer-events-auto flex items-center gap-2 overflow-x-auto">
          <button
            type="button"
            onClick={() => setFocusId("root::newsmap")}
            className={[
              "whitespace-nowrap rounded-full px-3 py-1 text-[11px] font-semibold transition-colors",
              focusId === "root::newsmap"
                ? "bg-accent text-foreground"
                : "bg-muted/60 text-muted-foreground hover:bg-accent/40 hover:text-foreground",
            ].join(" ")}
            title="Reset focus"
          >
            Reset
          </button>

          {breadcrumbNodes.map((node) => {
            const isLast = node.id === focusId;
            const label = node.name || "All";
            return (
              <button
                key={node.id}
                type="button"
                onClick={() => setFocusId(node.id ?? "root::newsmap")}
                disabled={isLast}
                className={[
                  "whitespace-nowrap rounded-full px-3 py-1 text-[11px] font-semibold transition-colors",
                  isLast
                    ? "bg-accent text-foreground"
                    : "bg-muted/60 text-muted-foreground hover:bg-accent/40 hover:text-foreground",
                ].join(" ")}
                title={label}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="absolute inset-0">
        <ReactECharts
          ref={chartRef}
          option={option}
          onEvents={onEvents}
          style={{ width: "100%", height: "100%" }}
          // Helps avoid treemap diff/animation edge-cases when labelLayout changes per update:
          notMerge={true}
          lazyUpdate={true}
        />
      </div>
    </div>
  );
}
