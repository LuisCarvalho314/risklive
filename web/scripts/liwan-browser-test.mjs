// Invoked only by tools/analytics/liwan_integration.py with disposable local servers.
import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
const [edge, disabledWeb, output] = process.argv.slice(2);
const browser = await chromium.launch({ headless: true });
const captured = [];
const errors = [];
async function context(target, positive = true) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  if (positive) {
    // Synthetic positive case only: production code rejects real browser automation.
    await ctx.addInitScript(() => Object.defineProperty(navigator, "webdriver", { get: () => false }));
  }
  await ctx.route("**/*", async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.hostname !== "risklive.test") return route.fulfill({ status: 200, contentType: "text/plain", body: "Synthetic source. No external request." });
    if (url.pathname === "/analytics/event") captured.push(JSON.parse(request.postData()));
    const response = await route.fetch({ url: target + url.pathname + url.search });
    await route.fulfill({ response });
  });
  return ctx;
}
const waitFor = async predicate => {
  for (let i = 0; i < 100; i++) {
    if (predicate()) return;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error(`Timed out waiting for analytics; captured: ${JSON.stringify(captured)}`);
};
try {
  const ctx = await context(edge);
  const page = await ctx.newPage();
  page.on("pageerror", e => errors.push(String(e)));
  await page.goto("http://risklive.test/alerts?search=PRIVATE_SEARCH");
  await waitFor(() => captured.some(e => e.name === "pageview"));
  // Prevent external navigation in this synthetic test while preserving React's click handler.
  await page.evaluate(() => document.addEventListener("click", e => {
    const link = e.target.closest?.("a");
    if (link?.href.startsWith("https://publisher.invalid")) e.preventDefault();
  }, true));
  await page.getByRole("link", { name: "Synthetic article", exact: true }).click();
  await waitFor(() => captured.filter(e => e.name === "article_opened").length === 1);
  await page.getByRole("button", { name: "High Risk", exact: true }).click();
  await waitFor(() => captured.some(e => e.name === "alert_filter_changed"));
  await page.getByRole("link", { name: "Newsmap", exact: true }).click();
  await page.locator("svg text").filter({ hasText: "Synthetic article" }).first().dblclick();
  await waitFor(() => captured.filter(e => e.name === "article_opened").length === 2);
  await page.getByRole("button", { name: "Squarify", exact: true }).click();
  await waitFor(() => captured.some(e => e.name === "newsmap_view_changed"));
  await page.getByRole("link", { name: "Newsmap Experimental", exact: true }).click();
  // Dispatch the double-click directly: the existing hover tooltip can intercept
  // the second physical click in headless pointer simulation. No product handler is mocked.
  const experimentalNode = page.locator("svg text").filter({ hasText: "energy" }).first();
  await experimentalNode.hover();
  await page.getByText("Sources (1)", { exact: true }).waitFor();
  await experimentalNode.dispatchEvent("dblclick", { clientX: 300, clientY: 300 });
  await page.getByRole("link", { name: /Synthetic article|publisher.invalid/ }).first().click();
  await waitFor(() => captured.filter(e => e.name === "article_opened").length === 3);
  await page.getByRole("link", { name: "Daily Report", exact: true }).click();
  await page.getByRole("button", { name: "second topic", exact: true }).click();
  await page.getByPlaceholder("Filter keywords").fill("PRIVATE_SEARCH");
  await page.getByPlaceholder("Filter keywords").press("Enter");
  await waitFor(() => captured.some(e => e.name === "topic_filter_used"));
  assert.deepEqual(captured.filter(e => e.name === "pageview").map(e => new URL(e.url).pathname), ["/alerts", "/newsmap", "/newsmap-experimental", "/topics"]);
  const articles = captured.filter(e => e.name === "article_opened");
  assert.equal(new Set(articles.map(e => e.properties.article_id)).size, 1);
  assert.deepEqual(articles.map(e => e.properties.section), ["alerts", "newsmap", "newsmap-experimental"]);
  for (const payload of captured) {
    assert.deepEqual(Object.keys(payload).sort(), ["entity_id", "name", "properties", "url"]);
    assert.ok(!JSON.stringify(payload).match(/PRIVATE_SEARCH|publisher.invalid|Synthetic article|referrer|screen_width|orientation|utm_/));
  }
  await page.getByRole("link", { name: "Privacy", exact: true }).click();
  const before = captured.length;
  await page.goto("http://risklive.test/ops");
  await page.waitForTimeout(400);
  assert.equal(captured.length, before);
  await page.goto("http://risklive.test/privacy");
  await page.getByRole("button", { name: "Opt out of usage analytics", exact: true }).click();
  await page.goto("http://risklive.test/alerts");
  await page.waitForTimeout(400);
  assert.equal(captured.length, before);
  await page.goto("http://risklive.test/ops");
  await page.waitForTimeout(400);
  assert.equal(captured.length, before);
  await ctx.close();
  for (const [target, positive] of [[disabledWeb, true], [edge, false]]) {
    const other = await context(target, positive);
    const p = await other.newPage();
    await p.goto("http://risklive.test/alerts");
    await p.waitForTimeout(500);
    assert.equal(captured.length, before, "disabled configuration/automation emitted an event");
    await other.close();
  }
  assert.deepEqual(errors, []);
  await writeFile(output, JSON.stringify({ captured, checks: { sharedArticleIdentity: true, allPageRoutes: true,
    privatePayload: true, optOut: true, excludedOps: true, disabledServer: true, automationExcluded: true } }, null, 2));
} catch (error) {
  console.error(JSON.stringify({ errors, pages: await Promise.all(browser.contexts().flatMap(c => c.pages()).map(async p => ({ url: p.url(), text: (await p.locator("body").innerText()).slice(0, 1800) }))) }));
  throw error;
} finally { await browser.close(); }
