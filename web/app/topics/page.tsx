import { TopicBrowser } from "@/components/topics/topic-browser";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { loadDashboard } from "@/lib/dashboard";

export default async function TopicsPage() {
  const dashboard = await loadDashboard();

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Daily Report</CardTitle>
          <CardDescription>Keyword-to-response summaries.</CardDescription>
        </CardHeader>
        <CardContent>
          {dashboard.topics.length ? (
            <TopicBrowser topics={dashboard.topics} />
          ) : (
            <p className="text-sm text-muted-foreground">No high risk reports available.</p>
          )}
        </CardContent>
      </Card>

    </div>
  );
}
