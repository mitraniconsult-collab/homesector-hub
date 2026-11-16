"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRef, useState } from "react";
import "./hub-navigation.css";

const groups = [
  { label: "Начало", links: [["/", "Табло"]] },
  { label: "Каталог и поръчки", links: [["/easyrea", "Easyrea Sync"], ["/barcodes", "EAN баркодове"], ["/logistics", "Логистика"]] },
  { label: "Канали", links: [["/feeds", "Продуктови фийдове"], ["/social", "Социални мрежи"]] },
  { label: "Управление", links: [["/reports", "Отчети"], ["/settings", "Настройки"]] },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const isCurrent = (href: string) => pathname === href || (href !== "/" && pathname.startsWith(href + "/"));
  return <aside className="sidebar hs-sidebar" data-route={pathname === "/reports" ? "reports" : undefined} onKeyDown={event => {
    if (event.key === "Escape" && open) { setOpen(false); toggle.current?.focus(); }
  }}>
    <div className="hs-header">
      <Link href="/" aria-label="Homesector Hub — Табло" onClick={() => setOpen(false)}>
        <img src="https://cdn.shopify.com/s/files/1/0676/9213/4667/files/Homesector_Logo_400x100px.png?v=1723215396" width="160" height="40" alt="Homesector" />
      </Link>
      <button ref={toggle} type="button" className="hs-toggle" aria-expanded={open} aria-controls="hs-navigation" onClick={() => setOpen(value => !value)}>
        {open ? "Затвори" : "Меню"}
      </button>
    </div>
    <div id="hs-navigation" className="hs-navigation" data-open={open}>
      <nav aria-label="Основно меню">
        {groups.map(group => <div key={group.label} className="hs-group">
          <div className="hs-group-label">{group.label}</div>
          {group.links.map(([href, label]) => <Link key={href} href={href} onClick={() => setOpen(false)} className={isCurrent(href) ? "active" : ""} aria-current={isCurrent(href) ? "page" : undefined}>{label}</Link>)}
        </div>)}
      </nav>
      <form className="hs-logout" action="/api/auth/logout" method="post"><button type="submit" className="btn secondary">Изход</button></form>
    </div>
  </aside>;
}
