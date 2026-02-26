import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TopicBrowser } from "@/components/topics/topic-browser";
import { sampleDashboard } from "@/tests/fixtures/dashboard";

describe("TopicBrowser", () => {
  it("renders markdown response and filters keywords", async () => {
    const user = userEvent.setup();
    render(<TopicBrowser topics={sampleDashboard.topics} />);

    expect(screen.getByText("Summary")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "nuclear policy" })).toBeInTheDocument();

    const input = screen.getByPlaceholderText("Filter keywords");
    await user.type(input, "unmatched");
    expect(screen.getByText("No topics match that filter.")).toBeInTheDocument();
  });
});
