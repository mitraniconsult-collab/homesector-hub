import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const { brand, title, text, sourceUrl } = await request.json();
  if (![brand, title, sourceUrl].every((v) => typeof v === "string") || !/^https:\/\//.test(sourceUrl) || title.length > 1000 || String(text || "").length > 5000) {
    return NextResponse.json({ error: "Невалидно съдържание." }, { status: 400 });
  }
  const key = process.env.OPENAI_API_KEY;
  if (!key) return NextResponse.json({ error: "Липсва OPENAI_API_KEY във Vercel. AI черновите не са активирани." }, { status: 503 });

  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: process.env.OPENAI_SOCIAL_MODEL || "gpt-4.1-mini",
      store: false,
      instructions: "Ти си редактор на социалните канали на Homesector.bg. Пренапиши на естествен, грамотен български кратък пост (до 650 знака) по предоставения източник. Запази точните продуктови и брандови имена; не измисляй наличности, цени, отстъпки или характеристики. Не превеждай буквално и не твърди, че Homesector продава конкретен продукт без потвърждение. Завърши с до 3 смислени хаштага. Върни само текста на поста.",
      input: `Марка: ${brand}\nОригинално заглавие: ${title}\nОригинален текст: ${text || ""}\nИзточник: ${sourceUrl}`,
      max_output_tokens: 500,
    }),
    signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) return NextResponse.json({ error: `AI услугата върна ${response.status}.` }, { status: 502 });
  const data = await response.json();
  const draft = (data.output || []).flatMap((o: { content?: { type: string; text?: string }[] }) => o.content || []).filter((c: { type: string }) => c.type === "output_text").map((c: { text?: string }) => c.text || "").join("\n").trim();
  if (!draft) return NextResponse.json({ error: "AI не върна текст." }, { status: 502 });
  return NextResponse.json({ draft });
}
