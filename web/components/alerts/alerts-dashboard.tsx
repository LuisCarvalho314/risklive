//© 2025 University of Aberdeen. All rights reserved


"use client";

import { useEffect, useMemo, useState } from "react";

import { AlertList } from "@/components/alerts/alert-list";
import { Button } from "@/components/ui/button";
import { AlertItem, FlaggedAlerts } from "@/lib/dashboard";

const alertFilters = ["All", "Red", "Yellow"] as const;

const alertFilterLabel = (value: (typeof alertFilters)[number]) => {
  if (value === "Red") return "High Risk";
  if (value === "Yellow") return "Medium Risk";
  return "All";
};

type AlertFilter = (typeof alertFilters)[number];

function filterItems(items: AlertItem[], query: string, filter: AlertFilter) {
  const lowered = query.trim().toLowerCase();
  return items.filter((item) => {
    if (filter !== "All" && item.alert_flag !== filter) return false;
    if (!lowered) return true;
    const haystack = [
      item.title,
      item.short_summary,
      item.description,
      item.news_category,
      item.alert_reason
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(lowered);
  });
}

function AlertSection({
  title,
  items,
  canLoadMore,
  onLoadMore
}: {
  title: string;
  items: AlertItem[];
  canLoadMore?: boolean;
  onLoadMore?: () => void;
}) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
        {title}
      </h3>
      <AlertList items={items} className="grid-cols-1 sm:grid-cols-2 lg:grid-cols-3" />
      {canLoadMore ? (
        <div>
          <Button type="button" size="sm" variant="outline" onClick={onLoadMore}>
            Load more
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export function AlertsDashboard({ flagged }: { flagged: FlaggedAlerts }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<AlertFilter>("All");
  const maxInitial = 200;
  const pageStep = 100;
  const [visibleRed, setVisibleRed] = useState(maxInitial);
  const [visibleYellow, setVisibleYellow] = useState(maxInitial);

  const flaggedFiltered = useMemo(() => {
    return {
      red: filterItems(flagged.red, query, filter),
      yellow: filterItems(flagged.yellow, query, filter)
    };
  }, [flagged, query, filter]);

  useEffect(() => {
    setVisibleRed(maxInitial);
    setVisibleYellow(maxInitial);
  }, [maxInitial, query, filter, flagged]);

  const redItems = flaggedFiltered.red.slice(0, visibleRed);
  const yellowItems = flaggedFiltered.yellow.slice(0, visibleYellow);
  const canLoadMoreRed = visibleRed < flaggedFiltered.red.length;
  const canLoadMoreYellow = visibleYellow < flaggedFiltered.yellow.length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search title, summary, category, reason"
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground lg:w-80"
        />
        <div className="flex flex-wrap gap-2">
          {alertFilters.map((value) => (
            <Button
              key={value}
              type="button"
              size="sm"
              variant={filter === value ? "default" : "outline"}
              onClick={() => setFilter(value)}
            >
              {alertFilterLabel(value)}
            </Button>
          ))}
        </div>
      </div>


      <section className="space-y-4">
        <h2 className="font-display text-2xl">News Alert Dashboard</h2>
        <p className="text-sm text-muted-foreground">All red and yellow alerts by flag.</p>

        <div className="grid grid-cols-1 gap-6">
          <AlertSection
            title="Red"
            items={redItems}
            canLoadMore={canLoadMoreRed}
            onLoadMore={() => setVisibleRed((value) => value + pageStep)}
          />
          <AlertSection
            title="Yellow"
            items={yellowItems}
            canLoadMore={canLoadMoreYellow}
            onLoadMore={() => setVisibleYellow((value) => value + pageStep)}
          />
        </div>
      </section>

    </div>
  );
}
