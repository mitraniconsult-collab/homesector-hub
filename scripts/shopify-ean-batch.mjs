#!/usr/bin/env node
// Homesector Shopify barcode-type migration. Read-only by default.
// Node.js 20+. Requires SHOPIFY_SHOP_DOMAIN and SHOPIFY_ADMIN_ACCESS_TOKEN.
import fs from "node:fs/promises";
import path from "node:path";

const args = new Set(process.argv.slice(2));
const argValue = (name, fallback) => {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : fallback;
};
const apply = args.has("--apply");
const workers = Math.min(8, Math.max(1, Number(argValue("--workers", "4")) || 4));
const maxPages = Math.max(1, Number(argValue("--max-pages", "999999")) || 1);
const checkpointFile = path.resolve(argValue("--checkpoint", "./shopify-ean-checkpoint.json"));
const apiVersion = process.env.SHOPIFY_API_VERSION || "2026-10";
const shop = (process.env.SHOPIFY_SHOP_DOMAIN || "").replace(/^https?:\/\//, "").replace(/\/$/, "");
const token = process.env.SHOPIFY_ADMIN_ACCESS_TOKEN;
if (!shop || !token || !/^[a-z0-9][a-z0-9.-]*\.myshopify\.com$/.test(shop)) {
  console.error("Set SHOPIFY_SHOP_DOMAIN=store.myshopify.com and SHOPIFY_ADMIN_ACCESS_TOKEN. Never commit tokens.");
  process.exit(1);
}
const endpoint = `https://${shop}/admin/api/${apiVersion}/graphql.json`;
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function graphql(query, variables = {}) {
  for (let attempt = 0; attempt < 7; attempt++) {
    let response;
    try {
      response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Shopify-Access-Token": token },
        body: JSON.stringify({ query, variables }),
        signal: AbortSignal.timeout(45000)
      });
    } catch (error) {
      if (attempt === 6) throw error;
      await pause(Math.min(30000, 900 * 2 ** attempt));
      continue;
    }
    if (response.status === 429 || response.status >= 500) {
      if (attempt === 6) throw new Error(`Shopify HTTP ${response.status}`);
      await pause(Math.min(30000, 1000 * 2 ** attempt));
      continue;
    }
    if (!response.ok) throw new Error(`Shopify HTTP ${response.status}: ${(await response.text()).slice(0, 400)}`);
    const body = await response.json();
    if (body.errors?.length) {
      const throttled = body.errors.every(e => e.extensions?.code === "THROTTLED");
      if (throttled && attempt < 6) { await pause(1200 * 2 ** attempt); continue; }
      throw new Error(JSON.stringify(body.errors));
    }
    const throttle = body.extensions?.cost?.throttleStatus;
    if (throttle && throttle.currentlyAvailable < 100) await pause(350);
    return body.data;
  }
  throw new Error("Retry limit reached");
}
function isEan(value) {
  if (typeof value !== "string" || !/^(\d{8}|\d{13})$/.test(value)) return false;
  const digits = [...value].map(Number);
  const check = digits.pop();
  const sum = digits.reverse().reduce((n, digit, i) => n + digit * (i % 2 === 0 ? 3 : 1), 0);
  return (10 - sum % 10) % 10 === check;
}
const query = `query($after:String){
  productVariants(first:50,after:$after) {
    nodes { id product { id } barcodes(first:20) { nodes { value type } pageInfo { hasNextPage } } }
    pageInfo { endCursor hasNextPage }
  }
}`;
const mutation = `mutation($productId:ID!,$variants:[ProductVariantsBulkInput!]!){
  productVariantsBulkUpdate(productId:$productId,variants:$variants) {
    productVariants { id }
    userErrors { field message }
  }
}`;
async function readCheckpoint() {
  try { return JSON.parse(await fs.readFile(checkpointFile, "utf8")); }
  catch (e) { if (e.code === "ENOENT") return null; throw e; }
}
async function writeCheckpoint(checkpoint) {
  const tmp = checkpointFile + ".tmp";
  await fs.writeFile(tmp, JSON.stringify(checkpoint, null, 2));
  await fs.rename(tmp, checkpointFile);
}
async function runPool(items, limit, fn) {
  let index = 0;
  const results = [];
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (index < items.length) {
      const current = index++;
      try { results[current] = { ok: true, result: await fn(items[current]) }; }
      catch (error) { results[current] = { ok: false, error: String(error) }; }
    }
  }));
  return results;
}
const previous = await readCheckpoint();
if (previous && previous.shop !== shop) throw new Error("Checkpoint belongs to another shop");
if (previous && previous.apiVersion !== apiVersion) throw new Error("Checkpoint API version differs");
if (previous && previous.apply !== apply) throw new Error("Use separate checkpoints for --apply and dry-run");
const state = previous || {
  shop, apiVersion, apply, after: null, pages: 0, examined: 0, eligible: 0,
  updated: 0, unchanged: 0, skippedEmpty: 0, skippedInvalid: 0, failed: [], updatedAt: null
};
let pagesThisRun = 0;
while (pagesThisRun < maxPages && !state.complete) {
  const data = await graphql(query, { after: state.after });
  const page = data.productVariants;
  const grouped = new Map();
  let empty = 0, invalid = 0, unchanged = 0, eligible = 0;
  for (const variant of page.nodes) {
    const barcodes = variant.barcodes.nodes;
    if (!barcodes.length) { empty++; continue; }
    // A partially fetched barcode list or mixed barcode formats must never be overwritten.
    if (variant.barcodes.pageInfo.hasNextPage || !barcodes.every(b => isEan(b.value))) { invalid++; continue; }
    if (barcodes.every(b => b.type === "EAN")) { unchanged++; continue; }
    eligible++;
    const group = grouped.get(variant.product.id) || [];
    group.push({ id: variant.id, barcodes: barcodes.map(b => ({ value: b.value, type: "EAN" })) });
    grouped.set(variant.product.id, group);
  }
  const jobs = [...grouped].map(([productId, variants]) => ({ productId, variants }));
  const results = apply
    ? await runPool(jobs, workers, async job => {
        const d = await graphql(mutation, job);
        const errors = d.productVariantsBulkUpdate?.userErrors || [];
        if (errors.length) throw new Error(JSON.stringify(errors));
        return job.variants.length;
      })
    : jobs.map(job => ({ ok: true, result: job.variants.length }));
  const failed = results.flatMap((r, i) => r.ok ? [] : [{ productId: jobs[i].productId, variants: jobs[i].variants.map(v => v.id), error: r.error }]);
  state.failed.push(...failed);
  // Retain the cursor on errors: the next invocation retries failed items; already-EAN rows are skipped.
  if (!failed.length) state.after = page.pageInfo.endCursor;
  state.pages++;
  pagesThisRun++;
  state.examined += page.nodes.length;
  state.eligible += eligible;
  state.updated += results.reduce((sum, r) => sum + (r.ok ? r.result : 0), 0);
  state.unchanged += unchanged;
  state.skippedEmpty += empty;
  state.skippedInvalid += invalid;
  state.updatedAt = new Date().toISOString();
  if (!failed.length && !page.pageInfo.hasNextPage) state.complete = true;
  await writeCheckpoint(state);
  console.log(JSON.stringify({ page: state.pages, scanned: page.nodes.length, eligible, changed: results.reduce((n,r)=>n+(r.ok?r.result:0),0), failed: failed.length, totalChanged: state.updated, complete: !!state.complete }));
  if (failed.length) { console.error("Errors saved in checkpoint; stopping without advancing cursor."); process.exitCode = 2; break; }
}
console.log(JSON.stringify({ checkpoint: checkpointFile, ...state }, null, 2));
