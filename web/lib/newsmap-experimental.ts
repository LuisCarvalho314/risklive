import * as fs from "node:fs/promises";
import * as path from "node:path";

import type { TreemapNode } from "@/lib/dashboard";
import type {
  ExperimentalBatch,
  ExperimentalTimeline,
  ExperimentalTimelineKey,
  ExperimentalTimelineResult,
} from "@/lib/newsmap-experimental-shared";

export type NewsCsvRow = {
  title: string;
  url?: string;
  description?: string;
  timestamp: string;
  query: string;
  sourcePrice?: number;
};

type SecaVerboseWordRef = {
  word_id: number;
  token?: string | null;
};

type SecaVerboseSourceRef = {
  internal_source_id: number;
  external_source_id: string;
};

type SecaVerboseHkt = {
  hkt_id: number;
  parent_node_id: number;
  expected_words?: SecaVerboseWordRef[];
  all_node_words_union?: SecaVerboseWordRef[];
  node_ids?: number[];
};

type SecaVerboseNode = {
  node_id: number;
  hkt_id: number;
  words?: SecaVerboseWordRef[];
  sources?: SecaVerboseSourceRef[];
  top_words?: SecaVerboseWordRef[];
  is_refuge_node?: boolean;
  diagnostics?: {
    hkt_id?: number;
    scoped_source_count?: number;
    mapped_source_count?: number;
    should_reconstruct?: boolean;
    trigger_reasons?: string[];
    alpha_error?: number;
    beta_error?: number;
    word_importance_error?: number;
    paper_alpha_error?: number;
    paper_beta_error?: number;
    paper_word_importance_error?: number;
  };
};

type SecaVerboseTree = {
  hkts: SecaVerboseHkt[];
  nodes: SecaVerboseNode[];
};

type SecaBatchContext = {
  batchDay?: string;
  latestDay?: string;
  activeWindowDays: number;
};

type SourceLookup = {
  byExternalId: Map<string, { title: string; url?: string }>;
  byUrl: Map<string, string>;
};

type SecaTimelineManifest = {
  total_batches?: number;
  files: string[];
  days?: string[];
  generated_at?: string;
  version?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function slugify(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "unknown";
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

function extractTokens(refs?: SecaVerboseWordRef[]): string[] {
  if (!Array.isArray(refs)) return [];
  return refs
    .map((entry) => asString(entry?.token))
    .filter((token): token is string => Boolean(token));
}

function isLikelyUrl(value: string): boolean {
  return /^https?:\/\//i.test(value.trim());
}

function nodeLabel(node: SecaVerboseNode): string {
  if (node.is_refuge_node) return "<>";
  const topTokens = extractTokens(node.top_words);
  if (topTokens.length) return topTokens.slice(0, 4).join(" ");
  const words = extractTokens(node.words);
  if (words.length) return words.slice(0, 4).join(" ");
  return `(node ${node.node_id})`;
}

function hktKeyword(hkt?: SecaVerboseHkt): string {
  if (!hkt) return "(unknown HKT)";
  const expected = extractTokens(hkt.expected_words);
  if (expected.length) return expected[0];
  const union = extractTokens(hkt.all_node_words_union);
  if (union.length) return union[0];
  return `HKT ${hkt.hkt_id}`;
}

function parseSecaTimelineManifest(payload: unknown): SecaTimelineManifest {
  if (!isRecord(payload)) throw new Error("SECA timeline manifest is not an object");
  const files = Array.isArray(payload.files)
    ? payload.files.map((file) => asString(file)).filter((file): file is string => Boolean(file))
    : [];
  if (!files.length) throw new Error("SECA timeline manifest must contain files[]");

  const totalBatches = asNumber(payload.total_batches);
  if (typeof totalBatches === "number" && Number.isInteger(totalBatches) && totalBatches !== files.length) {
    throw new Error("SECA timeline manifest total_batches must match files length");
  }
  const days = Array.isArray(payload.days)
    ? payload.days.map((value) => asString(value)).filter((value): value is string => Boolean(value))
    : undefined;
  if (days && days.length > 0 && days.length !== files.length) {
    throw new Error("SECA timeline manifest days length must match files length");
  }

  return {
    total_batches: totalBatches,
    files,
    days,
    generated_at: asString(payload.generated_at),
    version: asString(payload.version),
  };
}

function parseSecaVerboseTree(payload: unknown): SecaVerboseTree {
  if (!isRecord(payload)) throw new Error("SECA batch payload is not an object");
  if (!Array.isArray(payload.hkts) || !Array.isArray(payload.nodes)) {
    throw new Error("SECA batch payload must include hkts[] and nodes[]");
  }
  return {
    hkts: payload.hkts as SecaVerboseHkt[],
    nodes: payload.nodes as SecaVerboseNode[],
  };
}

function dayDiffUtc(latestDay?: string, batchDay?: string): number {
  if (!latestDay || !batchDay) return 0;
  const latest = new Date(`${latestDay}T00:00:00Z`);
  const batch = new Date(`${batchDay}T00:00:00Z`);
  if (Number.isNaN(latest.getTime()) || Number.isNaN(batch.getTime())) return 0;
  return Math.max(0, Math.round((latest.getTime() - batch.getTime()) / 86_400_000));
}

function computeBatchSignals(ctx: SecaBatchContext): { recencyWeight: number; activeWindowWeight: number } {
  const ageDays = dayDiffUtc(ctx.latestDay, ctx.batchDay);
  const recencyWeight = 1 / (1 + Math.max(0, ageDays)); // newer batch -> higher weight
  const activeWindowWeight = ageDays <= ctx.activeWindowDays ? 1 : 0.35;
  return { recencyWeight, activeWindowWeight };
}

function buildTreemapFromSecaVerboseTree(
  tree: SecaVerboseTree,
  ctx: SecaBatchContext,
  sourceLookup?: SourceLookup
): TreemapNode {
  const hktsById = new Map<number, SecaVerboseHkt>();
  const nodesById = new Map<number, SecaVerboseNode>();
  tree.hkts.forEach((hkt) => {
    if (typeof hkt?.hkt_id === "number") hktsById.set(hkt.hkt_id, hkt);
  });
  tree.nodes.forEach((node) => {
    if (typeof node?.node_id === "number") nodesById.set(node.node_id, node);
  });

  const parentByNodeId = new Map<number, number>();
  nodesById.forEach((node) => {
    const hkt = hktsById.get(node.hkt_id);
    const parentNodeId = hkt?.parent_node_id ?? 0;
    if (parentNodeId && nodesById.has(parentNodeId)) {
      parentByNodeId.set(node.node_id, parentNodeId);
    }
  });

  const childNodes = new Map<number, number[]>();
  nodesById.forEach((node) => {
    const parent = parentByNodeId.get(node.node_id);
    if (parent == null) return;
    if (!childNodes.has(parent)) childNodes.set(parent, []);
      childNodes.get(parent)!.push(node.node_id);
  });

  const childrenCountByNode = new Map<number, number>();
  childNodes.forEach((children, nodeId) => childrenCountByNode.set(nodeId, children.length));

  const nodeDepthCache = new Map<number, number>();
  const nodeDepth = (nodeId: number): number => {
    if (nodeDepthCache.has(nodeId)) return nodeDepthCache.get(nodeId) ?? 0;
    const parent = parentByNodeId.get(nodeId);
    const depth = parent ? nodeDepth(parent) + 1 : 0;
    nodeDepthCache.set(nodeId, depth);
    return depth;
  };

  const subtreeMassCache = new Map<number, number>();
  const subtreeMass = (nodeId: number): number => {
    if (subtreeMassCache.has(nodeId)) return subtreeMassCache.get(nodeId) ?? 1;
    const node = nodesById.get(nodeId);
    if (!node) return 1;
    const ownSources = Array.isArray(node.sources) ? node.sources.length : 0;
    const childMass = (childNodes.get(nodeId) ?? []).reduce((sum, childId) => sum + subtreeMass(childId), 0);
    const mass = Math.max(1, ownSources + childMass);
    subtreeMassCache.set(nodeId, mass);
    return mass;
  };

  const rootMass = Math.max(
    1,
    Array.from(nodesById.keys())
      .filter((id) => !parentByNodeId.has(id))
      .reduce((sum, rootId) => sum + subtreeMass(rootId), 0)
  );

  const { recencyWeight, activeWindowWeight } = computeBatchSignals(ctx);

  const buildNode = (nodeId: number, ancestors: Set<number>): TreemapNode | null => {
    const raw = nodesById.get(nodeId);
    if (!raw) return null;
    if (ancestors.has(nodeId)) return null;

    const nodeName = nodeLabel(raw);
    const category = hktKeyword(hktsById.get(raw.hkt_id));
    const sourceCount = Array.isArray(raw.sources) ? raw.sources.length : 0;
    const sourceRefs = Array.isArray(raw.sources)
      ? Array.from(
          new Map(
            raw.sources
              .map((entry) => asString(entry?.external_source_id))
              .filter((id): id is string => Boolean(id))
              .map((id) => {
                const isUrl = isLikelyUrl(id);
                const fromExternal = sourceLookup?.byExternalId.get(id);
                const url = isUrl ? id : fromExternal?.url ?? null;
                const title = fromExternal?.title ?? (url ? sourceLookup?.byUrl.get(url) : undefined);
                return [
                  id,
                  {
                    id,
                    ...(title ? { title } : {}),
                    url,
                    isUrl,
                  },
                ] as const;
              })
          ).values()
        )
      : [];
    const diagnostics = isRecord(raw.diagnostics) ? raw.diagnostics : undefined;
    const hkt = hktsById.get(raw.hkt_id);
    const expectedWordsArr = Array.isArray(hkt?.expected_words) ? hkt.expected_words : [];
    const unionWordsArr = Array.isArray(hkt?.all_node_words_union) ? hkt.all_node_words_union : [];
    const expectedWords = expectedWordsArr.length;
    const unionWords = unionWordsArr.length;
    const nodeWords = Array.isArray(raw.words) ? raw.words.length : 0;
    const topWords = Array.isArray(raw.top_words) ? raw.top_words.length : 0;
    const wordMass = Math.max(1, expectedWords + unionWords + nodeWords + topWords);

    // Proxy for trigger/error intensity using divergence and refuge pressure.
    const lexicalDivergence = unionWords > 0 ? Math.abs(unionWords - expectedWords) / unionWords : 0;
    const refugePenalty = raw.is_refuge_node ? 1 : 0;
    const branchBreadth = childrenCountByNode.get(raw.node_id) ?? 0;
    const triggerErrorProxy = 1 + lexicalDivergence + refugePenalty * 0.35 + Math.min(1, branchBreadth / 8);

    // HKT significance: deeper nodes with larger subtree mass get higher emphasis.
    const depth = nodeDepth(raw.node_id);
    const normalizedDepth = Math.min(1, depth / 6);
    const normalizedSubtreeMass = Math.min(1, subtreeMass(raw.node_id) / rootMass);
    const hktSignificance = 1 + normalizedDepth * 0.4 + normalizedSubtreeMass * 0.8;

    const baseSourceMass = Math.max(1, sourceCount);
    const recencySourceWeighted = baseSourceMass * (0.5 + recencyWeight); // 0.5..1.5
    const compositeValue = Math.max(
      1,
      Math.round(
        recencySourceWeighted *
          Math.sqrt(wordMass) *
          hktSignificance *
          triggerErrorProxy *
          activeWindowWeight
      )
    );
    const recencyValue = Math.max(1, Math.round(recencySourceWeighted * baseSourceMass));
    const wordMassValue = Math.max(1, Math.round(baseSourceMass * Math.sqrt(wordMass)));
    const hktSignificanceValue = Math.max(1, Math.round(baseSourceMass * hktSignificance));
    const triggerIntensityValue = Math.max(1, Math.round(baseSourceMass * triggerErrorProxy));
    const activeWindowValue = Math.max(1, Math.round(baseSourceMass * activeWindowWeight));

    const alphaErrorRaw = asNumber(diagnostics?.paper_alpha_error) ?? asNumber(diagnostics?.alpha_error);
    const betaErrorRaw = asNumber(diagnostics?.paper_beta_error) ?? asNumber(diagnostics?.beta_error);
    const wordImportanceErrorRaw =
      asNumber(diagnostics?.paper_word_importance_error) ?? asNumber(diagnostics?.word_importance_error);
    const mappedSourceCountRaw = asNumber(diagnostics?.mapped_source_count) ?? sourceCount;
    const shouldReconstruct = Boolean(diagnostics?.should_reconstruct);

    // Real SECA diagnostics first; scaled so larger tile = higher diagnostic magnitude.
    const mappedSourceCountValue = Math.max(1, Math.round(Math.max(0, mappedSourceCountRaw)));
    const alphaErrorValue = Math.max(1, Math.round((alphaErrorRaw ?? 0) * 1000));
    const betaErrorValue = Math.max(1, Math.round((betaErrorRaw ?? 0) * 1000));
    const wordImportanceErrorValue = Math.max(1, Math.round((wordImportanceErrorRaw ?? 0) * 1000));
    const errorTerms = [alphaErrorRaw, betaErrorRaw, wordImportanceErrorRaw].filter(
      (value): value is number => typeof value === "number" && Number.isFinite(value)
    );
    const combinedErrorRaw = errorTerms.length
      ? Math.sqrt(errorTerms.reduce((sum, value) => sum + value * value, 0) / errorTerms.length)
      : 0;
    const combinedErrorValue = Math.max(1, Math.round(combinedErrorRaw * 1000));
    const triggeredScoreValue = shouldReconstruct
      ? Math.max(1, mappedSourceCountValue * 2)
      : Math.max(1, Math.round(mappedSourceCountValue * 0.75));

    const nestedAncestors = new Set(ancestors);
    nestedAncestors.add(nodeId);

    const childTopicNodes = (childNodes.get(nodeId) ?? [])
      .sort((a, b) => a - b)
      .map((childId) => buildNode(childId, nestedAncestors))
      .filter((node): node is TreemapNode => Boolean(node));

    const children: TreemapNode[] = childTopicNodes;

    return {
      id: `node::${raw.node_id}`,
      name: nodeName,
      value: compositeValue,
      children,
      meta: {
        title: nodeName,
        category,
        topic: `HKT ${raw.hkt_id}`,
        topicLabel: `HKT ${raw.hkt_id}`,
        sourceCount,
        sourceRefs,
        description: [
          raw.is_refuge_node ? "SECA refuge node" : `SECA node ${raw.node_id}`,
          `sources=${sourceCount}`,
          `value=${compositeValue}`,
          `recency=${recencyWeight.toFixed(2)}`,
          `word_mass=${wordMass}`,
          `hkt_sig=${hktSignificance.toFixed(2)}`,
          `trigger_proxy=${triggerErrorProxy.toFixed(2)}`,
          `active_window=${activeWindowWeight.toFixed(2)}`,
          diagnostics ? "metrics=seca_actual" : "metrics=proxy_fallback",
        ].join(" | "),
        experimentalMetrics: {
          mappedSourceCount: mappedSourceCountValue,
          combinedError: combinedErrorValue,
          alphaError: alphaErrorValue,
          betaError: betaErrorValue,
          wordImportanceError: wordImportanceErrorValue,
          triggeredScore: triggeredScoreValue,
          composite: compositeValue,
          recency: recencyValue,
          wordMass: wordMassValue,
          hktSignificance: hktSignificanceValue,
          triggerIntensity: triggerIntensityValue,
          activeWindow: activeWindowValue,
        },
      },
    };
  };

  const rootNodeIds = Array.from(nodesById.values())
    .filter((node) => !parentByNodeId.has(node.node_id))
    .map((node) => node.node_id)
    .sort((a, b) => a - b);

  const rootChildren = rootNodeIds
    .map((nodeId) => buildNode(nodeId, new Set<number>()))
    .filter((node): node is TreemapNode => Boolean(node));

  return {
    id: "root::newsmap",
    name: "SECA Tree",
    children: rootChildren,
  };
}

function deriveHktTopicLabel(row: NewsCsvRow): string {
  const source = (row.description || row.title || "").trim();
  if (!source) return "General";
  const sentence = source.split(/[.!?]/)[0] ?? source;
  const tokens = sentence
    .split(/\s+/)
    .map((token) => token.replace(/[^a-zA-Z0-9-]/g, "").trim())
    .filter((token) => token.length > 2);
  const compact = tokens.slice(0, 4).join(" ");
  return compact || "General";
}

function parseCsvLine(line: string): string[] {
  const cells: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    const next = line[i + 1];
    if (char === "\"") {
      if (inQuotes && next === "\"") {
        current += "\"";
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === "," && !inQuotes) {
      cells.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  cells.push(current);
  return cells.map((value) => value.trim());
}

export function parseNewsDataCsv(content: string): NewsCsvRow[] {
  const lines = content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return [];
  const headers = parseCsvLine(lines[0]).map((header) => header.toLowerCase());
  const getIndex = (name: string) => headers.findIndex((header) => header === name.toLowerCase());
  const idxTitle = getIndex("title");
  const idxUrl = getIndex("url");
  const idxDescription = getIndex("description");
  const idxTimestamp = getIndex("timestamp");
  const idxQuery = getIndex("query");
  const idxSourcePrice = getIndex("source_price");

  if (idxTitle < 0 || idxTimestamp < 0 || idxQuery < 0) {
    throw new Error("news_data.csv is missing required columns");
  }

  const rows: NewsCsvRow[] = [];
  for (let i = 1; i < lines.length; i += 1) {
    const cells = parseCsvLine(lines[i]);
    const title = cells[idxTitle]?.trim();
    const timestamp = cells[idxTimestamp]?.trim();
    const query = cells[idxQuery]?.trim();
    if (!title || !timestamp || !query) continue;
    const priceRaw = idxSourcePrice >= 0 ? cells[idxSourcePrice]?.trim() : undefined;
    const sourcePrice = priceRaw ? Number(priceRaw) : undefined;
    rows.push({
      title,
      timestamp,
      query,
      url: idxUrl >= 0 ? cells[idxUrl]?.trim() || undefined : undefined,
      description: idxDescription >= 0 ? cells[idxDescription]?.trim() || undefined : undefined,
      sourcePrice: Number.isFinite(sourcePrice ?? NaN) ? sourcePrice : undefined,
    });
  }
  return rows;
}

export function clampBatchIndex(index: number, total: number): number {
  if (total <= 0) return 0;
  if (!Number.isFinite(index)) return total - 1;
  if (index < 0) return 0;
  if (index >= total) return total - 1;
  return Math.floor(index);
}

export function buildTreemapFromRows(rows: NewsCsvRow[], day: string): TreemapNode {
  const categories = new Map<string, NewsCsvRow[]>();
  rows.forEach((row) => {
    const key = row.query || "Unknown";
    if (!categories.has(key)) categories.set(key, []);
    categories.get(key)!.push(row);
  });

  const categoryNodes: TreemapNode[] = Array.from(categories.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([category, categoryRows]) => {
      const categorySlug = slugify(category);
      const byTopic = new Map<string, NewsCsvRow[]>();
      categoryRows.forEach((row) => {
        const topic = deriveHktTopicLabel(row);
        if (!byTopic.has(topic)) byTopic.set(topic, []);
        byTopic.get(topic)!.push(row);
      });

      const topicNodes: TreemapNode[] = Array.from(byTopic.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([topic, topicRows]) => {
          const topicSlug = slugify(topic);
          const leaves: TreemapNode[] = topicRows.map((row, idx) => ({
            id: `leaf::${categorySlug}::${topicSlug}::${idx}`,
            name: row.title,
            value: 1,
            meta: {
              title: row.title,
              url: row.url ?? null,
              category,
              timestamp: row.timestamp,
              shortSummary: row.description,
              description:
                row.sourcePrice != null
                  ? `${row.description ?? ""}\nSource price: ${row.sourcePrice}`.trim()
                  : row.description,
              topic,
              topicLabel: topic,
            },
          }));

          return {
            id: `topic::${categorySlug}::${topicSlug}`,
            name: topic,
            children: leaves,
          };
        });

      return {
        id: `cat::${categorySlug}`,
        name: category,
        children: topicNodes,
      };
    });

  return {
    id: "root::newsmap",
    name: "All News",
    children: categoryNodes,
  };
}

function toUtcDay(timestamp: string): string | null {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString().slice(0, 10);
}

function buildSourceLookup(rows: NewsCsvRow[]): SourceLookup {
  const byExternalId = new Map<string, { title: string; url?: string }>();
  const byUrl = new Map<string, string>();
  let globalIndex = 0;
  for (const row of rows) {
    const title = row.title.trim();
    if (title) {
      const normalizedUrl = row.url?.trim() || undefined;
      const externalId = `row_${String(globalIndex).padStart(6, "0")}`;
      byExternalId.set(externalId, normalizedUrl ? { title, url: normalizedUrl } : { title });
      if (row.url) {
        const url = row.url.trim();
        if (url) {
          byUrl.set(url, title);
          byExternalId.set(url, { title, url });
        }
      }
    }
    globalIndex += 1;
  }
  return { byExternalId, byUrl };
}

export function buildDailyBatches(rows: NewsCsvRow[]): ExperimentalBatch[] {
  const byDay = new Map<string, NewsCsvRow[]>();
  rows.forEach((row) => {
    const day = toUtcDay(row.timestamp);
    if (!day) return;
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day)!.push(row);
  });

  const days = Array.from(byDay.keys()).sort((a, b) => a.localeCompare(b));
  return days.map((day, index) => ({
    index,
    day,
    filename: `${day}.news_data.csv`,
    tree: buildTreemapFromRows(byDay.get(day) ?? [], day),
  }));
}

function getSecaTimelineDirectory(key: ExperimentalTimelineKey): string {
  const dirName = key === "7d" ? "seca-light-7d" : key === "3d" ? "seca-light-3d" : "seca-light-30d";
  return path.join(process.cwd(), "..", "results", "web", "newsmap", dirName);
}

async function readJson(filePath: string): Promise<unknown> {
  const raw = await fs.readFile(filePath, "utf-8");
  return JSON.parse(raw);
}

function resolveBatchPath(baseDir: string, filename: string): string {
  if (!filename || filename.includes("\u0000")) throw new Error("Invalid SECA batch filename");
  const resolved = path.resolve(baseDir, filename);
  const normalizedBase = path.resolve(baseDir) + path.sep;
  if (!resolved.startsWith(normalizedBase)) {
    throw new Error("SECA batch filename must remain within seca-light directory");
  }
  return resolved;
}

function parseBatchDay(batchPayload: unknown, index: number): string {
  if (isRecord(batchPayload)) {
    const ts = asString(batchPayload.generated_at) ?? asString(batchPayload.timestamp);
    if (ts) {
      const parsed = new Date(ts);
      if (!Number.isNaN(parsed.getTime())) return parsed.toISOString().slice(0, 10);
    }
  }
  return `batch-${String(index).padStart(4, "0")}`;
}

async function loadSecaTimelineBatches(key: ExperimentalTimelineKey): Promise<ExperimentalTimeline | null> {
  const baseDir = getSecaTimelineDirectory(key);
  let sourceLookup: SourceLookup | undefined;
  try {
    sourceLookup = buildSourceLookup(await readNewsDataFiles());
  } catch {
    sourceLookup = undefined;
  }
  const manifestCandidates = ["manifest.json", "timeline_manifest.json"];
  let manifest: SecaTimelineManifest | null = null;
  let lastError: string | null = null;

  for (const filename of manifestCandidates) {
    const filePath = path.join(baseDir, filename);
    try {
      const payload = await readJson(filePath);
      manifest = parseSecaTimelineManifest(payload);
      break;
    } catch (error) {
      lastError = error instanceof Error ? error.message : "Unknown manifest error";
    }
  }

  if (!manifest) {
    if (lastError) throw new Error(`SECA timeline manifest not loadable: ${lastError}`);
    return null;
  }

  const batches: ExperimentalBatch[] = [];
  const latestDayFromManifest = manifest.days?.[manifest.days.length - 1];
  for (let i = 0; i < manifest.files.length; i += 1) {
    const filename = manifest.files[i];
    const batchPath = resolveBatchPath(baseDir, filename);
    const batchPayload = await readJson(batchPath);
    const secaTree = parseSecaVerboseTree(batchPayload);
    const day = manifest.days?.[i] ?? parseBatchDay(batchPayload, i);
    const tree = buildTreemapFromSecaVerboseTree(
      secaTree,
      {
        batchDay: day,
        latestDay: latestDayFromManifest,
        activeWindowDays: key === "7d" ? 7 : key === "3d" ? 3 : 30,
      },
      sourceLookup
    );
    batches.push({ index: i, day, filename, tree });
  }

  if (!batches.length) return null;
  return {
    totalBatches: batches.length,
    selectedIndex: batches.length - 1,
    batches,
  };
}

function getNewsDataPaths(): string[] {
  const base = path.join(process.cwd(), "..", "results");
  return [path.join(base, "backup_data", "news_data.csv"), path.join(base, "data", "news_data.csv")];
}

async function readNewsDataFiles(): Promise<NewsCsvRow[]> {
  const paths = getNewsDataPaths();
  const allRows: NewsCsvRow[] = [];
  for (const filePath of paths) {
    try {
      const content = await fs.readFile(filePath, "utf-8");
      const rows = parseNewsDataCsv(content);
      allRows.push(...rows);
    } catch (error) {
      const enoent =
        error instanceof Error &&
        "code" in error &&
        (error as NodeJS.ErrnoException).code === "ENOENT";
      if (!enoent) throw error;
    }
  }
  return allRows;
}

export async function loadExperimentalNewsmap(): Promise<ExperimentalTimelineResult> {
  const secaErrors: Partial<Record<ExperimentalTimelineKey, string>> = {};
  const secaTimelines: Partial<Record<ExperimentalTimelineKey, ExperimentalTimeline>> = {};
  for (const key of ["30d", "7d", "3d"] as const) {
    try {
      const timeline = await loadSecaTimelineBatches(key);
      if (timeline) secaTimelines[key] = timeline;
    } catch (error) {
      secaErrors[key] = error instanceof Error ? error.message : "Unknown SECA loader error";
    }
  }
  if (secaTimelines["30d"] || secaTimelines["7d"] || secaTimelines["3d"]) {
    return {
      mode: "timeline",
      selectedKey: secaTimelines["30d"] ? "30d" : secaTimelines["7d"] ? "7d" : "3d",
      timelines: secaTimelines,
    };
  }

  try {
    const rows = await readNewsDataFiles();
    if (!rows.length) {
      throw new Error("No rows found in results/data or results/backup_data news_data.csv");
    }
    const batches = buildDailyBatches(rows);
    if (!batches.length) {
      throw new Error("No valid timestamped rows found for daily batches");
    }
    return {
      mode: "timeline",
      selectedKey: "30d",
      timelines: {
        "30d": {
          totalBatches: batches.length,
          selectedIndex: batches.length - 1,
          batches,
        },
      },
    };
  } catch (csvError) {
    const csvReason = csvError instanceof Error ? csvError.message : "Unknown CSV loader error";
    const secaReasons = (["30d", "7d", "3d"] as const)
      .map((key) => (secaErrors[key] ? `${key}: ${secaErrors[key]}` : null))
      .filter((value): value is string => Boolean(value));
    const reason = secaReasons.length
      ? `SECA timeline unavailable (${secaReasons.join("; ")}); CSV fallback failed (${csvReason})`
      : csvReason;
    return {
      mode: "fallback",
      reason,
    };
  }
}
