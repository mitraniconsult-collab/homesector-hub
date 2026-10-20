import { serveFeed } from "@/lib/feedDelivery";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 120;
export async function GET(request: Request) {
  return serveFeed(request, "xml");
}
