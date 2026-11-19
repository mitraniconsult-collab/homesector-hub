"use client";
import { useCallback, useEffect, useState } from "react";
type Registry = { imported?: boolean; uploadedAt?: string; count?: number; active?: number; error?: string };
type Match = { ean: string; shopify_id: string; sku: string; status: string; title: string };
type Comparison = { ready?: boolean; total?: number; matched?: number; ambiguous?: number; missingEan?: number; unmatched?: number; differentSku?: number; checkedAt?: string };
export default function EmagMapping() {
  const [registry, setRegistry] = useState<Registry>({});
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [comparison, setComparison] = useState<Comparison>({});
  const [progress, setProgress] = useState(0);
  const refresh = useCallback(async () => { try { const response = await fetch("/api/feeds/emag/mapping", { cache: "no-store" });
    if (!response.ok) throw Error("Неуспешно зареждане"); setRegistry(await response.json()); }
    catch { setError("Няма достъп до регистъра."); } }, []);
  useEffect(() => { void refresh(); void fetch("/api/feeds/emag/matches", { cache: "no-store" }).then(r => r.json()).then(setComparison).catch(() => {}); }, [refresh]);
  async function upload() { if (!file) return; setBusy(true); setError("");
    try { const data = new FormData(); data.set("file", file);
      const response = await fetch("/api/feeds/emag/mapping", { method: "POST", body: data });
      const result = await response.json(); if (!response.ok) throw Error(result.error || "Неуспешен импорт");
      setRegistry(result); setComparison({}); setFile(null);
    } catch (e) { setError(e instanceof Error ? e.message : "Грешка"); } finally { setBusy(false); } }
  async function compare() {
    setBusy(true); setError(""); setProgress(0);
    try {
      const response = await fetch("/api/feeds/emag/mapping?details=1", { cache: "no-store" });
      if (!response.ok) throw Error("Регистърът не е достъпен");
      const data = await response.json() as { offers: { ean: string }[] };
      const eans = [...new Set(data.offers.map(offer => offer.ean).filter(ean => /^\d{8,14}$/.test(ean)))];
      const matches: Match[] = [];
      for (let index = 0; index < eans.length; index += 30) {
        const page = await fetch("/api/worker/emag/match", { method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ eans: eans.slice(index, index + 30) }) });
        if (!page.ok) throw Error(`Проверка на група ${Math.floor(index / 30) + 1} не успя (HTTP ${page.status}).`);
        const payload = await page.json() as { matches?: Match[] };
        if (!Array.isArray(payload.matches)) throw Error("Непълен отговор от Worker");
        matches.push(...payload.matches);
        setProgress(Math.min(100, Math.round((index + 30) / eans.length * 100)));
      }
      const result = await fetch("/api/feeds/emag/matches", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ registryUploadedAt: registry.uploadedAt, matches }) });
      const payload = await result.json(); if (!result.ok) throw Error(payload.error || "Записът не успя");
      setComparison(payload);
    } catch (e) { setError(e instanceof Error ? e.message : "Грешка при съпоставянето"); }
    finally { setBusy(false); }
  }
  return <><div className="pageHead"><div><h1>eMAG — регистър на офертите</h1><p>Защитен импорт на идентификаторите от eMAG. Не променя оферти или фийдове.</p></div></div>
    <div className="grid two"><div className="card stack"><h2>Последен импорт</h2>
      {registry.imported ? <><strong>{registry.count?.toLocaleString("bg-BG")} оферти</strong><p>{registry.active?.toLocaleString("bg-BG")} активни</p><p className="muted">{registry.uploadedAt && new Date(registry.uploadedAt).toLocaleString("bg-BG", { timeZone: "Europe/Sofia" })}</p></> : <p className="muted">Все още няма записан регистър.</p>}
    </div><div className="card stack"><h2>Качи eMAG експорт</h2><label className="field">XLSX от „Актуализиране на оферти, цени и наличности“
      <input type="file" accept=".xlsx" onChange={e => setFile(e.target.files?.[0] || null)}/></label>
      <button type="button" className="btn primary" disabled={!file || busy} onClick={() => void upload()}>{busy ? "Импортиране…" : "Импортирай регистъра"}</button>
      {error && <div className="notice" role="alert">{error}</div>}</div></div>
    <div className="card stack" style={{ marginTop: 18 }}><h2>Съпоставяне със Shopify по EAN</h2>
      <p className="muted">Проверява всеки EAN в Shopify и запазва резултата. SKU се показва само за сравнение. Не променя продукти или оферти.</p>
      <div className="actions"><button className="btn primary" type="button" disabled={!registry.imported || busy} onClick={() => void compare()}>{busy ? `Проверка ${progress}%` : "Провери EAN съответствията"}</button></div>
      {comparison.ready && <><p><strong>{comparison.matched?.toLocaleString("bg-BG")}</strong> съвпадения от {comparison.total?.toLocaleString("bg-BG")} оферти</p>
        <p>{comparison.differentSku} с различен SKU · {comparison.ambiguous} двусмислени · {comparison.missingEan} без EAN · {comparison.unmatched} ненамерени</p>
        <p className="muted">Проверено: {comparison.checkedAt && new Date(comparison.checkedAt).toLocaleString("bg-BG", { timeZone: "Europe/Sofia" })}</p></>}
      {error && <div className="notice" role="alert">{error}</div>}
    </div>
    <div className="notice" style={{ marginTop: 20 }}>Автоматичното публикуване остава изключено. Само уникалните EAN съвпадения могат да преминат към следващ етап на одобрение.</div>
  </>;
}
