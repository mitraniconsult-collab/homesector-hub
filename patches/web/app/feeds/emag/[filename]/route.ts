import { serveEmagFeed } from "@/lib/emagDelivery";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request, context: { params: Promise<{ filename: string }> }) {
  const { filename } = await context.params;
  const match = /^BG-(0[2-8])\.xml$/.exec(filename);
  if (!match) return new Response(null, { status: 404 });
  return serveEmagFeed(request, Number(match[1]));
}
