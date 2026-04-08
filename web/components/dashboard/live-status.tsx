//© 2025 University of Aberdeen. All rights reserved


"use client";

function formatTimestamp(value: string | null): string {
  if (!value) return "never";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(parsed);
}

type Props = {
  generatedAt: string | null;
  lastLoadedAt: string | null;
  error: string | null;
  isLoading: boolean;
  isRefreshing: boolean;
};

export function DashboardLiveStatus({
  generatedAt,
  lastLoadedAt,
  error,
  isLoading,
  isRefreshing,
}: Props) {
  const stateLabel = isLoading
    ? "Loading dashboard..."
    : isRefreshing
      ? "Refreshing dashboard..."
      : error
        ? "Showing last good dashboard snapshot."
        : null;

  return (
    <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card/70 px-4 py-2 text-xs text-muted-foreground">
      {stateLabel ? <span>{stateLabel}</span> : null}
      <span>Generated: {formatTimestamp(generatedAt)}</span>
      <span>Loaded: {formatTimestamp(lastLoadedAt)}</span>
      {error ? (
        <span className="text-amber-700 dark:text-amber-300">{error}</span>
      ) : null}
    </div>
  );
}
