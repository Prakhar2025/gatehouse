# 02 Product Specification

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Depends on | 01-vision |
| Last updated | 2026-08-24 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft |

## 1. Product Definition

One sentence: Gatehouse screens every risky inbound signal reaching a household,
investigates it like a fraud analyst, and asks the family guardian to decide only
what genuinely needs a human.

The product has three surfaces:

1. Channels: how signals get in and how decisions get out (Telegram bot first,
   WhatsApp forwarding flow, email inbox).
2. Console: the web product (Next.js) where the guardian reviews the decision
   queue, evidence bundles, family circle status, and audit history.
3. Digest: scheduled summaries proving the quiet value ("14 screened, 12 silent
   blocks, 0 needed you").

## 2. Core Concepts

| Concept | Definition |
|---|---|
| Household | The unit of protection. One billing entity, one guardian role, N members |
| Guardian | Admin human. Receives escalations, makes gate decisions |
| Member | A protected person whose forwarded signals feed the household |
| Signal | Any inbound artifact submitted for screening: message text, screenshot, URL, phone number, payment request |
| Investigation | One agent run over one signal, producing a verdict and evidence bundle |
| Verdict | SAFE, SUSPICIOUS, SCAM, or NEEDS_HUMAN, each with confidence and reasons |
| Evidence bundle | Structured, explainable record: claims checked, graph findings, engagement transcript, screenshots, recommended action |
| Gate event | An escalation to the guardian requiring a decision: allow, warn member, block/report |
| Threat graph | Privacy-preserving cross-household graph of hashed identifiers and scam patterns |
| Country pack | Locale bundle: payment rail rules, scam script library, language coverage |

## 3. User Journeys

### Journey A: The forward (primary loop, must be flawless)

1. Father receives WhatsApp message: "Your SBI KYC expires today. Verify here:
   https://sbi-kyc-alert[.]top"
2. He long-presses, forwards to the Gatehouse bot his son added to his contact.
3. Gatehouse ingests, triages: DECISION class. Verification agent extracts the
   claim "SBI KYC expires today" and the URL. Checks: domain age 2 days, not an
   SBI domain, pattern matches known kit family. Graph agent finds the URL hash
   seen in 11 other submissions this week. Engage agent optionally opens a
   controlled chat with the number behind the link.
4. Verdict: SCAM, confidence 0.97. Guardian gets one notification with a compact
   card and a full evidence bundle in console.
5. Guardian taps "Warn dad": system sends father a plain-language warning he can
   show others. Event joins the threat graph. Audit log updated.

Target: forward to verdict under 30 seconds p95. Notification copy under 280
characters. Evidence bundle complete regardless of whether guardian opens it.

### Journey B: The quiet week

Guardian opens Telegram on Sunday: digest card. "18 signals screened. 15 safe
(newsletters, delivery updates). 3 auto-resolved scams, evidence archived. You
were needed 0 times." This journey sells the product better than any feature list.

### Journey C: The ambiguous case (trust-building moment)

A real bank offer message that looks scammy. Triage: NEEDS_HUMAN. Verify agent
checks the sender against the bank's official SMS sender ID registry entry in the
India pack, confirms legitimate short code, domain matches registrar record.
Verdict: SAFE with receipts shown. Guardian learns the system does not cry wolf.

### Journey D: Onboarding (under 3 minutes)

1. Guardian signs in with Google/OAuth on console.
2. Creates household "Sharma Family", invites via link.
3. Adds the Gatehouse bot contact to each member's phone (guided steps with
   screenshots per platform).
4. Runs the built-in self-test: sends three demo messages, sees three verdicts.
   Trust established before any real event.

### Journey E: Payment request gating

Member shares a UPI collect request screenshot. Triage detects payment intent.
Verify parses VPA, checks handle against pack rules (merchant VPA format, known
mule patterns), graph check on the payee hash, verdict card shows exactly why to
pay or not pay. System never touches the payment itself.

## 4. Feature Set: v1 Scope

### F1 Screening pipeline (core)

Multi-channel intake, deduplication, language detection, PII minimization at the
boundary, triage classification into NOISE / INFO / SCREEN / DECISION / EMERGENCY.
Noise closes silently. Info logs to digest. Screen triggers investigation.
Decision and Emergency escalate immediately (EMERGENCY adds urgency styling and
repeat notification).

### F2 Investigation engine (agent system)

Five Strands agents per doc 04: Triage, Verify, Graph, Engage, Guardian. Tool
contracts, allowlists, and budget caps defined there. Structured output verdicts
only. Every run writes an immutable audit record.

### F3 Evidence bundles

Bundle contains: original signal (redacted view), extracted claims with check
results, URL/domain report (age, reputation, kit-family match), identifier graph
findings (hashed), engagement summary if any, verdict with confidence and reason
codes, recommended action text in the member's language, timestamps and costs.
Exportable as shareable link and PDF (PDF post-v1).

### F4 Family circle

Household management: members, roles, linked devices/channels. Guardian can send
plain-language warnings to a member ("This is a fake bank message. Do not click.
Real banks never rush you."). Member panic button: forward with a keyword that
forces immediate escalation with priority routing.

### F5 Digests and notifications

Telegram-first notifications with inline decision buttons. Daily digest at a
guardian-chosen hour. Weekly trust report (screened counts, blocks, false-gate
reports if any). Notification copy templates versioned in repo, translatable.

### F6 Console (doc 10 details)

Login, dashboard, decision queue with keyboard-first review, signal detail with
evidence bundle viewer, graph visualization for connected events, circle
management, settings (quiet hours, thresholds, language), audit log.

### F7 Evaluation harness (doc 07)

Adversarial test set generation, replay runner, metrics computation, regression
gate in CI. Metrics: precision, recall, false-gate rate, escalation precision,
latency percentiles, cost per investigation.

### F8 Trust center

Public pages: how it works, data handling, retention, security practices, the
honest limitations section. This doubles as hackathon Design-score ammunition and
company credibility.

## 5. Out of Scope for v1 (explicit)

Voice call answering, OS-level SMS auto-reading, in-app keyboards, autonomous
payment blocking, enterprise admin features, native mobile apps (console is
responsive web; Telegram is the mobile surface), PDF export, languages beyond
English + Hindi + one more Indian language at launch (pack architecture supports
more).

## 6. UX Principles

1. Never make the guardian read raw agent output. Cards and reason codes only.
2. Every notification carries an action. Every action is one tap or one key.
3. Show receipts. Confidence is always paired with the two strongest pieces of
   evidence, not percentages alone.
4. Quiet by design: batch anything below escalation threshold into digests.
5. Language: guardian chooses UI language; member-facing warnings localized.
   v1 ships English + Hindi.

## 7. Acceptance Criteria for v1 (product level)

1. A stranger can onboard a household end-to-end without help in under 5 minutes.
2. Forward-to-verdict p95 under 30 seconds on Telegram.
3. Decision queue empty-state communicates the quiet week story.
4. Every escalation resolvable entirely from the notification card.
5. Evidence bundle answers: what came in, what we checked, what we found, why
   this verdict, what you should do.
6. Zero notifications for noise. Verified by eval harness assertion.
7. Audit log reconstructs any investigation deterministically from stored records.
