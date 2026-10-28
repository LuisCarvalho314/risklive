// Run locally: node scripts/article-map.mjs /absolute/path/dashboard.json [other.json ...]
// Output is private source metadata. Never send it to Liwan or publish it in web/public.
import { readFile } from "node:fs/promises";
import { articleId, normaliseArticleUrl } from "../lib/analytics/article-id.mjs";
const mapping = new Map();
function visit(value) {
  if (!value || typeof value !== "object") return;
  if (typeof value.url === "string") {
    const id = articleId(value.url);
    if (id) mapping.set(id, normaliseArticleUrl(value.url));
  }
  for (const child of Object.values(value)) {
    if (Array.isArray(child)) child.forEach(visit);
    else if (child && typeof child === "object") visit(child);
  }
}
if (!process.argv.slice(2).length) throw new Error("Supply one or more existing dashboard/source JSON files");
for (const file of process.argv.slice(2)) visit(JSON.parse(await readFile(file, "utf8")));
console.log(JSON.stringify(Object.fromEntries(mapping), null, 2));
