import fs from "fs/promises";
import path from "path";

import type { OpsArtifact } from "@/lib/ops/types";

type ArtifactSeed = Pick<OpsArtifact, "id" | "path" | "required">;

const ARTIFACTS: ArtifactSeed[] = [
  { id: "news_data", path: "results/data/news_data.csv", required: true },
  { id: "news_data_llm", path: "results/data/news_data_with_llm_info.csv", required: true },
  { id: "topics", path: "results/data/df_with_response_and_topics.csv", required: true },
  { id: "report", path: "results/data/df_report.csv", required: true },
  { id: "dashboard_json", path: "results/web/dashboard.json", required: true },
  { id: "topic_run_metadata", path: "results/images/run_metadata.json", required: false },
  { id: "seca_manifest_30d", path: "results/web/newsmap/seca-light-30d/timeline_manifest.json", required: false },
  { id: "seca_manifest_7d", path: "results/web/newsmap/seca-light-7d/timeline_manifest.json", required: false },
  { id: "seca_manifest_3d", path: "results/web/newsmap/seca-light-3d/timeline_manifest.json", required: false }
];

function absoluteFor(relativePath: string): string {
  return path.join(process.cwd(), "..", ...relativePath.split("/"));
}

async function countCsvRows(filePath: string): Promise<number | null> {
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    const lines = raw
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (lines.length <= 1) return 0;
    return lines.length - 1;
  } catch {
    return null;
  }
}

type TimelineManifest = {
  files?: string[];
};

function isManifest(value: unknown): value is TimelineManifest {
  return typeof value === "object" && value !== null;
}

function safeResolveBatchPath(baseDir: string, filename: string): string | null {
  if (!filename || filename.includes("\u0000")) return null;
  const resolved = path.resolve(baseDir, filename);
  const normalizedBase = path.resolve(baseDir) + path.sep;
  return resolved.startsWith(normalizedBase) ? resolved : null;
}

async function discoverSecaBatchArtifacts(manifestArtifact: OpsArtifact): Promise<OpsArtifact[]> {
  if (!manifestArtifact.exists) return [];
  const manifestFullPath = absoluteFor(manifestArtifact.path);
  const baseDir = path.dirname(manifestFullPath);
  let payload: unknown;
  try {
    payload = JSON.parse(await fs.readFile(manifestFullPath, "utf-8"));
  } catch {
    return [];
  }
  if (!isManifest(payload) || !Array.isArray(payload.files)) return [];

  const prefix =
    manifestArtifact.id === "seca_manifest_7d"
      ? "seca_7d_batch_"
      : manifestArtifact.id === "seca_manifest_3d"
        ? "seca_3d_batch_"
        : "seca_30d_batch_";
  const relBase = manifestArtifact.path.split("/").slice(0, -1).join("/");
  const discovered: OpsArtifact[] = [];
  for (let index = 0; index < payload.files.length; index += 1) {
    const filename = typeof payload.files[index] === "string" ? payload.files[index] : "";
    const fullPath = safeResolveBatchPath(baseDir, filename);
    const relPath = `${relBase}/${filename}`;
    if (!fullPath) {
      discovered.push({
        id: `${prefix}${index}`,
        path: relPath,
        required: false,
        exists: false,
        modifiedAt: null,
        sizeBytes: 0,
        rowCount: null,
      });
      continue;
    }
    try {
      const stat = await fs.stat(fullPath);
      discovered.push({
        id: `${prefix}${index}`,
        path: relPath,
        required: false,
        exists: true,
        modifiedAt: stat.mtime.toISOString(),
        sizeBytes: stat.size,
        rowCount: null,
      });
    } catch (error) {
      const missing =
        error instanceof Error &&
        "code" in error &&
        (error as NodeJS.ErrnoException).code === "ENOENT";
      if (!missing) throw error;
      discovered.push({
        id: `${prefix}${index}`,
        path: relPath,
        required: false,
        exists: false,
        modifiedAt: null,
        sizeBytes: 0,
        rowCount: null,
      });
    }
  }
  return discovered;
}

export async function inspectArtifacts(): Promise<OpsArtifact[]> {
  const results: OpsArtifact[] = [];

  for (const artifact of ARTIFACTS) {
    const fullPath = absoluteFor(artifact.path);
    try {
      const stat = await fs.stat(fullPath);
      const rowCount = artifact.path.endsWith(".csv") ? await countCsvRows(fullPath) : null;
      results.push({
        ...artifact,
        exists: true,
        modifiedAt: stat.mtime.toISOString(),
        sizeBytes: stat.size,
        rowCount
      });
    } catch (error) {
      const missing =
        error instanceof Error &&
        "code" in error &&
        (error as NodeJS.ErrnoException).code === "ENOENT";
      if (!missing) throw error;
      results.push({
        ...artifact,
        exists: false,
        modifiedAt: null,
        sizeBytes: 0,
        rowCount: null
      });
    }
  }

  const secaManifests = results.filter(
    (artifact) =>
      artifact.id === "seca_manifest_30d" ||
      artifact.id === "seca_manifest_7d" ||
      artifact.id === "seca_manifest_3d"
  );
  for (const manifest of secaManifests) {
    const batches = await discoverSecaBatchArtifacts(manifest);
    results.push(...batches);
  }

  return results;
}
