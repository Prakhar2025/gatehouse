# 01 Vision

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Last updated | 2026-08-24 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft |

## 1. Problem Statement

Fraud is an industrialized global economy that attacks households one message at a
time. The Global Anti-Scam Alliance estimates worldwide scam losses at
USD 1.03 trillion in 2024, with roughly one in four people losing money to scams
or identity theft in a twelve-month window. Only about 4 percent of victims fully
recover their funds. Attack volume is rising because generative AI has collapsed
the cost of producing convincing, personalized fraud in any language.

Every household already has a de facto security role: the tech-capable family
member who fields calls from parents about strange messages, checks links, warns
about fake KYC deadlines. That person is a human firewall with no tooling,
operating after the fact, one relative at a time.

Existing defenses sit in the wrong layer:

- Telco and network side systems (for example Apate.ai) divert and engage scam
  calls at carrier scale. They explicitly do not serve individuals.
- Caller ID platforms (Truecaller, 450M+ users) label numbers using community
  reports. Truecaller launched Family Protection in India in March 2026,
  validating family-circle protection as a product category. But caller ID sees
  only the calling party. It cannot read the WhatsApp message, open the link,
  verify the claim against issuer ground truth, or investigate a fresh phishing
  kit registered yesterday.
- Bank transaction alerts fire after money moves. Prevention window closed.

The unprotected layer is the message itself, before the human engages with it.
That is Gatehouse's layer.

## 2. Product Thesis

Gatehouse is an always-on autonomous agent for the household. It receives risky
inbound signals through forwarding channels, investigates each like a professional
fraud analyst would (claim verification against authoritative sources, identity
linkage across events, optional controlled engagement with the suspected scammer),
and escalates only genuine decisions to the family guardian with an explainable
evidence bundle. Everything else is handled silently and logged.

The design matches what autonomous agents are actually good at in 2026:
high-volume triage of unstructured text, tool-driven verification, patient
multi-turn engagement, and disciplined escalation instead of autonomous action on
money or messages.

Tagline: Nothing harmful gets past the gate.

## 3. Who It Is For

Primary persona: the Family Guardian. Age 20 to 35, digitally fluent, manages OTPs,
bill payments, and tech support for parents. Lives in India, Brazil, Nigeria,
Vietnam, Philippines, or any high-fraud-exposure market. Willing to pay small
monthly amounts for family safety; already pays for Truecaller Premium tiers or
cloud storage.

Secondary persona: the Protected Member. Parents, often 50+, targeted by KYC
expiry scams, digital arrest scams, investment groups, lottery messages, courier
impersonation. They change nothing about their behavior. Protection must not
require app installs on their side beyond channel linkage.

Tertiary persona (post-launch): community operators. Housing society WhatsApp
admins, school parent groups, small business owners who screen for whole groups.
This is the expansion wedge into B2B2C.

## 4. Why Now

1. LLM agents became reliable enough for unstructured triage with tool use
   (Strands Agents SDK, AgentCore Runtime, managed memory and observability).
2. Scam production industrialized with AI voice cloning and personalized
   scripting. Defenses built on static blocklists lose the arms race by design.
3. Family-protection willingness to pay was just validated by incumbents
   (Truecaller Family Protection, March 2026), while the investigation-grade
   personal layer remains empty.
4. Regulation and bank infrastructure (India's 1930 helpline, mule-account
   registries) prove institutional demand for pre-transaction signals, which is
   the future B2B revenue layer.

## 5. Market

Bottom-up: India alone reported INR 22,845 crore lost to cyber financial fraud in
2024 across 36.4 lakh reported cases (Ministry of Home Affairs data, Parliament
reply). Reported losses understate reality. A household product priced at INR 49
to 99 per month needs roughly 1M paying guardians for a USD 60M to 120M ARR
business in one market. GASA's USD 1.03T global loss figure defines the ceiling.
Asia-Pacific alone was estimated at USD 688B in 2024.

Initial wedge: urban Indian families with UPI-heavy payment behavior. Expansion:
Brazil (Pix), Nigeria, Vietnam, Philippines (per GASA loss concentration), then
US/EU elder-protection segment where competitors charge USD 10+ per month.

## 6. Competitive Landscape

| Player | Layer | What they do | Why Gatehouse is different |
|---|---|---|---|
| Truecaller (+ Family) | Caller ID | Community blocklists, call screening, family alerts | Sees who calls, not what is said. No message-level investigation, no verification tools, no engagement |
| Apate.ai | Telco network | Diverts scam calls to conversational bots at carrier scale | Explicitly refuses consumer products. Call-only, no messaging channels |
| Cloudbrink, spam blockers | Device | Static filters | Blocklist era technology, no reasoning, no context |
| Bank alerting | Post-transaction | Notify or freeze after initiation | Prevention window already closed when they act |
| Norton/Bitdefender family kits | Device security | App and web filtering | Not fraud-native, no message understanding |

Gatehouse combines four capabilities no incumbent holds together: message-level
understanding, claim verification against authoritative sources, cross-event
identity graphing with privacy-preserving hashes, and controlled scammer
engagement for evidence. The moat compounds: every investigated event enriches a
privacy-preserving threat graph that makes every other household safer, the
classic defensive network effect.

## 7. Product Principles

1. Recommend, never act. The agent never moves money, never sends messages as a
   human, never blocks silently. It gates attention, not agency.
2. Explain everything. Every verdict ships with an evidence bundle a non-technical
   guardian can understand and a regulator could audit.
3. Safety without surveillance. Hashed identifiers, minimal retention, no content
   mining beyond fraud defense, explicit consent model per member.
4. Silence is the default. A good week produces zero notifications. Escalation
   quality is the product.
5. Global core, local packs. Detection logic is locale-independent; payment rails,
   scam script libraries, and language models ship as country packs starting with
   India.

## 8. Business Model (launch shape)

- Free tier: family circle up to 3 members, manual forward-in screening, monthly
  digest, community threat alerts.
- Guardian plan (INR 99/mo or local equivalent): real-time autonomous
  investigation, engagement mode, priority escalation, evidence export, circle of
  5+ members.
- Later: anonymized threat-signal API for banks and fintechs (the Sentinel
  lineage becomes revenue), white-label for regional banks.

Open source strategy: the detection core (schemas, scoring rules, eval harness)
ships MIT licensed for trust and auditability. Hosted investigation infrastructure
and the shared threat graph are the paid hosted layer. This follows the standard
open-core security playbook.

## 9. Success Criteria

Product v1 is successful when all hold true:

1. Deployed production system on AWS AgentCore with a public URL, real ingestion
   channel, and measured latency under 30 seconds from forward to verdict.
2. Held-out adversarial evaluation with published precision, recall, false-gate
   rate, and cost per investigation, plus honest limitations.
3. At least 3 real households protected for 2+ weeks including the builder's own.
4. Zero incidents of the system acting autonomously on money or messages.
5. Hackathon submission filed early with bonus post published.

## 10. Non-Goals for v1

- Voice call interception (telco-controlled, legally complex; engagement of voice
  scams arrives via transcript forwarding first).
- Autonomous blocking of payments at bank level (requires bank partnerships).
- In-app keyboards or OS-level SMS reading (store policy risk); channel strategy
  starts with forwarding bots, see doc 05.
- Enterprise SOC features. Households first.

## 11. Risks and Mitigations (top level)

| Risk | Severity | Mitigation |
|---|---|---|
| Prompt injection via forwarded scam text | Critical | Instruction firewall, content fencing, canary tokens, tool allowlists. Doc 08 |
| False gates destroying trust | High | Human-gated decisions, calibrated thresholds, false-gate rate as a tracked KPI with alerting |
| Channel ToS (WhatsApp automation) | Medium | Forwarding-based ingestion within normal user behavior, official APIs where available, Telegram parity channel |
| Privacy backlash | High | Hashed graph boundary, retention TTLs, public security page, open-source core for auditability |
| Model cost blowout | Medium | Spend meter, per-investigation budgets, circuit breakers. Doc 08 charter rules |
