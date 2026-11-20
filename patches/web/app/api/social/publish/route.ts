import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const { message, sourceUrl } = await request.json();
  if (typeof message !== "string" || !message.trim() || message.length > 3000 || typeof sourceUrl !== "string" || !/^https:\/\//.test(sourceUrl)) {
    return NextResponse.json({ error: "Невалидна публикация." }, { status: 400 });
  }
  const pageId = process.env.META_PAGE_ID;
  const token = process.env.META_PAGE_ACCESS_TOKEN;
  if (!pageId || !token) return NextResponse.json({ error: "Липсват META_PAGE_ID и META_PAGE_ACCESS_TOKEN във Vercel." }, { status: 503 });
  const response = await fetch(`https://graph.facebook.com/v22.0/${encodeURIComponent(pageId)}/feed`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ access_token: token, message: `${message.trim()}\n\nИзточник: ${sourceUrl}` }),
    signal: AbortSignal.timeout(20000),
  });
  const data = await response.json();
  if (!response.ok || !data.id) return NextResponse.json({ error: data.error?.message || "Meta отказа публикуването." }, { status: 502 });
  return NextResponse.json({ id: data.id, channel: "facebook" });
}
