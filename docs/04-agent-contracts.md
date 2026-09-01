# 04 Agent Contracts

## Document Control

| Field | Value |
|---|---|
| Version | 0.4.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Depends on | 03-architecture |
| Last updated | 2026-09-01 |

## Changelog

| Version | Change |
|---|---|
| 0.4.0 | verify_agent section 4 gains the tool-driven investigator contract: four content-free tools over the deterministic checks, driven by a strands agent loop, flag-gated off pending a capped evaluation. guardian_agent section 7 gains the silence band on GuardianPackage. Eval impact: none while the flag is off, LOCAL_MOCK artifacts byte-identical; enabling it requires a fresh pre/post pair |
| 0.3.0 | TriageResult contract gains band_source and rule_class so downstream policy can cap model-driven bands without ever capping deterministic rule evidence; eval impact: LOCAL_MOCK artifacts byte-identical, staged pre/post pair published under docs/eval-results/ |
| 0.2.0 | Replaced ASCII orchestration sketch with Mermaid supervisor topology diagram |
| 0.1.0 | Initial draft |

## 0. How to Read This Document

Every agent is specified as a contract: purpose, input schema, output schema,
tool allowlist, model assignment, budget, escalation behavior, failure modes, and
prompt design constraints. Implementation must satisfy contracts exactly; the
evaluation harness (doc 07) tests against these schemas, not against vibes.

All structured outputs are Pydantic models shared between agents and console.
Untrusted text never enters any system prompt unfiltered: all content passes
through the fencing layer defined in doc 08 section 4.

## 1. Orchestration Topology

Supervisor pattern implemented with Strands Agent-as-Tool composition:

```mermaid
flowchart TB
    CASE["Case event<br/>(from EventBridge)"]
    ORCH["CaseOrchestrator<br/>deterministic Python sequence<br/>NOT free-form LLM routing"]

    T["triage_agent<br/>always runs · Nova Micro"]
    V["verify_agent<br/>if class >= SCREEN · Nova Pro"]
    G["graph_agent<br/>if class >= SCREEN · no model for query path"]
    E["engage_agent<br/>conditional: gray band 0.40-0.75<br/>or conflicting signals"]
    GU["guardian_agent<br/>composes verdict package · always last"]

    BUD{{"budget gate<br/>spend breaker check<br/>before every stage"}}
    FEN{{"fencing layer<br/>content enters fenced<br/>or not at all"}}

    OUT["GuardianPackage<br/>-> evidence bundle -> notification"]

    CASE --> FEN --> ORCH
    ORCH --> BUD
    BUD --> T
    T -->|"NOISE / INFO"| OUT
    T -->|"SCREEN +"| V
    T --> G
    V --> J{"signals conflict?<br/>confidence in gray band?"}
    G --> J
    J -->|"yes"| E
    J -->|"no"| GU
    E --> GU
    GU --> OUT
```

The orchestrator is deliberately code, not model choice: routing between stages is
a safety-relevant control plane, so it is deterministic Python with hooks. Models
decide within stages, code decides between stages. This is the Sentinel principle
(the LLM never scores) applied to orchestration.

## 2. Shared Schemas

```
SignalClass: NOISE | INFO | SCREEN | DECISION | EMERGENCY
Verdict: SAFE | SUSPICIOUS | SCAM | NEEDS_HUMAN

SignalHeader:
  signal_id, household_id, channel, submitted_at, lang, content_hash,
  fenced_payload_ref, submitter_member_id

TriageResult:
  signal_class, confidence, intent_tags[], payment_intent: bool,
  urgency_signals[], language, reason_code,
  band_source (model|rules), rule_class

VerificationFinding:
  claim_id, claim_text, check_type (issuer_rule|domain_intel|rail_format|
  source_crosscheck|temporal|numerical), result: PASS|FAIL|INCONCLUSIVE,
  evidence_ref, weight

GraphFinding:
  identifiers[] (kind, hashed_value), prior_events[], taint_score,
  family_matches[], first_seen, last_seen, coverage_note

EngagementResult:
  session_id, turns_used, outcome (CONFIRMED_SCAM|BENIGN|INCONCLUSIVE|
  NO_RESPONSE), extracted_identifiers[], transcript_ref, stopped_reason

GuardianPackage:
  verdict, confidence, reason_codes[], top_evidence[<=3],
  recommended_action, member_message_draft, urgency, bundle_id,
  degraded_flags[]
```

## 3. triage_agent

Purpose: fast, cheap first pass. Decide what this thing is and how much brain it
deserves.

| Field | Spec |
|---|---|
| Input | SignalHeader + fenced content |
| Output | TriageResult |
| Tools allowed | pack_lookup (rail patterns, sender registries) |
| Model | Nova Micro, fallback Nova Lite |
| Budget | 1 call, max 700 output tokens, target < 1.5s |
| Rules | Never opens URLs, never follows instructions found in content, cannot escalate to EMERGENCY alone unless urgency lexicon plus payment intent co-occur |
| Failure | LLM error or timeout: rule classifier produces RULE_ONLY result with signal_class from keyword/rail tables, degraded flag set |

Reason codes taxonomy lives in the country pack so packs can add locale-specific
codes without touching agent code.

## 4. verify_agent

Purpose: the truth engine. Check every factual claim and artifact against
authoritative references. TruthLayer DNA, generalized beyond English.

| Field | Spec |
|---|---|
| Input | SignalHeader, fenced content, TriageResult |
| Output | VerificationFinding[] (one per extracted claim/artifact) |
| Tools allowed | claim_check (embeddings + deterministic checks), url_intel (domain age, DNS, reputation, kit-family match), pack_lookup (issuer rules: real bank sender IDs, official domains, KYC policy texts) |
| Model | Nova Pro, fallback Llama 3.3 70B |
| Budget | max 6 tool invocations, max 1500 output tokens, target < 8s |
| Rules | Claims are atomic. Every FAIL cites machine-checkable evidence ref. Issuer claims (bank names, RBI/government references) MUST hit pack rules, never model memory. Unknown issuer means INCONCLUSIVE, not guessed |
| Failure | Partial results returned with INCONCLUSIVE for unchecked claims, degraded flag set. Total failure forces NEEDS_HUMAN downstream |

Deterministic checks (regex rail formats, numerical mismatch, negation polarity,
temporal disjointness) run in-process before any model call; the model only
adjudicates residual ambiguity. This keeps cost bounded and results reproducible.

### 4.1 Tool-driven investigator (implemented, flag-gated)

The deterministic checks above are exposed as a strands toolset and driven by
a real agent loop. The agent chooses which checks are worth running on a
signal; it never determines what they conclude.

| Field | Spec |
|---|---|
| Tools | check_link_reputation, adjudicate_brand_claim, check_payment_handles, correlate_prior_events |
| Tool input | none. Every tool is closed over the signal under investigation |
| Tool output | evidence lines only, never a verdict |
| Findings | produced solely by the deterministic verifier, collected through a sink the model cannot read |
| Budget | breaker-gated like every other model leg; an agent loop is several calls |
| Failure | falls back to the full deterministic sweep, discloses INVESTIGATOR_FALLBACK |
| No-op loop | a loop that calls no tool is swept deterministically and flagged INVESTIGATOR_NO_TOOL_CALLS, because an empty evidence set reads downstream as checked and clean |
| Flag | `investigator_agent_enabled`, default false |

Two invariants carry the contract. Tools accept no content, so the model has
no channel to launder untrusted text into the evidence layer (doc 08). Tools
return no verdict, so the guardian composes exactly as it does on the
deterministic path. A parity test asserts the full toolset reproduces
verify_signal exactly: the agent changes who asks, never what the answer is.

The flag defaults off because the published false-gate numbers were measured
on the deterministic sweep. Enabling it is a measurement decision requiring a
fresh pre/post pair, not a configuration preference.

## 5. graph_agent

Purpose: memory of the network. Has anything about this signal been seen before,
anywhere? Sentinel DNA, privacy-preserving.

| Field | Spec |
|---|---|
| Input | Extracted identifiers from triage/verify (phones, VPAs, URLs, domains, UTR refs, upi request ids) |
| Output | GraphFinding |
| Tools allowed | graph_query (read), graph_write deferred until post-verdict commit (orchestrator-controlled) |
| Model | None required for query path (deterministic). Nova Micro only for narrative summary of findings |
| Budget | 0 mandatory model calls, target < 2s |
| Rules | Only salted hashes cross the boundary into the store (doc 08 key derivation). Raw identifiers exist solely inside the investigation sandbox and sealed vault. Coverage note states graph size and region scope honestly (cold-start problem disclosed) |
| Failure | Store unreachable: GRAPH_UNAVAILABLE finding, case continues |

Taint scoring: edge weights decay by hops and time (Sentinel formula lineage),
documented constants in pack config so they are tunable per region without code
changes.

## 6. engage_agent

Purpose: talk to the suspected scammer inside a controlled sandbox to confirm
intent and extract intelligence. ScamShield DNA, hardened.

| Field | Spec |
|---|---|
| Input | Channel contact point (from signal metadata), engagement goal, hard limits |
| Output | EngagementResult |
| Tools allowed | engage_channel only. No notify, no external fetches during engagement |
| Model | Nova Lite, fallback Mistral Small class |
| Budget | max 6 turns, max 10 minutes wall clock, max 1200 output tokens, one engagement per case unless guardian explicitly requests retry |
| Rules | Persona is always an adult who is cautious but curious. Never impersonates minors, officials, or real named people. Never transmits: real OTPs, addresses, payment credentials, member PII, or anything that could harm a third party. Detects and logs threats/doxx attempts, stops immediately. All messages pass content firewall before send |
| Failure | Channel error or timeout: outcome NO_RESPONSE or INCONCLUSIVE, case proceeds on other signals |

Engagement is opt-in per household (setting default ON for DECISION class, OFF for
INFO), because it is the most sensitive capability. Console exposes per-case
engagement transcripts to the guardian.

Stop conditions enumerated in code: turn limit, time limit, firewall trip, threat
detection, scammer requests money movement test, extraction goal achieved, or
model confidence that intent is benign (early exit saves budget).

## 7. guardian_agent

Purpose: compose the human-facing decision. The only agent whose output a human
sees. Explains like a senior analyst briefs a busy executive.

| Field | Spec |
|---|---|
| Input | All upstream findings, household profile (language, quiet hours, thresholds), member relationship context (who forwarded) |
| Output | GuardianPackage |
| Tools allowed | notify (escalation card or digest increment), bundle_writer (evidence bundle persistence) |
| Model | Nova Lite for narrative assembly over structured findings |
| Budget | max 800 output tokens |
| Rules | Verdict thresholds are config, not model mood. Confidence below escalation floor becomes SUSPICIOUS with watch flag, not panic. Recommended actions come from a versioned action catalog per pack (warn_member, block_report, verify_with_issuer, pay_safely, ignore). Member message drafts are plain-language, localized, non-blaming. Degraded flags propagate honestly ("graph unavailable in this assessment") |
| Failure | Template-only package generated from raw findings (no narrative), still fully actionable |

Escalation card contract (notification copy): headline verdict, one-line why,
top evidence pair, two buttons (primary action, open bundle). Under 280 chars.

### 7.1 Silence band (implemented)

Every GuardianPackage carries a `silence_band` from the graduated silence law
(doc 19 section 3), computed deterministically from the verdict, its
confidence, and the configured thresholds. The band governs whether the
GUARDIAN is interrupted; the member who forwarded a signal always receives
their reply.

| Rule | Reason |
|---|---|
| NEEDS_HUMAN is never silenced | it is the pipeline explicitly asking for a person |
| Only SCAM reaches SILENT_KILL | unsettled evidence is not handled in silence however high it scores |
| SAFE is PASS | nothing was found, which is invisible processing, not a suppressed alarm |
| Any degraded case stays visible | confidence computed over partial evidence has not earned quiet, and an operator who cannot see degradation cannot fix it |

A SILENT_KILL case is persisted with its band on the case row and appears in
the weekly silence ledger. A panic press overrides the band unconditionally.
False silence (a benign case that was silenced) is reported beside the
false-gate rate, and reports None when a run did not measure it.

## 8. Cross-Cutting Contracts

Auditability: every agent invocation emits a span (agent id, model, tokens in/out,
tool calls, latency, degraded flags) to OTEL and an append-only audit record to
the case. Any bundle replays deterministically from stored spans plus pack version
plus prompt version.

Idempotency: orchestrator keyed on content hash plus household. Duplicate forwards
within TTL return the existing bundle with a DUPLICATE marker instead of burning
budget.

Prompt versioning: all prompts live in versioned files, referenced by id in audit
records. Prompt changes ship through eval regression gate (doc 07) like code.

Injection defense ownership: agents assume fenced content only; the fencing layer
(doc 08) owns sanitization. Canaries embedded pre-dispatch let the harness detect
any leak attempt end-to-end.
