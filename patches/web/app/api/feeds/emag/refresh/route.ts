import { get, put } from "@vercel/blob";
import { generateEmagXml } from "@/lib/emagFeed";
import { EMAG_PREFIX } from "@/lib/emagDelivery";

export const runtime = "nodejs";
export const maxDuration = 300;

// Deliberately not exposed to browser UI: this operation replaces the public feed.
// Call from an authorized scheduler after the catalog/offer mappings are approved.
export async function POST(request: Request) {
  const key = process.env.EMAG_FEED_REFRESH_TOKEN;
  if (!key) return Response.json({ error: "Refresh token not configured" }, { status: 503 });
  if (request.headers.get("authorization") !== `Bearer ${key}`) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }
  const store = process.env.SHOPIFY_STORE;
  const clientId = process.env.SHOPIFY_CLIENT_ID;
  const clientSecret = process.env.SHOPIFY_CLIENT_SECRET;
  const handlingDays = Number(process.env.EMAG_HANDLING_DAYS);
  const vatPercent = Number(process.env.EMAG_VAT_PERCENT);
  if (!store || !/^[a-z0-9-]+\.myshopify\.com$/.test(store) || !clientId || !clientSecret ||
      !process.env.EMAG_HANDLING_DAYS || !Number.isInteger(handlingDays) || handlingDays < 0 || handlingDays > 60 ||
      !process.env.EMAG_VAT_PERCENT || !Number.isFinite(vatPercent) || vatPercent < 0 || vatPercent > 100) {
    return Response.json({ error: "eMAG Shopify, VAT or handling configuration incomplete" }, { status: 503 });
  }
  // Explicit release guard: a generated file must not become a live publication
  // feed before matching existing eMAG IDs and validating product categories.
  if (process.env.EMAG_FEED_PUBLISH_ENABLED !== "true") {
    return Response.json({ error: "Publishing disabled until eMAG category and ID mapping is approved" }, { status: 409 });
  }
  try {
    const { xml, report } = await generateEmagXml({ store, clientId, clientSecret, handlingDays, vatPercent });
    const pathname = `${EMAG_PREFIX}snapshots/${report.sha256}.xml`;
    await put(pathname, xml, {
      access: "private", addRandomSuffix: false, allowOverwrite: true,
      contentType: "application/xml; charset=utf-8",
    });
    const manifest = { version: 1, generated_at: report.generated_at,
      sha256: report.sha256, xml_pathname: pathname, bytes: report.bytes, items: report.accepted };
    const current = await get(EMAG_PREFIX + "current.json", { access: "private", useCache: false });
    // Optimistic update avoids overwriting a newer refresh from a second worker.
    const currentEtag = current?.statusCode === 200 ? current.headers.get("etag") : null;
    await put(EMAG_PREFIX + "current.json", JSON.stringify(manifest), {
      access: "private", addRandomSuffix: false,
      allowOverwrite: Boolean(currentEtag),
      ...(currentEtag ? { ifMatch: currentEtag } : {}),
      contentType: "application/json",
    });
    return Response.json({ ok: true, ...report, url: "https://hub.homesector.bg/feeds/emag/BG.xml" });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "Feed refresh failed" }, { status: 502 });
  }
}
