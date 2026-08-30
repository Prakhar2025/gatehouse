/**
 * Live transport: the same GatehouseApi surface, backed by the console's
 * own API routes, which read the real Dynamo tables server-side. Household,
 * audit, and benchmark-metrics screens stay on the mock until their tables
 * exist; everything verdict-path is live.
 */
import type { GatehouseApi } from "./client";
import { MOCK_AUDIT, MOCK_HOUSEHOLD, MOCK_METRICS } from "./mock-data";
import type {
  AuditEntry,
  CasePage,
  CaseSummary,
  EvidenceBundle,
  Health,
  Household,
  MetricsSnapshot,
  SpendRollup,
} from "./schemas";

const j = async <T,>(input: string | Response, init?: RequestInit): Promise<T> => {
  const r = typeof input === "string" ? await fetch(input, init) : input;
  if (!r.ok) throw new Error(`live_${r.status}`);
  return (await r.json()) as T;
};

const toSummary = (c: Record<string, unknown>): CaseSummary => {
  const verdict = (c.verdict as string) ?? "NEEDS_HUMAN";
  const text = String(c.text ?? "");
  return {
    case_id: String(c.case_id),
    state: verdict === "SAFE" ? "CLOSED_SILENT" : "ESCALATED",
    verdict: verdict as CaseSummary["verdict"],
    confidence: (c.confidence as number) ?? null,
    why_line: text.slice(0, 90) || "(no preview)",
    member_name: String(c.member_name ?? "member"),
    received_at: String(c.received_at),
    degraded_flags: (c.degraded_flags as string[]) ?? [],
    recommended_action: verdict === "SAFE" ? "none" : "review_bundle",
  };
};

export const liveApi: GatehouseApi = {
  async getHealth(): Promise<Health> {
    const r = await j<{ health: Health }>("/api/metrics");
    return r.health;
  },
  async listCases(params): Promise<CasePage> {
    const raw = await j<{ cases: Record<string, unknown>[] }>("/api/cases");
    let cases = raw.cases.map(toSummary);
    if (params?.state) cases = cases.filter((c) => c.state === params.state);
    return { cases, next_cursor: null };
  },
  async getCase(caseId): Promise<CaseSummary> {
    const page = await this.listCases();
    const c = page.cases.find((x) => x.case_id === caseId);
    if (!c) throw new Error("CASE_NOT_FOUND");
    return c;
  },
  async getBundle(caseId): Promise<EvidenceBundle> {
    return j<EvidenceBundle>(`/api/bundle?id=${encodeURIComponent(caseId)}`);
  },
  async getCaseAudit(): Promise<AuditEntry[]> {
    return [];
  },
  async postDecision(caseId, body): Promise<{ case_id: string; state: "CLOSED_ACTIONED"; graph_commit: string }> {
    await j("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_id: caseId, agree: true, note: body.note ?? body.action }),
    });
    return { case_id: caseId, state: "CLOSED_ACTIONED", graph_commit: "queued" };
  },
  async getHousehold(): Promise<Household> {
    return structuredClone(MOCK_HOUSEHOLD);
  },
  async getAudit(): Promise<AuditEntry[]> {
    return MOCK_AUDIT;
  },
  async getMetrics(): Promise<MetricsSnapshot> {
    const r = await j<{ metrics: MetricsSnapshot }>("/api/metrics");
    return { ...MOCK_METRICS, ...r.metrics };
  },
  async getSpend(): Promise<SpendRollup> {
    const m = await this.getMetrics();
    return {
      window: "24h",
      total_usd: m.spend_7d_usd,
      per_stage: [{ stage: "triage", calls: 0, usd: m.spend_7d_usd }],
    };
  },
};
