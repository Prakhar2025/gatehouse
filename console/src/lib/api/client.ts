/**
 * Typed API client for the doc 14 contract. Today every method routes to
 * the mock transport; the moment the gateway ships, `setTransport` swaps in
 * the fetch transport that hits `/v1` with the same shapes, so no screen
 * code changes. Errors surface as typed problem+json codes per RFC 7807.
 */
import type {
  AuditEntry,
  CasePage,
  CaseSummary,
  DecisionResponse,
  EvidenceBundle,
  Health,
  Household,
  MetricsSnapshot,
  SpendRollup,
} from "./schemas";
import { liveApi } from "./live";

export interface GatehouseApi {
  getHealth(): Promise<Health>;
  listCases(params?: { state?: string; limit?: number; cursor?: string | null }): Promise<CasePage>;
  getCase(caseId: string): Promise<CaseSummary>;
  getBundle(caseId: string): Promise<EvidenceBundle>;
  getCaseAudit(caseId: string): Promise<AuditEntry[]>;
  postDecision(
    caseId: string,
    body: { action: "warn_member" | "allow" | "block_report" | "verify_with_issuer" | "ignore"; note?: string; notify_member?: boolean }
  ): Promise<DecisionResponse>;
  getHousehold(): Promise<Household>;
  getAudit(): Promise<AuditEntry[]>;
  getMetrics(): Promise<MetricsSnapshot>;
  getSpend(): Promise<SpendRollup>;
}

const delay = (ms = 220) => new Promise((r) => setTimeout(r, ms));

export const mockApi: GatehouseApi = {
  async getHealth() {
    await delay(80);
    return (await import("./mock-data")).MOCK_HEALTH;
  },
  async listCases(params) {
    await delay();
    const data = await import("./mock-data");
    let cases = [...data.MOCK_CASES];
    if (params?.state) cases = cases.filter((c) => c.state === params.state);
    return { cases, next_cursor: null };
  },
  async getCase(caseId) {
    await delay(120);
    const data = await import("./mock-data");
    const c = data.MOCK_CASES.find((x) => x.case_id === caseId);
    if (!c) throw new ApiError("CASE_NOT_FOUND", 404);
    return c;
  },
  async getBundle(caseId) {
    await delay(160);
    const data = await import("./mock-data");
    const b = data.MOCK_BUNDLES[caseId];
    if (!b) throw new ApiError("CASE_NOT_FOUND", 404);
    return b;
  },
  async getCaseAudit(caseId) {
    await delay(120);
    const data = await import("./mock-data");
    return data.MOCK_AUDIT.filter((a) => a.case_id === caseId);
  },
  async postDecision(caseId) {
    await delay(300);
    const data = await import("./mock-data");
    const c = data.MOCK_CASES.find((x) => x.case_id === caseId);
    if (!c) throw new ApiError("CASE_NOT_FOUND", 404);
    if (c.state === "CLOSED_ACTIONED") throw new ApiError("CASE_ALREADY_CLOSED", 409);
    return { case_id: caseId, state: "CLOSED_ACTIONED", graph_commit: "queued" };
  },
  async getHousehold() {
    await delay(140);
    return structuredClone((await import("./mock-data")).MOCK_HOUSEHOLD);
  },
  async getAudit() {
    await delay(180);
    return (await import("./mock-data")).MOCK_AUDIT;
  },
  async getMetrics() {
    await delay(120);
    return (await import("./mock-data")).MOCK_METRICS;
  },
  async getSpend() {
    await delay(100);
    return (await import("./mock-data")).MOCK_SPEND;
  },
};

export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
  ) {
    super(`api error ${code}`);
    this.name = "ApiError";
  }
}

let transport: GatehouseApi | null = null;

/** The live transport is the default; previews and tests inject the mock
 * explicitly via setTransport(mockApi). */
export const api = (): GatehouseApi => {
  if (!transport) transport = liveApi;
  return transport;
};

/** Swap in the real fetch transport when the gateway is live. */
export const setTransport = (t: GatehouseApi) => {
  transport = t;
};
