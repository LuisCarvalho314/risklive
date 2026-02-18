import { AlertsDashboard } from "@/components/alerts/alerts-dashboard";
import { loadDashboard } from "@/lib/dashboard";

export default async function AlertsPage() {
  const dashboard = await loadDashboard();

  return (
    <div className="h-full min-h-0 overflow-y-auto p-6">
      <AlertsDashboard flagged={dashboard.flagged_alerts} />
    </div>
  );
}
