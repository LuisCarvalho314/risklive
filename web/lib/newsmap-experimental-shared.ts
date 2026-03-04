import type { TreemapNode } from "@/lib/dashboard";

export type ExperimentalBatch = {
  index: number;
  day: string;
  filename: string;
  tree: TreemapNode;
};

export type ExperimentalTimeline = {
  totalBatches: number;
  selectedIndex: number;
  batches: ExperimentalBatch[];
};

export type ExperimentalTimelineKey = "30d" | "7d" | "3d";

export type ExperimentalTimelineResult =
  | {
      mode: "timeline";
      selectedKey: ExperimentalTimelineKey;
      timelines: Partial<Record<ExperimentalTimelineKey, ExperimentalTimeline>>;
    }
  | { mode: "fallback"; reason: string };

export type ExperimentalSizeMetric =
  | "mappedSourceCount"
  | "combinedError"
  | "alphaError"
  | "betaError"
  | "wordImportanceError"
  | "triggeredScore"
  | "composite";

export type ExperimentalSizeDirection = "highToLarge" | "highToSmall";

function valueOrZero(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function sortChildrenForLayout(children: TreemapNode[]): TreemapNode[] {
  return [...children].sort((a, b) => {
    const byValue = valueOrZero(b.value) - valueOrZero(a.value);
    if (byValue !== 0) return byValue;
    const byName = (a.name || "").localeCompare(b.name || "");
    if (byName !== 0) return byName;
    return (a.id || "").localeCompare(b.id || "");
  });
}

function getExperimentalMetricValue(node: TreemapNode, metric: ExperimentalSizeMetric): number | undefined {
  const metrics = node.meta?.experimentalMetrics;
  if (!metrics) return undefined;
  if (metric === "mappedSourceCount") return metrics.mappedSourceCount ?? metrics.composite;
  if (metric === "combinedError") return metrics.combinedError;
  if (metric === "alphaError") return metrics.alphaError;
  if (metric === "betaError") return metrics.betaError;
  if (metric === "wordImportanceError") return metrics.wordImportanceError;
  if (metric === "triggeredScore") return metrics.triggeredScore;
  return metrics.composite;
}

export function applyExperimentalSizeMetric(
  root: TreemapNode,
  metric: ExperimentalSizeMetric,
  direction: ExperimentalSizeDirection = "highToLarge"
): TreemapNode {
  const metricValues: number[] = [];
  const collectValues = (node: TreemapNode) => {
    const metricValue = getExperimentalMetricValue(node, metric);
    if (typeof metricValue === "number" && Number.isFinite(metricValue)) {
      metricValues.push(metricValue);
    }
    node.children?.forEach(collectValues);
  };
  collectValues(root);
  const minMetric = metricValues.length ? Math.min(...metricValues) : 0;
  const maxMetric = metricValues.length ? Math.max(...metricValues) : 0;

  const cloneNode = (node: TreemapNode): TreemapNode => {
    const nextChildrenRaw = node.children?.map(cloneNode);
    const metricValue = getExperimentalMetricValue(node, metric);
    const directionalMetricValue =
      typeof metricValue === "number" && Number.isFinite(metricValue)
        ? direction === "highToSmall"
          ? maxMetric + minMetric - metricValue
          : metricValue
        : undefined;
    const nextChildren = nextChildrenRaw ? sortChildrenForLayout(nextChildrenRaw) : undefined;
    const childAggregate = nextChildren?.reduce((sum, child) => sum + valueOrZero(child.value), 0);
    const nextValue =
      typeof directionalMetricValue === "number" && Number.isFinite(directionalMetricValue)
        ? directionalMetricValue
        : typeof node.value === "number" && Number.isFinite(node.value)
          ? node.value
          : typeof childAggregate === "number" && Number.isFinite(childAggregate)
            ? childAggregate
            : node.value;
    return {
      ...node,
      value: nextValue,
      children: nextChildren,
    };
  };
  return cloneNode(root);
}
