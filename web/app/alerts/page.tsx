import { AlertsDashboard } from "@/components/alerts/alerts-dashboard";
import { loadDashboard } from "@/lib/dashboard";

export default async function AlertsPage() {
  const dashboard = await loadDashboard();

  return (
    <AlertsDashboard flagged={dashboard.flagged_alerts} />
  );
}
