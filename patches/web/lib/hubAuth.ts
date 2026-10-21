import { sealData, unsealData } from "iron-session";
import { createHash, scrypt, timingSafeEqual } from "node:crypto";
import { promisify } from "node:util";

export const SESSION_COOKIE = process.env.NODE_ENV === "production" ? "__Host-hub-session" : "hub-session";
export const SESSION_TTL = 12 * 60 * 60;
const derive = promisify(scrypt);
type Session = { user: string; version: string; expires: number };
function version() {
  return createHash("sha256").update(process.env.HUB_LOGIN_PASSWORD_HASH || "").digest("hex");
}
export function configured() {
  return !!process.env.HUB_LOGIN_USER && !!process.env.HUB_LOGIN_PASSWORD_HASH && (process.env.HUB_SESSION_SECRET?.length || 0) >= 32;
}
export async function validSession(cookie?: string) {
  if (!cookie || !configured()) return false;
  try {
    const data = await unsealData<Session>(cookie, { password: process.env.HUB_SESSION_SECRET!, ttl: SESSION_TTL });
    return data.user === process.env.HUB_LOGIN_USER && data.version === version() && data.expires > Date.now();
  } catch { return false; }
}
export async function sessionSeal() {
  return sealData({ user: process.env.HUB_LOGIN_USER!, version: version(), expires: Date.now() + SESSION_TTL * 1000 }, { password: process.env.HUB_SESSION_SECRET!, ttl: SESSION_TTL });
}
export async function validCredentials(user: string, password: string) {
  if (!configured() || password.length > 256 || user.length > 120) return false;
  const [salt, hash] = process.env.HUB_LOGIN_PASSWORD_HASH!.split(":");
  if (!salt || !/^[a-f0-9]{128}$/.test(hash || "")) return false;
  const derived = await derive(password, salt, 64) as Buffer;
  const userHash = createHash("sha256").update(user).digest();
  const expectedUser = createHash("sha256").update(process.env.HUB_LOGIN_USER!).digest();
  return timingSafeEqual(derived, Buffer.from(hash, "hex")) && timingSafeEqual(userHash, expectedUser);
}
export function sameOrigin(request: Request) {
  try {
    const origin = new URL(request.headers.get("origin") || "");
    return ["https:", "http:"].includes(origin.protocol) && origin.host === request.headers.get("host");
  } catch { return false; }
}
// Only these machine endpoints accept the worker key. Each route also checks it.
export function workerRequest(request: Request) {
  const paths: Record<string, string[]> = {
    "/api/catalog-cache": ["GET", "PUT"],
    "/api/image-job-state": ["GET", "PUT"],
    "/api/reports": ["POST"],
  };
  if (!paths[new URL(request.url).pathname]?.includes(request.method)) return false;
  const token = process.env.HUB_WORKER_TOKEN;
  const actual = Buffer.from(request.headers.get("authorization") || "");
  const expected = Buffer.from(`Bearer ${token}`);
  return !!token && actual.length === expected.length && timingSafeEqual(actual, expected);
}
export function safeReturn(value: string | null) {
  return value && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\") && !value.startsWith("/login") && !value.startsWith("/api/") ? value : "/";
}
