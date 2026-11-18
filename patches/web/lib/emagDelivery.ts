import { get } from "@vercel/blob";
import { EMAG_SHARDS } from "@/lib/emagFeed";

export const EMAG_PREFIX = "feeds/emag-bg/";
type FeedPart = { index: number; sha256: string; xml_pathname: string;
  bytes: number; items: number; categories: number };
type Manifest = { version: 2; generated_at: string; shards: FeedPart[] };

export function emagFeedUrl(index: number): string {
  if (!Number.isInteger(index) || index < 1 || index > EMAG_SHARDS) throw new Error("Invalid eMAG shard");
  return `https://hub.homesector.bg/feeds/emag/BG${index === 1 ? "" : `-${String(index).padStart(2, "0")}`}.xml`;
}

export async function serveEmagFeed(request: Request, index = 1) {
  if (!Number.isInteger(index) || index < 1 || index > EMAG_SHARDS) return new Response(null, { status: 404 });
  try {
    const pointer = await get(EMAG_PREFIX + "current.json", {
      access: "private", useCache: false,
      headers: { "Accept-Encoding": "identity" },
    });
    if (!pointer || pointer.statusCode !== 200) {
      return Response.json({ error: "eMAG feed has not been published yet" }, { status: 503 });
    }
    const manifest = await new Response(pointer.stream).json() as Manifest;
    const validPart = (part: FeedPart) => part && Number.isInteger(part.index) &&
      part.index >= 1 && part.index <= EMAG_SHARDS && /^[a-f0-9]{64}$/.test(part.sha256) &&
      part.xml_pathname === EMAG_PREFIX + "snapshots/" + part.sha256 + ".xml" &&
      Number.isInteger(part.items) && part.items >= 1 && part.items <= 100_000 &&
      Number.isInteger(part.categories) && part.categories >= 1 && part.categories <= 150 &&
      Number.isInteger(part.bytes) && part.bytes >= 1 && part.bytes <= 100_000_000;
    if (manifest.version !== 2 || !Array.isArray(manifest.shards) ||
        manifest.shards.length !== EMAG_SHARDS ||
        !manifest.shards.every((part, i) => validPart(part) && part.index === i + 1) ||
        !Number.isFinite(Date.parse(manifest.generated_at))) {
      return Response.json({ error: "Invalid eMAG feed manifest" }, { status: 503 });
    }
    const part = manifest.shards[index - 1];
    const etag = '"sha256-' + part.sha256 + '"';
    const headers: Record<string, string> = {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=60, s-maxage=60, no-transform",
      "ETag": etag,
      "Last-Modified": new Date(manifest.generated_at).toUTCString(),
      "X-Feed-Items": String(part.items),
      "X-Feed-Categories": String(part.categories),
      "X-Content-Type-Options": "nosniff", "X-Robots-Tag": "noindex",
    };
    if (request.headers.get("if-none-match") === etag) return new Response(null, { status: 304, headers });
    const blob = await get(part.xml_pathname, {
      access: "private", headers: { "Accept-Encoding": "identity" },
    });
    if (!blob || blob.statusCode !== 200) {
      return Response.json({ error: "eMAG feed snapshot unavailable" }, { status: 503 });
    }
    headers["Content-Length"] = String(part.bytes);
    return new Response(blob.stream, { headers });
  } catch {
    return Response.json({ error: "eMAG feed storage unavailable" }, {
      status: 503, headers: { "Cache-Control": "no-store" },
    });
  }
}
