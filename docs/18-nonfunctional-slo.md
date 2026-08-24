# 18 Non-Functional Requirements, SLOs, and Capacity Model

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Depends on | 03, 05, 06, 08, 09, 15 |
| Last updated | 2026-08-24 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft: data classification, SLO table with error budgets, capacity math, concurrency decisions, tenancy isolation, DR posture |

An SLO without an error budget is a wish. Functional promises live in docs 02,
04, and 14; this document pins every "how well" claim to a measurable definition,
a number, and a consequence when the number breaks.

## 1. Data Classification (normative, fixes an undefined reference)

Earlier documents referred to "P1 data" informally. This table is now the single
source of truth; code constants in P1 must use these exact names.

| Class | Contents | Encryption | Who may read | Logs? | Retention |
|---|---|---|---|---|---|
| P0 PUBLIC | Pack rules, reason-code taxonomy, published metrics, marketing copy | none | everyone | n/a | indefinite |
| P1 PERSONAL_SENSITIVE | Raw forwarded content, extracted identifiers, vault items | KMS per household (vault), TLS transit | owning household guardian/member only via authorized surfaces; NEVER models directly except fenced working copies | never logged raw; scrubbing enforced by test | TTLs per doc 06 section 1 |
| P2 HOUSEHOLD_PRIVATE | Cases, verdicts, bundles, decisions, engagement transcripts | at-rest encryption, household-scoped keys in access layer | owning household; aggregate stats globally | correlation ids only | TTLs per doc 06 |
| P3 OPERATIONAL | Traces, spans, spend meters, audit chain hashes, infra config | standard AWS at-rest | builder + break-glass roles | this IS the log layer | 400 days |

Rules: downgrades are permanent (P1 redacted into working copy stays P1 in the
vault; the working copy is P2). Every storage location declares its highest
class in IaC tags; a test asserts no P1 fields appear in P3 sinks (CloudWatch,
traces) using seeded sentinel strings end to end.

## 2. Service Level Objectives

| # | Objective | SLI (measured how) | Target | Window | Error budget | Breach consequence |
|---|-----------|--------------------|--------|--------|--------------|--------------------|
| S1 | Screening latency | forward event time to card delivered at Telegram (event timestamps, CloudWatch) | p95 <= 30s, p50 <= 8s | rolling 7d | 5 percent of signals may exceed | freeze verdict-path prompt/pack releases until green 2 consecutive nights |
| S2 | Intake availability | webhook accepts returning 202 or documented duplicate | >= 99.5 percent | monthly | 3.6 hours downtime equivalent | page runbook R2, degradation banner |
| S3 | Notification dispatch | verdict written to notification accepted | p95 <= 5s | rolling 7d | 1 percent | inspect queue lag, scale notification lambda |
| S4 | Escalation usefulness | guardian agreement rate on escalations (soak ledger) | >= 60 percent | per soak week | soft: 2 consecutive weeks below triggers interaction-model redesign (PR/FAQ kill criterion) | stop feature work, recalibrate thresholds on dev split only |
| S5 | False gates | legitimate escalated as threatening (eval harness) | <= 5 percent | per release | release-blocking hard gate | block release, recalibrate, publish pre/post |
| S6 | Cost discipline | mean USD per investigation (spend meter) | <= 0.02 | weekly | soft: p95 > 0.03 for a week triggers engagement-default review | tighten caps, alarm owner |
| S7 | Silence guarantee | NOISE-classified signals producing notifications (digest assertion) | 0 | per digest cycle | zero tolerance | bug, fix before next release |

Single-builder honesty: alerting is async-first (digest email to owner), no
pager exists, so SLO breaches surface in the daily ops digest and the weekly
review, not at 3am. The system degrades automatically in the meantime by
design (doc 03 matrix), which is what makes async-only ops defensible.

## 3. Capacity Model (back-of-envelope, reproducible)

Assumptions v1 (revisit at 10k households): 1,000 households, 40 signals per
household-month average, 20 percent investigation rate, peak burst factor 50x
average load.

```
Average intake        : 40,000 signals/month ~= 0.015/sec
Designed burst        : 5 cases/sec sustained (doc 03 section 7)
Expected burst        : 0.75/sec  => 6.7x headroom over expectation
Investigations        : 8,000/month; worst concurrent ~5 AgentCore sessions
Storage growth        : bundles+findings ~15KB avg => ~600MB/year at v1 scale
Graph growth          : ~3 hashed identifier nodes per investigated case
                        => ~24k node rows/year (KB-scale each)
Model spend ceiling   : 8,000 x $0.02 = $160/month worst case, linear per household
Telegram constraint   : bot global cap 30 msg/sec; our egress is 3 orders below
DynamoDB              : on-demand; v1 load is single-digit WCU seconds; pennies
```

Scaling law: everything grows linearly with households except the graph (quadratic
worst case on co_occurrence edges, mitigated by top-K truncation per node, doc 06).
Recompute this section at every order-of-magnitude crossing; the formulas above
are the artifact, the numbers are instances.

## 4. Concurrency and Consistency Decisions (declared, not implied)

| Concern | Decision | Mechanism |
|---|---|---|
| Case writes | single-writer per case | only the orchestrator mutates a case during INVESTIGATING; humans mutate only in AWAITING_DECISION |
| Double-tap decisions | first-write-wins | conditional DynamoDB write on state=AWAITING_DECISION; loser receives 409 CASE_ALREADY_CLOSED (doc 14) |
| At-least-once delivery | exactly-once EFFECT | idempotency key (channel+hash+household) plus conditional puts; duplicates return prior result |
| Graph updates | post-verdict batch, retry-safe | one idempotent transaction keyed by case_id AFTER final verdict; failed cases leave zero residue |
| Ordering | logical, never wall-clock | record sequence numbers within partitions; cross-service clock comparison forbidden in logic |
| Read-your-writes | required on decision path | guardian's decision read-back uses consistent reads; dashboard queues tolerate eventual (15s poll, doc 10) |

## 5. Multi-Tenant Isolation

Tenant = household. Enforcement is layered because single-table DynamoDB cannot
enforce row security in IAM:

1. Every query is composed with the household prefix in the key (data-layer rule,
   type-enforced client wrapper, no raw-table access outside it).
2. Cross-tenant attempts fail as uniform 404 (no existence leak), asserted by the
   IDOR battery on every endpoint (doc 15).
3. Per-household intake throttles bound noisy neighbors (doc 05).
4. Spend breaker is GLOBAL by design (documented tradeoff): a runaway tenant can
   degrade everyone briefly; per-tenant budget exhaustion drops only that tenant
   to NEEDS_HUMAN passthrough first, global breaker is the last resort.

## 6. Backpressure and Overload

Intake Lambdas sit behind SQS buffers with bounded concurrency. Queue depth past
threshold flips triage to RULE_ONLY mode (fast, cheap, honest degraded flag),
never drops signals silently; sustained overload returns 429 with Retry-After at
the edge while queued work drains. DLQ depth alarms page the ops digest. Load
shedding order (documented preference): digests first, engagement second,
narrative prose third; verdict-critical path sheds LAST.

## 7. Disaster Recovery Posture

| Item | Policy |
|---|---|
| DynamoDB | point-in-time recovery enabled (35 days); nightly export to versioned S3 |
| Packs bucket | versioned, immutable artifacts, manifest pointer rollback (doc 09) |
| Secrets/config | SSM with documented values-as-IaC; rotation runbook |
| Region loss | rebuild-in-clean-region via bootstrap script; RTO 8 hours, RPO 24 hours; acceptable v1 tradeoff, revisited with revenue |
| Vault KMS | deletion is irreversible BY CONTRACT; deletion certificate flow (doc 06 section 5) is the user-facing promise |
| DR drills | restore-from-export rehearsal once before P7 exit, recorded in what-broke.md |

## 8. Progressive Delivery and Feature Flags

Flags (per-household setting or env): whatsapp_channel, engage_default_on,
regional_intel_share, voice_transcripts (future). Kill switches double as chaos
hooks (doc 15 fault injection uses the same switch layer). Default rollout:
staging soak >= 3 days, shadow replay clean (doc 15 L4), then 10 percent of
soak households, then GA. Flag removal is a scheduled cleanup, not an option:
stale flags are tech debt with a quarterly eviction ritual.

## 9. Acceptance Criteria for This Document

1. Every SLO row has an automatable SLI query or assertion listed in the eval/ops
   repos by P4 exit.
2. Classification names appear as code constants; the seeded-string test proving
   P1 never reaches P3 sinks passes in CI.
3. Capacity formulas recomputable from assumptions block alone.
4. DR restore rehearsal evidence linked from what-broke.md before P7 exit.
