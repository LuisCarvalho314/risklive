import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { AlertItem } from "@/lib/dashboard";
import { cn } from "@/lib/utils";

const badgeVariant = (flag?: string) => {
  if (flag === "Red") return "red";
  if (flag === "Yellow") return "yellow";
  return "default";
};

export function AlertList({
  items,
  className
}: {
  items: AlertItem[];
  className?: string;
}) {
  if (!items.length) {
    return <p className="text-sm text-muted-foreground">No alerts available.</p>;
  }

  const formatTimestamp = (value?: string | null) => {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return new Intl.DateTimeFormat("en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "UTC"
    }).format(date);
  };

  return (
    <ul className={cn("grid gap-3", className)}>
      {items.map((item, index) => (
        <li
          key={item.url || `${item.title}-${index}`}
          className="rounded-lg border border-border bg-card/70 px-4 py-3"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1">
              {item.url ? (
                <Link href={item.url} className="text-sm font-semibold text-foreground hover:underline">
                  {item.title}
                </Link>
              ) : (
                <p className="text-sm font-semibold text-foreground">{item.title}</p>
              )}
              {item.short_summary ? (
                <p className="text-xs text-muted-foreground">{item.short_summary}</p>
              ) : null}
              <div className="text-[11px] text-muted-foreground">
                {item.news_category ? <span>{item.news_category}</span> : null}
                {item.alert_reason ? <span>{item.news_category ? " • " : ""}{item.alert_reason}</span> : null}
                {item.timestamp ? (
                  <span>
                    {item.news_category || item.alert_reason ? " • " : ""}
                    {formatTimestamp(item.timestamp)}
                  </span>
                ) : null}
              </div>
            </div>
            <Badge variant={badgeVariant(item.alert_flag)}>
              {item.alert_flag || "Unknown"}
            </Badge>
          </div>
        </li>
      ))}
    </ul>
  );
}
