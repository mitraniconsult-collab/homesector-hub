import { get } from "@vercel/blob";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const manifestPath = "feeds/favi-ro/current-preview.json";

export async function GET() {
  try {
    const pointer = await get(manifestPath, { access: "private", useCache: false });
    if (!pointer || pointer.statusCode !== 200) return new Response("No RO preview", { status: 404 });
    const manifest = await new Response(pointer.stream).json();
    const pathname = manifest.xml_pathname;
    if (manifest.market !== "RO" || manifest.purpose !== "partial_preview" ||
        typeof pathname !== "string" ||
        !/^feeds\/favi-ro\/snapshots\/[a-f0-9]{64}\.xml$/.test(pathname)) {
      return new Response("Invalid RO preview pointer", { status: 503 });
    }
    const blob = await get(pathname, { access: "private", useCache: false });
    if (!blob || blob.statusCode !== 200) return new Response("RO preview unavailable", { status: 503 });
    return new Response(blob.stream, { headers: {
      "content-type": "application/xml; charset=utf-8",
      "cache-control": "public, max-age=60, no-transform",
      "x-feed-items": String(manifest.items),
      "x-feed-sha256": manifest.sha256,
    } });
  } catch {
    return new Response("RO preview unavailable", { status: 503 });
  }
}
