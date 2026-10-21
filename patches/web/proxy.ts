import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE, validSession, workerRequest, sameOrigin } from "@/lib/hubAuth";

export async function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;
  // Only published XML feeds are public; diagnostic reports remain private.
  const feed = ["/feeds/google/BG.xml", "/feeds/favi/GR-preview.xml"].includes(path) && ["GET", "HEAD"].includes(request.method);
  if (feed || workerRequest(request)) return NextResponse.next();
  const publicAuth = path === "/login" || path === "/api/auth/login";
  if (!publicAuth && !await validSession(request.cookies.get(SESSION_COOKIE)?.value)) {
    if (path.startsWith("/api/")) return NextResponse.json({ error: "Необходим е вход в Hub." }, { status: 401, headers: { "Cache-Control": "private, no-store" } });
    const url = new URL("/login", request.url);
    url.searchParams.set("next", path + request.nextUrl.search);
    return NextResponse.redirect(url);
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(request.method) && !sameOrigin(request)) {
    return NextResponse.json({ error: "Невалидна заявка." }, { status: 403 });
  }
  const response = NextResponse.next();
  response.headers.set("Cache-Control", "private, no-store");
  response.headers.set("X-Robots-Tag", "noindex, nofollow");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Referrer-Policy", "same-origin");
  return response;
}
export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
