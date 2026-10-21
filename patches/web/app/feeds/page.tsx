"use client";

import { useCallback, useEffect, useState } from "react";

type FaviReport = {
  status?: string;
  xml_items?: number;
  candidate_rows?: number;
  reviewed_category_products?: number;
  greek_published_products?: number;
  greek_published_variants?: number;
  mapped_category_products?: number;
  verified_market_url_products?: number;
  localized_copy_products_in_mapped_categories?: number;
  approved_by_favi?: boolean;
  published?: boolean;
};
type GoogleReport = {
  status?: string;
  homesector_items?: number;
  feedhub_items?: number;
  matched_variants?: number;
  only_feedhub?: number;
  only_homesector?: number;
};

const links = {
  google: { xml: "/feeds/google/BG.xml", report: "/feeds/google/BG-comparison.json" },
  favi: { xml: "/feeds/favi/GR-preview.xml", report: "/feeds/favi/GR-preview-report.json" },
};

export default function FeedsPage() {
  const [google, setGoogle] = useState<GoogleReport | null>(null);
  const [favi, setFavi] = useState<FaviReport | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      fetch(links.google.report, { cache: "no-store" }).then(async response => {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json() as Promise<GoogleReport>;
      }),
      fetch(links.favi.report, { cache: "no-store" }).then(async response => {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json() as Promise<FaviReport>;
      }),
    ]);
    const failures: Record<string, string> = {};
    if (results[0].status === "fulfilled") setGoogle(results[0].value);
    else { setGoogle(null); failures.google = "Отчетът временно не е достъпен."; }
    if (results[1].status === "fulfilled") setFavi(results[1].value);
    else { setFavi(null); failures.favi = "Отчетът временно не е достъпен."; }
    setErrors(failures);
    setLoading(false);
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  return <>
    <div className="pageHead">
      <div><h1>Feeds</h1><p>Фийдове по канал и пазар: преглед на състоянието, XML и отчетите.</p></div>
      <button className="btn secondary" type="button" onClick={() => void refresh()} disabled={loading}>{loading ? "Проверява…" : "Обнови статусите"}</button>
    </div>
    <div className="stack" aria-live="polite">
      <section className="card" aria-labelledby="google-bg-title">
        <div className="sectionTitle" style={{ margin: "0 0 12px" }}>
          <h2 id="google-bg-title">Google Shopping · България</h2>
          <span className="badge">Публикуван XML</span>
        </div>
        <p className="muted">Собственият фийд и сравнението му с Feedhub.</p>
        {google && <p>Наши варианти: <strong>{google.homesector_items?.toLocaleString("bg-BG") ?? "—"}</strong> · Feedhub: <strong>{google.feedhub_items?.toLocaleString("bg-BG") ?? "—"}</strong> · Съвпадащи: <strong>{google.matched_variants?.toLocaleString("bg-BG") ?? "—"}</strong></p>}
        {errors.google && <p role="alert" className="notice">{errors.google}</p>}
        <div className="actions" style={{ marginTop: 16 }}>
          <a className="btn primary" href={links.google.xml} target="_blank" rel="noopener noreferrer">Отвори XML</a>
          <a className="btn secondary" href={links.google.report} target="_blank" rel="noopener noreferrer">Сравнение с Feedhub</a>
        </div>
      </section>
      <section className="card" aria-labelledby="favi-gr-title">
        <div className="sectionTitle" style={{ margin: "0 0 12px" }}>
          <h2 id="favi-gr-title">FAVI · Гърция</h2>
          <span className="badge warn">Частичен преглед</span>
        </div>
        <p className="muted">Пробен гръцки фийд. Цветовите варианти са свързани към общ продукт.</p>
        {favi && <>
          <p>Варианти в XML: <strong>{favi.xml_items?.toLocaleString("bg-BG") ?? "—"}</strong> · Активни продукти за GR: <strong>{favi.greek_published_products?.toLocaleString("bg-BG") ?? "—"}</strong></p>
          <p className="muted">Варианти в Shopify за GR: {favi.greek_published_variants?.toLocaleString("bg-BG") ?? "—"} · С проверена категория: {(favi.mapped_category_products ?? favi.reviewed_category_products)?.toLocaleString("bg-BG") ?? "—"} · С проверен адрес: {favi.verified_market_url_products?.toLocaleString("bg-BG") ?? "—"} · С гръцко заглавие и описание сред категоризираните: {favi.localized_copy_products_in_mapped_categories?.toLocaleString("bg-BG") ?? "—"}</p>
        </>}
        <div className="notice" style={{ marginTop: 14 }}>Това е частичен преглед. Още не е одобрен от FAVI и не е подаден към тях. Не използвайте този URL като производствен фийд.</div>
        {errors.favi && <p role="alert" className="notice">{errors.favi}</p>}
        <div className="actions" style={{ marginTop: 16 }}>
          <a className="btn primary" href={links.favi.xml} target="_blank" rel="noopener noreferrer">Отвори XML прегледа</a>
          <a className="btn secondary" href={links.favi.report} target="_blank" rel="noopener noreferrer">Отчет за проверка</a>
        </div>
      </section>
    </div>
    <p className="muted" style={{ marginTop: 18 }}>Тук се виждат наличните фийдове и отчетите им. Стартиране на генерация, промяна на правила и подаване към каналите ще се добавят след свързване с управлението на задачите.</p>
  </>;
}
