import { serveFaviGrPreview } from "@/lib/faviGRDelivery";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 120;
export async function GET(request: Request) {
  return serveFaviGrPreview(request, "report");
}
