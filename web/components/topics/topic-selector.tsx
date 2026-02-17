"use client";

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

import { TopicEntry } from "@/lib/dashboard";

export function TopicSelector({ topics }: { topics: TopicEntry[] }) {
  const options = useMemo(
    () => topics.filter((topic) => topic.keyword && topic.response),
    [topics]
  );
  const [selected, setSelected] = useState(options[0]?.keyword ?? "");

  const active = options.find((topic) => topic.keyword === selected);

  return (
    <div className="space-y-4">
      <label className="flex flex-col gap-2 text-sm font-medium text-foreground">
        Select Topic
        <select
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
        >
          {options.map((topic) => (
            <option key={topic.keyword} value={topic.keyword}>
              {topic.keyword}
            </option>
          ))}
        </select>
      </label>
      {active ? (
        <div className="rounded-lg border border-border bg-card/80 p-4">
          <div className="prose prose-sm max-w-none text-foreground prose-headings:font-display prose-headings:text-foreground prose-p:text-foreground prose-li:text-foreground prose-strong:text-foreground dark:prose-invert">
            <ReactMarkdown>{active.response}</ReactMarkdown>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No response found for the selected topic.</p>
      )}
    </div>
  );
}
