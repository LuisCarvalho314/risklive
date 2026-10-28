import type { TreemapNode } from "@/lib/dashboard";
import type { ExperimentalTimelineResult, SecaV2Decision } from "@/lib/newsmap-experimental-shared";

type V2Result = Extract<ExperimentalTimelineResult, { mode: "v2" }>;
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null;
const index = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) >= 0;
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(v => typeof v === "string" && v.trim().length > 0);

/** Native V2 hierarchy. Render keys are batch-local structural positions only. */
export function buildSecaV2View(payload: unknown, day: string, titles = new Map<string, string>()): V2Result {
  if (!record(payload) || payload.schema_version !== 1 || !index(payload.batch)
      || payload.next_batch !== payload.batch + 1 || !index(payload.retained_source_count)
      || !Array.isArray(payload.decisions)) throw new Error("Invalid V2 report");
  const batch = payload.batch;
  const decisions: SecaV2Decision[] = payload.decisions.map(decision => {
    if (!record(decision) || !Array.isArray(decision.path) || !decision.path.every(index)
        || typeof decision.reconstructed !== "boolean" || !record(decision.errors)
        || !["alpha", "beta", "importance"].every(k => typeof decision.errors === "object"
          && decision.errors !== null && typeof (decision.errors as Record<string, unknown>)[k] === "number"
          && Number.isFinite((decision.errors as Record<string, number>)[k])
          && (decision.errors as Record<string, number>)[k] >= 0)) throw new Error("Invalid V2 decision");
    return { path: decision.path as number[], reconstructed: decision.reconstructed,
      errors: decision.errors as SecaV2Decision["errors"] };
  });
  let remainingNodes = 10_000;
  const build = (hkt: unknown, position: number[], budget: number, parentScope?: Set<string>): TreemapNode[] => {
    if (!record(hkt) || !Array.isArray(hkt.nodes) || position.length > 64) throw new Error("Invalid V2 HKT");
    const nodes = hkt.nodes.map(raw => {
      if (--remainingNodes < 0 || !record(raw) || !strings(raw.words) || !strings(raw.sources)
          || new Set(raw.sources).size !== raw.sources.length
          || raw.sources.some(id => parentScope && !parentScope.has(id))) throw new Error("Invalid V2 node");
      return { words: raw.words, sources: raw.sources, child: raw.child };
    });
    const total = nodes.reduce((sum, node) => sum + node.sources.length, 0);
    return nodes.map((node, offset) => {
      const nodePath = [...position, offset];
      const mass = total ? budget * node.sources.length / total : 0;
      const children = node.child == null ? [] : build(node.child, nodePath, mass, new Set(node.sources));
      const hasVisibleChildren = children.some(child => (child.meta?.sourceCount ?? 0) > 0);
      const name = node.words.length ? node.words.slice(0, 4).join(" ") : "Unassigned";
      return { id: `v2:${batch}:${nodePath.join("/")}`, name, value: hasVisibleChildren ? 0 : mass,
        children: hasVisibleChildren ? children : [],
        meta: { title: name, sourceCount: node.sources.length,
          experimentalLayoutWeights: true,
          sourceRefs: node.sources.map(id => ({ id, title: titles.get(id),
            url: /^https?:\/\//i.test(id) ? id : null, isUrl: /^https?:\/\//i.test(id) })),
          description: `${node.sources.length} retained sources. Keywords: ${node.words.join(", ") || "refuge"}.`,
        } };
    });
  };
  const children = build(payload.root, [], payload.retained_source_count);
  const sources = new Set(children.flatMap(child => child.meta?.sourceRefs?.map(source => source.id) ?? []));
  if (sources.size !== payload.retained_source_count) throw new Error("V2 retained source count mismatch");
  return { mode: "v2", batch, day, retainedSourceCount: payload.retained_source_count, decisions,
    tree: { id: "root::newsmap", name: "SECALight V2", value: 0, children,
      meta: { experimentalLayoutWeights: true } } };
}
