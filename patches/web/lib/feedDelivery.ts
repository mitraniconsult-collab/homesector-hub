import { get } from "@vercel/blob";

const prefix = "feeds/google-bg/";
const digest = /^[a-f0-9]{64}$/;
type Manifest = {
  version: number; channel: string; market: string; purpose: string;
  generated_at: string; items: number; bytes: number; sha256: string;
  xml_pathname: string; comparison_pathname: string; comparison_sha256: string;
};

export async function serveFeed(request: Request, kind: "xml" | "comparison") {
  try {
    const pointer = await get(prefix + "current.json", {
      access: "private", useCache: false, headers: { "Accept-Encoding": "identity" },
    });
    if (!pointer || pointer.statusCode !== 200) {
      return Response.json({ error: "Feed snapshot is not published yet" }, { status: 503 });
    }
    const manifest: Manifest = await new Response(pointer.stream).json();
    if (manifest.version !== 1 || manifest.channel !== "google" || manifest.market !== "BG"
        || manifest.purpose !== "comparison" || !digest.test(manifest.sha256)
        || !digest.test(manifest.comparison_sha256)
        || !Number.isInteger(manifest.items) || manifest.items < 1
        || !Number.isInteger(manifest.bytes) || manifest.bytes < 1 || manifest.bytes > 250 * 1024 * 1024
        || !Number.isFinite(Date.parse(manifest.generated_at))
        || manifest.xml_pathname !== prefix + "snapshots/" + manifest.sha256 + ".xml"
        || manifest.comparison_pathname !== prefix + "snapshots/" + manifest.comparison_sha256 + ".json") {
      return Response.json({ error: "Feed snapshot metadata is invalid" }, { status: 503 });
    }
    const checksum = kind === "xml" ? manifest.sha256 : manifest.comparison_sha256;
    const etag = '"sha256-' + checksum + '"';
    const headers: Record<string, string> = {
      "Content-Type": kind === "xml" ? "application/xml; charset=utf-8" : "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=60, s-maxage=60, no-transform",
      "ETag": etag, "Last-Modified": new Date(manifest.generated_at).toUTCString(),
      "X-Content-SHA256": checksum, "X-Feed-Items": String(manifest.items),
      "X-Feed-Purpose": "comparison", "X-Content-Type-Options": "nosniff",
      "X-Robots-Tag": "noindex",
    };
    if (request.headers.get("if-none-match") === etag) {
      return new Response(null, { status: 304, headers });
    }
    const path = kind === "xml" ? manifest.xml_pathname : manifest.comparison_pathname;
    const blob = await get(path, { access: "private", headers: { "Accept-Encoding": "identity" } });
    if (!blob || blob.statusCode !== 200) {
      return Response.json({ error: "Feed snapshot is unavailable" }, { status: 503 });
    }
    if (kind === "xml") headers["Content-Length"] = String(manifest.bytes);
    return new Response(blob.stream, { headers });
  } catch {
    return Response.json({ error: "Feed storage is temporarily unavailable" }, {
      status: 503, headers: { "Cache-Control": "no-store" },
    });
  }
}
