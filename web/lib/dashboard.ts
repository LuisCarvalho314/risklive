import fs from "fs/promises";
import { getDashboardPath } from "@/lib/dashboard-path";
export {
  DashboardValidationError,
  getDefaultDashboard,
  parseDashboardPayload,
  parseDashboardString,
} from "@/lib/dashboard-schema";
export type {
  AlertItem,
  AlertsSection,
  DashboardData,
  FlaggedAlerts,
  RecentAlerts,
  TopicEntry,
  TreemapNode,
} from "@/lib/dashboard-schema";
import { getDefaultDashboard, parseDashboardString, type DashboardData } from "@/lib/dashboard-schema";

export async function loadDashboard(): Promise<DashboardData> {
  const dashboardPath = getDashboardPath();
  try {
    const raw = await fs.readFile(dashboardPath, "utf-8");
    return parseDashboardString(raw);
  } catch (error) {
    const fileMissing =
      error instanceof Error &&
      "code" in error &&
      (error as NodeJS.ErrnoException).code === "ENOENT";
    if (fileMissing) {
      return getDefaultDashboard();
    }
    throw error;
  }
}
