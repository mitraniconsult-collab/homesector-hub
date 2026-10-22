import { get } from "@vercel/blob";

const prefix = "feeds/favi-hu/";
const digest = /^[a-f0-9]{64}$/;
type PreviewManifest = {
  version: number; channel: string; market: string; purpose: string;
  generated_at: string; items: number; bytes: number; sha256: string;
  report_sha256: string; xml_pathname: string; report_pathname: string;
  approved_by_favi: boolean; destination_subscriptions_changed: boolean;
};

export async function serveFaviHuPreview(request: Request, kind: "xml" | "report") {
  try {
    const pointer = await get(prefix + "current-preview.json", {
      access: "private", useCache: false, headers: { "Accept-Encoding": "identity" },
    });
    if (!pointer || pointer.statusCode !== 200) {
      return Response.json({ error: "Hungarian preview is not ready" }, { status: 503 });
    }
    const manifest: PreviewManifest = await new Response(pointer.stream).json();
    if (manifest.version !== 1 || manifest.channel !== "favi" || manifest.market !== "HU"
      || manifest.purpose !== "partial_preview" || manifest.approved_by_favi !== false
      || manifest.destination_subscriptions_changed !== false
      || !digest.test(manifest.sha256) || !digest.test(manifest.report_sha256)
      || !Number.isInteger(manifest.items) || manifest.items < 1
      || !Number.isInteger(manifest.bytes) || manifest.bytes < 1 || manifest.bytes > 250 * 1024 * 1024
      || !Number.isFinite(Date.parse(manifest.generated_at))
      || manifest.xml_pathname !== prefix + "snapshots/" + manifest.sha256 + ".xml"
      || manifest.report_pathname !== prefix + "snapshots/" + manifest.report_sha256 + ".json") {
      return Response.json({ error: "Hungarian preview metadata is invalid" }, { status: 503 });
    }
    const checksum = kind === "xml" ? manifest.sha256 : manifest.report_sha256;
    const etag = '"sha256-' + checksum + '"';
    const headers: Record<string, string> = {
      "Content-Type": kind === "xml" ? "application/xml; charset=utf-8" : "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=60, s-maxage=60, no-transform",
      "ETag": etag, "Last-Modified": new Date(manifest.generated_at).toUTCString(),
      "X-Content-SHA256": checksum, "X-Feed-Items": String(manifest.items),
      "X-Feed-Purpose": "partial_preview", "X-Content-Type-Options": "nosniff",
      "X-Robots-Tag": "noindex",
    };
    if (request.headers.get("if-none-match") === etag) {
      return new Response(null, { status: 304, headers });
    }
    const path = kind === "xml" ? manifest.xml_pathname : manifest.report_pathname;
    const blob = await get(path, { access: "private", headers: { "Accept-Encoding": "identity" } });
    if (!blob || blob.statusCode !== 200) {
      return Response.json({ error: "Hungarian preview snapshot is unavailable" }, { status: 503 });
    }
    if (kind === "xml") headers["Content-Length"] = String(manifest.bytes);
    return new Response(blob.stream, { headers });
  } catch {
    return Response.json({ error: "Feed storage is temporarily unavailable" }, {
      status: 503, headers: { "Cache-Control": "no-store" },
    });
  }
}
