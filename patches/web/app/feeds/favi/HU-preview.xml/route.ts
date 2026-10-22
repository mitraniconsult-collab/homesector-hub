import { serveFaviHuPreview } from "@/lib/faviHUDelivery";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 120;
export async function GET(request: Request) {
  return serveFaviHuPreview(request, "xml");
}
