export type TileAlgorithm = "squarify" | "binary" | "sliceDice" | "resquarify" | "slice" | "dice";

export type TreemapTuning = {
  /** Multiplier applied to non-emphasized node weights in `buildWeightedTree`. */
  epsilon: number;
  /** Area threshold for opacity ramp; `area <= minArea` starts at `minRectOpacity`. */
  minArea: number;
  /** Area span over which opacity ramps from `minRectOpacity` to 1. */
  opacityFadeRange: number;
  /** Lower bound for computed rectangle opacity after fade. */
  minRectOpacity: number;
  /** Fixed opacity override for category tiles (depth 1). */
  categoryRectOpacity: number;
  /** Fixed opacity override for topic tiles (depth 2). */
  topicRectOpacity: number;
  /** Fallback tile fill when node has no color. */
  baseFillColor: string;
  /** Stroke color for all tile borders. */
  rectStrokeColor: string;
  /** Preferred label color; `"auto"` uses contrast-based color. */
  labelColor: string;
  /** Letter spacing applied to category labels only. */
  labelLetterSpacing: string;
  /** Minimum font size for leaf labels (bounded sizing). */
  leafFontMin: number;
  /** Maximum font size for leaf labels (bounded sizing). */
  leafFontMax: number;
  /** Minimum font size for group labels (category/topic). */
  groupFontMin: number;
  /** Maximum font size for group labels (category/topic). */
  groupFontMax: number;
  /** Line-height multiplier for label layout. */
  lineHeight: number;
  /** Avg glyph width factor used for single-line size estimation. */
  avgGlyphWidthFactor: number;
  /** Height factor used for single-line size estimation. */
  textHeightFactor: number;
  /** Avg glyph width factor used for wrapping/truncation. */
  wrapGlyphWidthFactor: number;
  /** If true, wrapping may break inside words (character-level). */
  allowMidWordWrap: boolean;
  /** Base ratio for squarify/resquarify tiling. */
  squarifyRatio: number;
  /** `"screen"` derives ratio from current aspect; `"fixed"` uses `squarifyRatio`. */
  squarifyRatioMode: "fixed" | "screen";
  /** Multiplier applied to the computed squarify ratio. */
  squarifyRatioScale: number;
  /** Root-level tiling algorithm. */
  tileAlgorithmRoot: TileAlgorithm;
  /** Category-level tiling algorithm (depth 1). */
  tileAlgorithmCategory: TileAlgorithm;
  /** Topic-level tiling algorithm (depth 2). */
  tileAlgorithmTopic: TileAlgorithm;
  /** Leaf-level tiling algorithm (depth 3+). */
  tileAlgorithmLeaf: TileAlgorithm;
  /** Enable value sorting for binary tiler. */
  sortByValueForBinary: boolean;
  /** Sort order for binary tiler by parent depth. */
  binarySortOrderByDepth: {
    root: "asc" | "desc" | "none";
    category: "asc" | "desc" | "none";
    topic: "asc" | "desc" | "none";
    leaf: "asc" | "desc" | "none";
  };
  /** Enable value sorting for squarify/resquarify tilers. */
  sortByValueForSquarify: boolean;
  /** Sort order for squarify/resquarify by parent depth. */
  squarifySortOrderByDepth: {
    root: "asc" | "desc" | "none";
    category: "asc" | "desc" | "none";
    topic: "asc" | "desc" | "none";
    leaf: "asc" | "desc" | "none";
  };
  /** Weighting mode: `"leafCount"` uses 1 per leaf; `"value"` uses node.value. */
  weightMode: "leafCount" | "value";
  /** Multiplier applied to red-alert leaves when computing weights. */
  redAlertWeightBoost: number;
  /** Scale factor applied to the final leaf within each topic to reduce rounding remainder. */
  leafRemainderBias: number;
  /** Transform used when `weightMode === "value"` and not applied in normalize. */
  valueTransform: "none" | "sqrt" | "log1p";
  /** If true, normalize applies transform; otherwise `buildWeightedTree` does. */
  applyValueTransformInNormalize: boolean;
  /** Padding used for leaf label layout box. */
  labelPaddingLeaf: number;
  /** Extra padding added to all leaf label sides. */
  leafPaddingExtra: number;
  /** Padding used for group label layout box. */
  labelPaddingGroup: number;
  /** Extra X padding used by leaf font size estimation. */
  leafTextPaddingX: number;
  /** Extra Y padding used by leaf font size estimation. */
  leafTextPaddingY: number;
  /** Max wrapped lines allowed for leaf labels. */
  maxLeafLines: number;
  /** Max wrapped lines allowed for group labels (currently unused). */
  maxGroupLines: number;
  /** If true, leaf labels are forced to a single truncated line. */
  truncateLeafLabels: boolean;
  /** Width factor (of available width) for leaf truncation. */
  leafTruncationFactor: number;
  /** Lower bound for leaf truncation width factor. */
  leafTruncationMinFactor: number;
  /** Minimum tile width used to mark tiles "skinny". */
  minTileWidth: number;
  /** Minimum tile height used to mark tiles "skinny". */
  minTileHeight: number;
  /** If true, skinny tiles are not rendered at all. */
  hideSkinnyTiles: boolean;
  /** Minimum opacity required for pointer events. */
  interactiveMinOpacity: number;
  /** Minimum width required for pointer events. */
  interactiveMinWidth: number;
  /** Minimum height required for pointer events. */
  interactiveMinHeight: number;
  /** Minimum weight assigned to any group/leaf after scaling. */
  minGroupWeight: number;
  /** Default outer padding between sibling groups (fallback). */
  groupBorder: number;
  /** Default inner padding between children in a group (fallback). */
  groupBorderInner: number;
  /** Outer padding by depth for layout tiling. */
  groupBorderByDepth: {
    root: number;
    category: number;
    topic: number;
    leaf: number;
  };
  /** Inner padding by depth for layout tiling. */
  groupBorderInnerByDepth: {
    root: number;
    category: number;
    topic: number;
    leaf: number;
  };
  /** Top padding band reserved for group labels when enabled. */
  groupLabelBand: number;
  /** If true, adds top padding band for group labels in layout. */
  useLayoutLabelBand: boolean;
  /** Minimum depth that receives the label band padding. */
  labelBandMinDepth: number;
  /** Maximum depth that receives the label band padding. */
  labelBandMaxDepth: number;
  /** Morph animation duration in milliseconds. */
  animationDurationMs: number;
  /** Corner radius for tile rectangles. */
  tileRadius: number;
};

export const defaultTuning: TreemapTuning = {
  epsilon: 5,
  minArea: 120,
  opacityFadeRange: 120,
  minRectOpacity: 0.65,
  categoryRectOpacity: 0.6,
  topicRectOpacity: 0.45,
  baseFillColor: "#334155",
  rectStrokeColor: "rgba(15, 23, 42, 0.35)",
  labelColor: "#ffffff",
  labelLetterSpacing: "0.08em",
  leafFontMin: 2,
  leafFontMax: 72,
  groupFontMin: 6,
  groupFontMax: 18,
  lineHeight: 1.2,
  avgGlyphWidthFactor: 0.58,
  textHeightFactor: 0.9,
  wrapGlyphWidthFactor: 0.7,
  allowMidWordWrap: false,
  squarifyRatio: 1.61803398875,
  squarifyRatioMode: "screen",
  squarifyRatioScale: 1,
  tileAlgorithmRoot: "resquarify",
  tileAlgorithmCategory: "binary",
  tileAlgorithmTopic: "binary",
  tileAlgorithmLeaf: "binary",
  sortByValueForBinary: true,
  binarySortOrderByDepth: {
    root: "asc",
    category: "asc",
    topic: "asc",
    leaf: "asc",
  },
  sortByValueForSquarify: true,
  squarifySortOrderByDepth: {
    root: "desc",
    category: "desc",
    topic: "desc",
    leaf: "desc",
  },
  weightMode: "leafCount",
  redAlertWeightBoost: 10,
  leafRemainderBias: 0.9,
  valueTransform: "log1p",
  applyValueTransformInNormalize: true,
  labelPaddingLeaf: 0,
  leafPaddingExtra: 0,
  labelPaddingGroup: 4,
  leafTextPaddingX: 0,
  leafTextPaddingY: 1,
  maxLeafLines: 100,
  maxGroupLines: 100,
  truncateLeafLabels: false,
  leafTruncationFactor: 1,
  leafTruncationMinFactor: 0.3,
  minTileWidth: 120,
  minTileHeight: 120,
  hideSkinnyTiles: false,
  interactiveMinOpacity: 0.2,
  interactiveMinWidth: 1,
  interactiveMinHeight: 1,
  minGroupWeight: 1,
  groupBorder: 5,
  groupBorderInner: 2,
  groupBorderByDepth: {
    root: 0,
    category: 2,
    topic: 2,
    leaf: 0,
  },
  groupBorderInnerByDepth: {
    root: 5,
    category: 3,
    topic: 2,
    leaf: 0,
  },
  groupLabelBand: 30,
  useLayoutLabelBand: true,
  labelBandMinDepth: 1,
  labelBandMaxDepth: 4,
  animationDurationMs: 800,
  tileRadius: 6,
};

export const treemapPalettes: Record<string, string[]> = {
  default: [
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
  ],
  "github-light": [
    "#d08b85",
    "#c68a74",
    "#b98e6c",
    "#8ea27b",
    "#7fa590",
    "#79a3a6",
    "#6d8db8",
    "#7c80c2",
    "#8d7fc2",
    "#a67fae",
    "#b57d8a",
    "#b08a79",
  ],
  "catppuccin-latte": [
    "#dc8a78",
    "#dd7878",
    "#ea76cb",
    "#8839ef",
    "#d20f39",
    "#e64553",
    "#fe640b",
    "#df8e1d",
    "#40a02b",
    "#179299",
    "#04a5e5",
    "#1e66f5",
  ],
  dracula: [
    "#ffb86c",
    "#ff79c6",
    "#bd93f9",
    "#50fa7b",
    "#8be9fd",
    "#6fb1ff",
    "#8a7ddc",
    "#9a7bff",
    "#ff92df",
    "#ff6e6e",
    "#f1fa8c",
    "#caa9fa",
  ],
  "github-dark": [
    "#ff7b72",
    "#ffa657",
    "#d29922",
    "#7ee787",
    "#56d4dd",
    "#79c0ff",
    "#7d8590",
    "#8b949e",
    "#a371f7",
    "#db61a2",
    "#ffa198",
    "#c9d1d9",
  ],
  "catppuccin-mocha": [
    "#f5e0dc",
    "#f2cdcd",
    "#f5c2e7",
    "#cba6f7",
    "#f38ba8",
    "#eba0ac",
    "#fab387",
    "#f9e2af",
    "#a6e3a1",
    "#94e2d5",
    "#89dceb",
    "#89b4fa",
  ],
  "oled-modern": [
    "#00c2ff",
    "#00e5ff",
    "#00ff99",
    "#7c3aed",
    "#b026ff",
    "#ff2d55",
    "#ff6a00",
    "#ffd60a",
    "#7aff00",
    "#00ffa3",
    "#4b7bff",
    "#ff375f",
  ],
};

export const treemapLabelColors: Record<string, string> = {
  default: "#ffffff",
  "github-light": "#1f2937",
  dracula: "#e5e1f5",
  "github-dark": "#e6edf3",
  "catppuccin-latte": "#2e3440",
  "catppuccin-mocha": "#fdf6e3",
  "oled-modern": "#f8fafc",
};
