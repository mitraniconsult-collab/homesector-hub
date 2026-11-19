"use client";
import { useCallback, useEffect, useState } from "react";
type Registry = { imported?: boolean; uploadedAt?: string; count?: number; active?: number; error?: string };
export default function EmagMapping() {
  const [registry, setRegistry] = useState<Registry>({});
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => { try { const response = await fetch("/api/feeds/emag/mapping", { cache: "no-store" });
    if (!response.ok) throw Error("Неуспешно зареждане"); setRegistry(await response.json()); }
    catch { setError("Няма достъп до регистъра."); } }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  async function upload() { if (!file) return; setBusy(true); setError("");
    try { const data = new FormData(); data.set("file", file);
      const response = await fetch("/api/feeds/emag/mapping", { method: "POST", body: data });
      const result = await response.json(); if (!response.ok) throw Error(result.error || "Неуспешен импорт");
      setRegistry(result); setFile(null);
    } catch (e) { setError(e instanceof Error ? e.message : "Грешка"); } finally { setBusy(false); } }
  return <><div className="pageHead"><div><h1>eMAG — регистър на офертите</h1><p>Защитен импорт на идентификаторите от eMAG. Не променя оферти или фийдове.</p></div></div>
    <div className="grid two"><div className="card stack"><h2>Последен импорт</h2>
      {registry.imported ? <><strong>{registry.count?.toLocaleString("bg-BG")} оферти</strong><p>{registry.active?.toLocaleString("bg-BG")} активни</p><p className="muted">{registry.uploadedAt && new Date(registry.uploadedAt).toLocaleString("bg-BG", { timeZone: "Europe/Sofia" })}</p></> : <p className="muted">Все още няма записан регистър.</p>}
    </div><div className="card stack"><h2>Качи eMAG експорт</h2><label className="field">XLSX от „Актуализиране на оферти, цени и наличности“
      <input type="file" accept=".xlsx" onChange={e => setFile(e.target.files?.[0] || null)}/></label>
      <button type="button" className="btn primary" disabled={!file || busy} onClick={() => void upload()}>{busy ? "Импортиране…" : "Импортирай регистъра"}</button>
      {error && <div className="notice" role="alert">{error}</div>}</div></div>
    <div className="notice" style={{ marginTop: 20 }}>Регистърът съдържа eMAG идентификаторите. Shopify съответствията се проверяват отделно. Автоматичното публикуване остава изключено.</div>
  </>;
}
