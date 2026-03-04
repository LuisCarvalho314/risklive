"use client";

import { useMemo, useState } from "react";

import { TreemapClient } from "@/components/newsmap/treemap-client";
import type { TreemapNode } from "@/lib/dashboard";
import {
  applyExperimentalSizeMetric,
} from "@/lib/newsmap-experimental-shared";
import type {
  ExperimentalSizeDirection,
  ExperimentalSizeMetric,
  ExperimentalTimelineKey,
  ExperimentalTimelineResult,
} from "@/lib/newsmap-experimental-shared";

type Props = {
  timelineResult: ExperimentalTimelineResult;
  fallbackTree: TreemapNode;
};

export function TreemapExperimentalClient({ timelineResult, fallbackTree }: Props) {
  const isTimeline = timelineResult.mode === "timeline";
  const initialKey: ExperimentalTimelineKey = isTimeline ? timelineResult.selectedKey : "30d";
  const [selectedTimelineKey, setSelectedTimelineKey] = useState<ExperimentalTimelineKey>(initialKey);
  const [selectedIndexes, setSelectedIndexes] = useState<Partial<Record<ExperimentalTimelineKey, number>>>(() => {
    if (!isTimeline) return {};
    return {
      "30d": timelineResult.timelines["30d"]?.selectedIndex ?? 0,
      "7d": timelineResult.timelines["7d"]?.selectedIndex ?? 0,
      "3d": timelineResult.timelines["3d"]?.selectedIndex ?? 0,
    };
  });
  const [selectedMetric, setSelectedMetric] = useState<ExperimentalSizeMetric>("mappedSourceCount");
  const [sizeDirection, setSizeDirection] = useState<ExperimentalSizeDirection>("highToLarge");

  const availableTimelineKeys = useMemo(() => {
    if (!isTimeline) return [] as ExperimentalTimelineKey[];
    const keys: ExperimentalTimelineKey[] = [];
    if (timelineResult.timelines["30d"]) keys.push("30d");
    if (timelineResult.timelines["7d"]) keys.push("7d");
    if (timelineResult.timelines["3d"]) keys.push("3d");
    return keys;
  }, [isTimeline, timelineResult]);

  const activeTimelineKey: ExperimentalTimelineKey | null = useMemo(() => {
    if (!isTimeline) return null;
    if (timelineResult.timelines[selectedTimelineKey]) return selectedTimelineKey;
    return availableTimelineKeys[0] ?? null;
  }, [availableTimelineKeys, isTimeline, selectedTimelineKey, timelineResult]);

  const timelineMeta = useMemo(() => {
    if (!isTimeline || !activeTimelineKey) return null;
    const activeTimeline = timelineResult.timelines[activeTimelineKey];
    if (!activeTimeline) return null;
    const batches = activeTimeline.batches;
    const selectedIndex = selectedIndexes[activeTimelineKey] ?? activeTimeline.selectedIndex;
    const safeIndex = Math.max(0, Math.min(selectedIndex, batches.length - 1));
    const batch = batches[safeIndex];
    return {
      activeTimelineKey,
      safeIndex,
      batch,
      total: batches.length,
    };
  }, [activeTimelineKey, isTimeline, selectedIndexes, timelineResult]);

  const sliderMarkers = useMemo(() => {
    if (!timelineMeta) return [];
    const batches = isTimeline && activeTimelineKey ? timelineResult.timelines[activeTimelineKey]?.batches ?? [] : [];
    if (!batches.length) return [];

    const latestDate = new Date(`${batches[batches.length - 1].day}T00:00:00Z`);
    const fallbackIndices = [0, Math.floor((batches.length - 1) / 2), batches.length - 1];
    const markerIndices = Array.from(new Set(fallbackIndices)).sort((a, b) => a - b);

    return markerIndices
      .map((index) => {
        const batch = batches[index];
        if (!batch) return null;
        const dayDate = new Date(`${batch.day}T00:00:00Z`);
        const diffDays = Number.isFinite(dayDate.getTime()) && Number.isFinite(latestDate.getTime())
          ? Math.max(0, Math.round((latestDate.getTime() - dayDate.getTime()) / 86_400_000))
          : 0;
        const leftPct = batches.length > 1 ? (index / (batches.length - 1)) * 100 : 0;
        return {
          index,
          day: batch.day,
          diffLabel: `${diffDays}d`,
          leftPct,
        };
      })
      .filter((value): value is { index: number; day: string; diffLabel: string; leftPct: number } => Boolean(value));
  }, [activeTimelineKey, isTimeline, timelineMeta, timelineResult]);

  const tree = timelineMeta?.batch.tree ?? fallbackTree;
  const renderedTree = useMemo(
    () => (isTimeline ? applyExperimentalSizeMetric(tree, selectedMetric, sizeDirection) : tree),
    [isTimeline, selectedMetric, sizeDirection, tree]
  );

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden">
      <div className="shrink-0 rounded-xl border border-border bg-background/95 px-2.5 py-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center rounded-full border border-amber-500/60 bg-amber-500/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-700 dark:text-amber-300">
            Experimental
          </span>
          {isTimeline ? (
            <>
              <span className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Window
              </span>
              <div className="inline-flex rounded-full border border-border bg-muted/40 p-0.5">
                {(["30d", "7d", "3d"] as const).map((key) => {
                  const isAvailable = Boolean(timelineResult.timelines[key]);
                  return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => {
                      if (isAvailable) setSelectedTimelineKey(key);
                    }}
                    disabled={!isAvailable}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                      activeTimelineKey === key
                        ? "bg-background text-foreground shadow-sm"
                        : isAvailable
                          ? "text-muted-foreground hover:text-foreground"
                          : "cursor-not-allowed text-muted-foreground/50"
                    }`}
                  >
                    {key === "7d" ? "7 days" : key === "3d" ? "3 days" : "30 days"}
                  </button>
                  );
                })}
              </div>
            </>
          ) : null}
          {isTimeline ? (
            <>
              <span className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Size metric
              </span>
              <div className="inline-flex flex-wrap rounded-full border border-border bg-muted/40 p-0.5">
                {(
                  [
                    [
                      "mappedSourceCount",
                      "Mapped Sources",
                      "How many articles this node currently captures. Emphasizes coverage and volume.",
                    ],
                    [
                      "combinedError",
                      "Combined Error",
                      "Overall drift signal combining alpha, beta, and word-importance error. Emphasizes total instability.",
                    ],
                    [
                      "wordImportanceError",
                      "Word-Imp Error",
                      "How much important vocabulary shifted from expectation. Emphasizes topical vocabulary drift.",
                    ],
                    [
                      "alphaError",
                      "Alpha Error",
                      "How far word-strength patterns moved from baseline. Emphasizes intensity changes.",
                    ],
                    [
                      "betaError",
                      "Beta Error",
                      "How far word-eligibility/fit moved from baseline. Emphasizes boundary changes in topic fit.",
                    ],
                    [
                      "triggeredScore",
                      "Triggered",
                      "Highlights branches flagged for reconstruction. Emphasizes trigger status over pure size.",
                    ],
                    [
                      "composite",
                      "Composite",
                      "Fallback blended score for legacy batches without full diagnostics. Emphasizes balanced overview.",
                    ],
                  ] as Array<[ExperimentalSizeMetric, string, string]>
                ).map(([metric, label, description]) => (
                  <div key={metric} className="group relative">
                    <button
                      type="button"
                      onClick={() => setSelectedMetric(metric)}
                      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 ${
                        selectedMetric === metric
                          ? "bg-background text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {label}
                    </button>
                    <span className="pointer-events-none absolute left-1/2 top-full z-20 mt-1 w-52 -translate-x-1/2 rounded-md border border-border bg-background/95 px-2 py-1 text-[10px] leading-tight text-muted-foreground opacity-0 shadow-md transition-opacity group-hover:opacity-100">
                      {description}
                    </span>
                  </div>
                ))}
              </div>
              <span className="ml-2 shrink-0 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Direction
              </span>
              <div className="inline-flex rounded-full border border-border bg-muted/40 p-0.5">
                {(
                  [
                    ["highToLarge", "High -> Large"],
                    ["highToSmall", "High -> Small"],
                  ] as Array<[ExperimentalSizeDirection, string]>
                ).map(([direction, label]) => (
                  <button
                    key={direction}
                    type="button"
                    onClick={() => setSizeDirection(direction)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                      sizeDirection === direction
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </>
          ) : null}
        </div>

        {isTimeline && timelineMeta ? (
          <div className="mt-2 flex min-w-0 items-center gap-2">
            <label
              htmlFor="newsmap-batch-slider"
              className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground"
            >
              Batch
            </label>
            <div className="min-w-0 flex-1">
              <input
                id="newsmap-batch-slider"
                type="range"
                min={0}
                max={Math.max(timelineMeta.total - 1, 0)}
                value={timelineMeta.safeIndex}
                onChange={(event) =>
                  setSelectedIndexes((prev) => ({
                    ...prev,
                    [timelineMeta.activeTimelineKey]: Number(event.target.value),
                  }))
                }
                className="min-w-0 w-full"
                aria-label="Select daily timeline batch"
              />
              {sliderMarkers.length ? (
                <div className="relative mt-1 h-4 text-[11px] text-muted-foreground">
                  {sliderMarkers.map((marker) => (
                    <span
                      key={marker.index}
                      className="absolute -translate-x-1/2 select-none whitespace-nowrap"
                      style={{ left: `${marker.leftPct}%` }}
                      title={marker.day}
                    >
                      {marker.diffLabel}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
            <p className="shrink-0 text-sm text-muted-foreground">
              {timelineMeta.safeIndex + 1}/{timelineMeta.total}
            </p>
            <p className="min-w-0 break-all text-sm text-muted-foreground" title={timelineMeta.batch.filename}>
              {timelineMeta.batch.day}
            </p>
          </div>
        ) : (
          <div className="mt-2 rounded-md border border-amber-400/50 bg-amber-50/60 px-2 py-1 text-xs text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
            Static experimental timeline unavailable. Using dashboard fallback data. Reason:{" "}
            {timelineResult.mode === "fallback" ? timelineResult.reason : "Unknown"}
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-hidden pt-2">
        <TreemapClient
          data={renderedTree}
          preserveHierarchy={isTimeline}
          weightModeOverride={isTimeline ? "value" : undefined}
          experimentalInteractions={isTimeline}
          singleHierarchyColor={isTimeline}
          compactControls={isTimeline}
          controlHint={isTimeline ? "Double click a tile to show sources." : undefined}
        />
      </div>
    </div>
  );
}
