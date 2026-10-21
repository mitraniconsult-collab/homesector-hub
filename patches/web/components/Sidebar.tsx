"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  ["/", "Dashboard"],
  ["/easyrea", "Easyrea Sync"],
  ["/logistics", "Logistics"],
  ["/social", "Social"],
  ["/feeds", "Feeds"],
  ["/reports", "Reports"],
  ["/settings", "Settings"]
];

export default function Sidebar() {
  const pathname = usePathname();
  return <aside className="sidebar">
    <div className="logo"><b>HS</b><span>Operations Hub</span></div>
    <nav>{items.map(([href,label]) => <Link key={href} href={href} className={pathname === href ? "active" : ""}>{label}</Link>)}</nav>
    <div className="sidebarFooter"><span className="dot online"/> Internal workspace</div>
  </aside>;
}
