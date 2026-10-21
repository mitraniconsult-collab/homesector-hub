import type { Metadata } from "next";
import "./globals.css";
import { cookies } from "next/headers";
import { SESSION_COOKIE, validSession } from "@/lib/hubAuth";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = { title: "Homesector Operations Hub", description: "Internal operations workspace" };

export default async function RootLayout({ children }: Readonly<{children: React.ReactNode}>) {
  const authenticated = await validSession((await cookies()).get(SESSION_COOKIE)?.value);
  if (!authenticated) return <html lang="bg"><body><main style={{padding: 20}}>{children}</main></body></html>;
  return <html lang="bg"><body><div className="appShell"><Sidebar/><main className="mainArea">{children}</main></div></body></html>;
}
