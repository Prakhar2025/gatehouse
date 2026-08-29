import { NextResponse } from "next/server";
import { countOverrides, putOverride } from "@/lib/aws";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json(await countOverrides());
  } catch (err) {
    console.error("override count failed", err);
    return NextResponse.json({ error: "OVERRIDE_READ_FAILED" }, { status: 502 });
  }
}

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as { case_id?: string; agree?: boolean; note?: string };
    if (!body.case_id || typeof body.agree !== "boolean") {
      return NextResponse.json({ error: "INVALID_BODY" }, { status: 400 });
    }
    await putOverride({ case_id: body.case_id, agree: body.agree, note: body.note, actor: "guardian" });
    return NextResponse.json({ ok: true });
  } catch (err) {
    console.error("override write failed", err);
    return NextResponse.json({ error: "OVERRIDE_WRITE_FAILED" }, { status: 502 });
  }
}
