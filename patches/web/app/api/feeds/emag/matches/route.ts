import { get, put } from "@vercel/blob";

export const runtime = "nodejs";
const REGISTRY = "feeds/emag-bg/offer-registry.json";
const RESULT = "feeds/emag-bg/mapping-result.json";
type Offer = { offerId: string; ean: string; sku: string; pnk: string };
type Match = { ean: string; shopify_id: string; sku: string; status: string; title: string };

async function read(path: string) {
  const blob = await get(path, { access: "private", useCache: false });
  return blob?.statusCode === 200 ? new Response(blob.stream).json() : null;
}

export async function GET() {
  try {
    const [registry, result] = await Promise.all([read(REGISTRY), read(RESULT)]);
    if (!registry || !result || registry.uploadedAt !== result.registryUploadedAt)
      return Response.json({ ready: false });
    return Response.json({ ready: true, ...result.summary, checkedAt: result.checkedAt,
      examples: result.rows.filter((row: { classification: string }) => row.classification !== "matched").slice(0, 30) },
      { headers: { "Cache-Control": "private, no-store" } });
  } catch { return Response.json({ error: "Неуспешно зареждане." }, { status: 503 }); }
}

export async function POST(request: Request) {
  try {
    const content = await request.text();
    if (content.length > 2_000_000) return Response.json({ error: "Отчетът е твърде голям." }, { status: 413 });
    const payload = JSON.parse(content) as { registryUploadedAt: string; matches: Match[] };
    const registry = await read(REGISTRY);
    if (!registry || payload.registryUploadedAt !== registry.uploadedAt || !Array.isArray(payload.matches) || payload.matches.length > 20_000)
      return Response.json({ error: "Регистърът е променен или резултатът е невалиден." }, { status: 409 });
    const byEan = new Map<string, Map<string, Match>>();
    for (const match of payload.matches) {
      if (!/^\d{8,14}$/.test(match.ean) || !/^gid:\/\/shopify\/ProductVariant\/\d+$/.test(match.shopify_id) ||
          typeof match.sku !== "string" || typeof match.title !== "string" ||
          !["ACTIVE", "DRAFT", "ARCHIVED"].includes(match.status))
        return Response.json({ error: "Невалиден Shopify резултат." }, { status: 422 });
      if (!byEan.has(match.ean)) byEan.set(match.ean, new Map());
      byEan.get(match.ean)!.set(match.shopify_id, match);
    }
    const rows = (registry.offers as Offer[]).map(offer => {
      const candidates = [...(byEan.get(offer.ean)?.values() || [])];
      const classification = !offer.ean ? "missing_ean" : candidates.length === 1 ? "matched" : candidates.length > 1 ? "ambiguous" : "unmatched";
      return { offerId: offer.offerId, ean: offer.ean, emagSku: offer.sku, pnk: offer.pnk,
        classification, shopifyId: classification === "matched" ? candidates[0].shopify_id : null,
        shopifySku: classification === "matched" ? candidates[0].sku : null,
        shopifyStatus: classification === "matched" ? candidates[0].status : null };
    });
    const summary = { total: rows.length, matched: rows.filter(r => r.classification === "matched").length,
      ambiguous: rows.filter(r => r.classification === "ambiguous").length,
      missingEan: rows.filter(r => r.classification === "missing_ean").length,
      unmatched: rows.filter(r => r.classification === "unmatched").length,
      differentSku: rows.filter(r => r.classification === "matched" && r.emagSku !== r.shopifySku).length };
    const checkedAt = new Date().toISOString();
    await put(RESULT, JSON.stringify({ version: 1, registryUploadedAt: registry.uploadedAt, checkedAt, summary, rows }),
      { access: "private", addRandomSuffix: false, allowOverwrite: true, contentType: "application/json" });
    return Response.json({ ready: true, ...summary, checkedAt });
  } catch { return Response.json({ error: "Неуспешно записване на сравнението." }, { status: 503 }); }
}
