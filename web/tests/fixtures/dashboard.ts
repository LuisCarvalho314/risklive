import type { DashboardData } from "@/lib/dashboard";

export const sampleDashboard: DashboardData = {
  generated_at: "2026-02-27T00:00:00+00:00",
  alerts: {
    nuclear: [],
    non_nuclear: {}
  },
  recent_alerts: {
    red: [],
    yellow: [],
    green: []
  },
  flagged_alerts: {
    red: [
      {
        title: "Red Alert",
        short_summary: "critical update",
        alert_flag: "Red",
        news_category: "nuclear"
      }
    ],
    yellow: [
      {
        title: "Yellow Alert",
        short_summary: "watch item",
        alert_flag: "Yellow",
        news_category: "health"
      }
    ]
  },
  newsmap: {
    name: "All News",
    children: [
      {
        name: "nuclear",
        value: 2,
        children: [
          {
            name: "Red",
            value: 2,
            children: [
              {
                name: "Red Alert",
                value: 2,
                meta: {
                  title: "Red Alert",
                  alertFlag: "Red",
                  category: "nuclear",
                  topic: "42",
                  topicLabel: "risk, policy"
                }
              }
            ]
          }
        ]
      }
    ]
  },
  topics: [
    {
      keyword: "nuclear policy",
      response: "## Summary\n\nPolicy pressure is increasing."
    }
  ],
  topic_tree: "root->nuclear"
};
