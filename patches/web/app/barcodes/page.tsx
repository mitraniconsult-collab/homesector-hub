"use client";
import { useCallback, useEffect, useState } from "react";

type Job = { id: string; task: string; status: string; log?: string; return_code?: number; reports?: unknown; started_at?: string; finished_at?: string };
type WorkerHealth = { tasks: number };
const TASK = "ean_barcodes.py";
export default function BarcodeJobsPage() {
  const [mode,setMode] = useState<"dry"|"real">("dry");
  const [job,setJob] = useState<Job|null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [healthy,setHealthy] = useState(false);
  const refresh = useCallback(async ()=>{
    const [h,j] = await Promise.all([
      fetch("/api/worker/health",{cache:"no-store"}),
      fetch("/api/worker/jobs",{cache:"no-store"})
    ]);
    if(!h.ok || !j.ok) throw new Error("Няма връзка с Hub Worker.");
    const health = await h.json() as WorkerHealth;
    const data = await j.json() as {jobs:Job[]};
    if(!Array.isArray(data.jobs)) throw new Error("Невалиден отговор от Worker.");
    setHealthy(health.tasks>=7);
    setJob(data.jobs.filter(x=>x.task===TASK).sort((a,b)=>String(b.started_at||"").localeCompare(String(a.started_at||"")))[0]||null);
  },[]);
  useEffect(()=>{
    let active=true;
    const tick=async()=>{try{await refresh();if(active)setError("");}catch(e){if(active)setError(e instanceof Error?e.message:"Грешка");}};
    void tick();
    const id=setInterval(()=>void tick(),5000);
    return()=>{active=false;clearInterval(id);};
  },[refresh]);
  const active=!!job && ["queued","pending","running"].includes(job.status);
  async function start(){
    if(mode==="real" && !window.confirm("Реално да променя типа на всички валидни EAN баркодове в Shopify? Номерата остават същите.")) return;
    setBusy(true);setError("");
    try {
      const r=await fetch("/api/worker/jobs/run",{
        method:"POST",headers:{"content-type":"application/json"},
        body:JSON.stringify({task:TASK,mode})
      });
      const data=await r.json();
      if(!r.ok)throw new Error(data.detail||data.error||"Задачата не е стартирана.");
      setJob(data.job);
      await refresh();
    } catch(e){setError(e instanceof Error?e.message:"Грешка при стартиране");}
    finally {setBusy(false);}
  }
  const log=job?.log||"";
  const lines=log.trim().split("\n");
  const last=lines.filter(x=>x.includes("[EAN] page=")).at(-1)||"";
  const end=lines.filter(x=>x.includes("[EAN] FINAL")).at(-1)||"";
  return <div>
    <div className="pageHead"><div><h2>EAN баркодове</h2><p>Проверка и масова корекция на типа на баркодовете в Shopify — всички варианти, всички статуси.</p></div></div>
    <div className="notice">Променя се само типът на валидните EAN-8/EAN-13 баркодове. Номерата, цените, наличностите и продуктовите шаблони не се променят. Празните или невалидни кодове се пропускат и присъстват в CSV отчета.</div>
    <section className="card" style={{padding:24,marginTop:20}}>
      <div className="actions">
        <label className="field">Режим
          <select value={mode} disabled={busy||active} onChange={e=>setMode(e.target.value as "dry"|"real")}>
            <option value="dry">Тест — без промени</option>
            <option value="real">Реален — запис в Shopify</option>
          </select>
        </label>
        <button className={mode==="real"?"btn danger":"btn primary"} disabled={busy||active||!healthy} onClick={()=>void start()}>{busy?"Стартиране…":mode==="real"?"Стартирай реална корекция":"Стартирай тест"}</button>
      </div>
      <p className="muted">Worker обработва страниците по 50 варианта, групира ги по продукт и изпълнява до 4 паралелни записвания. При ново стартиране пропуска вече коригираните продукти.</p>
      {!healthy&&<p role="alert" className="notice">Worker още не е обновен с новата EAN задача.</p>}
    </section>
    {error&&<p className="notice" role="alert">{error}</p>}
    {job&&<section className="card" style={{padding:24,marginTop:20}}>
      <h3>Последна задача: {job.status==="success"?"Завършена":job.status==="running"?"Изпълнява се":job.status==="failed"?"Грешка":job.status}</h3>
      {last&&<p aria-live="polite">{last}</p>}
      {end&&<p>{end}</p>}
      <p className="muted">Номер: {job.id} {job.started_at&&" · Старт: "+job.started_at}</p>
      <details><summary>Технически журнал</summary><pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere",maxHeight:450,overflowY:"auto"}}>{log||"Все още няма записи."}</pre></details>
      {job.status==="failed"&&<p role="alert">Проверете журнала и отчетите. Неуспешните записи не се обозначават като успешно обработени.</p>}
      <p className="muted">CSV отчетът се съхранява в историята на изпълнението чрез системата за отчети на Hub.</p>
    </section>}
  </div>;
}
