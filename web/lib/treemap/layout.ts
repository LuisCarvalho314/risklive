import { easeCubicInOut } from "d3";
import {
  hierarchy,
  treemap,
  treemapBinary,
  treemapDice,
  treemapResquarify,
  treemapSlice,
  treemapSliceDice,
  treemapSquarify,
} from "d3-hierarchy";
import { useEffect, useMemo, useRef, useState } from "react";

import { TreemapNode } from "@/lib/dashboard";
import { TileAlgorithm, TreemapTuning } from "@/lib/treemap/config";

export type LayoutRect = {
  id: string;
  depth: number;
  data: TreemapNode;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  value: number;
  parentId: string | null;
};

export type LayoutMap = {
  byId: Map<string, LayoutRect>;
  nodes: LayoutRect[];
};

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function depthKeyFor(depth: number): "root" | "category" | "topic" | "leaf" {
  if (depth <= 0) return "root";
  if (depth === 1) return "category";
  if (depth === 2) return "topic";
  return "leaf";
}

export function computeLayout(
  root: TreemapNode,
  width: number,
  height: number,
  tuning: TreemapTuning
): LayoutMap {
  const baseRatio =
    tuning.squarifyRatioMode === "screen"
      ? Math.max(width / Math.max(1, height), height / Math.max(1, width))
      : tuning.squarifyRatio;
  const squarifyRatio = Math.max(1.01, baseRatio * tuning.squarifyRatioScale);

  const tileFromName = (name: TileAlgorithm) => {
    switch (name) {
      case "binary":
        return treemapBinary;
      case "slice":
        return treemapSlice;
      case "dice":
        return treemapDice;
      case "sliceDice":
        return treemapSliceDice;
      case "resquarify":
        return treemapResquarify.ratio(squarifyRatio);
      default:
        return treemapSquarify.ratio(squarifyRatio);
    }
  };

  const tile = (node: any, x0: number, y0: number, x1: number, y1: number) => {
    const algo = (() => {
      if (node.depth <= 0) return tileFromName(tuning.tileAlgorithmRoot);
      if (node.depth === 1) return tileFromName(tuning.tileAlgorithmCategory);
      if (node.depth === 2) return tileFromName(tuning.tileAlgorithmTopic);
      return tileFromName(tuning.tileAlgorithmLeaf);
    })();
    algo(node, x0, y0, x1, y1);
  };

  const layout = treemap<TreemapNode>()
    .tile(tile)
    .size([width, height])
    .round(false)
    .paddingInner((node: any) => {
      const key = depthKeyFor(node.depth);
      return tuning.groupBorderInnerByDepth[key] ?? (node.depth >= 1 ? tuning.groupBorderInner : 0);
    })
    .paddingOuter((node: any) => {
      const key = depthKeyFor(node.depth);
      return tuning.groupBorderByDepth[key] ?? (node.depth >= 1 ? tuning.groupBorder : 0);
    })
    .paddingTop((node: any) =>
      tuning.useLayoutLabelBand &&
      node.depth >= tuning.labelBandMinDepth &&
      node.depth <= tuning.labelBandMaxDepth
        ? tuning.groupLabelBand
        : 0
    )
    .paddingRight((node: any) => {
      const key = depthKeyFor(node.depth);
      return tuning.groupBorderByDepth[key] ?? (node.depth >= 1 ? tuning.groupBorder : 0);
    })
    .paddingBottom((node: any) => {
      const key = depthKeyFor(node.depth);
      return tuning.groupBorderByDepth[key] ?? (node.depth >= 1 ? tuning.groupBorder : 0);
    })
    .paddingLeft((node: any) => {
      const key = depthKeyFor(node.depth);
      return tuning.groupBorderByDepth[key] ?? (node.depth >= 1 ? tuning.groupBorder : 0);
    });

  const algorithmForDepth = (depth: number) => {
    if (depth <= 0) return tuning.tileAlgorithmRoot;
    if (depth === 1) return tuning.tileAlgorithmCategory;
    if (depth === 2) return tuning.tileAlgorithmTopic;
    return tuning.tileAlgorithmLeaf;
  };

  const orderForParentDepth = (parentDepth: number) => {
    const algo = algorithmForDepth(parentDepth);
    const key = depthKeyFor(parentDepth);

    if (algo === "binary") {
      if (!tuning.sortByValueForBinary) return null;
      const order = tuning.binarySortOrderByDepth[key];
      return order === "none" ? null : order;
    }

    if (algo === "squarify" || algo === "resquarify") {
      if (!tuning.sortByValueForSquarify) return null;
      const order = tuning.squarifySortOrderByDepth[key];
      return order === "none" ? null : order;
    }

    return null;
  };

  const sortComparator = (a: any, b: any) => {
    const parentDepth = a.parent?.depth ?? 0;
    const order = orderForParentDepth(parentDepth);
    if (!order) return 0;
    const direction = order === "desc" ? -1 : 1;
    return ((a.value ?? 0) - (b.value ?? 0)) * direction;
  };

  let rootNode = hierarchy(root)
    .sum((node: TreemapNode) => (typeof node.value === "number" ? node.value : 1))
    .sort(sortComparator);
  const mapped = layout(rootNode);

  const nodes: LayoutRect[] = [];
  const byId = new Map<string, LayoutRect>();

  mapped.descendants().forEach((node: any) => {
    const id = node.data.id;
    if (!id) return;

    const rect: LayoutRect = {
      id,
      depth: node.depth,
      data: node.data,
      x0: node.x0 ?? 0,
      y0: node.y0 ?? 0,
      x1: node.x1 ?? 0,
      y1: node.y1 ?? 0,
      value: node.value ?? 0,
      parentId: node.parent?.data.id ?? null,
    };

    nodes.push(rect);
    byId.set(id, rect);
  });

  return { byId, nodes };
}

export function blendLayouts(from: LayoutMap, to: LayoutMap, t: number): LayoutMap {
  const blendedNodes: LayoutRect[] = [];
  const byId = new Map<string, LayoutRect>();

  for (const target of to.nodes) {
    const source = from.byId.get(target.id) ?? target;
    const rect: LayoutRect = {
      ...target,
      x0: source.x0 + (target.x0 - source.x0) * t,
      y0: source.y0 + (target.y0 - source.y0) * t,
      x1: source.x1 + (target.x1 - source.x1) * t,
      y1: source.y1 + (target.y1 - source.y1) * t,
    };
    blendedNodes.push(rect);
    byId.set(rect.id, rect);
  }

  return { byId, nodes: blendedNodes };
}

export function useAnimatedLayout(target: LayoutMap | null, durationMs: number): LayoutMap | null {
  const [animated, setAnimated] = useState<LayoutMap | null>(target);
  const prevRef = useRef<LayoutMap | null>(null);

  useEffect(() => {
    if (!target) return;

    const from = prevRef.current ?? target;
    const start = performance.now();
    let raf = 0;

    const tick = (now: number) => {
      const t = clamp((now - start) / durationMs, 0, 1);
      const eased = easeCubicInOut(t);
      setAnimated(blendLayouts(from, target, eased));
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        prevRef.current = target;
        setAnimated(target);
      }
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs]);

  return animated;
}

export function useLayoutMap(root: TreemapNode, width: number, height: number, tuning: TreemapTuning) {
  return useMemo(() => {
    if (width <= 0 || height <= 0) return null;
    return computeLayout(root, width, height, tuning);
  }, [root, width, height, tuning]);
}
