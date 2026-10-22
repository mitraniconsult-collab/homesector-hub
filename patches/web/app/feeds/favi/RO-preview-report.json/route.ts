import { get } from "@vercel/blob";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  try {
    const pointer = await get("feeds/favi-ro/current-preview.json", {
      access: "private", useCache: false,
    });
    if (!pointer || pointer.statusCode !== 200) return new Response("No RO report", { status: 404 });
    const manifest = await new Response(pointer.stream).json();
    const pathname = manifest.report_pathname;
    if (manifest.market !== "RO" || manifest.purpose !== "partial_preview" ||
        typeof pathname !== "string" ||
        !/^feeds\/favi-ro\/snapshots\/[a-f0-9]{64}\.json$/.test(pathname)) {
      return new Response("Invalid RO report pointer", { status: 503 });
    }
    const blob = await get(pathname, { access: "private", useCache: false });
    if (!blob || blob.statusCode !== 200) return new Response("RO report unavailable", { status: 503 });
    return new Response(blob.stream, { headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "public, max-age=60, no-transform",
    } });
  } catch {
    return new Response("RO report unavailable", { status: 503 });
  }
}
