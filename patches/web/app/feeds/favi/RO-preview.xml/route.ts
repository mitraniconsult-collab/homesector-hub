import { serveFaviRoPreview } from "@/lib/faviRODelivery";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 120;
export async function GET(request: Request) {
  return serveFaviRoPreview(request, "xml");
}
