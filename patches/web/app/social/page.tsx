"use client";
import { useEffect, useState } from "react";
import { defaultBrands } from "@/lib/socialDefaults";
import type { CollectorItem } from "@/lib/collector";

type SocialItem = CollectorItem & { draft?: string; publishedId?: string };

export default function SocialPage() {
  const [items, setItems] = useState<SocialItem[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  useEffect(() => {
    try { const saved = localStorage.getItem("hs-hub-social-items"); if (saved) setItems(JSON.parse(saved)); } catch { /* invalid previous cache */ }
  }, []);
  function save(next: SocialItem[]) { setItems(next); localStorage.setItem("hs-hub-social-items", JSON.stringify(next)); }
  function update(id: string, fields: Partial<SocialItem>) { save(items.map(item => item.id === id ? { ...item, ...fields } : item)); }
  async function collect() {
    setBusy("collect"); setError(""); setInfo("");
    try {
      const response = await fetch("/api/collector", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ brands: defaultBrands }) });
      const data = await response.json(); if (!response.ok) throw Error(data.error || "Грешка при събиране");
      const existing = new Map(items.map(item => [item.fingerprint, item]));
      const incoming = (data.items as SocialItem[]).map(item => ({ ...item, ...existing.get(item.fingerprint) }));
      const seen = new Set(incoming.map(item => item.fingerprint));
      save([...incoming, ...items.filter(item => !seen.has(item.fingerprint))]);
      setInfo(`Проверени са ${defaultBrands.length} марки; получени са ${incoming.length} материала. Данните се съхраняват в този браузър.`);
    } catch (e) { setError(e instanceof Error ? e.message : "Грешка"); } finally { setBusy(""); }
  }
  async function draft(item: SocialItem) {
    setBusy(item.id); setError("");
    try {
      const response = await fetch("/api/social/draft", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ brand: item.brandName, title: item.title, text: item.text, sourceUrl: item.canonicalUrl }) });
      const data = await response.json(); if (!response.ok) throw Error(data.error || "AI грешка");
      update(item.id, { draft: data.draft, status: "reviewed" });
    } catch (e) { setError(e instanceof Error ? e.message : "Грешка"); } finally { setBusy(""); }
  }
  async function publish(item: SocialItem) {
    if (!item.draft?.trim() || !window.confirm("Да публикувам ли този текст във Facebook страницата на Homesector?")) return;
    setBusy(item.id); setError(""); setInfo("");
    try {
      const response = await fetch("/api/social/publish", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: item.draft, sourceUrl: item.canonicalUrl }) });
      const data = await response.json(); if (!response.ok) throw Error(data.error || "Meta грешка");
      update(item.id, { publishedId: data.id }); setInfo(`Публикувано във Facebook: ${data.id}`);
    } catch (e) { setError(e instanceof Error ? e.message : "Грешка"); } finally { setBusy(""); }
  }
  return <>
    <div className="pageHead"><div><h1>Social · Brand Collector</h1><p>Следене на марки → AI текст на български → редакция → публикуване.</p></div><div className="actions"><button className="btn primary" disabled={!!busy} onClick={collect}>{busy === "collect" ? "Проверявам…" : "Провери източниците"}</button></div></div>
    <div className="notice">На този етап се проверяват публичните сайтове на марките, не техните Instagram/Facebook постове. За автоматично следене и публикуване са необходими официални Meta интеграции и постоянно хранилище. Публикуване се извършва само след ваше потвърждение.</div>
    {error && <p className="notice" role="alert">{error}</p>}{info && <p className="card" role="status">{info}</p>}
    <div className="grid cards" style={{ marginTop: 18 }}><div className="card"><div className="metricLabel">Брандове</div><div className="metric">{defaultBrands.length}</div></div><div className="card"><div className="metricLabel">Материали</div><div className="metric">{items.length}</div></div><div className="card"><div className="metricLabel">Чернови</div><div className="metric">{items.filter(i => i.draft && !i.publishedId).length}</div></div><div className="card"><div className="metricLabel">Публикувани</div><div className="metric">{items.filter(i => i.publishedId).length}</div></div></div>
    <div className="sectionTitle"><h2>Наблюдавани брандове</h2></div><div className="grid two">{defaultBrands.map(b => <div className="card" key={b.id}><strong>{b.name}</strong><p className="muted">{b.website}</p></div>)}</div>
    <div className="sectionTitle"><h2>Съдържание и чернови</h2></div><div className="stack">{items.length === 0 ? <div className="card empty">Няма събрано съдържание. Стартирайте проверка.</div> : items.slice(0, 80).map(item => <article className="card" key={item.id}>
      <div className="actions"><span className="badge">{item.brandName}</span><span className="badge">{item.publishedId ? "Публикувано" : item.draft ? "Чернова" : "Нов материал"}</span></div>
      <h3>{item.title}</h3><p className="muted">{item.text}</p><p><a href={item.canonicalUrl} target="_blank" rel="noreferrer">Оригинален източник ↗</a></p>
      {item.imageUrl && <p><a href={item.imageUrl} target="_blank" rel="noreferrer">Снимка от източника ↗</a></p>}
      {item.draft !== undefined && <label className="field">Български текст — може да се редактира<textarea rows={5} value={item.draft} onChange={e => update(item.id, { draft: e.target.value })} /></label>}
      <div className="actions" style={{ marginTop: 12 }}><button className="btn secondary" disabled={!!busy || !!item.publishedId} onClick={() => draft(item)}>{busy === item.id ? "Изчакване…" : item.draft ? "Генерирай отново" : "AI текст на български"}</button>
      {item.draft && !item.publishedId && <button className="btn primary" disabled={!!busy} onClick={() => publish(item)}>Публикувай във Facebook</button>}
      {!item.publishedId && <button className="btn secondary" disabled={!!busy} onClick={() => update(item.id, { status: "ignored" })}>Пропусни</button>}
      </div></article>)}</div>
  </>;
}
