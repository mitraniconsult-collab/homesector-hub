import { get } from "@vercel/blob";

export const EMAG_PREFIX = "feeds/emag-bg/";
type Manifest = { version: 1; generated_at: string; sha256: string;
  xml_pathname: string; bytes: number; items: number };

export async function serveEmagFeed(request: Request) {
  try {
    const pointer = await get(EMAG_PREFIX + "current.json", {
      access: "private", useCache: false,
      headers: { "Accept-Encoding": "identity" },
    });
    if (!pointer || pointer.statusCode !== 200) {
      return Response.json({ error: "eMAG feed has not been published yet" }, { status: 503 });
    }
    const manifest = await new Response(pointer.stream).json() as Manifest;
    if (manifest.version !== 1 || !/^[a-f0-9]{64}$/.test(manifest.sha256) ||
        manifest.xml_pathname !== EMAG_PREFIX + "snapshots/" + manifest.sha256 + ".xml" ||
        !Number.isInteger(manifest.items) || manifest.items < 1 || manifest.items > 100_000 ||
        !Number.isInteger(manifest.bytes) || manifest.bytes < 1 || manifest.bytes > 100_000_000 ||
        !Number.isFinite(Date.parse(manifest.generated_at))) {
      return Response.json({ error: "Invalid eMAG feed manifest" }, { status: 503 });
    }
    const etag = '"sha256-' + manifest.sha256 + '"';
    const headers: Record<string, string> = {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=60, s-maxage=60, no-transform",
      "ETag": etag,
      "Last-Modified": new Date(manifest.generated_at).toUTCString(),
      "X-Feed-Items": String(manifest.items),
      "X-Content-Type-Options": "nosniff", "X-Robots-Tag": "noindex",
    };
    if (request.headers.get("if-none-match") === etag) return new Response(null, { status: 304, headers });
    const blob = await get(manifest.xml_pathname, {
      access: "private", headers: { "Accept-Encoding": "identity" },
    });
    if (!blob || blob.statusCode !== 200) {
      return Response.json({ error: "eMAG feed snapshot unavailable" }, { status: 503 });
    }
    headers["Content-Length"] = String(manifest.bytes);
    return new Response(blob.stream, { headers });
  } catch {
    return Response.json({ error: "eMAG feed storage unavailable" }, {
      status: 503, headers: { "Cache-Control": "no-store" },
    });
  }
}
