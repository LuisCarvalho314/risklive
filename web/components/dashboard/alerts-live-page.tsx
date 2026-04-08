//© 2025 University of Aberdeen. All rights reserved


"use client";

import { AlertsDashboard } from "@/components/alerts/alerts-dashboard";
import { useDashboardData } from "@/lib/dashboard-client";

export function AlertsLivePage() {
  const { dashboard } = useDashboardData();

  return (
    <div className="h-full min-h-0 overflow-y-auto p-6">
      <AlertsDashboard flagged={dashboard.flagged_alerts} />
    </div>
  );
}
