//© 2025 University of Aberdeen. All rights reserved


import { filterLogEvents, readLogEvents } from "@/lib/ops/log-parser";

export const dynamic = "force-dynamic";

function parseLimit(value: string | null): number | undefined {
  if (!value) return undefined;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const filter = {
    level: url.searchParams.get("level") ?? undefined,
    component: url.searchParams.get("component") ?? undefined,
    operation: url.searchParams.get("operation") ?? undefined,
    query: url.searchParams.get("query") ?? undefined,
    limit: parseLimit(url.searchParams.get("limit")),
  };

  const { events, parseErrors } = await readLogEvents();
  const filtered = filterLogEvents(events, filter);

  return new Response(
    JSON.stringify({
      events: filtered,
      count: filtered.length,
      parseErrors,
    }),
    {
      headers: {
        "content-type": "application/json",
        "cache-control": "no-store",
      },
    }
  );
}
