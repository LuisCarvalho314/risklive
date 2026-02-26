import { inspectArtifacts } from "@/lib/ops/artifact-inspector";

export const dynamic = "force-dynamic";

export async function GET() {
  const artifacts = await inspectArtifacts();
  return new Response(JSON.stringify({ artifacts }), {
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store"
    }
  });
}

