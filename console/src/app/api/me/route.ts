import { NextResponse } from "next/server";
import { authConfigured, verifySessionToken } from "@/lib/auth";
import { cookies } from "next/headers";

export const dynamic = "force-dynamic";

/** Auth probe for the client gate: 200 when the session cookie is valid. */
export async function GET() {
  if (!authConfigured()) {
    return NextResponse.json({ error: "AUTH_NOT_CONFIGURED" }, { status: 503 });
  }
  const jar = await cookies();
  const ok = verifySessionToken(jar.get("gh_session")?.value);
  return NextResponse.json({ ok }, { status: ok ? 200 : 401 });
}
