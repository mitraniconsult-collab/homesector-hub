"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { easyreaTasks } from "@/lib/modules";
import "./dashboard.css";

type Report = { pathname: string; task: string; status: string; mode: string; createdAt: string };

const shortcuts = [
  { title: "Синхронизирай наличности и дати", detail: "Актуализирай наличностите от доставчика", href: "/easyrea" },
  { title: "Качи нови продукти (AI)", detail: "Импорт, снимки и продуктова информация", href: "/easyrea" },
  { title: "Продуктови фийдове", detail: "Проверки за eMAG, Google и FAVI", href: "/feeds" },
  { title: "EAN баркодове", detail: "Открий и попълни липсващи баркодове", href: "/barcodes" },
];

export default function Dashboard() {
  const [reports, setReports] = useState<Report[]>([]);
  const [reportsState, setReportsState] = useState<"loading" | "ready" | "unavailable">("loading");
  const [workerState, setWorkerState] = useState<"checking" | "online" | "offline">("checking");

  const refresh = useCallback(async () => {
    setReportsState("loading");
    setWorkerState("checking");
    const [reportResult, workerResult] = await Promise.allSettled([
      fetch("/api/reports", { cache: "no-store" }).then(async response => {
        if (!response.ok) throw Error("Reports unavailable");
        const payload = await response.json();
        if (!Array.isArray(payload.reports)) throw Error("Invalid reports");
        return payload.reports as Report[];
      }),
      fetch("/api/worker/health", { cache: "no-store" }).then(response => response.ok),
    ]);
    if (reportResult.status === "fulfilled") {
      setReports(reportResult.value.slice(0, 4));
      setReportsState("ready");
    } else setReportsState("unavailable");
    setWorkerState(workerResult.status === "fulfilled" && workerResult.value ? "online" : "offline");
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const failures = reports.filter(report => report.status === "failed").length;
  return <div className="hub-dashboard">
    <div className="dashboard-heading">
      <div><span className="dashboard-eyebrow">Работно пространство</span><h1>Оперативно табло</h1><p>Най-важното за ежедневната работа на Homesector.</p></div>
      <button type="button" className="btn secondary dashboard-refresh" onClick={() => void refresh()} disabled={reportsState === "loading" && workerState === "checking"}>Обнови данните</button>
    </div>

    <div className="dashboard-overview">
      <div className="dashboard-summary">
        <div className="dashboard-summary-top"><h2>Състояние на системата</h2><span className={`dashboard-state ${workerState}`}>{workerState === "checking" ? "Проверка…" : workerState === "online" ? "Worker е достъпен" : "Worker не е достъпен"}</span></div>
        <p>{workerState === "online" ? "Можеш да стартираш задачи от Easyrea Sync." : workerState === "checking" ? "Проверяваме връзката с изпълнителя на задачите." : "Провери връзката в настройките, ако задачите не се стартират."}</p>
        <Link href={workerState === "offline" ? "/settings" : "/easyrea"} className="dashboard-text-link">{workerState === "offline" ? "Отвори настройките" : "Към задачите"}<span aria-hidden="true"> →</span></Link>
      </div>
      <div className="dashboard-summary dashboard-summary-compact"><span className="dashboard-overline">Последни отчети</span><strong>{reportsState === "loading" ? "…" : reportsState === "unavailable" ? "—" : reports.length}</strong><span>{reportsState === "unavailable" ? "Няма връзка с отчетите" : "показани последни изпълнения"}</span></div>
      <div className="dashboard-summary dashboard-summary-compact"><span className="dashboard-overline">Неуспешни изпълнения</span><strong>{reportsState === "ready" ? failures : "—"}</strong><span>{reportsState === "ready" ? "сред показаните отчети" : "няма потвърдени данни"}</span></div>
    </div>

    <div className="dashboard-section-heading"><div><h2>Бързи действия</h2><p>Най-често използваните инструменти</p></div></div>
    <div className="dashboard-shortcuts">{shortcuts.map((shortcut, i) => <Link href={shortcut.href} key={shortcut.title} className="dashboard-shortcut"><span className="dashboard-shortcut-icon" aria-hidden="true">{["↻", "+", "▤", "▦"][i]}</span><strong>{shortcut.title}</strong><span>{shortcut.detail}</span><span className="dashboard-open">Отвори <span aria-hidden="true">→</span></span></Link>)}</div>

    <div className="dashboard-section-heading dashboard-recent-title"><div><h2>Последни изпълнения</h2><p>Реални резултати от запазените отчети</p></div><Link href="/reports" className="dashboard-text-link">Всички отчети <span aria-hidden="true">→</span></Link></div>
    <div className="dashboard-history">
      {reportsState === "loading" && <div className="dashboard-empty">Зареждане на изпълненията…</div>}
      {reportsState === "unavailable" && <div className="dashboard-empty">В момента не можем да заредим историята. Опитай отново по-късно или отвори „Отчети“.</div>}
      {reportsState === "ready" && reports.length === 0 && <div className="dashboard-empty">Все още няма запазени изпълнения.</div>}
      {reportsState === "ready" && reports.map(report => <div className="dashboard-history-row" key={report.pathname}><div><strong>{easyreaTasks.find(task => task.key === report.task)?.name || report.task}</strong><span>{new Date(report.createdAt).toLocaleString("bg-BG", { timeZone: "Europe/Sofia", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })} · {report.mode === "real" ? "Реално изпълнение" : "Тест"}</span></div><span className={`dashboard-result ${report.status === "success" ? "success" : "failure"}`}>{report.status === "success" ? "Успешно" : "Грешка"}</span></div>)}
    </div>
  </div>;
}
