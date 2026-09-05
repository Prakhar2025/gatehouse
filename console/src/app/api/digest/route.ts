import { NextResponse } from "next/server";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, ScanCommand } from "@aws-sdk/lib-dynamodb";
import { toStringArray } from "@/lib/aws";

export const dynamic = "force-dynamic";

/** The weekly digest, computed live: the quiet-week story made checkable. */
export async function GET() {
  const region = process.env.GATEHOUSE_REGION ?? "ap-south-1";
  const table = process.env.GATEHOUSE_CASES_TABLE_NAME ?? "gatehouse-cases-staging";
  const doc = DynamoDBDocumentClient.from(new DynamoDBClient({ region }));
  const scan = await doc.send(
    new ScanCommand({
      TableName: table,
      FilterExpression: "#ca >= :start AND contains(sk, :b)",
      ExpressionAttributeNames: { "#ca": "created_at" },
      ExpressionAttributeValues: {
        ":start": Math.floor(Date.parse("2026-08-27T00:00:00Z") / 1000),
        ":b": "#BUNDLE#",
      },
    }),
  );
  const items = (scan.Items ?? []) as Array<Record<string, unknown>>;
  const rows = items
    .map((i) => ({
      case_id: String(i.case_id ?? ""),
      verdict: String(i.verdict ?? ""),
      reason_codes: toStringArray(i.reason_codes).filter((x) => x !== "NONE"),
      text: String(i.raw_text_redacted ?? ""),
      at: new Date(Number(i.created_at ?? 0) * 1000).toISOString(),
    }))
    .filter((r) => !r.text.includes("[ref ") && !r.text.includes("[smoke"))
    .sort((a, b) => b.at.localeCompare(a.at));
  const escalations = rows.filter((r) => r.verdict !== "SAFE");
  return NextResponse.json({
    generated_at: new Date().toISOString(),
    cases: rows.length,
    silent: rows.length - escalations.length,
    escalations,
  });
}
