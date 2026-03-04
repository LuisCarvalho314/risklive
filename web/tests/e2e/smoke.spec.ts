//© 2025 University of Aberdeen. All rights reserved


import { expect, test } from "@playwright/test";
import { mkdir, writeFile } from "fs/promises";
import path from "path";

import { sampleDashboard } from "../fixtures/dashboard";

test.beforeAll(async () => {
  const overridePath =
    process.env.DASHBOARD_JSON_PATH ??
    path.join(process.cwd(), "tests", ".runtime", "dashboard.json");
  const dashboardDir = path.dirname(overridePath);
  await mkdir(dashboardDir, { recursive: true });
  await writeFile(
    overridePath,
    JSON.stringify(sampleDashboard, null, 2),
    "utf-8"
  );
});

test("smoke: alerts/newsmap/topics pages render", async ({ page }) => {
  await page.goto("/alerts");
  await expect(page.getByText("News Alert Dashboard")).toBeVisible();

  await page.goto("/newsmap");
  await expect(page.locator("svg").first()).toBeVisible();

  await page.goto("/topics");
  await expect(page.getByText("Daily Report")).toBeVisible();
});
