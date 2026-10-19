"use client";
import { useEffect, useState } from "react";
type Row = { id:string; sku:string; title:string; result:string; note?:string; source_url?:string; image_count?:number };
type Job = { id:string; status:string; phase:string; mode:string; total:number; cursor:number; scanned:number; ai_calls:number; error?:string; counts:Record<string,number>; recent:Row[] };
const labels:Record<string,string> = {running:"Изпълнява се",paused:"На пауза",blocked:"Нужда от действие",success:"Завършена",cancelled:"Прекратена",ADDED:"Добавени",PLANNED:"Намерени (тест)",SKIPPED:"Пропуснати",REVIEW:"За проверка",REVIEW_VARIANTS:"Варианти за проверка",REVIEW_NO_SKU:"Липсва SKU",REVIEW_UNCERTAIN:"Непотвърден запис",REVIEW_MEDIA_FAILED:"Отказана снимка",pending:"Изчакват"};
export default function ShopifyImages() {
  const [job,setJob]=useState<Job|null>(null);
  const [mode,setMode]=useState("dry");
  const [limit,setLimit]=useState("100");
  const [collection,setCollection]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [ready,setReady]=useState(false);
  const [ai,setAi]=useState(false);
  useEffect(()=>{
    let active=true;
    let timer:ReturnType<typeof setTimeout>;
    const controller=new AbortController();
    async function poll(){
      try {
        const [health,status]=await Promise.all([fetch("/api/worker/health",{cache:"no-store",signal:controller.signal}),fetch("/api/worker/image-jobs",{cache:"no-store",signal:controller.signal})]);
        const h=await health.json(); const s=await status.json();
        if(!health.ok || h.image_jobs_version!==1) throw new Error("Worker още не е обновен за задачата със снимки.");
        if(!status.ok) throw new Error(s.detail || s.error || "Неуспешно четене на задачата");
        if(active){setReady(true);setAi(!!h.ai_available?.openai);setJob(s.job);setError("");}
      } catch(e){if(active && !controller.signal.aborted) setError(e instanceof Error?e.message:"Няма връзка с Worker");}
      finally {if(active)timer=setTimeout(poll,5000);}
    }
    void poll();
    return()=>{active=false;controller.abort();clearTimeout(timer);};
  },[]);
  async function action(name="") {
    setBusy(true);setError("");
    try {
      const response=await fetch(`/api/worker/image-jobs${name?`/${name}`:""}`,{method:"POST",headers:{"content-type":"application/json"},body:name?undefined:JSON.stringify({mode,limit:Number(limit),collection_id:collection})});
      const data=await response.json();
      if(!response.ok)throw new Error(data.detail || data.error || "Задачата не е стартирана");
      setJob(data.job);
    }catch(e){setError(e instanceof Error?e.message:"Грешка");}finally{setBusy(false);}
  }
  const unfinished=job && !["success","cancelled"].includes(job.status);
  return <>
    <div className="pageHead"><div><h1>Снимки на продукти</h1><p>Допълване на липсващи изображения с проверка чрез OpenAI API.</p></div></div>
    <div className="notice">Задачата продължава на сървъра и след затваряне на страницата или чата. Напредъкът се запазва след всеки продукт и се възстановява след рестарт. Работи по активни продукти без изображения. Обединени продукти с варианти се отделят за проверка.</div>
    <section className="card" style={{padding:24,marginTop:20}} aria-label="Нова задача за снимки">
      <div className="actions">
        <label className="field">Колекция<select value={collection} onChange={e=>setCollection(e.target.value)} disabled={!!unfinished || busy}><option value="">Всички активни продукти</option><option value="647445709067">Покривала за градински мебели</option><option value="647445741835">Поддръжка на градински мебели</option></select></label>
        <label className="field">Максимум продукти<input type="number" min={1} max={5000} value={limit} onChange={e=>setLimit(e.target.value)} disabled={!!unfinished || busy}/></label>
        <label className="field">Режим<select value={mode} onChange={e=>setMode(e.target.value)} disabled={!!unfinished || busy}><option value="dry">Тест — само намиране на снимки</option><option value="real">Реален — AI проверка и качване</option></select></label>
        <button className={`btn ${mode==="real"?"danger":"primary"}`} disabled={!ready || busy || !!unfinished || (mode==="real"&&!ai) || !Number.isInteger(Number(limit)) || Number(limit)<1 || Number(limit)>5000} onClick={()=>void action()}>{busy?"Записва…":"Стартирай"}</button>
      </div>
      <p className="muted">Тестът не прави AI заявки и не променя Shopify. Реалният режим проверява SKU/EAN и съответствието с оригиналната галерия от Decoration Brands чрез OpenAI. Съществуващи снимки не се изтриват.</p>
      {ready&&!ai&&<p role="status">OpenAI ключът липсва в Worker. Тестът е достъпен; реалният режим изисква настройване на OPENAI_API_KEY.</p>}
    </section>
    {error&&<p className="notice" role="alert">{error}</p>}
    {job&&<>
      <div className="sectionTitle"><h2>{labels[job.status] || job.status}</h2><div className="actions">
        {job.status==="running"&&<button className="btn secondary" disabled={busy} onClick={()=>void action("pause")}>Пауза</button>}
        {["paused","blocked"].includes(job.status)&&<button className="btn primary" disabled={busy || (job.mode==="real"&&!ai)} onClick={()=>void action("resume")}>Продължи</button>}
        {unfinished&&<button className="btn secondary" disabled={busy} onClick={()=>void action("cancel")}>Прекрати</button>}
        <a className="btn secondary" href="/api/worker/image-jobs/report" download="product-images.csv">Свали CSV отчет</a>
      </div></div>
      <p aria-live="polite">{job.phase==="scan"?`Прегледани ${job.scanned} продукта; намерени ${job.total} кандидата.`:`Обработени ${job.cursor} от ${job.total} продукта.`} AI проверки: {job.ai_calls}. {job.mode==="dry"?"Тестов режим.":"Реално качване."}</p>
      <p className="muted">{Object.entries(job.counts).map(([key,value])=>`${labels[key]||key}: ${value}`).join(" · ")}</p>
      {job.error&&<p className="notice" role="alert">{job.error}</p>}
      <div className="card" style={{overflowX:"auto"}}><table className="table"><caption style={{textAlign:"left",padding:16}}>Последни обработени продукти</caption><thead><tr><th>SKU</th><th>Продукт</th><th>Резултат</th><th>Снимки</th><th>Бележка</th></tr></thead><tbody>{job.recent.map(row=><tr key={row.id}><td>{row.sku}</td><td>{row.title}</td><td>{labels[row.result]||row.result}</td><td>{row.image_count||0}</td><td>{row.note}{row.source_url&&<> <a href={row.source_url} target="_blank" rel="noreferrer">Източник</a></>}</td></tr>)}</tbody></table></div>
      <p className="muted">Пауза и прекратяване действат между стъпките. Вече изпратено качване може да завърши. Продуктите с несъответстващ модел, цвят или размер остават за проверка.</p>
    </>}
  </>;
}
