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
    const entries = Array.isArray(payload.feeds) ? payload.feeds : [];
    const publicHub = "https://hub.homesector.bg";
    const previews = await Promise.all(["BG", "GR", "RO", "HU"].map(async market => {
      const reportUrl = new URL(`/feeds/favi/${market}-preview-report.json`, publicHub);
      try {
        const reportResponse = await fetch(reportUrl, {
          cache: "no-store", signal: AbortSignal.timeout(10000),
        });
        if (!reportResponse.ok) return null;
        const report = await reportResponse.json();
        const count = Number(market === "BG" ? report.id_migration_candidate_items : report.xml_items);
        const generated = Date.parse(report.generated_at);
        if (report.market !== market || report.source_complete !== true ||
            !Number.isSafeInteger(count) || count <= 0 || !Number.isFinite(generated)) {
          return null;
        }
        return { channel: "favi", market,
          status: Date.now() - generated > 30 * 3600_000 ? "preview_stale" : "unpublished_preview",
          product_count: count, last_updated: report.generated_at,
          xml_url: new URL(`/feeds/favi/${market}-preview.xml`, publicHub).toString(),
          report_url: reportUrl.toString(),
        };
      } catch { return null; }
    }));
    for (const preview of previews) {
      if (!preview) continue;
      const index = entries.findIndex((feed: {channel: string; market: string}) =>
        feed.channel === "favi" && feed.market === preview.market);
      if (index >= 0) entries[index] = preview;
    }
    return NextResponse.json({ ...payload, feeds: entries }, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json({ error: "Worker unreachable" }, { status: 502 });
  }
}
