/**
 * Wire contracts mirrored from the backend (doc 04 schemas, doc 06 bundle
 * layout, doc 14 endpoint payloads). Zod is the single source: TypeScript
 * types are inferred, so console drift from the API contract fails here
 * first, not in production.
 */
import { z } from "zod";

export const VerdictSchema = z.enum(["SAFE", "SUSPICIOUS", "SCAM", "NEEDS_HUMAN"]);
export type Verdict = z.infer<typeof VerdictSchema>;

export const SignalClassSchema = z.enum(["NOISE", "INFO", "SCREEN", "DECISION", "EMERGENCY"]);
export type SignalClass = z.infer<typeof SignalClassSchema>;

export const CheckTypeSchema = z.enum([
  "lexicon_rule",
  "issuer_rule",
  "domain_intel",
  "rail_format",
  "source_crosscheck",
  "temporal",
  "numerical",
]);
export type CheckType = z.infer<typeof CheckTypeSchema>;

export const CheckResultSchema = z.enum(["PASS", "FAIL", "INCONCLUSIVE"]);
export type CheckResult = z.infer<typeof CheckResultSchema>;

export const CaseStateSchema = z.enum([
  "RECEIVED",
  "INVESTIGATING",
  "ESCALATED",
  "CLOSED_ACTIONED",
  "CLOSED_SILENT",
]);
export type CaseState = z.infer<typeof CaseStateSchema>;

export const HealthSchema = z.object({
  status: z.string(),
  version: z.string(),
  degraded: z.array(z.string()),
});
export type Health = z.infer<typeof HealthSchema>;

export const VerificationFindingSchema = z.object({
  subject: z.string(),
  check_type: CheckTypeSchema,
  result: CheckResultSchema,
  evidence_ref: z.string(),
  weight: z.number(),
});
export type VerificationFinding = z.infer<typeof VerificationFindingSchema>;

export const GraphIdentifierSchema = z.object({
  kind: z.enum(["PHONE", "VPA", "DOMAIN", "URL_PATH", "BANK_ACCT", "EMAIL", "UTR_REF"]),
  hashed_value: z.string(),
});
export type GraphIdentifier = z.infer<typeof GraphIdentifierSchema>;

export const GraphFindingSchema = z.object({
  identifiers: z.array(GraphIdentifierSchema),
  prior_events: z.number(),
  max_taint: z.number(),
  unavailable: z.boolean(),
});
export type GraphFinding = z.infer<typeof GraphFindingSchema>;

export const TraceSpanSchema = z.object({
  stage: z.string(),
  status: z.enum(["ok", "degraded", "failed"]),
  ms: z.number(),
});
export type TraceSpan = z.infer<typeof TraceSpanSchema>;

export const CostEntrySchema = z.object({
  stage: z.string(),
  model_id: z.string(),
  input_tokens: z.number(),
  output_tokens: z.number(),
  usd: z.number(),
});
export type CostEntry = z.infer<typeof CostEntrySchema>;

export const EngagementTurnSchema = z.object({
  role: z.enum(["engage_agent", "suspect"]),
  text: z.string(),
  offset_s: z.number(),
});
export type EngagementTurn = z.infer<typeof EngagementTurnSchema>;

export const EvidenceBundleSchema = z.object({
  bundle_id: z.string(),
  case_id: z.string(),
  household_id: z.string(),
  created_at: z.string(),
  pack_version: z.string(),
  prompt_versions: z.record(z.string(), z.string()),
  verdict: VerdictSchema,
  confidence: z.number(),
  reason_codes: z.array(z.string()),
  recommended_action: z.string(),
  degraded_flags: z.array(z.string()),
  signal_view: z.object({
    channel: z.enum(["telegram", "whatsapp", "email", "api"]),
    member_name: z.string(),
    text: z.string(),
    received_at: z.string(),
  }),
  triage: z.object({
    signal_class: SignalClassSchema,
    confidence: z.number(),
    payment_intent: z.boolean(),
    urgency_signals: z.array(z.string()),
    reason_code: z.string(),
    band_source: z.enum(["model", "rules"]),
    rule_class: SignalClassSchema,
  }),
  findings: z.array(VerificationFindingSchema),
  graph: GraphFindingSchema,
  trace: z.object({ total_ms: z.number(), spans: z.array(TraceSpanSchema) }),
  cost: z.object({ total_usd: z.number(), entries: z.array(CostEntrySchema) }),
  engagement: z
    .object({
      outcome: z.enum(["CONFIRMED_SCAM", "BENIGN", "INCONCLUSIVE", "NO_RESPONSE"]),
      stop_reason: z.string(),
      turns: z.array(EngagementTurnSchema),
    })
    .nullable(),
  integrity: z.object({ sha256: z.string(), chain_prev: z.string().nullable() }),
});
export type EvidenceBundle = z.infer<typeof EvidenceBundleSchema>;

export const CaseSummarySchema = z.object({
  case_id: z.string(),
  state: CaseStateSchema,
  verdict: VerdictSchema.nullable(),
  confidence: z.number().nullable(),
  why_line: z.string(),
  member_name: z.string(),
  received_at: z.string(),
  degraded_flags: z.array(z.string()),
  recommended_action: z.string().nullable(),
});
export type CaseSummary = z.infer<typeof CaseSummarySchema>;

export const CasePageSchema = z.object({
  cases: z.array(CaseSummarySchema),
  next_cursor: z.string().nullable(),
});
export type CasePage = z.infer<typeof CasePageSchema>;

export const DecisionResponseSchema = z.object({
  case_id: z.string(),
  state: CaseStateSchema,
  graph_commit: z.string(),
});
export type DecisionResponse = z.infer<typeof DecisionResponseSchema>;

export const HouseholdMemberSchema = z.object({
  member_id: z.string(),
  display_name: z.string(),
  role: z.enum(["guardian", "member"]),
  bindings: z.array(z.object({ channel: z.string(), status: z.enum(["bound", "pending", "revoked"]) })),
  engagement_consent: z.boolean(),
  warning_count_30d: z.number(),
  last_signal_at: z.string().nullable(),
});
export type HouseholdMember = z.infer<typeof HouseholdMemberSchema>;

export const InviteSchema = z.object({
  invite_id: z.string(),
  code: z.string(),
  household_id: z.string(),
  status: z.enum(["minted", "bound", "expired"]),
  created_at: z.string(),
});

export const HouseholdSchema = z.object({
  household_id: z.string(),
  name: z.string(),
  members: z.array(HouseholdMemberSchema),
  invites: z.array(InviteSchema),
  settings: z.object({
    quiet_hours: z.object({ start: z.string(), end: z.string(), timezone: z.string() }),
    engagement_enabled: z.boolean(),
    language: z.enum(["en", "hi"]),
    thresholds: z.object({
      escalation_floor: z.number(),
      gray_band_low: z.number(),
      gray_band_high: z.number(),
    }),
  }),
  consent_ledger: z.array(
    z.object({ at: z.string(), subject: z.string(), grant: z.string(), revoked_at: z.string().nullable() })
  ),
});
export type Household = z.infer<typeof HouseholdSchema>;

export const AuditEntrySchema = z.object({
  seq: z.number(),
  at: z.string(),
  actor: z.string(),
  event_type: z.string(),
  case_id: z.string().nullable(),
  summary: z.string(),
  hash: z.string(),
  prev_hash: z.string().nullable(),
});
export type AuditEntry = z.infer<typeof AuditEntrySchema>;

export const SpendRollupSchema = z.object({
  window: z.string(),
  total_usd: z.number(),
  per_stage: z.array(z.object({ stage: z.string(), calls: z.number(), usd: z.number() })),
});
export type SpendRollup = z.infer<typeof SpendRollupSchema>;

export const MetricsSnapshotSchema = z.object({
  screened_7d: z.number(),
  silent_7d: z.number(),
  escalations_open: z.number(),
  latency_p50_ms: z.number(),
  latency_p95_ms: z.number(),
  spend_mean_usd: z.number(),
  spend_7d_usd: z.number(),
  precision: z.number(),
  precision_ci: z.tuple([z.number(), z.number()]),
  false_gate_rate: z.number(),
  false_gate_ci: z.tuple([z.number(), z.number()]),
  verdict_mix_7d: z.array(z.object({ verdict: VerdictSchema, count: z.number() })),
  trend_7d: z.array(z.object({ day: z.string(), cases: z.number(), escalations: z.number() })),
});
export type MetricsSnapshot = z.infer<typeof MetricsSnapshotSchema>;
