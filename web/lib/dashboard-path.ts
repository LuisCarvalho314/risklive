import path from "path";

export function getDashboardPath(): string {
  const override = process.env.DASHBOARD_JSON_PATH?.trim();
  if (override) return override;
  return path.join(process.cwd(), "..", "results", "web", "dashboard.json");
}

