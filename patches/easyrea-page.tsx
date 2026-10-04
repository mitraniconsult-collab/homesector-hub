"use client";
import { useEffect, useRef, useState } from "react";
import { easyreaTasks } from "@/lib/modules";

type RunMode = "dry" | "real";
type Job = { id:string; task:string; status:string; created_at?:string; started_at?:string|null; finished_at?:string|null; return_code?:number|null; log?:string; reports?:{filename:string;downloadUrl:string}[]; report_error?:string|null };
const terminal = (s?:string) => s === "success" || s === "failed";

export default function EasyreaPage(){
  const [submitting,setSubmitting]=useState(false);
  const [mode,setMode]=useState<RunMode>("dry");
  const [batchSize,setBatchSize]=useState("500");
  const [batchNumber,setBatchNumber]=useState("1");
  const [message,setMessage]=useState("");
  const [job,setJob]=useState<Job|null>(null);
  const [pollError,setPollError]=useState("");
  const logRef=useRef<HTMLDivElement|null>(null);

  async function readJob(id:string){
    const r=await fetch(`/api/worker/jobs/${id}`,{cache:"no-store"});
    const d=await r.json();
    if(!r.ok) throw new Error(d.error||d.detail||"Неуспешно четене на job статуса");
    setJob(d.job); setPollError(""); return d.job as Job;
  }

  useEffect(()=>{
    if(!job?.id || terminal(job.status)) return;
    let stopped=false; let timer:number;
    const tick=async()=>{
      try{ const latest=await readJob(job.id); if(!stopped && !terminal(latest.status)) timer=window.setTimeout(tick,2000); }
      catch(e){ if(!stopped){ setPollError(e instanceof Error?e.message:"Грешка при live обновяването"); timer=window.setTimeout(tick,4000); } }
    };
    timer=window.setTimeout(tick,700);
    return()=>{stopped=true; window.clearTimeout(timer)};
  },[job?.id,job?.status]);

  useEffect(()=>{ if(logRef.current) logRef.current.scrollTop=logRef.current.scrollHeight; },[job?.log]);

  async function run(task:string){
    if(submitting || (job && !terminal(job.status))) return;
    setSubmitting(true);
    setMessage(`Подготвя ${task}…`); setPollError(""); setJob(null);
    try{
      if(task === "sync.py"){
        const health=await fetch("/api/worker/health",{cache:"no-store"});
        const configuration=await health.json();
        if(!health.ok || configuration.stock_sync_version !== 2) throw new Error("Python Worker още използва старата синхронизация. Обновете Worker до последната версия, преди да стартирате общата задача.");
      }
      const r=await fetch("/api/worker/jobs/run",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({task,mode,batch_size:Number(batchSize),batch_number:Number(batchNumber)})});
      const d=await r.json(); if(!r.ok) throw new Error(d.error||d.detail||"Worker error");
      setJob(d.job); setMessage(`Job ${d.job?.id||""} е стартиран в ${mode==="dry"?"TEST / DRY RUN":"REAL RUN"}.`);
    }catch(e){setMessage(e instanceof Error?e.message:"Грешка")}finally{setSubmitting(false)}
  }

  const status=job?`${job.status.toUpperCase()}${job.return_code!==null&&job.return_code!==undefined?` · exit ${job.return_code}`:""}`:"";
  const logText=job?.log || (job?`Job ${job.id}: ${status}\nИзчаквам първия изход от Python процеса…`:"Пусни задача и тук ще се появят live прогресът и логовете.");

  return <>
    <div className="pageHead"><div><h1>Easyrea Sync</h1><p>Съществуващите Python задачи, управлявани през Hub.</p></div><div className="actions">
      <button className={`btn ${mode==="dry"?"primary":"secondary"}`} onClick={()=>setMode("dry")}>TEST / DRY RUN</button>
      <button className={`btn ${mode==="real"?"danger":"secondary"}`} onClick={()=>setMode("real")}>REAL RUN</button>
    </div></div>
    <div className="notice">Общата синхронизация обновява продажбата при изчерпване и датите, без да променя складовите количества. Непознатите статуси остават за проверка; реалният режим спира при над 25% липсващи или непознати продукти.</div>
    <div className="sectionTitle"><h2>Задачи</h2><div className="actions">
      <label className="field">Batch size<input value={batchSize} onChange={e=>setBatchSize(e.target.value)}/></label>
      <label className="field">Batch number<input value={batchNumber} onChange={e=>setBatchNumber(e.target.value)}/></label>
    </div></div>
    <div className="card"><table className="table"><thead><tr><th>Задача</th><th>График</th><th>Време</th><th>Променя данни</th><th></th></tr></thead><tbody>
      {easyreaTasks.map(t=><tr key={t.key}><td><strong>{t.name}</strong><div className="muted code">{t.key}</div>{t.key==="export_missing_skus.py"&&<div className="muted">EAN на варианти без SKU: atmosphera, Hesperide, Secret De Gourmet, 5five, Neka.</div>}</td><td>{t.cadence}</td><td>{t.duration}</td><td>{t.writes?"Да":"Не"}</td><td><button className="btn secondary" disabled={submitting || (!!job&&!terminal(job.status))} onClick={()=>run(t.key)}>Пусни</button></td></tr>)}
    </tbody></table></div>
    {message&&<div className="sectionTitle"><div className="notice">{message}</div></div>}
    <div className="sectionTitle"><h2>Job log</h2>{job&&<div className="muted code">{job.id} · {status}</div>}</div>
    {pollError&&<div className="notice">Live log: {pollError}</div>}
    {job?.reports?.map(r=><div className="sectionTitle" key={r.downloadUrl}><a className="btn primary" href={r.downloadUrl}>Свали {r.filename}</a><a className="btn secondary" href="/reports">Всички отчети</a></div>)}
    {job?.report_error&&<div className="notice">{job.report_error}</div>}
    <div className="log" ref={logRef} style={{whiteSpace:"pre-wrap",maxHeight:520,overflow:"auto"}}>{logText}</div>
  </>;
}
