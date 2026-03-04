import { TreemapNode } from "@/lib/dashboard";
import { TreemapTuning } from "@/lib/treemap/config";

type Meta = NonNullable<TreemapNode["meta"]>;

export type NodeIndex = {
  byId: Map<string, TreemapNode>;
  parentById: Map<string, string | null>;
  childrenById: Map<string, string[]>;
  leafIds: Set<string>;
};

export function indexTree(root: TreemapNode): NodeIndex {
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

export function ancestorsOf(nodeId: string, parentById: Map<string, string | null>): string[] {
  const path: string[] = [];
  let current: string | null | undefined = nodeId;
  while (current) {
    path.push(current);
    current = parentById.get(current) ?? null;
  }
  return path.reverse();
}

export function descendantsOf(nodeId: string, childrenById: Map<string, string[]>): Set<string> {
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

export function buildEmphasisSet(params: {
  focusId: string;
  flagFilter: "All" | "Red" | "Yellow";
  treeIndex: NodeIndex;
}): Set<string> {
  const { focusId, flagFilter, treeIndex } = params;
  const rootId = "root::newsmap";
  const validFocusId = treeIndex.byId.has(focusId) ? focusId : rootId;

  const focusSet = new Set<string>();
  unionInto(focusSet, descendantsOf(validFocusId, treeIndex.childrenById));
  unionInto(focusSet, ancestorsOf(validFocusId, treeIndex.parentById));

  if (flagFilter === "All") {
    focusSet.add(rootId);
    return focusSet;
  }

  const flaggedLeaves = new Set<string>();
  for (const leafId of treeIndex.leafIds) {
    const leaf = treeIndex.byId.get(leafId);
        const meta = (leaf?.meta ?? {}) as Meta;
        const flag = (meta.alertFlag ?? "").toString().trim().toLowerCase();
        if (flag === flagFilter.toLowerCase()) flaggedLeaves.add(leafId);
  }

  const filterKeep = new Set<string>();
  for (const leafId of flaggedLeaves) {
    unionInto(filterKeep, ancestorsOf(leafId, treeIndex.parentById));
    filterKeep.add(leafId);
  }

  const emphasized = new Set<string>();
  emphasized.add(rootId);
  for (const id of focusSet) {
    if (filterKeep.has(id)) emphasized.add(id);
  }

  const toAddAncestors: string[] = [];
  for (const id of emphasized) {
    for (const a of ancestorsOf(id, treeIndex.parentById)) toAddAncestors.push(a);
  }
  unionInto(emphasized, toAddAncestors);

  return emphasized;
}

export function buildWeightedTree(root: TreemapNode, emphasized: Set<string>, tuning: TreemapTuning): TreemapNode {
  const { minGroupWeight, epsilon, weightMode, valueTransform, redAlertWeightBoost } = tuning;
  const weightById = new Map<string, number>();

  const transformValue = (value: number) => {
    if (weightMode !== "value") return 1;
    if (tuning.applyValueTransformInNormalize) return Math.max(0, value);
    if (valueTransform === "sqrt") return Math.sqrt(Math.max(0, value));
    if (valueTransform === "log1p") return Math.log1p(Math.max(0, value));
    return Math.max(0, value);
  };

  const computeWeights = (node: TreemapNode): number => {
    const children = node.children ?? [];
    if (!children.length) {
      const raw = typeof node.value === "number" ? node.value : 1;
      const weightBase = weightMode === "value" ? transformValue(raw) : 1;
      const meta = (node.meta ?? {}) as Meta;
      const flag = (meta.alertFlag ?? "").toString().trim().toLowerCase();
      const boost = flag === "red" ? Math.max(1, redAlertWeightBoost) : 1;
      const weight = weightBase * boost;
      if (node.id) weightById.set(node.id, weight);
      return weight;
    }

    const total = children.reduce((sum, child) => sum + computeWeights(child), 0);
    if (node.id) weightById.set(node.id, total);
    return total;
  };

  computeWeights(root);

  const clone = (node: TreemapNode): TreemapNode => {
    const children = node.children?.map(clone) ?? [];
    const baseValue = weightById.get(node.id ?? "") ?? 1;

    if (children.length) {
      const sum = children.reduce((acc, child) => acc + (weightById.get(child.id ?? "") ?? 1), 0);
      const scaled = emphasized.has(node.id ?? "") ? sum : sum * epsilon;
      const weight = Math.max(scaled, minGroupWeight);
      return { ...node, children, value: weight };
    }

    const scaled = emphasized.has(node.id ?? "") ? baseValue : baseValue * epsilon;
    const weight = Math.max(scaled, minGroupWeight);
    return { ...node, children: [], value: weight };
  };

  return clone(root);
}

export function buildFilteredTree(root: TreemapNode, keepIds: Set<string>): TreemapNode {
  const clone = (node: TreemapNode): TreemapNode | null => {
    if (node.id && !keepIds.has(node.id)) return null;
    const children = (node.children ?? [])
      .map(clone)
      .filter(Boolean) as TreemapNode[];
    return { ...node, children };
  };

  return clone(root) ?? { ...root, children: [] };
}

export function findSubtree(root: TreemapNode, targetId: string): TreemapNode | null {
  if (root.id === targetId) return root;
  const stack: TreemapNode[] = [...(root.children ?? [])];
  while (stack.length) {
    const node = stack.pop()!;
    if (node.id === targetId) return node;
    const children = node.children ?? [];
    for (const child of children) stack.push(child);
  }
  return null;
}
