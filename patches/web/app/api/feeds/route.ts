import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const base = process.env.HUB_WORKER_URL;
  const token = process.env.HUB_WORKER_TOKEN;
  if (!base || !token) {
    return NextResponse.json({ error: "Worker connection not configured" }, { status: 503 });
  }
  try {
    const response = await fetch(new URL("/feeds/status", base), {
      headers: { Authorization: "Bearer " + token },
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) {
      return NextResponse.json({ error: "Worker feed status unavailable" }, { status: 502 });
    }
    const payload = await response.json();
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Worker unreachable" }, { status: 502 });
  }
}
