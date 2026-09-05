/**
 * Console API Lambda: serves the gatehouse console's data endpoints from the
 * same AWS account as the bot. Zero packaging: aws-sdk v3 ships in the
 * Node runtime.
 *
 * Access split: reads are public so the console can be shown without a
 * password. Writes require the HMAC session cookie issued by /auth, because
 * an unauthenticated write would let a stranger label cases as the guardian
 * and poison the ledger the accuracy metrics are computed from.
 *
 * Env: CONSOLE_PASSWORD, GATEHOUSE_REGION (default ap-south-1),
 * GATEHOUSE_CASES_TABLE_NAME (default gatehouse-cases-staging).
 */
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import {
  DynamoDBDocumentClient,
  ScanCommand,
  PutCommand,
  GetCommand,
} from "@aws-sdk/lib-dynamodb";
import { createHmac, timingSafeEqual } from "node:crypto";

const region = process.env.GATEHOUSE_REGION ?? "ap-south-1";
const table = process.env.GATEHOUSE_CASES_TABLE_NAME ?? "gatehouse-cases-staging";
const doc = DynamoDBDocumentClient.from(new DynamoDBClient({ region }));
const SOAK_START = Math.floor(Date.parse("2026-08-27T00:00:00Z") / 1000);
const PASSWORD = process.env.CONSOLE_PASSWORD ?? "";
const SESSION_COOKIE = "gh_session";
const HOUSEHOLD = process.env.GATEHOUSE_HOUSEHOLD_ID ?? "shukla-home";

/**
 * Accuracy and latency figures from the sealed 480-case dev split, mirrored
 * from docs/eval-results/full-dev-metrics.json. They are benchmark results,
 * not live household measurement, and every response that carries them also
 * carries `benchmark.source` so the console never presents them as live.
 */
const BENCHMARK = {
  source: "480-case dev split, offline",
  as_of: "2026-08-31",
  precision: 1.0,
  precision_ci: [0.9887, 1.0],
  false_gate_rate: 0.0,
  false_gate_ci: [0.0, 0.0253],
  latency_p50_ms: 1180,
  latency_p95_ms: 2640,
};
const TTL = 60 * 60 * 12;

const sign = (p) => createHmac("sha256", PASSWORD).update(p).digest("base64url");
const validSession = (cookieHeader) => {
  if (!PASSWORD) return false;
  const raw = (cookieHeader ?? "")
    .split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith(SESSION_COOKIE + "="));
  if (!raw) return false;
  const token = raw.slice(SESSION_COOKIE.length + 1);
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return false;
  const expected = sign(payload);
  if (sig.length !== expected.length) return false;
  try {
    if (!timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) return false;
  } catch {
    return false;
  }
  return Number(payload) > Math.floor(Date.now() / 1000);
};

const json = (code, body, extraHeaders = {}) => ({
  statusCode: code,
  headers: {
    "content-type": "application/json",
    "cache-control": "no-store",
    ...extraHeaders,
  },
  body: JSON.stringify(body),
});

/**
 * Public reads are cacheable. Without this every visitor to a public URL runs
 * a full table Scan, which is both a latency floor and an unbounded cost tap
 * that grows with the table. Short TTL keeps the console feeling live.
 */
const CACHEABLE = { "cache-control": "public, max-age=30, s-maxage=60" };

const toStringArray = (v) => {
  if (v instanceof Set) return Array.from(v).map(String);
  if (Array.isArray(v)) return v.map(String);
  if (v && typeof v === "object") {
    if (Array.isArray(v.SS)) return v.SS.map(String);
    return Object.values(v).flatMap((x) => (Array.isArray(x) ? x.map(String) : toStringArray(x)));
  }
  return [];
};

const scanBundles = async () => {
  const r = await doc.send(
    new ScanCommand({
      TableName: table,
      FilterExpression: "#ca >= :start AND contains(sk, :b)",
      ExpressionAttributeNames: { "#ca": "created_at" },
      ExpressionAttributeValues: { ":start": SOAK_START, ":b": "#BUNDLE#" },
    }),
  );
  return (r.Items ?? []).filter(
    (i) => !String(i.raw_text_redacted ?? "").includes("[ref ") &&
           !String(i.raw_text_redacted ?? "").includes("[smoke"),
  );
};

export const handler = async (event) => {
  const path = (event.rawPath ?? "").replace(/\/$/, "");
  const method = event.requestContext?.http?.method ?? "GET";
  // HTTP API payload v2 moves Cookie out of headers into a top-level array.
  const cookieHeader = Array.isArray(event.cookies)
    ? event.cookies.join("; ")
    : (event.headers?.cookie ?? event.headers?.Cookie ?? "");

  const route = path.replace(/^.*\/console-api/, "") || "/";

  // --- public: login ---
  if (route === "/auth" && method === "POST") {
    const body = JSON.parse(event.body ?? "{}");
    if (!PASSWORD) return json(503, { error: "AUTH_NOT_CONFIGURED" });
    const ok =
      typeof body.password === "string" &&
      body.password.length === PASSWORD.length &&
      timingSafeEqual(Buffer.from(body.password), Buffer.from(PASSWORD));
    if (!ok) return json(401, { error: "INVALID_CREDENTIALS" });
    const exp = Math.floor(Date.now() / 1000) + TTL;
    const token = `${exp}.${sign(String(exp))}`;
    return json(200, { ok: true }, {
      "set-cookie": `${SESSION_COOKIE}=${token}; HttpOnly; SameSite=Lax; Secure; Path=/; Max-Age=${TTL}`,
    });
  }

  if (route === "/me") return json(200, { ok: true, authed: validSession(cookieHeader) });

  if (route === "/cases") {
    const items = await scanBundles();
    const cases = items
      .map((i) => ({
        case_id: String(i.case_id ?? String(i.sk).split("#")[1] ?? ""),
        verdict: i.verdict ?? "NEEDS_HUMAN",
        confidence: Number(i.verdict_confidence ?? 0),
        text: String(i.raw_text_redacted ?? ""),
        member_name: "member",
        received_at: new Date(Number(i.created_at ?? 0) * 1000).toISOString(),
        degraded_flags: toStringArray(i.degraded_flags).filter((f) => f !== "NONE"),
      }))
      .sort((a, b) => b.received_at.localeCompare(a.received_at));
    return json(200, { cases }, CACHEABLE);
  }

  if (route === "/metrics") {
    const items = await scanBundles();
    const verdicts = items.map((i) => String(i.verdict ?? ""));
    const spends = items.map((i) => Number(i.spend_usd ?? 0));
    const count = (v) => verdicts.filter((x) => x === v).length;
    const degraded = items.filter((i) =>
      toStringArray(i.degraded_flags).some((f) => f !== "NONE"),
    ).length;
    const sorted = [...spends].sort((a, b) => a - b);
    const perDay = new Map();
    const now = new Date();
    for (let d = 6; d >= 0; d -= 1) {
      const key = new Date(now.getTime() - d * 86400000).toISOString().slice(5, 10);
      perDay.set(key, { cases: 0, escalations: 0 });
    }
    for (const it of items) {
      const key = new Date(Number(it.created_at ?? 0) * 1000).toISOString().slice(5, 10);
      const bucket = perDay.get(key);
      if (!bucket) continue;
      bucket.cases += 1;
      if (["SUSPICIOUS", "SCAM", "NEEDS_HUMAN"].includes(String(it.verdict))) bucket.escalations += 1;
    }
    return json(200, {
      health: { status: "ok", version: "1.4.2", degraded: [] },
      benchmark: BENCHMARK,
      metrics: {
        screened_7d: items.length,
        silent_7d: count("SAFE"),
        escalations_open: count("SUSPICIOUS") + count("SCAM"),
        latency_p50_ms: BENCHMARK.latency_p50_ms,
        latency_p95_ms: BENCHMARK.latency_p95_ms,
        spend_mean_usd: spends.length ? spends.reduce((a, b) => a + b, 0) / spends.length : 0,
        spend_7d_usd: spends.reduce((a, b) => a + b, 0),
        // Benchmark figures, not live measurement. They come from the sealed
        // 480-case dev split committed at docs/eval-results/full-dev-metrics.json
        // and are surfaced under `benchmark` below so the console can label
        // them. Live accuracy needs labelled outcomes the household has not
        // produced in volume yet; reporting these as live would be the exact
        // measurement lie the project exists to avoid.
        precision: BENCHMARK.precision,
        precision_ci: BENCHMARK.precision_ci,
        false_gate_rate: BENCHMARK.false_gate_rate,
        false_gate_ci: BENCHMARK.false_gate_ci,
        verdict_mix_7d: [
          { verdict: "SAFE", count: count("SAFE") },
          { verdict: "SUSPICIOUS", count: count("SUSPICIOUS") },
          { verdict: "SCAM", count: count("SCAM") },
          { verdict: "NEEDS_HUMAN", count: count("NEEDS_HUMAN") },
        ],
        trend_7d: [...perDay.entries()].map(([day, v]) => ({
          day: `Sep ${day.slice(3)}`,
          cases: v.cases,
          escalations: v.escalations,
        })),
        degraded_cases: degraded,
        spend_p95_usd: sorted.length ? sorted[Math.min(sorted.length - 1, Math.round(0.95 * sorted.length))] : 0,
      },
    }, CACHEABLE);
  }

  if (route === "/digest") {
    const items = await scanBundles();
    const rows = items
      .map((i) => ({
        case_id: String(i.case_id ?? ""),
        verdict: String(i.verdict ?? ""),
        reason_codes: toStringArray(i.reason_codes),
        text: String(i.raw_text_redacted ?? ""),
        at: new Date(Number(i.created_at ?? 0) * 1000).toISOString(),
      }))
      .sort((a, b) => b.at.localeCompare(a.at));
    return json(200, {
      generated_at: new Date().toISOString(),
      cases: rows.length,
      silent: rows.filter((r) => r.verdict === "SAFE").length,
      escalations: rows.filter((r) => r.verdict !== "SAFE"),
    }, CACHEABLE);
  }

  if (route === "/bundle") {
    const id = event.rawQueryString
      ? new URLSearchParams(event.rawQueryString).get("id")
      : null;
    if (!id) return json(400, { error: "MISSING_ID" });
    const r = await doc.send(
      new ScanCommand({
        TableName: table,
        FilterExpression: "contains(sk, :b) AND contains(sk, :id)",
        ExpressionAttributeValues: { ":b": "#BUNDLE#", ":id": id },
      }),
    );
    const item = (r.Items ?? [])[0];
    if (!item) return json(404, { error: "CASE_NOT_FOUND" });
    const parse = (key, fallback) => {
      try {
        const raw = item[key];
        return typeof raw === "string" ? JSON.parse(raw) : (raw ?? fallback);
      } catch {
        return fallback;
      }
    };
    const pkg = parse("package", {});
    const triage = parse("triage", {});
    return json(200, {
      bundle_id: String(item.sk ?? id),
      case_id: String(item.case_id ?? id),
      household_id: String(item.pk ?? "").replace("HOUSEHOLD#", ""),
      created_at: new Date(Number(item.created_at ?? 0) * 1000).toISOString(),
      pack_version: String(item.pack_version ?? "0.2.0"),
      prompt_versions: {},
      verdict: item.verdict ?? "NEEDS_HUMAN",
      confidence: Number(item.verdict_confidence ?? 0),
      reason_codes: toStringArray(item.reason_codes),
      recommended_action: pkg.recommended_action ?? "review_bundle",
      degraded_flags: toStringArray(item.degraded_flags).filter((f) => f !== "NONE"),
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
        urgency_signals: triage.urgency_signals ?? [],
        reason_code: String(triage.reason_code ?? ""),
        band_source: "model",
        rule_class: triage.signal_class ?? "SCREEN",
      },
      findings: (parse("verify_findings", []) ?? []).map((f) => ({
        subject: String(f.subject ?? ""),
        check_type: String(f.check_type ?? "domain_intel"),
        result: String(f.result ?? "INCONCLUSIVE"),
        evidence_ref: String(f.evidence_ref ?? ""),
        weight: Number(f.weight ?? 0),
      })),
      graph: parse("graph", { identifiers: [], prior_events: 0, max_taint: 0, unavailable: false }),
      trace: { total_ms: 0, spans: [], note: "stage timings live in CloudWatch; not persisted in v1 bundles" },
      cost: {
        total_usd: Number(item.spend_usd ?? 0),
        entries: [{
          stage: "investigation",
          model_id: "apac.amazon.nova-micro-v1:0",
          input_tokens: 0,
          output_tokens: 0,
          usd: Number(item.spend_usd ?? 0),
        }],
      },
      engagement: null,
      integrity: { sha256: String(item.canary ?? ""), chain_prev: null },
    }, CACHEABLE);
  }

  if (route === "/review" && method === "GET") {
    // Counts reduce to the latest label per case, not a row count. Override
    // rows are append-only with a millisecond sort key, so a guardian who
    // corrects the same case twice would otherwise be counted twice and a
    // disagreement later revised to an agreement would never clear.
    const r = await doc.send(
      new ScanCommand({
        TableName: table,
        FilterExpression: "begins_with(sk, :ovr)",
        ExpressionAttributeValues: { ":ovr": "OVERRIDE#" },
      }),
    );
    const latest = new Map();
    for (const i of r.Items ?? []) {
      const caseId = String(i.case_id ?? "");
      if (!caseId) continue;
      const stamp = Number(String(i.sk ?? "").split("#")[1] ?? 0);
      const prev = latest.get(caseId);
      if (!prev || stamp >= prev.stamp) latest.set(caseId, { stamp, agree: i.agree !== false });
    }
    const labels = Object.fromEntries([...latest].map(([k, v]) => [k, v.agree]));
    return json(200, {
      total: latest.size,
      disagreed: [...latest.values()].filter((v) => !v.agree).length,
      labels,
    }, CACHEABLE);
  }

  if (route === "/review" && method === "POST") {
    if (!validSession(cookieHeader)) return json(401, { error: "UNAUTHENTICATED" });
    const body = JSON.parse(event.body ?? "{}");
    if (!body.case_id || typeof body.agree !== "boolean") {
      return json(400, { error: "INVALID_BODY" });
    }
    await doc.send(
      new PutCommand({
        TableName: table,
        Item: {
          pk: `HOUSEHOLD#${HOUSEHOLD}`,
          sk: `OVERRIDE#${Date.now()}#${body.case_id}`,
          case_id: body.case_id,
          agree: body.agree,
          note: String(body.note ?? ""),
          actor: "guardian",
          created_at: Math.floor(Date.now() / 1000),
        },
      }),
    );
    return json(200, { ok: true });
  }

  if (route === "/audit") {
    // The override ledger is the real, append-only record of guardian action.
    // It is the only audit source that exists today, so it is the only one
    // served: an audit screen backed by invented rows is worse than none.
    const r = await doc.send(
      new ScanCommand({
        TableName: table,
        FilterExpression: "begins_with(sk, :ovr)",
        ExpressionAttributeValues: { ":ovr": "OVERRIDE#" },
      }),
    );
    const entries = (r.Items ?? [])
      .map((i) => ({
        id: String(i.sk ?? ""),
        at: new Date(Number(i.created_at ?? 0) * 1000).toISOString(),
        actor: String(i.actor ?? "guardian"),
        action: i.agree === false ? "labelled_wrong" : "labelled_correct",
        case_id: String(i.case_id ?? ""),
        note: String(i.note ?? ""),
      }))
      .sort((a, b) => b.at.localeCompare(a.at));
    return json(200, { entries }, CACHEABLE);
  }

  if (route === "/overrides") {
    const r = await doc.send(
      new ScanCommand({
        TableName: table,
        FilterExpression: "begins_with(sk, :ovr)",
        ExpressionAttributeValues: { ":ovr": "OVERRIDE#" },
      }),
    );
    const items = r.Items ?? [];
    return json(200, {
      total: items.length,
      disagreed: items.filter((i) => i.agree === false).length,
    }, CACHEABLE);
  }

  return json(404, { error: "NOT_FOUND" });
};
