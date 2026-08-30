import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, verifySessionToken } from "@/lib/auth";

/**
 * Protects the console surface and its data routes at the edge. Public
 * pages (landing, how-it-works, trust) stay open by design.
 */
const PUBLIC = ["/", "/how-it-works", "/trust", "/console/login", "/api/auth"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (PUBLIC.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }
  const authed = verifySessionToken(req.cookies.get(SESSION_COOKIE)?.value);
  if (authed) return NextResponse.next();
  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "UNAUTHENTICATED" }, { status: 401 });
  }
  const url = req.nextUrl.clone();
  url.pathname = "/console/login";
  url.searchParams.set("from", pathname);
  return NextResponse.redirect(url);
}

export const config = {
  // Node runtime required: session verification uses node:crypto HMAC.
  runtime: "nodejs",
  matcher: ["/console/:path*", "/api/cases/:path*", "/api/review/:path*", "/api/bundle/:path*", "/api/metrics/:path*"],
};
