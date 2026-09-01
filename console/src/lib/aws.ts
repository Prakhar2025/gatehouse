import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, ScanCommand, PutCommand } from "@aws-sdk/lib-dynamodb";

/**
 * Server-side Dynamo access for the live review loop. Runs only in API
 * routes: the credential chain is the default one (IAM role on Vercel, the
 * local chain in development), and no credential ever reaches the client.
 */
const region = process.env.GATEHOUSE_REGION ?? "ap-south-1";
const casesTable = process.env.GATEHOUSE_CASES_TABLE_NAME ?? "gatehouse-cases-staging";
const householdId = process.env.GATEHOUSE_HOUSEHOLD_ID ?? "shukla-home";

const doc = DynamoDBDocumentClient.from(new DynamoDBClient({ region }), {
  marshallOptions: { removeUndefinedValues: true },
});

export interface LiveCase {
  case_id: string;
  household_id: string;
  verdict: string | null;
  confidence: number | null;
  member_name: string;
  received_at: string;
  text: string;
  degraded_flags: string[];
}

/** Real soak-window cases from bundle items, newest first, test traffic excluded. */
export async function listLiveCases(limit = 50): Promise<LiveCase[]> {
  const scan = await doc.send(
    new ScanCommand({
      TableName: casesTable,
      FilterExpression: "#ca >= :start AND contains(sk, :b)",
      ExpressionAttributeNames: { "#ca": "created_at" },
      ExpressionAttributeValues: {
        ":start": SOAK_START_EPOCH,
        ":b": "#BUNDLE#",
      },
    }),
  );
  const items = (scan.Items ?? []) as Array<Record<string, unknown>>;
  const asArray = (v: unknown): string[] =>
    Array.isArray(v) ? v.map(String) : v && typeof v === "object" ? Array.from(Object.values(v as Record<string, string>)).map(String) : [];
  return items
    .map((i) => {
      const text = String(i.raw_text_redacted ?? "");
      const flags = asArray(i.degraded_flags).filter((f) => f !== "NONE");
      return {
        case_id: String(i.case_id ?? String(i.sk ?? "").replace("CASE#", "").split("#")[0]),
        household_id: String(i.pk ?? "").replace("HOUSEHOLD#", ""),
        verdict: (i.verdict as string) ?? null,
        confidence: i.verdict_confidence != null ? Number(i.verdict_confidence) : null,
        member_name: "member",
        received_at: new Date(Number(i.created_at) * 1000).toISOString(),
        text,
        degraded_flags: flags,
      };
    })
    // Structural exclusion: harness sends carry "[ref NNN]" tags, smoke sends
    // carry "[smoke"; neither belongs in a guardian truth-tapping feed.
    .filter((c) => !c.text.includes("[ref ") && !c.text.includes("[smoke"))
    .sort((a, b) => b.received_at.localeCompare(a.received_at))
    .slice(0, limit);
}

const SOAK_START_EPOCH = Math.floor(Date.parse("2026-08-27T00:00:00Z") / 1000);

export interface OverrideRow {
  case_id: string;
  agree: boolean;
  note?: string;
  actor: string;
}

/** Guardian agreement tap: the label that trains the next calibration. */
export async function putOverride(row: OverrideRow): Promise<void> {
  await doc.send(
    new PutCommand({
      TableName: casesTable,
      Item: {
        pk: `HOUSEHOLD#${householdId}`,
        sk: `OVERRIDE#${Date.now()}#${row.case_id}`,
        case_id: row.case_id,
        agree: row.agree,
        note: row.note ?? "",
        actor: row.actor,
        created_at: Math.floor(Date.now() / 1000),
      },
    }),
  );
}

export interface OverrideSummary {
  /** Distinct cases carrying a label, not rows written. */
  total: number;
  /** Distinct cases whose most recent label disagrees with the verdict. */
  disagreed: number;
  /** case_id -> most recent agreement tap, so the feed can show its own state. */
  labels: Record<string, boolean>;
}

/**
 * Reduce raw override rows to the latest label per case. Rows stay
 * append-only because the audit chain must keep every tap, but a case
 * labelled twice has to count once: a denominator that grows on re-taps
 * reports a disagreement rate that was never measured. Pure and exported so
 * the reduction is verifiable without a table (scripts/check-overrides.ts).
 */
export function reduceOverrides(items: Array<Record<string, unknown>>): OverrideSummary {
  // sk is OVERRIDE#<ms>#<case_id>; the millisecond stamp orders taps that
  // share a created_at second, which a scan returns in no useful order.
  const stampOf = (row: Record<string, unknown>): number => {
    const fromSk = Number(String(row.sk ?? "").split("#")[1]);
    return Number.isFinite(fromSk) ? fromSk : Number(row.created_at ?? 0) * 1000;
  };

  const latest = new Map<string, { at: number; agree: boolean }>();
  for (const row of items) {
    const caseId = String(row.case_id ?? "");
    if (!caseId) continue;
    const at = stampOf(row);
    const seen = latest.get(caseId);
    if (!seen || at > seen.at) latest.set(caseId, { at, agree: row.agree === true });
  }

  const labels: Record<string, boolean> = {};
  let disagreed = 0;
  for (const [caseId, row] of latest) {
    labels[caseId] = row.agree;
    if (!row.agree) disagreed += 1;
  }
  return { total: latest.size, disagreed, labels };
}

/** Latest guardian label per case, read from the live table. */
export async function readOverrides(): Promise<OverrideSummary> {
  const scan = await doc.send(
    new ScanCommand({
      TableName: casesTable,
      FilterExpression: "begins_with(sk, :ovr)",
      ExpressionAttributeValues: { ":ovr": "OVERRIDE#" },
    }),
  );
  return reduceOverrides((scan.Items ?? []) as Array<Record<string, unknown>>);
}

export { casesTable, region };
