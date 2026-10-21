import { safeReturn } from "@/lib/hubAuth";
export default async function Login({ searchParams }: { searchParams: Promise<{ next?: string; error?: string }> }) {
  const params = await searchParams;
  return <section className="card" style={{ width: "100%", maxWidth: 420, margin: "12vh auto", padding: 32 }}>
    <div className="logo"><b>HS</b><span>Homesector Hub</span></div>
    <h1 style={{ marginTop: 0 }}>Вход</h1><p className="muted" style={{ marginBottom: 24 }}>Работно пространство на Homesector</p>
    <form action="/api/auth/login" method="post" className="stack">
      <input type="hidden" name="next" value={safeReturn(params.next || null)} />
      <label className="field">Потребител<input name="username" autoComplete="username" required maxLength={120} autoFocus /></label>
      <label className="field">Парола<input name="password" type="password" autoComplete="current-password" required maxLength={256} /></label>
      {params.error && <p role="alert" style={{ color: "var(--bad)" }}>Невалиден потребител или парола.</p>}
      <button className="btn primary" type="submit">Вход</button>
    </form>
  </section>;
}
