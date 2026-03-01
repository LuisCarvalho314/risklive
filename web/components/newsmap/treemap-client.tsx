"use client";

import { ParentSize } from "@visx/responsive";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { TreemapCanvas } from "@/components/newsmap/treemap-canvas";
import { TreemapNode } from "@/lib/dashboard";
import { defaultTuning, treemapLabelColors, treemapPalettes } from "@/lib/treemap/config";
import {
  ancestorsOf,
  buildEmphasisSet,
  buildFilteredTree,
  buildWeightedTree,
  findSubtree,
  indexTree
} from "@/lib/treemap/focus";
import { normalizeToNewsmapTree } from "@/lib/treemap/normalize";

type Meta = NonNullable<TreemapNode["meta"]>;

type FlagFilter = "All" | "Red" | "Yellow";
type LayoutMode = "squarify" | "binary";
type SourceRef = { id: string; title?: string; url: string | null; isUrl: boolean };
const TOOLTIP_LEAVE_GRACE_MS = 0;

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const clean = hex.trim().replace("#", "");
  const full =
    clean.length === 3
      ? clean
          .split("")
          .map((char) => `${char}${char}`)
          .join("")
      : clean;
  const value = Number.parseInt(full, 16);
  if (Number.isNaN(value)) return { r: 0, g: 0, b: 0 };
  return { r: (value >> 16) & 255, g: (value >> 8) & 255, b: value & 255 };
}

function mixWithWhite(hex: string, amount: number): string {
  const clamped = Math.max(0, Math.min(1, amount));
  const { r, g, b } = hexToRgb(hex);
  const mix = (channel: number) => Math.round(channel + (255 - channel) * clamped);
  return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`;
}

function applyPaletteToHierarchy(
  root: TreemapNode,
  palette: string[],
  baseFillColor: string,
  singleColorMode = false
): TreemapNode {
  if (!palette.length) return root;
  const representativeColor =
    palette[Math.floor(palette.length / 2)] ?? palette[0] ?? baseFillColor;

  const applyNode = (node: TreemapNode, depth: number, categoryColor: string | null, indexInParent: number): TreemapNode => {
    const fallbackCategoryColor = categoryColor ?? (singleColorMode ? representativeColor : palette[indexInParent % palette.length] ?? baseFillColor);
    const nextCategoryColor =
      depth === 1
        ? singleColorMode
          ? representativeColor
          : palette[indexInParent % palette.length] ?? baseFillColor
        : fallbackCategoryColor;

    let color = node.itemStyle?.color;
    if (depth === 0) color = "transparent";
    else if (depth === 1) color = nextCategoryColor;
    else if (depth === 2) color = mixWithWhite(nextCategoryColor, 0.24);
    else color = mixWithWhite(nextCategoryColor, 0.34);

    const children = node.children?.map((child, childIndex) =>
      applyNode(child, depth + 1, nextCategoryColor, childIndex)
    );

    return {
      ...node,
      itemStyle: { ...(node.itemStyle ?? {}), color },
      ...(children ? { children } : {}),
    };
  };

  return applyNode(root, 0, null, 0);
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

export function TreemapClient({
  data,
  preserveHierarchy = false,
  weightModeOverride,
  experimentalInteractions = false,
  singleHierarchyColor = false,
  compactControls = false,
  controlHint,
}: {
  data: TreemapNode;
  preserveHierarchy?: boolean;
  weightModeOverride?: "leafCount" | "value";
  experimentalInteractions?: boolean;
  singleHierarchyColor?: boolean;
  compactControls?: boolean;
  controlHint?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  const [flagFilter, setFlagFilter] = useState<FlagFilter>("All");
  const [focusId, setFocusId] = useState<string>("root::newsmap");
  const [tooltip, setTooltip] = useState<{ x: number; y: number; node: TreemapNode } | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ left: number; top: number } | null>(null);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("binary");
  const [themeId, setThemeId] = useState<string>("light");
  const [isDark, setIsDark] = useState<boolean>(true);
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<string[]>([]);
  const [showSourceList, setShowSourceList] = useState<boolean>(false);
  const [tooltipHovered, setTooltipHovered] = useState<boolean>(false);
  const [tooltipPinnedUntil, setTooltipPinnedUntil] = useState<number>(0);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const tooltipHideTimerRef = useRef<number | null>(null);

  const labelColor = useMemo(() => {
    if (themeId.startsWith("catppuccin-")) return "auto";
    return treemapLabelColors[themeId] ?? treemapLabelColors.default;
  }, [themeId]);

  const tuning = useMemo(
    () => ({
      ...defaultTuning,
      tileAlgorithmRoot: layoutMode,
      tileAlgorithmCategory: layoutMode,
      tileAlgorithmTopic: layoutMode,
      tileAlgorithmLeaf: layoutMode,
      labelColor,
      allowMidWordWrap: preserveHierarchy,
      ...(weightModeOverride ? { weightMode: weightModeOverride } : {}),
    }),
    [layoutMode, weightModeOverride, labelColor, preserveHierarchy]
  );

  useEffect(() => {
    const root = document.documentElement;
    const getTheme = () =>
      root.dataset.theme || (root.classList.contains("dark") ? "dark" : "light");
    const nextTheme = getTheme();
    setThemeId(nextTheme);
    setIsDark(root.classList.contains("dark"));

    const observer = new MutationObserver(() => {
      setThemeId(getTheme());
      setIsDark(root.classList.contains("dark"));
    });
    observer.observe(root, { attributes: true, attributeFilter: ["data-theme", "class"] });
    return () => observer.disconnect();
  }, []);

  const palette = useMemo(() => {
    return treemapPalettes[themeId] ?? treemapPalettes.default;
  }, [themeId]);

  const normalizedRoot = useMemo(() => {
    if (!preserveHierarchy) return normalizeToNewsmapTree(data, tuning, palette);
    return applyPaletteToHierarchy(data, palette, tuning.baseFillColor, singleHierarchyColor);
  }, [data, tuning, palette, preserveHierarchy, singleHierarchyColor]);
  const treeIndex = useMemo(() => indexTree(normalizedRoot), [normalizedRoot]);

  const focusPath = useMemo(() => {
    if (!treeIndex.byId.has(focusId)) return ancestorsOf("root::newsmap", treeIndex.parentById);
    return ancestorsOf(focusId, treeIndex.parentById);
  }, [focusId, treeIndex]);
  const emphasized = useMemo(
    () => buildEmphasisSet({ focusId, flagFilter, treeIndex }),
    [focusId, flagFilter, treeIndex]
  );

  const categories = useMemo(() => {
    if (preserveHierarchy) return [];
    const children = normalizedRoot.children ?? [];
    return children
      .filter((node) => node.id?.startsWith("cat::"))
      .map((node) => ({
        id: node.id ?? "",
        name: node.name || "Category",
        color: node.itemStyle?.color ?? defaultTuning.baseFillColor,
      }));
  }, [normalizedRoot, preserveHierarchy]);

  useEffect(() => {
    if (!categories.length) {
      setSelectedCategoryIds([]);
      return;
    }
    setSelectedCategoryIds((prev) => {
      if (!prev.length) return categories.map((c) => c.id);
      const known = new Set(categories.map((c) => c.id));
      const filtered = prev.filter((id) => known.has(id));
      return filtered.length ? filtered : categories.map((c) => c.id);
    });
  }, [categories]);

  const selectedCategorySet = useMemo(
    () => new Set(selectedCategoryIds),
    [selectedCategoryIds]
  );

  const selectedCategorySlugs = useMemo(() => {
    return new Set(
      selectedCategoryIds
        .map((id) => id.split("cat::")[1] ?? "")
        .filter(Boolean)
    );
  }, [selectedCategoryIds]);

  const getCategoryTextColor = useCallback((hex: string) => {
    const cleaned = hex.trim().replace("#", "");
    const full =
      cleaned.length === 3
        ? cleaned.split("").map((c) => c + c).join("")
        : cleaned;
    if (full.length !== 6) return "#0b0b0b";
    const num = parseInt(full, 16);
    const r = (num >> 16) & 255;
    const g = (num >> 8) & 255;
    const b = num & 255;
    const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    return luminance > 0.6 ? "#0b0b0b" : "#f8fafc";
  }, []);

  const getCategorySlugFromId = useCallback((id: string) => {
    if (id.startsWith("cat::")) return id.split("cat::")[1] ?? "";
    if (id.startsWith("topic::")) {
      const parts = id.split("topic::")[1]?.split("::") ?? [];
      return parts[0] ?? "";
    }
    if (id.startsWith("leaf::")) {
      const parts = id.split("leaf::")[1]?.split("::") ?? [];
      return parts[0] ?? "";
    }
    return "";
  }, []);

  const focusRoot = useMemo(() => {
    if (focusId === "root::newsmap") return normalizedRoot;
    return findSubtree(normalizedRoot, focusId) ?? normalizedRoot;
  }, [focusId, normalizedRoot]);

  const categoryFilteredRoot = useMemo(() => {
    const total = categories.length;
    if (!total || selectedCategorySet.size === total) return focusRoot;

    const focusSlug = getCategorySlugFromId(focusRoot.id ?? "");
    if (focusSlug && !selectedCategorySlugs.has(focusSlug)) {
      return { ...focusRoot, children: [] };
    }

    if (focusRoot.id === "root::newsmap") {
      const filteredChildren = (focusRoot.children ?? []).filter((node) =>
        selectedCategorySet.has(node.id ?? "")
      );
      return { ...focusRoot, children: filteredChildren };
    }

    return focusRoot;
  }, [
    categories.length,
    focusRoot,
    getCategorySlugFromId,
    selectedCategorySet,
    selectedCategorySlugs,
  ]);

  useEffect(() => {
    if (focusId === "root::newsmap") return;
    const focusSlug = getCategorySlugFromId(focusRoot.id ?? "");
    if (focusSlug && !selectedCategorySlugs.has(focusSlug)) {
      setFocusId("root::newsmap");
    }
  }, [focusId, focusRoot, getCategorySlugFromId, selectedCategorySlugs]);

  const finalRoot = useMemo(() => {
    if (preserveHierarchy || flagFilter === "All") return categoryFilteredRoot;
    return buildFilteredTree(categoryFilteredRoot, emphasized);
  }, [categoryFilteredRoot, emphasized, flagFilter, preserveHierarchy]);

  const weightedRoot = useMemo(
    () => buildWeightedTree(finalRoot, emphasized, tuning),
    [finalRoot, emphasized, tuning]
  );

  useLayoutEffect(() => {
    if (!tooltip) {
      setTooltipPos(null);
      return;
    }
    const container = containerRef.current;
    const tip = tooltipRef.current;
    if (!container || !tip) return;

    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;
    const tipWidth = tip.offsetWidth;
    const tipHeight = tip.offsetHeight;
    const gap = 12;
    const edge = 8;

    let left = tooltip.x + gap;
    let top = tooltip.y + gap;

    if (left + tipWidth + edge > containerWidth) {
      left = tooltip.x - tipWidth - gap;
    }
    if (top + tipHeight + edge > containerHeight) {
      top = tooltip.y - tipHeight - gap;
    }

    left = Math.max(edge, Math.min(left, containerWidth - tipWidth - edge));
    top = Math.max(edge, Math.min(top, containerHeight - tipHeight - edge));

    setTooltipPos({ left, top });
  }, [tooltip]);

  useEffect(() => {
    setShowSourceList(false);
    setTooltipPinnedUntil(0);
  }, [tooltip?.node?.id]);

  useEffect(() => {
    return () => {
      if (tooltipHideTimerRef.current != null) {
        window.clearTimeout(tooltipHideTimerRef.current);
      }
    };
  }, []);

  const isTooltipPinned = useCallback(() => tooltipPinnedUntil > Date.now(), [tooltipPinnedUntil]);

  const scheduleTooltipClose = useCallback(
    (delayMs: number) => {
      if (tooltipHideTimerRef.current != null) {
        window.clearTimeout(tooltipHideTimerRef.current);
      }
      tooltipHideTimerRef.current = window.setTimeout(() => {
        if (!tooltipHovered && !isTooltipPinned()) {
          setTooltip(null);
          setShowSourceList(false);
        }
      }, delayMs);
    },
    [tooltipHovered, isTooltipPinned]
  );

  const setTooltipWithHoverGrace = useCallback(
    (
      value: { x: number; y: number; node: TreemapNode } | null,
      options?: { pinMs?: number; showSources?: boolean }
    ) => {
      if (tooltipHideTimerRef.current != null) {
        window.clearTimeout(tooltipHideTimerRef.current);
        tooltipHideTimerRef.current = null;
      }
      if (value) {
        if (!options?.pinMs && isTooltipPinned()) {
          if (tooltip?.node?.id && value.node.id && tooltip.node.id !== value.node.id) {
            setTooltipPinnedUntil(0);
          } else {
            return;
          }
        }
        setTooltip(value);
        if (options?.pinMs && options.pinMs > 0) {
          setTooltipPinnedUntil(Date.now() + options.pinMs);
        }
        if (options?.showSources === true) {
          setShowSourceList(true);
        }
        return;
      }
      scheduleTooltipClose(TOOLTIP_LEAVE_GRACE_MS);
    },
    [isTooltipPinned, scheduleTooltipClose, tooltip?.node?.id]
  );

  useEffect(() => {
    if (!tooltip || tooltipHovered) return;
    if (!isTooltipPinned()) return;
    const remaining = Math.max(0, tooltipPinnedUntil - Date.now());
    const timer = window.setTimeout(() => {
        if (!tooltipHovered && !isTooltipPinned()) {
          setTooltip(null);
          setShowSourceList(false);
        }
      }, remaining + 20);
    return () => window.clearTimeout(timer);
  }, [tooltip, tooltipHovered, tooltipPinnedUntil, isTooltipPinned]);

  const controlHeightClass = compactControls ? "h-7" : "h-8";
  const controlTextClass = compactControls ? "text-[10px]" : "text-[11px]";
  const controlPadClass = compactControls ? "px-2" : "px-3";
  const controlGroupGapClass = compactControls ? "gap-1.5" : "gap-2";
  const controlStripGapClass = compactControls ? "gap-2" : "gap-3";

  const buttonClass = useCallback(
    (active: boolean) =>
    [
      "inline-flex items-center justify-center rounded-full font-semibold uppercase tracking-[0.14em] transition-colors",
      controlHeightClass,
      controlPadClass,
      controlTextClass,
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
      active
        ? "bg-accent text-foreground"
        : "bg-muted/60 text-muted-foreground hover:bg-accent/40 hover:text-foreground",
    ].join(" "),
    [controlHeightClass, controlPadClass, controlTextClass]
  );

  const modeButtonClass = useCallback(
    (active: boolean) =>
      [
        "inline-flex items-center justify-center rounded-full font-semibold uppercase tracking-[0.14em] transition-colors",
        controlHeightClass,
        controlPadClass,
        controlTextClass,
        "border border-border",
        active
          ? "bg-foreground text-background"
          : "bg-transparent text-muted-foreground hover:bg-muted/40 hover:text-foreground",
      ].join(" "),
    [controlHeightClass, controlPadClass, controlTextClass]
  );

  const breadcrumbNodes = useMemo(() => {
    const ids = focusPath.length ? focusPath : ["root::newsmap"];
    return ids.map((id) => treeIndex.byId.get(id)).filter(Boolean) as TreemapNode[];
  }, [focusPath, treeIndex]);

  const tooltipSourceRefs = useMemo(() => {
    const refs = tooltip?.node?.meta?.sourceRefs;
    if (!Array.isArray(refs) || refs.length === 0) return [] as SourceRef[];
    const parsed: SourceRef[] = [];
    for (const entry of refs) {
      const id = (entry?.id ?? "").trim();
      if (!id) continue;
      const title = typeof entry?.title === "string" && entry.title.trim() ? entry.title.trim() : undefined;
      const url = typeof entry?.url === "string" && entry.url.trim() ? entry.url.trim() : null;
      const isUrl = typeof entry?.isUrl === "boolean" ? entry.isUrl : Boolean(url);
      parsed.push({ id, title, url, isUrl });
    }
    return parsed;
  }, [tooltip?.node?.meta?.sourceRefs]);

  const visibleSourceRefs = useMemo(() => tooltipSourceRefs.slice(0, 50), [tooltipSourceRefs]);

  return (
    <div className="relative flex h-full min-h-0 w-full flex-col overflow-hidden">
      <div
        className={[
          "sticky top-0 z-10 border-b border-border/60 bg-background/95 backdrop-blur-sm",
          compactControls ? "px-2 py-1.5" : "p-2",
        ].join(" ")}
      >
        <div className={["flex min-w-0 items-center", compactControls ? "gap-1.5" : "gap-2"].join(" ")}>
          <div className="newsmap-control-scroll min-w-0 flex-1 overflow-x-auto pr-2">
            <div className={["inline-flex items-center whitespace-nowrap", controlStripGapClass].join(" ")}>
              <div className={["inline-flex items-center", controlGroupGapClass].join(" ")}>
                <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Layout</span>
              </div>
              <div className={["inline-flex items-center", controlGroupGapClass].join(" ")}>
                <button
                  type="button"
                  onClick={() => setLayoutMode("binary")}
                  className={modeButtonClass(layoutMode === "binary")}
                >
                  Binary
                </button>
                <button
                  type="button"
                  onClick={() => setLayoutMode("squarify")}
                  className={modeButtonClass(layoutMode === "squarify")}
                >
                  Squarify
                </button>
              </div>

              {preserveHierarchy ? null : (
                <>
                  <span className="h-5 w-px bg-border/70" />

                  <div className={["inline-flex items-center", controlGroupGapClass].join(" ")}>
                    <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Risk</span>
                  </div>
                  <div className={["inline-flex items-center", controlGroupGapClass].join(" ")}>
                    <button
                      type="button"
                      onClick={() => setFlagFilter("All")}
                      className={[
                        ...buttonClass(flagFilter === "All").split(" "),
                        flagFilter === "All" ? "ring-2 ring-accent/60 ring-offset-2 ring-offset-background" : "",
                      ].join(" ").trim()}
                    >
                      All
                    </button>
                    <button
                      type="button"
                      onClick={() => setFlagFilter("Red")}
                      className={buttonClass(flagFilter === "Red")}
                    >
                      High Risk
                    </button>
                    <button
                      type="button"
                      onClick={() => setFlagFilter("Yellow")}
                      className={buttonClass(flagFilter === "Yellow")}
                    >
                      Medium Risk
                    </button>
                  </div>
                </>
              )}

              <span className="h-5 w-px bg-border/70" />

              <div className={["inline-flex items-center", controlGroupGapClass].join(" ")}>
                <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Path</span>
              </div>
              <div className={["relative inline-flex items-center", controlGroupGapClass].join(" ")}>
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
                        "inline-flex items-center justify-center whitespace-nowrap rounded-full font-semibold transition-colors",
                        controlHeightClass,
                        controlPadClass,
                        controlTextClass,
                        isLast
                          ? "bg-accent text-foreground"
                          : "bg-muted/60 text-muted-foreground hover:bg-accent/40 hover:text-foreground",
                      ].join(" ")}
                      title={label}
                    >
                      <span className={compactControls ? "max-w-[9rem] truncate" : undefined}>{label}</span>
                    </button>
                  );
                })}
              </div>

              {preserveHierarchy ? null : (
                <>
                  <span className="h-5 w-px bg-border/70" />

                  <div className={["inline-flex items-center", controlGroupGapClass].join(" ")}>
                    <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Categories</span>
                  </div>
                  <div className={["inline-flex min-w-0 items-center", controlGroupGapClass].join(" ")}>
                    <button
                      type="button"
                      onClick={() => {
                        setFocusId("root::newsmap");
                        setSelectedCategoryIds(categories.map((c) => c.id));
                      }}
                      className={[
                        "inline-flex items-center justify-center whitespace-nowrap rounded-full font-semibold uppercase tracking-[0.14em] transition-colors",
                        controlHeightClass,
                        controlPadClass,
                        controlTextClass,
                        "border border-border",
                        selectedCategorySet.size === categories.length
                          ? "bg-foreground text-background"
                          : "bg-transparent text-muted-foreground hover:bg-muted/40 hover:text-foreground",
                      ].join(" ")}
                      title="All categories"
                    >
                      All Categories
                    </button>
                    {categories.map((category) => (
                      <button
                        key={category.id}
                        type="button"
                        onClick={() => {
                          setSelectedCategoryIds((prev) => {
                            const next = new Set(prev);
                            if (next.has(category.id)) next.delete(category.id);
                            else next.add(category.id);
                            if (!next.size) return categories.map((c) => c.id);
                            return Array.from(next);
                          });
                        }}
                        className={[
                          "inline-flex items-center justify-center whitespace-nowrap rounded-full font-semibold uppercase tracking-[0.14em] transition",
                          controlHeightClass,
                          controlPadClass,
                          controlTextClass,
                        ].join(" ")}
                        style={{
                          backgroundColor: category.color,
                          color: getCategoryTextColor(category.color),
                          opacity: selectedCategorySet.has(category.id) ? 1 : 0.35,
                          outline: selectedCategorySet.has(category.id)
                            ? "2px solid rgba(0,0,0,0.15)"
                            : "1px dashed rgba(0,0,0,0.2)",
                          outlineOffset: 1,
                        }}
                        title={category.name}
                      >
                        {category.name}
                      </button>
                    ))}
                  </div>
                </>
              )}
              {controlHint ? (
                <>
                  <span className="h-5 w-px bg-border/70" />
                  <span className="pointer-events-none text-[10px] text-muted-foreground">{controlHint}</span>
                </>
              ) : null}
            </div>
          </div>

          <div className="flex-none">
            <button
              type="button"
              onClick={() => {
                setFocusId("root::newsmap");
                setFlagFilter("All");
                setLayoutMode("binary");
                setSelectedCategoryIds(categories.map((c) => c.id));
              }}
              className={[
                "inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-full font-semibold uppercase tracking-[0.14em] transition-colors",
                controlHeightClass,
                compactControls ? "px-2.5" : "px-3",
                controlTextClass,
                "border border-border",
                focusId === "root::newsmap" && flagFilter === "All"
                  ? "bg-foreground text-background"
                  : "bg-background/80 text-muted-foreground backdrop-blur hover:bg-muted/60 hover:text-foreground",
              ].join(" ")}
              title="Reset all filters"
              aria-label="Reset all filters"
            >
              Reset
            </button>
          </div>
        </div>
      </div>

      <div ref={containerRef} className="relative min-h-0 flex-1 overflow-hidden">
        <ParentSize>
          {({ width, height }) => {
            if (width <= 0 || height <= 0) return null;
            return (
              <TreemapCanvas
                width={width}
                height={height}
                root={weightedRoot}
                tuning={tuning}
                containerRef={containerRef}
                setFocusId={setFocusId}
                setTooltip={setTooltipWithHoverGrace}
                experimentalInteractions={experimentalInteractions}
              />
            );
          }}
        </ParentSize>
      </div>

      {tooltip ? (
        <div
          ref={tooltipRef}
          className="pointer-events-auto absolute z-20 max-w-xs rounded-lg border border-border bg-popover p-3 text-xs text-foreground shadow-lg"
          style={tooltipPos ? { left: tooltipPos.left, top: tooltipPos.top } : undefined}
          onMouseEnter={() => {
            if (tooltipHideTimerRef.current != null) {
              window.clearTimeout(tooltipHideTimerRef.current);
              tooltipHideTimerRef.current = null;
            }
            setTooltipHovered(true);
          }}
          onMouseLeave={() => {
            setTooltipHovered(false);
            if (isTooltipPinned()) {
              const remaining = Math.max(0, tooltipPinnedUntil - Date.now());
              scheduleTooltipClose(remaining + TOOLTIP_LEAVE_GRACE_MS);
              return;
            }
            scheduleTooltipClose(TOOLTIP_LEAVE_GRACE_MS);
          }}
        >
          {(() => {
            const meta = (tooltip.node.meta ?? {}) as Meta;
            const title = meta.title || tooltip.node.name || "";
            const category = meta.category || "";
            const topic = meta.topicLabel || meta.topic || "";
            const flag = meta.alertFlag || "";
            const time = formatTimestamp(meta.timestamp);
            const summary = meta.shortSummary || meta.description || "";
            return (
              <div className="space-y-1">
                <div className="text-sm font-semibold">{title}</div>
                {category ? <div className="text-muted-foreground">{category}</div> : null}
                {topic ? <div className="text-muted-foreground">{topic}</div> : null}
                {flag ? (
                  <div className="pt-1 text-[11px] font-semibold">
                    {flag}{meta.alertReason ? ` — ${meta.alertReason}` : ""}
                  </div>
                ) : null}
                {time ? <div className="text-[11px] text-muted-foreground">{time}</div> : null}
                {summary ? <div className="pt-2 text-[11px] text-foreground/90">{summary}</div> : null}
                {tooltipSourceRefs.length > 0 && !experimentalInteractions ? (
                  <div className="pt-2">
                    <button
                      type="button"
                      onClick={() => {
                        setShowSourceList((value) => !value);
                      }}
                      className="inline-flex h-7 items-center rounded-full border border-border bg-background px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground hover:text-foreground"
                    >
                      Sources ({tooltipSourceRefs.length})
                    </button>
                  </div>
                ) : null}
                {tooltipSourceRefs.length > 0 && experimentalInteractions ? (
                  <div className="pt-2">
                    <span className="inline-flex h-7 items-center rounded-full border border-border bg-background px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                      Sources ({tooltipSourceRefs.length})
                    </span>
                  </div>
                ) : null}
                {showSourceList && visibleSourceRefs.length > 0 ? (
                  <div className="mt-2 space-y-1 rounded-md border border-border bg-background/90 p-2">
                    <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                      Source List
                    </div>
                    <div className="max-h-40 space-y-1 overflow-y-auto">
                      {visibleSourceRefs.map((source) =>
                        source.url ? (
                          <a
                            key={source.id}
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                            className="block rounded border border-border/70 px-2 py-1 hover:bg-accent/20"
                            title={source.url}
                          >
                            <div className="truncate text-[11px] font-medium text-foreground">
                              {source.title ?? source.id}
                            </div>
                            <div className="truncate text-[10px] text-muted-foreground">{source.url}</div>
                          </a>
                        ) : (
                          <div
                            key={source.id}
                            className="flex items-center justify-between gap-2 rounded border border-border/70 px-2 py-1"
                            title={source.id}
                          >
                            <div className="min-w-0">
                              <div className="truncate text-[11px] font-medium text-foreground">
                                {source.title ?? source.id}
                              </div>
                              <div className="truncate text-[10px] text-muted-foreground">{source.id}</div>
                            </div>
                            <button
                              type="button"
                              onClick={() => {
                                if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
                                  void navigator.clipboard.writeText(source.id);
                                }
                              }}
                              className="inline-flex h-6 items-center rounded border border-border px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground hover:text-foreground"
                            >
                              Copy
                            </button>
                          </div>
                        )
                      )}
                    </div>
                    {tooltipSourceRefs.length > visibleSourceRefs.length ? (
                      <div className="text-[10px] text-muted-foreground">
                        +{tooltipSourceRefs.length - visibleSourceRefs.length} more sources not shown
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })()}
        </div>
      ) : null}
    </div>
  );
}
