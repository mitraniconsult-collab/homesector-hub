import { serveEmagFeed } from "@/lib/emagDelivery";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export async function GET(request: Request) {
  return serveEmagFeed(request);
}
