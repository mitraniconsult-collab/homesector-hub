import { get, put } from "@vercel/blob";
import * as XLSX from "xlsx";

export const runtime = "nodejs";
export const maxDuration = 60;
const PATH = "feeds/emag-bg/offer-registry.json";
type Offer = { offerId: string; pnk: string; sku: string; ean: string; status: string };

export async function GET() {
  try {
    const saved = await get(PATH, { access: "private", useCache: false });
    if (!saved || saved.statusCode !== 200) return Response.json({ imported: false });
    const value = await new Response(saved.stream).json();
    return Response.json({ imported: true, uploadedAt: value.uploadedAt, count: value.offers.length,
      active: value.offers.filter((offer: Offer) => offer.status === "1").length,
      examples: value.offers.slice(0, 8) }, { headers: { "Cache-Control": "private, no-store" } });
  } catch { return Response.json({ error: "Регистърът не може да бъде прочетен." }, { status: 503 }); }
}

export async function POST(request: Request) {
  const body = await request.formData().catch(() => null);
  const file = body?.get("file");
  if (!(file instanceof File) || !/\.xlsx$/i.test(file.name) || file.size > 8_000_000 || file.size < 1000)
    return Response.json({ error: "Изберете валиден eMAG XLSX файл до 8 MB." }, { status: 400 });
  try {
    const workbook = XLSX.read(Buffer.from(await file.arrayBuffer()), { type: "buffer" });
    const sheet = workbook.Sheets["оферти"];
    const rows = sheet ? XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1, defval: "", raw: false }) : [];
    const field = (row: unknown[], index: number) => String(row?.[index] ?? "").trim();
    if (!sheet || field(rows[2], 6) !== "vendor_ext_id" ||
        field(rows[2], 3) !== "part_number_key" ||
        field(rows[2], 4) !== "part_number")
      return Response.json({ error: "Файлът не е eMAG експорт на оферти." }, { status: 400 });
    const offers: Offer[] = [];
    const ids = new Set<string>();
    for (let index = 5; index < rows.length; index++) {
      const row = rows[index];
      const id = field(row, 6);
      if (!id) continue;
      const offer = { offerId: id, pnk: field(row, 3),
        sku: field(row, 4), ean: field(row, 5),
        status: field(row, 13) };
      if (!/^\d+$/.test(id) || !offer.pnk || !offer.sku || ids.has(id))
        return Response.json({ error: `Невалидна или дублирана оферта на ред ${index + 1}.` }, { status: 422 });
      ids.add(id); offers.push(offer);
    }
    if (!offers.length || offers.length > 100_000)
      return Response.json({ error: "Няма валидни оферти." }, { status: 422 });
    const uploadedAt = new Date().toISOString();
    await put(PATH, JSON.stringify({ version: 1, uploadedAt, offers }), {
      access: "private", allowOverwrite: true, addRandomSuffix: false, contentType: "application/json",
    });
    return Response.json({ imported: true, uploadedAt, count: offers.length,
      active: offers.filter(offer => offer.status === "1").length });
  } catch (error) {
    console.error("eMAG registry import failed", error instanceof Error ? error.message : "Unknown error");
    return Response.json({ error: "Неуспешен импорт. Ако файлът е валиден, проверете настройката на Blob хранилището." }, { status: 503 });
  }
}
