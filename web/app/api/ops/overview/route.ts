import { buildOpsOverview } from "@/lib/ops/status-aggregator";

export const dynamic = "force-dynamic";

export async function GET() {
  const overview = await buildOpsOverview();
  return new Response(JSON.stringify(overview), {
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store"
    }
  });
}

