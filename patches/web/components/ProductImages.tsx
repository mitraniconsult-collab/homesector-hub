"use client";
import { useEffect, useState } from "react";
type Row = { id:string; sku:string; barcode?:string; stage?:string; reason_code?:string; action?:string; product_status?:string; source_query?:string; source_candidates?:number; title:string; result:string; note?:string; source_url?:string; image_count?:number };
type Job = { id:string; status:string; phase:string; mode:string; total:number; cursor:number; scanned:number; ai_calls:number; vendor?:string; error?:string; counts:Record<string,number>; recent:Row[] };
const labels:Record<string,string> = {running:"Изпълнява се",paused:"На пауза",blocked:"Нужда от действие",success:"Завършена",cancelled:"Прекратена",ADDED:"Добавени",IMPROVED:"Заменени",UNCHANGED:"Без нужда от промяна",REVIEW_CLEANUP:"Старите снимки изискват проверка",REVIEW_VARIANT_MEDIA:"Снимка на вариант за проверка",PLANNED:"Намерени (тест)",SKIPPED:"Пропуснати",REVIEW:"За проверка",REVIEW_VARIANTS:"Варианти за проверка",REVIEW_NO_SKU:"Липсва SKU (стар отчет)",REVIEW_NO_IDENTIFIER:"Липсват SKU и EAN",REVIEW_UNCERTAIN:"Непотвърден запис",REVIEW_MEDIA_FAILED:"Отказана снимка",pending:"Изчакват"};
const stages:Record<string,string>={scan:"Проверка на данни",precheck:"Повторна проверка",source:"Търсене на оригинали",quality:"Качество на снимките",ai:"Проверка на съответствието",upload:"Качване в Shopify",cleanup:"Замяна на стари снимки",completed:"Завършено",process:"Обработка"};
export default function ProductImages() {
  const [job,setJob]=useState<Job|null>(null);
  const [mode,setMode]=useState("dry");
  const [limit,setLimit]=useState("100");
  const [collection,setCollection]=useState("");
  const [vendor,setVendor]=useState("");
  const [vendors,setVendors]=useState<string[]>([]);
  const [vendorFilterReady,setVendorFilterReady]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [ready,setReady]=useState(false);
  const [ai,setAi]=useState(false);
  useEffect(()=>{
    let active=true;
    let timer:ReturnType<typeof setTimeout>;
    const controller=new AbortController();
    let vendorsLoaded=false;
    async function poll(){
      try {
        const [health,status]=await Promise.all([fetch("/api/worker/health",{cache:"no-store",signal:controller.signal}),fetch("/api/worker/image-jobs",{cache:"no-store",signal:controller.signal})]);
        const h=await health.json(); const s=await status.json();
        if(!health.ok || h.image_jobs_version!==2) throw new Error("Worker още не е обновен за задачата със снимки.");
        if(!status.ok) throw new Error(s.detail || s.error || "Неуспешно четене на задачата");
        if(active){setReady(true);setAi(!!h.ai_available?.openai);setJob(s.job);setError("");}
        if(h.image_jobs_diagnostics_version!==1) throw new Error("Добави снимки изчаква обновяване на обработката и отчета.");
        if(!h.image_jobs_vendor_filter) throw new Error("Изборът на бранд изчаква обновяване на Worker.");
        if(!vendorsLoaded){
          const response=await fetch("/api/worker/image-jobs/vendors",{cache:"no-store",signal:controller.signal});
          const data=await response.json();
          if(!response.ok || !Array.isArray(data.vendors) || !data.vendors.every((v:unknown)=>typeof v==="string")) throw new Error(data.detail || "Брандовете не могат да се заредят от Shopify.");
          if(active){setVendors(data.vendors);setVendorFilterReady(true);vendorsLoaded=true;}
        }
      } catch(e){if(active && !controller.signal.aborted) setError(e instanceof Error?e.message:"Няма връзка с Worker");}
      finally {if(active)timer=setTimeout(poll,5000);}
    }
    void poll();
    return()=>{active=false;controller.abort();clearTimeout(timer);};
  },[]);
  async function action(name="") {
    setBusy(true);setError("");
    try {
      const response=await fetch(`/api/worker/image-jobs${name?`/${name}`:""}`,{method:"POST",headers:{"content-type":"application/json"},body:name?undefined:JSON.stringify({mode,limit:Number(limit),collection_id:collection,vendor})});
      const data=await response.json();
      if(!response.ok)throw new Error(data.detail || data.error || "Задачата не е стартирана");
      setJob(data.job);
    }catch(e){setError(e instanceof Error?e.message:"Грешка");}finally{setBusy(false);}
  }
  const unfinished=job && !["success","cancelled"].includes(job.status);
  return <>
    <div className="pageHead"><div><h2>Добави снимки</h2><p>Допълване на галерии и замяна на некачествени снимки с оригинали от Decoration Brands.</p></div></div>
    <div className="notice">Задачата продължава на сървъра и след затваряне на страницата или чата. Напредъкът се запазва след всеки продукт и се възстановява след рестарт. Проверява активни, Draft и Archived продукти с 0–2 снимки и галерии със съмнение за лошо качество. Снимки се добавят без активиране на продукта. Търси по SKU, а при липса или неуспешно търсене — и по EAN/баркод. Обединени продукти с варианти се отделят за проверка по цвят и модел.</div>
    <section className="card" style={{padding:24,marginTop:20}} aria-label="Нова задача за снимки">
      <div className="actions">
        <label className="field">Бранд<select value={unfinished?job.vendor||"":vendor} onChange={e=>setVendor(e.target.value)} disabled={!!unfinished || busy || !vendorFilterReady}><option value="">Всички брандове</option>{unfinished&&job.vendor&&!vendors.includes(job.vendor)&&<option value={job.vendor}>{job.vendor}</option>}{vendors.map(name=><option key={name} value={name}>{name}</option>)}</select></label>
        <label className="field">Колекция<select value={collection} onChange={e=>setCollection(e.target.value)} disabled={!!unfinished || busy}><option value="">Всички продукти</option><option value="647445709067">Покривала за градински мебели</option><option value="647445741835">Поддръжка на градински мебели</option></select></label>
        <label className="field">Максимум продукти<input type="number" min={1} max={5000} value={limit} onChange={e=>setLimit(e.target.value)} disabled={!!unfinished || busy}/></label>
        <label className="field">Режим<select value={mode} onChange={e=>setMode(e.target.value)} disabled={!!unfinished || busy}><option value="dry">Тест — оригинали и качество</option><option value="real">Реален — AI проверка и качване</option></select></label>
        <button className={`btn ${mode==="real"?"danger":"primary"}`} disabled={!ready || !vendorFilterReady || busy || !!unfinished || (mode==="real"&&!ai) || !Number.isInteger(Number(limit)) || Number(limit)<1 || Number(limit)>5000} onClick={()=>void action()}>{busy?"Записва…":"Стартирай"}</button>
      </div>
      <p className="muted">Брандът и колекцията се прилагат заедно. Изборът се запазва за цялата задача, включително при продължаване след пауза.</p>
      <p className="muted">Тестът не прави AI заявки и не променя Shopify. Реалният режим проверява SKU/EAN и съответствието с оригиналната галерия от Decoration Brands чрез OpenAI. Добрите снимки се запазват. Некачествените се заменят само с по-добри оригинали от Decoration Brands след успешно качване. Старите файлове остават в Shopify Files.</p>
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
      <p className="muted">Бранд на задачата: <strong>{job.vendor || "Всички брандове"}</strong></p>
      <p aria-live="polite">{job.phase==="scan"?`Прегледани ${job.scanned} продукта; намерени ${job.total} кандидата.`:`Обработени ${job.cursor} от ${job.total} продукта.`} AI проверки: {job.ai_calls}. {job.mode==="dry"?"Тестов режим.":"Реално качване."}</p>
      <p className="muted">{Object.entries(job.counts).map(([key,value])=>`${labels[key]||key}: ${value}`).join(" · ")}</p>
      {job.error&&<p className="notice" role="alert">{job.error}</p>}
      <div className="card" style={{overflowX:"auto"}}><table className="table"><caption style={{textAlign:"left",padding:16}}>Последни обработени продукти</caption><thead><tr><th>SKU</th><th>Продукт</th><th>Етап</th><th>Резултат</th><th>Снимки</th><th>Бележка</th></tr></thead><tbody>{job.recent.map(row=><tr key={row.id}><td>{row.sku || "Без SKU"}{row.barcode&&<div className="muted">EAN: {row.barcode}</div>}</td><td>{row.title}{row.product_status&&<div className="muted">{row.product_status}</div>}</td><td>{stages[row.stage||""]||"—"}</td><td>{labels[row.result]||row.result}</td><td>{row.image_count??"—"}</td><td>{row.note}{row.action&&<p><strong>Следващо действие:</strong> {row.action}</p>}{row.source_query&&<div className="muted">Търсено: {row.source_query}. Проверени страници: {row.source_candidates??"—"}.</div>}{row.source_url&&<> <a href={row.source_url} target="_blank" rel="noreferrer">Източник</a></>}</td></tr>)}</tbody></table></div>
      <p className="muted">Пауза и прекратяване действат между стъпките. Вече изпратено качване може да завърши. Продуктите с несъответстващ модел, цвят или размер остават за проверка.</p>
    </>}
  </>;
}
