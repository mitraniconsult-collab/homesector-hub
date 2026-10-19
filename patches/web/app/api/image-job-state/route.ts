import { get, put, BlobPreconditionFailedError } from "@vercel/blob";
import { timingSafeEqual } from "node:crypto";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
const path = "jobs/product-images-v1.json";
function authorized(req: Request) {
  const token = process.env.HUB_WORKER_TOKEN;
  const expected = Buffer.from(`Bearer ${token}`);
  const actual = Buffer.from(req.headers.get("authorization") || "");
  return !!token && expected.length === actual.length && timingSafeEqual(expected, actual);
}
export async function GET(req: Request) {
  if (!authorized(req)) return Response.json({ error: "Unauthorized" }, { status: 401 });
  try {
    const data = await get(path, { access: "private", useCache: false });
    if (!data || data.statusCode !== 200) return Response.json({ error: "Missing" }, { status: 404 });
    return new Response(data.stream, { headers: { "content-type": "application/json", "cache-control": "private, no-store", etag: data.blob.etag, "x-hub-state-version": data.blob.etag } });
  } catch { return Response.json({ error: "State unavailable" }, { status: 503 }); }
}
export async function PUT(req: Request) {
  if (!authorized(req)) return Response.json({ error: "Unauthorized" }, { status: 401 });
  const match = req.headers.get("if-match");
  if (!match) return Response.json({ error: "Conditional write required" }, { status: 428 });
  try {
    const text = await req.text();
    if (Buffer.byteLength(text) > 4_000_000) return Response.json({ error: "State too large" }, { status: 413 });
    const state = JSON.parse(text);
    if (state.version !== 1 || typeof state.id !== "string" || !Array.isArray(state.items)) return Response.json({ error: "Invalid state" }, { status: 400 });
    // '*' means create-only; existing state is replaced only with its exact ETag.
    if (match === "*" && await get(path, { access: "private", useCache: false })) return Response.json({ error: "Conflict" }, { status: 409 });
    const blob = await put(path, text, { access: "private", addRandomSuffix: false, allowOverwrite: match !== "*", ...(match !== "*" ? { ifMatch: match } : {}), contentType: "application/json" });
    return Response.json({ ok: true }, { headers: { etag: blob.etag, "cache-control": "no-store" } });
  } catch (error) {
    if (error instanceof BlobPreconditionFailedError || (error instanceof Error && /already exists/i.test(error.message))) return Response.json({ error: "Conflict" }, { status: 409 });
    return Response.json({ error: "State write failed" }, { status: 503 });
  }
}
