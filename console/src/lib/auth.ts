import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Gateway-lite auth for the single-household console (v1). A password from
 * the environment exchanges for an HMAC-signed HttpOnly session cookie.
 * Zero dependencies, zero network. Cognito replaces this at multi-tenant
 * scale (doc 10); the session boundary stays identical when it does.
 */
export const SESSION_COOKIE = "gh_session";
const SESSION_TTL_S = 60 * 60 * 12;

function secret(): string {
  return process.env.CONSOLE_PASSWORD ?? "";
}

export function authConfigured(): boolean {
  return secret().length >= 8;
}

function sign(payload: string): string {
  return createHmac("sha256", secret()).update(payload).digest("base64url");
}

export function createSessionToken(): { token: string; maxAge: number } {
  const exp = Math.floor(Date.now() / 1000) + SESSION_TTL_S;
  const payload = String(exp);
  return { token: `${payload}.${sign(payload)}`, maxAge: SESSION_TTL_S };
}

export function verifySessionToken(token: string | undefined): boolean {
  if (!token || !authConfigured()) return false;
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return false;
  const expected = sign(payload);
  if (
    sig.length !== expected.length ||
    !timingSafeEqual(Buffer.from(sig), Buffer.from(expected))
  ) {
    return false;
  }
  return Number(payload) > Math.floor(Date.now() / 1000);
}

export function verifyPassword(input: string | undefined): boolean {
  if (!input || !authConfigured()) return false;
  const a = Buffer.from(input);
  const b = Buffer.from(secret());
  return a.length === b.length && timingSafeEqual(a, b);
}
