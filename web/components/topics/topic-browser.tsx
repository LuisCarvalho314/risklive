//© 2025 University of Aberdeen. All rights reserved


"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { TopicEntry } from "@/lib/dashboard";

export function TopicBrowser({ topics }: { topics: TopicEntry[] }) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(topics[0]?.keyword ?? "");

  const filtered = useMemo(() => {
    const lowered = query.trim().toLowerCase();
    const seen = new Set<string>();
    const out: TopicEntry[] = [];

    for (const topic of topics) {
      const keyword = topic.keyword?.trim();
      if (!keyword) continue;
      if (seen.has(keyword)) continue;
      if (lowered && !keyword.toLowerCase().includes(lowered)) continue;
      seen.add(keyword);
      out.push(topic);
    }

    return out;
  }, [topics, query]);

  const active = topics.find((topic) => topic.keyword === selected) ?? filtered[0];

  useEffect(() => {
    if (!filtered.length) {
      setSelected("");
      return;
    }
    if (!filtered.some((topic) => topic.keyword === selected)) {
      setSelected(filtered[0]?.keyword ?? "");
    }
  }, [filtered, selected]);

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_3fr]">
      <div className="space-y-3">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Filter keywords"
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
        />
        <div className="max-h-[520px] space-y-2 overflow-y-auto rounded-lg border border-border bg-card/60 p-3">
          {filtered.map((topic) => (
            <Button
              key={topic.keyword}
              type="button"
              variant={selected === topic.keyword ? "default" : "ghost"}
              className="w-full justify-start"
              onClick={() => setSelected(topic.keyword)}
            >
              {topic.keyword}
            </Button>
          ))}
          {!filtered.length ? (
            <p className="text-sm text-muted-foreground">No topics match that filter.</p>
          ) : null}
        </div>
      </div>
      <div className="min-h-[520px] rounded-lg border border-border bg-card/80 p-6">
        {active ? (
          <div className="prose prose-sm max-w-none text-foreground prose-headings:font-display prose-headings:text-foreground prose-p:text-foreground prose-li:text-foreground prose-strong:text-foreground dark:prose-invert">
            <ReactMarkdown>{active.response}</ReactMarkdown>
          </div>
        ) : (
          "No response found for the selected topic."
        )}
      </div>
    </div>
  );
}
