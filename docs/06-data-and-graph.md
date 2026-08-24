# 06 Data Model and Threat Graph

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Depends on | 03-architecture, 04-agent-contracts |
| Last updated | 2026-08-24 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft |

## 1. Storage Layout

Single-table DynamoDB design (table: gatehouse-main) plus two purpose-built
stores. On-demand billing until scale says otherwise.

```
PK                      SK                          Entity
----------------------  --------------------------  ---------------------------
HH#<household_id>       PROFILE                     household profile/settings
HH#<household_id>       MEMBER#<member_id>          member record + bindings
HH#<household_id>       CASE#<case_id>              case lifecycle + verdict ref
HH#<household_id>       DIGEST#<yyyy-mm-dd>         daily counters
CASE#<case_id>          SIGNAL                      signal header + fenced refs
CASE#<case_id>          FINDING#<seq>               verification/graph findings
CASE#<case_id>          ENGAGE#<session>            engagement summary + ref
CASE#<case_id>          BUNDLE                      evidence bundle (verdict pkg)
CASE#<case_id>          AUDIT#<seq>                 append-only audit events
VAULT#<case_id>         ITEM#<seq>                  sealed PII items (KMS)
SPEND#<yyyy-mm-dd>      METER#<agent>               spend meter rows
GRAPH#NODE              ID#<kind>#<h64>             graph node (hashed ids)
GRAPH#NODE              EDGE#<kind>#<h64>           adjacency entries w/ weights
PATTERN#FAMILY          <family_id>                 scam kit family registry
PACK#<region>           VERSION#<v>                 country pack manifest ref
OPS#ALERT               <alert_id>                  ops alerts (budget breaker)
```

GSI-1: inverted access for guardian queues (PK=member guardian id, SK=case state).
GSI-2: pattern family lookup by indicator hash family prefix.

TTL policy (privacy by construction):
- Raw signal fenced payload refs: 30 days
- Vault items: 90 days (only if case unresolved, else purged at resolution)
- Engagement transcripts: 180 days (threat intel value) then expired
- Audit records: 400 days (compliance posture), evidence bundles 400 days
- Digest counters: indefinite (aggregates only, zero content)

## 2. Evidence Bundle Schema (the product's core artifact)

```
EvidenceBundle:
  bundle_id, case_id, household_id, created_at, pack_version, prompt_versions{}
  signal_view:            redacted render of original (text/media ref)
  claims[]:               claim_id, text, check_type, result, evidence_ref
  url_reports[]:          url_hash, domain, age_days, dns_class, reputation,
                          kit_family_match, screenshot_ref
  graph_finding:          GraphFinding (doc 04 schema) or unavailable flag
  engagement_summary:     EngagementResult or skipped flag with reason
  verdict_block:          Verdict, confidence, reason_codes[], thresholds_used
  recommended_action:     action_catalog id + localized human text
  cost_block:             model calls, tokens, USD estimate per agent
  decision_record:        guardian decision, actor, timestamp, latency
  integrity:              sha256 of canonical JSON, chain hash to prior bundle
```

The bundle is immutable once written; corrections create successor bundles with
parent references. Console renders bundles read-only from this schema. The
integrity chain makes tampering detectable, which matters later for bank/regulator
sharing stories.

## 3. Threat Graph Design

Purpose: the cross-household memory that turns isolated forwards into a network
defense. Sentinel lesson applied globally: fraud infrastructures reuse identifiers;
reuse is the signal.

Nodes: hashed identifier kinds: PHONE, VPA (UPI handle), DOMAIN, URL_PATH, BANK_ACCT,
EMAIL, UTR_REF, DEVICE_FINGERPRINT (future), WHATSAPP_LID (future).
Edges: CO_OCCURS (same case), FUNDS_TO (payment request linkage), VARIANT_OF
(kit family similarity), REPORTED_BY (guardian confirmations).

Node record:
```
id: kind + salted hash (HMAC-SHA256, salt in KMS, rotated yearly with rehash job)
first_seen, last_seen, event_count, distinct_households_seen,
taint: {score, updated_at}, families[], region_codes[]
edge list truncated to top-K by weight with total_weight summary
```

Taint scoring (deterministic, documented):
```
taint(n) = clamp( base_confirm + Σ_edges w(e) * decay(hops) * time_decay(days) )
base_confirm: guardian-confirmed scam = 0.9, pack-listed malicious = 0.8,
model-verdict SCAM = 0.6 (unconfirmed by human), SUSPICIOUS contributes 0.25
decay(hops) = 0.6^hops   (Sentinel lineage)
time_decay = exp(-days_since_last_event / 45)
```
Constants live in pack config; changes ship through eval regression gate.

Privacy mechanics: hashes are HMAC outputs, not plain digests, defeating rainbow
reconstruction of phone numbers. Cross-region queries only return aggregates unless
both households opted into regional intel sharing (default ON at signup in
high-fraud regions, OFF available, honest toggle).

Cold start honesty: graph coverage note printed in every bundle ("network memory:
N events, M households, region coverage X") so early users see why a clean graph
check is weak evidence. This disclosure doubles as eval-harness input.

Write path: orchestrator commits graph updates ONLY after final verdict, in one
idempotent transaction batch keyed by case_id (retry-safe). No mid-investigation
writes: a failed case must leave zero graph residue.

## 4. Country Pack Registry

Structure (versioned artifacts in S3, manifest in table):

```
packs/in/v3/
  manifest.yaml         region, languages, rail configs, version, checksum
  rails/upi.yaml        VPA grammar, collect request fields, merchant patterns
  issuers/sbi.yaml      official domains, SMS sender IDs, KYC policy excerpts
  issuers/*.yaml        all major banks + RBI + govt bodies
  lexicons/scam.yaml    urgency phrases, script fragments, per language
  actions/catalog.yaml  recommended action templates, localized strings
  scoring.yaml          taint constants, threshold defaults
```

Pack lookup is a tool (pack_lookup) with explicit version pinning per case so any
bundle replays exactly against the pack version that judged it. Community
contribution path documented for v1.1 (PR against packs repo with CI validation),
which seeds the open-source moat.

## 5. Retention, Deletion, Export (user rights)

- Household deletion: cascading purge across tables, vault KMS key destroyed,
  graph nodes retain hashes but household attribution dropped (aggregate counts
  remain, content gone), deletion certificate issued.
- Data export: guardian can pull full JSON export of household cases/bundles.
- Consent ledger: per-member record of what is shared (regional intel toggle,
  engagement opt-in) with timestamps.

## 6. Access Patterns (verified against table design)

| Pattern | Access | Used by |
|---|---|---|
| Open case by id | PK=CASE#id, all SKs | Investigator, console detail |
| Guardian queue | GSI-1 by member+state | Console dashboard |
| Dedupe check | content hash index table (hash->case, TTL) | Gateway |
| Graph neighbors | GRAPH#NODE pk + edge SKs | graph_agent |
| Digest rollup | HH pk + DIGEST sk range | Notification service |
| Spend alarm scan | SPEND pk | Budget breaker cron |
| Replay bundle | CASE pk + BUNDLE + AUDIT range | Evals, support |

Every pattern above must be exercised by an integration test before prod signoff
(doc 07 exit criteria), keeping the classic single-table failure mode (forgotten
access patterns discovered in prod) out of this build.
