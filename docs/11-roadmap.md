# 11 Roadmap and Build Protocol

## Document Control

| Field | Value |
|---|---|
| Version | 0.2.0 |
| Status | Draft for owner review |
| Owner | Prakhar Shukla |
| Depends on | all prior docs |
| Last updated | 2026-08-24 |

## Changelog

| Version | Change |
|---|---|
| 0.2.0 | Added the honest scale-up truth section (P8 is a horizon, not a step), post-P8 product eras, money/spend policy, and what "done company" means. Phase exit criteria unchanged |
| 0.1.0 | Initial draft |

## 0. Operating Model

Phase-gated like the Sentinel build: build -> verify -> push -> report -> wait
for owner go. Phases have exit criteria, not dates. The hackathon deadline
(Sep 14, 2026) is a checkpoint we hit mid-journey with submission-ready
artifacts; the product roadmap continues past it unchanged.

## 0.5 The Honest Truth About "Just 8 Steps" (read this, owner)

The phases P1-P7 are the construction plan for ONE working system: the v1
product with real households protected, deployed on AWS, measured honestly.
That system is genuinely valuable: it is the hackathon entry, the portfolio
masterpiece, the launchable seed, and the demo that opens doors.

But P8 is not a "step". It is a HORIZON with no finish line, because a product
that fights an adaptive criminal economy is never done:

- Scam scripts mutate weekly; packs, lexicons, and thresholds need forever-maintenance
- The threat graph gets smarter only if someone keeps feeding and tuning it
- Channels change policies, models get deprecated, platforms drift
- Users churn without new surface area (voice-note screening, more languages,
  community circles, bank integrations)

So the honest shape of the journey after v1 looks like ERAS, not steps:

| Era | What it contains | Exit condition |
|-----|------------------|----------------|
| Era 1: v1 live (P1-P7) | Working system, measured, submitted, soak households protected | Launch checklist signed (doc 09 section 7) |
| Era 2: hardening + growth (post-launch months 1-3) | WhatsApp GA, Chrome extension, second country pack, pricing experiment, first 100 paying guardians, external pen test | First revenue + churn below target |
| Era 3: platform (months 3-12) | Threat-intel API design partners (banks), white-label regional deployments, SOC 2 groundwork, team hiring decision, voice-transcript screening | B2B line item exists OR clear evidence to pivot |
| Era 4: company (year 1+) | Fundraise or bootstrap decision, multi-region graph, regulator engagement, category leadership in personal fraud defense | This era never closes while the company lives |

Million-dollar outcome is a real possibility from this foundation, but it is
bought with Eras 2-4 execution (growth, retention, distribution, partnerships),
not with finishing P7. P7 buys you the RIGHT TO PLAY. Anyone who tells you
eight steps ends at a million dollars is selling slop; we are not.

## 1. Phase Definitions

### P0 Design Lock (current)
Scope: docs suite finalized, repo initialized, charter active, PR/FAQ written,
API spec drafted, testing strategy and risk register live.
Exit: owner approves docs (batch OK); versions bumped to 1.0.0; git history
clean; dependency toolchain installed and verified latest stable (done Aug 24).

### P1 Skeleton
Scope: repo scaffold (src layout, pyproject strict, ruff+mypy+pytest wired,
GitHub Actions CI green), Makefile targets, config module, structured logging,
MIT LICENSE, README skeleton, country-pack schema + India pack v0 (rail
grammars, 5 issuer YAMLs, scam lexicons en/hi), eval harness scaffolding with
offline deterministic mini-set (30 cases), Docker base image verified locally.
Exit: `make check` green in CI; harness runs mini-set offline with mocked
agents; pack schema validates; clean checkout works on a fresh clone.

### P2 Core Agents
Scope: shared Pydantic schemas, fencing layer complete + unit-tested,
triage/verify/graph agents per contracts against Bedrock models, orchestrator
with idempotency, mock model provider mode (full loop runs offline), spend
meter module, contract tests generated from doc 04 schemas.
Exit: 480-case dev split runs end-to-end LOCAL_MOCK; schema validation 100
percent; nightly GitHub Action replays subset green two nights running.

### P3 Channels + Live Investigator Loop
Scope: Telegram end-to-end (webhook Lambda, binding flow, escalation cards,
callbacks, /panic, digests), WhatsApp webhook skeleton behind flag, email
intake, EventBridge wiring, case store + evidence bundles persisted,
notification service with quiet hours, engage_agent behind household flag.
Exit: Journey A completes on real Telegram under 30s p95 across 50 sends;
channel test matrix (doc 05 section 7) green; duplicate-forward budget
protection proven; spend meter shows real per-case costs within budget.

### P4 Deployment
Scope: AgentCore Runtime packaging + staging deploy via starter toolkit, SAM
stacks for gateway/tables/bus, observability pipeline with traces per agent
step, chaos tests for failure matrix rows 1-7, model routing verification
ritual executed and appended to doc 03 section 8, canary trip drill forced in
staging.
Exit: staging URL serves full loop; traces reconstruct any case; chaos suite
green; nightly evals green consecutive nights; rollback rehearsed once.

### P5 Console
Scope: Next.js app per doc 10 (auth, dashboard, queue keyboard flow, case
detail bundle viewer, circle, settings, audit), OpenAPI-typed client from doc
14 spec, locale files en/hi, Lighthouse budgets enforced in CI.
Exit: doc 10 section 8 acceptance criteria pass; console drives real staging
cases including decisions feeding graph commits.

### P6 Evals + Soak + Honesty
Scope: full 600-case set final generation, first sealed hold-out opening
(sanity run), threshold calibration on dev split with published pre/post, soak
households onboarded (builder family + 2 more), weekly soak report automation,
failure taxonomy draft from REAL misses, cost report.
Exit: metrics table populated with Wilson CIs; false-gate rate <= 5 percent on
dev split; soak running clean 7+ days; taxonomy document exists from real
cases only.

### P7 Release + Submission
Scope: second hold-out opening (final numbers), README final (results,
limitations, architecture diagram), trust center live, video produced per doc
12 script and acceptance criteria, builder.aws.com bonus posts published,
Devpost submission filed EARLY (target Sep 10), launch announcement assets.
Exit: submission receipt; release tag cut; status page live; doc 09 section 7
checklist fully signed.

### P8 Post-Launch Horizon (Era 2 entry)
Scope as defined in section 0.5 table: hardening, growth mechanics, second
pack, pricing experiments, design-partner conversations. Detailed planning
happens at P7 exit with soak data in hand; pre-planning further now would be
speculation wearing a roadmap costume.

## 2. Verification Standards per Phase

`make check` = ruff format check + ruff lint + mypy strict + pytest fast suite.
Phase-specific additions listed in exit criteria. Coverage floors: 85 percent
overall, 95 percent on fencing/orchestrator/spend/redaction modules. Nightly CI
= full offline eval + chaos spot checks. No phase exits with known-red nightly.

## 3. Reporting Protocol

Per phase completion the team reports: what was built, verification output
(pasted, not paraphrased), what broke (appended simultaneously to
docs/what-broke.md), budget spent to date, and the single riskiest observation
of the phase. Owner reviews, then says go.

## 4. Change Control

Docs: version bump + changelog line per edit; contract changes (doc 04
schemas, doc 14 endpoints) require eval/test impact notes before merge. Pack
changes require regression gate run. Prompt changes are code changes: PR +
nightly green required. Emergency hotfix path documented in runbooks,
retro-documented within 24h.

## 5. Money Policy (owner constraint: zero non-AWS spend)

Everything ships on AWS promo credits plus free tiers. Verified cost map:
Vercel Hobby free, Telegram Bot API free, SES free tier covers digest volume,
GitHub Actions free for public repos, DynamoDB/Lambda/EventBridge near-zero at
v1 scale inside credits, AgentCore + Bedrock covered by requested credits
($50 hackathon credit request submitted Aug 24; existing builder credits as
buffer). Charter section 8 budget rules enforce Bedrock discipline. No paid
domains until revenue (gatehouse.in parked only when justified), no paid SaaS
tools, no paid stock assets. The build is engineered so zero external rupees
are required through P7, by design, not luck.

## 6. Definition of Done (global)

A feature is done when: implemented per contract, type-checked, tested (unit +
integration where applicable), evaluated (if verdict-path touching), observed
(trace spans present), documented (doc updated + changelog line), and demoable
from clean checkout via make targets. Anything less is WIP and does not reach
main.
