/**
 * Deterministic mock dataset standing in for the doc 14 API until the
 * gateway integration lands. Seeded and fixed-timestamp so renders are
 * hydration-stable and the demo is identical every run. The five opening
 * cases are the family's real first forwards from the 2026-08-27 soak,
 * verdicts exactly as the live system returned them.
 */
import type {
  AuditEntry,
  CaseSummary,
  EvidenceBundle,
  Health,
  Household,
  MetricsSnapshot,
  SpendRollup,
} from "./schemas";

export const MOCK_NOW = "2026-08-27T09:14:00+05:30";

const hash = (label: string, n: number) =>
  `${label}${(0x9e3779b9 * n >>> 0).toString(16).padStart(8, "0")}${(0x85ebca6b * (n + 7) >>> 0)
    .toString(16)
    .padStart(8, "0")}`.slice(0, 24);

const ago = (minutes: number) => {
  const base = new Date(MOCK_NOW).getTime();
  return new Date(base - minutes * 60_000).toISOString();
};

interface FlatSeed {
  case_id: string;
  verdict: EvidenceBundle["verdict"];
  confidence: number;
  reason_codes: string[];
  recommended_action: string;
  degraded_flags: string[];
  member_name: string;
  received_at: string;
  text: string;
  triage_class: EvidenceBundle["triage"]["signal_class"];
  triage_confidence: number;
  payment_intent: boolean;
  urgency: string[];
  reason_code: string;
  rule_class: EvidenceBundle["triage"]["rule_class"];
  findings: EvidenceBundle["findings"];
  graph: EvidenceBundle["graph"];
  engagement: EvidenceBundle["engagement"];
  total_ms: number;
  why_line: string;
}

type CaseBundleSeed = FlatSeed & { n: number };

const bundleFor = (c: CaseBundleSeed): EvidenceBundle => ({
  bundle_id: hash("bnd", c.n),
  case_id: c.case_id,
  household_id: "shukla-home",
  created_at: c.received_at,
  pack_version: "0.2.0",
  prompt_versions: { triage: "triage-v7", guardian: "guardian-v4" },
  verdict: c.verdict,
  confidence: c.confidence,
  reason_codes: c.reason_codes,
  recommended_action: c.recommended_action,
  degraded_flags: c.degraded_flags,
  signal_view: {
    channel: "telegram",
    member_name: c.member_name,
    text: c.text,
    received_at: c.received_at,
  },
  triage: {
    signal_class: c.triage_class,
    confidence: c.triage_confidence,
    payment_intent: c.payment_intent,
    urgency_signals: c.urgency,
    reason_code: c.reason_code,
    band_source: "model",
    rule_class: c.rule_class,
  },
  findings: c.findings,
  graph: c.graph,
  trace: {
    total_ms: c.total_ms,
    spans: [
      { stage: "fence", status: "ok", ms: Math.round(c.total_ms * 0.04) },
      { stage: "triage", status: "ok", ms: Math.round(c.total_ms * 0.52) },
      { stage: "verify", status: c.degraded_flags.length ? "degraded" : "ok", ms: Math.round(c.total_ms * 0.24) },
      { stage: "graph", status: "ok", ms: Math.round(c.total_ms * 0.12) },
      { stage: "guardian", status: "ok", ms: Math.round(c.total_ms * 0.08) },
    ],
  },
  cost: {
    total_usd: Number((c.total_ms / 1_000_000).toFixed(6)),
    entries: [
      {
        stage: "triage",
        model_id: "apac.amazon.nova-micro-v1:0",
        input_tokens: 384,
        output_tokens: 24,
        usd: Number(((c.total_ms / 1_000_000) * 0.93).toFixed(6)),
      },
    ],
  },
  engagement: c.engagement ?? null,
  integrity: { sha256: hash("sha", c.n * 3), chain_prev: c.n === 1 ? null : hash("sha", (c.n - 1) * 3) },
});

const mk = (n: number, over: Partial<FlatSeed> & Pick<FlatSeed, "case_id" | "verdict" | "member_name" | "received_at" | "text" | "why_line">): CaseBundleSeed => ({
  n,
  confidence: over.confidence ?? 0.8,
  reason_codes: over.reason_codes ?? [],
  recommended_action: over.recommended_action ?? "review_bundle",
  degraded_flags: over.degraded_flags ?? [],
  triage_class: over.triage_class ?? "SCREEN",
  triage_confidence: over.triage_confidence ?? over.confidence ?? 0.8,
  payment_intent: over.payment_intent ?? false,
  urgency: over.urgency ?? [],
  reason_code: over.reason_code ?? "model:review",
  rule_class: over.rule_class ?? "INFO",
  findings: over.findings ?? [],
  graph: over.graph ?? { identifiers: [], prior_events: 0, max_taint: 0, unavailable: false },
  engagement: over.engagement ?? null,
  total_ms: over.total_ms ?? 900,
  ...over,
});

const FIND_DOMAIN_PASS = {
  subject: "www.bluedart.com",
  check_type: "domain_intel" as const,
  result: "PASS" as const,
  evidence_ref: "trusted_domain:bluedart.com",
  weight: 0.85,
};
const FIND_ISSUER_PASS = (name: string, dom: string) => ({
  subject: name,
  check_type: "issuer_rule" as const,
  result: "PASS" as const,
  evidence_ref: `claims ${name} and links resolve inside ${dom}`,
  weight: 0.9,
});
const FIND_ISSUER_FAIL = (name: string, dom: string) => ({
  subject: name,
  check_type: "issuer_rule" as const,
  result: "FAIL" as const,
  evidence_ref: `claims ${name} but links point outside ${dom} official domains`,
  weight: 0.5,
});
const FIND_DOMAIN_INCONC = (host: string) => ({
  subject: host,
  check_type: "domain_intel" as const,
  result: "INCONCLUSIVE" as const,
  evidence_ref: "not_in_issuer_registry; age_intel_pends_p3",
  weight: 0.2,
});

const seeds: CaseBundleSeed[] = [
  mk(1, {
    case_id: "c_01J9KQ7Z2M",
    verdict: "SCAM",
    confidence: 0.91,
    why_line: "Kotak claimed but link sits on spoof domain kotak.bank.in",
    member_name: "Papa",
    received_at: ago(9),
    text:
      "Sent Rs.7.00 from Kotak Bank A/c X3047 to Nagpur Metro NMRC Ti on 26-08-26. UPI Ref 004421693139. Not done by you? Tap https://kotak.bank.in/KBANKT/Fraud",
    reason_codes: ["HARD_FAIL_ISSUER_RULE", "PAYMENT_INTENT"],
    recommended_action: "warn_member",
    triage_class: "DECISION",
    triage_confidence: 0.87,
    payment_intent: true,
    urgency: ["urgent", "immediately"],
    reason_code: "model:credential_phish",
    rule_class: "SCREEN",
    findings: [
      FIND_ISSUER_FAIL("Kotak", "kotak.com"),
      FIND_DOMAIN_INCONC("kotak.bank.in"),
    ],
    graph: {
      identifiers: [
        { kind: "VPA", hashed_value: hash("vpa", 4) },
        { kind: "UTR_REF", hashed_value: hash("utr", 5) },
      ],
      prior_events: 2,
      max_taint: 0.62,
      unavailable: false,
    },
    total_ms: 1240,
  }),
  mk(2, {
    case_id: "c_01J9KQ8XM4",
    verdict: "SUSPICIOUS",
    confidence: 0.62,
    why_line: "Bank fraud alert shape; link on official surface, VPA handle present",
    member_name: "Papa",
    received_at: ago(9),
    text:
      "Sent Rs.349.00 from Kotak Bank AC X3047 to navircbpmobilerec.cf@axisbank on 18-05-26.UPI Ref 650470270016. Not you, https://kotak.com/KBANKT/Fraud",
    reason_codes: ["TRIAGE_DECISION", "PAYMENT_INTENT"],
    recommended_action: "review_bundle",
    triage_class: "DECISION",
    triage_confidence: 0.78,
    payment_intent: true,
    reason_code: "model:fraud_alert_ambiguity",
    rule_class: "SCREEN",
    findings: [FIND_ISSUER_PASS("Kotak", "kotak.com"), FIND_DOMAIN_PASS],
    graph: {
      identifiers: [{ kind: "VPA", hashed_value: hash("vpa", 9) }],
      prior_events: 0,
      max_taint: 0,
      unavailable: false,
    },
    total_ms: 1010,
  }),
  mk(3, {
    case_id: "c_01J9KQ9TP8",
    verdict: "SUSPICIOUS",
    confidence: 0.58,
    why_line: "Loan-bait with unverifiable URL shortener; gated, not guessed",
    member_name: "Bhai",
    received_at: ago(14),
    text:
      "CIBIL Verified! INR 44000 Loan Approved on 8/26/2026 Finish KYC for transfer. Apply here: http://1kx.in/2PRsU0\n\nCred Sathi",
    reason_codes: ["TRIAGE_SCREEN", "DOMAIN_UNVERIFIED"],
    recommended_action: "review_bundle",
    triage_class: "SCREEN",
    triage_confidence: 0.61,
    reason_code: "model:loan_bait",
    rule_class: "SCREEN",
    findings: [FIND_DOMAIN_INCONC("1kx.in")],
    graph: { identifiers: [], prior_events: 0, max_taint: 0, unavailable: false },
    total_ms: 860,
  }),
  mk(4, {
    case_id: "c_01J9KQAA1N",
    verdict: "SUSPICIOUS",
    confidence: 0.6,
    why_line: "Digital-arrest script in Hindi; authority impersonation signals",
    member_name: "Maa",
    received_at: ago(48),
    text:
      "यह मुंबई पुलिस साइबर सेल है। आपके आधार से जुड़ा पासपोर्ट जब्त हुआ है। तुरंत video call पर जुड़ें और account verification कराएं, वरना कल सुबह गिरफ्तारी होगी।",
    reason_codes: ["TRIAGE_DECISION"],
    recommended_action: "review_bundle",
    triage_class: "DECISION",
    triage_confidence: 0.83,
    urgency: ["तुरंत", "कल"],
    reason_code: "model:authority_impersonation",
    rule_class: "INFO",
    findings: [],
    graph: { identifiers: [], prior_events: 0, max_taint: 0, unavailable: false },
    total_ms: 940,
  }),
  mk(5, {
    case_id: "c_01J9KQBK7D",
    verdict: "SUSPICIOUS",
    confidence: 0.55,
    why_line: "UPI collect coercion; PIN-to-receive confusion shape",
    member_name: "Bhai",
    received_at: ago(71),
    text:
      "You have 1 pending collect request of Rs 4,999 from 'FASTag Recharge'. To RECEIVE money enter your UPI PIN. Scan to receive refund of failed transaction.",
    reason_codes: ["TRIAGE_SCREEN", "PAYMENT_INTENT"],
    recommended_action: "review_bundle",
    triage_class: "SCREEN",
    triage_confidence: 0.52,
    payment_intent: true,
    reason_code: "model:upi_collect_abuse",
    rule_class: "SCREEN",
    findings: [],
    graph: { identifiers: [], prior_events: 0, max_taint: 0, unavailable: false },
    total_ms: 780,
  }),
  mk(6, {
    case_id: "c_01J9KQCV2R",
    verdict: "NEEDS_HUMAN",
    confidence: 0.5,
    why_line: "Verification dependency unreachable; honest incomplete verdict",
    member_name: "Papa",
    received_at: ago(95),
    text: "Your KYC has expired, update now at http://sbi-kyc-update-in.top before account freeze",
    reason_codes: ["VERIFY_UNAVAILABLE"],
    degraded_flags: ["VERIFY_UNAVAILABLE"],
    recommended_action: "review_bundle",
    triage_class: "DECISION",
    triage_confidence: 0.74,
    reason_code: "model:kyc_phish",
    rule_class: "SCREEN",
    findings: [FIND_DOMAIN_INCONC("sbi-kyc-update-in.top")],
    graph: { identifiers: [], prior_events: 0, max_taint: 0, unavailable: true },
    total_ms: 1520,
  }),
  mk(7, {
    case_id: "c_01J9KQD9FS",
    verdict: "SUSPICIOUS",
    confidence: 0.57,
    why_line: "Relative-impersonation ask fused with urgency; number handed over",
    member_name: "Maa",
    received_at: ago(120),
    text: "Papa meri phone kharab ho gayi, mujhe 5000 urgent upi kar do is number pe 9876501234",
    reason_codes: ["TRIAGE_DECISION"],
    recommended_action: "review_bundle",
    triage_class: "DECISION",
    triage_confidence: 0.71,
    payment_intent: true,
    reason_code: "model:relative_impersonation",
    rule_class: "INFO",
    findings: [],
    graph: {
      identifiers: [{ kind: "PHONE", hashed_value: hash("ph", 11) }],
      prior_events: 1,
      max_taint: 0.4,
      unavailable: false,
    },
    total_ms: 700,
  }),
  mk(8, {
    case_id: "c_01J9KQEPW1",
    verdict: "SCAM",
    confidence: 0.88,
    why_line: "Advance-fee lottery; fee demand before any prize",
    member_name: "Maa",
    received_at: ago(190),
    text: "Congratulations! Your number won the KBC lucky draw of Rs 25,00,000. Send 5000 processing fee to claim your prize.",
    reason_codes: ["HARD_FAIL_LEXICON_RULE"],
    recommended_action: "warn_member",
    triage_class: "DECISION",
    triage_confidence: 0.9,
    payment_intent: true,
    reason_code: "model:advance_fee",
    rule_class: "DECISION",
    findings: [],
    graph: { identifiers: [], prior_events: 0, max_taint: 0, unavailable: false },
    engagement: {
      outcome: "CONFIRMED_SCAM",
      stop_reason: "turn_budget",
      turns: [
        { role: "engage_agent", text: "Prize reference के लिए caller id या official SMS स्क्रीनशॉट भेजिए?", offset_s: 0 },
        { role: "suspect", text: "Sir fee pehle, agent baad me. 30 min me prize transfer.", offset_s: 46 },
        { role: "engage_agent", text: "RBI ke anusaar prize ke liye fee nahi li jaati. Reference number?", offset_s: 74 },
        { role: "suspect", text: "Do not message this number again.", offset_s: 121 },
      ],
    },
    total_ms: 1680,
  }),
  mk(9, {
    case_id: "c_01J9KQF4HT",
    verdict: "SAFE",
    confidence: 0.85,
    why_line: "Official courier link verified; COD note has no collectable handle",
    member_name: "Papa",
    received_at: ago(260),
    text:
      "BlueDart: parcel arriving today. Pay Rs 2500 cash on delivery. Track at https://www.bluedart.com/track",
    reason_codes: ["ISSUER_VERIFIED"],
    recommended_action: "none",
    triage_class: "DECISION",
    triage_confidence: 0.9,
    payment_intent: true,
    reason_code: "model:delivery_cod",
    rule_class: "INFO",
    findings: [FIND_DOMAIN_PASS, FIND_ISSUER_PASS("BlueDart", "bluedart.com")],
    graph: { identifiers: [], prior_events: 0, max_taint: 0, unavailable: false },
    total_ms: 1090,
  }),
  mk(10, {
    case_id: "c_01J9KQGKR6",
    verdict: "SAFE",
    confidence: 0.78,
    why_line: "Member's own OTP forward; no action channel present",
    member_name: "Maa",
    received_at: ago(300),
    text: "SBI: your OTP is 449210. Do not share with anyone.",
    reason_codes: ["NO_ACTION_CHANNEL"],
    recommended_action: "none",
    triage_class: "DECISION",
    triage_confidence: 0.92,
    reason_code: "model:otp_panic",
    rule_class: "INFO",
    findings: [],
    graph: { identifiers: [], prior_events: 0, max_taint: 0, unavailable: false },
    total_ms: 640,
  }),
  mk(11, {
    case_id: "c_01J9KQH2LD",
    verdict: "SAFE",
    confidence: 0.9,
    why_line: "Plain family chatter",
    member_name: "Bhai",
    received_at: ago(420),
    text: "Hi",
    reason_codes: ["NO_RISK_SIGNALS"],
    recommended_action: "none",
    triage_class: "NOISE",
    triage_confidence: 0.1,
    reason_code: "model:noise",
    rule_class: "NOISE",
    findings: [],
    graph: { identifiers: [], prior_events: 0, max_taint: 0, unavailable: false },
    total_ms: 520,
  }),
  mk(12, {
    case_id: "c_01J9KQJ8NV",
    verdict: "SAFE",
    confidence: 0.88,
    why_line: "Plain family request; no fraud shape",
    member_name: "Papa",
    received_at: ago(430),
    text: "Please pay 1000rs",
    reason_codes: ["NO_RISK_SIGNALS"],
    recommended_action: "none",
    triage_class: "INFO",
    triage_confidence: 0.15,
    payment_intent: true,
    reason_code: "model:benign_request",
    rule_class: "INFO",
    findings: [],
    graph: { identifiers: [], prior_events: 0, max_taint: 0, unavailable: false },
    total_ms: 560,
  }),
  mk(13, {
    case_id: "c_01J9KQKQ3X",
    verdict: "SAFE",
    confidence: 0.8,
    why_line: "Government portal link on trusted tier",
    member_name: "Bhai",
    received_at: ago(600),
    text: "Income Tax refund of Rs 2,340 processed. Track status on https://www.incometax.gov.in after login.",
    reason_codes: ["ISSUER_VERIFIED"],
    recommended_action: "none",
    triage_class: "SCREEN",
    triage_confidence: 0.55,
    reason_code: "model:govt_notice",
    rule_class: "INFO",
    findings: [FIND_DOMAIN_PASS, FIND_ISSUER_PASS("Income Tax Department", "incometax.gov.in")],
    graph: { identifiers: [], prior_events: 0, max_taint: 0, unavailable: false },
    total_ms: 830,
  }),
  mk(14, {
    case_id: "c_01J9KQM9ZB",
    verdict: "SAFE",
    confidence: 0.75,
    why_line: "Newsletter; no handles",
    member_name: "Maa",
    received_at: ago(700),
    text: "Zomato Gold: 40 percent off this weekend on select restaurants. Order now on the app.",
    reason_codes: ["NO_ACTION_CHANNEL"],
    recommended_action: "none",
    triage_class: "SCREEN",
    triage_confidence: 0.48,
    reason_code: "model:promo",
    rule_class: "INFO",
    findings: [],
    graph: { identifiers: [], prior_events: 0, max_taint: 0, unavailable: false },
    total_ms: 610,
  }),
];

export const MOCK_CASES: CaseSummary[] = seeds.map((s) => ({
  case_id: s.case_id,
  state: (s.verdict === "SAFE" ? "CLOSED_SILENT" : s.verdict === "NEEDS_HUMAN" ? "ESCALATED" : "ESCALATED") as CaseSummary["state"],
  verdict: s.verdict,
  confidence: s.confidence,
  why_line: s.why_line ?? "",
  member_name: s.member_name,
  received_at: s.received_at,
  degraded_flags: s.degraded_flags,
  recommended_action: s.recommended_action,
}));

export const MOCK_BUNDLES: Record<string, EvidenceBundle> = Object.fromEntries(
  seeds.map((s) => [s.case_id, bundleFor(s)])
);

export const MOCK_HEALTH: Health = {
  status: "ok",
  version: "1.4.2",
  degraded: [],
};

export const MOCK_METRICS: MetricsSnapshot = {
  screened_7d: 148,
  silent_7d: 131,
  escalations_open: MOCK_CASES.filter((c) => c.state === "ESCALATED").length,
  latency_p50_ms: 1180,
  latency_p95_ms: 2640,
  spend_mean_usd: 0.00026,
  spend_7d_usd: 0.0385,
  precision: 1.0,
  precision_ci: [0.9887, 1.0],
  false_gate_rate: 0.0,
  false_gate_ci: [0.0, 0.0253],
  verdict_mix_7d: [
    { verdict: "SAFE", count: 131 },
    { verdict: "SUSPICIOUS", count: 12 },
    { verdict: "SCAM", count: 4 },
    { verdict: "NEEDS_HUMAN", count: 1 },
  ],
  trend_7d: [
    { day: "Aug 21", cases: 12, escalations: 1 },
    { day: "Aug 22", cases: 15, escalations: 0 },
    { day: "Aug 23", cases: 11, escalations: 1 },
    { day: "Aug 24", cases: 19, escalations: 2 },
    { day: "Aug 25", cases: 24, escalations: 1 },
    { day: "Aug 26", cases: 31, escalations: 3 },
    { day: "Aug 27", cases: 36, escalations: 5 },
  ],
};

export const MOCK_HOUSEHOLD: Household = {
  household_id: "shukla-home",
  name: "Shukla Family",
  members: [
    {
      member_id: "m_01",
      display_name: "Prakhar (Guardian)",
      role: "guardian",
      bindings: [{ channel: "telegram", status: "bound" }],
      engagement_consent: true,
      warning_count_30d: 0,
      last_signal_at: ago(9),
    },
    {
      member_id: "m_02",
      display_name: "Papa",
      role: "member",
      bindings: [{ channel: "telegram", status: "bound" }],
      engagement_consent: false,
      warning_count_30d: 2,
      last_signal_at: ago(9),
    },
    {
      member_id: "m_03",
      display_name: "Maa",
      role: "member",
      bindings: [{ channel: "telegram", status: "bound" }],
      engagement_consent: true,
      warning_count_30d: 1,
      last_signal_at: ago(48),
    },
    {
      member_id: "m_04",
      display_name: "Bhai",
      role: "member",
      bindings: [{ channel: "telegram", status: "bound" }],
      engagement_consent: true,
      warning_count_30d: 0,
      last_signal_at: ago(14),
    },
  ],
  invites: [
    { invite_id: "inv_1", code: "BYZE42", household_id: "shukla-home", status: "bound", created_at: ago(1500) },
    { invite_id: "inv_2", code: "XMYNW9", household_id: "shukla-home", status: "bound", created_at: ago(1500) },
    { invite_id: "inv_3", code: "DWPMT8", household_id: "shukla-home", status: "bound", created_at: ago(1500) },
  ],
  settings: {
    quiet_hours: { start: "22:00", end: "07:00", timezone: "Asia/Kolkata" },
    engagement_enabled: true,
    language: "en",
    thresholds: { escalation_floor: 0.7, gray_band_low: 0.4, gray_band_high: 0.75 },
  },
  consent_ledger: [
    { at: ago(1500), subject: "Papa", grant: "telegram binding", revoked_at: null },
    { at: ago(1490), subject: "Maa", grant: "telegram binding, engagement consent", revoked_at: null },
    { at: ago(1480), subject: "Bhai", grant: "telegram binding, engagement consent", revoked_at: null },
  ],
};

export const MOCK_AUDIT: AuditEntry[] = seeds.flatMap((s, i) => {
  const base: AuditEntry[] = [
    {
      seq: (seeds.length - i) * 3 - 2,
      at: s.received_at,
      actor: "system",
      event_type: "case.received",
      case_id: s.case_id,
      summary: `signal received from ${s.member_name} via telegram`,
      hash: hash("aud", i * 10 + 1),
      prev_hash: i === 0 ? null : hash("aud", (i - 1) * 10 + 3),
    },
    {
      seq: (seeds.length - i) * 3 - 1,
      at: s.received_at,
      actor: "system",
      event_type: "verdict.composed",
      case_id: s.case_id,
      summary: `verdict ${s.verdict} at ${s.confidence} with ${s.reason_codes.join(", ") || "no codes"}`,
      hash: hash("aud", i * 10 + 2),
      prev_hash: hash("aud", i * 10 + 1),
    },
  ];
  if (s.verdict !== "SAFE") {
    base.push({
      seq: (seeds.length - i) * 3,
      at: s.received_at,
      actor: "guardian",
      event_type: "escalation.notified",
      case_id: s.case_id,
      summary: "guardian card delivered over telegram with evidence bundle",
      hash: hash("aud", i * 10 + 3),
      prev_hash: hash("aud", i * 10 + 2),
    });
  }
  return base;
});

export const MOCK_SPEND: SpendRollup = {
  window: "24h",
  total_usd: 0.0041,
  per_stage: [{ stage: "triage", calls: 14, usd: 0.0041 }],
};
