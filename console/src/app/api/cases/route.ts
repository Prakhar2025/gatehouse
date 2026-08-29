import { NextResponse } from "next/server";
import { listLiveCases } from "@/lib/aws";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const cases = await listLiveCases();
    return NextResponse.json({ cases });
  } catch (err) {
    console.error("live cases read failed", err);
    return NextResponse.json({ error: "LIVE_READ_FAILED" }, { status: 502 });
  }
}
