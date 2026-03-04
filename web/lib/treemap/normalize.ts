import { TreemapNode } from "@/lib/dashboard";
import type { TreemapTuning } from "@/lib/treemap/config";

type Meta = NonNullable<TreemapNode["meta"]>;

const fallbackPalette = [
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

function normalizeAlertFlag(value?: string | null): "Red" | "Yellow" | "Green" | undefined {
  if (!value) return undefined;
  const cleaned = value.trim().toLowerCase();
  if (cleaned === "red") return "Red";
  if (cleaned === "yellow") return "Yellow";
  if (cleaned === "green") return "Green";
  return undefined;
}

function applyValueTransform(value: number, tuning?: TreemapTuning): number {
  if (!tuning || tuning.weightMode !== "value" || !tuning.applyValueTransformInNormalize) {
    return Math.max(1, value);
  }

  const raw = Math.max(0, value);
  let transformed = raw;
  if (tuning.valueTransform === "sqrt") transformed = Math.sqrt(raw);
  if (tuning.valueTransform === "log1p") transformed = Math.log1p(raw);

  return Math.max(0.0001, transformed);
}

export function normalizeToNewsmapTree(
  input: TreemapNode,
  tuning?: TreemapTuning,
  palette?: string[]
): TreemapNode {
  const leaves = collectLeaves(input);
  const activePalette = palette && palette.length ? palette : fallbackPalette;

  type LeafRecord = { leaf: TreemapNode; meta: Meta };
  const records: LeafRecord[] = leaves
    .map((leaf) => {
      const rawMeta = (leaf.meta ?? {}) as Meta & { alert_flag?: string | null };
      const rawFlag = rawMeta.alertFlag ?? rawMeta.alert_flag;
      return {
        leaf,
        meta: {
          ...rawMeta,
          alertFlag: normalizeAlertFlag(rawFlag),
        } as Meta,
      };
    })
    .filter((rec) => rec.meta.alertFlag !== "Green");

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
    return activePalette[index % activePalette.length];
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

      const leafNodes: TreemapNode[] = topicLeaves.map(({ leaf, meta }, index) => {
        const isLastLeaf = index === topicLeaves.length - 1;
        const stableKey = `${meta.url ?? ""}|${meta.title ?? ""}|${leaf.name ?? ""}`;
        const leafId = `leaf::${slugify(categoryName)}::${slugify(topicName)}::${djb2Hash(stableKey)}::${index}`;

        const rawValue = typeof leaf.value === "number" ? leaf.value : 1;
        const baseValue = applyValueTransform(rawValue, tuning);
        const remainderBias =
          tuning?.leafRemainderBias && tuning.leafRemainderBias > 0 && tuning.leafRemainderBias < 1 && isLastLeaf
            ? tuning.leafRemainderBias
            : 1;

        return {
          name: meta.title || leaf.name || "Untitled",
          id: leafId,
          value: Math.max(0.0001, baseValue * remainderBias),
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
