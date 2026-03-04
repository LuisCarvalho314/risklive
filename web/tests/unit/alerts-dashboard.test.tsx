//© 2025 University of Aberdeen. All rights reserved


import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AlertsDashboard } from "@/components/alerts/alerts-dashboard";
import { sampleDashboard } from "@/tests/fixtures/dashboard";

describe("AlertsDashboard", () => {
  it("renders flagged alerts and supports filter/search", async () => {
    const user = userEvent.setup();
    render(<AlertsDashboard flagged={sampleDashboard.flagged_alerts} />);

    expect(screen.getByText("News Alert Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Red Alert")).toBeInTheDocument();
    expect(screen.getByText("Yellow Alert")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "High Risk" }));
    expect(screen.getByText("Red Alert")).toBeInTheDocument();
    expect(screen.queryByText("Yellow Alert")).not.toBeInTheDocument();

    const input = screen.getByPlaceholderText("Search title, summary, category, reason");
    await user.clear(input);
    await user.type(input, "watch item");
    expect(screen.queryByText("Red Alert")).not.toBeInTheDocument();
    expect(screen.queryByText("Yellow Alert")).not.toBeInTheDocument();
    expect(screen.getAllByText("No alerts available.").length).toBeGreaterThan(0);
  });
});
