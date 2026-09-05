import { NextResponse } from "next/server";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, ScanCommand } from "@aws-sdk/lib-dynamodb";
import { toStringArray } from "@/lib/aws";

export const dynamic = "force-dynamic";

/** Live evidence bundle for one case, mapped from the persisted BUNDLE item. */
export async function GET(req: Request) {
  const id = new URL(req.url).searchParams.get("id");
  if (!id) return NextResponse.json({ error: "MISSING_ID" }, { status: 400 });
  const region = process.env.GATEHOUSE_REGION ?? "ap-south-1";
  const table = process.env.GATEHOUSE_CASES_TABLE_NAME ?? "gatehouse-cases-staging";
  const doc = DynamoDBDocumentClient.from(new DynamoDBClient({ region }));
  const scan = await doc.send(
    new ScanCommand({
      TableName: table,
      FilterExpression: "contains(sk, :b) AND contains(sk, :id)",
      ExpressionAttributeValues: { ":b": "#BUNDLE#", ":id": id },
    }),
  );
  const item = (scan.Items ?? [])[0] as Record<string, unknown> | undefined;
  if (!item) return NextResponse.json({ error: "CASE_NOT_FOUND" }, { status: 404 });
  const parse = (key: string, fallback: unknown) => {
    try {
      const raw = item[key];
      return typeof raw === "string" ? JSON.parse(raw) : (raw ?? fallback);
    } catch {
      return fallback;
    }
  };
  const pkg = parse("package", {}) as Record<string, unknown>;
  const triage = parse("triage", {}) as Record<string, unknown>;
  const findings = parse("verify_findings", []) as Array<Record<string, unknown>>;
  const graph = parse("graph", { identifiers: [], prior_events: 0, max_taint: 0, unavailable: false });
  const flags = toStringArray(item.degraded_flags).filter((x) => x !== "NONE");
  return NextResponse.json({
    bundle_id: String(item.sk ?? id),
    case_id: String(item.case_id ?? id),
    household_id: String(item.pk ?? "").replace("HOUSEHOLD#", ""),
    created_at: new Date(Number(item.created_at ?? 0) * 1000).toISOString(),
    pack_version: String(item.pack_version ?? "0.2.0"),
    prompt_versions: {},
    verdict: item.verdict ?? "NEEDS_HUMAN",
    confidence: Number(item.verdict_confidence ?? 0),
    reason_codes: toStringArray(item.reason_codes).filter((x) => x !== "NONE"),
    recommended_action: (pkg.recommended_action as string) ?? "review_bundle",
    degraded_flags: flags,
    signal_view: {
      channel: String(item.channel ?? "telegram"),
      member_name: "member",
      text: String(item.raw_text_redacted ?? ""),
      received_at: new Date(Number(item.created_at ?? 0) * 1000).toISOString(),
    },
    triage: {
      signal_class: triage.signal_class ?? "SCREEN",
      confidence: Number(triage.confidence ?? 0),
      payment_intent: Boolean(triage.payment_intent),
      urgency_signals: toStringArray(triage.urgency_signals),
      reason_code: String(triage.reason_code ?? ""),
      band_source: "model",
      rule_class: triage.signal_class ?? "SCREEN",
    },
    findings: findings.map((f) => ({
      subject: String(f.subject ?? ""),
      check_type: String(f.check_type ?? "domain_intel"),
      result: String(f.result ?? "INCONCLUSIVE"),
      evidence_ref: String(f.evidence_ref ?? ""),
      weight: Number(f.weight ?? 0),
    })),
    graph,
    trace: {
      total_ms: 0,
      spans: [],
      note: "stage timings are not persisted in v1 bundles; live traces live in CloudWatch",
    },
    cost: {
      total_usd: Number(item.spend_usd ?? 0),
      entries: [
        {
          stage: "investigation",
          model_id: process.env.GATEHOUSE_MODEL_ID ?? "apac.amazon.nova-micro-v1:0",
          input_tokens: 0,
          output_tokens: 0,
          usd: Number(item.spend_usd ?? 0),
        },
      ],
    },
    engagement: null,
    integrity: { sha256: String(item.canary ?? ""), chain_prev: null },
  });
}
