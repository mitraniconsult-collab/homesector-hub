import { NextRequest, NextResponse } from "next/server";
import { configured, validCredentials, sameOrigin, sessionSeal, SESSION_COOKIE, SESSION_TTL, safeReturn } from "@/lib/hubAuth";
export const runtime = "nodejs";
// Best-effort local throttle supplements a randomly generated, high-entropy password.
const attempts = new Map<string, { count: number; until: number }>();
export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) return new Response(null, { status: 403 });
  if (!configured()) return new Response("Входът не е конфигуриран.", { status: 503 });
  if (Number(request.headers.get("content-length") || 0) > 4096) return new Response(null, { status: 413 });
  const ip = request.headers.get("x-vercel-forwarded-for") || request.headers.get("x-forwarded-for") || "unknown";
  const now = Date.now();
  for (const [key, entry] of attempts) if (entry.until < now) attempts.delete(key);
  const entry = attempts.get(ip) || { count: 0, until: now + 15 * 60 * 1000 };
  if (entry.count >= 10) return new Response("Твърде много опити. Опитайте след 15 минути.", { status: 429, headers: { "Retry-After": "900" } });
  entry.count++; attempts.set(ip, entry);
  let form: FormData;
  try { form = await request.formData(); } catch { return new Response(null, { status: 400 }); }
  const next = safeReturn(String(form.get("next") || ""));
  if (!await validCredentials(String(form.get("username") || ""), String(form.get("password") || ""))) {
    const url = new URL("/login", request.url); url.searchParams.set("error", "credentials"); url.searchParams.set("next", next);
    return NextResponse.redirect(url, 303);
  }
  attempts.delete(ip);
  const response = NextResponse.redirect(new URL(next, request.url), 303);
  response.cookies.set(SESSION_COOKIE, await sessionSeal(), { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "strict", path: "/", maxAge: SESSION_TTL });
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}
