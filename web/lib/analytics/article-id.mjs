import { sha256 } from "@noble/hashes/sha2.js";
import { bytesToHex } from "@noble/hashes/utils.js";

// v1: preserve path/query identity; remove fragments and known attribution only.
// Do not strip arbitrary queries (e.g. ?article=42) or change path case.
export function normaliseArticleUrl(value) {
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return null;
    url.hash = "";
    for (const key of [...url.searchParams.keys()]) {
      if (/^(utm_.*|fbclid|gclid|msclkid)$/i.test(key)) url.searchParams.delete(key);
    }
    url.searchParams.sort();
    return url.href;
  } catch {
    return null;
  }
}

export function articleId(url) {
  const normalised = normaliseArticleUrl(url);
  return normalised ? `url-v1-${bytesToHex(sha256(new TextEncoder().encode(normalised)))}` : null;
}
