# 13 PR/FAQ (Working Backwards)

## Document Control

| Field | Value |
|---|---|
| Version | 0.1.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Method | Amazon working-backwards process: the press release is written before the product exists. If this document does not excite real customers, the product is wrong, not the prose |
| Last updated | 2026-08-24 |

## Changelog

| Version | Change |
|---|---|
| 0.1.0 | Initial draft |

---

## PART 1: The Press Release (written as if launching, dated in the future)

### Gatehouse Launches Autonomous Fraud Defense for Families: Forward Any Suspicious Message, Get an Expert Investigation in Seconds

**Bengaluru, November 2026.** Gatehouse today announced general availability of
its household fraud-defense agent, giving every family what only fraud analysts
at large companies have had until now: a tireless investigator that examines
every suspicious message, link, payment request, and unknown contact before it
can do harm.

Scams stole an estimated 1.03 trillion US dollars from people worldwide last
year, and one in four people lost money to fraud. The moment of attack is
always the same: one person, alone, reading one convincing message on their
phone. Caller ID apps label phone numbers. Banks alert customers after money
has already moved. Nobody defends the actual moment.

"Every family has someone who becomes the human firewall," said Prakhar Shukla,
founder of Gatehouse. "That person checks links at midnight, fields panicked
calls about KYC deadlines, and warns relatives about investment groups. We
built Gatehouse so that person finally has a machine that works while they
sleep."

Gatehouse works through channels families already use. Any family member can
forward a suspicious message to the Gatehouse bot on Telegram or WhatsApp. In
seconds, a team of AI agents investigates like a professional analyst:

- **Verify** checks claims against authoritative references: real bank sender
  registries, official government domains, payment rail rules.
- **Remember** consults a privacy-preserving threat graph: if this link,
  account, or number has attacked other families, the new victim sees exactly
  that evidence.
- **Engage**, when needed, talks to the suspected scammer itself inside strict
  guardrails, confirming intent and collecting evidence without exposing any
  real personal data.
- **Escalate**: most messages are handled silently. Only genuine decisions
  reach the family guardian, as one notification card with plain-language
  reasons and recommended actions. The system never moves money, never blocks
  anything by itself, never reads anything without consent. Humans decide;
  Gatehouse investigates.

Families see their protection record in a simple console: everything screened,
everything silently resolved, every verdict explainable down to the original
evidence. The detection core is open source so security researchers and
regulators can audit exactly how decisions are made.

"My father forwarded a fake bank message yesterday," said Meera, an early user
in Pune. "By the time he finished reading it, my phone already showed why it
was fake: the domain was two days old and eleven other families had received
the same message. He shows that screenshot to everyone now."

Gatehouse is free for one family circle with manual forwarding. The Guardian
plan adds real-time autonomous investigation, scammer engagement, priority
escalation, and extended family circles at 99 rupees per month. Regional
launch begins in India with packs for UPI and major banks; Brazil, Nigeria,
Vietnam, and the Philippines follow within the year.

**How to start:** add the Gatehouse bot, forward any message you are unsure
about, and run the built-in family self-test. Nothing harmful gets past the
gate.

---

## PART 2: Frequently Asked Questions (the internal hard questions)

### Customer and market

**Who is the customer, precisely?**
The Family Guardian: 20 to 35, digitally fluent, manages payments and tech
support for parents, in a high-fraud-exposure market (India first). Secondary:
the Protected Member (parents 50+) whose behavior changes zero; they gain a
contact, not an app. Willingness to pay is proven by Truecaller Premium tiers
and Family Protection launch (March 2026); our wedge is investigation-grade
depth those products structurally lack.

**How big is the market, honestly?**
GASA estimates USD 1.03T global scam losses (2024), USD 688B in Asia-Pacific
alone. India reported INR 22,845 crore cyber-fraud losses across 36.4 lakh
cases (MHA, Parliament reply). Bottom-up: 1M guardians at INR 99/month is
roughly USD 60M ARR in one country. This is a venture-scale problem with a
subscription-shaped solution.

**Why will people change behavior to adopt this?**
They already perform the behavior manually: forwarding suspicious things to
children and siblings ("beta, is this real?"). Gatehouse formalizes an existing
habit instead of inventing one. Adoption friction is adding one contact.

### Product mechanics

**What happens when the agent is wrong?**
Two failure classes, both engineered: false gates (legitimate flagged) are
capped by calibration targets (false-gate rate under 5 percent, measured on
held-out sets and published), and misses (scam passed silently) surface when
any other household reports the same indicator, retroactively warning every
household that received it. Every bundle carries confidence and reason codes;
guardians can override, and overrides retrain thresholds honestly (dev split
only).

**Why would a scammer not just adapt?**
They do; that is the design assumption. Static blocklists lose arms races.
Gatehouse's defense is investigation (fresh kits get fresh verdicts) plus
network memory (reuse gets caught cross-household). Scammer economics degrade
when reuse burns infrastructure faster; that is measurable over time via taint
decay curves, published quarterly.

**Is engagement legal and safe?**
No impersonation of real people or officials, no minors personas, no
transmission of any real data, hard stop conditions, opt-in per household,
transcripts visible to the guardian. Legal review of ToS language precedes
public launch (checklist item, doc 08). Engagement is a capability we can ship
without, and defaults respect that.

**Does this read all my messages? (privacy)**
No. Gatehouse sees only what is explicitly forwarded plus channel metadata
needed for binding. There is no OS-level SMS reading, no keyboard, no inbox
access. Identifiers enter the threat graph only as HMAC hashes. Retention TTLs
are public. Deletion is mechanical and certified.

### Business

**How does this make money?**
Freemium subscription (guardian plan INR 99/mo), later: anonymized
threat-signal API for banks and fintechs (design partners post-launch), white-
label regional bank deployments. Open-core boundary documented: detection core
MIT, hosted investigation + shared graph paid.

**Unit economics at small scale?**
Mean cost per investigation budgeted at USD 0.02 (doc 09 section 6). At 1k
households x 50 signals/mo x 20 percent investigate rate, model spend is about
USD 200/month against potential gross of USD 49k to 99k monthly at target ARPU.
Infrastructure is serverless near-zero idle cost.

**What is the moat?**
Three compounding layers: the cross-household hashed threat graph (data
network effect), country packs maintained with community contributions (content
moat), and honest measurement culture producing regulator-grade audit trails
(trust moat). None are copy-paste features for an incumbent whose architecture
assumes caller-ID-scale signals rather than message-level investigation.

**Why has no one built this?**
Telco-side players refuse B2C by business model; caller-ID players optimize
number reputation, not message understanding; banks act post-transaction by
regulatory design. A consumer agent company needed three things that converged
only recently: cheap reliable LLM agents, managed agent infrastructure
(AgentCore), and a founder with production fraud-detection experience who is
also the family firewall.

### Risks

**Biggest risks and mitigations, ranked?**
1. Prompt injection breakthroughs: fencing layer, canaries, tool allowlists,
   blast-radius-free architecture (no dangerous tools exist).
2. Trust collapse from one bad verdict: explainability-first bundles, override
   ledger, public metrics with limitations.
3. Channel platform policy shifts: multi-channel abstraction, Telegram parity,
   API-first escape hatches.
4. Single-builder operational risk: runbooks, alarms designed async-first,
   chaos-tested degradation, breaker automation.

**What would make us kill this?**
Soak-phase reality check: if guardian escalation precision stays low after
calibration (guardians ignoring cards), the core loop fails and we revisit the
interaction model before spending on growth. Kill criteria defined now: fewer
than 60 percent escalation agreement after four weeks of soak tuning.
