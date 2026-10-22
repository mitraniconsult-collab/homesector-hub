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
  generated_at?: string;
  source_snapshot_at?: string;
  approved_by_favi?: boolean;
  published?: boolean;
};
type GoogleReport = {
  status?: string;
  checked_at?: string;
  homesector_items?: number;
  feedhub_items?: number;
  matched_variants?: number;
  only_feedhub?: number;
  only_homesector?: number;
  xml_preflight?: {
    passed?: boolean;
    submitted?: boolean;
    issues?: { missing_description?: number };
  };
};
type RomanianReport = {
  xml_items?: number;
  romanian_published_products?: number;
  romanian_published_variants?: number;
  mapped_category_products?: number;
  verified_market_url_products?: number;
  generated_at?: string;
  source_complete?: boolean;
};

const links = {
  google: { xml: "/feeds/google/BG.xml", report: "/feeds/google/BG-comparison.json" },
  favi: { xml: "/feeds/favi/GR-preview.xml", report: "/feeds/favi/GR-preview-report.json" },
  faviRo: { xml: "/feeds/favi/RO-preview.xml", report: "/feeds/favi/RO-preview-report.json" },
};

function share(part?: number, total?: number) {
  if (part === undefined || !total) return "—";
  return `${Math.round(part / total * 100)}%`;
}

export default function FeedsPage() {
  const [google, setGoogle] = useState<GoogleReport | null>(null);
  const [favi, setFavi] = useState<FaviReport | null>(null);
  const [faviRo, setFaviRo] = useState<RomanianReport | null>(null);
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
      fetch(links.faviRo.report, { cache: "no-store" }).then(async response => {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json() as Promise<RomanianReport>;
      }),
    ]);
    const failures: Record<string, string> = {};
    if (results[0].status === "fulfilled") setGoogle(results[0].value);
    else { setGoogle(null); failures.google = "Отчетът временно не е достъпен."; }
    if (results[1].status === "fulfilled") setFavi(results[1].value);
    else { setFavi(null); failures.favi = "Отчетът временно не е достъпен."; }
    setFaviRo(results[2].status === "fulfilled" && results[2].value.source_complete
      ? results[2].value : null);
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
          <span className="badge warn">Публичен XML за сравнение</span>
        </div>
        <p className="muted">Собственият XML и сравнението му с Feedhub. Статусът на проверката и подаването е показан по-долу.</p>
        {google && <p>Наши варианти: <strong>{google.homesector_items?.toLocaleString("bg-BG") ?? "—"}</strong> · Feedhub: <strong>{google.feedhub_items?.toLocaleString("bg-BG") ?? "—"}</strong> · Съвпадащи: <strong>{google.matched_variants?.toLocaleString("bg-BG") ?? "—"}</strong></p>}
        {google && <p>Проверка на XML: <strong>{google.xml_preflight?.passed === true ? "Премината" : google.xml_preflight?.passed === false ? "Има проблеми" : "—"}</strong> · Подаден към Merchant Center: <strong>{google.xml_preflight?.submitted === true ? "Да" : google.xml_preflight?.submitted === false ? "Не" : "—"}</strong> · Липсващи описания: <strong>{google.xml_preflight?.issues?.missing_description?.toLocaleString("bg-BG") ?? "—"}</strong></p>}
        {google?.checked_at && <p className="muted">Сравнението е проверено на {new Date(google.checked_at).toLocaleString("bg-BG")}.</p>}
        {errors.google && <p role="alert" className="notice">{errors.google}</p>}
        <div className="actions" style={{ marginTop: 16 }}>
          <a className="btn primary" href={links.google.xml} target="_blank" rel="noopener noreferrer">Отвори XML за сравнение</a>
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
          <p>Варианти в XML: <strong>{favi.xml_items?.toLocaleString("bg-BG") ?? "—"}</strong> от {favi.greek_published_variants?.toLocaleString("bg-BG") ?? "—"} в Shopify за GR ({share(favi.xml_items, favi.greek_published_variants)}).</p>
          <p>Активни продукти за GR: <strong>{favi.greek_published_products?.toLocaleString("bg-BG") ?? "—"}</strong></p>
          <ul>
            <li>С проверена FAVI категория: {(favi.mapped_category_products ?? favi.reviewed_category_products)?.toLocaleString("bg-BG") ?? "—"} продукта ({share(favi.mapped_category_products ?? favi.reviewed_category_products, favi.greek_published_products)} от GR каталога)</li>
            <li>С потвърден гръцки адрес: {favi.verified_market_url_products?.toLocaleString("bg-BG") ?? "—"} продукта ({share(favi.verified_market_url_products, favi.mapped_category_products ?? favi.reviewed_category_products)} от категоризираните)</li>
            <li>С гръцко заглавие и описание: {favi.localized_copy_products_in_mapped_categories?.toLocaleString("bg-BG") ?? "—"} продукта ({share(favi.localized_copy_products_in_mapped_categories, favi.mapped_category_products ?? favi.reviewed_category_products)} от категоризираните)</li>
          </ul>
          {(favi.generated_at || favi.source_snapshot_at) && <p className="muted">Отчет: {favi.generated_at ? new Date(favi.generated_at).toLocaleString("bg-BG") : "—"} · Shopify snapshot: {favi.source_snapshot_at ? new Date(favi.source_snapshot_at).toLocaleString("bg-BG") : "—"}</p>}
        </>}
        <div className="notice" style={{ marginTop: 14 }}>Това е частичен преглед. Още не е одобрен от FAVI и не е подаден към тях. Не използвайте този URL като производствен фийд.</div>
        {errors.favi && <p role="alert" className="notice">{errors.favi}</p>}
        <div className="actions" style={{ marginTop: 16 }}>
          <a className="btn primary" href={links.favi.xml} target="_blank" rel="noopener noreferrer">Отвори XML прегледа</a>
          <a className="btn secondary" href={links.favi.report} target="_blank" rel="noopener noreferrer">Отчет за проверка</a>
        </div>
      </section>
      <section className="card" aria-labelledby="favi-ro-title">
        <div className="sectionTitle" style={{ margin: "0 0 12px" }}>
          <h2 id="favi-ro-title">FAVI · Румъния</h2>
          <span className="badge warn">{faviRo ? "XML преглед" : "Пълен обход"}</span>
        </div>
        {faviRo ? <>
          <p>Варианти в XML: <strong>{faviRo.xml_items?.toLocaleString("bg-BG") ?? "—"}</strong> от {faviRo.romanian_published_variants?.toLocaleString("bg-BG") ?? "—"} в Shopify за RO.</p>
          <p>Продукти за RO: {faviRo.romanian_published_products?.toLocaleString("bg-BG") ?? "—"} · с категория: {faviRo.mapped_category_products?.toLocaleString("bg-BG") ?? "—"} · с проверен URL: {faviRo.verified_market_url_products?.toLocaleString("bg-BG") ?? "—"}.</p>
          {faviRo.generated_at && <p className="muted">Отчет: {new Date(faviRo.generated_at).toLocaleString("bg-BG")}</p>}
          <div className="actions" style={{ marginTop: 16 }}>
            <a className="btn primary" href={links.faviRo.xml} target="_blank" rel="noopener noreferrer">Отвори XML прегледа</a>
            <a className="btn secondary" href={links.faviRo.report} target="_blank" rel="noopener noreferrer">Отчет за проверка</a>
          </div>
        </> : <p className="muted">Обходът е в ход. XML и отчет ще се появят след пълна проверка.</p>}
      </section>
      <section className="card" aria-labelledby="favi-hu-title">
        <div className="sectionTitle" style={{ margin: "0 0 12px" }}>
          <h2 id="favi-hu-title">FAVI · Унгария</h2>
          <span className="badge warn">Предстои</span>
        </div>
        <p className="muted">Унгарският фийд следва след пълния RO обход и проверка на HUF, преводи, категории и URL-и.</p>
      </section>
    </div>
    <p className="muted" style={{ marginTop: 18 }}>Тук се виждат наличните фийдове и отчетите им. Стартиране на генерация, промяна на правила и подаване към каналите ще се добавят след свързване с управлението на задачите.</p>
  </>;
}
