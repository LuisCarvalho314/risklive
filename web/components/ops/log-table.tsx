//© 2025 University of Aberdeen. All rights reserved


"use client";

import { useMemo, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { OpsLogEvent } from "@/lib/ops/types";

type Props = {
  events: OpsLogEvent[];
};

function normalize(value: string | undefined): string {
  return (value ?? "").toLowerCase();
}

export function LogTable({ events }: Props) {
  const [level, setLevel] = useState("all");
  const [component, setComponent] = useState("");
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    return events
      .filter((event) => (level === "all" ? true : normalize(event.level) === level))
      .filter((event) => (component ? normalize(event.component).includes(normalize(component)) : true))
      .filter((event) => (query ? normalize(JSON.stringify(event)).includes(normalize(query)) : true))
      .slice(0, 100);
  }, [component, events, level, query]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Logs</CardTitle>
        <CardDescription>Client-side filtered snapshot of structured logs.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-3 grid gap-3 md:grid-cols-3">
          <label className="text-xs text-muted-foreground">
            Level
            <select
              aria-label="Level"
              value={level}
              onChange={(event) => setLevel(event.target.value)}
              className="mt-1 block w-full rounded-md border border-border bg-background px-2 py-1 text-sm"
            >
              <option value="all">All</option>
              <option value="error">Error</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
              <option value="debug">Debug</option>
            </select>
          </label>

          <label className="text-xs text-muted-foreground">
            Component
            <input
              aria-label="Component"
              value={component}
              onChange={(event) => setComponent(event.target.value)}
              placeholder="app.server"
              className="mt-1 block w-full rounded-md border border-border bg-background px-2 py-1 text-sm"
            />
          </label>

          <label className="text-xs text-muted-foreground">
            Search
            <input
              aria-label="Search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="error_code, route, message..."
              className="mt-1 block w-full rounded-md border border-border bg-background px-2 py-1 text-sm"
            />
          </label>
        </div>

        <div className="max-h-[420px] overflow-auto rounded-lg border border-border">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="sticky top-0 bg-card">
              <tr className="border-b border-border">
                <th className="px-3 py-2">ts</th>
                <th className="px-3 py-2">level</th>
                <th className="px-3 py-2">component</th>
                <th className="px-3 py-2">operation</th>
                <th className="px-3 py-2">event</th>
                <th className="px-3 py-2">message</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((event, index) => (
                <tr key={`${event.ts}-${event.event}-${index}`} className="border-b border-border/70">
                  <td className="px-3 py-2 align-top text-muted-foreground">{event.ts ?? "-"}</td>
                  <td className="px-3 py-2 align-top">{event.level ?? "-"}</td>
                  <td className="px-3 py-2 align-top">{event.component ?? "-"}</td>
                  <td className="px-3 py-2 align-top">{event.operation ?? "-"}</td>
                  <td className="px-3 py-2 align-top">{event.event ?? "-"}</td>
                  <td className="px-3 py-2 align-top">{event.message ?? "-"}</td>
                </tr>
              ))}
              {filtered.length === 0 ? (
                <tr>
                  <td className="px-3 py-3 text-muted-foreground" colSpan={6}>
                    No matching log events.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

