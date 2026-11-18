import { createHash } from "node:crypto";

const API_VERSION = "2026-04";
const MAX_BYTES = 100_000_000;
const MAX_ITEMS = 100_000;
const MAX_CATEGORIES = 150;

type Variant = {
  id: string; sku?: string | null; barcode?: string | null; title?: string | null;
  price?: string | null; inventoryQuantity?: number | null;
  image?: { url: string } | null;
  product: {
    id: string; status: string; title: string; handle: string;
    vendor?: string | null; descriptionHtml?: string | null;
    productType?: string | null; category?: { name: string } | null;
    featuredImage?: { url: string } | null;
  };
};
type Connection = { nodes: Variant[]; pageInfo: { hasNextPage: boolean; endCursor: string | null } };

const QUERY = `query EmagFeedVariants($cursor:String) {
  productVariants(first:100,after:$cursor) {
    nodes { id sku barcode title price inventoryQuantity image { url }
      product { id status title handle vendor descriptionHtml productType
        category { name } featuredImage { url } } }
    pageInfo { hasNextPage endCursor }
  }
}`;

export function escapeXml(value: unknown): string {
  return String(value ?? "").replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\uFFFE\uFFFF]/g, "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&apos;");
}

export function netPrice(value: string, vatPercent: number): string {
  const gross = Number(value);
  if (!Number.isFinite(gross) || gross <= 0 || vatPercent < 0 || vatPercent > 100) {
    throw new Error("Invalid price or VAT");
  }
  return (Math.round((gross / (1 + vatPercent / 100) + Number.EPSILON) * 100) / 100).toFixed(2);
}

export function validEan(value: string): boolean {
  if (!/^(\d{8}|\d{13})$/.test(value)) return false;
  const payload = value.slice(0, -1);
  const sum = [...payload].reverse().reduce((total, digit, offset) =>
    total + Number(digit) * (offset % 2 === 0 ? 3 : 1), 0);
  return (10 - sum % 10) % 10 === Number(value.at(-1));
}

function node(name: string, value: unknown): string {
  return `<${name}>${escapeXml(value)}</${name}>`;
}

export function feedItem(v: Variant, vatPercent: number, handlingDays: number): string | null {
  const p = v.product;
  const sku = v.sku?.trim() || "";
  const category = p.category?.name?.trim() || p.productType?.trim() || "";
  const image = v.image?.url || p.featuredImage?.url;
  if (p.status !== "ACTIVE" || !sku || !category || !image || !p.handle || !p.vendor) return null;
  const ean = v.barcode?.trim() || "";
  if (ean && !validEan(ean)) return null;
  let salePrice: string;
  try { salePrice = netPrice(v.price || "", vatPercent); } catch { return null; }
  const id = v.id.split("/").at(-1) || "";
  if (!/^\d+$/.test(id)) return null;
  const title = v.title && v.title !== "Default Title" ? `${p.title} - ${v.title}` : p.title;
  const url = `https://homesector.bg/products/${encodeURIComponent(p.handle)}?variant=${id}`;
  return `<product>${node("product_id", id)}${node("product_code", sku)}` +
    `${node("category", category)}${node("product_name", title)}` +
    `${node("brand", p.vendor)}${node("product_url", url)}` +
    `${node("image_url", image)}${node("sale_price", salePrice)}` +
    `${node("stock", Math.max(0, Math.trunc(v.inventoryQuantity || 0)))}` +
    `${node("description", p.descriptionHtml || "")}` +
    `${ean ? node("ean", ean) : ""}${node("vat", vatPercent)}` +
    `${node("handling_time", handlingDays)}</product>`;
}

async function shopifyToken(store: string, clientId: string, clientSecret: string): Promise<string> {
  const response = await fetch(`https://${store}/admin/oauth/access_token`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ grant_type: "client_credentials", client_id: clientId, client_secret: clientSecret }),
    cache: "no-store", signal: AbortSignal.timeout(30_000),
  });
  if (!response.ok) throw new Error(`Shopify OAuth HTTP ${response.status}`);
  const payload = await response.json();
  if (!payload.access_token) throw new Error("Missing Shopify access token");
  return payload.access_token;
}

async function page(store: string, token: string, cursor: string | null): Promise<Connection> {
  for (let attempt = 0; attempt < 6; attempt++) {
    try {
      const response = await fetch(`https://${store}/admin/api/${API_VERSION}/graphql.json`, {
        method: "POST", cache: "no-store", signal: AbortSignal.timeout(45_000),
        headers: { "Content-Type": "application/json", "X-Shopify-Access-Token": token },
        body: JSON.stringify({ query: QUERY, variables: { cursor } }),
      });
      if (response.status === 429 || response.status >= 500) throw new Error("retryable");
      if (!response.ok) throw new Error(`Shopify HTTP ${response.status}`);
      const payload = await response.json();
      if (payload.errors?.length) {
        if (payload.errors.every((error: { extensions?: { code?: string } }) =>
          error.extensions?.code === "THROTTLED")) throw new Error("retryable");
        throw new Error("Shopify GraphQL query rejected");
      }
      const connection = payload.data?.productVariants as Connection | undefined;
      if (!connection?.nodes || !connection.pageInfo) throw new Error("Incomplete Shopify response");
      return connection;
    } catch (error) {
      if (attempt === 5 || !(error instanceof Error) ||
          !(error.message === "retryable" || error.name === "TimeoutError" || error.name === "AbortError")) throw error;
      await new Promise(resolve => setTimeout(resolve, Math.min(1000 * 2 ** attempt, 15_000)));
    }
  }
  throw new Error("Shopify pagination failed");
}

export async function generateEmagXml(config: {
  store: string; clientId: string; clientSecret: string; vatPercent: number; handlingDays: number;
}) {
  const token = await shopifyToken(config.store, config.clientId, config.clientSecret);
  const seen = new Set<string>();
  const categories = new Set<string>();
  const parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<products>'];
  let cursor: string | null = null;
  let scanned = 0; let accepted = 0; let skipped = 0;
  while (true) {
    const connection = await page(config.store, token, cursor);
    for (const variant of connection.nodes) {
      if (seen.has(variant.id)) throw new Error("Duplicate Shopify variant in pagination");
      seen.add(variant.id);
      scanned++;
      const item = feedItem(variant, config.vatPercent, config.handlingDays);
      if (!item) { skipped++; continue; }
      parts.push(item); accepted++;
      categories.add(variant.product.category?.name?.trim() || variant.product.productType?.trim() || "");
      if (accepted > MAX_ITEMS || categories.size > MAX_CATEGORIES) throw new Error("eMAG feed limits exceeded");
    }
    if (!connection.pageInfo.hasNextPage) break;
    const next = connection.pageInfo.endCursor;
    if (!next || next === cursor || !connection.nodes.length) throw new Error("Incomplete Shopify pagination");
    cursor = next;
  }
  parts.push('</products>');
  if (!accepted) throw new Error("No eligible products; refusing to publish an empty feed");
  const xml = parts.join("\n");
  const bytes = Buffer.byteLength(xml, "utf8");
  if (bytes > MAX_BYTES) throw new Error("eMAG feed exceeds 100MB");
  return { xml, report: { scanned, accepted, skipped, categories: categories.size, bytes,
    sha256: createHash("sha256").update(xml).digest("hex"),
    generated_at: new Date().toISOString() } };
}
