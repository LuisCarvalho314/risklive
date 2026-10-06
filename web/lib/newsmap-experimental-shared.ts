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

function metricValue(node: TreemapNode, metric: ExperimentalSizeMetric): number | undefined {
  const value = node.meta?.experimentalMetrics?.[metric];
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : undefined;
}

export function experimentalMetricStatus(root: TreemapNode, metric: ExperimentalSizeMetric) {
  const scopes = new Map<string, boolean>();
  const visit = (node: TreemapNode) => {
    if (node.meta?.experimentalMetrics) {
      const id = String(node.meta.experimentalMetrics.hktId ?? node.id);
      scopes.set(id, metricValue(node, metric) !== undefined);
    }
    node.children?.forEach(visit);
  };
  visit(root);
  const available = [...scopes.values()].filter(Boolean).length;
  return { available, total: scopes.size, unavailable: available < scopes.size || scopes.size === 0 };
}

/** Each sibling HKT scope owns one budget. Its nodes divide that budget by
 * source mass (equal if empty), then descendants partition it conditionally.
 * Only leaves carry D3 sum mass. Internal values are zero, avoiding duplicate
 * diagnostic mass across descendants. Incomplete snapshots use equal HKT
 * budgets with an explicit unavailable status, never a proxy substitution.
 */
export function applyExperimentalSizeMetric(
  root: TreemapNode,
  metric: ExperimentalSizeMetric,
  direction: ExperimentalSizeDirection = "highToLarge"
): TreemapNode {
  const unavailable = experimentalMetricStatus(root, metric).unavailable;
  const provenance = unavailable ? "unavailable" : metric === "composite" ? "legacy_proxy" : "seca_actual";
  const epsilon = 1e-9;
  const divide = (nodes: TreemapNode[], budget: number): TreemapNode[] => {
    const groups = new Map<string, TreemapNode[]>();
    nodes.forEach((node) => {
      const id = String(node.meta?.experimentalMetrics?.hktId ?? node.id);
      groups.set(id, [...(groups.get(id) ?? []), node]);
    });
    const entries = [...groups.values()];
    const values = entries.map((group) => unavailable ? 1 : metricValue(group[0], metric) ?? 1);
    const min = Math.min(...values), max = Math.max(...values);
    const weights = values.map((value) => epsilon + (direction === "highToSmall" ? max - value + min : value));
    const total = weights.reduce((sum, value) => sum + value, 0);
    return entries.flatMap((group, index) => {
      const masses = group.map((node) => Math.max(1, node.meta?.sourceCount ?? 1));
      const mass = masses.reduce((sum, value) => sum + value, 0);
      return group.map((node, i) => clone(node, budget * weights[index] / total * masses[i] / mass));
    });
  };
  const clone = (node: TreemapNode, budget: number): TreemapNode => {
    const children = node.children?.length ? divide(node.children, budget) : undefined;
    return { ...node, value: children ? 0 : budget, children,
      meta: { ...node.meta, experimentalLayoutWeights: true, experimentalMetricProvenance: provenance,
        description: `${node.meta?.description ?? ""} | selected_metric=${metric} | selected_metrics=${provenance}` } };
  };
  return clone(root, 1);
}
