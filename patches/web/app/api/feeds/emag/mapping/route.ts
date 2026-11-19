import { get, put } from "@vercel/blob";
import ExcelJS from "exceljs";

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
    const workbook = new ExcelJS.Workbook();
    await workbook.xlsx.load(Buffer.from(await file.arrayBuffer()) as never);
    const sheet = workbook.getWorksheet("оферти");
    if (!sheet || sheet.getRow(3).getCell(7).text.trim() !== "vendor_ext_id" ||
        sheet.getRow(3).getCell(4).text.trim() !== "part_number_key" ||
        sheet.getRow(3).getCell(5).text.trim() !== "part_number")
      return Response.json({ error: "Файлът не е eMAG експорт на оферти." }, { status: 400 });
    const offers: Offer[] = [];
    const ids = new Set<string>();
    for (let index = 6; index <= sheet.rowCount; index++) {
      const row = sheet.getRow(index);
      const id = row.getCell(7).text.trim();
      if (!id) continue;
      const offer = { offerId: id, pnk: row.getCell(4).text.trim(),
        sku: row.getCell(5).text.trim(), ean: row.getCell(6).text.trim(),
        status: row.getCell(14).text.trim() };
      if (!/^\d+$/.test(id) || !offer.pnk || !offer.sku || ids.has(id))
        return Response.json({ error: `Невалидна или дублирана оферта на ред ${index}.` }, { status: 422 });
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
  } catch { return Response.json({ error: "Неуспешен импорт. Проверете файла и хранилището." }, { status: 503 }); }
}
