//© 2025 University of Aberdeen. All rights reserved


import { readFile } from "fs/promises";
import { getDashboardPath } from "@/lib/dashboard-path";

export const revalidate = 60;

export async function GET() {
  const dashboardPath = getDashboardPath();
  try {
    const raw = await readFile(dashboardPath, "utf-8");
    return new Response(raw, {
      headers: {
        "content-type": "application/json",
        "cache-control": "public, max-age=60"
      }
    });
  } catch (error) {
    return new Response(
      JSON.stringify({ error: "dashboard.json not found" }),
      {
        status: 404,
        headers: { "content-type": "application/json" }
      }
    );
  }
}
